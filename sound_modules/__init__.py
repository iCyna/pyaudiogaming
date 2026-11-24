# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# Codec plugin registry and lazy BASS add-on loader.
# Supports Windows, Linux, macOS, Android, and iOS.

import importlib

CODECS = {
    "windows": ("pybassopus", "pybassflac", "pybasswma", "pybass_aac", "pybass_alac", "pybassmpc"),
    "linux": ("pybassopus", "pybassflac", "pybassmpc"),
    "macos": ("pybassopus", "pybassflac", "pybass_aac", "pybassmpc"),
    "android": ("pybassopus", "pybassflac", "pybass_aac", "pybass_alac", "pybassmpc"),
    "ios": ("pybassopus", "pybassflac", "pybassmpc"),
}
errors = {}


def load_all_codecs():
    """Explicitly import all optional codec wrappers for the current platform."""
    from .. import system
    for name in CODECS.get(system.get_platform()["os"], ()):
        try:
            importlib.import_module("." + name, __name__)
        except (OSError, AttributeError, ImportError) as err:
            errors[name] = str(err)
