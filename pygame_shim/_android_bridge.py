# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# Android Chaquopy/BeeWare native bridge for the pygame shim.
# Supports Android.

import threading
from . import locals as _L
from . import event as _event
from . import key as _key
from . import mouse as _mouse

_HAS_JAVA = False
try:
    import java
    from java import jclass, dynamic_proxy
    _HAS_JAVA = True
except Exception:
    java = None
    jclass = None
    dynamic_proxy = None

_LOCK = threading.Lock()
_ACTIVITY = None
_VIEW = None
_BRIDGE_PROXY = None  # Keep strong reference so JVM GC does not collect it
_BOOTSTRAPPED = False
_LAST_TOUCH = {}

# Android KeyEvent.KEYCODE_* -> pygame.K_*
_ANDROID_KEYMAP = {
    4: _L.K_ESCAPE,        # KEYCODE_BACK
    7: _L.K_0, 8: _L.K_1, 9: _L.K_2, 10: _L.K_3, 11: _L.K_4,
    12: _L.K_5, 13: _L.K_6, 14: _L.K_7, 15: _L.K_8, 16: _L.K_9,
    19: _L.K_UP,           # KEYCODE_DPAD_UP
    20: _L.K_DOWN,         # KEYCODE_DPAD_DOWN
    21: _L.K_LEFT,         # KEYCODE_DPAD_LEFT
    22: _L.K_RIGHT,        # KEYCODE_DPAD_RIGHT
    23: _L.K_RETURN,       # KEYCODE_DPAD_CENTER
    29: _L.K_a, 30: _L.K_b, 31: _L.K_c, 32: _L.K_d, 33: _L.K_e,
    34: _L.K_f, 35: _L.K_g, 36: _L.K_h, 37: _L.K_i, 38: _L.K_j,
    39: _L.K_k, 40: _L.K_l, 41: _L.K_m, 42: _L.K_n, 43: _L.K_o,
    44: _L.K_p, 45: _L.K_q, 46: _L.K_r, 47: _L.K_s, 48: _L.K_t,
    49: _L.K_u, 50: _L.K_v, 51: _L.K_w, 52: _L.K_x, 53: _L.K_y,
    54: _L.K_z,
    55: _L.K_COMMA,
    56: _L.K_PERIOD,
    57: _L.K_LALT,
    58: _L.K_RALT,
    59: _L.K_LSHIFT,
    60: _L.K_RSHIFT,
    61: _L.K_TAB,
    62: _L.K_SPACE,
    66: _L.K_RETURN,       # KEYCODE_ENTER
    67: _L.K_BACKSPACE,    # KEYCODE_DEL
    68: _L.K_BACKQUOTE,
    69: _L.K_MINUS,
    70: _L.K_EQUALS,
    71: _L.K_LEFTBRACKET,
    72: _L.K_RIGHTBRACKET,
    73: _L.K_BACKSLASH,
    74: _L.K_SEMICOLON,
    75: _L.K_QUOTE,
    76: _L.K_SLASH,
    82: _L.K_MENU,
    92: _L.K_PAGEUP,
    93: _L.K_PAGEDOWN,
    111: _L.K_ESCAPE,
    112: _L.K_DELETE,      # KEYCODE_FORWARD_DEL
    113: _L.K_LCTRL,
    114: _L.K_RCTRL,
    115: _L.K_CAPSLOCK,
    117: _L.K_LGUI,
    118: _L.K_RGUI,
    120: _L.K_PRINTSCREEN,
    121: _L.K_PAUSE,
    122: _L.K_HOME,        # KEYCODE_MOVE_HOME
    123: _L.K_END,         # KEYCODE_MOVE_END
    124: _L.K_INSERT,
    131: _L.K_F1, 132: _L.K_F2, 133: _L.K_F3, 134: _L.K_F4,
    135: _L.K_F5, 136: _L.K_F6, 137: _L.K_F7, 138: _L.K_F8,
    139: _L.K_F9, 140: _L.K_F10, 141: _L.K_F11, 142: _L.K_F12,
    144: _L.K_KP0, 145: _L.K_KP1, 146: _L.K_KP2, 147: _L.K_KP3,
    148: _L.K_KP4, 149: _L.K_KP5, 150: _L.K_KP6, 151: _L.K_KP7,
    152: _L.K_KP8, 153: _L.K_KP9,
    154: _L.K_KP_DIVIDE,
    155: _L.K_KP_MULTIPLY,
    156: _L.K_KP_MINUS,
    157: _L.K_KP_PLUS,
    158: _L.K_KP_PERIOD,
    160: _L.K_KP_ENTER,
    161: _L.K_KP_EQUALS,
}


