# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# pygame.joystick compatibility shim for mobile platforms.
# Supports Android and iOS.

_INIT_DONE = False


def init():
    global _INIT_DONE
    _INIT_DONE = True


def quit():
    global _INIT_DONE
    _INIT_DONE = False


def get_init():
    return _INIT_DONE


def get_count():
    return 0


class Joystick:
    def __init__(self, idx=0):
        self._id = int(idx)
        self._inited = False

    def init(self):
        self._inited = True

    def quit(self):
        self._inited = False

    def get_init(self):
        return self._inited

    def get_id(self):
        return self._id

    def get_name(self):
        return ""

    def rumble(self, low_frequency, high_frequency, duration):
        return False

    def stop_rumble(self):
        return None
