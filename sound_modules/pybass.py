# copyright(c) Max Kolosov 2009 maxkolosov@inbox.ru
# http://vosolok2008.narod.ru
# BSD license

__version__ = '0.5.1'
__versionTime__ = '2009-11-19'
__author__ = 'Max Kolosov <maxkolosov@inbox.ru>'
__doc__ = '''
pybass.py - is ctypes python module for BASS (http://www.un4seen.com).

BASS is an audio library for use in Windows, Linux and MacOSX software. Its
purpose is to provide the most powerful and efficient (yet easy to use),
sample, stream, MOD music, and recording functions. All in a tiny DLL,
under 100KB in size.

Main Features
=============
* Samples
  supports WAV/AIFF/MP3/MP2/MP1/OGG and custom generated samples
* Sample streams
  stream any sample data in 8/16/32 bit, with both "push" and "pull" systems
* File streams
  MP3/MP2/MP1/OGG/WAV/AIFF file streaming
* Internet file streaming
  stream files from the internet, including Shout/Icecast
* User file streaming
  stream files from anywhere using any delivery method
* Multi-channel streaming
  support for more than plain stereo, including multi-channel OGG/WAV/AIFF files
* MOD music
  uses the same engine as XMPlay = best accuracy, speed, and quality
* MO3 music
  MP3/OGG compressed MOD music
* Add-on system
  support for more formats is available via add-ons (aka plugins)
* Multiple outputs
  simultaneously use multiple soundcards, and move channels between them
* Recording
  flexible recording system, with support for multiple devices
* Decode without playback
  streams and MOD musics can be outputted in any way you want
* speaker assignment
  assign streams and MOD musics to specific speakers
* High precision synchronization
  synchronize events in your software to the streams and MOD musics
* DirectX 8 effects
  chorus/compressor/distortion/echo/flanger/gargle/parameq/reverb
* User defined DSP functions
  custom effects may be applied to musics and streams
* 32 bit floating-point decoding and processing
  floating-point stream/music decoding, DSP, FX, and recording
* 3D sound
  play samples/streams/musics in any 3D position, with EAX support
'''

import os, sys, ctypes, platform
from pyaudiogaming import system

bass_module=system.load_dll("bass")
func_type = system.get_functype()

QWORD = ctypes.c_uint64

def LOBYTE(a): return (ctypes.c_byte)(a)
def HIBYTE(a): return (ctypes.c_byte)((a)>>8)
def LOWORD(a): return (ctypes.c_ushort)(a)
def HIWORD(a): return (ctypes.c_ushort)((a)>>16)
def MAKEWORD(a,b): return (ctypes.c_ushort)(((a)&0xff)|((b)<<8))
def MAKELONG(a,b): return (ctypes.c_uint32)(((a)&0xffff)|((b)<<16))

BASSVERSION = 0x204
BASSVERSIONTEXT = '2.4'

HMUSIC = ctypes.c_uint32		# MOD music handle
HSAMPLE = ctypes.c_uint32	# sample handle
HCHANNEL = ctypes.c_uint32	# playing sample's channel handle
HSTREAM = ctypes.c_uint32	# sample stream handle
HRECORD = ctypes.c_uint32	# recording handle
HSYNC = ctypes.c_uint32		# synchronizer handle
HDSP = ctypes.c_uint32		# DSP handle
BASS_DSP_PROC = func_type(None, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p)
HFX = ctypes.c_uint32		# DX8 effect handle
HPLUGIN = ctypes.c_uint32	# Plugin handle

# Error codes returned by BASS_ErrorGetCode
error_descriptions = {}
BASS_OK = 0 
error_descriptions[BASS_OK] = 'all is OK'
BASS_ERROR_MEM = 1
error_descriptions[BASS_ERROR_MEM] = 'memory error'
BASS_ERROR_FILEOPEN = 2
error_descriptions[BASS_ERROR_FILEOPEN] = "can't open the file"
BASS_ERROR_DRIVER = 3
error_descriptions[BASS_ERROR_DRIVER] = "can't find a free/valid driver"
BASS_ERROR_BUFLOST = 4
error_descriptions[BASS_ERROR_BUFLOST] = 'the sample buffer was lost'
BASS_ERROR_HANDLE = 5
error_descriptions[BASS_ERROR_HANDLE] = 'invalid handle'
BASS_ERROR_FORMAT = 6
error_descriptions[BASS_ERROR_FORMAT] = 'unsupported sample format'
BASS_ERROR_POSITION = 7
error_descriptions[BASS_ERROR_POSITION] = 'invalid position'
BASS_ERROR_INIT = 8
error_descriptions[BASS_ERROR_INIT] = 'BASS_Init has not been successfully called'
BASS_ERROR_START = 9
error_descriptions[BASS_ERROR_START] = 'BASS_Start has not been successfully called'
BASS_ERROR_ALREADY = 14
error_descriptions[BASS_ERROR_ALREADY] = 'already initialized/paused/whatever'
BASS_ERROR_NOCHAN = 18
error_descriptions[BASS_ERROR_NOCHAN] = "can't get a free channel"
BASS_ERROR_ILLTYPE = 19
error_descriptions[BASS_ERROR_ILLTYPE] = 'an illegal type was specified'
BASS_ERROR_ILLPARAM = 20
error_descriptions[BASS_ERROR_ILLPARAM] = 'an illegal parameter was specified'
BASS_ERROR_NO3D = 21
error_descriptions[BASS_ERROR_NO3D] = 'no 3D support'
BASS_ERROR_NOEAX = 22
error_descriptions[BASS_ERROR_NOEAX] = 'no EAX support'
BASS_ERROR_DEVICE = 23
error_descriptions[BASS_ERROR_DEVICE] = 'illegal device number'
BASS_ERROR_NOPLAY = 24
error_descriptions[BASS_ERROR_NOPLAY] = 'not playing'
BASS_ERROR_FREQ = 25
error_descriptions[BASS_ERROR_FREQ] = 'illegal sample rate'
BASS_ERROR_NOTFILE = 27
error_descriptions[BASS_ERROR_NOTFILE] = 'the stream is not a file stream'
BASS_ERROR_NOHW = 29
error_descriptions[BASS_ERROR_NOHW] = 'no hardware voices available'
BASS_ERROR_EMPTY = 31
error_descriptions[BASS_ERROR_EMPTY] = 'the MOD music has no sequence data'
BASS_ERROR_NONET = 32
error_descriptions[BASS_ERROR_NONET] = 'no internet connection could be opened'
BASS_ERROR_CREATE = 33
error_descriptions[BASS_ERROR_CREATE] = "couldn't create the file"
BASS_ERROR_NOFX = 34
error_descriptions[BASS_ERROR_NOFX] = 'effects are not available'
BASS_ERROR_NOTAVAIL = 37
error_descriptions[BASS_ERROR_NOTAVAIL] = 'requested data is not available'
BASS_ERROR_DECODE = 38
error_descriptions[BASS_ERROR_DECODE] = 'the channel is a "decoding channel"'
BASS_ERROR_DX = 39
error_descriptions[BASS_ERROR_DX] = 'a sufficient DirectX version is not installed'
BASS_ERROR_TIMEOUT = 40
error_descriptions[BASS_ERROR_TIMEOUT] = 'connection timedout'
BASS_ERROR_FILEFORM = 41
error_descriptions[BASS_ERROR_FILEFORM] = 'unsupported file format'
BASS_ERROR_SPEAKER = 42
error_descriptions[BASS_ERROR_SPEAKER] = 'unavailable speaker'
BASS_ERROR_VERSION = 43
error_descriptions[BASS_ERROR_VERSION] = 'invalid BASS version (used by add-ons)'
BASS_ERROR_CODEC = 44
error_descriptions[BASS_ERROR_CODEC] = 'codec is not available/supported'
BASS_ERROR_ENDED = 45
error_descriptions[BASS_ERROR_ENDED] = 'the channel/file has ended'
BASS_ERROR_UNKNOWN = -1
error_descriptions[BASS_ERROR_UNKNOWN] = 'some other mystery problem'

def get_error_description(error_code = -1):
	return error_descriptions.get(error_code, 'unknown BASS error code ' + str(error_code))

# BASS_SetConfig options
BASS_CONFIG_BUFFER = 0
BASS_CONFIG_UPDATEPERIOD = 1
BASS_CONFIG_GVOL_SAMPLE = 4
BASS_CONFIG_GVOL_STREAM = 5
BASS_CONFIG_GVOL_MUSIC = 6
BASS_CONFIG_CURVE_VOL = 7
BASS_CONFIG_CURVE_PAN = 8
BASS_CONFIG_FLOATDSP = 9
BASS_CONFIG_3DALGORITHM = 10
BASS_CONFIG_NET_TIMEOUT = 11
BASS_CONFIG_NET_BUFFER = 12
BASS_CONFIG_PAUSE_NOPLAY = 13
BASS_CONFIG_NET_PREBUF = 15
BASS_CONFIG_NET_PASSIVE = 18
BASS_CONFIG_REC_BUFFER = 19
BASS_CONFIG_NET_PLAYLIST = 21
BASS_CONFIG_MUSIC_VIRTUAL = 22
BASS_CONFIG_VERIFY = 23
BASS_CONFIG_UPDATETHREADS = 24
BASS_CONFIG_NET_READTIMEOUT = 37
BASS_CONFIG_SRC = 43
BASS_CONFIG_SRC_SAMPLE = 44
BASS_CONFIG_HANDLES = 41
BASS_CONFIG_UNICODE = 42
BASS_CONFIG_VISTA_SPEAKERS = 38
BASS_CONFIG_IOS_SPEAKER = 39

#if defined(__linux__) || defined (_WIN32_WCE)
BASS_CONFIG_DEV_BUFFER = 27
#endif

# BASS_SetConfigPtr options
BASS_CONFIG_NET_AGENT = 16
BASS_CONFIG_NET_PROXY = 17
BASS_CONFIG_DEV_DEFAULT = 36

# Initialization flags
BASS_DEVICE_8BITS = 1# use 8 bit resolution, else 16 bit
BASS_DEVICE_MONO = 2# use mono, else stereo
BASS_DEVICE_3D = 4# enable 3D functionality
BASS_DEVICE_LATENCY = 256# calculate device latency (BASS_INFO struct)
BASS_DEVICE_CPSPEAKERS = 1024# detect speakers via Windows control panel
BASS_DEVICE_SPEAKERS = 2048# force enabling of speaker assignment
BASS_DEVICE_NOSPEAKER = 4096# ignore speaker arrangement
#ifdef __linux__
BASS_DEVICE_DMIX = 8192# use "dmix" (shared) output

# DirectSound interfaces (for use with BASS_GetDSoundObject)
BASS_OBJECT_DS = 1# IDirectSound
BASS_OBJECT_DS3DL = 2# IDirectSound3DListener

# Device info structure
class BASS_DEVICEINFO(ctypes.Structure):
	_fields_ = [('name', ctypes.c_char_p),#description
				('driver', ctypes.c_char_p),#driver
				('flags', ctypes.c_uint32)
				]
if platform.system().lower() == 'windows':
	if sys.getwindowsversion()[3] == 3:#VER_PLATFORM_WIN32_CE
		BASS_DEVICEINFO._fields_ = [('name', ctypes.c_wchar_p),#description
					('driver', ctypes.c_wchar_p),#driver
					('flags', ctypes.c_uint32)
					]

# BASS_DEVICEINFO flags
BASS_DEVICE_ENABLED = 1
BASS_DEVICE_DEFAULT = 2
BASS_DEVICE_INIT = 4