def _meta_to_kmod(meta_state):
    m = 0
    if meta_state & 0x00000040:  # META_SHIFT_LEFT_ON
        m |= _L.KMOD_LSHIFT
    if meta_state & 0x00000080:  # META_SHIFT_RIGHT_ON
        m |= _L.KMOD_RSHIFT
    if (meta_state & 0x00000001) and not (m & _L.KMOD_SHIFT):  # META_SHIFT_ON
        m |= _L.KMOD_LSHIFT
    if meta_state & 0x00002000:  # META_CTRL_LEFT_ON
        m |= _L.KMOD_LCTRL
    if meta_state & 0x00004000:  # META_CTRL_RIGHT_ON
        m |= _L.KMOD_RCTRL
    if (meta_state & 0x00001000) and not (m & _L.KMOD_CTRL):  # META_CTRL_ON
        m |= _L.KMOD_LCTRL
    if meta_state & 0x00000010:  # META_ALT_LEFT_ON
        m |= _L.KMOD_LALT
    if meta_state & 0x00000020:  # META_ALT_RIGHT_ON
        m |= _L.KMOD_RALT
    if (meta_state & 0x00000002) and not (m & _L.KMOD_ALT):  # META_ALT_ON
        m |= _L.KMOD_LALT
    if meta_state & 0x00020000:  # META_META_LEFT_ON
        m |= _L.KMOD_LGUI
    if meta_state & 0x00040000:  # META_META_RIGHT_ON
        m |= _L.KMOD_RGUI
    if (meta_state & 0x00010000) and not (m & _L.KMOD_GUI):  # META_META_ON
        m |= _L.KMOD_LGUI
    if meta_state & 0x00100000:  # META_CAPS_LOCK_ON
        m |= _L.KMOD_CAPS
    return m


def is_android_java_available():
    return _HAS_JAVA


def get_activity():
    global _ACTIVITY
    if _ACTIVITY is not None:
        return _ACTIVITY
    if not _HAS_JAVA:
        return None
    for cls_name in ("org.beeware.android.MainActivity",):
        try:
            cls = jclass(cls_name)
            act = getattr(cls, "singletonThis", None)
            if act is not None:
                _ACTIVITY = act
                return _ACTIVITY
        except Exception:
            pass
    try:
        Python = jclass("com.chaquo.python.Python")
        platform = Python.getPlatform()
        if hasattr(platform, "getApplication"):
            _ACTIVITY = platform.getApplication()
    except Exception:
        pass
    return _ACTIVITY


def _run_on_ui_sync(fn, timeout=2.0):
    act = get_activity()
    if act is None or not hasattr(act, "runOnUiThread"):
        fn()
        return
    Looper = jclass("android.os.Looper")
    if Looper.myLooper() == Looper.getMainLooper():
        fn()
        return
    done = threading.Event()
    err = []

    class _Runner(dynamic_proxy(jclass("java.lang.Runnable"))):
        def run(self):
            try:
                fn()
            except Exception as exc:
                err.append(exc)
            finally:
                done.set()

    act.runOnUiThread(_Runner())
    done.wait(timeout)
    if err:
        raise err[0]


