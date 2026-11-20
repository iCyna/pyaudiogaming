# -*- coding: utf-8 -*-
# BASS_HRTF python wrapper v5.0
# copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>

__version__ = '0.5.0'
__author__ = 'ihcyna (Labubu) <phucnggo29@gmail.com>'
__doc__ = '''
pybass_hrtf.py - ctypes python module for BASS_HRTF v5.0 extension.
Supports both Zero-Overhead DSP Mode (AttachDSP for Stream, Sample, Music, MIDI, Mixer, VST, Record)
and Decode/Live Stream Mode (StreamCreate for Push Voice Chat, Decode Streams, Files, Samples, Music),
with configurable Frame Size (64..2048), Binaural HRTF, Physical Direct Filter, Parametric Reflection Reverb,
Multi-Path Effect, Virtual Surround, Ambisonics Pipeline, Panning Effect, AABB Raycast, and Smooth Sliding.
'''

import ctypes
import os
import sys
from . import pybass
from pyaudiogaming import system

QWORD = pybass.QWORD
HSTREAM = pybass.HSTREAM
HDSP = pybass.HDSP if hasattr(pybass, 'HDSP') else ctypes.c_uint32
DWORD = ctypes.c_uint32
BOOL = ctypes.c_int

# Slide attribute types for BASS_HRTF_SlideAttribute
BASS_HRTF_ATTR_OCCLUSION   = 1
BASS_HRTF_ATTR_MAX_BLEND   = 2
BASS_HRTF_ATTR_GAIN        = 3
BASS_HRTF_ATTR_AIR_ABSORB  = 4
BASS_HRTF_ATTR_REVERB_WET  = 5

# Spatialization / Panning Modes for BASS_HRTF_SetPanningMode
BASS_HRTF_MODE_BINAURAL         = 0
BASS_HRTF_MODE_PANNING          = 1
BASS_HRTF_MODE_AMBISONICS       = 2
BASS_HRTF_MODE_VIRTUAL_SURROUND = 3

# SteamAudio FX Types for BASS_HRTF_AddSteamFX / BASS_HRTF_RemoveSteamFX
BASS_HRTF_FX_DIRECT             = 1
BASS_HRTF_FX_REFLECTION         = 2
BASS_HRTF_FX_PATHING            = 3
BASS_HRTF_FX_VIRTUAL_SURROUND   = 4
BASS_HRTF_FX_AMBISONICS         = 5
BASS_HRTF_FX_PANNING            = 6

# Parameter IDs for BASS_HRTF_SetFXParam / BASS_HRTF_GetFXParam
BASS_HRTF_PARAM_OCCLUSION          = 1
BASS_HRTF_PARAM_SPATIAL_BLEND      = 2
BASS_HRTF_PARAM_GAIN               = 3
BASS_HRTF_PARAM_AIR_ABSORPTION     = 4
BASS_HRTF_PARAM_DIRECTIVITY        = 5
BASS_HRTF_PARAM_DIRECTIVITY_WEIGHT = 6
BASS_HRTF_PARAM_DIRECTIVITY_POWER  = 7
BASS_HRTF_PARAM_SOURCE_RADIUS      = 8
BASS_HRTF_PARAM_TRANS_LOW          = 9
BASS_HRTF_PARAM_TRANS_MID          = 10
BASS_HRTF_PARAM_TRANS_HIGH         = 11
BASS_HRTF_PARAM_REVERB_LOW         = 12
BASS_HRTF_PARAM_REVERB_MID         = 13
BASS_HRTF_PARAM_REVERB_HIGH        = 14
BASS_HRTF_PARAM_REVERB_EQ_LOW      = 15
BASS_HRTF_PARAM_REVERB_EQ_MID      = 16
BASS_HRTF_PARAM_REVERB_EQ_HIGH     = 17
BASS_HRTF_PARAM_REVERB_DELAY_MS    = 18
BASS_HRTF_PARAM_REVERB_WET         = 19
BASS_HRTF_PARAM_PATH_EQ_LOW        = 20
BASS_HRTF_PARAM_PATH_EQ_MID        = 21
BASS_HRTF_PARAM_PATH_EQ_HIGH       = 22
BASS_HRTF_PARAM_PATH_WET           = 23
BASS_HRTF_PARAM_AMBI_ORDER         = 24
BASS_HRTF_PARAM_SURROUND_LAYOUT    = 25
BASS_HRTF_PARAM_INTERPOLATION      = 26
BASS_HRTF_PARAM_LOW_LATENCY_FLUSH  = 27

