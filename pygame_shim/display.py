# -*- coding: utf-8 -*-
"""pygame.display shim backed by PygameView on Android."""
from .surface import Surface
from . import _android_bridge

_INITIALIZED = False
_SURFACE = None
_CAPTION = ""


def init():
    global _INITIALIZED
    _INITIALIZED = True
    _android_bridge.bootstrap_android()


def quit():
    global _INITIALIZED, _SURFACE
    _INITIALIZED = False
    _SURFACE = None


def get_init():
    return _INITIALIZED


def set_mode(size=(0, 0), flags=0, depth=0, display=0, vsync=0):
    global _INITIALIZED, _SURFACE
    _INITIALIZED = True
    _android_bridge.bootstrap_android()
    w = int(size[0]) if size and size[0] > 0 else 800
    h = int(size[1]) if size and size[1] > 0 else 600
    _SURFACE = Surface((w, h), flags)
    _android_bridge.set_logical_size(w, h)
    return _SURFACE


def get_surface():
    return _SURFACE


def get_window_size():
    if _SURFACE is not None:
        return _SURFACE.get_size()
    return (800, 600)


def set_caption(title, icontitle=None):
    global _CAPTION
    _CAPTION = str(title)
    _android_bridge.set_title(_CAPTION)


def get_caption():
    return (_CAPTION, _CAPTION)


def flip():
    if _SURFACE is not None and _SURFACE._bitmap is not None:
        _android_bridge.present_bitmap(_SURFACE._bitmap)


def update(rectangle=None):
    flip()
