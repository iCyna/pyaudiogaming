# -*- coding: utf-8 -*-
# BASS_HRTF python wrapper
# copyright 2026 belong ihcyna (Labubu)<phucnggo29@gmail.com>
# some ideas adapted from standard pybass wrappers.

__version__ = '0.1' 
__author__ = 'ihcyna (Labubu) <phucnggo29@gmail.com>' 
__doc__ = '''
pybass_hrtf.py - is ctypes python module for BASS_HRTF extension.
BASS_HRTF provides true 3D binaural spatialization, distance attenuation,
air absorption, and occlusion/transmission via Steam Audio integration.
'''

import ctypes 
import os, sys
from . import pybass 
from pyaudiogaming import system 

QWORD = pybass.QWORD 
HSTREAM = pybass.HSTREAM 
DWORD = ctypes.c_ulong  # Sửa từ pybass.QWORD thành c_ulong (32-bit)
BOOL = ctypes.c_byte    # Sửa lỗi pybass.BOOL không tồn tại

# load module:
basshrtf_module = system.load_dll('bass_hrtf')
func_type = system.get_functype() 

# --- BASS_HRTF Functions ---

BASS_HRTF_Init = func_type(BOOL, ctypes.c_int)(('BASS_HRTF_Init', basshrtf_module))

# Wrapper cho InitEx để xử lý an toàn kiểu chuỗi (str sang bytes) trên Python 3
_BASS_HRTF_InitEx = func_type(BOOL, ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, DWORD)(('BASS_HRTF_InitEx', basshrtf_module))
def BASS_HRTF_InitEx(sampleRate, bassPath, phononPath, sofaPath, version):
    if bassPath and isinstance(bassPath, str):
        bassPath = bassPath.encode(sys.getfilesystemencoding())
    if phononPath and isinstance(phononPath, str):
        phononPath = phononPath.encode(sys.getfilesystemencoding())
    if sofaPath and isinstance(sofaPath, str):
        sofaPath = sofaPath.encode(sys.getfilesystemencoding())
    return _BASS_HRTF_InitEx(sampleRate, bassPath, phononPath, sofaPath, version)

BASS_HRTF_Free = func_type(None)(('BASS_HRTF_Free', basshrtf_module))
BASS_HRTF_StreamCreate = func_type(HSTREAM, DWORD, DWORD)(('BASS_HRTF_StreamCreate', basshrtf_module))
BASS_HRTF_Set3D = func_type(BOOL, HSTREAM, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_int)(('BASS_HRTF_Set3D', basshrtf_module))
BASS_HRTF_SetPositionAuto = func_type(BOOL, HSTREAM, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_int)(('BASS_HRTF_SetPositionAuto', basshrtf_module))
BASS_HRTF_SetPhysicalParams = func_type(BOOL, HSTREAM, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float)(('BASS_HRTF_SetPhysicalParams', basshrtf_module))
BASS_HRTF_Reset = func_type(BOOL, HSTREAM)(('BASS_HRTF_Reset', basshrtf_module))