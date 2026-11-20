# -*- coding: utf-8 -*-
"""pygame.time shim."""
import time as _time

_START_NS = _time.monotonic_ns()


def get_ticks():
    return (_time.monotonic_ns() - _START_NS) // 1_000_000


def wait(milliseconds):
    ms = max(0, int(milliseconds))
    t0 = _time.monotonic_ns()
    if ms > 0:
        _time.sleep(ms / 1000.0)
    return (_time.monotonic_ns() - t0) // 1_000_000


delay = wait


class Clock:
    def __init__(self):
        self._last = _time.monotonic()
        self._raw_dt = 0.0
        self._fps = 0.0

    def tick(self, framerate=0):
        now = _time.monotonic()
        elapsed = now - self._last
        if framerate and framerate > 0:
            target = 1.0 / float(framerate)
            remain = target - elapsed
            if remain > 0.001:
                _time.sleep(remain)
                now = _time.monotonic()
                elapsed = now - self._last
        self._last = now
        self._raw_dt = elapsed
        if elapsed > 0:
            self._fps = 1.0 / elapsed
        return int(elapsed * 1000.0)

    tick_busy_loop = tick

    def get_time(self):
        return int(self._raw_dt * 1000.0)

    def get_fps(self):
        return self._fps