# Material Preset IDs (0..11)
BASS_HRTF_MAT_AIR      = 0
BASS_HRTF_MAT_GENERIC  = 1
BASS_HRTF_MAT_BRICK    = 2
BASS_HRTF_MAT_CONCRETE = 3
BASS_HRTF_MAT_CERAMIC  = 4
BASS_HRTF_MAT_GRAVEL   = 5
BASS_HRTF_MAT_CARPET   = 6
BASS_HRTF_MAT_GLASS    = 7
BASS_HRTF_MAT_PLASTER  = 8
BASS_HRTF_MAT_WOOD     = 9
BASS_HRTF_MAT_METAL    = 10
BASS_HRTF_MAT_ROCK     = 11

# SteamAudio Reverb Preset IDs (0..15)
BASS_HRTF_REVERB_SMALL_ROOM   = 0
BASS_HRTF_REVERB_MEDIUM_ROOM  = 1
BASS_HRTF_REVERB_LARGE_ROOM   = 2
BASS_HRTF_REVERB_HALL         = 3
BASS_HRTF_REVERB_LONG_HALLWAY = 4
BASS_HRTF_REVERB_CAVE         = 5
BASS_HRTF_REVERB_CANYON       = 6
BASS_HRTF_REVERB_BATHROOM     = 7
BASS_HRTF_REVERB_WAREHOUSE    = 8
BASS_HRTF_REVERB_TUNNEL       = 9
BASS_HRTF_REVERB_FOREST       = 10
BASS_HRTF_REVERB_CITY         = 11
BASS_HRTF_REVERB_UNDERWATER   = 12
BASS_HRTF_REVERB_BUNKER       = 13
BASS_HRTF_REVERB_STUDIO       = 14
BASS_HRTF_REVERB_ARENA        = 15

# Speaker Layout Types for Virtual Surround
BASS_HRTF_LAYOUT_MONO         = 0
BASS_HRTF_LAYOUT_STEREO       = 1
BASS_HRTF_LAYOUT_QUAD         = 2
BASS_HRTF_LAYOUT_SURROUND_5_1 = 3
BASS_HRTF_LAYOUT_SURROUND_7_1 = 4

# Load module:
basshrtf_module = system.load_dll('bass_hrtf')
func_type = system.get_functype()

_local_frame_size = 512
_node_frame_sizes = {}
_node_fx_params = {}


def _bind(name, restype, *argtypes, fallback=None):
    if basshrtf_module is not None:
        try:
            return func_type(restype, *argtypes)((name, basshrtf_module))
        except AttributeError:
            pass
    if fallback is not None:
        return fallback
    def _missing(*args):
        return 0 if restype is not None else None
    return _missing


# Initialize BASS_HRTF with default settings: (sampleRate)
BASS_HRTF_Init = _bind('BASS_HRTF_Init', BOOL, ctypes.c_int)

_BASS_HRTF_InitEx = _bind('BASS_HRTF_InitEx', BOOL, ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, DWORD)
def BASS_HRTF_InitEx(sampleRate, bassPath=None, phononPath=None, sofaPath=None, version=0, frameSize=None):
    """Extended initialization with custom library/SOFA paths, Steam Audio version, and optional frameSize."""
    if frameSize is not None:
        BASS_HRTF_SetFrameSize(int(frameSize))
    if bassPath and isinstance(bassPath, str):
        bassPath = bassPath.encode(sys.getfilesystemencoding())
    if phononPath and isinstance(phononPath, str):
        phononPath = phononPath.encode(sys.getfilesystemencoding())
    if sofaPath and isinstance(sofaPath, str):
        sofaPath = sofaPath.encode(sys.getfilesystemencoding())
    return _BASS_HRTF_InitEx(int(sampleRate), bassPath, phononPath, sofaPath, int(version))

