# -*- coding: utf-8 -*-
"""pygame.scrap clipboard shim backed by Android ClipboardManager."""
from . import _android_bridge
from . import locals as _L

_INITIALIZED = False
_FALLBACK_CLIP = b""


def init():
    global _INITIALIZED
    _INITIALIZED = True


def get_init():
    return _INITIALIZED


def put(scrap_type, data):
    global _FALLBACK_CLIP
    if isinstance(data, bytes):
        text = data.decode("utf-8", errors="replace").rstrip("\x00")
        _FALLBACK_CLIP = data
    else:
        text = str(data)
        _FALLBACK_CLIP = text.encode("utf-8") + b"\x00"
    _android_bridge.set_clipboard(text)


def get(scrap_type):
    if _android_bridge.is_android_java_available():
        txt = _android_bridge.get_clipboard()
        if txt:
            return txt.encode("utf-8") + b"\x00"
    return _FALLBACK_CLIP
