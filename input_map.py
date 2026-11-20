# -*- coding: utf-8 -*-
"""Unified cross-platform Action / Input Mapping for PyAudioGaming.

Unifies PC keyboard (single keys & modifier chords), mouse, Android/iOS touch gestures
(``tap`` / ``swipe`` via ``Window``), and Gamepad (buttons, D-pad, triggers, sticks)
under clean named actions — with interactive rebinding, JSON persistence, and
screen-reader friendly descriptions.

Binding syntax examples:
- Keyboard: ``"space"``, ``"enter"``, ``"escape"``, ``"f2"``, ``"ctrl+s"``, ``"shift+left"``, ``"alt+enter"``
- Touch: ``"tap:1:2"`` (1 finger, 2 taps), ``"tap:1:2:left-play"`` (with zone),
  ``"swipe:left"``, ``"swipe:up:2"`` (2-finger swipe up), ``"swipe:right:1:center"``
- Mouse: ``"mouse:left"``, ``"mouse:right"``, ``"mouse:middle"``
- Gamepad: ``"pad:a"``, ``"pad:b"``, ``"pad:x"``, ``"pad:y"``, ``"pad:lb"``, ``"pad:rb"``,
  ``"pad:start"``, ``"pad:back"``, ``"pad:0"``, ``"pad:dpad_up"``, ``"pad:dpad_down"``,
  ``"pad:dpad_left"``, ``"pad:dpad_right"``, ``"pad:lx-"``, ``"pad:lx+"``, ``"pad:ly-"``, ``"pad:ly+"``,
  ``"pad:lt"``, ``"pad:rt"``
"""

import json
from pathlib import Path

from .timer import Timer

__all__ = [
	"InputMap",
	"GAMEPAD_BUTTON_ALIASES",
]

# Standard Xbox / SDL2 button indices
GAMEPAD_BUTTON_ALIASES = {
	"a": 0, "cross": 0,
	"b": 1, "circle": 1,
	"x": 2, "square": 2,
	"y": 3, "triangle": 3,
	"lb": 4, "l1": 4,
	"rb": 5, "r1": 5,
	"back": 6, "select": 6, "view": 6,
	"start": 7, "menu": 7,
	"ls": 8, "l3": 8,
	"rs": 9, "r3": 9,
}

_MOD_ALIASES = {
	"ctrl": ("lctrl", "rctrl"),
	"control": ("lctrl", "rctrl"),
	"shift": ("lshift", "rshift"),
	"alt": ("lalt", "ralt"),
	"lctrl": ("lctrl",),
	"rctrl": ("rctrl",),
	"lshift": ("lshift",),
	"rshift": ("rshift",),
	"lalt": ("lalt",),
	"ralt": ("ralt",),
}

_MOUSE_BUTTON_MAP = {
	"left": 0, "lmb": 0, "1": 0,
	"middle": 1, "mmb": 1, "2": 1,
	"right": 2, "rmb": 2, "3": 2,
}


def _normalize_binding(binding: str) -> str:
	return str(binding).strip().lower()