class BASS_INFO(ctypes.Structure):
	_fields_ = [('flags', ctypes.c_uint32),#device capabilities (DSCAPS_xxx flags)
				('hwsize', ctypes.c_uint32),#size of total device hardware memory
				('hwfree', ctypes.c_uint32),#size of free device hardware memory
				('freesam', ctypes.c_uint32),#number of free sample slots in the hardware
				('free3d', ctypes.c_uint32),#number of free 3D sample slots in the hardware
				('minrate', ctypes.c_uint32),#min sample rate supported by the hardware
				('maxrate', ctypes.c_uint32),#max sample rate supported by the hardware
				('eax', ctypes.c_int),#device supports EAX? (always FALSE if BASS_DEVICE_3D was not used)
				('minbuf', ctypes.c_uint32),#recommended minimum buffer length in ms (requires BASS_DEVICE_LATENCY)
				('dsver', ctypes.c_uint32),#DirectSound version
				('latency', ctypes.c_uint32),#delay (in ms) before start of playback (requires BASS_DEVICE_LATENCY)
				('initflags', ctypes.c_uint32),#BASS_Init "flags" parameter
				('speakers', ctypes.c_uint32),#number of speakers available
				('freq', ctypes.c_uint32)#current output rate (Vista/OSX only)
				]

# BASS_INFO flags (from DSOUND.H)
DSCAPS_CONTINUOUSRATE = 0x00000010# supports all sample rates between min/maxrate
DSCAPS_EMULDRIVER = 0x00000020# device does NOT have hardware DirectSound support
DSCAPS_CERTIFIED = 0x00000040# device driver has been certified by Microsoft
DSCAPS_SECONDARYMONO = 0x00000100# mono
DSCAPS_SECONDARYSTEREO = 0x00000200# stereo
DSCAPS_SECONDARY8BIT = 0x00000400# 8 bit
DSCAPS_SECONDARY16BIT = 0x00000800# 16 bit

# Recording device info structure
class BASS_RECORDINFO(ctypes.Structure):
	_fields_ = [('flags', ctypes.c_uint32),#DWORD flags;// device capabilities (DSCCAPS_xxx flags)
				('formats', ctypes.c_uint32),#DWORD formats;// supported standard formats (WAVE_FORMAT_xxx flags)
				('inputs', ctypes.c_uint32),#DWORD inputs;	// number of inputs
				('singlein', ctypes.c_int),#BOOL singlein;// TRUE = only 1 input can be set at a time
				('freq', ctypes.c_uint32)#DWORD freq;	// current input rate (Vista/OSX only)
				]

# BASS_RECORDINFO flags (from DSOUND.H)
DSCCAPS_EMULDRIVER = DSCAPS_EMULDRIVER# device does NOT have hardware DirectSound recording support
DSCCAPS_CERTIFIED = DSCAPS_CERTIFIED# device driver has been certified by Microsoft

# defines for formats field of BASS_RECORDINFO (from MMSYSTEM.H)
WAVE_FORMAT_1M08 = 0x00000001# 11.025 kHz, Mono,   8-bit
WAVE_FORMAT_1S08 = 0x00000002# 11.025 kHz, Stereo, 8-bit
WAVE_FORMAT_1M16 = 0x00000004# 11.025 kHz, Mono,   16-bit
WAVE_FORMAT_1S16 = 0x00000008# 11.025 kHz, Stereo, 16-bit
WAVE_FORMAT_2M08 = 0x00000010# 22.05  kHz, Mono,   8-bit
WAVE_FORMAT_2S08 = 0x00000020# 22.05  kHz, Stereo, 8-bit
WAVE_FORMAT_2M16 = 0x00000040# 22.05  kHz, Mono,   16-bit
WAVE_FORMAT_2S16 = 0x00000080# 22.05  kHz, Stereo, 16-bit
WAVE_FORMAT_4M08 = 0x00000100# 44.1   kHz, Mono,   8-bit
WAVE_FORMAT_4S08 = 0x00000200# 44.1   kHz, Stereo, 8-bit
WAVE_FORMAT_4M16 = 0x00000400# 44.1   kHz, Mono,   16-bit
WAVE_FORMAT_4S16 = 0x00000800# 44.1   kHz, Stereo, 16-bit

# Sample info structure
class BASS_SAMPLE(ctypes.Structure):
	_fields_ = [('freq', ctypes.c_uint32),#DWORD freq;// default playback rate
				('volume', ctypes.c_float),#float volume;// default volume (0-1)
				('pan', ctypes.c_float),#float pan;// default pan (-1=left, 0=middle, 1=right)
				('flags', ctypes.c_uint32),#DWORD flags;// BASS_SAMPLE_xxx flags
				('length', ctypes.c_uint32),#DWORD length;// length (in bytes)
				('max', ctypes.c_uint32),#DWORD max;// maximum simultaneous playbacks
				('origres', ctypes.c_uint32),#DWORD origres;// original resolution bits
				('chans', ctypes.c_uint32),#DWORD chans;// number of channels
				('mingap', ctypes.c_uint32),#DWORD mingap;	// minimum gap (ms) between creating channels
				('mode3d', ctypes.c_uint32),#DWORD mode3d;// BASS_3DMODE_xxx mode
				('mindist', ctypes.c_float),#float mindist;// minimum distance
				('maxdist', ctypes.c_float),#float maxdist;// maximum distance
				('iangle', ctypes.c_uint32),#DWORD iangle;// angle of inside projection cone
				('oangle', ctypes.c_uint32),#DWORD oangle;// angle of outside projection cone
				('outvol', ctypes.c_float),#float outvol;// delta-volume outside the projection cone
				('vam', ctypes.c_uint32),#DWORD vam;// voice allocation/management flags (BASS_VAM_xxx)
				('priority', ctypes.c_uint32)#DWORD priority;// priority (0=lowest, 0xffffffff=highest)
				]

BASS_SAMPLE_8BITS = 1# 8 bit
BASS_SAMPLE_FLOAT = 256# 32-bit floating-point
BASS_SAMPLE_MONO = 2# mono
BASS_SAMPLE_LOOP = 4# looped
BASS_SAMPLE_3D = 8# 3D functionality
BASS_SAMPLE_SOFTWARE = 16# not using hardware mixing
BASS_SAMPLE_MUTEMAX = 32# mute at max distance (3D only)
BASS_SAMPLE_VAM = 64# DX7 voice allocation & management
BASS_SAMPLE_FX = 128# old implementation of DX8 effects
BASS_SAMPLE_OVER_VOL = 0x10000# override lowest volume
BASS_SAMPLE_OVER_POS = 0x20000# override longest playing
BASS_SAMPLE_OVER_DIST = 0x30000# override furthest from listener (3D only)
BASS_STREAM_PRESCAN = 0x20000# enable pin-point seeking/length (MP3/MP2/MP1)
BASS_MP3_SETPOS = BASS_STREAM_PRESCAN
BASS_STREAM_AUTOFREE = 0x40000# automatically free the stream when it stop/ends
BASS_STREAM_RESTRATE = 0x80000# restrict the download rate of internet file streams
BASS_STREAM_BLOCK = 0x100000# download/play internet file stream in small blocks
BASS_STREAM_DECODE = 0x200000# don't play the stream, only decode (BASS_ChannelGetData)
BASS_STREAM_STATUS = 0x800000# give server status info (HTTP/ICY tags) in DOWNLOADPROC

BASS_MUSIC_FLOAT = BASS_SAMPLE_FLOAT
BASS_MUSIC_MONO = BASS_SAMPLE_MONO
BASS_MUSIC_LOOP = BASS_SAMPLE_LOOP
BASS_MUSIC_3D = BASS_SAMPLE_3D
BASS_MUSIC_FX = BASS_SAMPLE_FX
BASS_MUSIC_AUTOFREE = BASS_STREAM_AUTOFREE
BASS_MUSIC_DECODE = BASS_STREAM_DECODE
BASS_MUSIC_PRESCAN = BASS_STREAM_PRESCAN# calculate playback length
BASS_MUSIC_CALCLEN = BASS_MUSIC_PRESCAN
BASS_MUSIC_RAMP = 0x200# normal ramping
BASS_MUSIC_RAMPS = 0x400# sensitive ramping
BASS_MUSIC_SURROUND = 0x800# surround sound
BASS_MUSIC_SURROUND2 = 0x1000# surround sound (mode 2)
BASS_MUSIC_FT2MOD = 0x2000# play .MOD as FastTracker 2 does
BASS_MUSIC_PT1MOD = 0x4000# play .MOD as ProTracker 1 does
BASS_MUSIC_NONINTER = 0x10000# non-interpolated sample mixing
BASS_MUSIC_SINCINTER = 0x800000# sinc interpolated sample mixing
BASS_MUSIC_POSRESET = 0x8000# stop all notes when moving position
BASS_MUSIC_POSRESETEX = 0x400000# stop all notes and reset bmp/etc when moving position
BASS_MUSIC_STOPBACK = 0x80000# stop the music on a backwards jump effect
BASS_MUSIC_NOSAMPLE = 0x100000# don't load the samples

# speaker assignment flags
BASS_SPEAKER_FRONT = 0x1000000# front speakers
BASS_SPEAKER_REAR = 0x2000000# rear/side speakers
BASS_SPEAKER_CENLFE = 0x3000000# center & LFE speakers (5.1)
BASS_SPEAKER_REAR2 = 0x4000000# rear center speakers (7.1)
def BASS_SPEAKER_N(n): return ((n)<<24)# n'th pair of speakers (max 15)
BASS_SPEAKER_LEFT = 0x10000000# modifier: left
BASS_SPEAKER_RIGHT = 0x20000000# modifier: right
BASS_SPEAKER_FRONTLEFT = BASS_SPEAKER_FRONT|BASS_SPEAKER_LEFT
BASS_SPEAKER_FRONTRIGHT = BASS_SPEAKER_FRONT|BASS_SPEAKER_RIGHT
BASS_SPEAKER_REARLEFT = BASS_SPEAKER_REAR|BASS_SPEAKER_LEFT
BASS_SPEAKER_REARRIGHT = BASS_SPEAKER_REAR|BASS_SPEAKER_RIGHT
BASS_SPEAKER_CENTER = BASS_SPEAKER_CENLFE|BASS_SPEAKER_LEFT
BASS_SPEAKER_LFE = BASS_SPEAKER_CENLFE|BASS_SPEAKER_RIGHT
BASS_SPEAKER_REAR2LEFT = BASS_SPEAKER_REAR2|BASS_SPEAKER_LEFT
BASS_SPEAKER_REAR2RIGHT = BASS_SPEAKER_REAR2|BASS_SPEAKER_RIGHT
BASS_UNICODE = (-2147483648)
BASS_RECORD_PAUSE = 0x8000# start recording paused

# DX7 voice allocation & management flags
BASS_VAM_HARDWARE = 1
BASS_VAM_SOFTWARE = 2
BASS_VAM_TERM_TIME = 4
BASS_VAM_TERM_DIST = 8
BASS_VAM_TERM_PRIO = 16

# Channel info structure
class BASS_CHANNELINFO(ctypes.Structure):
	_fields_ = [('freq', ctypes.c_uint32),#DWORD freq;// default playback rate
				('chans', ctypes.c_uint32),#DWORD chans;// channels
				('flags', ctypes.c_uint32),#DWORD flags;// BASS_SAMPLE/STREAM/MUSIC/SPEAKER flags
				('ctype', ctypes.c_uint32),#DWORD ctype;// type of channel
				('origres', ctypes.c_uint32),#DWORD origres;// original resolution
				('plugin', HPLUGIN),#HPLUGIN plugin;// plugin
				('sample', HSAMPLE),#HSAMPLE sample;// sample
				('filename', ctypes.c_char_p)#const char *filename;// filename
				]