def bootstrap_android():
    """Attach PygameView to BeeWare MainActivity on the UI thread."""
    global _VIEW, _BRIDGE_PROXY, _BOOTSTRAPPED
    with _LOCK:
        if _BOOTSTRAPPED:
            return _VIEW is not None
        if not _HAS_JAVA:
            _BOOTSTRAPPED = True
            return False

    act = get_activity()
    if act is None:
        return False

    try:
        PygameView = jclass("org.pyaudiogaming.PygameView")
        EventBridgeIface = jclass("org.pyaudiogaming.PygameView$EventBridge")
    except Exception as exc:
        print(f"[pygame_shim] PygameView class unavailable: {exc}")
        return False

    class _PyBridge(dynamic_proxy(EventBridgeIface)):
        def onTouch(self, action, pointerId, normX, normY, pxX, pxY, pointerCount):
            pid = int(pointerId)
            nx, ny = float(normX), float(normY)
            px, py = int(pxX), int(pxY)
            prev = _LAST_TOUCH.get(pid, (nx, ny))
            dx, dy = nx - prev[0], ny - prev[1]

            if action == 0:  # DOWN
                _LAST_TOUCH[pid] = (nx, ny)
                _event.post(_event.Event(_L.FINGERDOWN, {
                    "finger_id": pid, "x": nx, "y": ny, "dx": 0.0, "dy": 0.0, "touch_id": 0
                }))
                _mouse._update_pos((px, py))
                if int(pointerCount) == 1:
                    _mouse._update_button(1, True)
                    _event.post(_event.Event(_L.MOUSEBUTTONDOWN, {
                        "pos": (px, py), "button": 1, "touch": True
                    }))
            elif action == 1:  # MOVE
                _LAST_TOUCH[pid] = (nx, ny)
                _event.post(_event.Event(_L.FINGERMOTION, {
                    "finger_id": pid, "x": nx, "y": ny, "dx": dx, "dy": dy, "touch_id": 0
                }))
                _mouse._update_pos((px, py))
                _event.post(_event.Event(_L.MOUSEMOTION, {
                    "pos": (px, py), "rel": (0, 0), "buttons": (1, 0, 0), "touch": True
                }))
            else:  # UP / CANCEL
                _LAST_TOUCH.pop(pid, None)
                _event.post(_event.Event(_L.FINGERUP, {
                    "finger_id": pid, "x": nx, "y": ny, "dx": dx, "dy": dy, "touch_id": 0
                }))
                _mouse._update_pos((px, py))
                if int(pointerCount) <= 0:
                    _mouse._update_button(1, False)
                    _event.post(_event.Event(_L.MOUSEBUTTONUP, {
                        "pos": (px, py), "button": 1, "touch": True
                    }))

        def onMultiGesture(self, pinched, rotated, cx, cy, numFingers):
            _event.post(_event.Event(_L.MULTIGESTURE, {
                "pinched": float(pinched),
                "rotated": float(rotated),
                "x": float(cx),
                "y": float(cy),
                "num_fingers": int(numFingers),
            }))

        def onKey(self, isDown, keyCode, unicodeChar, metaState):
            pg_key = _ANDROID_KEYMAP.get(int(keyCode))
            if pg_key is None and int(unicodeChar) > 0:
                ch = chr(int(unicodeChar)).lower()
                if "a" <= ch <= "z" or "0" <= ch <= "9":
                    pg_key = ord(ch)
            if pg_key is None:
                return
            mods = _meta_to_kmod(int(metaState))
            _key._set_key_state(pg_key, bool(isDown), mods)
            uni = chr(int(unicodeChar)) if int(unicodeChar) > 0 else ""
            ev_type = _L.KEYDOWN if isDown else _L.KEYUP
            _event.post(_event.Event(ev_type, {
                "key": pg_key, "mod": mods, "unicode": uni, "scancode": int(keyCode)
            }))

        def onTextInput(self, text):
            if text:
                _event.post(_event.Event(_L.TEXTINPUT, {"text": str(text)}))

        def onTextEditing(self, text):
            _event.post(_event.Event(_L.TEXTEDITING, {
                "text": str(text or ""), "start": 0, "length": len(str(text or ""))
            }))

        def onFocusChanged(self, focused):
            f = bool(focused)
            _key._set_focused(f)
            _event.post(_event.Event(_L.WINDOWFOCUSGAINED if f else _L.WINDOWFOCUSLOST))
            _event.post(_event.Event(_L.ACTIVEEVENT, {"gain": 1 if f else 0, "state": 2}))

        def onQuit(self):
            _event.post(_event.Event(_L.QUIT))

    bridge_proxy = _PyBridge()

    def _setup():
        global _VIEW, _BRIDGE_PROXY, _BOOTSTRAPPED
        view = PygameView(act)
        view.setEventBridge(bridge_proxy)
        view.attachToActivity(act)
        _VIEW = view
        _BRIDGE_PROXY = bridge_proxy
        _BOOTSTRAPPED = True

    _run_on_ui_sync(_setup)
    return _VIEW is not None


def get_view():
    if _VIEW is None and _HAS_JAVA and not _BOOTSTRAPPED:
        bootstrap_android()
    return _VIEW


def set_logical_size(w, h):
    v = get_view()
    if v is not None:
        v.setLogicalSize(int(w), int(h))


def present_bitmap(bitmap):
    v = get_view()
    if v is not None and bitmap is not None:
        v.presentBitmap(bitmap)


