"""BASS_MPC wrapper"""

import ctypes
from . import pybass
from pyaudiogaming import system

# Load the bass_mpc dynamic library
bass_mpc_module = system.load_dll('bass_mpc')
func_type = system.get_functype()

# DWORD BASSDEF(BASS_MPC_StreamCreateFile)(BOOL mem, const void *file, QWORD offset, QWORD length, DWORD flags);
BASS_MPC_StreamCreateFile = func_type(ctypes.c_ulong, ctypes.c_byte, ctypes.c_void_p, pybass.QWORD, pybass.QWORD, ctypes.c_ulong)(('BASS_MPC_StreamCreateFile', bass_mpc_module))

# DWORD BASSDEF(BASS_MPC_StreamCreateURL)(const char *url, DWORD offset, DWORD flags, DOWNLOADPROC *proc, void *user);
BASS_MPC_StreamCreateURL = func_type(ctypes.c_ulong, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_ulong, pybass.DOWNLOADPROC, ctypes.c_void_p)(('BASS_MPC_StreamCreateURL', bass_mpc_module))

# DWORD BASSDEF(BASS_MPC_StreamCreateFileUser)(DWORD system, DWORD flags, const BASS_FILEPROCS *procs, void *user);
# Note: BASS_FILEPROCS structure needs to be passed correctly from pybass
BASS_MPC_StreamCreateFileUser = func_type(ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p)(('BASS_MPC_StreamCreateFileUser', bass_mpc_module))