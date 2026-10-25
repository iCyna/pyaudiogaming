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
import os 
from . import pybass 
from pyaudiogaming import system 

QWORD = pybass.QWORD 
HSTREAM = pybass.HSTREAM 
DWORD = pybass.DWORD
BOOL = pybass.BOOL

# load module:
basshrtf_module = system.load_dll('bass_hrtf')
func_type = system.get_functype() 

# --- BASS_HRTF Functions ---

# BOOL BASS_HRTF_Init(int sampleRate);
BASS_HRTF_Init = func_type(ctypes.c_byte, ctypes.c_int)(('BASS_HRTF_Init', basshrtf_module))

# BOOL BASS_HRTF_InitEx(int sampleRate, const char* bassPath, const char* phononPath, const char* sofaPath, uint32_t version);
BASS_HRTF_InitEx = func_type(ctypes.c_byte, ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong)(('BASS_HRTF_InitEx', basshrtf_module))

# void BASS_HRTF_Free(void);
BASS_HRTF_Free = func_type(None)(('BASS_HRTF_Free', basshrtf_module))

# HSTREAM BASS_HRTF_StreamCreate(DWORD sourceChan, DWORD flags);
BASS_HRTF_StreamCreate = func_type(ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong)(('BASS_HRTF_StreamCreate', basshrtf_module))

# BOOL BASS_HRTF_Set3D(HSTREAM hrtfStream, float relX, float relY, float relZ, float attenuation, int bilinear);
BASS_HRTF_Set3D = func_type(ctypes.c_byte, ctypes.c_ulong, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_int)(('BASS_HRTF_Set3D', basshrtf_module))

# BOOL BASS_HRTF_SetPositionAuto(HSTREAM hrtfStream, float relX, float relY, float relZ, float minDist, float maxDist, int bilinear);
BASS_HRTF_SetPositionAuto = func_type(ctypes.c_byte, ctypes.c_ulong, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_int)(('BASS_HRTF_SetPositionAuto', basshrtf_module))

# BOOL BASS_HRTF_SetPhysicalParams(HSTREAM hrtfStream, float relX, float relY, float relZ, float occlusion, float airAbsorption);
BASS_HRTF_SetPhysicalParams = func_type(ctypes.c_byte, ctypes.c_ulong, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float)(('BASS_HRTF_SetPhysicalParams', basshrtf_module))

# BOOL BASS_HRTF_Reset(HSTREAM hrtfStream);
BASS_HRTF_Reset = func_type(ctypes.c_byte, ctypes.c_ulong)(('BASS_HRTF_Reset', basshrtf_module))