# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# PyAudioGaming package entry point (audio, speech, input, and UI toolkit).
# Supports Windows, Linux, macOS, Android, and iOS.

import importlib

_LAZY_SUBMODULES = ("g2access", "sound_modules", "sound_pool", "speech", "window", "vb", "menu", "utils", "system")


def __getattr__(name):
	if name in _LAZY_SUBMODULES:
		mod = importlib.import_module("." + name, __name__)
		globals()[name] = mod
		return mod
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
