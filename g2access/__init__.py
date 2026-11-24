# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# G2Access compact high-performance screen reader and BASS-routed TTS engine.
# Supports Windows, Linux, macOS, Android, and iOS.

from .core import AudioPipeline, Provider, load_native_lib, pcm_to_wav
from .router import Auto, Router

__all__ = ["Router", "Auto", "Provider", "AudioPipeline", "load_native_lib", "pcm_to_wav"]
