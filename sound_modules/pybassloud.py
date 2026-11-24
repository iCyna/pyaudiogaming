# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# BASSloud ctypes wrapper for ITU-R BS.1770 / EBU R128 loudness measurement.
# Supports Windows, Linux, macOS, Android, and iOS.

import ctypes
from . import pybass
from pyaudiogaming import system

HLOUDNESS = ctypes.c_uint32
DWORD = ctypes.c_uint32
BOOL = ctypes.c_int

# Measurement mode flags for BASS_Loudness_Start / BASS_Loudness_GetLevel
BASS_LOUDNESS_CURRENT    = 0
BASS_LOUDNESS_INTEGRATED = 1
BASS_LOUDNESS_RANGE      = 2
BASS_LOUDNESS_PEAK       = 4
BASS_LOUDNESS_TRUEPEAK   = 8
BASS_LOUDNESS_AUTOFREE   = 0x8000

bassloud_module = system.load_dll('bassloud')
func_type = system.get_functype()


def _bind(name, restype, *argtypes):
    if bassloud_module is not None:
        try:
            return func_type(restype, *argtypes)((name, bassloud_module))
        except AttributeError:
            pass
    def _missing(*args):
        return 0 if restype is not None else None
    return _missing


BASS_Loudness_GetVersion = _bind('BASS_Loudness_GetVersion', DWORD)
BASS_Loudness_Start = _bind('BASS_Loudness_Start', HLOUDNESS, DWORD, DWORD, ctypes.c_int)
BASS_Loudness_Stop = _bind('BASS_Loudness_Stop', BOOL, DWORD)
BASS_Loudness_SetChannel = _bind('BASS_Loudness_SetChannel', BOOL, HLOUDNESS, DWORD, ctypes.c_int)
BASS_Loudness_GetChannel = _bind('BASS_Loudness_GetChannel', DWORD, HLOUDNESS)
BASS_Loudness_GetLevel = _bind('BASS_Loudness_GetLevel', BOOL, HLOUDNESS, DWORD, ctypes.POINTER(ctypes.c_float))
BASS_Loudness_GetLevelMulti = _bind('BASS_Loudness_GetLevelMulti', BOOL, ctypes.POINTER(HLOUDNESS), DWORD, DWORD, ctypes.POINTER(ctypes.c_float))

# Backward-compatible aliases
BASS_LOUD_GetVersion = BASS_Loudness_GetVersion
BASS_LOUD_Start = BASS_Loudness_Start
BASS_LOUD_Stop = BASS_Loudness_Stop
BASS_LOUD_GetLevel = BASS_Loudness_GetLevel
