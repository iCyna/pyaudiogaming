"""BASSLOUD wrapper"""

import ctypes
from . import pybass
from pyaudiogaming import system

# Load the bassloud dynamic library
bassloud_module = system.load_dll('bassloud')
func_type = system.get_functype()

# DWORD BASSDEF(BASS_LOUD_GetVersion)();
BASS_LOUD_GetVersion = func_type(ctypes.c_ulong)(('BASS_LOUD_GetVersion', bassloud_module))

# BOOL BASSDEF(BASS_LOUD_SetLevel)(DWORD handle, float level);
BASS_LOUD_SetLevel = func_type(ctypes.c_byte, ctypes.c_ulong, ctypes.c_float)(('BASS_LOUD_SetLevel', bassloud_module))

# float BASSDEF(BASS_LOUD_GetLevel)(DWORD handle);
BASS_LOUD_GetLevel = func_type(ctypes.c_float, ctypes.c_ulong)(('BASS_LOUD_GetLevel', bassloud_module))

# BOOL BASSDEF(BASS_LOUD_Start)(DWORD handle, DWORD flags);
BASS_LOUD_Start = func_type(ctypes.c_byte, ctypes.c_ulong, ctypes.c_ulong)(('BASS_LOUD_Start', bassloud_module))

# BOOL BASSDEF(BASS_LOUD_Stop)(DWORD handle);
BASS_LOUD_Stop = func_type(ctypes.c_byte, ctypes.c_ulong)(('BASS_LOUD_Stop', bassloud_module))