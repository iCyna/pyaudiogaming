# -*- coding: utf-8 -*-
"""Cross-platform haptics & rumble feedback for PyAudioGaming.

Supports:
- Android: ``android.os.Vibrator`` / ``VibratorManager`` + ``VibrationEffect`` (via Chaquopy or pyjnius)
- iOS: ``UIImpactFeedbackGenerator`` / ``UINotificationFeedbackGenerator`` (via rubicon-objc if installed)
- Windows Gamepad: Native XInput (``xinput1_4.dll`` / ``xinput1_3.dll`` / ``xinput9_1_0.dll``) via ``ctypes``
- Desktop Gamepad (Windows/Linux/macOS): ``pygame.joystick.Joystick.rumble`` (SDL2)
- Fallback: Safe silent no-op when no haptic hardware is available.

All pattern playback is 100% single-threaded (call ``haptics.update()`` in your game loop).
"""

import ctypes
import os
import sys

from . import system
from .timer import Timer

__all__ = [
	"HapticEngine",
	"haptics",
	"vibrate",
	"stop",
	"pattern",
	"preset",
	"update",
	"set_enabled",
	"set_intensity",
	"is_supported",
	"PRESETS",
]

# Built-in audio-game haptic presets: list of (duration_ms, strength_0_to_1)
# Strength 0.0 represents a pause/gap between pulses.
PRESETS = {
	"tick": [(12, 0.25)],
	"click": [(20, 0.45)],
	"select": [(28, 0.55)],
	"double_tap": [(22, 0.5), (45, 0.0), (22, 0.65)],
	"success": [(30, 0.45), (40, 0.0), (65, 0.85)],
	"warning": [(60, 0.7), (50, 0.0), (60, 0.7)],
	"error": [(90, 0.9), (45, 0.0), (90, 0.9), (45, 0.0), (140, 1.0)],
	"blocked": [(35, 0.75), (30, 0.0), (35, 0.5)],
	"footstep": [(16, 0.22)],
	"hit_light": [(45, 0.55)],
	"hit_heavy": [(140, 1.0)],
	"explosion": [(80, 1.0), (30, 0.4), (160, 0.9), (40, 0.3), (120, 0.5)],
	"heartbeat": [(45, 0.65), (90, 0.0), (60, 0.9), (320, 0.0)],
}


class _XINPUT_VIBRATION(ctypes.Structure):
	_fields_ = [
		("wLeftMotorSpeed", ctypes.c_ushort),
		("wRightMotorSpeed", ctypes.c_ushort),
	]


class _AndroidBackend:
	"""Android Vibrator backend using Chaquopy ``java`` or ``pyjnius``."""

	def __init__(self):
		self._vibrator = None
		self._api_level = 0
		self._vib_effect_cls = None
		self._init_done = False

	def _ensure_init(self):
		if self._init_done:
			return
		self._init_done = True
		if system.get_platform()["os"] != "android":
			return
		try:
			ctx, bridge = system.get_android_activity()
			if ctx is None:
				return
			jcls = (lambda n: __import__("java").jclass(n)) if bridge == "chaquopy" else (lambda n: __import__("jnius").autoclass(n))
			BuildVersion = jcls("android.os.Build$VERSION")
			Context = jcls("android.content.Context")
			self._api_level = int(BuildVersion.SDK_INT)
			if self._api_level >= 31:
				vm = ctx.getSystemService(Context.VIBRATOR_MANAGER_SERVICE)
				if vm is not None:
					self._vibrator = vm.getDefaultVibrator()
			if self._vibrator is None:
				self._vibrator = ctx.getSystemService(Context.VIBRATOR_SERVICE)
			if self._api_level >= 26:
				self._vib_effect_cls = jcls("android.os.VibrationEffect")
		except Exception:
			self._vibrator = None

	@property
	def available(self) -> bool:
		self._ensure_init()
		if self._vibrator is None:
			return False
		try:
			return bool(self._vibrator.hasVibrator())
		except Exception:
			return True

	def vibrate(self, duration_ms: int, strength: float, **kwargs) -> bool:
		self._ensure_init()
		if self._vibrator is None:
			return False
		duration_ms = max(1, int(duration_ms))
		amp = max(1, min(255, int(round(strength * 255))))
		try:
			if self._vib_effect_cls is not None and self._api_level >= 26:
				effect = self._vib_effect_cls.createOneShot(int(duration_ms), int(amp))
				self._vibrator.vibrate(effect)
			else:
				self._vibrator.vibrate(int(duration_ms))
			return True
		except Exception:
			return False

	def stop(self, **kwargs):
		self._ensure_init()
		if self._vibrator is not None:
			try:
				self._vibrator.cancel()
			except Exception:
				pass