def set_overlay_text(text, is_error=False):
    v = get_view()
    if v is not None:
        try:
            v.setOverlayText(str(text), bool(is_error))
        except Exception:
            pass


def show_error_dialog(title, message):
    """Show native Android AlertDialog with scrollable traceback, Copy and Close buttons."""
    v = get_view()
    if v is not None and hasattr(v, "showErrorDialog"):
        try:
            v.showErrorDialog(str(title), str(message))
            return True
        except Exception:
            pass
    set_overlay_text(f"{title}\n{message}", is_error=True)
    return False


def close_app():
    """Finish Android Activity and terminate native window cleanly on game exit."""
    if not _HAS_JAVA:
        return False
    v = _VIEW
    if v is not None and hasattr(v, "closeApp"):
        try:
            v.closeApp()
            return True
        except Exception:
            pass
    act = get_activity()
    if act is not None:
        try:
            def _do_finish():
                try:
                    act.finishAndRemoveTask()
                except Exception:
                    try:
                        act.finishAffinity()
                    except Exception:
                        try:
                            act.finish()
                        except Exception:
                            pass
                try:
                    Process = jclass("android.os.Process")
                    Process.killProcess(Process.myPid())
                except Exception:
                    pass
                try:
                    jclass("java.lang.System").exit(0)
                except Exception:
                    pass

            _run_on_ui_sync(_do_finish, timeout=1.0)
            return True
        except Exception:
            pass
    try:
        Process = jclass("android.os.Process")
        Process.killProcess(Process.myPid())
        return True
    except Exception:
        return False


def set_title(title):
    act = get_activity()
    if act is None or not hasattr(act, "setTitle"):
        return
    try:
        _run_on_ui_sync(lambda: act.setTitle(str(title)), timeout=0.5)
    except Exception:
        pass


def show_keyboard():
    v = get_view()
    if v is not None:
        try:
            v.showKeyboard()
        except Exception:
            pass


def hide_keyboard():
    v = get_view()
    if v is not None:
        try:
            v.hideKeyboard()
        except Exception:
            pass


def set_fullscreen(enabled=True):
    """Safely toggle Android ActionBar / FLAG_FULLSCREEN without breaking PygameView touch dispatch."""
    if not _HAS_JAVA:
        return False
    want_fs = bool(enabled)
    v = get_view()
    act = get_activity()
    if act is None:
        return False
    try:
        WMParams = jclass("android.view.WindowManager$LayoutParams")

        def _apply_fs():
            try:
                if hasattr(act, "getSupportActionBar"):
                    ab = act.getSupportActionBar()
                    if ab is not None:
                        ab.hide() if want_fs else ab.show()
                elif hasattr(act, "getActionBar"):
                    ab = act.getActionBar()
                    if ab is not None:
                        ab.hide() if want_fs else ab.show()
            except Exception:
                pass
            try:
                win = act.getWindow()
                if win is not None:
                    if want_fs:
                        win.addFlags(WMParams.FLAG_FULLSCREEN)
                    else:
                        win.clearFlags(WMParams.FLAG_FULLSCREEN)
            except Exception:
                pass
            if v is not None:
                try:
                    v.requestFocus()
                except Exception:
                    pass

        _run_on_ui_sync(_apply_fs, timeout=1.0)
        return True
    except Exception:
        return False


def set_clipboard(text):
    if not _HAS_JAVA:
        return False
    act = get_activity()
    if act is None:
        return False
    try:
        Context = jclass("android.content.Context")
        ClipData = jclass("android.content.ClipData")

        def _do():
            cm = act.getSystemService(Context.CLIPBOARD_SERVICE)
            if cm is not None:
                cm.setPrimaryClip(ClipData.newPlainText("text", str(text)))

        _run_on_ui_sync(_do, timeout=1.0)
        return True
    except Exception:
        return False


def get_clipboard():
    if not _HAS_JAVA:
        return ""
    act = get_activity()
    if act is None:
        return ""
    result = [""]
    try:
        Context = jclass("android.content.Context")

        def _do():
            cm = act.getSystemService(Context.CLIPBOARD_SERVICE)
            if cm is not None and cm.hasPrimaryClip():
                clip = cm.getPrimaryClip()
                if clip is not None and clip.getItemCount() > 0:
                    item = clip.getItemAt(0)
                    txt = item.coerceToText(act)
                    if txt is not None:
                        result[0] = str(txt)

        _run_on_ui_sync(_do, timeout=1.0)
    except Exception:
        pass
    return result[0]