BASS_CTYPE_SAMPLE = 1
BASS_CTYPE_RECORD = 2
BASS_CTYPE_STREAM = 0x10000
BASS_CTYPE_STREAM_OGG = 0x10002
BASS_CTYPE_STREAM_MP1 = 0x10003
BASS_CTYPE_STREAM_MP2 = 0x10004
BASS_CTYPE_STREAM_MP3 = 0x10005
BASS_CTYPE_STREAM_AIFF = 0x10006
BASS_CTYPE_STREAM_CA = 0x10007
BASS_CTYPE_STREAM_WAV = 0x40000# WAVE flag, LOWORD=codec
BASS_CTYPE_STREAM_WAV_PCM = 0x50001
BASS_CTYPE_STREAM_WAV_FLOAT = 0x50003
BASS_CTYPE_MUSIC_MOD = 0x20000
BASS_CTYPE_MUSIC_MTM = 0x20001
BASS_CTYPE_MUSIC_S3M = 0x20002
BASS_CTYPE_MUSIC_XM = 0x20003
BASS_CTYPE_MUSIC_IT = 0x20004
BASS_CTYPE_MUSIC_MO3 = 0x00100# MO3 flag

class BASS_PLUGINFORM(ctypes.Structure):
	_fields_ = [('ctype', ctypes.c_uint32),#DWORD ctype;		// channel type
				('name', ctypes.c_char_p),#const char *name;	// format description
				('exts', ctypes.c_char_p)#const char *exts;	// file extension filter (*.ext1;*.ext2;etc...)
				]
if platform.system().lower() == 'windows':
	if sys.getwindowsversion()[3] == 3:#VER_PLATFORM_WIN32_CE
		BASS_PLUGINFORM._fields_ = [('ctype', ctypes.c_uint32),#DWORD ctype;		// channel type
					('name', ctypes.c_wchar_p),#const wchar_t *name;	// format description
					('exts', ctypes.c_wchar_p)#const wchar_t *exts;	// file extension filter (*.ext1;*.ext2;etc...)
					]

class BASS_PLUGININFO(ctypes.Structure):
	_fields_ = [('version', ctypes.c_uint32),#DWORD version;// version (same form as BASS_GetVersion)
				('formatc', ctypes.c_uint32),#DWORD formatc;// number of formats
				('formats', ctypes.POINTER(BASS_PLUGINFORM))#const BASS_PLUGINFORM *formats;// the array of formats
				]

# 3D vector (for 3D positions/velocities/orientations)
class BASS_3DVECTOR(ctypes.Structure):
	_fields_ = [('x', ctypes.c_float),#float x;// +=right, -=left
				('y', ctypes.c_float),#float y;// +=up, -=down
				('z', ctypes.c_float)#float z;// +=front, -=behind
				]

# 3D channel modes
BASS_3DMODE_NORMAL = 0
BASS_3DMODE_RELATIVE = 1
BASS_3DMODE_OFF = 2

# software 3D mixing algorithms (used with BASS_CONFIG_3DALGORITHM)
BASS_3DALG_DEFAULT = 0
BASS_3DALG_OFF = 1
BASS_3DALG_FULL = 2
BASS_3DALG_LIGHT = 3

# EAX environments, use with BASS_SetEAXParameters
EAX_ENVIRONMENT_GENERIC = 0
EAX_ENVIRONMENT_PADDEDCELL = 1
EAX_ENVIRONMENT_ROOM = 2
EAX_ENVIRONMENT_BATHROOM = 3
EAX_ENVIRONMENT_LIVINGROOM = 4
EAX_ENVIRONMENT_STONEROOM = 5
EAX_ENVIRONMENT_AUDITORIUM = 6
EAX_ENVIRONMENT_CONCERTHALL = 7
EAX_ENVIRONMENT_CAVE = 8
EAX_ENVIRONMENT_ARENA = 9
EAX_ENVIRONMENT_HANGAR = 10
EAX_ENVIRONMENT_CARPETEDHALLWAY = 11
EAX_ENVIRONMENT_HALLWAY = 12
EAX_ENVIRONMENT_STONECORRIDOR = 13
EAX_ENVIRONMENT_ALLEY = 14
EAX_ENVIRONMENT_FOREST = 15
EAX_ENVIRONMENT_CITY = 16
EAX_ENVIRONMENT_MOUNTAINS = 17
EAX_ENVIRONMENT_QUARRY = 18
EAX_ENVIRONMENT_PLAIN = 19
EAX_ENVIRONMENT_PARKINGLOT = 20
EAX_ENVIRONMENT_SEWERPIPE = 21
EAX_ENVIRONMENT_UNDERWATER = 22
EAX_ENVIRONMENT_DRUGGED = 23
EAX_ENVIRONMENT_DIZZY = 24
EAX_ENVIRONMENT_PSYCHOTIC = 25
EAX_ENVIRONMENT_COUNT = 26# total number of environments

# EAX presets, usage: BASS_SetEAXParameters(EAX_PRESET_xxx)
EAX_PRESET_GENERIC         =(EAX_ENVIRONMENT_GENERIC,0.5,1.493,0.5)
EAX_PRESET_PADDEDCELL      =(EAX_ENVIRONMENT_PADDEDCELL,0.25,0.1,0.0)
EAX_PRESET_ROOM            =(EAX_ENVIRONMENT_ROOM,0.417,0.4,0.666)
EAX_PRESET_BATHROOM        =(EAX_ENVIRONMENT_BATHROOM,0.653,1.499,0.166)
EAX_PRESET_LIVINGROOM      =(EAX_ENVIRONMENT_LIVINGROOM,0.208,0.478,0.0)
EAX_PRESET_STONEROOM       =(EAX_ENVIRONMENT_STONEROOM,0.5,2.309,0.888)
EAX_PRESET_AUDITORIUM      =(EAX_ENVIRONMENT_AUDITORIUM,0.403,4.279,0.5)
EAX_PRESET_CONCERTHALL     =(EAX_ENVIRONMENT_CONCERTHALL,0.5,3.961,0.5)
EAX_PRESET_CAVE            =(EAX_ENVIRONMENT_CAVE,0.5,2.886,1.304)
EAX_PRESET_ARENA           =(EAX_ENVIRONMENT_ARENA,0.361,7.284,0.332)
EAX_PRESET_HANGAR          =(EAX_ENVIRONMENT_HANGAR,0.5,10.0,0.3)
EAX_PRESET_CARPETEDHALLWAY =(EAX_ENVIRONMENT_CARPETEDHALLWAY,0.153,0.259,2.0)
EAX_PRESET_HALLWAY         =(EAX_ENVIRONMENT_HALLWAY,0.361,1.493,0.0)
EAX_PRESET_STONECORRIDOR   =(EAX_ENVIRONMENT_STONECORRIDOR,0.444,2.697,0.638)
EAX_PRESET_ALLEY           =(EAX_ENVIRONMENT_ALLEY,0.25,1.752,0.776)
EAX_PRESET_FOREST          =(EAX_ENVIRONMENT_FOREST,0.111,3.145,0.472)
EAX_PRESET_CITY            =(EAX_ENVIRONMENT_CITY,0.111,2.767,0.224)
EAX_PRESET_MOUNTAINS       =(EAX_ENVIRONMENT_MOUNTAINS,0.194,7.841,0.472)
EAX_PRESET_QUARRY          =(EAX_ENVIRONMENT_QUARRY,1.0,1.499,0.5)
EAX_PRESET_PLAIN           =(EAX_ENVIRONMENT_PLAIN,0.097,2.767,0.224)
EAX_PRESET_PARKINGLOT      =(EAX_ENVIRONMENT_PARKINGLOT,0.208,1.652,1.5)
EAX_PRESET_SEWERPIPE       =(EAX_ENVIRONMENT_SEWERPIPE,0.652,2.886,0.25)
EAX_PRESET_UNDERWATER      =(EAX_ENVIRONMENT_UNDERWATER,1.0,1.499,0.0)
EAX_PRESET_DRUGGED         =(EAX_ENVIRONMENT_DRUGGED,0.875,8.392,1.388)
EAX_PRESET_DIZZY           =(EAX_ENVIRONMENT_DIZZY,0.139,17.234,0.666)
EAX_PRESET_PSYCHOTIC       =(EAX_ENVIRONMENT_PSYCHOTIC,0.486,7.563,0.806)

#typedef DWORD (CALLBACK STREAMPROC)(HSTREAM handle, void *buffer, DWORD length, void *user);
STREAMPROC = func_type(ctypes.c_uint32, HSTREAM, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p) 
# User stream callback function. NOTE: A stream function should obviously be as quick
#as possible, other streams (and MOD musics) can't be mixed until it's finished.
#handle : The stream that needs writing
#buffer : Buffer to write the samples in
#length : Number of bytes to write
#user   : The 'user' parameter value given when calling BASS_StreamCreate
#RETURN : Number of bytes written. Set the BASS_STREAMPROC_END flag to end the stream.

#~ def user_stream_callback_function(handle, buffer, length, user):
	#~ b = ctypes.cast(buffer, ctypes.c_char_p)
	#~ ctypes.memset(b, 0, length)
	#~ data = ctypes.c_char_p(' ' * length)
	#~ ctypes.memmove(b, data, length)
	#~ if your_custom_function_is_eof() or your_custom_flag_is_eof:
		#~ length |= BASS_STREAMPROC_END
	#~ return length
#~ user_func = STREAMPROC(user_stream_callback_function)

BASS_STREAMPROC_END = (-2147483648)# end of user stream flag

# special STREAMPROCs
def streamproc_dummy(handle, buffer, length, user): return 0
streamproc_push = -1
STREAMPROC_DUMMY = STREAMPROC(streamproc_dummy)# "dummy" stream
STREAMPROC_PUSH = STREAMPROC(streamproc_push)# push stream

# BASS_StreamCreateFileUser file systems
STREAMFILE_NOBUFFER = 0
STREAMFILE_BUFFER = 1
STREAMFILE_BUFFERPUSH = 2

# User file stream callback functions
#typedef void (CALLBACK FILECLOSEPROC)(void *user);
FILECLOSEPROC = func_type(None, ctypes.c_void_p) 
#typedef QWORD (CALLBACK FILELENPROC)(void *user);
FILELENPROC = func_type(QWORD, ctypes.c_void_p) 
#typedef DWORD (CALLBACK FILEREADPROC)(void *buffer, DWORD length, void *user);
FILEREADPROC = func_type(ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p) 
#typedef BOOL (CALLBACK FILESEEKPROC)(QWORD offset, void *user);
FILESEEKPROC = func_type(ctypes.c_int, QWORD, ctypes.c_void_p) 

class BASS_FILEPROCS(ctypes.Structure):
	_fields_ = [('close', FILECLOSEPROC),#FILECLOSEPROC *close;
				('length', FILELENPROC),#FILELENPROC *length;
				('read', FILEREADPROC),#FILEREADPROC *read;
				('seek', FILESEEKPROC)#FILESEEKPROC *seek;
				]

# BASS_StreamPutFileData options
BASS_FILEDATA_END = 0

# BASS_StreamGetFilePosition modes
BASS_FILEPOS_CURRENT = 0
BASS_FILEPOS_DECODE = BASS_FILEPOS_CURRENT
BASS_FILEPOS_DOWNLOAD = 1
BASS_FILEPOS_END = 2
BASS_FILEPOS_START = 3
BASS_FILEPOS_CONNECTED = 4
BASS_FILEPOS_BUFFER = 5
BASS_FILEPOS_SOCKET = 6

#typedef void (CALLBACK DOWNLOADPROC)(const void *buffer, DWORD length, void *user);
DOWNLOADPROC = func_type(None, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p) 
# Internet stream download callback function.
#buffer : Buffer containing the downloaded data... NULL=end of download
#length : Number of bytes in the buffer
#user   : The 'user' parameter value given when calling BASS_StreamCreateURL

