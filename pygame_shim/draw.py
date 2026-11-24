# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# pygame.draw shim backed by native Canvas and Paint.
# Supports Android and iOS.

from .rect import Rect
from .surface import to_android_color, to_jfloat
from . import _android_bridge

_Paint = None
_PaintStyle = None
_RectF = None
_Path = None

if _android_bridge.is_android_java_available():
    try:
        from java import jclass as _jclass
        _Paint = _jclass("android.graphics.Paint")
        _PaintStyle = _jclass("android.graphics.Paint$Style")
        _RectF = _jclass("android.graphics.RectF")
        _Path = _jclass("android.graphics.Path")
    except Exception:
        _Paint = None


def _make_paint(color, width=0):
    p = _Paint(_Paint.ANTI_ALIAS_FLAG)
    p.setColor(to_android_color(color))
    if width and width > 0:
        p.setStyle(_PaintStyle.STROKE)
        p.setStrokeWidth(to_jfloat(width))
    else:
        p.setStyle(_PaintStyle.FILL)
    return p


def rect(surface, color, rect_arg, width=0, border_radius=0,
         border_top_left_radius=-1, border_top_right_radius=-1,
         border_bottom_left_radius=-1, border_bottom_right_radius=-1):
    r = rect_arg if isinstance(rect_arg, Rect) else Rect(rect_arg)
    canvas = getattr(surface, "_canvas", None)
    if canvas is not None and _Paint is not None:
        p = _make_paint(color, width)
        rf = _RectF(to_jfloat(r.x), to_jfloat(r.y), to_jfloat(r.right), to_jfloat(r.bottom))
        br = max(0, int(border_radius))
        if br > 0:
            canvas.drawRoundRect(rf, to_jfloat(br), to_jfloat(br), p)
        else:
            canvas.drawRect(rf, p)
    return r


def line(surface, color, start_pos, end_pos, width=1):
    x1, y1 = float(start_pos[0]), float(start_pos[1])
    x2, y2 = float(end_pos[0]), float(end_pos[1])
    canvas = getattr(surface, "_canvas", None)
    if canvas is not None and _Paint is not None:
        p = _make_paint(color, max(1, int(width)))
        canvas.drawLine(to_jfloat(x1), to_jfloat(y1), to_jfloat(x2), to_jfloat(y2), p)
    lx, rx = int(min(x1, x2)), int(max(x1, x2))
    ty, by = int(min(y1, y2)), int(max(y1, y2))
    return Rect(lx, ty, max(1, rx - lx), max(1, by - ty))


def lines(surface, color, closed, points, width=1):
    pts = list(points)
    if len(pts) < 2:
        return Rect(0, 0, 0, 0)
    canvas = getattr(surface, "_canvas", None)
    if canvas is not None and _Paint is not None and _Path is not None:
        p = _make_paint(color, max(1, int(width)))
        path = _Path()
        path.moveTo(to_jfloat(pts[0][0]), to_jfloat(pts[0][1]))
        for pt in pts[1:]:
            path.lineTo(to_jfloat(pt[0]), to_jfloat(pt[1]))
        if closed:
            path.close()
        canvas.drawPath(path, p)
    xs = [int(pt[0]) for pt in pts]
    ys = [int(pt[1]) for pt in pts]
    return Rect(min(xs), min(ys), max(1, max(xs) - min(xs)), max(1, max(ys) - min(ys)))


def circle(surface, color, center, radius, width=0):
    cx, cy = float(center[0]), float(center[1])
    rad = float(radius)
    canvas = getattr(surface, "_canvas", None)
    if canvas is not None and _Paint is not None:
        p = _make_paint(color, width)
        canvas.drawCircle(to_jfloat(cx), to_jfloat(cy), to_jfloat(rad), p)
    ir = int(rad)
    return Rect(int(cx) - ir, int(cy) - ir, max(1, ir * 2), max(1, ir * 2))
