# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# pygame.mouse pointer and button state shim.
# Supports Android and iOS.

_POS = (0, 0)
_BUTTONS = [False, False, False]
_VISIBLE = True


def _update_pos(pos):
    global _POS
    _POS = (int(pos[0]), int(pos[1]))


def _update_button(button, is_down):
    idx = int(button) - 1
    if 0 <= idx < 3:
        _BUTTONS[idx] = bool(is_down)


def get_pos():
    return _POS


def get_pressed(num_buttons=3):
    if num_buttons == 5:
        return (_BUTTONS[0], _BUTTONS[1], _BUTTONS[2], False, False)
    return tuple(_BUTTONS)


def set_visible(value):
    global _VISIBLE
    prev = _VISIBLE
    _VISIBLE = bool(value)
    return prev


def get_visible():
    return _VISIBLE