# BASS_ChannelSetSync types
BASS_SYNC_POS = 0
BASS_SYNC_END = 2
BASS_SYNC_META = 4
BASS_SYNC_SLIDE = 5
BASS_SYNC_STALL = 6
BASS_SYNC_DOWNLOAD = 7
BASS_SYNC_FREE = 8
BASS_SYNC_SETPOS = 11
BASS_SYNC_MUSICPOS = 10
BASS_SYNC_MUSICINST = 1
BASS_SYNC_MUSICFX = 3
BASS_SYNC_OGG_CHANGE = 12
BASS_SYNC_MIXTIME = 0x40000000
BASS_SYNC_ONETIME = (-2147483648)

#typedef void (CALLBACK SYNCPROC)(HSYNC handle, DWORD channel, DWORD data, void *user);
SYNCPROC = func_type(None, HSYNC, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p) 
# Sync callback function. NOTE: a sync callback function should be very
#quick as other syncs can't be processed until it has finished. If the sync
#is a "mixtime" sync, then other streams and MOD musics can't be mixed until
#it's finished either.
#handle : The sync that has occured
#channel: Channel that the sync occured in
#data   : Additional data associated with the sync's occurance
#user   : The 'user' parameter given when calling BASS_ChannelSetSync

#typedef void (CALLBACK DSPPROC)(HDSP handle, DWORD channel, void *buffer, DWORD length, void *user);
DSPPROC = func_type(None, HDSP, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p) 
# DSP callback function. NOTE: A DSP function should obviously be as quick as
#possible... other DSP functions, streams and MOD musics can not be processed
#until it's finished.
#handle : The DSP handle
#channel: Channel that the DSP is being applied to
#buffer : Buffer to apply the DSP to
#length : Number of bytes in the buffer
#user   : The 'user' parameter given when calling BASS_ChannelSetDSP

#typedef BOOL (CALLBACK RECORDPROC)(HRECORD handle, const void *buffer, DWORD length, void *user);
RECORDPROC = func_type(ctypes.c_int, HRECORD, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p) 
# Recording callback function.
#handle : The recording handle
#buffer : Buffer containing the recorded sample data
#length : Number of bytes
#user   : The 'user' parameter value given when calling BASS_RecordStart
#RETURN : TRUE = continue recording, FALSE = stop

# BASS_ChannelIsActive return values
BASS_ACTIVE_STOPPED = 0
BASS_ACTIVE_PLAYING = 1
BASS_ACTIVE_STALLED = 2
BASS_ACTIVE_PAUSED = 3

# Channel attributes
BASS_ATTRIB_FREQ = 1
BASS_ATTRIB_VOL = 2
BASS_ATTRIB_PAN = 3
BASS_ATTRIB_EAXMIX = 4
BASS_ATTRIB_MUSIC_AMPLIFY = 0x100
BASS_ATTRIB_MUSIC_PANSEP = 0x101
BASS_ATTRIB_MUSIC_PSCALER = 0x102
BASS_ATTRIB_MUSIC_BPM = 0x103
BASS_ATTRIB_MUSIC_SPEED = 0x104
BASS_ATTRIB_MUSIC_VOL_GLOBAL = 0x105
BASS_ATTRIB_MUSIC_VOL_CHAN = 0x200# + channel #
BASS_ATTRIB_MUSIC_VOL_INST = 0x300# + instrument #

# BASS_ChannelGetData flags
BASS_DATA_AVAILABLE = 0# query how much data is buffered
BASS_DATA_FLOAT = 0x40000000# flag: return floating-point sample data
BASS_DATA_FFT256 = (-2147483648)# 256 sample FFT
BASS_DATA_FFT512 = (-2147483647)# 512 FFT
BASS_DATA_FFT1024 = (-2147483646)# 1024 FFT
BASS_DATA_FFT2048 = (-2147483645)# 2048 FFT
BASS_DATA_FFT4096 = (-2147483644)# 4096 FFT
BASS_DATA_FFT8192 = (-2147483643)# 8192 FFT
BASS_DATA_FFT_INDIVIDUAL = 0x10# FFT flag: FFT for each channel, else all combined
BASS_DATA_FFT_NOWINDOW = 0x20# FFT flag: no Hanning window

# BASS_ChannelGetTags types : what's returned
BASS_TAG_ID3 = 0# ID3v1 tags : TAG_ID3 structure
BASS_TAG_ID3V2 = 1# ID3v2 tags : variable length block
BASS_TAG_OGG = 2# OGG comments : series of null-terminated UTF-8 strings
BASS_TAG_HTTP = 3# HTTP headers : series of null-terminated ANSI strings
BASS_TAG_ICY = 4# ICY headers : series of null-terminated ANSI strings
BASS_TAG_META = 5# ICY metadata : ANSI string
BASS_TAG_VENDOR = 9# OGG encoder : UTF-8 string
BASS_TAG_LYRICS3 = 10# Lyric3v2 tag : ASCII string
BASS_TAG_CA_CODEC = 11# CoreAudio codec info : TAG_CA_CODEC structure
BASS_TAG_RIFF_INFO = 0x100# RIFF "INFO" tags : series of null-terminated ANSI strings
BASS_TAG_RIFF_BEXT = 0x101# RIFF/BWF "bext" tags : TAG_BEXT structure
BASS_TAG_RIFF_CART = 0x102# RIFF/BWF "cart" tags : TAG_CART structure
BASS_TAG_MUSIC_NAME = 0x10000# MOD music name : ANSI string
BASS_TAG_MUSIC_MESSAGE = 0x10001# MOD message : ANSI string
BASS_TAG_MUSIC_ORDERS = 0x10002# MOD order list : BYTE array of pattern numbers
BASS_TAG_MUSIC_INST = 0x10100# + instrument #, MOD instrument name : ANSI string
BASS_TAG_MUSIC_SAMPLE = 0x10300# + sample #, MOD sample name : ANSI string

# ID3v1 tag structure
class TAG_ID3(ctypes.Structure):
	_fields_ = [('id', ctypes.c_char*3),#char id[3];
				('title', ctypes.c_char*30),#char title[30];
				('artist', ctypes.c_char*30),#char artist[30];
				('album', ctypes.c_char*30),#char album[30];
				('year', ctypes.c_char*4),#char year[4];
				('comment', ctypes.c_char*30),#char comment[30];
				('genre', ctypes.c_byte)#BYTE genre;
				]

# BWF "bext" tag structure
class TAG_BEXT(ctypes.Structure):
	_fields_ = [('Description', ctypes.c_char*256),#char Description[256];// description
				('Originator', ctypes.c_char*32),#char Originator[32];// name of the originator
				('OriginatorReference', ctypes.c_char*32),#char OriginatorReference[32];// reference of the originator
				('OriginationDate', ctypes.c_char*10),#char OriginationDate[10];// date of creation (yyyy-mm-dd)
				('OriginationTime', ctypes.c_char*8),#char OriginationTime[8];// time of creation (hh-mm-ss)
				('TimeReference', QWORD),#QWORD TimeReference;// first sample count since midnight (little-endian)
				('Version', ctypes.c_ushort),#WORD Version;// BWF version (little-endian)
				('UMID', ctypes.c_byte*64),#BYTE UMID[64];// SMPTE UMID
				('Reserved', ctypes.c_byte*190),#BYTE Reserved[190];
				('CodingHistory', ctypes.c_char_p)#char CodingHistory[];// history
				]

# BWF "cart" tag structures
class TAG_CART_TIMER(ctypes.Structure):
	_fields_ = [('dwUsage', ctypes.c_uint32),#DWORD dwUsage;// FOURCC timer usage ID
				('dwValue', ctypes.c_uint32)#DWORD dwValue;// timer value in samples from head
				]

class TAG_CART(ctypes.Structure):
	_fields_ = [('Version', ctypes.c_char*4),#char Version[4];// version of the data structure
				('Title', ctypes.c_char*64),#char Title[64];// title of cart audio sequence
				('Artist', ctypes.c_char*64),#char Artist[64];// artist or creator name
				('CutID', ctypes.c_char*64),#char CutID[64];// cut number identification
				('ClientID', ctypes.c_char*64),#char ClientID[64];// client identification
				('Category', ctypes.c_char*64),#char Category[64];// category ID, PSA, NEWS, etc
				('Classification', ctypes.c_char*64),#char Classification[64];// classification or auxiliary key
				('OutCue', ctypes.c_char*64),#char OutCue[64];// out cue text
				('StartDate', ctypes.c_char*10),#char StartDate[10];// yyyy-mm-dd
				('StartTime', ctypes.c_char*8),#char StartTime[8];// hh:mm:ss
				('EndDate', ctypes.c_char*10),#char EndDate[10];// yyyy-mm-dd
				('EndTime', ctypes.c_char*8),#char EndTime[8];// hh:mm:ss
				('ProducerAppID', ctypes.c_char*64),#char ProducerAppID[64];// name of vendor or application
				('ProducerAppVersion', ctypes.c_char*64),#char ProducerAppVersion[64];// version of producer application
				('UserDef', ctypes.c_char*64),#char UserDef[64];// user defined text
				('dwLevelReference', ctypes.c_uint32),#DWORD dwLevelReference;// sample value for 0 dB reference
				('PostTimer', TAG_CART_TIMER*8),#TAG_CART_TIMER PostTimer[8];// 8 time markers after head
				('Reserved', ctypes.c_char*276),#char Reserved[276];
				('URL', ctypes.c_char*1024),#char URL[1024];// uniform resource locator
				('TagText', ctypes.c_char_p)#char TagText[];// free form text for scripts or tags
				]

# CoreAudio codec info structure
class TAG_CA_CODEC(ctypes.Structure):
	_fields_ = [('ftype', ctypes.c_uint32),#DWORD ftype;// file format
				('atype', ctypes.c_uint32),#DWORD atype;// audio format
				('name', ctypes.c_char_p)#const char *name;// description
				]

# BASS_ChannelGetLength/GetPosition/SetPosition modes
BASS_POS_BYTE = 0# byte position
BASS_POS_MUSIC_ORDER = 1# order.row position, MAKELONG(order,row)
BASS_POS_DECODE = 0x10000000# flag: get the decoding (not playing) position

# BASS_RecordSetInput flags
BASS_INPUT_OFF = 0x10000
BASS_INPUT_ON = 0x20000
BASS_INPUT_TYPE_MASK = (-16777216)
BASS_INPUT_TYPE_UNDEF = 0x00000000
BASS_INPUT_TYPE_DIGITAL = 0x01000000
BASS_INPUT_TYPE_LINE = 0x02000000
BASS_INPUT_TYPE_MIC = 0x03000000
BASS_INPUT_TYPE_SYNTH = 0x04000000
BASS_INPUT_TYPE_CD = 0x05000000
BASS_INPUT_TYPE_PHONE = 0x06000000
BASS_INPUT_TYPE_SPEAKER = 0x07000000
BASS_INPUT_TYPE_WAVE = 0x08000000
BASS_INPUT_TYPE_AUX = 0x09000000
BASS_INPUT_TYPE_ANALOG = 0x0a000000

# DX8 effect types, use with BASS_ChannelSetFX
(
 BASS_FX_DX8_CHORUS,
 BASS_FX_DX8_COMPRESSOR,
 BASS_FX_DX8_DISTORTION,
 BASS_FX_DX8_ECHO,
 BASS_FX_DX8_FLANGER,
 BASS_FX_DX8_GARGLE,
 BASS_FX_DX8_I3DL2REVERB,
 BASS_FX_DX8_PARAMEQ,
 BASS_FX_DX8_REVERB,
 ) = range(9)


class BASS_DX8_CHORUS(ctypes.Structure):
	_fields_ = [('fWetDryMix', ctypes.c_float),#float       fWetDryMix;
				('fDepth', ctypes.c_float),#float       fDepth;
				('fFeedback', ctypes.c_float),#float       fFeedback;
				('fFrequency', ctypes.c_float),#float       fFrequency;
				('lWaveform', ctypes.c_uint32),#DWORD       lWaveform;// 0=triangle, 1=sine
				('fDelay', ctypes.c_float),#float       fDelay;
				('lPhase', ctypes.c_uint32)#DWORD       lPhase;// BASS_DX8_PHASE_xxx
				]