# Free all HRTF resources and active nodes
BASS_HRTF_Free = _bind('BASS_HRTF_Free', None)

# --- Dynamic Frame Size API ---
def _fallback_set_frame_size(fs):
    global _local_frame_size
    fs = int(fs)
    if fs < 64 or fs > 2048:
        return 0
    _local_frame_size = (fs + 15) & ~15
    return 1

def _fallback_get_frame_size():
    return _local_frame_size

def _fallback_set_node_frame_size(handle, fs):
    fs = int(fs)
    if fs < 64 or fs > 2048:
        return 0
    _node_frame_sizes[int(handle)] = (fs + 15) & ~15
    return 1

def _fallback_get_node_frame_size(handle):
    return _node_frame_sizes.get(int(handle), _local_frame_size)

BASS_HRTF_SetFrameSize = _bind('BASS_HRTF_SetFrameSize', BOOL, ctypes.c_int, fallback=_fallback_set_frame_size)
BASS_HRTF_GetFrameSize = _bind('BASS_HRTF_GetFrameSize', ctypes.c_int, fallback=_fallback_get_frame_size)
BASS_HRTF_SetNodeFrameSize = _bind('BASS_HRTF_SetNodeFrameSize', BOOL, DWORD, ctypes.c_int, fallback=_fallback_set_node_frame_size)
BASS_HRTF_GetNodeFrameSize = _bind('BASS_HRTF_GetNodeFrameSize', ctypes.c_int, DWORD, fallback=_fallback_get_node_frame_size)
BASS_HRTF_SetLiveStreamMode = _bind('BASS_HRTF_SetLiveStreamMode', BOOL, DWORD, BOOL, BOOL)

# --- Distance, Source Radius, Directivity, Spatial Blend & Sliding ---
BASS_HRTF_SetDistanceModel = _bind(
    'BASS_HRTF_SetDistanceModel', None,
    ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float
)

BASS_HRTF_SetNodeDistanceLimits = _bind(
    'BASS_HRTF_SetNodeDistanceLimits', BOOL,
    DWORD, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float
)

BASS_HRTF_SetSourceRadius = _bind('BASS_HRTF_SetSourceRadius', BOOL, DWORD, ctypes.c_float)
BASS_HRTF_SetDirectivity = _bind('BASS_HRTF_SetDirectivity', BOOL, DWORD, ctypes.c_float)
BASS_HRTF_SetDirectivityEx = _bind(
    'BASS_HRTF_SetDirectivityEx', BOOL,
    DWORD, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float
)
BASS_HRTF_SetAirAbsorptionBands = _bind(
    'BASS_HRTF_SetAirAbsorptionBands', BOOL,
    DWORD, ctypes.c_float, ctypes.c_float, ctypes.c_float
)
BASS_HRTF_SetSpatialBlend = _bind('BASS_HRTF_SetSpatialBlend', BOOL, DWORD, ctypes.c_float)
BASS_HRTF_SetStereoInput = _bind('BASS_HRTF_SetStereoInput', BOOL, DWORD, BOOL)

BASS_HRTF_SlidePosition = _bind(
    'BASS_HRTF_SlidePosition', BOOL,
    DWORD, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float
)

BASS_HRTF_SlideAttribute = _bind(
    'BASS_HRTF_SlideAttribute', BOOL,
    DWORD, ctypes.c_int, ctypes.c_float, ctypes.c_float
)

