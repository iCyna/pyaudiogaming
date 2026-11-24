# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# pygame.key state and modifier shim.
# Supports Android and iOS.

from . import locals as _L

_FOCUSED = True
_MODS = 0
_PRESSED = set()

_NAME_TO_CODE = {
    "backspace": _L.K_BACKSPACE,
    "tab": _L.K_TAB,
    "clear": _L.K_CLEAR,
    "return": _L.K_RETURN,
    "enter": _L.K_RETURN,
    "pause": _L.K_PAUSE,
    "escape": _L.K_ESCAPE,
    "esc": _L.K_ESCAPE,
    "space": _L.K_SPACE,
    " ": _L.K_SPACE,
    "!": _L.K_EXCLAIM,
    '"': _L.K_QUOTEDBL,
    "#": _L.K_HASH,
    "$": _L.K_DOLLAR,
    "%": _L.K_PERCENT,
    "&": _L.K_AMPERSAND,
    "'": _L.K_QUOTE,
    "(": _L.K_LEFTPAREN,
    ")": _L.K_RIGHTPAREN,
    "*": _L.K_ASTERISK,
    "+": _L.K_PLUS,
    ",": _L.K_COMMA,
    "-": _L.K_MINUS,
    ".": _L.K_PERIOD,
    "/": _L.K_SLASH,
    ":": _L.K_COLON,
    ";": _L.K_SEMICOLON,
    "<": _L.K_LESS,
    "=": _L.K_EQUALS,
    ">": _L.K_GREATER,
    "?": _L.K_QUESTION,
    "@": _L.K_AT,
    "[": _L.K_LEFTBRACKET,
    "\\": _L.K_BACKSLASH,
    "]": _L.K_RIGHTBRACKET,
    "^": _L.K_CARET,
    "_": _L.K_UNDERSCORE,
    "`": _L.K_BACKQUOTE,
    "delete": _L.K_DELETE,
    "del": _L.K_DELETE,
    "caps lock": _L.K_CAPSLOCK,
    "capslock": _L.K_CAPSLOCK,
    "print screen": _L.K_PRINTSCREEN,
    "scroll lock": _L.K_SCROLLLOCK,
    "insert": _L.K_INSERT,
    "home": _L.K_HOME,
    "page up": _L.K_PAGEUP,
    "pageup": _L.K_PAGEUP,
    "end": _L.K_END,
    "page down": _L.K_PAGEDOWN,
    "pagedown": _L.K_PAGEDOWN,
    "right": _L.K_RIGHT,
    "left": _L.K_LEFT,
    "down": _L.K_DOWN,
    "up": _L.K_UP,
    "left ctrl": _L.K_LCTRL,
    "right ctrl": _L.K_RCTRL,
    "left shift": _L.K_LSHIFT,
    "right shift": _L.K_RSHIFT,
    "left alt": _L.K_LALT,
    "right alt": _L.K_RALT,
    "left meta": _L.K_LGUI,
    "right meta": _L.K_RGUI,
    "left gui": _L.K_LGUI,
    "right gui": _L.K_RGUI,
    "menu": _L.K_MENU,
}

for _c in "abcdefghijklmnopqrstuvwxyz":
    _NAME_TO_CODE[_c] = getattr(_L, f"K_{_c}")
for _d in "0123456789":
    _NAME_TO_CODE[_d] = getattr(_L, f"K_{_d}")
for _i in range(1, 16):
    _NAME_TO_CODE[f"f{_i}"] = getattr(_L, f"K_F{_i}")

_CODE_TO_NAME = {v: k for k, v in _NAME_TO_CODE.items()}


def _set_focused(val):
    global _FOCUSED
    _FOCUSED = bool(val)


def _set_key_state(code, is_down, mods=None):
    global _MODS
    if is_down:
        _PRESSED.add(code)
    else:
        _PRESSED.discard(code)
    if mods is not None:
        _MODS = int(mods)


def get_focused():
    return _FOCUSED


def get_mods():
    return _MODS


def set_mods(mods):
    global _MODS
    _MODS = int(mods)


class _PressedState:
    def __getitem__(self, code):
        return code in _PRESSED


def get_pressed():
    return _PressedState()


def key_code(name):
    if not isinstance(name, str):
        raise TypeError("key_code() argument must be str")
    key_name = name.lower().strip()
    if key_name in _NAME_TO_CODE:
        return _NAME_TO_CODE[key_name]
    if len(key_name) == 1:
        return ord(key_name)
    raise ValueError(f"Unknown key name: {name}")


def name(code):
    return _CODE_TO_NAME.get(code, "")


def start_text_input():
    from . import _android_bridge, _ios_bridge
    _android_bridge.show_keyboard()
    _ios_bridge.show_keyboard()


def stop_text_input():
    from . import _android_bridge, _ios_bridge
    _android_bridge.hide_keyboard()
    _ios_bridge.hide_keyboard()


def set_text_input_rect(rect=None):
    return None


def set_repeat(delay=0, interval=0):
    return None
