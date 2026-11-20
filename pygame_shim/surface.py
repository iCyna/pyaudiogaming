# -*- coding: utf-8 -*-
"""pygame.Surface shim backed by Android Bitmap + Canvas."""
from .rect import Rect
from . import _android_bridge

_Bitmap = None
_BitmapConfig = None
_Canvas = None
_Paint = None
_Color = None
_RectF = None

if _android_bridge.is_android_java_available():
    try:
        from java import jclass as _jclass
        _Bitmap = _jclass("android.graphics.Bitmap")
        _BitmapConfig = _jclass("android.graphics.Bitmap$Config")
        _Canvas = _jclass("android.graphics.Canvas")
        _Paint = _jclass("android.graphics.Paint")
        _Color = _jclass("android.graphics.Color")
        _RectF = _jclass("android.graphics.RectF")
    except Exception:
        _Bitmap = None


def to_android_color(color):
    if isinstance(color, int):
        r = (color >> 16) & 0xFF
        g = (color >> 8) & 0xFF
        b = color & 0xFF
        a = 255
    else:
        r = int(color[0]) & 0xFF
        g = int(color[1]) & 0xFF
        b = int(color[2]) & 0xFF
        a = int(color[3]) & 0xFF if len(color) >= 4 else 255
    if _Color is not None:
        return _Color.argb(a, r, g, b)
    return (a << 24) | (r << 16) | (g << 8) | b


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
        col = to_android_color(color)
        if self._canvas is not None:
            if rect is None:
                self._canvas.drawColor(col)
                return Rect(0, 0, self._w, self._h)
            r = rect if isinstance(rect, Rect) else Rect(rect)
            p = _Paint()
            p.setColor(col)
            self._canvas.drawRect(float(r.x), float(r.y), float(r.right), float(r.bottom), p)
            return r
        return Rect(0, 0, self._w, self._h) if rect is None else (rect if isinstance(rect, Rect) else Rect(rect))

    def blit(self, source, dest, area=None, special_flags=0):
        if isinstance(dest, Rect):
            dx, dy = dest.x, dest.y
        else:
            dx, dy = int(dest[0]), int(dest[1])
        if self._canvas is not None and source is not None and getattr(source, "_bitmap", None) is not None:
            self._canvas.drawBitmap(source._bitmap, float(dx), float(dy), None)
        sw = source.get_width() if source is not None else 0
        sh = source.get_height() if source is not None else 0
        return Rect(dx, dy, sw, sh)

    def copy(self):
        s = Surface((self._w, self._h), self._flags)
        if s._canvas is not None and self._bitmap is not None:
            s._canvas.drawBitmap(self._bitmap, 0.0, 0.0, None)
        return s

    def convert(self):
        return self

    def convert_alpha(self):
        return self