class BASS_DX8_COMPRESSOR(ctypes.Structure):
	_fields_ = [('fGain', ctypes.c_float),#float   fGain;
				('fAttack', ctypes.c_float),#float   fAttack;
				('fRelease', ctypes.c_float),#float   fRelease;
				('fThreshold', ctypes.c_float),#float   fThreshold;
				('fRatio', ctypes.c_float),#float   fRatio;
				('fPredelay', ctypes.c_float)#float   fPredelay;
				]

class BASS_DX8_DISTORTION(ctypes.Structure):
	_fields_ = [('fGain', ctypes.c_float),#float   fGain;
				('fEdge', ctypes.c_float),#float   fEdge;
				('fPostEQCenterFrequency', ctypes.c_float),#float   fPostEQCenterFrequency;
				('fPostEQBandwidth', ctypes.c_float),#float   fPostEQBandwidth;
				('fPreLowpassCutoff', ctypes.c_float)#float   fPreLowpassCutoff;
				]

class BASS_DX8_ECHO(ctypes.Structure):
	_fields_ = [('fWetDryMix', ctypes.c_float),#float   fWetDryMix;
				('fFeedback', ctypes.c_float),#float   fFeedback;
				('fLeftDelay', ctypes.c_float),#float   fLeftDelay;
				('fRightDelay', ctypes.c_float),#float   fRightDelay;
				('lPanDelay', ctypes.c_int)#BOOL    lPanDelay;
				]

class BASS_DX8_FLANGER(ctypes.Structure):
	_fields_ = [('fWetDryMix', ctypes.c_float),#float       fWetDryMix;
				('fDepth', ctypes.c_float),#float       fDepth;
				('fFeedback', ctypes.c_float),#float       fFeedback;
				('fFrequency', ctypes.c_float),#float       fFrequency;
				('lWaveform', ctypes.c_uint32),#DWORD lWaveform;// 0=triangle, 1=sine
				('fDelay', ctypes.c_float),#float       fDelay;
				('lPhase', ctypes.c_uint32)#DWORD       lPhase;// BASS_DX8_PHASE_xxx
				]

class BASS_DX8_GARGLE(ctypes.Structure):
	_fields_ = [('dwRateHz', ctypes.c_uint32),#DWORD dwRateHz;// Rate of modulation in hz
				('dwWaveShape', ctypes.c_uint32)#DWORD dwWaveShape;// 0=triangle, 1=square
				]

class BASS_DX8_I3DL2REVERB(ctypes.Structure):
	_fields_ = [('lRoom', ctypes.c_int),#int    lRoom;// [-10000, 0]      default: -1000 mB
				('lRoomHF', ctypes.c_int),#int    lRoomHF;// [-10000, 0]      default: 0 mB
				('flRoomRolloffFactor', ctypes.c_float),#float  flRoomRolloffFactor;// [0.0, 10.0]      default: 0.0
				('flDecayTime', ctypes.c_float),#float  flDecayTime;// [0.1, 20.0]      default: 1.49s
				('flDecayHFRatio', ctypes.c_float),#float  flDecayHFRatio;// [0.1, 2.0]       default: 0.83
				('lReflections', ctypes.c_int),#int    lReflections;// [-10000, 1000]   default: -2602 mB
				('flReflectionsDelay', ctypes.c_float),#float  flReflectionsDelay;// [0.0, 0.3]       default: 0.007 s
				('lReverb', ctypes.c_int),#int    lReverb;// [-10000, 2000]   default: 200 mB
				('flReverbDelay', ctypes.c_float),#float  flReverbDelay;// [0.0, 0.1]       default: 0.011 s
				('flDiffusion', ctypes.c_float),#float  flDiffusion;// [0.0, 100.0]     default: 100.0 %
				('flDensity', ctypes.c_float),#float  flDensity;// [0.0, 100.0]     default: 100.0 %
				('flHFReference', ctypes.c_float)#float  flHFReference;// [20.0, 20000.0]  default: 5000.0 Hz
				]

class BASS_DX8_PARAMEQ(ctypes.Structure):
	_fields_ = [('fCenter', ctypes.c_float),#float   fCenter;
				('fBandwidth', ctypes.c_float),#float   fBandwidth;
				('fGain', ctypes.c_float)#float   fGain;
				]

class BASS_DX8_REVERB(ctypes.Structure):
	_fields_ = [('fInGain', ctypes.c_float),#float fInGain;// [-96.0,0.0]            default: 0.0 dB
				('fReverbMix', ctypes.c_float),#float fReverbMix;// [0,0.0]         default: 0.0 db
				('fReverbTime', ctypes.c_float),#float fReverbTime;// [0.001,100.0]     default: 1000.0 ms
				('fHighFreqRTRatio', ctypes.c_float)#float fHighFreqRTRatio;// [0.001,0] default: 0.001
				]

BASS_DX8_PHASE_NEG_180 = 0
BASS_DX8_PHASE_NEG_90 = 1
BASS_DX8_PHASE_ZERO = 2
BASS_DX8_PHASE_90 = 3
BASS_DX8_PHASE_180 = 4


def BASS_PluginLoad(file, flags):
    if file is not None and not isinstance(file, bytes):
        if system.get_platform()["os"] == "windows":
            file = ctypes.create_unicode_buffer(os.fspath(file))
            flags |= BASS_UNICODE
        else: file = os.fsencode(file)
    return _BASS_PluginLoad(file, flags)


#~ BASS_ChannelGetTags = func_type(ctypes.c_char_p, ctypes.c_uint32, ctypes.c_uint32)(('BASS_ChannelGetTags', bass_module))


if platform.system().lower() == 'windows':
	#BOOL BASSDEF(BASS_Init)(int device, DWORD freq, DWORD flags, HWND win, const GUID *dsguid); = func_type()(('', bass_module))
	#void *BASSDEF(BASS_GetDSoundObject)(DWORD object);
	BASS_GetDSoundObject = func_type(ctypes.c_void_p, ctypes.c_uint32)(('BASS_GetDSoundObject', bass_module))
	#BOOL BASSDEF(BASS_SetEAXParameters)(int env, float vol, float decay, float damp);
	BASS_SetEAXParameters = func_type(ctypes.c_int, ctypes.c_int, ctypes.c_float, ctypes.c_float, ctypes.c_float)(('BASS_SetEAXParameters', bass_module))
	#BOOL BASSDEF(BASS_GetEAXParameters)(DWORD *env, float *vol, float *decay, float *damp);
	BASS_GetEAXParameters = func_type(ctypes.c_int, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float))(('BASS_GetEAXParameters', bass_module))

def seconds_to_string(value):
	str_seconds = '00'
	str_minutes = '00'
	str_hours = '00'
	seconds = int(value)
	if seconds > 0:
		if seconds < 10:
			str_seconds = '0' + str(seconds)
		elif seconds > 60:
			str_seconds = str(seconds%60)
		else:
			str_seconds = str(seconds)
	minutes = int(value/60)
	if minutes > 0:
		if minutes < 10:
			str_minutes = '0' + str(minutes)
		elif minutes > 60:
			str_minutes = str(minutes%60)
		else:
			str_minutes = str(minutes)
	hours = int(minutes/60)
	if hours > 0:
		if hours < 10:
			str_hours = '0' + str(hours)
		elif hours < 60:
			str_hours = str(hours)
	return str_hours + ':' + str_minutes + ':' + str_seconds

def stream_length_as_hms(handle, mode = BASS_POS_BYTE):
	return seconds_to_string(BASS_ChannelBytes2Seconds(handle, BASS_ChannelGetLength(handle, mode)))

def get_tags(handle, tags = BASS_TAG_OGG):
	result = []
	addr = BASS_ChannelGetTags(handle, tags)
	res = ''
	while isinstance(res, str):
		res = ctypes.string_at(addr)
		#~ res = ctypes.wstring_at(addr)
		addr += len(res) + 1
		if res:
			if 32 < ord(res[0]) < 256:
				result.append(res)
			else:
				res = None
	return result

def get_tags_as_dict(handle, tags = BASS_TAG_OGG):
	result_as_dict = {}
	addr = BASS_ChannelGetTags(handle, tags)
	str_tag = ''
	while isinstance(str_tag, str):
		str_tag = ctypes.string_at(addr)
		addr += len(str_tag) + 1
		if str_tag:
			if 32 < ord(str_tag[0]) < 256:
				key, value = str_tag.split('=')
				result_as_dict[key] = value
			else:
				str_tag = None
	return result_as_dict


# Core signatures synchronized with the bundled bass.h (2025).
def _bind_core(name, restype, *argtypes):
    try:
        return func_type(restype, *argtypes)((name, bass_module))
    except AttributeError:
        def unavailable(*args):
            raise NotImplementedError(f"{name} is unavailable in this BASS binary; update the native library")
        unavailable.__name__ = name
        return unavailable