class _IOSBackend:
	"""iOS UIImpactFeedbackGenerator backend via rubicon-objc (when running on iOS)."""

	def __init__(self):
		self._gen_cls = None
		self._init_done = False

	def _ensure_init(self):
		if self._init_done:
			return
		self._init_done = True
		if sys.platform != "ios":
			return
		try:
			from rubicon.objc import ObjCClass
			self._gen_cls = ObjCClass("UIImpactFeedbackGenerator")
		except Exception:
			self._gen_cls = None

	@property
	def available(self) -> bool:
		self._ensure_init()
		return self._gen_cls is not None

	def vibrate(self, duration_ms: int, strength: float, **kwargs) -> bool:
		self._ensure_init()
		if self._gen_cls is None:
			return False
		try:
			# 0 = light, 1 = medium, 2 = heavy
			style = 0 if strength < 0.35 else (1 if strength < 0.7 else 2)
			gen = self._gen_cls.alloc().initWithStyle_(style)
			gen.prepare()
			gen.impactOccurred()
			return True
		except Exception:
			return False

	def stop(self, **kwargs):
		pass


class _XInputBackend:
	"""Windows native XInput gamepad vibration via ctypes (zero external dependencies)."""

	def __init__(self):
		self._dll = None
		self._init_done = False
		self._active_timers = {}  # device_idx -> (Timer, duration_ms)

	def _ensure_init(self):
		if self._init_done:
			return
		self._init_done = True
		if os.name != "nt":
			return
		for name in ("xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"):
			try:
				dll = ctypes.WinDLL(name)
				dll.XInputSetState.argtypes = [ctypes.c_uint, ctypes.POINTER(_XINPUT_VIBRATION)]
				dll.XInputSetState.restype = ctypes.c_uint
				self._dll = dll
				break
			except Exception:
				continue

	@property
	def available(self) -> bool:
		self._ensure_init()
		return self._dll is not None

	def vibrate(self, duration_ms: int, strength: float, low_freq=None, high_freq=None, device: int = 0) -> bool:
		self._ensure_init()
		if self._dll is None:
			return False
		low = strength if low_freq is None else max(0.0, min(1.0, float(low_freq)))
		high = strength if high_freq is None else max(0.0, min(1.0, float(high_freq)))
		vib = _XINPUT_VIBRATION(int(low * 65535), int(high * 65535))
		try:
			res = self._dll.XInputSetState(int(device), ctypes.byref(vib))
			if res == 0:
				self._active_timers[int(device)] = (Timer(duration=max(1, int(duration_ms))), int(duration_ms))
				return True
		except Exception:
			pass
		return False

	def stop(self, device: int = 0):
		self._ensure_init()
		if self._dll is None:
			return
		self._active_timers.pop(int(device), None)
		vib = _XINPUT_VIBRATION(0, 0)
		try:
			self._dll.XInputSetState(int(device), ctypes.byref(vib))
		except Exception:
			pass

	def update(self):
		if not self._active_timers:
			return
		expired = [dev for dev, (tm, _) in self._active_timers.items() if tm.expired]
		for dev in expired:
			self.stop(device=dev)


class _PygameJoystickBackend:
	"""SDL2 / pygame Joystick rumble backend (Windows, Linux, macOS)."""

	def __init__(self):
		self._joysticks = {}

	def _get_joystick(self, device: int = 0):
		try:
			import pygame
			if not pygame.get_init():
				return None
			if not pygame.joystick.get_init():
				pygame.joystick.init()
			count = pygame.joystick.get_count()
			if device < 0 or device >= count:
				return None
			joy = self._joysticks.get(device)
			if joy is None or not joy.get_init():
				joy = pygame.joystick.Joystick(device)
				joy.init()
				self._joysticks[device] = joy
			return joy
		except Exception:
			return None

	@property
	def available(self) -> bool:
		joy = self._get_joystick(0)
		return joy is not None and hasattr(joy, "rumble")

	def vibrate(self, duration_ms: int, strength: float, low_freq=None, high_freq=None, device: int = 0) -> bool:
		joy = self._get_joystick(device)
		if joy is None or not hasattr(joy, "rumble"):
			return False
		low = strength if low_freq is None else max(0.0, min(1.0, float(low_freq)))
		high = strength if high_freq is None else max(0.0, min(1.0, float(high_freq)))
		try:
			return bool(joy.rumble(float(low), float(high), max(1, int(duration_ms))))
		except Exception:
			return False

	def stop(self, device: int = 0):
		joy = self._get_joystick(device)
		if joy is not None and hasattr(joy, "stop_rumble"):
			try:
				joy.stop_rumble()
			except Exception:
				pass


