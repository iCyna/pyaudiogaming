# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# pygame.font shim backed by native Paint and Typeface.
# Supports Android and iOS.

import math
from .surface import Surface, to_android_color, to_jfloat
from . import _android_bridge

_INITIALIZED = False
_Paint = None
_Typeface = None

if _android_bridge.is_android_java_available():
    try:
        from java import jclass as _jclass
        _Paint = _jclass("android.graphics.Paint")
        _Typeface = _jclass("android.graphics.Typeface")
    except Exception:
        _Paint = None


def init():
    global _INITIALIZED
    _INITIALIZED = True


def quit():
    global _INITIALIZED
    _INITIALIZED = False


def get_init():
    return _INITIALIZED


class Font:
    def __init__(self, name=None, size=18, bold=False, italic=False):
        self._size = max(8, int(size))
        self._bold = bool(bold)
        self._italic = bool(italic)
        self._paint = None
        self._cache = {}
        self._cache_order = []
        if _Paint is not None:
            p = _Paint(_Paint.ANTI_ALIAS_FLAG)
            p.setTextSize(to_jfloat(self._size))
            if _Typeface is not None:
                style = _Typeface.NORMAL
                if self._bold and self._italic:
                    style = _Typeface.BOLD_ITALIC
                elif self._bold:
                    style = _Typeface.BOLD
                elif self._italic:
                    style = _Typeface.ITALIC
                family = _Typeface.SANS_SERIF
                if isinstance(name, str) and "mono" in name.lower() or (isinstance(name, str) and "consolas" in name.lower()):
                    family = _Typeface.MONOSPACE
                p.setTypeface(_Typeface.create(family, style))
            self._paint = p

    def get_height(self):
        if self._paint is not None:
            fm = self._paint.getFontMetrics()
            return max(1, int(math.ceil(fm.descent - fm.ascent)))
        return int(self._size * 1.25)

    get_linesize = get_height

    def size(self, text):
        s = str(text)
        if self._paint is not None:
            w = max(1, int(math.ceil(self._paint.measureText(s)))) if s else 0
            return (w, self.get_height())
        return (int(len(s) * self._size * 0.55), self.get_height())

    def render(self, text, antialias, color, background=None):
        s = str(text)
        col_key = tuple(color) if isinstance(color, (list, tuple)) else color
        bg_key = tuple(background) if isinstance(background, (list, tuple)) else background
        ckey = (s, bool(antialias), col_key, bg_key)
        cached = self._cache.get(ckey)
        if cached is not None:
            return cached
        w, h = self.size(s)
        surf = Surface((max(1, w + 2), max(1, h + 2)))
        if background is not None:
            surf.fill(background)
        if self._paint is not None and surf._canvas is not None and s:
            self._paint.setAntiAlias(bool(antialias))
            self._paint.setColor(to_android_color(color))
            fm = self._paint.getFontMetrics()
            baseline = -fm.ascent
            surf._canvas.drawText(s, to_jfloat(1.0), to_jfloat(baseline), self._paint)
        self._cache[ckey] = surf
        self._cache_order.append(ckey)
        if len(self._cache_order) > 128:
            old_k = self._cache_order.pop(0)
            old_s = self._cache.pop(old_k, None)
            if old_s is not None and getattr(old_s, "_bitmap", None) is not None:
                try:
                    old_s._bitmap.recycle()
                except Exception:
                    pass
        return surf


def SysFont(name, size, bold=False, italic=False):
    picked = name[0] if isinstance(name, (list, tuple)) and name else name
    return Font(picked, size=size, bold=bold, italic=italic)
