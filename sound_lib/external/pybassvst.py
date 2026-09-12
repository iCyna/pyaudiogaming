# -*- coding: utf-8 -*-
# BASS_VST python wrapper
# copyright 2026 belong ihcyna (Labubu)<phucnggo29@gmail.com>.[cite: 1]
# some ideas adapted from standard pybass wrappers.[cite: 1]

__version__ = '0.1' 
__author__ = 'ihcyna (Labubu) <phucnggo29@gmail.com>' 
__doc__ = '''
pybassvst.py - is ctypes python module for BASS_VST.[cite: 1]
BASS_VST is an extension to the BASS audio library, providing the ability[cite: 1]
to use VST plugins in BASS channels (DSP effects) and load VSTi instruments.[cite: 1]
'''

import ctypes 
import os 
from . import pybass 
from pyaudiogaming import system 

QWORD = pybass.QWORD 
HSTREAM = pybass.HSTREAM 

bassvst_module = system.load_dll('bass_vst')
func_type = system.get_functype() 
pybass.BASS_PluginLoad(system.get_path('bass_vst'), 0) 

# --- BASS_VST Flags ---
BASS_VST_KEEP_CHANS = 0x00000001 
BASS_VST_SCOPE_SPECTRUM = 0x00000000 
BASS_VST_SCOPE_OSCILLATOR = 0x00000001 

# --- BASS_VST Structures ---

class BASS_VST_INFO(ctypes.Structure): 
    _fields_ = [ 
        ('channelHandle', ctypes.c_ulong),    # DWORD[cite: 1]
        ('uniqueID', ctypes.c_ulong),         # DWORD[cite: 1]
        ('effectName', ctypes.c_char * 80),   # char[80][cite: 1]
        ('effectVersion', ctypes.c_ulong),    # DWORD[cite: 1]
        ('effectVstVersion', ctypes.c_ulong), # DWORD[cite: 1]
        ('hostVstVersion', ctypes.c_ulong),   # DWORD[cite: 1]
        ('productName', ctypes.c_char * 80),  # char[80][cite: 1]
        ('vendorName', ctypes.c_char * 80),   # char[80][cite: 1]
        ('vendorVersion', ctypes.c_ulong),    # DWORD[cite: 1]
        ('chansIn', ctypes.c_ulong),          # DWORD[cite: 1]
        ('chansOut', ctypes.c_ulong),         # DWORD[cite: 1]
        ('initialDelay', ctypes.c_ulong),     # DWORD[cite: 1]
        ('hasEditor', ctypes.c_ulong),        # DWORD[cite: 1]
        ('editorWidth', ctypes.c_ulong),      # DWORD[cite: 1]
        ('editorHeight', ctypes.c_ulong),     # DWORD[cite: 1]
        ('aeffect', ctypes.c_void_p),         # AEffect*[cite: 1]
        ('isInstrument', ctypes.c_ulong),     # DWORD[cite: 1]
        ('dspHandle', ctypes.c_ulong)         # HDSP[cite: 1]
    ]

class BASS_VST_PARAM_INFO(ctypes.Structure): 
    _fields_ = [ 
        ('name', ctypes.c_char * 16),         # char[16][cite: 1]
        ('unit', ctypes.c_char * 16),         # char[16][cite: 1]
        ('display', ctypes.c_char * 16),      # char[16][cite: 1]
        ('defaultValue', ctypes.c_float)      # float[cite: 1]
    ]

# Callback type for BASS_VST_SetCallback
# typedef DWORD (CALLBACK* BASSVSTPROC)(DWORD action, DWORD param1, DWORD param2, void* user);
BASSVSTPROC = ctypes.CFUNCTYPE(ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p)

# --- BASS_VST Functions (Original) ---

# DWORD BASS_VST_ChannelSetDSP(DWORD chan, const void *dllFile, DWORD flags, int priority);[cite: 1]
BASS_VST_ChannelSetDSP = func_type(ctypes.c_ulong, ctypes.c_ulong, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_int)(('BASS_VST_ChannelSetDSP', bassvst_module)) 

# BOOL BASS_VST_ChannelRemoveDSP(DWORD chan, DWORD vstHandle);[cite: 1]
BASS_VST_ChannelRemoveDSP = func_type(ctypes.c_byte, ctypes.c_ulong, ctypes.c_ulong)(('BASS_VST_ChannelRemoveDSP', bassvst_module)) 

# DWORD BASS_VST_ChannelCreate(DWORD freq, DWORD chans, const void *dllFile, DWORD flags);[cite: 1]
BASS_VST_ChannelCreate = func_type(ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_char_p, ctypes.c_ulong)(('BASS_VST_ChannelCreate', bassvst_module)) 

# BOOL BASS_VST_ChannelFree(DWORD vstHandle);[cite: 1]
BASS_VST_ChannelFree = func_type(ctypes.c_byte, ctypes.c_ulong)(('BASS_VST_ChannelFree', bassvst_module)) 