class HapticEngine:
	"""Unified cross-platform haptic feedback controller with pattern sequencer & presets."""

	def __init__(self, enabled: bool = True, intensity: float = 1.0):
		self._enabled = bool(enabled)
		self._intensity = max(0.0, min(1.0, float(intensity)))
		self._android = _AndroidBackend()
		self._ios = _IOSBackend()
		self._xinput = _XInputBackend()
		self._pygame_joy = _PygameJoystickBackend()
		self._active_patterns = []  # list of dicts for non-blocking pattern playback

	@property
	def enabled(self) -> bool:
		return self._enabled

	def set_enabled(self, enabled: bool):
		self._enabled = bool(enabled)
		if not self._enabled:
			self.stop()

	@property
	def intensity(self) -> float:
		return self._intensity

	def set_intensity(self, value: float):
		self._intensity = max(0.0, min(1.0, float(value)))

	def is_supported(self) -> bool:
		return (
			self._android.available
			or self._ios.available
			or self._pygame_joy.available
			or self._xinput.available
		)

	def vibrate(self, duration_ms: int = 40, strength: float = 0.6, low_freq=None, high_freq=None, device: int = 0) -> bool:
		"""Trigger a single vibration pulse. Returns True if a hardware backend accepted it."""
		if not self._enabled or self._intensity <= 0.0:
			return False
		duration_ms = max(1, int(duration_ms))
		eff_strength = max(0.0, min(1.0, float(strength) * self._intensity))
		if eff_strength <= 0.0:
			return False

		eff_low = None if low_freq is None else max(0.0, min(1.0, float(low_freq) * self._intensity))
		eff_high = None if high_freq is None else max(0.0, min(1.0, float(high_freq) * self._intensity))

		if self._android.available:
			return self._android.vibrate(duration_ms, eff_strength)
		if self._ios.available:
			return self._ios.vibrate(duration_ms, eff_strength)
		if self._pygame_joy.vibrate(duration_ms, eff_strength, low_freq=eff_low, high_freq=eff_high, device=device):
			return True
		if self._xinput.vibrate(duration_ms, eff_strength, low_freq=eff_low, high_freq=eff_high, device=device):
			return True
		return False

	def stop(self, device: int = 0):
		"""Immediately stop all active vibrations and cancel queued patterns."""
		self._active_patterns = [p for p in self._active_patterns if p["device"] != device]
		self._android.stop()
		self._ios.stop()
		self._pygame_joy.stop(device=device)
		self._xinput.stop(device=device)

	def pattern(self, steps, repeat: int = 1, device: int = 0):
		"""Play a sequence of ``(duration_ms, strength)`` tuples non-blockingly.

		Call ``haptics.update()`` each frame to advance the sequence.
		"""
		if not self._enabled or not steps or repeat <= 0:
			return False
		norm = [(max(1, int(d)), max(0.0, min(1.0, float(s)))) for d, s in steps]
		entry = {
			"steps": norm,
			"index": 0,
			"repeat": int(repeat),
			"device": int(device),
			"timer": Timer(duration=norm[0][0]),
		}
		# Replace any existing pattern on the same device
		self._active_patterns = [p for p in self._active_patterns if p["device"] != int(device)]
		self._active_patterns.append(entry)
		dur, strength = norm[0]
		if strength > 0.0:
			self.vibrate(dur, strength, device=device)
		else:
			self._pygame_joy.stop(device=device)
			self._xinput.stop(device=device)
		return True

	def preset(self, name: str, repeat: int = 1, device: int = 0) -> bool:
		"""Play a named preset from ``PRESETS`` (e.g. ``'click'``, ``'hit_heavy'``, ``'error'``)."""
		steps = PRESETS.get(str(name).lower().strip())
		if not steps:
			return False
		return self.pattern(steps, repeat=repeat, device=device)

	def update(self):
		"""Advance active haptic patterns and auto-stop timed XInput motors. Call once per frame."""
		self._xinput.update()
		if not self._active_patterns:
			return
		still_active = []
		for p in self._active_patterns:
			if not p["timer"].expired:
				still_active.append(p)
				continue
			p["index"] += 1
			if p["index"] >= len(p["steps"]):
				p["repeat"] -= 1
				if p["repeat"] <= 0:
					continue
				p["index"] = 0
			dur, strength = p["steps"][p["index"]]
			p["timer"].restart(duration=dur)
			if strength > 0.0:
				self.vibrate(dur, strength, device=p["device"])
			else:
				self._pygame_joy.stop(device=p["device"])
				self._xinput.stop(device=p["device"])
			still_active.append(p)
		self._active_patterns = still_active


# Global singleton convenience instance
haptics = HapticEngine()


def vibrate(duration_ms: int = 40, strength: float = 0.6, low_freq=None, high_freq=None, device: int = 0) -> bool:
	return haptics.vibrate(duration_ms, strength, low_freq=low_freq, high_freq=high_freq, device=device)


def stop(device: int = 0):
	haptics.stop(device=device)


def pattern(steps, repeat: int = 1, device: int = 0) -> bool:
	return haptics.pattern(steps, repeat=repeat, device=device)


def preset(name: str, repeat: int = 1, device: int = 0) -> bool:
	return haptics.preset(name, repeat=repeat, device=device)


def update():
	haptics.update()


def set_enabled(enabled: bool):
	haptics.set_enabled(enabled)


def set_intensity(value: float):
	haptics.set_intensity(value)


def is_supported() -> bool:
	return haptics.is_supported()