BASS_SetConfig = _bind_core('BASS_SetConfig', ctypes.c_int, ctypes.c_uint32, ctypes.c_uint32)
BASS_GetConfig = _bind_core('BASS_GetConfig', ctypes.c_uint32, ctypes.c_uint32)
BASS_SetConfigPtr = _bind_core('BASS_SetConfigPtr', ctypes.c_int, ctypes.c_uint32, ctypes.c_void_p)
BASS_GetConfigPtr = _bind_core('BASS_GetConfigPtr', ctypes.c_void_p, ctypes.c_uint32)
BASS_GetVersion = _bind_core('BASS_GetVersion', ctypes.c_uint32)
BASS_ErrorGetCode = _bind_core('BASS_ErrorGetCode', ctypes.c_int)
BASS_GetDeviceInfo = _bind_core('BASS_GetDeviceInfo', ctypes.c_int, ctypes.c_uint32, ctypes.POINTER(BASS_DEVICEINFO))
BASS_Init = _bind_core('BASS_Init', ctypes.c_int, ctypes.c_int, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p)
BASS_Free = _bind_core('BASS_Free', ctypes.c_int)
BASS_SetDevice = _bind_core('BASS_SetDevice', ctypes.c_int, ctypes.c_uint32)
BASS_GetDevice = _bind_core('BASS_GetDevice', ctypes.c_uint32)
BASS_GetInfo = _bind_core('BASS_GetInfo', ctypes.c_int, ctypes.POINTER(BASS_INFO))
BASS_Start = _bind_core('BASS_Start', ctypes.c_int)
BASS_Stop = _bind_core('BASS_Stop', ctypes.c_int)
BASS_Pause = _bind_core('BASS_Pause', ctypes.c_int)
BASS_IsStarted = _bind_core('BASS_IsStarted', ctypes.c_uint32)
BASS_Update = _bind_core('BASS_Update', ctypes.c_int, ctypes.c_uint32)
BASS_GetCPU = _bind_core('BASS_GetCPU', ctypes.c_float)
BASS_SetVolume = _bind_core('BASS_SetVolume', ctypes.c_int, ctypes.c_float)
BASS_GetVolume = _bind_core('BASS_GetVolume', ctypes.c_float)
BASS_Set3DFactors = _bind_core('BASS_Set3DFactors', ctypes.c_int, ctypes.c_float, ctypes.c_float, ctypes.c_float)
BASS_Get3DFactors = _bind_core('BASS_Get3DFactors', ctypes.c_int, ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float))
BASS_Set3DPosition = _bind_core('BASS_Set3DPosition', ctypes.c_int, ctypes.POINTER(BASS_3DVECTOR), ctypes.POINTER(BASS_3DVECTOR), ctypes.POINTER(BASS_3DVECTOR), ctypes.POINTER(BASS_3DVECTOR))
BASS_Get3DPosition = _bind_core('BASS_Get3DPosition', ctypes.c_int, ctypes.POINTER(BASS_3DVECTOR), ctypes.POINTER(BASS_3DVECTOR), ctypes.POINTER(BASS_3DVECTOR), ctypes.POINTER(BASS_3DVECTOR))
BASS_Apply3D = _bind_core('BASS_Apply3D', None)
_BASS_PluginLoad = _bind_core('BASS_PluginLoad', HPLUGIN, ctypes.c_void_p, ctypes.c_uint32)
BASS_PluginFree = _bind_core('BASS_PluginFree', ctypes.c_int, HPLUGIN)
BASS_PluginEnable = _bind_core('BASS_PluginEnable', ctypes.c_int, HPLUGIN, ctypes.c_int)
BASS_PluginGetInfo = _bind_core('BASS_PluginGetInfo', ctypes.POINTER(BASS_PLUGININFO), HPLUGIN)
BASS_SampleLoad = _bind_core('BASS_SampleLoad', HSAMPLE, ctypes.c_uint32, ctypes.c_void_p, QWORD, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32)
BASS_SampleCreate = _bind_core('BASS_SampleCreate', HSAMPLE, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32)
BASS_SampleFree = _bind_core('BASS_SampleFree', ctypes.c_int, HSAMPLE)
BASS_SampleSetData = _bind_core('BASS_SampleSetData', ctypes.c_int, HSAMPLE, ctypes.c_void_p)
BASS_SampleGetData = _bind_core('BASS_SampleGetData', ctypes.c_int, HSAMPLE, ctypes.c_void_p)
BASS_SampleGetInfo = _bind_core('BASS_SampleGetInfo', ctypes.c_int, HSAMPLE, ctypes.POINTER(BASS_SAMPLE))
BASS_SampleSetInfo = _bind_core('BASS_SampleSetInfo', ctypes.c_int, HSAMPLE, ctypes.POINTER(BASS_SAMPLE))
BASS_SampleGetChannel = _bind_core('BASS_SampleGetChannel', ctypes.c_uint32, HSAMPLE, ctypes.c_uint32)
BASS_SampleGetChannels = _bind_core('BASS_SampleGetChannels', ctypes.c_uint32, HSAMPLE, ctypes.POINTER(HCHANNEL))
BASS_SampleStop = _bind_core('BASS_SampleStop', ctypes.c_int, HSAMPLE)
BASS_StreamCreate = _bind_core('BASS_StreamCreate', HSTREAM, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, STREAMPROC, ctypes.c_void_p)
BASS_StreamCreateFile = _bind_core('BASS_StreamCreateFile', HSTREAM, ctypes.c_uint32, ctypes.c_void_p, QWORD, QWORD, ctypes.c_uint32)
BASS_StreamCreateURL = _bind_core('BASS_StreamCreateURL', HSTREAM, ctypes.c_char_p, ctypes.c_uint32, ctypes.c_uint32, DOWNLOADPROC, ctypes.c_void_p)
BASS_StreamCreateFileUser = _bind_core('BASS_StreamCreateFileUser', HSTREAM, ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(BASS_FILEPROCS), ctypes.c_void_p)
BASS_StreamCancel = _bind_core('BASS_StreamCancel', ctypes.c_int, ctypes.c_void_p)
BASS_StreamFree = _bind_core('BASS_StreamFree', ctypes.c_int, HSTREAM)
BASS_StreamGetFilePosition = _bind_core('BASS_StreamGetFilePosition', QWORD, HSTREAM, ctypes.c_uint32)
BASS_StreamPutData = _bind_core('BASS_StreamPutData', ctypes.c_uint32, HSTREAM, ctypes.c_void_p, ctypes.c_uint32)
BASS_StreamPutFileData = _bind_core('BASS_StreamPutFileData', ctypes.c_uint32, HSTREAM, ctypes.c_void_p, ctypes.c_uint32)
BASS_MusicLoad = _bind_core('BASS_MusicLoad', HMUSIC, ctypes.c_uint32, ctypes.c_void_p, QWORD, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32)
BASS_MusicFree = _bind_core('BASS_MusicFree', ctypes.c_int, HMUSIC)
BASS_RecordGetDeviceInfo = _bind_core('BASS_RecordGetDeviceInfo', ctypes.c_int, ctypes.c_uint32, ctypes.POINTER(BASS_DEVICEINFO))
BASS_RecordInit = _bind_core('BASS_RecordInit', ctypes.c_int, ctypes.c_int)
BASS_RecordFree = _bind_core('BASS_RecordFree', ctypes.c_int)
BASS_RecordSetDevice = _bind_core('BASS_RecordSetDevice', ctypes.c_int, ctypes.c_uint32)
BASS_RecordGetDevice = _bind_core('BASS_RecordGetDevice', ctypes.c_uint32)
BASS_RecordGetInfo = _bind_core('BASS_RecordGetInfo', ctypes.c_int, ctypes.POINTER(BASS_RECORDINFO))
BASS_RecordGetInputName = _bind_core('BASS_RecordGetInputName', ctypes.c_char_p, ctypes.c_int)
BASS_RecordSetInput = _bind_core('BASS_RecordSetInput', ctypes.c_int, ctypes.c_int, ctypes.c_uint32, ctypes.c_float)
BASS_RecordGetInput = _bind_core('BASS_RecordGetInput', ctypes.c_uint32, ctypes.c_int, ctypes.POINTER(ctypes.c_float))
BASS_RecordStart = _bind_core('BASS_RecordStart', HRECORD, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, RECORDPROC, ctypes.c_void_p)
BASS_ChannelBytes2Seconds = _bind_core('BASS_ChannelBytes2Seconds', ctypes.c_double, ctypes.c_uint32, QWORD)
BASS_ChannelSeconds2Bytes = _bind_core('BASS_ChannelSeconds2Bytes', QWORD, ctypes.c_uint32, ctypes.c_double)
BASS_ChannelGetDevice = _bind_core('BASS_ChannelGetDevice', ctypes.c_uint32, ctypes.c_uint32)
BASS_ChannelSetDevice = _bind_core('BASS_ChannelSetDevice', ctypes.c_int, ctypes.c_uint32, ctypes.c_uint32)
BASS_ChannelIsActive = _bind_core('BASS_ChannelIsActive', ctypes.c_uint32, ctypes.c_uint32)
BASS_ChannelGetInfo = _bind_core('BASS_ChannelGetInfo', ctypes.c_int, ctypes.c_uint32, ctypes.POINTER(BASS_CHANNELINFO))
BASS_ChannelGetTags = _bind_core('BASS_ChannelGetTags', ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32)
BASS_ChannelFlags = _bind_core('BASS_ChannelFlags', ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32)
BASS_ChannelLock = _bind_core('BASS_ChannelLock', ctypes.c_int, ctypes.c_uint32, ctypes.c_int)
BASS_ChannelRef = _bind_core('BASS_ChannelRef', ctypes.c_int, ctypes.c_uint32, ctypes.c_int)
BASS_ChannelFree = _bind_core('BASS_ChannelFree', ctypes.c_int, ctypes.c_uint32)
BASS_ChannelPlay = _bind_core('BASS_ChannelPlay', ctypes.c_int, ctypes.c_uint32, ctypes.c_int)
BASS_ChannelStart = _bind_core('BASS_ChannelStart', ctypes.c_int, ctypes.c_uint32)
BASS_ChannelStop = _bind_core('BASS_ChannelStop', ctypes.c_int, ctypes.c_uint32)
BASS_ChannelPause = _bind_core('BASS_ChannelPause', ctypes.c_int, ctypes.c_uint32)
BASS_ChannelUpdate = _bind_core('BASS_ChannelUpdate', ctypes.c_int, ctypes.c_uint32, ctypes.c_uint32)
BASS_ChannelSetAttribute = _bind_core('BASS_ChannelSetAttribute', ctypes.c_int, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_float)
BASS_ChannelGetAttribute = _bind_core('BASS_ChannelGetAttribute', ctypes.c_int, ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(ctypes.c_float))
BASS_ChannelSlideAttribute = _bind_core('BASS_ChannelSlideAttribute', ctypes.c_int, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_float, ctypes.c_uint32)
BASS_ChannelIsSliding = _bind_core('BASS_ChannelIsSliding', ctypes.c_int, ctypes.c_uint32, ctypes.c_uint32)
BASS_ChannelSetAttributeEx = _bind_core('BASS_ChannelSetAttributeEx', ctypes.c_int, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32)
BASS_ChannelGetAttributeEx = _bind_core('BASS_ChannelGetAttributeEx', ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32)
BASS_ChannelSet3DAttributes = _bind_core('BASS_ChannelSet3DAttributes', ctypes.c_int, ctypes.c_uint32, ctypes.c_int, ctypes.c_float, ctypes.c_float, ctypes.c_int, ctypes.c_int, ctypes.c_float)
BASS_ChannelGet3DAttributes = _bind_core('BASS_ChannelGet3DAttributes', ctypes.c_int, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_float))
BASS_ChannelSet3DPosition = _bind_core('BASS_ChannelSet3DPosition', ctypes.c_int, ctypes.c_uint32, ctypes.POINTER(BASS_3DVECTOR), ctypes.POINTER(BASS_3DVECTOR), ctypes.POINTER(BASS_3DVECTOR))
BASS_ChannelGet3DPosition = _bind_core('BASS_ChannelGet3DPosition', ctypes.c_int, ctypes.c_uint32, ctypes.POINTER(BASS_3DVECTOR), ctypes.POINTER(BASS_3DVECTOR), ctypes.POINTER(BASS_3DVECTOR))
BASS_ChannelGetLength = _bind_core('BASS_ChannelGetLength', QWORD, ctypes.c_uint32, ctypes.c_uint32)
BASS_ChannelSetPosition = _bind_core('BASS_ChannelSetPosition', ctypes.c_int, ctypes.c_uint32, QWORD, ctypes.c_uint32)
BASS_ChannelGetPosition = _bind_core('BASS_ChannelGetPosition', QWORD, ctypes.c_uint32, ctypes.c_uint32)
BASS_ChannelGetLevel = _bind_core('BASS_ChannelGetLevel', ctypes.c_uint32, ctypes.c_uint32)
BASS_ChannelGetLevelEx = _bind_core('BASS_ChannelGetLevelEx', ctypes.c_int, ctypes.c_uint32, ctypes.POINTER(ctypes.c_float), ctypes.c_float, ctypes.c_uint32)
BASS_ChannelGetData = _bind_core('BASS_ChannelGetData', ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32)
BASS_ChannelSetSync = _bind_core('BASS_ChannelSetSync', HSYNC, ctypes.c_uint32, ctypes.c_uint32, QWORD, SYNCPROC, ctypes.c_void_p)
BASS_ChannelRemoveSync = _bind_core('BASS_ChannelRemoveSync', ctypes.c_int, ctypes.c_uint32, HSYNC)
BASS_ChannelSetLink = _bind_core('BASS_ChannelSetLink', ctypes.c_int, ctypes.c_uint32, ctypes.c_uint32)
BASS_ChannelRemoveLink = _bind_core('BASS_ChannelRemoveLink', ctypes.c_int, ctypes.c_uint32, ctypes.c_uint32)
BASS_ChannelSetDSP = _bind_core('BASS_ChannelSetDSP', HDSP, ctypes.c_uint32, DSPPROC, ctypes.c_void_p, ctypes.c_int)
BASS_ChannelSetDSPEx = _bind_core('BASS_ChannelSetDSPEx', HDSP, ctypes.c_uint32, DSPPROC, ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32)
BASS_ChannelRemoveDSP = _bind_core('BASS_ChannelRemoveDSP', ctypes.c_int, ctypes.c_uint32, HDSP)
BASS_ChannelSetFX = _bind_core('BASS_ChannelSetFX', HFX, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_int)
BASS_ChannelRemoveFX = _bind_core('BASS_ChannelRemoveFX', ctypes.c_int, ctypes.c_uint32, HFX)
BASS_FXSetParameters = _bind_core('BASS_FXSetParameters', ctypes.c_int, HFX, ctypes.c_void_p)
BASS_FXGetParameters = _bind_core('BASS_FXGetParameters', ctypes.c_int, HFX, ctypes.c_void_p)
BASS_FXSetPriority = _bind_core('BASS_FXSetPriority', ctypes.c_int, ctypes.c_uint32, ctypes.c_int)
BASS_FXSetBypass = _bind_core('BASS_FXSetBypass', ctypes.c_int, ctypes.c_uint32, ctypes.c_int)
BASS_FXReset = _bind_core('BASS_FXReset', ctypes.c_int, ctypes.c_uint32)
BASS_FXFree = _bind_core('BASS_FXFree', ctypes.c_int, ctypes.c_uint32)