class InputMap:
	"""Maps named game actions to keyboard, touch gesture, mouse, and gamepad bindings."""

	def __init__(self, bindings: dict = None, deadzone: float = 0.35):
		self._bindings = {}  # action_name -> list[str]
		self._defaults = {}
		self.deadzone = max(0.05, min(0.95, float(deadzone)))
		self._prev_pad_state = {}
		self._prev_mouse_state = {}
		self._repeat_timers = {}
		self._joysticks = {}

		if bindings:
			for action, b_list in bindings.items():
				if isinstance(b_list, str):
					self.bind(action, b_list)
				else:
					self.bind(action, *b_list)
			self._defaults = {k: list(v) for k, v in self._bindings.items()}

	# ------------------------------------------------------------------
	# Binding management
	# ------------------------------------------------------------------
	def bind(self, action: str, *bindings: str):
		"""Add one or more bindings to ``action``."""
		act = str(action).strip()
		lst = self._bindings.setdefault(act, [])
		for b in bindings:
			nb = _normalize_binding(b)
			if nb and nb not in lst:
				lst.append(nb)
		return self

	def unbind(self, action: str, binding: str = None):
		"""Remove a specific binding from ``action``, or all bindings if ``binding is None``."""
		act = str(action).strip()
		if act not in self._bindings:
			return self
		if binding is None:
			self._bindings[act].clear()
		else:
			nb = _normalize_binding(binding)
			self._bindings[act] = [x for x in self._bindings[act] if x != nb]
		return self

	def rebind(self, action: str, old_binding: str, new_binding: str) -> bool:
		"""Replace ``old_binding`` with ``new_binding`` for ``action``."""
		act = str(action).strip()
		lst = self._bindings.get(act)
		if not lst:
			return False
		old_n = _normalize_binding(old_binding)
		new_n = _normalize_binding(new_binding)
		if old_n in lst:
			idx = lst.index(old_n)
			lst[idx] = new_n
			return True
		return False

	def set_bindings(self, action: str, bindings: list):
		act = str(action).strip()
		self._bindings[act] = [_normalize_binding(b) for b in bindings if str(b).strip()]
		return self

	def get_bindings(self, action: str) -> list:
		return list(self._bindings.get(str(action).strip(), []))

	def actions(self) -> list:
		return list(self._bindings.keys())

	def clear(self, action: str = None):
		if action is None:
			self._bindings.clear()
		else:
			self._bindings.pop(str(action).strip(), None)

	def reset_defaults(self):
		self._bindings = {k: list(v) for k, v in self._defaults.items()}

	# ------------------------------------------------------------------
	# Internal hardware helpers
	# ------------------------------------------------------------------
	def _get_joystick(self, index: int = 0):
		try:
			import pygame
			if not pygame.get_init():
				return None
			if not pygame.joystick.get_init():
				pygame.joystick.init()
			if index < 0 or index >= pygame.joystick.get_count():
				return None
			joy = self._joysticks.get(index)
			if joy is None or not joy.get_init():
				joy = pygame.joystick.Joystick(index)
				joy.init()
				self._joysticks[index] = joy
			return joy
		except Exception:
			return None

	def _check_modifiers(self, mods: list, wnd) -> bool:
		for m in mods:
			keys = _MOD_ALIASES.get(m, (m,))
			if not any(wnd.keyPressing(k) for k in keys):
				return False
		return True

	def _eval_pad_raw(self, spec: str, joy_idx: int = 0) -> float:
		joy = self._get_joystick(joy_idx)
		if joy is None:
			return 0.0
		try:
			if spec in GAMEPAD_BUTTON_ALIASES:
				btn = GAMEPAD_BUTTON_ALIASES[spec]
				return 1.0 if (btn < joy.get_numbuttons() and joy.get_button(btn)) else 0.0
			if spec.isdigit():
				btn = int(spec)
				return 1.0 if (btn < joy.get_numbuttons() and joy.get_button(btn)) else 0.0
			if spec.startswith("dpad_") and joy.get_numhats() > 0:
				hx, hy = joy.get_hat(0)
				if spec == "dpad_left":
					return 1.0 if hx < 0 else 0.0
				if spec == "dpad_right":
					return 1.0 if hx > 0 else 0.0
				if spec == "dpad_up":
					return 1.0 if hy > 0 else 0.0
				if spec == "dpad_down":
					return 1.0 if hy < 0 else 0.0
			# Analog axes
			axis_map = {
				"lx-": (0, -1), "lx+": (0, 1),
				"ly-": (1, -1), "ly+": (1, 1),
				"rx-": (2, -1), "rx+": (2, 1),
				"ry-": (3, -1), "ry+": (3, 1),
				"lt": (4, 1), "rt": (5, 1),
			}
			if spec in axis_map:
				ax_i, direction = axis_map[spec]
				if ax_i < joy.get_numaxes():
					val = float(joy.get_axis(ax_i))
					if spec in ("lt", "rt"):
						norm = (val + 1.0) * 0.5 if val < 0.0 else val
						return norm if norm >= self.deadzone else 0.0
					signed = val * direction
					return signed if signed >= self.deadzone else 0.0
		except Exception:
			pass
		return 0.0

	def _eval_binding(self, binding: str, wnd, mode: str = "pressed", repeat_ms: int = 0) -> bool:
		# 1. Touch tap: "tap:fingers:count[:zone]"
		if binding.startswith("tap:"):
			if mode == "released" or not hasattr(wnd, "tap"):
				return False
			parts = binding.split(":")
			fingers = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
			count = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
			zone = parts[3] if len(parts) > 3 and parts[3] else None
			try:
				return bool(wnd.tap(fingers=fingers, count=count, zone=zone))
			except Exception:
				return False

		# 2. Touch swipe: "swipe:direction[:fingers[:zone]]"
		if binding.startswith("swipe:"):
			if mode == "released" or not hasattr(wnd, "swipe"):
				return False
			parts = binding.split(":")
			direction = parts[1] if len(parts) > 1 else "right"
			fingers = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
			zone = parts[3] if len(parts) > 3 and parts[3] else None
			try:
				return bool(wnd.swipe(direction, fingers=fingers, zone=zone))
			except Exception:
				return False

		# 3. Mouse: "mouse:left|right|middle"
		if binding.startswith("mouse:"):
			btn_name = binding.split(":", 1)[1]
			idx = _MOUSE_BUTTON_MAP.get(btn_name)
			if idx is None:
				return False
			try:
				import pygame
				cur = bool(pygame.mouse.get_pressed()[idx])
			except Exception:
				return False
			prev = self._prev_mouse_state.get(idx, False)
			self._prev_mouse_state[idx] = cur
			if mode == "pressed":
				return cur and not prev
			if mode == "released":
				return (not cur) and prev
			return cur

		# 4. Gamepad: "pad:<spec>"
		if binding.startswith("pad:"):
			spec = binding.split(":", 1)[1]
			cur = self._eval_pad_raw(spec) >= self.deadzone
			prev = self._prev_pad_state.get(spec, False)
			self._prev_pad_state[spec] = cur
			if mode == "pressed":
				return cur and not prev
			if mode == "released":
				return (not cur) and prev
			if repeat_ms > 0 and cur:
				tm = self._repeat_timers.setdefault(binding, Timer())
				return tm.ready(repeat_ms, auto_restart=True)
			return cur

		# 5. Keyboard (single key or chord like "ctrl+shift+s")
		parts = [p.strip() for p in binding.split("+") if p.strip()]
		if not parts:
			return False
		mods, main_key = parts[:-1], parts[-1]
		if mods and not self._check_modifiers(mods, wnd):
			return False

		try:
			if mode == "pressed":
				return bool(wnd.keyPressed(main_key))
			if mode == "released":
				if hasattr(wnd, "keyReleased"):
					return bool(wnd.keyReleased(main_key))
				return False
			# pressing
			if repeat_ms > 0:
				return bool(wnd.keyPressing(main_key, t=int(repeat_ms)))
			return bool(wnd.keyPressing(main_key))
		except Exception:
			return False

	# ------------------------------------------------------------------
	# Public query API
	# ------------------------------------------------------------------
	def pressed(self, action: str, wnd) -> bool:
		"""Return True on the frame any binding of ``action`` is newly triggered."""
		for b in self._bindings.get(action, ()):
			if self._eval_binding(b, wnd, mode="pressed"):
				return True
		return False

	def pressing(self, action: str, wnd, repeat_ms: int = 0) -> bool:
		"""Return True while any binding of ``action`` is held (with optional ``repeat_ms`` throttle)."""
		for b in self._bindings.get(action, ()):
			if self._eval_binding(b, wnd, mode="pressing", repeat_ms=repeat_ms):
				return True
		return False

	def released(self, action: str, wnd) -> bool:
		"""Return True on the frame a binding of ``action`` is released."""
		for b in self._bindings.get(action, ()):
			if self._eval_binding(b, wnd, mode="released"):
				return True
		return False

	def any_pressed(self, actions, wnd):
		"""Return the first action name in ``actions`` that was pressed this frame, else ``None``."""
		for act in actions:
			if self.pressed(act, wnd):
				return act
		return None

	def axis(self, neg_action: str, pos_action: str, wnd) -> float:
		"""Return an axis value in ``[-1.0, 1.0]`` combining keyboard & gamepad sticks."""
		neg_val = 0.0
		pos_val = 0.0
		for b in self._bindings.get(neg_action, ()):
			if b.startswith("pad:"):
				neg_val = max(neg_val, self._eval_pad_raw(b.split(":", 1)[1]))
			elif self._eval_binding(b, wnd, mode="pressing"):
				neg_val = 1.0
		for b in self._bindings.get(pos_action, ()):
			if b.startswith("pad:"):
				pos_val = max(pos_val, self._eval_pad_raw(b.split(":", 1)[1]))
			elif self._eval_binding(b, wnd, mode="pressing"):
				pos_val = 1.0
		return max(-1.0, min(1.0, pos_val - neg_val))

	# ------------------------------------------------------------------
	# Interactive capture & screen-reader descriptions
	# ------------------------------------------------------------------
	def capture_next_binding(self, wnd, cancel_key: str = "escape"):
		"""Poll once for a newly pressed key/combo or gamepad button; returns binding string or ``None``."""
		try:
			import pygame
			if hasattr(wnd, "keyPressed") and cancel_key and wnd.keyPressed(cancel_key):
				return ""
			events = getattr(wnd, "events", None)
			if events is None:
				events = []
			for e in events:
				if e.type == pygame.KEYDOWN:
					kname = pygame.key.name(e.key).lower()
					if kname in ("left ctrl", "right ctrl", "left shift", "right shift", "left alt", "right alt"):
						continue
					mods = []
					if e.mod & pygame.KMOD_CTRL:
						mods.append("ctrl")
					if e.mod & pygame.KMOD_SHIFT:
						mods.append("shift")
					if e.mod & pygame.KMOD_ALT:
						mods.append("alt")
					return "+".join(mods + [kname])
				elif e.type == pygame.JOYBUTTONDOWN:
					return f"pad:{e.button}"
		except Exception:
			pass
		return None

	def describe(self, action: str, separator: str = ", ") -> str:
		"""Return a human-readable / TTS-friendly description of an action's bindings."""
		items = []
		for b in self._bindings.get(action, ()):
			if b.startswith("tap:"):
				parts = b.split(":")
				f = parts[1] if len(parts) > 1 else "1"
				c = parts[2] if len(parts) > 2 else "1"
				z = f" ({parts[3]})" if len(parts) > 3 and parts[3] else ""
				tap_lbl = "double tap" if c == "2" else (f"{c}-tap" if c != "1" else "tap")
				items.append(f"{f}-finger {tap_lbl}{z}")
			elif b.startswith("swipe:"):
				parts = b.split(":")
				d = parts[1] if len(parts) > 1 else ""
				items.append(f"swipe {d}")
			elif b.startswith("pad:"):
				items.append(f"gamepad {b.split(':', 1)[1].upper()}")
			elif b.startswith("mouse:"):
				items.append(f"mouse {b.split(':', 1)[1]}")
			else:
				items.append(b.upper())
		return separator.join(items) if items else "unbound"

	# ------------------------------------------------------------------
	# Persistence (JSON)
	# ------------------------------------------------------------------
	def to_dict(self) -> dict:
		return {k: list(v) for k, v in self._bindings.items()}

	@classmethod
	def from_dict(cls, data: dict, deadzone: float = 0.35) -> "InputMap":
		return cls(bindings=data, deadzone=deadzone)

	def save(self, filepath) -> Path:
		p = Path(filepath)
		p.parent.mkdir(parents=True, exist_ok=True)
		p.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
		return p

	def load(self, filepath) -> bool:
		p = Path(filepath)
		if not p.is_file():
			return False
		try:
			data = json.loads(p.read_text(encoding="utf-8"))
			if isinstance(data, dict):
				for k, v in data.items():
					if isinstance(v, list):
						self.set_bindings(k, v)
				return True
		except Exception:
			pass
		return False