# --- DSP & Stream Creation ---
BASS_HRTF_AttachDSP = _bind('BASS_HRTF_AttachDSP', HDSP, DWORD, ctypes.c_int)
BASS_HRTF_DetachDSP = _bind('BASS_HRTF_DetachDSP', BOOL, DWORD)
BASS_HRTF_SetEnabled = _bind('BASS_HRTF_SetEnabled', BOOL, DWORD, BOOL)
BASS_HRTF_StreamCreate = _bind('BASS_HRTF_StreamCreate', HSTREAM, DWORD, DWORD)
BASS_HRTF_Reset = _bind('BASS_HRTF_Reset', BOOL, DWORD)

# --- Listener & 3D Coordinates ---
BASS_HRTF_UpdateListener = _bind(
    'BASS_HRTF_UpdateListener', None,
    ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float
)

BASS_HRTF_UpdateListenerEx = _bind(
    'BASS_HRTF_UpdateListenerEx', None,
    ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float,
    fallback=lambda x, y, z, yaw, pitch, roll=0.0: BASS_HRTF_UpdateListener(x, y, z, yaw, pitch)
)

BASS_HRTF_SetWorldPosition = _bind(
    'BASS_HRTF_SetWorldPosition', BOOL,
    DWORD, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_int
)

BASS_HRTF_SetUser3D = _bind(
    'BASS_HRTF_SetUser3D', BOOL,
    DWORD, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_int
)

BASS_HRTF_SetPosition3D = _bind(
    'BASS_HRTF_SetPosition3D', BOOL,
    DWORD,
    ctypes.c_float, ctypes.c_float, ctypes.c_float,
    ctypes.c_float, ctypes.c_float, ctypes.c_float,
    ctypes.c_float, ctypes.c_int
)

BASS_HRTF_Set3D = _bind(
    'BASS_HRTF_Set3D', BOOL,
    DWORD, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_int
)

BASS_HRTF_SetPositionAuto = _bind(
    'BASS_HRTF_SetPositionAuto', BOOL,
    DWORD, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_int
)

# --- Environment Raycast AABB & Physical Direct Filter ---
BASS_HRTF_EnvAddBoxPreset = _bind(
    'BASS_HRTF_EnvAddBoxPreset', ctypes.c_int,
    ctypes.c_int, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float
)
BASS_HRTF_EnvClearBoxes = _bind('BASS_HRTF_EnvClearBoxes', None)
BASS_HRTF_EnvSetAutoRaycast = _bind('BASS_HRTF_EnvSetAutoRaycast', None, BOOL)
BASS_HRTF_SetNodeMaterialPreset = _bind('BASS_HRTF_SetNodeMaterialPreset', BOOL, DWORD, ctypes.c_int)

BASS_HRTF_EnablePhysicalFilter = _bind('BASS_HRTF_EnablePhysicalFilter', BOOL, DWORD, BOOL)
BASS_HRTF_SetPhysicalParams = _bind(
    'BASS_HRTF_SetPhysicalParams', BOOL,
    DWORD, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float
)
BASS_HRTF_SetTransmissionBands = _bind(
    'BASS_HRTF_SetTransmissionBands', BOOL,
    DWORD, ctypes.c_float, ctypes.c_float, ctypes.c_float
)

# --- SteamAudio Extended Effects (Reflections, Pathing, Virtual Surround, Ambisonics, Panning) ---
def _fallback_add_steam_fx(handle, fx_type, preset_id=0):
    fx_type = int(fx_type)
    if fx_type == BASS_HRTF_FX_DIRECT:
        BASS_HRTF_EnablePhysicalFilter(handle, 1)
        if 0 <= int(preset_id) <= 11:
            BASS_HRTF_SetNodeMaterialPreset(handle, int(preset_id))
        return 1
    return 1

def _fallback_remove_steam_fx(handle, fx_type):
    if int(fx_type) == BASS_HRTF_FX_DIRECT:
        BASS_HRTF_EnablePhysicalFilter(handle, 0)
    return 1

def _fallback_clear_steam_fx(handle):
    BASS_HRTF_EnablePhysicalFilter(handle, 0)
    return 1

