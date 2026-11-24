# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# Main game window loop with keyboard, mouse, touch, and speech integration.
# Supports Windows, Linux, macOS, Android, and iOS.

import math
from collections import deque
import pygame
from . import buffer, system, key
from .timer import Timer

_sound_pool_mod = None
_control_mod = None


def _get_sound_pool():
    global _sound_pool_mod
    if _sound_pool_mod is None:
        from . import sound_pool as _sp
        _sound_pool_mod = _sp
    return _sound_pool_mod


def _get_control():
    global _control_mod
    if _control_mod is None:
        from .sound_modules import control as _ctrl
        _control_mod = _ctrl
    return _control_mod

ZONES = {
    "left": (0.0, 0.0, 0.5, 1.0),
    "right": (0.5, 0.0, 1.0, 1.0),
    "top": (0.0, 0.0, 1.0, 0.5),
    "bottom": (0.0, 0.5, 1.0, 1.0),
    "center": (0.25, 0.25, 0.75, 0.75),
    "top-left": (0.0, 0.0, 0.5, 0.5),
    "top-right": (0.5, 0.0, 1.0, 0.5),
    "bottom-left": (0.0, 0.5, 0.5, 1.0),
    "bottom-right": (0.5, 0.5, 1.0, 1.0),
    # 3-tier vertical gameplay layout (top 15% system/info, middle 45% target/action, bottom 40% full-width movement)
    "top-bar": (0.0, 0.0, 1.0, 0.15),
    "top-left-bar": (0.0, 0.0, 0.5, 0.15),
    "top-right-bar": (0.5, 0.0, 1.0, 0.15),
    "mid-play": (0.0, 0.15, 1.0, 0.60),
    "bottom-play": (0.0, 0.60, 1.0, 1.0),
    "right-play": (0.0, 0.15, 1.0, 0.60),
    "left-play": (0.0, 0.60, 1.0, 1.0),
}
TOUCH_SLOP = 0.035
DOUBLE_TAP_SLOP = 0.14
DOUBLE_TAP_TIMEOUT_MS = 360
SWIPE_THRESHOLD = 0.08
SWIPE_MAX_DURATION_MS = 650
SWIPE_MIN_VELOCITY = 0.15
EXPLORE_HOLD_MS = 320
LONG_PRESS_MS = 550


