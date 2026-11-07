# -*- coding: utf-8 -*-
# BASS_HRTF python wrapper v3.2
# copyright 2026 belong ihcyna (Labubu)<phucnggo29@gmail.com>
# some ideas adapted from standard pybass wrappers.

__version__ = '0.3.2'
__author__ = 'ihcyna (Labubu) <phucnggo29@gmail.com>'
__doc__ = '''
pybass_hrtf.py - ctypes python module for BASS_HRTF v3.2 extension.
Supports both Zero-Overhead DSP Mode (AttachDSP for Stream, Sample, MIDI, Mixer, VST)
and Decode Stream Mode (StreamCreate), with pure Binaural HRTF by default,
optional Physical Direct Filter, Distance Culling, and Smooth Sliding.
'''

import ctypes
import os, sys
from . import pybass
from pyaudiogaming import system

QWORD = pybass.QWORD
HSTREAM = pybass.HSTREAM
HDSP = pybass.HDSP if hasattr(pybass, 'HDSP') else ctypes.c_uint32
DWORD = ctypes.c_uint32
BOOL = ctypes.c_int

# Slide attribute types for BASS_HRTF_SlideAttribute
BASS_HRTF_ATTR_OCCLUSION  = 1
BASS_HRTF_ATTR_MAX_BLEND  = 2
BASS_HRTF_ATTR_GAIN       = 3
BASS_HRTF_ATTR_AIR_ABSORB = 4

# Load module:
basshrtf_module = system.load_dll('bass_hrtf')
func_type = system.get_functype()

# Initialize BASS_HRTF with default settings: (sampleRate)
BASS_HRTF_Init = func_type(BOOL, ctypes.c_int)(('BASS_HRTF_Init', basshrtf_module))

_BASS_HRTF_InitEx = func_type(BOOL, ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, DWORD)(('BASS_HRTF_InitEx', basshrtf_module))
def BASS_HRTF_InitEx(sampleRate, bassPath=None, phononPath=None, sofaPath=None, version=0):
    """Extended initialization with custom library/SOFA paths and Steam Audio version."""
    if bassPath and isinstance(bassPath, str):
        bassPath = bassPath.encode(sys.getfilesystemencoding())
    if phononPath and isinstance(phononPath, str):
        phononPath = phononPath.encode(sys.getfilesystemencoding())
    if sofaPath and isinstance(sofaPath, str):
        sofaPath = sofaPath.encode(sys.getfilesystemencoding())
    return _BASS_HRTF_InitEx(int(sampleRate), bassPath, phononPath, sofaPath, int(version))

# Free all HRTF resources and active nodes
BASS_HRTF_Free = func_type(None)(('BASS_HRTF_Free', basshrtf_module))

# Configure global distance model: (minDist, maxDist, rolloffFactor, blendStep)
BASS_HRTF_SetDistanceModel = func_type(
    None, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float
)(('BASS_HRTF_SetDistanceModel', basshrtf_module))

# Configure distance model for a specific node: (handle, minDist, maxDist, rolloffFactor, blendStep)
BASS_HRTF_SetNodeDistanceLimits = func_type(
    BOOL, DWORD, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float
)(('BASS_HRTF_SetNodeDistanceLimits', basshrtf_module))

# Set volumetric sound source radius: (handle, radius)
BASS_HRTF_SetSourceRadius = func_type(
    BOOL, DWORD, ctypes.c_float
)(('BASS_HRTF_SetSourceRadius', basshrtf_module))

# Set source directivity/cone focus (0.0 = omnidirectional, 1.0 = directional): (handle, directivity)
BASS_HRTF_SetDirectivity = func_type(
    BOOL, DWORD, ctypes.c_float
)(('BASS_HRTF_SetDirectivity', basshrtf_module))

# Set maximum spatial blend limit (0.0 to 1.0): (handle, maxBlend)
BASS_HRTF_SetSpatialBlend = func_type(
    BOOL, DWORD, ctypes.c_float
)(('BASS_HRTF_SetSpatialBlend', basshrtf_module))

# Smoothly slide source position over time: (handle, targetX, targetY, targetZ, timeMs)
BASS_HRTF_SlidePosition = func_type(
    BOOL, DWORD, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float
)(('BASS_HRTF_SlidePosition', basshrtf_module))