# Constants from the bundled bass.h.
BASS_OK = 0
BASS_ERROR_MEM = 1
BASS_ERROR_FILEOPEN = 2
BASS_ERROR_DRIVER = 3
BASS_ERROR_BUFLOST = 4
BASS_ERROR_HANDLE = 5
BASS_ERROR_FORMAT = 6
BASS_ERROR_POSITION = 7
BASS_ERROR_INIT = 8
BASS_ERROR_START = 9
BASS_ERROR_SSL = 10
BASS_ERROR_REINIT = 11
BASS_ERROR_TRACK = 13
BASS_ERROR_ALREADY = 14
BASS_ERROR_NOTAUDIO = 17
BASS_ERROR_NOCHAN = 18
BASS_ERROR_ILLTYPE = 19
BASS_ERROR_ILLPARAM = 20
BASS_ERROR_NO3D = 21
BASS_ERROR_NOEAX = 22
BASS_ERROR_DEVICE = 23
BASS_ERROR_NOPLAY = 24
BASS_ERROR_FREQ = 25
BASS_ERROR_NOTFILE = 27
BASS_ERROR_NOHW = 29
BASS_ERROR_EMPTY = 31
BASS_ERROR_NONET = 32
BASS_ERROR_CREATE = 33
BASS_ERROR_NOFX = 34
BASS_ERROR_NOTAVAIL = 37
BASS_ERROR_DECODE = 38
BASS_ERROR_DX = 39
BASS_ERROR_TIMEOUT = 40
BASS_ERROR_FILEFORM = 41
BASS_ERROR_SPEAKER = 42
BASS_ERROR_VERSION = 43
BASS_ERROR_CODEC = 44
BASS_ERROR_ENDED = 45
BASS_ERROR_BUSY = 46
BASS_ERROR_UNSTREAMABLE = 47
BASS_ERROR_PROTOCOL = 48
BASS_ERROR_DENIED = 49
BASS_ERROR_FREEING = 50
BASS_ERROR_CANCEL = 51
BASS_ERROR_UNKNOWN = -1
BASS_CONFIG_BUFFER = 0
BASS_CONFIG_UPDATEPERIOD = 1
BASS_CONFIG_GVOL_SAMPLE = 4
BASS_CONFIG_GVOL_STREAM = 5
BASS_CONFIG_GVOL_MUSIC = 6
BASS_CONFIG_CURVE_VOL = 7
BASS_CONFIG_CURVE_PAN = 8
BASS_CONFIG_FLOATDSP = 9
BASS_CONFIG_3DALGORITHM = 10
BASS_CONFIG_NET_TIMEOUT = 11
BASS_CONFIG_NET_BUFFER = 12
BASS_CONFIG_PAUSE_NOPLAY = 13
BASS_CONFIG_NET_PREBUF = 15
BASS_CONFIG_NET_PASSIVE = 18
BASS_CONFIG_REC_BUFFER = 19
BASS_CONFIG_NET_PLAYLIST = 21
BASS_CONFIG_MUSIC_VIRTUAL = 22
BASS_CONFIG_VERIFY = 23
BASS_CONFIG_UPDATETHREADS = 24
BASS_CONFIG_DEV_BUFFER = 27
BASS_CONFIG_REC_LOOPBACK = 28
BASS_CONFIG_IOS_SESSION = 34
BASS_CONFIG_IOS_MIXAUDIO = 34
BASS_CONFIG_DEV_DEFAULT = 36
BASS_CONFIG_NET_READTIMEOUT = 37
BASS_CONFIG_VISTA_SPEAKERS = 38
BASS_CONFIG_IOS_SPEAKER = 39
BASS_CONFIG_MF_DISABLE = 40
BASS_CONFIG_HANDLES = 41
BASS_CONFIG_UNICODE = 42
BASS_CONFIG_SRC = 43
BASS_CONFIG_SRC_SAMPLE = 44
BASS_CONFIG_ASYNCFILE_BUFFER = 45
BASS_CONFIG_OGG_PRESCAN = 47
BASS_CONFIG_VIDEO = 48
BASS_CONFIG_MF_VIDEO = 48
BASS_CONFIG_AIRPLAY = 49
BASS_CONFIG_DEV_NONSTOP = 50
BASS_CONFIG_IOS_NOCATEGORY = 51
BASS_CONFIG_VERIFY_NET = 52
BASS_CONFIG_DEV_PERIOD = 53
BASS_CONFIG_FLOAT = 54
BASS_CONFIG_NET_SEEK = 56
BASS_CONFIG_AM_DISABLE = 58
BASS_CONFIG_NET_PLAYLIST_DEPTH = 59
BASS_CONFIG_NET_PREBUF_WAIT = 60
BASS_CONFIG_ANDROID_SESSIONID = 62
BASS_CONFIG_WASAPI_PERSIST = 65
BASS_CONFIG_REC_WASAPI = 66
BASS_CONFIG_ANDROID_AAUDIO = 67
BASS_CONFIG_SAMPLE_ONEHANDLE = 69
BASS_CONFIG_NET_META = 71
BASS_CONFIG_NET_RESTRATE = 72
BASS_CONFIG_REC_DEFAULT = 73
BASS_CONFIG_NORAMP = 74
BASS_CONFIG_NOSOUND_MAXDELAY = 76
BASS_CONFIG_STACKALLOC = 79
BASS_CONFIG_DOWNMIX = 80
BASS_CONFIG_NET_AGENT = 16
BASS_CONFIG_NET_PROXY = 17
BASS_CONFIG_DEV_NOTIFY = 33
BASS_CONFIG_IOS_NOTIFY = 46
BASS_CONFIG_ANDROID_JAVAVM = 63
BASS_CONFIG_LIBSSL = 64
BASS_CONFIG_FILENAME = 75
BASS_CONFIG_FILEOPENPROCS = 77
BASS_CONFIG_THREAD = 1073741824
BASS_IOS_SESSION_MIX = 1
BASS_IOS_SESSION_DUCK = 2
BASS_IOS_SESSION_AMBIENT = 4
BASS_IOS_SESSION_SPEAKER = 8
BASS_IOS_SESSION_DISABLE = 16
BASS_IOS_SESSION_DEACTIVATE = 32
BASS_IOS_SESSION_AIRPLAY = 64
BASS_IOS_SESSION_BTHFP = 128
BASS_IOS_SESSION_BTA2DP = 256
BASS_DEVICE_8BITS = 1
BASS_DEVICE_MONO = 2
BASS_DEVICE_3D = 4
BASS_DEVICE_16BITS = 8
BASS_DEVICE_REINIT = 128
BASS_DEVICE_LATENCY = 256
BASS_DEVICE_CPSPEAKERS = 1024
BASS_DEVICE_SPEAKERS = 2048
BASS_DEVICE_NOSPEAKER = 4096
BASS_DEVICE_DMIX = 8192
BASS_DEVICE_FREQ = 16384
BASS_DEVICE_STEREO = 32768
BASS_DEVICE_HOG = 65536
BASS_DEVICE_AUDIOTRACK = 131072
BASS_DEVICE_DSOUND = 262144
BASS_DEVICE_SOFTWARE = 524288
BASS_DEVICE_OPENSLES = 1048576
BASS_DEVICE_APPLEVOICE = 2097152
BASS_OBJECT_DS = 1
BASS_OBJECT_DS3DL = 2
BASS_DEVICE_ENABLED = 1
BASS_DEVICE_DEFAULT = 2
BASS_DEVICE_INIT = 4
BASS_DEVICE_LOOPBACK = 8
BASS_DEVICE_DEFAULTCOM = 128
BASS_DEVICE_TYPE_MASK = 4278190080
BASS_DEVICE_TYPE_NETWORK = 16777216
BASS_DEVICE_TYPE_SPEAKERS = 33554432
BASS_DEVICE_TYPE_LINE = 50331648
BASS_DEVICE_TYPE_HEADPHONES = 67108864
BASS_DEVICE_TYPE_MICROPHONE = 83886080
BASS_DEVICE_TYPE_HEADSET = 100663296
BASS_DEVICE_TYPE_HANDSET = 117440512
BASS_DEVICE_TYPE_DIGITAL = 134217728
BASS_DEVICE_TYPE_SPDIF = 150994944
BASS_DEVICE_TYPE_HDMI = 167772160
BASS_DEVICE_TYPE_DISPLAYPORT = 1073741824
BASS_DEVICES_AIRPLAY = 16777216
BASS_FILE_NAME = 0
BASS_FILE_MEM = 1
BASS_FILE_MEMCOPY = 3
BASS_FILE_HANDLE = 4
BASS_SAMPLE_8BITS = 1
BASS_SAMPLE_MONO = 2
BASS_SAMPLE_LOOP = 4
BASS_SAMPLE_3D = 8
BASS_SAMPLE_SOFTWARE = 16
BASS_SAMPLE_MUTEMAX = 32
BASS_SAMPLE_NOREORDER = 64
BASS_SAMPLE_FX = 128
BASS_SAMPLE_FLOAT = 256
BASS_SAMPLE_OVER_VOL = 65536
BASS_SAMPLE_OVER_POS = 131072
BASS_SAMPLE_OVER_DIST = 196608
BASS_STREAM_PRESCAN = 131072
BASS_STREAM_AUTOFREE = 262144
BASS_STREAM_RESTRATE = 524288
BASS_STREAM_BLOCK = 1048576
BASS_STREAM_DECODE = 2097152
BASS_STREAM_STATUS = 8388608
BASS_MP3_IGNOREDELAY = 512
BASS_MP3_SETPOS = 131072
BASS_MUSIC_FLOAT = 256
BASS_MUSIC_MONO = 2
BASS_MUSIC_LOOP = 4
BASS_MUSIC_3D = 8
BASS_MUSIC_FX = 128
BASS_MUSIC_AUTOFREE = 262144
BASS_MUSIC_DECODE = 2097152
BASS_MUSIC_PRESCAN = 131072
BASS_MUSIC_CALCLEN = 131072
BASS_MUSIC_RAMP = 512
BASS_MUSIC_RAMPS = 1024
BASS_MUSIC_SURROUND = 2048
BASS_MUSIC_SURROUND2 = 4096
BASS_MUSIC_FT2PAN = 8192
BASS_MUSIC_FT2MOD = 8192
BASS_MUSIC_PT1MOD = 16384
BASS_MUSIC_NONINTER = 65536
BASS_MUSIC_SINCINTER = 8388608
BASS_MUSIC_POSRESET = 32768
BASS_MUSIC_POSRESETEX = 4194304
BASS_MUSIC_STOPBACK = 524288
BASS_MUSIC_NOSAMPLE = 1048576
BASS_SPEAKER_FRONT = 16777216
BASS_SPEAKER_REAR = 33554432
BASS_SPEAKER_CENLFE = 50331648
BASS_SPEAKER_SIDE = 67108864
BASS_SPEAKER_LEFT = 268435456
BASS_SPEAKER_RIGHT = 536870912
BASS_SPEAKER_FRONTLEFT = 285212672
BASS_SPEAKER_FRONTRIGHT = 553648128
BASS_SPEAKER_REARLEFT = 301989888
BASS_SPEAKER_REARRIGHT = 570425344
BASS_SPEAKER_CENTER = 318767104
BASS_SPEAKER_LFE = 587202560
BASS_SPEAKER_SIDELEFT = 335544320
BASS_SPEAKER_SIDERIGHT = 603979776
BASS_SPEAKER_REAR2 = 67108864
BASS_SPEAKER_REAR2LEFT = 335544320
BASS_SPEAKER_REAR2RIGHT = 603979776
BASS_ASYNCFILE = 1073741824
BASS_UNICODE = 2147483648
BASS_RECORD_OPENSLES = 4096
BASS_RECORD_PAUSE = 32768
BASS_ORIGRES_FLOAT = 65536
BASS_CTYPE_SAMPLE = 1
BASS_CTYPE_RECORD = 2
BASS_CTYPE_STREAM = 65536
BASS_CTYPE_STREAM_VORBIS = 65538
BASS_CTYPE_STREAM_OGG = 65538
BASS_CTYPE_STREAM_MP1 = 65539
BASS_CTYPE_STREAM_MP2 = 65540
BASS_CTYPE_STREAM_MP3 = 65541
BASS_CTYPE_STREAM_AIFF = 65542
BASS_CTYPE_STREAM_CA = 65543
BASS_CTYPE_STREAM_MF = 65544
BASS_CTYPE_STREAM_AM = 65545
BASS_CTYPE_STREAM_SAMPLE = 65546
BASS_CTYPE_STREAM_DUMMY = 98304
BASS_CTYPE_STREAM_DEVICE = 98305
BASS_CTYPE_STREAM_WAV = 262144
BASS_CTYPE_STREAM_WAV_PCM = 327681
BASS_CTYPE_STREAM_WAV_FLOAT = 327683
BASS_CTYPE_MUSIC_MOD = 131072
BASS_CTYPE_MUSIC_MTM = 131073
BASS_CTYPE_MUSIC_S3M = 131074
BASS_CTYPE_MUSIC_XM = 131075
BASS_CTYPE_MUSIC_IT = 131076
BASS_CTYPE_MUSIC_MO3 = 256
BASS_PLUGIN_PROC = 1
BASS_3DMODE_NORMAL = 0
BASS_3DMODE_RELATIVE = 1
BASS_3DMODE_OFF = 2
BASS_3DALG_DEFAULT = 0
BASS_3DALG_OFF = 1
BASS_SAMCHAN_NEW = 1
BASS_SAMCHAN_STREAM = 2
BASS_STREAMPROC_AGAIN = 1073741824
BASS_STREAMPROC_END = 2147483648
BASS_FILEDATA_END = 0
BASS_FILEPOS_CURRENT = 0
BASS_FILEPOS_DECODE = 0
BASS_FILEPOS_DOWNLOAD = 1
BASS_FILEPOS_END = 2
BASS_FILEPOS_START = 3
BASS_FILEPOS_CONNECTED = 4
BASS_FILEPOS_BUFFER = 5
BASS_FILEPOS_SOCKET = 6
BASS_FILEPOS_ASYNCBUF = 7
BASS_FILEPOS_SIZE = 8
BASS_FILEPOS_BUFFERING = 9
BASS_FILEPOS_AVAILABLE = 10
BASS_FILEPOS_ASYNCSIZE = 12
BASS_SYNC_POS = 0
BASS_SYNC_END = 2
BASS_SYNC_META = 4
BASS_SYNC_SLIDE = 5
BASS_SYNC_STALL = 6
BASS_SYNC_DOWNLOAD = 7
BASS_SYNC_FREE = 8
BASS_SYNC_SETPOS = 11
BASS_SYNC_MUSICPOS = 10
BASS_SYNC_MUSICINST = 1
BASS_SYNC_MUSICFX = 3
BASS_SYNC_OGG_CHANGE = 12
BASS_SYNC_ATTRIB = 13
BASS_SYNC_DEV_FAIL = 14
BASS_SYNC_DEV_FORMAT = 15
BASS_SYNC_POS_RAW = 16
BASS_SYNC_THREAD = 536870912
BASS_SYNC_MIXTIME = 1073741824
BASS_SYNC_ONETIME = 2147483648
BASS_ACTIVE_STOPPED = 0
BASS_ACTIVE_PLAYING = 1
BASS_ACTIVE_STALLED = 2
BASS_ACTIVE_PAUSED = 3
BASS_ACTIVE_PAUSED_DEVICE = 4
BASS_ATTRIB_FREQ = 1
BASS_ATTRIB_VOL = 2
BASS_ATTRIB_PAN = 3
BASS_ATTRIB_EAXMIX = 4
BASS_ATTRIB_NOBUFFER = 5
BASS_ATTRIB_VBR = 6
BASS_ATTRIB_CPU = 7
BASS_ATTRIB_SRC = 8
BASS_ATTRIB_NET_RESUME = 9
BASS_ATTRIB_SCANINFO = 10
BASS_ATTRIB_NORAMP = 11
BASS_ATTRIB_BITRATE = 12
BASS_ATTRIB_BUFFER = 13
BASS_ATTRIB_GRANULE = 14
BASS_ATTRIB_USER = 15
BASS_ATTRIB_TAIL = 16
BASS_ATTRIB_PUSH_LIMIT = 17
BASS_ATTRIB_DOWNLOADPROC = 18
BASS_ATTRIB_VOLDSP = 19
BASS_ATTRIB_VOLDSP_PRIORITY = 20
BASS_ATTRIB_DOWNMIX = 21
BASS_ATTRIB_MUSIC_AMPLIFY = 256
BASS_ATTRIB_MUSIC_PANSEP = 257
BASS_ATTRIB_MUSIC_PSCALER = 258
BASS_ATTRIB_MUSIC_BPM = 259
BASS_ATTRIB_MUSIC_SPEED = 260
BASS_ATTRIB_MUSIC_VOL_GLOBAL = 261
BASS_ATTRIB_MUSIC_ACTIVE = 262
BASS_ATTRIB_MUSIC_VOL_CHAN = 512
BASS_ATTRIB_MUSIC_VOL_INST = 768
BASS_ATTRIBTYPE_FLOAT = -1
BASS_ATTRIBTYPE_INT = -2
BASS_SLIDE_LOG = 16777216
BASS_DATA_AVAILABLE = 0
BASS_DATA_NOREMOVE = 268435456
BASS_DATA_FIXED = 536870912
BASS_DATA_FLOAT = 1073741824
BASS_DATA_FFT256 = 2147483648
BASS_DATA_FFT512 = 2147483649
BASS_DATA_FFT1024 = 2147483650
BASS_DATA_FFT2048 = 2147483651
BASS_DATA_FFT4096 = 2147483652
BASS_DATA_FFT8192 = 2147483653
BASS_DATA_FFT16384 = 2147483654
BASS_DATA_FFT32768 = 2147483655
BASS_DATA_FFT_INDIVIDUAL = 16
BASS_DATA_FFT_NOWINDOW = 32
BASS_DATA_FFT_REMOVEDC = 64
BASS_DATA_FFT_COMPLEX = 128
BASS_DATA_FFT_NYQUIST = 256
BASS_LEVEL_MONO = 1
BASS_LEVEL_STEREO = 2
BASS_LEVEL_RMS = 4
BASS_LEVEL_VOLPAN = 8
BASS_LEVEL_NOREMOVE = 16
BASS_TAG_ID3 = 0
BASS_TAG_ID3V2 = 1
BASS_TAG_OGG = 2
BASS_TAG_HTTP = 3
BASS_TAG_ICY = 4
BASS_TAG_META = 5
BASS_TAG_APE = 6
BASS_TAG_MP4 = 7
BASS_TAG_WMA = 8
BASS_TAG_VENDOR = 9
BASS_TAG_LYRICS3 = 10
BASS_TAG_CA_CODEC = 11
BASS_TAG_MF = 13
BASS_TAG_WAVEFORMAT = 14
BASS_TAG_AM_NAME = 16
BASS_TAG_ID3V2_2 = 17
BASS_TAG_AM_MIME = 18
BASS_TAG_LOCATION = 19
BASS_TAG_ID3V2_BINARY = 20
BASS_TAG_ID3V2_2_BINARY = 21
BASS_TAG_RIFF_INFO = 256
BASS_TAG_RIFF_BEXT = 257
BASS_TAG_RIFF_CART = 258
BASS_TAG_RIFF_DISP = 259
BASS_TAG_RIFF_CUE = 260
BASS_TAG_RIFF_SMPL = 261
BASS_TAG_APE_BINARY = 4096
BASS_TAG_MP4_COVERART = 5120
BASS_TAG_MUSIC_NAME = 65536
BASS_TAG_MUSIC_MESSAGE = 65537
BASS_TAG_MUSIC_ORDERS = 65538
BASS_TAG_MUSIC_AUTH = 65539
BASS_TAG_MUSIC_INST = 65792
BASS_TAG_MUSIC_CHAN = 66048
BASS_TAG_MUSIC_SAMPLE = 66304
BASS_TAG_INCREF = 536870912
BASS_POS_BYTE = 0
BASS_POS_MUSIC_ORDER = 1
BASS_POS_OGG = 3
BASS_POS_TRACK = 4
BASS_POS_RAW = 6
BASS_POS_END = 16
BASS_POS_LOOP = 17
BASS_POS_DSP = 8388608
BASS_POS_FLUSH = 16777216
BASS_POS_RESET = 33554432
BASS_POS_RELATIVE = 67108864
BASS_POS_INEXACT = 134217728
BASS_POS_DECODE = 268435456
BASS_POS_DECODETO = 536870912
BASS_POS_SCAN = 1073741824
BASS_NODEVICE = 131072
BASS_INPUT_OFF = 65536
BASS_INPUT_ON = 131072
BASS_INPUT_TYPE_MASK = 4278190080
BASS_INPUT_TYPE_UNDEF = 0
BASS_INPUT_TYPE_DIGITAL = 16777216
BASS_INPUT_TYPE_LINE = 33554432
BASS_INPUT_TYPE_MIC = 50331648
BASS_INPUT_TYPE_SYNTH = 67108864
BASS_INPUT_TYPE_CD = 83886080
BASS_INPUT_TYPE_PHONE = 100663296
BASS_INPUT_TYPE_SPEAKER = 117440512
BASS_INPUT_TYPE_WAVE = 134217728
BASS_INPUT_TYPE_AUX = 150994944
BASS_INPUT_TYPE_ANALOG = 167772160
BASS_DSP_READONLY = 1
BASS_DSP_FLOAT = 2
BASS_DSP_FREECALL = 4
BASS_DSP_BYPASS = 4194304
BASS_FX_DX8_CHORUS = 0
BASS_FX_DX8_COMPRESSOR = 1
BASS_FX_DX8_DISTORTION = 2
BASS_FX_DX8_ECHO = 3
BASS_FX_DX8_FLANGER = 4
BASS_FX_DX8_GARGLE = 5
BASS_FX_DX8_I3DL2REVERB = 6
BASS_FX_DX8_PARAMEQ = 7
BASS_FX_DX8_REVERB = 8
BASS_FX_VOLUME = 9
BASS_DX8_PHASE_NEG_180 = 0
BASS_DX8_PHASE_NEG_90 = 1
BASS_DX8_PHASE_ZERO = 2
BASS_DX8_PHASE_90 = 3
BASS_DX8_PHASE_180 = 4
BASS_DEVICENOTIFY_ENABLED = 0
BASS_DEVICENOTIFY_DEFAULT = 1
BASS_DEVICENOTIFY_REC_DEFAULT = 2
BASS_DEVICENOTIFY_DEFAULTCOM = 3
BASS_DEVICENOTIFY_REC_DEFAULTCOM = 4
BASS_IOSNOTIFY_INTERRUPT = 1
BASS_IOSNOTIFY_INTERRUPT_END = 2