class WindowBase:
    def __init__(self, platform=None):
        self._os = system.get_platform()["os"]
        self.platform = platform or ("mobile" if self._os in ("android", "ios") else "pc")
        buffer.platform = self.platform
        self._speech = None
        self.clock, self.fp = pygame.time.Clock(), 60
        self.frame_callback = self.exit_callback = self.lost_focus_callback = None
        self.events, self.touches = [], {}
        self.keys, self.previousKeys = set(), set()
        self._pressed, self._released, self._repeat = set(), set(), {}
        self._mouse, self._clicks, self._ups = set(), set(), set()
        self.pos, self.wheel = (0, 0), (0, 0)
        self.active_slidings, self.completed_slides = [], []
        self._slide_events, self._sliding_events = [], []
        self._taps, self.pinch, self.turn = 0, 0.0, 0.0
        self._tap_events = []
        self._explore_events = []
        self._long_press_events = []
        self._pending_tap = None
        self._tap_batch_fingers = 0
        self._tap_batch_pos = (0.5, 0.5)
        self._tap_batch_synthetic = False
        self._tap_streak = 0
        self._tap_streak_fingers = 0
        self._tap_timer = Timer()
        self._gesture_max_fingers = 0
        self._focused = True
        self._fullscreen = True
        self.gesture_mode = "game"
        self.mods = 0

    @property
    def speech(self):
        if self._speech is None:
            from . import speech as _speech_mod
            self._speech = _speech_mod.Speech()
        return self._speech

    @speech.setter
    def speech(self, value):
        self._speech = value

    def init(self, x, y, ttl, vv=0, show_vv=False, author=""):
        if not pygame.display.get_init():
            pygame.display.init()
        self.screen = pygame.display.set_mode((max(1, int(x)), max(1, int(y))), pygame.NOFRAME)
        pygame.display.set_caption(f"{ttl} {vv}" if show_vv else ttl)
        buffer.name_window, buffer.version, buffer.author, buffer.frame = ttl, vv, author, self
        self._focus(bool(pygame.key.get_focused()))
        return True

    def set_fullscreen(self, enabled=True):
        """Toggle true edge-to-edge fullscreen and system edge-gesture exclusion (dynamic, non-hardcoded)."""
        self._fullscreen = bool(enabled)
        try:
            from .pygame_shim import _android_bridge, _ios_bridge
            if _android_bridge.is_android_java_available():
                _android_bridge.set_fullscreen(self._fullscreen)
            elif _ios_bridge.is_ios_available():
                _ios_bridge.set_fullscreen(self._fullscreen)
        except Exception:
            pass
        return self._fullscreen

    def get_fullscreen(self):
        return bool(self._fullscreen)

    def set_gesture_mode(self, mode="game"):
        """Set gesture mode: 'game' (continuous sliding movement) or 'ui' (TalkBack explore + flick only)."""
        self.gesture_mode = "ui" if str(mode).lower() == "ui" else "game"
        return self.gesture_mode

    def _focus(self, focused):
        changed = focused != self._focused
        self._focused = focused
        import sys as _sys
        sp = _sound_pool_mod or _sys.modules.get("pyaudiogaming.sound_pool")
        if sp is not None:
            sp.set_focus(focused)
        if changed and not focused:
            self.keys.clear()
            self._pressed.clear(); self._released.clear()
            self.mods = 0
            self._mouse.clear()
            self._repeat.clear()
            self.touches.clear()
            self._gesture_max_fingers = 0
            if self.lost_focus_callback: self.lost_focus_callback()

    @staticmethod
    def _match_zone(pos, zone):
        if zone is None:
            return True
        bounds = ZONES.get(zone.lower()) if isinstance(zone, str) else zone
        if not bounds or len(bounds) != 4:
            return False
        x, y = pos
        return bounds[0] <= x <= bounds[2] and bounds[1] <= y <= bounds[3]

    def touchPos(self):
        """Trả về tọa độ chuẩn hóa (0.0 -> 1.0) của ngón tay đang chạm hoặc chuột."""
        if self.touches:
            first = next(iter(self.touches.values()))
            return first["current"]
        w, h = pygame.display.get_window_size() if pygame.display.get_init() else (1, 1)
        return (self.pos[0] / max(1, w), self.pos[1] / max(1, h))

    def in_zone(self, zone, pos=None):
        """Kiểm tra điểm chạm hiện tại (hoặc pos truyền vào) có nằm trong vùng zone không."""
        return self._match_zone(pos or self.touchPos(), zone)

    def frameUpdate(self):
        self.clock.tick(self.fp)
        self.previousKeys = self.keys.copy()
        self._pressed.clear(); self._released.clear()
        self._clicks.clear(); self._ups.clear()
        self.completed_slides.clear(); self.active_slidings.clear()
        self._slide_events.clear(); self._sliding_events.clear()
        self._tap_events.clear()
        self._explore_events.clear()
        self._long_press_events.clear()
        self.wheel, self._taps, self.pinch, self.turn = (0, 0), 0, 0.0, 0.0
        self.events = pygame.event.get()
        pending = deque(self.events)
        frame_released_slides = {}

        def _flush_pending_tap():
            if self._pending_tap is not None:
                pt = self._pending_tap
                self._pending_tap = None
                self._taps = pt["count"]
                self._tap_events.append({
                    "fingers": pt["fingers"],
                    "count": pt["count"],
                    "pos": pt["pos"],
                })

        def _commit_tap_batch():
            if self._tap_batch_fingers <= 0 or self.touches:
                return
            if frame_released_slides:
                self._tap_batch_fingers = 0
                self._pending_tap = None
                return
            fingers = max(self._tap_batch_fingers, self._gesture_max_fingers)
            tap_pos = self._tap_batch_pos
            is_syn = self._tap_batch_synthetic
            self._tap_batch_fingers = 0
            self._tap_batch_synthetic = False
            self._gesture_max_fingers = 0
            if fingers == 1:
                if self._pending_tap is not None and self._pending_tap["fingers"] == 1 and self._pending_tap["timer"].elapsed <= DOUBLE_TAP_TIMEOUT_MS:
                    new_count = self._pending_tap["count"] + 1
                    self._pending_tap = None
                    self._taps = new_count
                    self._tap_events.append({"fingers": 1, "count": new_count, "pos": tap_pos})
                elif is_syn:
                    self._taps = 1
                    self._tap_events.append({"fingers": 1, "count": 1, "pos": tap_pos})
                else:
                    self._pending_tap = {"fingers": 1, "count": 1, "pos": tap_pos, "timer": Timer()}
            else:
                self._pending_tap = None
                if self._tap_timer.elapsed <= DOUBLE_TAP_TIMEOUT_MS and self._tap_streak_fingers == fingers:
                    self._tap_streak += 1
                else:
                    self._tap_streak = 1
                    self._tap_streak_fingers = fingers
                self._tap_timer.restart()
                self._taps = self._tap_streak
                self._tap_events.append({"fingers": fingers, "count": self._tap_streak, "pos": tap_pos})

        while pending:
            event = pending.popleft()
            if event.type == pygame.QUIT:
                if self.exit_callback: self.exit_callback()
            elif event.type in (pygame.WINDOWFOCUSLOST, pygame.WINDOWMINIMIZED, getattr(pygame, "APP_WILLENTERBACKGROUND", -1)):
                self._focus(False)
            elif event.type in (pygame.WINDOWFOCUSGAINED, getattr(pygame, "APP_DIDENTERFOREGROUND", -1)):
                self._focus(True)
            elif event.type == pygame.ACTIVEEVENT and event.state & 2:
                self._focus(bool(event.gain))
            elif event.type == pygame.KEYDOWN:
                if event.key not in self.keys: self._pressed.add(event.key)
                self.keys.add(event.key)
                self.mods = event.mod if hasattr(event, "mod") else pygame.key.get_mods()
            elif event.type == pygame.KEYUP:
                self.keys.discard(event.key); self._released.add(event.key)
                self.mods = event.mod if hasattr(event, "mod") else pygame.key.get_mods()
                self._repeat.pop(event.key, None)
            elif event.type == pygame.MOUSEMOTION:
                self.pos = event.pos
            elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                if getattr(event, "touch", False): continue
                self.pos = event.pos
                if event.type == pygame.MOUSEBUTTONDOWN:
                    self._mouse.add(event.button); self._clicks.add(event.button)
                else:
                    self._mouse.discard(event.button); self._ups.add(event.button)
            elif event.type == pygame.MOUSEWHEEL:
                self.wheel = (self.wheel[0] + event.x, self.wheel[1] + event.y)
            elif event.type == pygame.FINGERDOWN:
                if len(self.touches) == 0 and self._pending_tap is not None and self._pending_tap["fingers"] == 1:
                    p_dist = math.hypot(event.x - self._pending_tap["pos"][0], event.y - self._pending_tap["pos"][1])
                    if self._pending_tap["timer"].elapsed > DOUBLE_TAP_TIMEOUT_MS or p_dist > DOUBLE_TAP_SLOP:
                        _flush_pending_tap()
                self.touches[event.finger_id] = {
                    "start": (event.x, event.y),
                    "current": (event.x, event.y),
                    "timer": Timer(),
                    "moved": False,
                    "sliding": False,
                    "exploring": False,
                    "long_fired": False,
                    "synthetic": bool(getattr(event, "synthetic", False)),
                }
                self._gesture_max_fingers = max(self._gesture_max_fingers, len(self.touches))
            elif event.type in (pygame.FINGERMOTION, pygame.FINGERUP):
                touch = self.touches.get(event.finger_id)
                if touch:
                    touch["current"] = (event.x, event.y)
                    dx, dy = event.x - touch["start"][0], event.y - touch["start"][1]
                    dist = math.hypot(dx, dy)
                    axis_dist = max(abs(dx), abs(dy))
                    direction = ("right" if dx > 0 else "left") if abs(dx) > abs(dy) else ("down" if dy > 0 else "up")
                    elapsed_ms = touch["timer"].elapsed
                    vel = dist / max(0.001, elapsed_ms / 1000.0)
                    if dist > TOUCH_SLOP:
                        touch["moved"] = True
                        self._pending_tap = None
                    if event.type == pygame.FINGERMOTION:
                        allow_slide = (self.gesture_mode == "game")
                        if allow_slide and axis_dist >= SWIPE_THRESHOLD and not touch["exploring"] and (touch["sliding"] or elapsed_ms < EXPLORE_HOLD_MS):
                            touch["sliding"] = True
                            self.active_slidings.append(direction)
                        elif len(self.touches) == 1 and touch["moved"] and not touch["sliding"]:
                            if touch["exploring"] or elapsed_ms >= EXPLORE_HOLD_MS:
                                touch["exploring"] = True
                                self._explore_events.append({"phase": "move", "pos": (event.x, event.y), "fingers": 1})
                    else:
                        if axis_dist >= SWIPE_THRESHOLD and elapsed_ms <= SWIPE_MAX_DURATION_MS:
                            touch["moved"] = True
                            self._pending_tap = None
                            self.completed_slides.append(direction)
                            info = frame_released_slides.setdefault(direction, {"count": 0, "start": touch["start"]})
                            info["count"] += 1
                        elif touch["exploring"]:
                            self._explore_events.append({"phase": "end", "pos": (event.x, event.y), "fingers": 1})
                        elif touch["sliding"]:
                            self._pending_tap = None
                        elif not touch["moved"] and not touch["long_fired"] and elapsed_ms < LONG_PRESS_MS:
                            self._tap_batch_fingers += 1
                            self._tap_batch_pos = touch["start"]
                            self._tap_batch_synthetic = bool(touch.get("synthetic", False))
                        elif touch["moved"] and len(self.touches) == 1:
                            self._explore_events.append({"phase": "end", "pos": (event.x, event.y), "fingers": 1})
                        self.touches.pop(event.finger_id, None)
                        if self._tap_batch_fingers > 0 and not self.touches:
                            _commit_tap_batch()
            elif event.type == pygame.MULTIGESTURE:
                self.pinch += event.pinched
                self.turn += event.rotated

        # TalkBack TouchExplorer tap resolution:
        # 1-finger tap waits DOUBLE_TAP_TIMEOUT_MS so Tap 1 of a double-tap NEVER misfires as a single-tap read!
        if frame_released_slides:
            self._tap_batch_fingers = 0
            self._pending_tap = None
        _commit_tap_batch()

        if not self.touches and self._pending_tap is not None and self._pending_tap["timer"].elapsed >= DOUBLE_TAP_TIMEOUT_MS:
            _flush_pending_tap()

        # Chốt các cú vuốt nhấc tay (swipe / keySlide) kèm số ngón và tọa độ bắt đầu
        for direction, info in frame_released_slides.items():
            fingers = max(self._gesture_max_fingers, info["count"])
            self._slide_events.append({"dir": direction, "fingers": fingers, "start": info["start"]})
        if not self.touches:
            self._gesture_max_fingers = 0

        # Duy trì trạng thái vuốt giữ (swiping / keySliding) và phát hiện nhấn giữ tại chỗ (long_press)
        held_dirs = {}
        allow_held_slide = (self.gesture_mode == "game")
        for touch in self.touches.values():
            dx, dy = (touch["current"][i] - touch["start"][i] for i in (0, 1))
            if allow_held_slide and (touch.get("sliding") or max(abs(dx), abs(dy)) >= SWIPE_THRESHOLD) and not touch.get("exploring"):
                touch["moved"] = True
                touch["sliding"] = True
                direction = ("right" if dx > 0 else "left") if abs(dx) > abs(dy) else ("down" if dy > 0 else "up")
                if direction not in self.active_slidings:
                    self.active_slidings.append(direction)
                info = held_dirs.setdefault(direction, {"count": 0, "start": touch["start"]})
                info["count"] += 1
            elif not touch["moved"] and not touch["long_fired"] and touch["timer"].elapsed >= LONG_PRESS_MS:
                touch["long_fired"] = True
                self._pending_tap = None
                self._long_press_events.append({
                    "fingers": max(len(self.touches), self._gesture_max_fingers),
                    "pos": touch["start"]
                })
        for direction, info in held_dirs.items():
            self._sliding_events.append({"dir": direction, "fingers": max(len(self.touches), self._gesture_max_fingers), "start": info["start"]})

        # Xóa bộ đếm lặp của những hướng/số ngón đã nhả tay
        active_keys = {f"swipe_{e['dir']}_{e['fingers']}" for e in (self._sliding_events + self._slide_events)}
        active_keys.update({f"swipe_{d}_None" for d in (self.active_slidings + self.completed_slides)})
        for k in list(self._repeat.keys()):
            if isinstance(k, str) and k.startswith("swipe_") and k not in active_keys:
                self._repeat.pop(k, None)

        if self.keyPressed("ctrl") or (self.tap(fingers=2, count=1) == 1):
            self.speech.speech.silence()
        if self.keyPressed("alt+f4") and self.exit_callback: self.exit_callback()
        if self.frame_callback: self.frame_callback()

    def clear_input(self):
        """Discard stale text/key/touch input while preserving quit and focus events."""
        pygame.event.clear([pygame.KEYDOWN, pygame.KEYUP, pygame.TEXTINPUT, pygame.TEXTEDITING, pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP])
        self.keys.clear()
        self.previousKeys.clear()
        self._pressed.clear(); self._released.clear(); self._repeat.clear()
        self.touches.clear()
        self._tap_events.clear(); self._explore_events.clear(); self._slide_events.clear(); self._sliding_events.clear(); self._long_press_events.clear()
        self.completed_slides.clear(); self.active_slidings.clear()
        self._pending_tap = None
        self._tap_batch_synthetic = False
        self._taps = self._tap_streak = self._tap_streak_fingers = self._tap_batch_fingers = self._gesture_max_fingers = 0
        self.mods = 0
        self.events = []

    def keyPressed(self, name):
        if isinstance(name, str) and name.lower() in key.MODS:
            group = key.MODS[name.lower()]
            return any(code in self._pressed for code in self._mod_keys(group))
        code, mask = key.chord(name)
        return code in self._pressed and (not mask or key.match(self.mods, mask))

    @staticmethod
    def _mod_keys(group):
        return {pygame.KMOD_CTRL: (pygame.K_LCTRL, pygame.K_RCTRL),
                pygame.KMOD_SHIFT: (pygame.K_LSHIFT, pygame.K_RSHIFT),
                pygame.KMOD_ALT: (pygame.K_LALT, pygame.K_RALT),
                pygame.KMOD_GUI: (pygame.K_LGUI, pygame.K_RGUI)}[group]

    def keyReleased(self, name):
        if isinstance(name, str) and name.lower() in key.MODS:
            return any(code in self._released for code in self._mod_keys(key.MODS[name.lower()]))
        code, mask = key.chord(name)
        return code in self._released and (not mask or key.match(self.mods, mask))

    def keyPressing(self, name, t=0):
        code, mask = key.chord(name)
        down = code in self.keys
        if isinstance(name, str) and name.lower() in key.MODS:
            down = bool(self.mods & key.MODS[name.lower()])
        if not down or (mask and not key.match(self.mods, mask)):
            self._repeat.pop(code, None)
            return False
        if not t: return True
        tmr = self._repeat.get(code)
        if code in self._pressed or tmr is None or tmr.elapsed >= t:
            if tmr is None:
                self._repeat[code] = Timer()
            else:
                tmr.restart()
            return True
        return False

    def mousePressed(self, button=1): return button in self._clicks
    def mouseReleased(self, button=1): return button in self._ups
    def mousePressing(self, button=1): return button in self._mouse

    def tap(self, fingers=None, count=1, zone=None):
        """
        Kiểm tra cử chỉ chạm màn hình:
        - Mặc định tap() trả về số lần chạm (tương thích 100% với code cũ).
        - Có thể lọc theo số ngón (fingers=2), số lần chạm liên tiếp (count=2 cho double-tap), và vùng màn hình (zone="right").
        """
        if fingers is None and count == 1 and zone is None:
            return self._taps
        for ev in self._tap_events:
            if (fingers is None or ev["fingers"] == fingers) and ev["count"] >= count and self._match_zone(ev["pos"], zone):
                return ev["count"]
        return 0

    def double_tap(self, fingers=1, zone=None):
        """Kiểm tra chạm đúp (chuẩn TalkBack/VoiceOver để kích hoạt)."""
        return bool(self.tap(fingers=fingers, count=2, zone=zone))

    def tap_pos(self, fingers=1, count=1, zone=None):
        """Return normalized (x, y) position of the matching tap event, or None."""
        for ev in self._tap_events:
            if (fingers is None or ev["fingers"] == fingers) and ev["count"] == count and self._match_zone(ev["pos"], zone):
                return ev["pos"]
        return None

    def explore_pos(self, zone=None):
        """Return latest normalized (x, y) position during 1-finger Explore-by-Touch, or None."""
        for ev in reversed(self._explore_events):
            if ev["phase"] == "move" and self._match_zone(ev["pos"], zone):
                return ev["pos"]
        return None

    def explore_end_pos(self, zone=None):
        """Return normalized (x, y) position when 1-finger Explore-by-Touch ends, or None."""
        for ev in reversed(self._explore_events):
            if ev["phase"] == "end" and self._match_zone(ev["pos"], zone):
                return ev["pos"]
        return None

    def long_press(self, fingers=1, zone=None):
        """Kiểm tra nhấn giữ tại chỗ trên màn hình (không trượt)."""
        return any(
            (fingers is None or ev["fingers"] == fingers) and self._match_zone(ev["pos"], zone)
            for ev in self._long_press_events
        )

    def keySlide(self, direction, fingers=None, zone=None):
        """Kiểm tra vuốt nhấc tay theo hướng, số ngón tay (fingers) và khu vực (zone)."""
        d = direction.lower()
        if fingers is None and zone is None:
            return d in self.completed_slides
        return any(
            ev["dir"] == d and (fingers is None or ev["fingers"] == fingers) and self._match_zone(ev["start"], zone)
            for ev in self._slide_events
        )

    def swipe(self, direction, fingers=None, zone=None):
        return self.keySlide(direction, fingers=fingers, zone=zone)

    def keySliding(self, direction, t=0, fingers=None, zone=None):
        """Kiểm tra vuốt giữ theo hướng, có hẹn giờ mỗi bước t (ms), lọc theo số ngón (fingers) và khu vực (zone)."""
        d = direction.lower()
        if fingers is None and zone is None:
            down = d in self.active_slidings or d in self.completed_slides
        else:
            down = any(
                ev["dir"] == d and (fingers is None or ev["fingers"] == fingers) and self._match_zone(ev["start"], zone)
                for ev in (self._sliding_events + self._slide_events)
            )
        rkey = f"swipe_{d}_{fingers}"
        if not down:
            self._repeat.pop(rkey, None)
            return False
        if not t: return True
        tmr = self._repeat.get(rkey)
        if tmr is None or tmr.elapsed >= t:
            if tmr is None:
                self._repeat[rkey] = Timer()
            else:
                tmr.restart()
            return True
        return False

    def swiping(self, direction, t=0, fingers=None, zone=None):
        return self.keySliding(direction, t=t, fingers=fingers, zone=zone)

    def sym(self, target, action="tap", fingers=1, count=1, pos=(0.5, 0.5), value=0.2):
        """
        Giả lập phím bấm, chạm nhiều lần (count), chạm/vuốt nhiều ngón (fingers),
        và chọn vị trí/khu vực trên màn hình (pos có thể là tuple (x, y) hoặc tên zone như "left", "top-right").
        """
        act = action.lower() if isinstance(action, str) else "tap"
        t_str = target.lower() if isinstance(target, str) else ""

        # Cho phép truyền tên zone (ví dụ pos="left") hoặc tọa độ (x, y)
        if isinstance(pos, str) and pos.lower() in ZONES:
            b = ZONES[pos.lower()]
            sx, sy = (b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0
        else:
            sx, sy = pos

        # 1. Giả lập chạm (Tap: hỗ trợ nhiều ngón `fingers` và chạm nhiều lần `count`)
        if t_str == "tap":
            cnt = max(1, int(count))
            syn_flag = (cnt == 1)
            for tap_i in range(cnt):
                for f in range(max(1, int(fingers))):
                    pygame.event.post(pygame.event.Event(pygame.FINGERDOWN, {"finger_id": f, "x": sx, "y": sy, "dx": 0.0, "dy": 0.0, "synthetic": syn_flag}))
                for f in range(max(1, int(fingers))):
                    pygame.event.post(pygame.event.Event(pygame.FINGERUP, {"finger_id": f, "x": sx, "y": sy, "dx": 0.0, "dy": 0.0, "synthetic": syn_flag}))
            return True

        # 2. Giả lập Pinch / Turn
        if t_str in ("pinch", "turn", "rotate"):
            pinched = float(value) if t_str == "pinch" else 0.0
            rotated = float(value) if t_str in ("turn", "rotate") else 0.0
            pygame.event.post(pygame.event.Event(pygame.MULTIGESTURE, {"pinched": pinched, "rotated": rotated, "x": sx, "y": sy, "num_fingers": max(2, int(fingers))}))
            return True

        # 3. Giả lập vuốt 4 hướng với nhiều ngón (fingers) tại vùng (pos)
        vectors = {"up": (0.0, -0.25), "down": (0.0, 0.25), "left": (-0.25, 0.0), "right": (0.25, 0.0)}
        for prefix in ("swipe_", "slide_"):
            if t_str.startswith(prefix):
                t_str = t_str[len(prefix):]
                if act == "tap": act = "swipe"
        if t_str in vectors and act in ("swipe", "slide", "hold", "down", "up", "release"):
            dx, dy = vectors[t_str]
            ex, ey = max(0.0, min(1.0, sx + dx)), max(0.0, min(1.0, sy + dy))
            f_count = max(1, int(fingers))
            if act in ("swipe", "slide"):
                for f in range(f_count):
                    pygame.event.post(pygame.event.Event(pygame.FINGERDOWN, {"finger_id": f, "x": sx, "y": sy, "dx": 0.0, "dy": 0.0}))
                    pygame.event.post(pygame.event.Event(pygame.FINGERMOTION, {"finger_id": f, "x": ex, "y": ey, "dx": dx, "dy": dy}))
                for f in range(f_count):
                    pygame.event.post(pygame.event.Event(pygame.FINGERUP, {"finger_id": f, "x": ex, "y": ey, "dx": dx, "dy": dy}))
            elif act in ("hold", "down"):
                for f in range(f_count):
                    pygame.event.post(pygame.event.Event(pygame.FINGERDOWN, {"finger_id": f, "x": sx, "y": sy, "dx": 0.0, "dy": 0.0}))
                    pygame.event.post(pygame.event.Event(pygame.FINGERMOTION, {"finger_id": f, "x": ex, "y": ey, "dx": dx, "dy": dy}))
            elif act in ("up", "release"):
                for f in range(f_count):
                    pygame.event.post(pygame.event.Event(pygame.FINGERUP, {"finger_id": f, "x": ex, "y": ey, "dx": 0.0, "dy": 0.0}))
            return True

        # 4. Giả lập bàn phím
        code, mask = (target, 0) if isinstance(target, int) else key.chord(str(target))
        if code:
            if act in ("press", "down", "tap"):
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN, {"key": code, "mod": mask, "unicode": "", "scancode": 0}))
            if act in ("release", "up", "tap"):
                pygame.event.post(pygame.event.Event(pygame.KEYUP, {"key": code, "mod": mask, "unicode": "", "scancode": 0}))
            return True
        return False

    sim = sym

    def touchCount(self): return len(self.touches)
    def get_focused_window(self): return self._focused
    def set_global_sound(self, value): return _get_sound_pool().set_global_sound(value)
    def get_global_sound(self): return _get_sound_pool().get_global_sound()

    def wait(self, msec):
        timer = Timer()
        while timer.elapsed < msec: self.frameUpdate()

    def say(self, text, i=True, split=False): self.speech.say(text, i=i, split=split)
    def saync(self, text): self.speech.saync(text)
    def say3d(self, text, lx, ly, lz, sx, sy, sz, i=True, **kwargs): self.speech.say3d(text, lx, ly, lz, sx, sy, sz, i=i, **kwargs)
    speech3d = say3d

    def input(self, title, message, password=False, dir=False, file=False):
        from . import inputBox
        return inputBox.kbt(None, title, message, password=password, dir_dialog=dir, file_dialog=file)

    def message(self, m, callback=None, open=None, move=None, close=None):
        from . import vb
        return vb.message(m, callback, open, move, close, window=self)

    def message_gui(self, title, message, type=None):
        from . import inputBox
        return inputBox.dialogMessage(title, message, inputBox.INFO if type is None else type)

    def load_sound(self, name, h="both"): return _get_control().load_sound_file(name, key=name, target=h)
    def sound_cast(self, name, data, h="both"): return _get_control().save_mem_buffer(name, data, target=h)
    cast_sound = sound_cast
    def make_spak(self, source, output_path=None, password="", **kwargs):
        from . import utils
        return utils.make_spak(source, output_path=output_path, password=password, **kwargs)
    def load_spak(self, spak_path, password="", mode="lazy", target="both", **kwargs):
        from . import utils
        return utils.load_spak(spak_path, password=password, mode=mode, target=target, **kwargs)

    def beep(self, frequency, duration):
        if self._os == "windows":
            import ctypes
            ctypes.windll.kernel32.Beep(int(frequency), int(duration))
        else:
            import struct
            rate = 44100
            pcm = b"".join(struct.pack("<h", int(5000 * math.sin(2 * math.pi * frequency * i / rate))) for i in range(int(rate * duration / 1000)))
            tone = _get_sound_pool().sound()
            tone.freq = rate
            tone.stream("", draw=True, mono=True)
            tone.push(pcm); tone.play()
            self.wait(duration)
            tone.close()

    def beep_progress_bar(self, progress, duration=120):
        self.beep(200 + int(max(0, min(100, progress)) / 100 * 1300), duration)


class WindowPC(WindowBase): pass
class WindowMobile(WindowBase): pass
class Window(WindowBase): pass