def _fallback_set_fx_param(handle, param_id, value):
    h, pid, val = int(handle), int(param_id), float(value)
    _node_fx_params[(h, pid)] = val
    if pid == BASS_HRTF_PARAM_SPATIAL_BLEND:
        return BASS_HRTF_SetSpatialBlend(h, val)
    if pid == BASS_HRTF_PARAM_DIRECTIVITY:
        return BASS_HRTF_SetDirectivity(h, val)
    if pid == BASS_HRTF_PARAM_SOURCE_RADIUS:
        return BASS_HRTF_SetSourceRadius(h, val)
    if pid in (BASS_HRTF_PARAM_OCCLUSION, BASS_HRTF_PARAM_GAIN, BASS_HRTF_PARAM_AIR_ABSORPTION):
        attr_map = {
            BASS_HRTF_PARAM_OCCLUSION: BASS_HRTF_ATTR_OCCLUSION,
            BASS_HRTF_PARAM_GAIN: BASS_HRTF_ATTR_GAIN,
            BASS_HRTF_PARAM_AIR_ABSORPTION: BASS_HRTF_ATTR_AIR_ABSORB,
        }
        return BASS_HRTF_SlideAttribute(h, attr_map[pid], val, 1.0)
    return 1

def _fallback_get_fx_param(handle, param_id):
    return float(_node_fx_params.get((int(handle), int(param_id)), 0.0))

BASS_HRTF_AddSteamFX = _bind('BASS_HRTF_AddSteamFX', BOOL, DWORD, ctypes.c_int, ctypes.c_int, fallback=_fallback_add_steam_fx)
BASS_HRTF_RemoveSteamFX = _bind('BASS_HRTF_RemoveSteamFX', BOOL, DWORD, ctypes.c_int, fallback=_fallback_remove_steam_fx)
BASS_HRTF_ClearSteamFX = _bind('BASS_HRTF_ClearSteamFX', BOOL, DWORD, fallback=_fallback_clear_steam_fx)
BASS_HRTF_SetFXParam = _bind('BASS_HRTF_SetFXParam', BOOL, DWORD, ctypes.c_int, ctypes.c_float, fallback=_fallback_set_fx_param)
BASS_HRTF_GetFXParam = _bind('BASS_HRTF_GetFXParam', ctypes.c_float, DWORD, ctypes.c_int, fallback=_fallback_get_fx_param)

BASS_HRTF_EnableReflectionEffect = _bind('BASS_HRTF_EnableReflectionEffect', BOOL, DWORD, BOOL)
BASS_HRTF_SetReflectionParams = _bind(
    'BASS_HRTF_SetReflectionParams', BOOL,
    DWORD, ctypes.c_float, ctypes.c_float, ctypes.c_float,
    ctypes.c_float, ctypes.c_float, ctypes.c_float,
    ctypes.c_float, ctypes.c_float
)
BASS_HRTF_SetReflectionPreset = _bind('BASS_HRTF_SetReflectionPreset', BOOL, DWORD, ctypes.c_int, ctypes.c_float)

BASS_HRTF_EnablePathEffect = _bind('BASS_HRTF_EnablePathEffect', BOOL, DWORD, BOOL)
BASS_HRTF_SetPathParams = _bind(
    'BASS_HRTF_SetPathParams', BOOL,
    DWORD, ctypes.c_float, ctypes.c_float, ctypes.c_float,
    ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float,
    ctypes.c_float
)

BASS_HRTF_EnableVirtualSurround = _bind('BASS_HRTF_EnableVirtualSurround', BOOL, DWORD, BOOL, ctypes.c_int)
BASS_HRTF_EnableAmbisonics = _bind('BASS_HRTF_EnableAmbisonics', BOOL, DWORD, BOOL, ctypes.c_int)
BASS_HRTF_SetPanningMode = _bind('BASS_HRTF_SetPanningMode', BOOL, DWORD, ctypes.c_int)