# Smoothly slide attribute over time (1=Occlusion, 2=MaxBlend, 3=Gain, 4=AirAbs): (handle, attrType, targetValue, timeMs)
BASS_HRTF_SlideAttribute = func_type(
    BOOL, DWORD, ctypes.c_int, ctypes.c_float, ctypes.c_float
)(('BASS_HRTF_SlideAttribute', basshrtf_module))

# Attach/Detach zero-overhead HRTF DSP on a stereo channel: (channel, priority) / (channelOrDsp)
BASS_HRTF_AttachDSP = func_type(HDSP, DWORD, ctypes.c_int)(('BASS_HRTF_AttachDSP', basshrtf_module))
BASS_HRTF_DetachDSP = func_type(BOOL, DWORD)(('BASS_HRTF_DetachDSP', basshrtf_module))

# Enable or bypass HRTF processing for a node: (handle, enable)
BASS_HRTF_SetEnabled = func_type(BOOL, DWORD, BOOL)(('BASS_HRTF_SetEnabled', basshrtf_module))

# Create a decode-to-stereo HRTF stream from a mono float decode channel: (sourceChan, flags)
BASS_HRTF_StreamCreate = func_type(HSTREAM, DWORD, DWORD)(('BASS_HRTF_StreamCreate', basshrtf_module))

# Reset internal buffers and stop active slides for a node: (handle)
BASS_HRTF_Reset = func_type(BOOL, DWORD)(('BASS_HRTF_Reset', basshrtf_module))

# Update global listener position and orientation (auto-updates world-space nodes): (listenerX, listenerY, listenerZ, yawDeg, pitchDeg)
BASS_HRTF_UpdateListener = func_type(
    None, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float
)(('BASS_HRTF_UpdateListener', basshrtf_module))

# Set source position in world space (relative to global listener): (handle, worldX, worldY, worldZ, bilinear)
BASS_HRTF_SetWorldPosition = func_type(
    BOOL, DWORD, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_int
)(('BASS_HRTF_SetWorldPosition', basshrtf_module))

# Set relative 3D position with listener yaw rotation: (handle, userX, userY, userZ, listenerYawDeg, bilinear)
BASS_HRTF_SetUser3D = func_type(
    BOOL, DWORD, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_int
)(('BASS_HRTF_SetUser3D', basshrtf_module))

# Set explicit listener and source positions in 3D space: (handle, listenerX, listenerY, listenerZ, sourceX, sourceY, sourceZ, listenerYawDeg, bilinear)
BASS_HRTF_SetPosition3D = func_type(
    BOOL, DWORD,
    ctypes.c_float, ctypes.c_float, ctypes.c_float,
    ctypes.c_float, ctypes.c_float, ctypes.c_float,
    ctypes.c_float, ctypes.c_int
)(('BASS_HRTF_SetPosition3D', basshrtf_module))

# Set relative 3D position with manual attenuation (pass attenuation < 0 for auto distance model): (handle, userX, userY, userZ, attenuation, bilinear)
BASS_HRTF_Set3D = func_type(
    BOOL, DWORD, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_int
)(('BASS_HRTF_Set3D', basshrtf_module))

# Set relative 3D position with custom min/max distance limits: (handle, userX, userY, userZ, minDist, maxDist, bilinear)
BASS_HRTF_SetPositionAuto = func_type(
    BOOL, DWORD, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_int
)(('BASS_HRTF_SetPositionAuto', basshrtf_module))

# Enable/Disable physical direct filter (enable=False returns to 100% pure binaural HRTF): (handle, enable)
BASS_HRTF_EnablePhysicalFilter = func_type(BOOL, DWORD, BOOL)(('BASS_HRTF_EnablePhysicalFilter', basshrtf_module))

# Set relative coordinates with occlusion (0.0 to 1.0) and air absorption (0.0 to N): (handle, userX, userY, userZ, occlusion, airAbsorption)
BASS_HRTF_SetPhysicalParams = func_type(
    BOOL, DWORD, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float
)(('BASS_HRTF_SetPhysicalParams', basshrtf_module))

# Set 3-band frequency transmission through obstacles (0.0 to 1.0): (handle, lowBass, mid, highTreble)
BASS_HRTF_SetTransmissionBands = func_type(
    BOOL, DWORD, ctypes.c_float, ctypes.c_float, ctypes.c_float
)(('BASS_HRTF_SetTransmissionBands', basshrtf_module))