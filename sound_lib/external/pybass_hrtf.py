# -*- coding: utf-8 -*-
# BASS_HRTF python wrapper v3.0
# copyright 2026 belong ihcyna (Labubu)<phucnggo29@gmail.com>
# some ideas adapted from standard pybass wrappers.

__version__ = '0.3'
__author__ = 'ihcyna (Labubu) <phucnggo29@gmail.com>'
__doc__ = '''
pybass_hrtf.py - ctypes python module for BASS_HRTF v3.0 extension.
Supports both Zero-Overhead DSP Mode (AttachDSP for Stream, Sample, MIDI, Mixer, VST)
and Decode Stream Mode (StreamCreate), with pure Binaural HRTF by default and
optional Physical Direct Filter (Occlusion, Transmission, Air Absorption).
'''

import ctypes
import os, sys
from . import pybass
from pyaudiogaming import system

QWORD = pybass.QWORD
HSTREAM = pybass.HSTREAM
HDSP = pybass.HDSP if hasattr(pybass, 'HDSP') else ctypes.c_ulong
DWORD = ctypes.c_ulong
BOOL = ctypes.c_int

# load module:
basshrtf_module = system.load_dll('bass_hrtf')
func_type = system.get_functype()

BASS_HRTF_Init = func_type(BOOL, ctypes.c_int)(('BASS_HRTF_Init', basshrtf_module))

_BASS_HRTF_InitEx = func_type(BOOL, ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, DWORD)(('BASS_HRTF_InitEx', basshrtf_module))
def BASS_HRTF_InitEx(sampleRate, bassPath=None, phononPath=None, sofaPath=None, version=0):
    if bassPath and isinstance(bassPath, str):
        bassPath = bassPath.encode(sys.getfilesystemencoding())
    if phononPath and isinstance(phononPath, str):
        phononPath = phononPath.encode(sys.getfilesystemencoding())
    if sofaPath and isinstance(sofaPath, str):
        sofaPath = sofaPath.encode(sys.getfilesystemencoding())
    return _BASS_HRTF_InitEx(int(sampleRate), bassPath, phononPath, sofaPath, int(version))

BASS_HRTF_Free = func_type(None)(('BASS_HRTF_Free', basshrtf_module))

# Configure global distance model: (minDist, maxDist, rolloffFactor, blendStep)
BASS_HRTF_SetDistanceModel = func_type(
    None, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float
)(('BASS_HRTF_SetDistanceModel', basshrtf_module))

BASS_HRTF_AttachDSP = func_type(HDSP, DWORD, ctypes.c_int)(('BASS_HRTF_AttachDSP', basshrtf_module))
BASS_HRTF_DetachDSP = func_type(BOOL, DWORD)(('BASS_HRTF_DetachDSP', basshrtf_module))
BASS_HRTF_SetEnabled = func_type(BOOL, DWORD, BOOL)(('BASS_HRTF_SetEnabled', basshrtf_module))

BASS_HRTF_StreamCreate = func_type(HSTREAM, DWORD, DWORD)(('BASS_HRTF_StreamCreate', basshrtf_module))
BASS_HRTF_Reset = func_type(BOOL, DWORD)(('BASS_HRTF_Reset', basshrtf_module))

# BASS_HRTF_SetUser3D(handle, userX, userY, userZ, listenerYawDeg, bilinear)
BASS_HRTF_SetUser3D = func_type(
    BOOL, DWORD, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_int
)(('BASS_HRTF_SetUser3D', basshrtf_module))

# BASS_HRTF_SetPosition3D(handle, listenerX, listenerY, listenerZ, sourceX, sourceY, sourceZ, listenerYawDeg, bilinear)
BASS_HRTF_SetPosition3D = func_type(
    BOOL, DWORD,
    ctypes.c_float, ctypes.c_float, ctypes.c_float,
    ctypes.c_float, ctypes.c_float, ctypes.c_float,
    ctypes.c_float, ctypes.c_int
)(('BASS_HRTF_SetPosition3D', basshrtf_module))

#Note: Pass attenuation = -1.0 so that C automatically calculates smooth attenuation based on DistanceModel.
# BASS_HRTF_Set3D(handle, userX, userY, userZ, attenuation, bilinear)
BASS_HRTF_Set3D = func_type(
    BOOL, DWORD, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_int
)(('BASS_HRTF_Set3D', basshrtf_module))

# BASS_HRTF_SetPositionAuto(handle, userX, userY, userZ, minDist, maxDist, bilinear)
BASS_HRTF_SetPositionAuto = func_type(
    BOOL, DWORD, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_int
)(('BASS_HRTF_SetPositionAuto', basshrtf_module))

# Enable/Disable the physical filter separately (enable=False -> Return to the original HRTF 100%)
BASS_HRTF_EnablePhysicalFilter = func_type(BOOL, DWORD, BOOL)(('BASS_HRTF_EnablePhysicalFilter', basshrtf_module))

# Set coordinates including wall obstruction (occlusion: 0.0->1.0) and air absorption (air absorption: 0.0->N)
BASS_HRTF_SetPhysicalParams = func_type(
    BOOL, DWORD, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float
)(('BASS_HRTF_SetPhysicalParams', basshrtf_module))

# Customize the sound transmission of 3 frequency bands through walls (low bass, mid, high treble: 0.0->1.0)
BASS_HRTF_SetTransmissionBands = func_type(
    BOOL, DWORD, ctypes.c_float, ctypes.c_float, ctypes.c_float
)(('BASS_HRTF_SetTransmissionBands', basshrtf_module))