# BOOL BASS_VST_GetInfo(DWORD vstHandle, BASS_VST_INFO *info);[cite: 1]
BASS_VST_GetInfo = func_type(ctypes.c_byte, ctypes.c_ulong, ctypes.POINTER(BASS_VST_INFO))(('BASS_VST_GetInfo', bassvst_module)) 

# int BASS_VST_GetParamCount(DWORD vstHandle);[cite: 1]
BASS_VST_GetParamCount = func_type(ctypes.c_int, ctypes.c_ulong)(('BASS_VST_GetParamCount', bassvst_module)) 

# float BASS_VST_GetParam(DWORD vstHandle, int paramIndex);[cite: 1]
BASS_VST_GetParam = func_type(ctypes.c_float, ctypes.c_ulong, ctypes.c_int)(('BASS_VST_GetParam', bassvst_module)) 

# BOOL BASS_VST_SetParam(DWORD vstHandle, int paramIndex, float value);[cite: 1]
BASS_VST_SetParam = func_type(ctypes.c_byte, ctypes.c_ulong, ctypes.c_int, ctypes.c_float)(('BASS_VST_SetParam', bassvst_module)) 

# BOOL BASS_VST_GetParamInfo(DWORD vstHandle, int paramIndex, BASS_VST_PARAM_INFO *info);[cite: 1]
BASS_VST_GetParamInfo = func_type(ctypes.c_byte, ctypes.c_ulong, ctypes.c_int, ctypes.POINTER(BASS_VST_PARAM_INFO))(('BASS_VST_GetParamInfo', bassvst_module)) 

# int BASS_VST_GetProgramCount(DWORD vstHandle);[cite: 1]
BASS_VST_GetProgramCount = func_type(ctypes.c_int, ctypes.c_ulong)(('BASS_VST_GetProgramCount', bassvst_module)) 

# int BASS_VST_GetProgram(DWORD vstHandle);[cite: 1]
BASS_VST_GetProgram = func_type(ctypes.c_int, ctypes.c_ulong)(('BASS_VST_GetProgram', bassvst_module)) 

# BOOL BASS_VST_SetProgram(DWORD vstHandle, int programIndex);[cite: 1]
BASS_VST_SetProgram = func_type(ctypes.c_byte, ctypes.c_ulong, ctypes.c_int)(('BASS_VST_SetProgram', bassvst_module)) 

# DWORD BASS_VST_EmbedEditor(DWORD vstHandle, HWND parentWindow);[cite: 1]
BASS_VST_EmbedEditor = func_type(ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p)(('BASS_VST_EmbedEditor', bassvst_module)) 

# BOOL BASS_VST_ProcessEvent(DWORD vstHandle, DWORD midiCh, DWORD midiEvent, DWORD midiVelocity);
BASS_VST_ProcessEvent = func_type(ctypes.c_byte, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong)(('BASS_VST_ProcessEvent', bassvst_module))

# BOOL BASS_VST_ProcessEventRaw(DWORD vstHandle, const void *eventData, DWORD length);
BASS_VST_ProcessEventRaw = func_type(ctypes.c_byte, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong)(('BASS_VST_ProcessEventRaw', bassvst_module))

# BOOL BASS_VST_SetBypass(DWORD vstHandle, BOOL state);
BASS_VST_SetBypass = func_type(ctypes.c_byte, ctypes.c_ulong, ctypes.c_byte)(('BASS_VST_SetBypass', bassvst_module))

# BOOL BASS_VST_GetBypass(DWORD vstHandle);
BASS_VST_GetBypass = func_type(ctypes.c_byte, ctypes.c_ulong)(('BASS_VST_GetBypass', bassvst_module))

# DWORD BASS_VST_GetChunk(DWORD vstHandle, BOOL isPreset, void **chunk);
BASS_VST_GetChunk = func_type(ctypes.c_ulong, ctypes.c_ulong, ctypes.c_byte, ctypes.POINTER(ctypes.c_void_p))(('BASS_VST_GetChunk', bassvst_module))

# DWORD BASS_VST_SetChunk(DWORD vstHandle, BOOL isPreset, const void *chunk, DWORD length);
BASS_VST_SetChunk = func_type(ctypes.c_ulong, ctypes.c_ulong, ctypes.c_byte, ctypes.c_void_p, ctypes.c_ulong)(('BASS_VST_SetChunk', bassvst_module))

# const char* BASS_VST_GetProgramName(DWORD vstHandle, int programIndex);
BASS_VST_GetProgramName = func_type(ctypes.c_char_p, ctypes.c_ulong, ctypes.c_int)(('BASS_VST_GetProgramName', bassvst_module))

# BOOL BASS_VST_SetProgramName(DWORD vstHandle, const char *name);
BASS_VST_SetProgramName = func_type(ctypes.c_byte, ctypes.c_ulong, ctypes.c_char_p)(('BASS_VST_SetProgramName', bassvst_module))

# BOOL BASS_VST_SetCallback(DWORD vstHandle, BASSVSTPROC proc, void *user);
BASS_VST_SetCallback = func_type(ctypes.c_byte, ctypes.c_ulong, BASSVSTPROC, ctypes.c_void_p)(('BASS_VST_SetCallback', bassvst_module))