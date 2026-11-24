# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# pygame.Surface shim backed by native Bitmap and Canvas.
# Supports Android and iOS.

from .rect import Rect
from . import _android_bridge

_Bitmap = None
_BitmapConfig = None
_Canvas = None
_Paint = None
_Color = None
_RectF = None
_jint = None
_jfloat = None

if _android_bridge.is_android_java_available():
    try:
        from java import jclass as _jclass, jint as _java_jint, jfloat as _java_jfloat
        _Bitmap = _jclass("android.graphics.Bitmap")
        _BitmapConfig = _jclass("android.graphics.Bitmap$Config")
        _Canvas = _jclass("android.graphics.Canvas")
        _Paint = _jclass("android.graphics.Paint")
        _Color = _jclass("android.graphics.Color")
        _RectF = _jclass("android.graphics.RectF")
        _jint = _java_jint
        _jfloat = _java_jfloat
    except Exception:
        _Bitmap = None


def to_jfloat(val):
    f = float(val)
    return _jfloat(f) if _jfloat is not None else f


def _parse_argb(color):
    if isinstance(color, int):
        return 255, (color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF
    r, g, b = int(color[0]) & 0xFF, int(color[1]) & 0xFF, int(color[2]) & 0xFF
    a = int(color[3]) & 0xFF if len(color) >= 4 else 255
    return a, r, g, b


def to_android_color(color):
    a, r, g, b = _parse_argb(color)
    val = (a << 24) | (r << 16) | (g << 8) | b
    if val >= 0x80000000:
        val -= 0x100000000
    return _jint(val) if _jint is not None else val


class Surface:
    def __init__(self, size, flags=0, depth=32, masks=None):
        self._w = max(1, int(size[0]))
        self._h = max(1, int(size[1]))
        self._flags = int(flags)
        self._bitmap = None
        self._canvas = None
        if _Bitmap is not None:
            self._bitmap = _Bitmap.createBitmap(self._w, self._h, _BitmapConfig.ARGB_8888)
            self._canvas = _Canvas(self._bitmap)

    def get_size(self):
        return (self._w, self._h)

    def get_width(self):
        return self._w

    def get_height(self):
        return self._h

    def get_rect(self, **kwargs):
        r = Rect(0, 0, self._w, self._h)
        for k, v in kwargs.items():
            setattr(r, k, v)
        return r

    def fill(self, color, rect=None, special_flags=0):
        a, r_c, g_c, b_c = _parse_argb(color)
        if self._canvas is not None:
            if rect is None:
                self._canvas.drawARGB(a, r_c, g_c, b_c)
                return Rect(0, 0, self._w, self._h)
            r = rect if isinstance(rect, Rect) else Rect(rect)
            p = _Paint()
            p.setColor(to_android_color(color))
            self._canvas.drawRect(to_jfloat(r.x), to_jfloat(r.y), to_jfloat(r.right), to_jfloat(r.bottom), p)
            return r
        return Rect(0, 0, self._w, self._h) if rect is None else (rect if isinstance(rect, Rect) else Rect(rect))

    def blit(self, source, dest, area=None, special_flags=0):
        if isinstance(dest, Rect):
            dx, dy = dest.x, dest.y
        else:
            dx, dy = int(dest[0]), int(dest[1])
        if self._canvas is not None and source is not None and getattr(source, "_bitmap", None) is not None:
            self._canvas.drawBitmap(source._bitmap, to_jfloat(dx), to_jfloat(dy), None)
        sw = source.get_width() if source is not None else 0
        sh = source.get_height() if source is not None else 0
        return Rect(dx, dy, sw, sh)

    def copy(self):
        s = Surface((self._w, self._h), self._flags)
        if s._canvas is not None and self._bitmap is not None:
            s._canvas.drawBitmap(self._bitmap, to_jfloat(0.0), to_jfloat(0.0), None)
        return s

    def set_clip(self, rect=None):
        self._clip = None if rect is None else (rect if isinstance(rect, Rect) else Rect(rect))

    def get_clip(self):
        return getattr(self, "_clip", None) or Rect(0, 0, self._w, self._h)

    def convert(self):
        return self

    def convert_alpha(self):
        return self
