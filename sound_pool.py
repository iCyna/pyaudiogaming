# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# Multifunctional audio engine: playback, 3D/HRTF, FX, tempo/tone, recording, and streaming.
# Supports Windows, Linux, macOS, Android, and iOS.

import array, math, os, struct, threading, time, ctypes, importlib
from .sound_modules import control, pybass as bass, pybassmix as bassmix, pybass_fx as bass_fx
from . import system, utils, buffer
from .sound_fx import *

class _OptionalAddon:
	# Lazy loader for optional BASS addons
	def __init__(self, name): self.name = name
	def __getattr__(self, attr): return getattr(importlib.import_module(".sound_modules." + self.name, __package__), attr)

pybassvst, pybassmidi, pybassenc = _OptionalAddon("pybassvst"), _OptionalAddon("pybassmidi"), _OptionalAddon("pybassenc")
pybassloud, pytags, pybasswasapi = _OptionalAddon("pybassloud"), _OptionalAddon("pytags"), _OptionalAddon("pybasswasapi")
_hrtf, _hrtf_sample_rate, _hrtf_frame_size, _oneshot_pool = None, None, 512, []
_global_sound, _focused = False, True

BASS_ATTRIB_FREQ = getattr(bass, 'BASS_ATTRIB_FREQ', 1)
BASS_ATTRIB_VOL = getattr(bass, 'BASS_ATTRIB_VOL', 2)
BASS_ATTRIB_PAN = getattr(bass, 'BASS_ATTRIB_PAN', 3)
BASS_ATTRIB_TEMPO = getattr(bass_fx, 'BASS_ATTRIB_TEMPO', 0x10000)
BASS_ATTRIB_TEMPO_PITCH = getattr(bass_fx, 'BASS_ATTRIB_TEMPO_PITCH', 0x10001)
BASS_ATTRIB_TEMPO_FREQ = getattr(bass_fx, 'BASS_ATTRIB_TEMPO_FREQ', 0x10002)
BASS_ACTIVE_STOPPED = getattr(bass, 'BASS_ACTIVE_STOPPED', 0)
BASS_ACTIVE_PLAYING = getattr(bass, 'BASS_ACTIVE_PLAYING', 1)
BASS_ACTIVE_STALLED = getattr(bass, 'BASS_ACTIVE_STALLED', 2)
BASS_ACTIVE_PAUSED = getattr(bass, 'BASS_ACTIVE_PAUSED', 3)
BASS_FX_BFX_PITCHSHIFT = getattr(bass_fx, 'BASS_FX_BFX_PITCHSHIFT', 0x10015)
STREAMPROC_PUSH = bass.STREAMPROC_PUSH
RECORDPROC_TYPE = getattr(bass, 'RECORDPROC', ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p))

ATTR_MAP = {
	"volume": BASS_ATTRIB_VOL, "vol": BASS_ATTRIB_VOL, "pan": BASS_ATTRIB_PAN,
	"frequency": BASS_ATTRIB_FREQ, "freq": BASS_ATTRIB_FREQ, "pitch": BASS_ATTRIB_FREQ,
	"tempo": BASS_ATTRIB_TEMPO, "tone": BASS_ATTRIB_TEMPO_PITCH, "tempo_freq": BASS_ATTRIB_TEMPO_FREQ
}

_hrtf_lock = threading.Lock()
_hrtf_prewarm_started = False


def is_hrtf_ready():
	"""Return True if Steam Audio HRTF is already initialized (non-blocking)."""
	return _hrtf_sample_rate is not None


def _initialize_hrtf(sample_rate=None, frame_size=None):
	# Initialize native HRTF addon on demand (thread-safe for background prewarm)
	global _hrtf, _hrtf_sample_rate, _hrtf_frame_size
	if _hrtf is not None and _hrtf_sample_rate is not None and frame_size is None:
		return _hrtf
	with _hrtf_lock:
		if _hrtf is None:
			from .sound_modules import pybass_hrtf
			_hrtf = pybass_hrtf
		if frame_size is not None:
			_hrtf_frame_size = max(64, min(2048, int(frame_size)))
			_hrtf.BASS_HRTF_SetFrameSize(_hrtf_frame_size)
		if sample_rate is None:
			sample_rate = getattr(buffer.hAudiobuffers.get("output"), "frequency", 44100)
		if _hrtf_sample_rate is None:
			if not _hrtf.BASS_HRTF_InitEx(int(sample_rate), os.fsencode(system.get_path("bass")), os.fsencode(system.get_path("phonon")), None, 0x040500, frameSize=_hrtf_frame_size):
				raise RuntimeError("BASS_HRTF_Init failed; check bass_hrtf and phonon libraries")
			_hrtf_sample_rate = int(sample_rate)
	return _hrtf


def prewarm_hrtf_async(sample_rate=None, delay=0.0):
	"""Pre-initialize Steam Audio HRTF on a background thread so startup & first 3D sound never stall."""
	global _hrtf_prewarm_started
	if _hrtf_sample_rate is not None or _hrtf_prewarm_started:
		return
	_hrtf_prewarm_started = True
	def _bg():
		try:
			_initialize_hrtf(sample_rate=sample_rate)
		except Exception:
			pass
	if delay and delay > 0.0:
		t = threading.Timer(float(delay), _bg)
		t.daemon = True
		t.name = "PyAGHRTFPrewarm"
		t.start()
	else:
		threading.Thread(target=_bg, name="PyAGHRTFPrewarm", daemon=True).start()

def set_hrtf_frame_size(frame_size=512):
	global _hrtf_frame_size
	_hrtf_frame_size = max(64, min(2048, int(frame_size)))
	if _hrtf is not None:
		return bool(_hrtf.BASS_HRTF_SetFrameSize(_hrtf_frame_size))
	return True

def get_hrtf_frame_size():
	if _hrtf is not None:
		fs = int(_hrtf.BASS_HRTF_GetFrameSize())
		if fs > 0:
			return fs
	return _hrtf_frame_size

def set_hrtf_distance_model(min_dist=1.0, max_dist=50.0, rolloff=0.12, blend_step=0.25):
	_initialize_hrtf().BASS_HRTF_SetDistanceModel(float(min_dist), float(max_dist), float(rolloff), float(blend_step))

def update_hrtf_listener(listener_x, listener_y, listener_z, yaw=0.0, pitch=0.0, roll=0.0):
	_initialize_hrtf().BASS_HRTF_UpdateListenerEx(float(listener_x), float(listener_y), float(listener_z), float(yaw), float(pitch), float(roll))

def add_hrtf_env_box(material_preset, min_x, max_x, min_y, max_y, min_z, max_z):
	return int(_initialize_hrtf().BASS_HRTF_EnvAddBoxPreset(int(material_preset), float(min_x), float(max_x), float(min_y), float(max_y), float(min_z), float(max_z)))

def clear_hrtf_env_boxes():
	_initialize_hrtf().BASS_HRTF_EnvClearBoxes()

def set_hrtf_auto_raycast(enabled=True):
	_initialize_hrtf().BASS_HRTF_EnvSetAutoRaycast(1 if enabled else 0)

def get_global_sound(): return _global_sound

def set_global_sound(value):
	# True allows background audio; False mutes on focus loss
	global _global_sound
	_global_sound = bool(value); set_focus(_focused)
	return _global_sound

def set_focus(value):
	global _focused
	_focused, out = bool(value), buffer.hAudiobuffers.get("output")
	if out and control.sound_initialized: out._focus(_focused or _global_sound)


class _Devices:
	_record = False

	@classmethod
	def devices(cls):
		# Enumerate enabled playback or recording devices across platforms
		get_info = bass.BASS_RecordGetDeviceInfo if cls._record else bass.BASS_GetDeviceInfo
		info, index, result, enc = bass.BASS_DEVICEINFO(), 0, [], ("mbcs" if control._IS_WIN else "utf-8")
		while get_info(index, ctypes.byref(info)):
			if info.flags & bass.BASS_DEVICE_ENABLED:
				result.append({
					"index": index, "id": (info.driver or b"").decode(enc, errors="replace"),
					"name": (info.name or b"").decode(enc, errors="replace").replace("(", "").replace(")", "").strip(),
					"flags": info.flags
				})
			index += 1
		return result

	def find_device_by_id(self, value):
		for dev in self.devices():
			if (isinstance(value, int) and dev["index"] == value) or (isinstance(value, str) and dev["id"] == value): return dev["index"]
		return -1

	@classmethod
	def get_device_names(cls): return [dev["name"] for dev in cls.devices()]

	def find_device_by_name(self, name):
		return next((dev["index"] for dev in self.devices() if dev["name"] == name), -1)

	def find_default_device(self):
		return next((dev["index"] for dev in self.devices() if dev["flags"] & bass.BASS_DEVICE_DEFAULT), -1)


class OutputManager(_Devices):
	# Unified Output Device manager with direct instance-based device switching
	def __init__(self, device=-1, frequency=44100, period=10, bbuffer=500, flags=0, clsid=None):
		self._device, self.frequency, self.period, self.bbuffer, self.flags, self.clsid = device, frequency, period, bbuffer, flags, clsid
		control.init_sound(dev=device, freq=frequency, period=period, bbuffer=bbuffer, flags=flags, clsid=clsid)
		self.master_mixer = control.master_output
		self._saved_volume = getattr(buffer.hAudiobuffers.get("output"), "_saved_volume", None)

	def start(self): return bool(bass.BASS_Start())
	def pause(self): return bool(bass.BASS_Pause())
	def stop(self): return bool(bass.BASS_Stop())

	def free(self):
		self._focus(True)
		if _hrtf is not None:
			try: _hrtf.BASS_HRTF_Free()
			except Exception: pass
		res = control.shutdown_sound()
		if buffer.hAudiobuffers.get("output") is self: buffer.hAudiobuffers.pop("output", None)
		return res

	def get_device(self):
		try: return int(bass.BASS_GetDevice())
		except Exception: return -1

	def set_device(self, device):
		# Migrate all cached HSAMPLEs and active SoundBase instances to the new output device
		if isinstance(device, str):
			idx = self.find_device_by_name(device)
			device = idx if idx != -1 else self.find_device_by_id(device)
			if device == -1: return False
		dev_idx, previous = int(device if device is not None else -1), self.get_device()
		if dev_idx == previous: return True
		if not bass.BASS_Init(dev_idx, self.frequency, self.flags, None, self.clsid) and bass.BASS_ErrorGetCode() != 14: return False
		if not bass.BASS_SetDevice(dev_idx if dev_idx != -1 else bass.BASS_GetDevice()): return False
		actual = self.get_device()
		with control.preload_mutex:
			for entry in control.sample_cache.values():
				if entry[0]: bass.BASS_ChannelSetDevice(entry[0], actual)
		for obj in list(buffer.hSound_poolbuffers.values()):
			smp_h, de_h, main_h = getattr(obj, "_sample_handle", None), getattr(obj, "dedata", None), getattr(obj, "handle", None)
			if smp_h: bass.BASS_ChannelSetDevice(smp_h, actual)
			if de_h: bass.BASS_ChannelSetDevice(de_h, actual)
			if main_h: bass.BASS_ChannelSetDevice(main_h, actual)
		self._device = actual
		return True

	device = property(fget=get_device, fset=set_device)

	def get_volume(self):
		return (bass.BASS_GetConfig(bass.BASS_CONFIG_GVOL_STREAM) / 100.0, bass.BASS_GetConfig(bass.BASS_CONFIG_GVOL_SAMPLE) / 100.0)

	def set_volume(self, volume):
		if volume is not None:
			vals = volume if isinstance(volume, (tuple, list)) else (volume, volume)
			vals = tuple(max(0.0, min(100.0, float(v))) for v in vals)
			if len(vals) != 2: raise ValueError("Volume needs stream and sample values")
			if self._saved_volume is not None: self._saved_volume = vals
			else: self._write_volume(vals)
		return volume

	def _write_volume(self, values):
		for cfg, val in zip((bass.BASS_CONFIG_GVOL_STREAM, bass.BASS_CONFIG_GVOL_SAMPLE), values):
			bass.BASS_SetConfig(cfg, round(val * 100))

	def _focus(self, focused):
		if not focused and self._saved_volume is None:
			self._saved_volume = self.get_volume(); self._write_volume((0, 0))
		elif focused and self._saved_volume is not None:
			self._write_volume(self._saved_volume); self._saved_volume = None

	volume = property(get_volume, set_volume)

	def find_user_provided_device(self, name):
		idx = self.find_device_by_name(name)
		return idx if idx != -1 else self.find_default_device()


class InputManager(_Devices):
	_record = True
	# Unified Input Recording device manager
	def __init__(self, device=-1):
		self._device = device
		control.bass_call(bass.BASS_RecordInit, device, check_error=True)

	def free(self): return bool(bass.BASS_RecordFree())

	def get_device(self):
		try: return int(bass.BASS_RecordGetDevice())
		except Exception: return -1

	def set_device(self, device):
		if isinstance(device, str):
			idx = self.find_device_by_name(device)
			device = idx if idx != -1 else self.find_device_by_id(device)
			if device == -1: return False
		try:
			if not bass.BASS_RecordInit(int(device)) and bass.BASS_ErrorGetCode() != 14: return False
			actual = bass.BASS_RecordGetDevice() if int(device) == -1 else int(device)
			if not bass.BASS_RecordSetDevice(actual): return False
			self._device = device; return True
		except Exception: return False

	device = property(fget=get_device, fset=set_device)

	def find_user_provided_device(self, name):
		idx = self.find_device_by_name(name)
		return idx if idx != -1 else self.find_default_device()


def output(period=10, bbuffer=500, ThreeD=False, sample_rate=44100, dev=-1, frame_size=None, **kwargs):
	hrtf = kwargs.pop("hrtf", False)
	if frame_size is not None:
		set_hrtf_frame_size(frame_size)
	out = OutputManager(device=dev, frequency=sample_rate, period=period, bbuffer=bbuffer, **kwargs)
	buffer.hAudiobuffers["output"], buffer.hfxbuffers["basic"] = out, Basic()
	set_focus(_focused)
	if ThreeD or hrtf:
		# Defer HRTF prewarm until after startup window & module imports settle (avoids Windows DLL Loader Lock stall)
		prewarm_hrtf_async(sample_rate, delay=1.2)
	return out

def input(device=-1):
	inp = InputManager(device=device)
	buffer.hAudiobuffers["input"] = inp
	return inp

def set_output_device(device):
	out = buffer.hAudiobuffers.get("output")
	return out.set_device(device) if out and hasattr(out, "set_device") else output().set_device(device)

def get_output_device():
	out = buffer.hAudiobuffers.get("output")
	return out.get_device() if out and hasattr(out, "get_device") else int(bass.BASS_GetDevice())

def set_input_device(device):
	inp = buffer.hAudiobuffers.get("input")
	return inp.set_device(device) if inp and hasattr(inp, "set_device") else input().set_device(device)

def get_input_device():
	inp = buffer.hAudiobuffers.get("input")
	return inp.get_device() if inp and hasattr(inp, "get_device") else int(bass.BASS_RecordGetDevice())


class SoundBase:
	# Base class for all sound, mixer, musical, music, record, and VST objects
	def __init__(self):
		self.handle, self.dedata, self.parent_mixer, self.store_entry = None, None, None, None
		self.active_fx_handles, self.active_steam_fx, self._fx_param_cache = {}, {}, {}
		self.mono, self.freq, self.chans, self.paused = False, 44100, 2, False
		self._is_decode, self._is_live_push, self._is_music, self._is_url, self._frame_size = False, False, False, False, None
		self._pitch_shift_fx, self._tone_semitones, self._hrtf_stream, self._hrtf_dsp, self._3d = None, 0.0, False, 0, None
		self._tempo_handle, self._reverse_handle, self._loudness_handle, self._encode_handle, self._encode_proc = None, None, None, None, None
		self._sync_handles = {}
		self.user_volume_offset, self.user_pan_offset, self.user_pitch_offset = 0.0, 0.0, 0.0
		self._last_vol, self._last_pan, self._last_pitch, self._last_tempo, self._last_tone, self._last_hrtf_args = None, None, None, 100.0, 100.0, None
		self._fade_state, self._slide3d_key, self._slide3d_start, self._slide3d_info = {}, None, 0.0, None

	@property
	def channel(self): return self.handle

	def _get_raw_channel_handle(self):
		if not self.handle: return 0
		raw = getattr(self.handle, "handle", self.handle)
		try: return int(raw.value if hasattr(raw, "value") else raw)
		except Exception: return 0

	def _get_raw_source_handle(self):
		target = self.dedata if self.dedata else self.handle
		if not target: return 0
		raw = getattr(target, "handle", target)
		try: return int(raw.value if hasattr(raw, "value") else raw)
		except Exception: return 0

	def _resolve_attr(self, attr): return ATTR_MAP.get(attr, attr) if isinstance(attr, str) else int(attr)

	def _norm_attr_name(self, attr_type):
		t = attr_type.lower() if isinstance(attr_type, str) else "volume"
		if t in ("volume", "vol"): return "volume"
		if t in ("pitch", "frequency", "freq"): return "pitch"
		if t == "pan": return "pan"
		return t

	# --- Per-Node & Global Frame Size Management ---
	def set_frame_size(self, frame_size):
		fs = max(64, min(2048, int(frame_size)))
		self._frame_size = fs
		raw = self._get_raw_channel_handle()
		if raw and (self._hrtf_stream or self._hrtf_dsp):
			return bool(_initialize_hrtf().BASS_HRTF_SetNodeFrameSize(raw, fs))
		return True

	def get_frame_size(self):
		raw = self._get_raw_channel_handle()
		if raw and (self._hrtf_stream or self._hrtf_dsp) and _hrtf is not None:
			fs = int(_hrtf.BASS_HRTF_GetNodeFrameSize(raw))
			if fs > 0:
				return fs
		return self._frame_size if self._frame_size is not None else get_hrtf_frame_size()

	frame_size = property(fget=get_frame_size, fset=set_frame_size)

	def is_fading(self, attr_type=None):
		if not self._fade_state: return False
		now = time.monotonic()
		for k in list(self._fade_state.keys()):
			sv, tv, st_t, dur = self._fade_state[k]
			if now - st_t >= dur: self._fade_state.pop(k, None)
		if attr_type is None: return bool(self._fade_state)
		return self._norm_attr_name(attr_type) in self._fade_state

	def get_faded_value(self, attr_type="volume", default_val=100.0):
		nt = self._norm_attr_name(attr_type)
		info = self._fade_state.get(nt)
		if not info: return float(default_val)
		sv, tv, st_t, dur = info
		el = time.monotonic() - st_t
		if dur <= 0.0 or el >= dur:
			self._fade_state.pop(nt, None)
			return float(tv)
		return float(sv + (tv - sv) * max(0.0, min(1.0, el / dur)))

	def set_mixer(self, target_mixer=None):
		raw = self._get_raw_channel_handle()
		if not raw: self.parent_mixer = target_mixer; return False
		if target_mixer is None:
			if self.parent_mixer and hasattr(self.parent_mixer, "remove"): self.parent_mixer.remove(self)
			elif self.parent_mixer and hasattr(self.parent_mixer, "remove_channel"): self.parent_mixer.remove_channel(raw)
			self.parent_mixer = None; return True
		if hasattr(target_mixer, "add") and target_mixer.add(self): self.parent_mixer = target_mixer; return True
		if hasattr(target_mixer, "add_channel") and target_mixer.add_channel(raw): self.parent_mixer = target_mixer; return True
		return False

	def _attach_hrtf(self, decode=None, flags=0):
		if self._hrtf_stream: return True
		raw = self._get_raw_channel_handle()
		if not raw: return False
		if decode is None:
			decode = self._is_decode
		out_flags = int(flags) | (control.BASS_STREAM_DECODE if decode else 0)
		hrtf_lib = _initialize_hrtf(frame_size=self._frame_size)
		rendered = hrtf_lib.BASS_HRTF_StreamCreate(raw, out_flags)
		if rendered:
			if self.store_entry: control.unregister_hstream(self.store_entry)
			self.dedata, self.handle, self._hrtf_stream, self.chans = self.handle, rendered, True, 2
			self.store_entry = control.register_hstream(self.handle)
			if self._frame_size is not None:
				hrtf_lib.BASS_HRTF_SetNodeFrameSize(rendered, int(self._frame_size))
			if self._is_live_push:
				hrtf_lib.BASS_HRTF_SetLiveStreamMode(rendered, 1, 1)
			return True
		raise RuntimeError(f"Cannot create HRTF stream: BASS error {bass.BASS_ErrorGetCode()}")

	def attach_hrtf_dsp(self, priority=0):
		# Attach HRTF DSP directly to channel, or auto-wrap mono decode stream for full 2-ear binaural stereo
		if self._hrtf_stream or self._hrtf_dsp: return True
		raw = self._get_raw_channel_handle()
		if not raw: return False
		ci = bass.BASS_CHANNELINFO()
		if bass.BASS_ChannelGetInfo(raw, ctypes.byref(ci)):
			self.freq, self.chans = ci.freq, ci.chans
			# If source is a 1-channel mono decode stream, wrapping with BASS_HRTF_StreamCreate gives true 2-channel stereo binaural output
			if ci.chans == 1 and (ci.flags & control.BASS_STREAM_DECODE):
				try:
					return self._attach_hrtf(decode=self._is_decode)
				except Exception:
					pass
		hrtf_lib = _initialize_hrtf(frame_size=self._frame_size)
		dsp = hrtf_lib.BASS_HRTF_AttachDSP(raw, int(priority))
		if dsp:
			self._hrtf_dsp = dsp
			if self._frame_size is not None:
				hrtf_lib.BASS_HRTF_SetNodeFrameSize(raw, int(self._frame_size))
			if self._is_live_push:
				hrtf_lib.BASS_HRTF_SetLiveStreamMode(raw, 1, 1)
			return True
		return False

	def detach_hrtf_dsp(self):
		if not self._hrtf_dsp: return False
		raw = self._get_raw_channel_handle()
		if _hrtf and raw: _hrtf.BASS_HRTF_DetachDSP(raw)
		self._hrtf_dsp, self._last_hrtf_args = 0, None
		return True

	def set_hrtf_enabled(self, enabled=True):
		raw = self._get_raw_channel_handle()
		return bool(raw and _hrtf and _hrtf.BASS_HRTF_SetEnabled(raw, 1 if enabled else 0))

	def _ensure_hrtf_attached(self):
		if self._hrtf_stream or self._hrtf_dsp:
			return True
		if self.attach_hrtf_dsp():
			return True
		return self._attach_hrtf(decode=self._is_decode)

	def setPaused(self, p):
		if self.paused == p or (not self.playing and p): return
		self.paused = bool(p)
		if self.handle:
			is_mixed = bool(bassmix.BASS_Mixer_ChannelGetMixer(self.handle))
			if self.paused:
				if is_mixed: bassmix.BASS_Mixer_ChannelFlags(self.handle, control.BASS_MIXER_PAUSE, control.BASS_MIXER_PAUSE)
				else: bass.BASS_ChannelPause(self.handle)
			else:
				if is_mixed: bassmix.BASS_Mixer_ChannelFlags(self.handle, 0, control.BASS_MIXER_PAUSE)
				else: bass.BASS_ChannelPlay(self.handle, False)

	def fade(self, fadetime, value=0, type="volume"):
		if self.handle:
			nt = self._norm_attr_name(type)
			attr = self._resolve_attr(nt)
			target_v = float(value)
			ft_ms = int(max(0, fadetime))
			if nt == "volume":
				cur_v = self._last_vol if self._last_vol is not None else float(self.volume or 0.0)
				target_v = max(0.0, min(100.0, target_v))
				v = target_v / 100.0
				self._last_vol = target_v if ft_ms == 0 else None
			elif nt == "pan":
				cur_v = self._last_pan if self._last_pan is not None else float(self.pan or 0.0)
				target_v = max(-100.0, min(100.0, target_v))
				v = target_v / 100.0
				self._last_pan = target_v if ft_ms == 0 else None
			elif nt == "pitch":
				cur_v = self._last_pitch if self._last_pitch is not None else float(self.pitch or 100.0)
				v = (target_v / 100.0) * float(self.freq)
				self._last_pitch = target_v if ft_ms == 0 else None
			elif nt == "tempo":
				cur_v = float(self._last_tempo if self._last_tempo is not None else 100.0)
				target_v = max(0.0, target_v)
				v = max(-95.0, min(5000.0, target_v - 100.0))
				self._last_tempo = target_v if ft_ms == 0 else None
			elif nt == "tone":
				cur_v = float(self._last_tone if self._last_tone is not None else 100.0)
				target_v = max(0.0, target_v)
				v = self._tone_percent_to_semitones(target_v)
				self._last_tone = target_v if ft_ms == 0 else None
			else:
				cur_v, v = target_v, target_v
			slide_target = self._tempo_handle if (nt in ("tempo", "tone") and self._tempo_handle) else self.handle
			if nt == "tone" and not self._tempo_handle:
				self.set_tone(target_v)
				return
			if ft_ms > 0:
				if nt in self._fade_state: cur_v = self.get_faded_value(nt, cur_v)
				self._fade_state[nt] = (float(cur_v), float(target_v), time.monotonic(), ft_ms / 1000.0)
				bass.BASS_ChannelSlideAttribute(slide_target, attr, ctypes.c_float(v), ft_ms)
			else:
				self._fade_state.pop(nt, None)
				bass.BASS_ChannelSetAttribute(slide_target, attr, ctypes.c_float(v))

	def fadeout(self, fadetime, value=0, type="volume"):
		if self.handle:
			return self.fade(fadetime, value, type=type)

	def fadein(self, fadetime, value=100, type="volume"):
		if self.handle:
			return self.fade(fadetime, value, type=type)

	# =========================================================================
	# UNIFIED FX SYSTEM: ADD/ENABLE FX (setfx) vs MODIFY PARAMETERS (set_fx_param / set_param)
	# Supports BASS DX8, BASS_FX (BFX), and Steam Audio (BASS_HRTF)
	# =========================================================================
	def setfx(self, fx_key, priority=0, **overrides):
		"""Add or enable an audio effect preset (BASS_FX, DX8, Filter, or Steam Audio FX)."""
		if not self.handle: return False
		fx_engine = buffer.hfxbuffers.get("basic")
		if fx_engine is None:
			fx_engine = Basic()
			buffer.hfxbuffers["basic"] = fx_engine
		target = fx_engine.get_fx(fx_key)
		if not target: return False

		engine_type = target.get("engine", "bass")
		store_key = target.get("id") or fx_key

		# --- STEAM AUDIO FX ---
		if engine_type == "steam":
			if not self._ensure_hrtf_attached():
				return False
			raw = self._get_raw_channel_handle()
			hrtf_lib = _initialize_hrtf(frame_size=self._frame_size)
			fx_type = int(target["fx_type"])
			preset_id = int(target.get("preset_id", 0))
			if not hrtf_lib.BASS_HRTF_AddSteamFX(raw, fx_type, preset_id):
				return False
			for extra_type, extra_preset in target.get("extra_fx", ()):
				hrtf_lib.BASS_HRTF_AddSteamFX(raw, int(extra_type), int(extra_preset))
			merged_params = dict(target.get("params") or {})
			merged_params.update(overrides)
			if merged_params:
				self.set_fx_param(store_key, **merged_params)
			self.active_steam_fx[store_key] = {"fx_type": fx_type, "preset_id": preset_id, "params": merged_params}
			self.active_fx_handles[store_key] = ("steam", fx_type)
			return True

		# --- BASS / BASS_FX / DX8 ---
		if store_key in self.active_fx_handles:
			old_h = self.active_fx_handles.pop(store_key, None)
			if isinstance(old_h, int) and old_h:
				try: bass.BASS_ChannelRemoveFX(self.handle, old_h)
				except Exception: pass
		fx_alloc = bass.BASS_ChannelSetFX(self.handle, target["name"], int(priority))
		if not fx_alloc: return False
		params = target["param"]()
		if overrides:
			fx_engine.apply_param_overrides(params, **overrides)
		bass.BASS_FXSetParameters(fx_alloc, ctypes.byref(params) if hasattr(params, "_fields_") else params)
		self.active_fx_handles[store_key] = fx_alloc
		self._fx_param_cache[store_key] = params
		return True

	add_fx = setfx

	def set_fx_param(self, fx_key=None, **params):
		"""Update parameters of an active BASS_FX or Steam Audio FX without recreating the effect."""
		if not self.handle or not params: return False
		fx_engine = buffer.hfxbuffers.get("basic") or Basic()

		# 1. If fx_key points to an active BASS_FX / DX8 handle, update its struct in-place
		if fx_key and fx_key in self.active_fx_handles and not isinstance(self.active_fx_handles[fx_key], tuple):
			fx_h = self.active_fx_handles[fx_key]
			param_struct = self._fx_param_cache.get(fx_key)
			if param_struct is None:
				target = fx_engine.get_fx(fx_key)
				if target and "param" in target:
					param_struct = target["param"]()
					bass.BASS_FXGetParameters(fx_h, ctypes.byref(param_struct))
			if param_struct is not None:
				fx_engine.apply_param_overrides(param_struct, **params)
				self._fx_param_cache[fx_key] = param_struct
				return bool(bass.BASS_FXSetParameters(fx_h, ctypes.byref(param_struct)))
			return False

		# 2. Otherwise update Steam Audio / HRTF parameters on the node
		if not self._hrtf_stream and not self._hrtf_dsp:
			if not self._ensure_hrtf_attached():
				return False
		raw = self._get_raw_channel_handle()
		if not raw: return False
		hrtf_lib = _initialize_hrtf(frame_size=self._frame_size)
		ok = True
		for k, v in params.items():
			pid = fx_engine.resolve_steam_param_id(k)
			if pid is not None:
				if not hrtf_lib.BASS_HRTF_SetFXParam(raw, int(pid), float(v)):
					ok = False
			elif fx_key and fx_key in self.active_fx_handles and not isinstance(self.active_fx_handles[fx_key], tuple):
				pass
		if fx_key and fx_key in self.active_steam_fx:
			self.active_steam_fx[fx_key]["params"].update(params)
		return ok

	def set_param(self, param_name=None, value=None, fx_key=None, **kwargs):
		"""Direct parameter setter for Steam Audio HRTF or an active FX (distinct from setfx)."""
		params = dict(kwargs)
		if param_name is not None and value is not None:
			params[str(param_name)] = value
		return self.set_fx_param(fx_key=fx_key, **params)

	def get_param(self, param_name, fx_key=None):
		"""Query a parameter value from Steam Audio HRTF or an active BASS_FX."""
		fx_engine = buffer.hfxbuffers.get("basic") or Basic()
		if fx_key and fx_key in self._fx_param_cache:
			st = self._fx_param_cache[fx_key]
			if hasattr(st, param_name):
				return getattr(st, param_name)
		pid = fx_engine.resolve_steam_param_id(param_name)
		raw = self._get_raw_channel_handle()
		if pid is not None and raw and (self._hrtf_stream or self._hrtf_dsp):
			return float(_initialize_hrtf().BASS_HRTF_GetFXParam(raw, int(pid)))
		return None

	def remove_fx(self, fx_key):
		"""Remove a single active BASS_FX or Steam Audio FX."""
		if not self.handle or fx_key not in self.active_fx_handles: return False
		entry = self.active_fx_handles.pop(fx_key, None)
		self._fx_param_cache.pop(fx_key, None)
		self.active_steam_fx.pop(fx_key, None)
		if isinstance(entry, tuple) and entry[0] == "steam":
			raw = self._get_raw_channel_handle()
			if raw and _hrtf:
				return bool(_hrtf.BASS_HRTF_RemoveSteamFX(raw, int(entry[1])))
			return True
		if entry:
			try: return bool(bass.BASS_ChannelRemoveFX(self.handle, entry))
			except Exception: return False
		return False

	def remove_all_fx(self):
		if not self.handle: return
		for fx_key, fx_h in list(self.active_fx_handles.items()):
			if isinstance(fx_h, tuple) and fx_h[0] == "steam":
				raw = self._get_raw_channel_handle()
				if raw and _hrtf:
					try: _hrtf.BASS_HRTF_RemoveSteamFX(raw, int(fx_h[1]))
					except Exception: pass
			elif fx_h:
				try: bass.BASS_ChannelRemoveFX(self.handle, fx_h)
				except Exception: pass
		self.active_fx_handles.clear()
		self.active_steam_fx.clear()
		self._fx_param_cache.clear()
		raw = self._get_raw_channel_handle()
		if raw and _hrtf and (self._hrtf_stream or self._hrtf_dsp):
			try: _hrtf.BASS_HRTF_ClearSteamFX(raw)
			except Exception: pass

	# --- Steam Audio Dedicated High-Level Controls ---
	def set_steam_reverb(self, preset="steam_medium_room", wet=-1.0, **overrides):
		if isinstance(preset, int):
			if not self._ensure_hrtf_attached(): return False
			raw = self._get_raw_channel_handle()
			ok = bool(_initialize_hrtf().BASS_HRTF_SetReflectionPreset(raw, int(preset), float(wet)))
			if overrides: self.set_fx_param(**overrides)
			return ok
		key = preset if str(preset).startswith("steam_") else f"steam_{str(preset).replace(' ', '_')}"
		if wet >= 0.0: overrides["reverb_wet"] = float(wet)
		return self.setfx(key, **overrides)

	def set_steam_reflection_params(self, reverb_low=1.2, reverb_mid=1.0, reverb_high=0.7, eq_low=1.0, eq_mid=0.9, eq_high=0.7, delay_ms=20.0, wet_mix=0.25):
		if not self._ensure_hrtf_attached(): return False
		raw = self._get_raw_channel_handle()
		hrtf_lib = _initialize_hrtf()
		hrtf_lib.BASS_HRTF_EnableReflectionEffect(raw, 1)
		return bool(hrtf_lib.BASS_HRTF_SetReflectionParams(
			raw, float(reverb_low), float(reverb_mid), float(reverb_high),
			float(eq_low), float(eq_mid), float(eq_high), float(delay_ms), float(wet_mix)
		))

	def set_steam_path_params(self, eq_low=0.9, eq_mid=0.7, eq_high=0.45, sh0=1.0, sh1=0.5, sh2=0.5, sh3=0.5, wet_mix=0.25):
		if not self._ensure_hrtf_attached(): return False
		raw = self._get_raw_channel_handle()
		hrtf_lib = _initialize_hrtf()
		hrtf_lib.BASS_HRTF_EnablePathEffect(raw, 1)
		return bool(hrtf_lib.BASS_HRTF_SetPathParams(
			raw, float(eq_low), float(eq_mid), float(eq_high),
			float(sh0), float(sh1), float(sh2), float(sh3), float(wet_mix)
		))

	def set_steam_material(self, material_preset, enable_direct=True):
		if not self._ensure_hrtf_attached(): return False
		raw = self._get_raw_channel_handle()
		hrtf_lib = _initialize_hrtf()
		if enable_direct: hrtf_lib.BASS_HRTF_EnablePhysicalFilter(raw, 1)
		return bool(hrtf_lib.BASS_HRTF_SetNodeMaterialPreset(raw, int(material_preset)))

	def set_steam_physical_params(self, x=0.0, y=0.0, z=0.0, occlusion=0.0, air_absorption=1.0, trans_low=None, trans_mid=None, trans_high=None):
		if not self._ensure_hrtf_attached(): return False
		raw = self._get_raw_channel_handle()
		hrtf_lib = _initialize_hrtf()
		ok = bool(hrtf_lib.BASS_HRTF_SetPhysicalParams(raw, float(x), float(y), float(z), float(occlusion), float(air_absorption)))
		if trans_low is not None and trans_mid is not None and trans_high is not None:
			hrtf_lib.BASS_HRTF_SetTransmissionBands(raw, float(trans_low), float(trans_mid), float(trans_high))
		return ok

	def set_steam_directivity(self, directivity=1.0, dipole_weight=None, dipole_power=1.0, ahead=(0.0, 1.0, 0.0)):
		if not self._ensure_hrtf_attached(): return False
		raw = self._get_raw_channel_handle()
		hrtf_lib = _initialize_hrtf()
		if dipole_weight is not None:
			return bool(hrtf_lib.BASS_HRTF_SetDirectivityEx(raw, float(dipole_weight), float(dipole_power), float(ahead[0]), float(ahead[1]), float(ahead[2])))
		return bool(hrtf_lib.BASS_HRTF_SetDirectivity(raw, float(directivity)))

	def set_steam_mode(self, mode=0, ambi_order=1, surround_layout=1):
		if not self._ensure_hrtf_attached(): return False
		raw = self._get_raw_channel_handle()
		hrtf_lib = _initialize_hrtf()
		if isinstance(mode, str):
			m_map = {"binaural": 0, "panning": 1, "ambisonics": 2, "virtual_surround": 3, "surround": 3}
			mode = m_map.get(mode.lower().strip(), 0)
		mode = int(mode)
		if mode == 2:
			hrtf_lib.BASS_HRTF_EnableAmbisonics(raw, 1, int(ambi_order))
		elif mode == 3:
			hrtf_lib.BASS_HRTF_EnableVirtualSurround(raw, 1, int(surround_layout))
		return bool(hrtf_lib.BASS_HRTF_SetPanningMode(raw, mode))

	def set_hrtf_distance_limits(self, min_dist=1.0, max_dist=50.0, rolloff=0.12, blend_step=0.25):
		if not self._ensure_hrtf_attached(): return False
		return bool(_initialize_hrtf().BASS_HRTF_SetNodeDistanceLimits(self._get_raw_channel_handle(), float(min_dist), float(max_dist), float(rolloff), float(blend_step)))

	def set_hrtf_source_radius(self, radius=0.0):
		if not self._ensure_hrtf_attached(): return False
		return bool(_initialize_hrtf().BASS_HRTF_SetSourceRadius(self._get_raw_channel_handle(), float(radius)))

	def set_hrtf_air_absorption_bands(self, low=1.0, mid=1.0, high=1.0):
		if not self._ensure_hrtf_attached(): return False
		return bool(_initialize_hrtf().BASS_HRTF_SetAirAbsorptionBands(self._get_raw_channel_handle(), float(low), float(mid), float(high)))

	def set_hrtf_spatial_blend(self, blend=1.0):
		if not self._ensure_hrtf_attached(): return False
		return bool(_initialize_hrtf().BASS_HRTF_SetSpatialBlend(self._get_raw_channel_handle(), max(0.0, min(1.0, float(blend)))))

	def set_hrtf_stereo_input(self, enabled=True):
		if not self._ensure_hrtf_attached(): return False
		return bool(_initialize_hrtf().BASS_HRTF_SetStereoInput(self._get_raw_channel_handle(), 1 if enabled else 0))

	def slide_hrtf_position(self, x, y, z, time_ms=250.0):
		if not self._ensure_hrtf_attached(): return False
		return bool(_initialize_hrtf().BASS_HRTF_SlidePosition(self._get_raw_channel_handle(), float(x), float(y), float(z), float(time_ms)))

	def slide_hrtf_attribute(self, attr, target, time_ms=250.0):
		if not self._ensure_hrtf_attached(): return False
		hrtf_lib = _initialize_hrtf()
		if isinstance(attr, str):
			a_map = {
				"occlusion": hrtf_lib.BASS_HRTF_ATTR_OCCLUSION,
				"max_blend": hrtf_lib.BASS_HRTF_ATTR_MAX_BLEND,
				"blend": hrtf_lib.BASS_HRTF_ATTR_MAX_BLEND,
				"gain": hrtf_lib.BASS_HRTF_ATTR_GAIN,
				"air_absorption": hrtf_lib.BASS_HRTF_ATTR_AIR_ABSORB,
				"air": hrtf_lib.BASS_HRTF_ATTR_AIR_ABSORB,
				"reverb_wet": hrtf_lib.BASS_HRTF_ATTR_REVERB_WET,
				"wet": hrtf_lib.BASS_HRTF_ATTR_REVERB_WET,
			}
			attr = a_map.get(attr.strip().lower(), hrtf_lib.BASS_HRTF_ATTR_GAIN)
		return bool(hrtf_lib.BASS_HRTF_SlideAttribute(self._get_raw_channel_handle(), int(attr), float(target), float(time_ms)))

	def set_hrtf_world_position(self, x, y, z, bilinear=True):
		if not self._ensure_hrtf_attached(): return False
		return bool(_initialize_hrtf().BASS_HRTF_SetWorldPosition(self._get_raw_channel_handle(), float(x), float(y), float(z), 1 if bilinear else 0))

	def set_hrtf_live_stream_mode(self, enabled=True, low_latency_flush=True):
		if not self._ensure_hrtf_attached(): return False
		return bool(_initialize_hrtf().BASS_HRTF_SetLiveStreamMode(self._get_raw_channel_handle(), 1 if enabled else 0, 1 if low_latency_flush else 0))

	def reset_hrtf(self):
		raw = self._get_raw_channel_handle()
		return bool(raw and _hrtf and _hrtf.BASS_HRTF_Reset(raw))

	def set_steam_direct_enabled(self, enabled=True):
		if not self._ensure_hrtf_attached(): return False
		return bool(_initialize_hrtf().BASS_HRTF_EnablePhysicalFilter(self._get_raw_channel_handle(), 1 if enabled else 0))

	def set_steam_reflection_enabled(self, enabled=True):
		if not self._ensure_hrtf_attached(): return False
		return bool(_initialize_hrtf().BASS_HRTF_EnableReflectionEffect(self._get_raw_channel_handle(), 1 if enabled else 0))

	def set_steam_path_enabled(self, enabled=True):
		if not self._ensure_hrtf_attached(): return False
		return bool(_initialize_hrtf().BASS_HRTF_EnablePathEffect(self._get_raw_channel_handle(), 1 if enabled else 0))

	# --- Tempo (speed without pitch) & Tone (pitch without speed), 0..100+ scale (100 = normal) ---
	@staticmethod
	def _tone_percent_to_semitones(value):
		v = max(0.0, float(value))
		if v <= 0.0:
			return -60.0
		return max(-60.0, min(60.0, 12.0 * math.log2(max(0.03125, v / 100.0))))

	@staticmethod
	def _semitones_to_tone_percent(semitones):
		return 100.0 * (2.0 ** (float(semitones) / 12.0))

	@property
	def tempo(self):
		"""Playback speed percentage without changing pitch (100 = normal, 50 = half, 200 = 2x)."""
		if not self.handle: return 100.0
		if "tempo" in self._fade_state: return self.get_faded_value("tempo", self._last_tempo or 100.0)
		target = self._tempo_handle or self.handle
		val = ctypes.c_float(0.0)
		if bass.BASS_ChannelGetAttribute(target, BASS_ATTRIB_TEMPO, ctypes.byref(val)):
			self._last_tempo = val.value + 100.0
		return float(self._last_tempo if self._last_tempo is not None else 100.0)

	@tempo.setter
	def tempo(self, value):
		self.set_tempo(value)

	def set_tempo(self, value):
		"""Set playback speed percentage (0..100+, 100 = normal) without changing pitch (requires tempo=True stream)."""
		if not self.handle: return False
		v = max(0.0, float(value))
		target = self._tempo_handle or self.handle
		bass_pct = max(-95.0, min(5000.0, v - 100.0))
		self._last_tempo = v
		self._fade_state.pop("tempo", None)
		return bool(bass.BASS_ChannelSetAttribute(target, BASS_ATTRIB_TEMPO, ctypes.c_float(bass_pct)))

	def get_tempo(self):
		return self.tempo

	@property
	def tone(self):
		"""Pitch percentage without changing speed (100 = normal, 50 = -1 octave, 200 = +1 octave)."""
		if not self.handle: return 100.0
		if "tone" in self._fade_state: return self.get_faded_value("tone", self._last_tone or 100.0)
		if self._tempo_handle:
			val = ctypes.c_float(0.0)
			if bass.BASS_ChannelGetAttribute(self._tempo_handle, BASS_ATTRIB_TEMPO_PITCH, ctypes.byref(val)):
				self._tone_semitones = val.value
				self._last_tone = self._semitones_to_tone_percent(val.value)
		return float(self._last_tone if self._last_tone is not None else 100.0)

	@tone.setter
	def tone(self, value):
		self.set_tone(value)

	def set_tone(self, value):
		"""Set pitch percentage (0..100+, 100 = normal) without changing playback speed."""
		if not self.handle: return False
		v = max(0.0, float(value))
		semis = self._tone_percent_to_semitones(v)
		self._last_tone = v
		self._tone_semitones = semis
		self._fade_state.pop("tone", None)
		if self._tempo_handle:
			return bool(bass.BASS_ChannelSetAttribute(self._tempo_handle, BASS_ATTRIB_TEMPO_PITCH, ctypes.c_float(semis)))
		# Fallback on non-tempo streams: use BASS_FX_BFX_PITCHSHIFT DSP (pitch without speed change)
		if abs(semis) < 0.01:
			if self._pitch_shift_fx:
				try: bass.BASS_ChannelRemoveFX(self.handle, self._pitch_shift_fx)
				except Exception: pass
				self._pitch_shift_fx = None
			return True
		if not self._pitch_shift_fx:
			self._pitch_shift_fx = bass.BASS_ChannelSetFX(self.handle, BASS_FX_BFX_PITCHSHIFT, 0)
		if not self._pitch_shift_fx:
			return False
		p = BASS_BFX_PITCHSHIFT()
		p.fPitchShift = 1.0
		p.fSemitones = float(max(-24.0, min(24.0, semis)))
		p.lFFTsize = 1024
		p.lOsamp = 8
		p.lChannel = BASS_BFX_CHANALL
		return bool(bass.BASS_FXSetParameters(self._pitch_shift_fx, ctypes.byref(p)))

	def get_tone(self):
		return self.tone

	def set_reverse_direction(self, reverse=True):
		"""Switch playback direction on a reverse=True stream (-1 = reverse, +1 = forward)."""
		target = self._reverse_handle or self.handle
		if not target: return False
		attr = getattr(bass_fx, "BASS_ATTRIB_REVERSE_DIR", 0x11000)
		return bool(bass.BASS_ChannelSetAttribute(target, attr, ctypes.c_float(-1.0 if reverse else 1.0)))

	def get_bpm(self, start_sec=0.0, end_sec=None, min_bpm=45, max_bpm=230):
		"""Detect BPM of a decode stream via BASS_FX_BPM_DecodeGet."""
		ch = self._get_raw_source_handle()
		if not ch: return 0.0
		if end_sec is None:
			dur = self.get_length()
			end_sec = max(1.0, (dur / 1000.0) if dur > 0 else 30.0)
		minmax = (int(max_bpm) << 16) | (int(min_bpm) & 0xFFFF)
		try:
			return float(bass_fx.BASS_FX_BPM_DecodeGet(ch, float(start_sec), float(end_sec), minmax, 0, None, None))
		except Exception:
			return 0.0

	# --- Tags / Metadata (pytags + BASS_ChannelGetTags including URL ICY/META) ---
	def get_tags(self, fmt=None):
		"""Read audio tags via TAGS (ID3/OGG/FLAC/MP4/WMA/MOD) or URL StreamTitle metadata."""
		ch = self._get_raw_source_handle() or self._get_raw_channel_handle()
		if not ch: return "" if fmt else {}
		if fmt is not None:
			try:
				res = pytags.TAGS_Read(ch, str(fmt).encode("utf-8"))
				return res.decode("utf-8", errors="replace") if res else ""
			except Exception:
				return ""
		info = {}
		try:
			for key, token in (("title", "%TITL"), ("artist", "%ARTI"), ("album", "%ALBM"), ("year", "%YEAR"), ("track", "%TRCK"), ("genre", "%GNRE"), ("comment", "%CMNT")):
				val = pytags.TAGS_Read(ch, token.encode("utf-8"))
				if val:
					txt = val.decode("utf-8", errors="replace").strip()
					if txt: info[key] = txt
		except Exception:
			pass
		# Also check shoutcast/icecast META for URL streams
		try:
			meta_ptr = bass.BASS_ChannelGetTags(ch, bass.BASS_TAG_META)
			if meta_ptr:
				raw_meta = ctypes.cast(meta_ptr, ctypes.c_char_p).value
				if raw_meta:
					info["stream_meta"] = raw_meta.decode("utf-8", errors="replace")
		except Exception:
			pass
		return info

	# --- Loudness Measurement (pybassloud: ITU-R BS.1770 / EBU R128) ---
	def start_loudness(self, flags=None, priority=0):
		if not self.handle: return False
		self.stop_loudness()
		if flags is None:
			flags = pybassloud.BASS_LOUDNESS_INTEGRATED | pybassloud.BASS_LOUDNESS_CURRENT | pybassloud.BASS_LOUDNESS_PEAK | pybassloud.BASS_LOUDNESS_TRUEPEAK | pybassloud.BASS_LOUDNESS_RANGE
		h = pybassloud.BASS_Loudness_Start(self.handle, int(flags), int(priority))
		if h:
			self._loudness_handle = int(h)
			return True
		return False

	def get_loudness(self, mode="integrated"):
		if not self._loudness_handle: return None
		m_map = {
			"current": pybassloud.BASS_LOUDNESS_CURRENT,
			"integrated": pybassloud.BASS_LOUDNESS_INTEGRATED,
			"range": pybassloud.BASS_LOUDNESS_RANGE,
			"peak": pybassloud.BASS_LOUDNESS_PEAK,
			"truepeak": pybassloud.BASS_LOUDNESS_TRUEPEAK,
		}
		m_flag = m_map.get(str(mode).lower(), int(mode) if isinstance(mode, int) else pybassloud.BASS_LOUDNESS_INTEGRATED)
		val = ctypes.c_float(0.0)
		if pybassloud.BASS_Loudness_GetLevel(self._loudness_handle, m_flag, ctypes.byref(val)):
			return float(val.value)
		return None

	def stop_loudness(self):
		if self._loudness_handle:
			try: pybassloud.BASS_Loudness_Stop(self._loudness_handle)
			except Exception: pass
			self._loudness_handle = None

	# --- Native Encoding (pybassenc: WAV / MP3 / OGG / FLAC / OPUS) ---
	def start_encode(self, output_path=None, fmt="wav", options="", flags=0, callback=None):
		if not self.handle: return False
		self.stop_encode()
		fmt_l = str(fmt or "wav").strip().lower()
		opt_b = str(options or "").encode("utf-8")
		c_proc = None
		if callable(callback):
			enc_cb_type = getattr(pybassenc, "ENCODEPROC", ctypes.CFUNCTYPE(None, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p))
			def _enc_cb(handle, channel, buf_ptr, length, user):
				if buf_ptr and length > 0:
					try: callback(ctypes.string_at(buf_ptr, int(length)))
					except Exception: pass
			c_proc = enc_cb_type(_enc_cb)
		out_b = os.fsencode(os.fspath(output_path)) if output_path else None
		h = 0
		if fmt_l == "mp3":
			h = pybassenc.BASS_Encode_MP3_StartFile(self.handle, opt_b, int(flags), out_b) if out_b else pybassenc.BASS_Encode_MP3_Start(self.handle, opt_b, int(flags), c_proc, None)
		elif fmt_l == "ogg":
			h = pybassenc.BASS_Encode_OGG_StartFile(self.handle, opt_b, int(flags), out_b) if out_b else pybassenc.BASS_Encode_OGG_Start(self.handle, opt_b, int(flags), c_proc, None)
		elif fmt_l == "flac":
			h = pybassenc.BASS_Encode_FLAC_StartFile(self.handle, opt_b, int(flags), out_b) if out_b else pybassenc.BASS_Encode_FLAC_Start(self.handle, opt_b, int(flags), c_proc, None)
		elif fmt_l == "opus":
			h = pybassenc.BASS_Encode_OPUS_StartFile(self.handle, opt_b, int(flags), out_b) if out_b else pybassenc.BASS_Encode_OPUS_Start(self.handle, opt_b, int(flags), c_proc, None)
		else:
			pcm_flags = int(flags) | (getattr(pybassenc, "BASS_ENCODE_PCM", 64) if fmt_l == "wav" else 0)
			h = pybassenc.BASS_Encode_Start(self.handle, str(output_path or options or ""), pcm_flags, c_proc, None)
		if h:
			self._encode_handle = int(h)
			self._encode_proc = c_proc
			return True
		return False

	def set_encode_paused(self, paused=True):
		return bool(self._encode_handle and pybassenc.BASS_Encode_SetPaused(self._encode_handle, 1 if paused else 0))

	def stop_encode(self):
		if self._encode_handle:
			try: pybassenc.BASS_Encode_Stop(self._encode_handle)
			except Exception: pass
			self._encode_handle = None
			self._encode_proc = None

	# --- Event-Driven Sync Callbacks (BASS_ChannelSetSync) ---
	def on_sync(self, sync_type, callback, param=0, onetime=False):
		if not self.handle or not callable(callback): return 0
		s_map = {
			"pos": bass.BASS_SYNC_POS,
			"end": bass.BASS_SYNC_END,
			"meta": bass.BASS_SYNC_META,
			"slide": bass.BASS_SYNC_SLIDE,
			"stall": bass.BASS_SYNC_STALL,
			"download": bass.BASS_SYNC_DOWNLOAD,
			"free": bass.BASS_SYNC_FREE,
		}
		st = s_map.get(str(sync_type).lower(), int(sync_type) if isinstance(sync_type, int) else bass.BASS_SYNC_END)
		if onetime:
			st |= getattr(bass, "BASS_SYNC_ONETIME", 0x80000000)
		def _cb(handle, channel, data, user):
			try: callback(handle, channel, data)
			except Exception: pass
		c_cb = bass.SYNCPROC(_cb)
		hsync = bass.BASS_ChannelSetSync(self.handle, st, int(param), c_cb, None)
		if hsync:
			self._sync_handles[int(hsync)] = c_cb
			return int(hsync)
		return 0

	def remove_sync(self, hsync):
		if not self.handle or not hsync: return False
		self._sync_handles.pop(int(hsync), None)
		return bool(bass.BASS_ChannelRemoveSync(self.handle, int(hsync)))

	def clear_syncs(self):
		if self.handle:
			for hsync in list(self._sync_handles.keys()):
				try: bass.BASS_ChannelRemoveSync(self.handle, hsync)
				except Exception: pass
		self._sync_handles.clear()

	# --- BASSmix Matrix & Split Streams ---
	def set_matrix(self, matrix):
		"""Set BASSmix channel mixing matrix (2D list of floats or flat list of floats)."""
		if not self.handle or not matrix: return False
		flat = [float(x) for row in matrix for x in (row if isinstance(row, (list, tuple)) else (row,))]
		arr = (ctypes.c_float * len(flat))(*flat)
		return bool(bassmix.BASS_Mixer_ChannelSetMatrix(self.handle, arr))

	def split(self, flags=0, chanmap=None):
		"""Create a BASS_Split_StreamCreate clone from a decode stream."""
		ch = self._get_raw_source_handle()
		if not ch: return None
		cmap = (ctypes.c_int * (len(chanmap) + 1))(*[int(c) for c in chanmap], -1) if chanmap else None
		sp = bassmix.BASS_Split_StreamCreate(ch, int(flags), cmap)
		if not sp: return None
		child = sound()
		child.handle = sp
		child.freq, child.chans = self.freq, self.chans
		child.store_entry = control.register_hstream(sp)
		return child

	def get_data(self, frame_size=None, data_type="raw"):
		# Always read from the processed output handle (self.handle) when HRTF stream or DSP is active!
		ch = self.handle if (self._hrtf_stream or self._hrtf_dsp or not self.dedata) else self.dedata
		if not ch: return None
		if frame_size is None:
			frame_size = self.get_frame_size()
		frame_size = int(frame_size)
		if data_type == "raw":
			buf = (ctypes.c_ubyte * (frame_size * 2))()
			res = bass.BASS_ChannelGetData(ch, buf, frame_size * 2)
			return bytes(buf[:res]) if 0 < res <= len(buf) else None
		b_samp = 4 if "32" in data_type else 2
		tot, buf = frame_size * b_samp, (ctypes.c_ubyte * (frame_size * b_samp))()
		res = bass.BASS_ChannelGetData(ch, buf, tot | (control.BASS_DATA_FLOAT if "32" in data_type else 0))
		if res <= 0 or res == 0xFFFFFFFF: return None
		if data_type == "float32": return ctypes.cast(buf, ctypes.POINTER(ctypes.c_float))[:res // 4]
		if data_type == "int16": return ctypes.cast(buf, ctypes.POINTER(ctypes.c_int16))[:res // 2]
		return bytes(buf[:res])

	def get_length(self):
		ch = self.dedata if self.dedata else self.handle
		if not ch: return -1
		l = bass.BASS_ChannelGetLength(ch, control.BASS_POS_BYTE)
		return -1 if l in (-1, 0xFFFFFFFFFFFFFFFF) else int(bass.BASS_ChannelBytes2Seconds(ch, l) * 1000)

	@property
	def volume(self):
		if not self.handle: return False
		if "volume" in self._fade_state: return self.get_faded_value("volume", self._last_vol or 0.0)
		if self._last_vol is not None: return self._last_vol
		val = ctypes.c_float(0.0)
		bass.BASS_ChannelGetAttribute(self.handle, BASS_ATTRIB_VOL, ctypes.byref(val))
		self._last_vol = val.value * 100.0
		return self._last_vol

	@volume.setter
	def volume(self, value):
		if self.handle:
			v = max(0.0, min(100.0, float(value)))
			if self._last_vol is None or abs(self._last_vol - v) > 0.01:
				self._last_vol = v
				bass.BASS_ChannelSetAttribute(self.handle, BASS_ATTRIB_VOL, ctypes.c_float(v / 100.0))

	@property
	def pitch(self):
		if not self.handle: return False
		if "pitch" in self._fade_state: return self.get_faded_value("pitch", self._last_pitch or 100.0)
		if self._last_pitch is not None: return self._last_pitch
		val = ctypes.c_float(0.0)
		target = self.dedata if (self._hrtf_stream and self.dedata) else self.handle
		bass.BASS_ChannelGetAttribute(target, BASS_ATTRIB_FREQ, ctypes.byref(val))
		self._last_pitch = (val.value / self.freq) * 100.0
		return self._last_pitch

	@pitch.setter
	def pitch(self, value):
		if self.handle:
			p = float(value)
			if self._last_pitch is None or abs(self._last_pitch - p) > 0.01:
				self._last_pitch = p
				bass.BASS_ChannelSetAttribute(self.handle, BASS_ATTRIB_FREQ, ctypes.c_float((p / 100.0) * self.freq))

	@property
	def pan(self):
		if not self.handle: return False
		if "pan" in self._fade_state: return self.get_faded_value("pan", self._last_pan or 0.0)
		if self._last_pan is not None: return self._last_pan
		val = ctypes.c_float(0.0)
		bass.BASS_ChannelGetAttribute(self.handle, BASS_ATTRIB_PAN, ctypes.byref(val))
		self._last_pan = val.value * 100.0
		return self._last_pan

	@pan.setter
	def pan(self, value):
		if self.handle:
			pn = max(-100.0, min(100.0, float(value)))
			if self._last_pan is None or abs(self._last_pan - pn) > 0.01:
				self._last_pan = pn
				bass.BASS_ChannelSetAttribute(self.handle, BASS_ATTRIB_PAN, ctypes.c_float(pn / 100.0))

	@property
	def playing(self):
		if not self.handle: return False
		if bassmix.BASS_Mixer_ChannelGetMixer(self.handle):
			return bass.BASS_ChannelIsActive(self.handle) == BASS_ACTIVE_PLAYING and not (bassmix.BASS_Mixer_ChannelFlags(self.handle, 0, 0) & control.BASS_MIXER_CHAN_PAUSE)
		return bass.BASS_ChannelIsActive(self.handle) == BASS_ACTIVE_PLAYING

	@property
	def is_playing(self): return self.playing

	@property
	def stopped(self): return not self.handle or bass.BASS_ChannelIsActive(self.handle) == BASS_ACTIVE_STOPPED
	@property
	def stalled(self): return bool(self.handle and bass.BASS_ChannelIsActive(self.handle) == BASS_ACTIVE_STALLED)

	@property
	def position(self):
		if not self.handle: return 0
		ch = self.dedata if self.dedata else self.handle
		pos = bassmix.BASS_Mixer_ChannelGetPosition(ch, control.BASS_POS_BYTE) if bassmix.BASS_Mixer_ChannelGetMixer(ch) else bass.BASS_ChannelGetPosition(ch, control.BASS_POS_BYTE)
		return 0 if pos in (-1, 0xFFFFFFFFFFFFFFFF) else int(bass.BASS_ChannelBytes2Seconds(ch, pos) * 1000)

	@position.setter
	def position(self, ms_value):
		if not self.handle: return
		ch = self.dedata if self.dedata else self.handle
		b_target = bass.BASS_ChannelSeconds2Bytes(ch, ctypes.c_double(float(ms_value) / 1000.0))
		if bassmix.BASS_Mixer_ChannelGetMixer(ch): bassmix.BASS_Mixer_ChannelSetPosition(ch, b_target, control.BASS_POS_BYTE)
		else: bass.BASS_ChannelSetPosition(ch, b_target, control.BASS_POS_BYTE)
		if (self._hrtf_stream or self._hrtf_dsp) and _hrtf: _hrtf.BASS_HRTF_Reset(self._get_raw_channel_handle())

	def seek(self, ms_value): self.position = ms_value

	def _compute_rotated_delta(self, lx, ly, lz, sx, sy, sz, rotation=0.0):
		dx, dy, dz = float(sx - lx), float(sy - ly), float(sz - lz)
		if abs(rotation) > 0.001:
			rad = math.radians(rotation)
			c, s = math.cos(rad), math.sin(rad)
			dx, dy = c * dx - s * dy, s * dx + c * dy
		return dx, dy, dz

	def set3d(self, listener_x, listener_y, listener_z, source_x, source_y, source_z,
	          rotation=0, head=180, pan_step=2.5, volume_step=2.5,
	          behind_pitch_decrease=0, behind_volume_decrease=0,
	          pitch_step=1, pitch_range=92, pan_range=70,
	          start_pan=0, start_volume=100, start_pitch=100,
	          soft=False, mix_pan_with_hrtf=False, bilinear=True):
		if "volume" in self._fade_state: start_volume = self.get_faded_value("volume", start_volume)
		if "pitch" in self._fade_state: start_pitch = self.get_faded_value("pitch", start_pitch)
		if "pan" in self._fade_state: start_pan = self.get_faded_value("pan", start_pan)
		if soft or self._hrtf_stream or self._hrtf_dsp:
			return self.set3dsoft(
				listener_x, listener_y, listener_z, source_x, source_y, source_z,
				rotation=rotation, start_pan=start_pan, start_volume=start_volume, start_pitch=start_pitch,
				pan_step=pan_step if mix_pan_with_hrtf else 0.0, volume_step=volume_step,
				behind_pitch_decrease=behind_pitch_decrease, behind_volume_decrease=behind_volume_decrease,
				pitch_step=pitch_step, pitch_range=pitch_range, pan_range=pan_range, bilinear=bilinear
			)
		return self.math3d(
			listener_x, listener_y, listener_z, source_x, source_y, source_z,
			pan_step, volume_step, behind_pitch_decrease, behind_volume_decrease,
			pitch_step, pitch_range, pan_range, start_pan, start_volume, start_pitch,
			soft=False, rotation=rotation
		)

	def set3dsoft(self, listener_x, listener_y, listener_z, source_x, source_y, source_z,
	              rotation=0, start_volume=100, volume_step=2.5, start_pitch=100,
	              start_pan=0, pan_step=0.0, behind_pitch_decrease=0, behind_volume_decrease=0,
	              pitch_step=0, pitch_range=92, pan_range=70, bilinear=True):
		if not self._hrtf_stream and not self._hrtf_dsp:
			self._ensure_hrtf_attached()
		raw = self._get_raw_channel_handle()
		if not raw: return False
		dx, dy, dz = self._compute_rotated_delta(listener_x, listener_y, listener_z, source_x, source_y, source_z, rotation)
		dist = math.sqrt(dx * dx + dy * dy + dz * dz)
		atten = 1.0 if volume_step <= 0 else max(0.0, 1.0 - dist * (float(volume_step) / 100.0))
		hrtf_key = (round(dx, 2), round(dy, 2), round(dz, 2), round(atten, 3), bool(bilinear))
		if self._last_hrtf_args != hrtf_key:
			if not _initialize_hrtf().BASS_HRTF_Set3D(raw, dx, dy, dz, float(atten), 1 if bilinear else 0): return False
			self._last_hrtf_args = hrtf_key
		self._3d = (listener_x, listener_y, listener_z, source_x, source_y, source_z)
		f_vol, f_pan, f_pitch = float(start_volume) + self.user_volume_offset, float(start_pan) + self.user_pan_offset, float(start_pitch) + self.user_pitch_offset
		if pan_step != 0.0: f_pan = max(min(f_pan + dx * float(pan_step), float(pan_range)), -float(pan_range))
		self.pan, self.volume, self.pitch = f_pan, f_vol, f_pitch
		return True

	def math3d(self, listener_x, listener_y, listener_z, source_x, source_y, source_z,
	           pan_step, volume_step, behind_pitch_decrease, behind_volume_decrease,
	           pitch_step, pitch_range, pan_range, start_pan, start_volume, start_pitch,
	           soft=False, rotation=0.0):
		if soft or self._hrtf_stream or self._hrtf_dsp:
			return self.set3dsoft(
				listener_x, listener_y, listener_z, source_x, source_y, source_z,
				rotation=rotation, start_volume=start_volume, volume_step=volume_step,
				start_pitch=start_pitch, start_pan=start_pan,
				behind_pitch_decrease=behind_pitch_decrease, behind_volume_decrease=behind_volume_decrease,
				pitch_step=pitch_step, pitch_range=pitch_range, pan_range=pan_range
			)
		dx, dy, dz = self._compute_rotated_delta(listener_x, listener_y, listener_z, source_x, source_y, source_z, rotation)
		self.pan = max(min(start_pan + self.user_pan_offset + dx * pan_step, pan_range), -pan_range)
		horiz_dist, delta_z = math.sqrt(dx * dx + dy * dy), abs(dz)
		self.volume = max(min((start_volume + self.user_volume_offset) - (horiz_dist + delta_z * 0.5) * volume_step, 100.0), 0.0)
		self.pitch = start_pitch + self.user_pitch_offset
		return True

	@property
	def is_sliding3d(self):
		info = self._slide3d_info
		if not info: return False
		if info.get("mode") == "once" and self._slide3d_start:
			return (time.monotonic() - self._slide3d_start) * 1000.0 < float(info.get("fadetime", 1000))
		return True

	def slide3d(self, *args, **kwargs):
		if len(args) >= 9:
			listener_x, listener_y, listener_z = args[0], args[1], args[2]
			from_x, from_y, from_z = args[3], args[4], args[5]
			to_x, to_y, to_z = args[6], args[7], args[8]
			fadetime = args[9] if len(args) > 9 else kwargs.get("fadetime", 1000)
			mode = args[10] if len(args) > 10 else kwargs.get("mode", "loop")
		elif len(args) >= 6:
			from_x, from_y, from_z = args[0], args[1], args[2]
			to_x, to_y, to_z = args[3], args[4], args[5]
			fadetime = args[6] if len(args) > 6 else kwargs.get("fadetime", 1000)
			mode = args[7] if len(args) > 7 else kwargs.get("mode", "loop")
			listener = kwargs.get("listener")
			if listener and len(listener) >= 3:
				listener_x, listener_y, listener_z = listener[0], listener[1], listener[2]
			elif self._3d and len(self._3d) >= 3:
				listener_x, listener_y, listener_z = self._3d[0], self._3d[1], self._3d[2]
			else:
				listener_x, listener_y, listener_z = 0.0, 0.0, 0.0
		else:
			return (0.0, 0.0, 0.0)
		rotation = kwargs.get("rotation", 0)
		start_pan = kwargs.get("start_pan", 0)
		start_volume = kwargs.get("start_volume", 100)
		start_pitch = kwargs.get("start_pitch", 100)
		pan_step = kwargs.get("pan_step", 2.5)
		volume_step = kwargs.get("volume_step", 2.5)
		behind_pitch_decrease = kwargs.get("behind_pitch_decrease", 0)
		behind_volume_decrease = kwargs.get("behind_volume_decrease", 0)
		pitch_step = kwargs.get("pitch_step", 1)
		pitch_range = kwargs.get("pitch_range", 92)
		pan_range = kwargs.get("pan_range", 70)
		soft = kwargs.get("soft", False)
		mix_pan_with_hrtf = kwargs.get("mix_pan_with_hrtf", False)
		bilinear = kwargs.get("bilinear", True)
		fx, fy, fz = float(from_x), float(from_y), float(from_z)
		tx, ty, tz = float(to_x), float(to_y), float(to_z)
		dur_ms = max(1, int(fadetime or 1000))
		s_mode = str(mode or "loop").lower()
		s_key = (fx, fy, fz, tx, ty, tz, dur_ms, s_mode)
		now = time.monotonic()
		is_new_slide = (self._slide3d_key != s_key)
		if is_new_slide:
			self._slide3d_key = s_key
			self._slide3d_start = now
		el_ms = max(0.0, (now - self._slide3d_start) * 1000.0)
		if s_mode in ("once", "group_event"):
			ratio = min(1.0, el_ms / float(dur_ms))
		elif s_mode == "pingpong":
			cyc = (el_ms / float(dur_ms)) % 2.0
			ratio = cyc if cyc <= 1.0 else (2.0 - cyc)
		else:
			ratio = (el_ms % float(dur_ms)) / float(dur_ms)
		cx = fx + (tx - fx) * ratio
		cy = fy + (ty - fy) * ratio
		cz = fz + (tz - fz) * ratio
		self._slide3d_info = {
			"from": (fx, fy, fz), "to": (tx, ty, tz), "fadetime": dur_ms, "mode": s_mode,
			"pos": (cx, cy, cz), "start_pan": start_pan, "start_volume": start_volume, "start_pitch": start_pitch,
			"pan_step": pan_step, "volume_step": volume_step, "soft": soft
		}
		self.set3d(
			listener_x, listener_y, listener_z, cx, cy, cz,
			rotation=rotation, pan_step=pan_step, volume_step=volume_step,
			behind_pitch_decrease=behind_pitch_decrease, behind_volume_decrease=behind_volume_decrease,
			pitch_step=pitch_step, pitch_range=pitch_range, pan_range=pan_range,
			start_pan=start_pan, start_volume=start_volume, start_pitch=start_pitch,
			soft=soft, mix_pan_with_hrtf=mix_pan_with_hrtf, bilinear=bilinear
		)
		# Native C-level HRTF position slide (smoothly interpolates even for one-shot slide3d without per-frame polling)
		if (soft or self._hrtf_stream or self._hrtf_dsp) and s_mode in ("once", "group_event"):
			rem_ms = max(0.0, float(dur_ms) - el_ms)
			if rem_ms > 0.0 and (is_new_slide or el_ms < float(dur_ms)):
				dx_t, dy_t, dz_t = self._compute_rotated_delta(listener_x, listener_y, listener_z, tx, ty, tz, rotation)
				raw = self._get_raw_channel_handle()
				if raw:
					try:
						_initialize_hrtf().BASS_HRTF_SlidePosition(raw, float(dx_t), float(dy_t), float(dz_t), float(rem_ms))
					except Exception:
						pass
		return (cx, cy, cz)

	def update_slide3d(self, listener_x, listener_y, listener_z, rotation=0):
		info = self._slide3d_info
		if not info: return None
		fx, fy, fz = info["from"]
		tx, ty, tz = info["to"]
		return self.slide3d(
			listener_x, listener_y, listener_z, fx, fy, fz, tx, ty, tz,
			fadetime=info["fadetime"], mode=info["mode"], rotation=rotation,
			start_pan=info.get("start_pan", 0), start_volume=info.get("start_volume", 100),
			start_pitch=info.get("start_pitch", 100), pan_step=info.get("pan_step", 2.5),
			volume_step=info.get("volume_step", 2.5), soft=info.get("soft", False)
		)


class vst(SoundBase):
	def __init__(self):
		super().__init__()
		self.sound_token = utils.token(max=25)
		buffer.hSound_poolbuffers[self.sound_token] = self
		self.handle, self.vst_handle, self._target_channel, self.freq, self.chans = None, None, None, 44100, 2

	def create_instrument(self, dll_path, frequency=44100, channels=2, flags=0, ThreeD=False, decode=False, **kwargs):
		self.close(); self.freq, self.chans, self._is_decode = frequency, channels, bool(decode)
		c_path, u_fl = control.encode_path(dll_path)
		self.vst_handle = pybassvst.BASS_VST_ChannelCreate(frequency, channels, c_path, control.parse_flags(flags | u_fl, ThreeD=ThreeD, decode=decode, **kwargs))
		if not self.vst_handle: return False
		self.handle, self.store_entry = self.vst_handle, control.register_hstream(self.vst_handle)
		if ThreeD: self._ensure_hrtf_attached()
		return True

	def attach_dsp(self, target_sound, dll_path, flags=0, priority=0):
		ch = target_sound._get_raw_channel_handle() if hasattr(target_sound, "_get_raw_channel_handle") else int(target_sound or 0)
		if not ch: return False
		c_path, u_fl = control.encode_path(dll_path)
		h = pybassvst.BASS_VST_ChannelSetDSP(ch, c_path, int(flags) | u_fl, int(priority))
		if h:
			self._target_channel = ch
			self.vst_handle = int(h)
			return True
		return False

	def set_vst_param(self, index, value):
		return bool(self.vst_handle and pybassvst.BASS_VST_SetParam(self.vst_handle, int(index), float(value)))

	def get_vst_param(self, index):
		return float(pybassvst.BASS_VST_GetParam(self.vst_handle, int(index))) if self.vst_handle else 0.0

	def get_vst_param_count(self):
		return int(pybassvst.BASS_VST_GetParamCount(self.vst_handle)) if self.vst_handle else 0

	def set_vst_program(self, index):
		return bool(self.vst_handle and pybassvst.BASS_VST_SetProgram(self.vst_handle, int(index)))

	def get_vst_program(self):
		return int(pybassvst.BASS_VST_GetProgram(self.vst_handle)) if self.vst_handle else 0

	def get_vst_program_count(self):
		return int(pybassvst.BASS_VST_GetProgramCount(self.vst_handle)) if self.vst_handle else 0

	def set_vst_bypass(self, bypass=True):
		return bool(self.vst_handle and pybassvst.BASS_VST_SetBypass(self.vst_handle, 1 if bypass else 0))

	def get_vst_bypass(self):
		return bool(self.vst_handle and pybassvst.BASS_VST_GetBypass(self.vst_handle))

	def play(self):
		if self.handle: bass.BASS_ChannelPlay(self.handle, False)

	def stop(self):
		if self.handle: bass.BASS_ChannelStop(self.handle); bass.BASS_ChannelSetPosition(self.handle, 0, control.BASS_POS_BYTE)

	def close(self):
		try:
			self.clear_syncs()
			self.stop_loudness()
			self.stop_encode()
			self.remove_all_fx()
			self.detach_hrtf_dsp()
			if self.vst_handle and self._target_channel:
				pybassvst.BASS_VST_ChannelRemoveDSP(self._target_channel, self.vst_handle)
				self.vst_handle, self._target_channel = None, None
			elif self.vst_handle:
				pybassvst.BASS_VST_ChannelFree(self.vst_handle); self.vst_handle = None
			if self.handle: bass.BASS_StreamFree(self.handle); self.handle = None
			if self.store_entry: control.unregister_hstream(self.store_entry); self.store_entry = None
			buffer.hSound_poolbuffers.pop(self.sound_token, None)
		except Exception: pass


class mixer(SoundBase):
	# Optional standalone Mixer wrapper for explicit sub-mixing when needed
	def __init__(self, parent=None):
		super().__init__()
		self.sound_token = utils.token(max=25)
		buffer.hSound_poolbuffers[self.sound_token] = self
		self.sources, self.sub_mixers, self.parent_mixer = {}, set(), parent

	def _get_raw_handle(self, obj):
		if obj is None: return 0
		if hasattr(obj, "handle") and obj.handle: obj = obj.handle
		elif hasattr(obj, "channel") and obj.channel: obj = obj.channel
		return int(obj.value if hasattr(obj, "value") else obj)

	def create(self, frequency=44100, channels=2, flags=control.BASS_MIXER_NONSTOP | control.BASS_MIXER_RESUME, ThreeD=False, parent=None, **kwargs):
		self.close(); self.freq, self.chans = frequency, channels
		target_parent = parent if parent is not None else self.parent_mixer
		is_dec = bool(kwargs.get("decode", bool(target_parent)))
		self._is_decode = is_dec
		kwargs.setdefault("decode", is_dec); kwargs.setdefault("float", True)
		self.handle = bassmix.BASS_Mixer_StreamCreate(frequency, channels, control.parse_flags(flags, ThreeD=ThreeD, **kwargs))
		if not self.handle: return False
		self.store_entry = control.register_hstream(self.handle)
		if target_parent: self.set_parent_mixer(target_parent)
		if ThreeD: self.attach_hrtf_dsp()
		return True

	def set_parent_mixer(self, parent_mixer=None):
		if not self.handle: return False
		if self.parent_mixer and self.parent_mixer is not parent_mixer:
			if hasattr(self.parent_mixer, "remove"): self.parent_mixer.remove(self)
			elif hasattr(self.parent_mixer, "remove_mixer"): self.parent_mixer.remove_mixer(self, True)
		self.parent_mixer = parent_mixer
		if parent_mixer and hasattr(parent_mixer, "add"): return parent_mixer.add(self)
		if parent_mixer and hasattr(parent_mixer, "add_channel"): return parent_mixer.add_channel(self.handle)
		return True

	def add(self, source, flags=control.BASS_MIXER_CHAN_NORAMPIN, start=None, length=None, **kwargs):
		if not self.handle: return False
		raw_src = self._get_raw_handle(source)
		if not raw_src: return False
		fl = control.parse_flags(flags, **kwargs)
		res = bassmix.BASS_Mixer_StreamAddChannelEx(self.handle, raw_src, fl, int(start), int(length)) if start is not None and length is not None else bassmix.BASS_Mixer_StreamAddChannel(self.handle, raw_src, fl)
		if bool(res):
			self.sources[raw_src] = source
			if hasattr(source, "parent_mixer"): source.parent_mixer = self
			if isinstance(source, mixer): self.sub_mixers.add(source)
			return True
		return False

	def remove(self, source):
		raw_src = self._get_raw_handle(source)
		self.sources.pop(raw_src, None)
		if isinstance(source, mixer): self.sub_mixers.discard(source)
		return bool(bassmix.BASS_Mixer_ChannelRemove(raw_src))

	def play(self):
		if self.handle:
			if bassmix.BASS_Mixer_ChannelGetMixer(self.handle): bassmix.BASS_Mixer_ChannelFlags(self.handle, 0, control.BASS_MIXER_CHAN_PAUSE)
			else: bass.BASS_ChannelPlay(self.handle, False)

	def stop(self):
		if self.handle:
			if bassmix.BASS_Mixer_ChannelGetMixer(self.handle):
				bassmix.BASS_Mixer_ChannelFlags(self.handle, control.BASS_MIXER_CHAN_PAUSE, control.BASS_MIXER_CHAN_PAUSE)
			else:
				bass.BASS_ChannelStop(self.handle); bass.BASS_ChannelSetPosition(self.handle, 0, control.BASS_POS_BYTE)

	def close(self):
		try:
			self.remove_all_fx()
			self.detach_hrtf_dsp()
			for raw_src in list(self.sources.keys()): bassmix.BASS_Mixer_ChannelRemove(raw_src)
			self.sources.clear(); self.sub_mixers.clear()
			if self.parent_mixer and hasattr(self.parent_mixer, "remove"): self.parent_mixer.remove(self)
			if self.store_entry: control.unregister_hstream(self.store_entry); self.store_entry = None
			if self.handle: bass.BASS_StreamFree(self.handle); self.handle = None
			buffer.hSound_poolbuffers.pop(self.sound_token, None)
		except Exception: pass


_IMA_INDEX_TABLE = (-1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8)
_IMA_STEP_TABLE = (
	7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31,
	34, 37, 41, 45, 50, 55, 60, 66, 73, 80, 88, 97, 107, 118, 130, 143,
	157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449, 494, 544, 598, 658,
	724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066, 2272, 2499, 2749, 3024,
	3327, 3660, 4026, 4428, 4871, 5358, 5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899,
	15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767,
)


def scale_pcm16(pcm_bytes, gain=1.0):
	"""Apply linear gain to signed 16-bit little-endian PCM bytes."""
	g = float(gain)
	if not pcm_bytes or abs(g - 1.0) < 1e-3:
		return bytes(pcm_bytes)
	samples = array.array("h")
	samples.frombytes(pcm_bytes[:len(pcm_bytes) - (len(pcm_bytes) & 1)])
	if g <= 0.0:
		return b"\x00" * (len(samples) * 2)
	for idx in range(len(samples)):
		v = int(samples[idx] * g)
		if v > 32767:
			v = 32767
		elif v < -32768:
			v = -32768
		samples[idx] = v
	return samples.tobytes()


def encode_audio_frame(pcm_bytes):
	"""Encode 16-bit mono PCM bytes into a self-contained 4:1 IMA-ADPCM frame."""
	if not pcm_bytes or len(pcm_bytes) < 2:
		return b""
	samples = array.array("h")
	samples.frombytes(pcm_bytes[:len(pcm_bytes) - (len(pcm_bytes) & 1)])
	n = len(samples)
	if n == 0:
		return b""
	pred = int(samples[0])
	idx = 0
	if n > 1:
		d0 = abs(int(samples[1]) - pred)
		while idx < 88 and _IMA_STEP_TABLE[idx] < d0:
			idx += 1
	out = bytearray(4 + ((n - 1 + 1) // 2))
	struct.pack_into("<hBB", out, 0, pred, idx, (n - 1) & 1)
	step_tbl = _IMA_STEP_TABLE
	idx_tbl = _IMA_INDEX_TABLE
	pos = 4
	high_nib = False
	cur_byte = 0
	for s_i in range(1, n):
		step = step_tbl[idx]
		diff = int(samples[s_i]) - pred
		nib = 0
		if diff < 0:
			nib = 8
			diff = -diff
		vpdiff = step >> 3
		if diff >= step:
			nib |= 4
			diff -= step
			vpdiff += step
		step >>= 1
		if diff >= step:
			nib |= 2
			diff -= step
			vpdiff += step
		step >>= 1
		if diff >= step:
			nib |= 1
			vpdiff += step
		if nib & 8:
			pred -= vpdiff
		else:
			pred += vpdiff
		if pred > 32767:
			pred = 32767
		elif pred < -32768:
			pred = -32768
		idx += idx_tbl[nib]
		if idx < 0:
			idx = 0
		elif idx > 88:
			idx = 88
		if high_nib:
			out[pos] = cur_byte | (nib << 4)
			pos += 1
			high_nib = False
		else:
			cur_byte = nib
			high_nib = True
	if high_nib:
		out[pos] = cur_byte
	return bytes(out)


def decode_audio_frame(encoded_bytes):
	"""Decode a self-contained 4:1 IMA-ADPCM frame back into 16-bit mono PCM bytes."""
	if not encoded_bytes or len(encoded_bytes) < 4:
		return b""
	pred, idx, odd_flag = struct.unpack_from("<hBB", encoded_bytes, 0)
	if idx > 88:
		idx = 88
	data = encoded_bytes[4:]
	total_nibs = len(data) * 2 - (1 if odd_flag else 0)
	samples = array.array("h", [pred])
	step_tbl = _IMA_STEP_TABLE
	idx_tbl = _IMA_INDEX_TABLE
	for n_i in range(total_nibs):
		b = data[n_i >> 1]
		nib = (b >> 4) if (n_i & 1) else (b & 0x0F)
		step = step_tbl[idx]
		vpdiff = step >> 3
		if nib & 4:
			vpdiff += step
		if nib & 2:
			vpdiff += step >> 1
		if nib & 1:
			vpdiff += step >> 2
		if nib & 8:
			pred -= vpdiff
		else:
			pred += vpdiff
		if pred > 32767:
			pred = 32767
		elif pred < -32768:
			pred = -32768
		idx += idx_tbl[nib]
		if idx < 0:
			idx = 0
		elif idx > 88:
			idx = 88
		samples.append(pred)
	return samples.tobytes()


class record(SoundBase):
	def __init__(self):
		super().__init__()
		self.sound_token, self.encoder_token = utils.token(max=25), utils.token(max=25)
		buffer.hrecordthreadbuffers[self.sound_token] = self
		self.encoder, self._sample_data, self._c_proc, self._memory_ref = None, bytearray(), None, None
		self._gain = 1.0
		self._rec_running = False
		self._android_rec = None
		self._android_ns = None
		self._android_aec = None
		self._android_thread = None

	def set_gain(self, gain):
		self._gain = max(0.0, min(4.0, float(gain)))

	def _request_android_mic_perm(self):
		try:
			from java import jclass
			from .pygame_shim import _android_bridge
			act = _android_bridge.get_activity()
			if act is None:
				return False
			perm = "android.permission.RECORD_AUDIO"
			if hasattr(act, "checkSelfPermission") and int(act.checkSelfPermission(perm)) == 0:
				return True
			if hasattr(act, "requestPermissions"):
				act.requestPermissions([perm], 7001)
			return True
		except Exception:
			return False

	def _start_android_noise_suppressed(self, freq, chans, period_ms, callback):
		try:
			from java import jclass, jarray, jbyte
			self._request_android_mic_perm()
			AudioRecord = jclass("android.media.AudioRecord")
			AudioFormat = jclass("android.media.AudioFormat")
			AudioSource = jclass("android.media.MediaRecorder$AudioSource")
			ch_cfg = AudioFormat.CHANNEL_IN_MONO if chans == 1 else AudioFormat.CHANNEL_IN_STEREO
			enc = AudioFormat.ENCODING_PCM_16BIT
			min_buf = int(AudioRecord.getMinBufferSize(int(freq), ch_cfg, enc))
			frame_bytes = max(320, int(freq * chans * 2 * (period_ms / 1000.0)))
			buf_sz = max(min_buf * 2, frame_bytes * 4)
			rec = AudioRecord(AudioSource.VOICE_COMMUNICATION, int(freq), ch_cfg, enc, buf_sz)
			if int(rec.getState()) != int(AudioRecord.STATE_INITIALIZED):
				rec.release()
				return False
			sid = int(rec.getAudioSessionId())
			try:
				NoiseSuppressor = jclass("android.media.audiofx.NoiseSuppressor")
				if NoiseSuppressor.isAvailable():
					ns = NoiseSuppressor.create(sid)
					if ns is not None:
						ns.setEnabled(True)
						self._android_ns = ns
			except Exception:
				pass
			try:
				AEC = jclass("android.media.audiofx.AcousticEchoCanceler")
				if AEC.isAvailable():
					aec = AEC.create(sid)
					if aec is not None:
						aec.setEnabled(True)
						self._android_aec = aec
			except Exception:
				pass
			rec.startRecording()
			self._android_rec = rec
			self._rec_running = True

			def _loop():
				jbuf = jarray(jbyte)(frame_bytes)
				while self._rec_running and self._android_rec is not None:
					try:
						nread = int(rec.read(jbuf, 0, frame_bytes))
						if nread > 0:
							try:
								raw = memoryview(jbuf).cast("B")[:nread].tobytes()
							except Exception:
								raw = bytes(b & 0xFF for b in jbuf[:nread])
							if abs(self._gain - 1.0) >= 1e-3:
								raw = scale_pcm16(raw, self._gain)
							if callable(callback):
								callback(raw)
							else:
								self._sample_data.extend(raw)
					except Exception:
						break

			self._android_thread = threading.Thread(target=_loop, name="PyAGAndroidRecord", daemon=True)
			self._android_thread.start()
			return True
		except Exception:
			return False

	def start(self, freq=24000, chans=1, period_ms=20, callback=None, device=-1, gain=1.0, noise_suppress=False):
		"""Start live microphone recording (16-bit PCM). Pure audio capture via BASS_RecordStart (or Android NoiseSuppressor)."""
		self.stop()
		self.freq, self.chans = int(freq), int(chans)
		self.set_gain(gain)
		is_android = (system.get_platform()["os"] == "android")
		if is_android:
			self._request_android_mic_perm()
			if noise_suppress and self._start_android_noise_suppressed(self.freq, self.chans, int(period_ms), callback):
				return True

		if not bass.BASS_RecordInit(int(device)) and bass.BASS_ErrorGetCode() != 14:
			raise RuntimeError(f"Cannot initialize recording device {device}: BASS error {bass.BASS_ErrorGetCode()}")
		if int(device) != -1:
			try:
				bass.BASS_RecordSetDevice(int(device))
			except Exception:
				pass

		def _rec_cb(handle, buf_ptr, length, user):
			if not self._rec_running:
				return False
			if buf_ptr and length > 0:
				raw = ctypes.string_at(buf_ptr, int(length))
				if abs(self._gain - 1.0) >= 1e-3:
					raw = scale_pcm16(raw, self._gain)
				if callable(callback):
					try:
						callback(raw)
					except Exception:
						pass
				else:
					self._sample_data.extend(raw)
			return True

		self._c_proc = RECORDPROC_TYPE(_rec_cb)
		self._rec_running = True
		rec_flags = (max(5, min(200, int(period_ms))) << 16)
		self.handle = bass.BASS_RecordStart(self.freq, self.chans, rec_flags, self._c_proc, None)
		if not self.handle:
			self._rec_running = False
			self._c_proc = None
			raise RuntimeError(f"Cannot start recording: BASS error {bass.BASS_ErrorGetCode()}")
		return True

	def stream(self, filename, draw=False, mono=False, ThreeD=False, decode=False, autofree=False, use_dsp_hrtf=True, preload=True, frame_size=None, **kwargs):
		if self.handle: self.close()
		buffer.hSound_poolbuffers[self.sound_token] = self
		if frame_size is not None: self._frame_size = max(64, min(2048, int(frame_size)))
		if isinstance(filename, os.PathLike): filename = os.fspath(filename)
		self.filename, self.mono, self._is_decode, self._is_live_push = filename, mono, bool(decode), bool(draw)
		need_hrtf_stream = ThreeD and (not use_dsp_hrtf or (draw and mono))
		source_decode = bool(decode) or need_hrtf_stream
		if ThreeD and not draw:
			kwargs.setdefault("float", True)
		fl = control.parse_flags(0, mono=True if (ThreeD and not use_dsp_hrtf and not draw) else mono, decode=source_decode, autofree=(autofree and not source_decode), **kwargs)
		mem_src = None if draw else control.resolve_memory_source(filename)
		if draw:
			chans = 1 if (mono or need_hrtf_stream) else 2
			self.handle = bass.BASS_StreamCreate(int(self.freq), chans, fl, STREAMPROC_PUSH, None)
		elif mem_src is not None:
			ptr, length, self._memory_ref = mem_src
			self.handle = bass.BASS_StreamCreateFile(True, ptr, 0, length, fl)
		else:
			c_path, u_fl = control.encode_path(filename)
			self.handle = bass.BASS_StreamCreateFile(False, c_path, 0, 0, fl | u_fl | control.BASS_ASYNCFILE)
		if not self.handle and bass.BASS_ErrorGetCode() == 41 and not control.loaded_plugins:
			control.load_codec_plugins()
			if not draw and filename and utils.is_url(filename):
				self.handle = bass.BASS_StreamCreateURL(str(filename).strip().encode("utf-8"), 0, fl | getattr(bass, "BASS_STREAM_STATUS", 0x800000), None, None)
			elif mem_src is not None:
				self.handle = bass.BASS_StreamCreateFile(True, mem_src[0], 0, mem_src[1], fl)
			else:
				c_path, u_fl = control.encode_path(filename)
				self.handle = bass.BASS_StreamCreateFile(False, c_path, 0, 0, fl | u_fl | control.BASS_ASYNCFILE)
		if not self.handle:
			err = bass.BASS_ErrorGetCode(); self.close()
			raise RuntimeError(f"Cannot open stream {filename!r}: BASS error {err}")
		ci = bass.BASS_CHANNELINFO()
		if bass.BASS_ChannelGetInfo(self.handle, ctypes.byref(ci)):
			self.freq, self.chans = ci.freq, ci.chans
		self.store_entry = control.register_hstream(self.handle)
		if ThreeD:
			if need_hrtf_stream or (self.chans == 1 and source_decode):
				self._attach_hrtf(decode=decode)
			elif self.chans == 1 and not source_decode and not draw:
				# Re-open 1-channel file as decode source and wrap in 2-channel stereo HRTF stream
				bass.BASS_StreamFree(self.handle)
				control.unregister_hstream(self.store_entry); self.store_entry = None
				fl_dec = fl | control.BASS_STREAM_DECODE
				if mem_src is not None:
					self.handle = bass.BASS_StreamCreateFile(True, mem_src[0], 0, mem_src[1], fl_dec)
				else:
					c_path, u_fl = control.encode_path(filename)
					self.handle = bass.BASS_StreamCreateFile(False, c_path, 0, 0, fl_dec | u_fl | control.BASS_ASYNCFILE)
				self.store_entry = control.register_hstream(self.handle)
				self._attach_hrtf(decode=decode)
			else:
				self.attach_hrtf_dsp()
		return int(self.get_length())

	def push(self, data):
		target = self.dedata if self.dedata else self.handle
		if not target: return 0
		raw_data = bytes(data)
		res = bass.BASS_StreamPutData(target, raw_data, len(raw_data))
		if res == 0xFFFFFFFF: raise RuntimeError(f"Cannot push stream data: BASS error {bass.BASS_ErrorGetCode()}")
		return res

	def read_pcm(self, num_bytes=960):
		"""Read decoded PCM bytes from a decode=True stream (returns b'' on EOF)."""
		if not self.handle: return b""
		n = max(2, int(num_bytes))
		buf = ctypes.create_string_buffer(n)
		got = bass.BASS_ChannelGetData(self.handle, buf, n)
		if got in (0, 0xFFFFFFFF) or got < 0:
			return b""
		return buf.raw[:int(got)]

	def get_sample(self): return bytes(self._sample_data)
	def clear_sample(self): self._sample_data = bytearray()

	def stop(self):
		self._rec_running = False
		if self._android_rec is not None:
			try:
				self._android_rec.stop()
				self._android_rec.release()
			except Exception:
				pass
			self._android_rec = None
		if self._android_ns is not None:
			try: self._android_ns.release()
			except Exception: pass
			self._android_ns = None
		if self._android_aec is not None:
			try: self._android_aec.release()
			except Exception: pass
			self._android_aec = None
		if self.encoder: pybassenc.BASS_Encode_Stop(self.encoder); self.encoder = None
		if self.handle: bass.BASS_ChannelStop(self.handle); self.handle = None
		if self.dedata: bass.BASS_ChannelStop(self.dedata); self.dedata = None
		self._c_proc = None

	def close(self):
		try:
			self.stop()
			self.remove_all_fx()
			self.detach_hrtf_dsp()
			if self.store_entry: control.unregister_hstream(self.store_entry); self.store_entry = None
			if self.encoder: pybassenc.BASS_Encode_Stop(self.encoder); self.encoder = None
			if self.handle: bass.BASS_StreamFree(self.handle); self.handle = None
			if self.dedata: bass.BASS_StreamFree(self.dedata); self.dedata = None
			self._c_proc, self._memory_ref, self._hrtf_stream = None, None, False
			buffer.hrecordthreadbuffers.pop(self.sound_token, None)
			buffer.hSound_poolbuffers.pop(self.sound_token, None)
		except Exception: pass


class musical(SoundBase):
	def __init__(self):
		super().__init__()
		self.sound_token, self.fonts_storage = utils.token(max=25), []
		buffer.hSound_poolbuffers[self.sound_token] = self

	def load_font(self, font_path, flags=0, **kwargs):
		c_path, u_fl = control.encode_path(system.match(system.embedded_data_path(), "..", font_path))
		f_handle = pybassmidi.BASS_MIDI_FontInit(c_path, control.parse_flags(u_fl, flags=flags, **kwargs))
		if f_handle: pybassmidi.BASS_MIDI_FontLoad(f_handle, -1, -1); self.fonts_storage.append(f_handle)
		return f_handle

	def create_realtime(self, channels=16, flags=0, ThreeD=False, decode=False, use_dsp_hrtf=True, **kwargs):
		if self.handle: self.close()
		self._is_decode = bool(decode)
		source_decode = bool(decode) or (ThreeD and not use_dsp_hrtf)
		self.handle = pybassmidi.BASS_MIDI_StreamCreate(int(channels), control.parse_flags(flags, ThreeD=ThreeD, decode=source_decode, **kwargs), int(self.freq))
		if self.handle:
			self.store_entry = control.register_hstream(self.handle)
			if ThreeD:
				if use_dsp_hrtf: self.attach_hrtf_dsp()
				else: self._attach_hrtf(decode=decode)
			return True
		return False

	def send_event(self, chan, event, param):
		ch = self._get_raw_source_handle() or self._get_raw_channel_handle()
		return bool(ch and pybassmidi.BASS_MIDI_StreamEvent(ch, int(chan), int(event), int(param)))

	def note_on(self, chan, note, velocity=100):
		ev = getattr(pybassmidi, "MIDI_EVENT_NOTE", 1)
		param = (max(0, min(127, int(velocity))) << 8) | (max(0, min(127, int(note))) & 0x7F)
		return self.send_event(chan, ev, param)

	def note_off(self, chan, note):
		return self.note_on(chan, note, 0)

	def stream(self, filename, mono=False, ThreeD=False, decode=False, use_dsp_hrtf=True, **kwargs):
		if self.handle: self.close()
		self._is_decode = bool(decode)
		source_decode = bool(decode) or (ThreeD and not use_dsp_hrtf)
		fl = control.parse_flags(0, mono=False if (ThreeD and use_dsp_hrtf) else mono, ThreeD=ThreeD, decode=source_decode, **kwargs)
		if filename and utils.is_url(filename):
			self._is_url = True
			self.handle = pybassmidi.BASS_MIDI_StreamCreateURL(str(filename).strip().encode("utf-8"), 0, fl, None, None, int(self.freq))
		else:
			c_path, u_fl = control.encode_path(filename)
			self.handle = pybassmidi.BASS_MIDI_StreamCreateFile(False, c_path, 0, 0, fl | u_fl, int(self.freq))
		if self.handle:
			self.store_entry = control.register_hstream(self.handle)
			if ThreeD:
				if use_dsp_hrtf: self.attach_hrtf_dsp()
				else: self._attach_hrtf(decode=decode)
			return int(bass.BASS_ChannelBytes2Seconds(self.dedata or self.handle, bass.BASS_ChannelGetLength(self.dedata or self.handle, control.BASS_POS_BYTE)) * 1000)
		return 0

	def play(self):
		if self.handle: bass.BASS_ChannelPlay(self.handle, False)

	def stop(self):
		if self.handle: bass.BASS_ChannelStop(self.handle); bass.BASS_ChannelSetPosition(self.handle, 0, control.BASS_POS_BYTE)
		if self.dedata: bass.BASS_ChannelStop(self.dedata); bass.BASS_ChannelSetPosition(self.dedata, 0, control.BASS_POS_BYTE)

	def close(self):
		try:
			self.remove_all_fx()
			self.detach_hrtf_dsp()
			if self.store_entry: control.unregister_hstream(self.store_entry); self.store_entry = None
			if self.handle: bass.BASS_StreamFree(self.handle); self.handle = None
			if self.dedata: bass.BASS_StreamFree(self.dedata); self.dedata = None
			for sf in self.fonts_storage: pybassmidi.BASS_MIDI_FontFree(sf)
			self.fonts_storage.clear()
			buffer.hSound_poolbuffers.pop(self.sound_token, None)
		except Exception: pass


class sound(SoundBase):
	def __init__(self):
		super().__init__()
		self.sound_token = utils.token(max=25)
		buffer.hSound_poolbuffers[self.sound_token] = self
		self.preload_ref, self._sample_handle, self._sample_cached, self._memory_ref = None, None, False, None

	def stream(self, filename="", draw=False, mono=False, ThreeD=False, decode=False, autofree=False, use_dsp_hrtf=False, preload=False, frame_size=None, tempo=False, reverse=False, **kwargs):
		# Zero-stutter direct streaming using URL (BASS_StreamCreateURL), zero-copy preload/mmap, BASS_ASYNCFILE, Push Stream, Tempo/Reverse, or HMUSIC fallback
		if self.handle: self.close()
		buffer.hSound_poolbuffers[self.sound_token] = self
		if frame_size is not None:
			self._frame_size = max(64, min(2048, int(frame_size)))
		if isinstance(filename, os.PathLike): filename = os.fspath(filename)
		is_url = (not draw) and bool(filename) and utils.is_url(filename)
		self.filename, self.mono, self._is_decode, self._is_live_push, self._is_url = filename, mono, bool(decode), bool(draw), is_url

		# If draw=True (real-time voice chat push stream) and mono=True, use HRTF Stream Mode so 1-ch push data renders to 2-ch stereo HRTF
		need_hrtf_stream = ThreeD and (not use_dsp_hrtf or (draw and mono))
		need_fx_wrap = bool(tempo) or bool(reverse)
		source_decode = bool(decode) or need_hrtf_stream or need_fx_wrap
		if ThreeD and not draw:
			kwargs.setdefault("float", True)

		fl = control.parse_flags(
			0,
			mono=True if (ThreeD and not use_dsp_hrtf and not draw) else (mono if not (ThreeD and use_dsp_hrtf and not draw) else False),
			decode=source_decode,
			autofree=(autofree and not source_decode),
			**kwargs
		)
		mem_src = None if (draw or is_url) else control.resolve_memory_source(filename)
		if draw:
			chans = 1 if (mono or need_hrtf_stream) else 2
			self.handle = bass.BASS_StreamCreate(int(self.freq), chans, fl, STREAMPROC_PUSH, None)
		elif is_url:
			url_bytes = str(filename).strip().encode("utf-8")
			url_fl = fl | getattr(bass, "BASS_STREAM_STATUS", 0x800000)
			self.handle = bass.BASS_StreamCreateURL(url_bytes, 0, url_fl, None, None)
		elif mem_src is not None:
			ptr, length, self._memory_ref = mem_src
			self.handle = bass.BASS_StreamCreateFile(True, ptr, 0, length, fl)
			if not self.handle and bass.BASS_ErrorGetCode() == 41:
				m_fl = fl | bass.BASS_MUSIC_PRESCAN | bass.BASS_MUSIC_POSRESETEX | bass.BASS_MUSIC_RAMP
				self.handle = bass.BASS_MusicLoad(True, ptr, 0, length, m_fl, int(self.freq))
				if self.handle: self._is_music = True
		else:
			pre = control.preload_encoded(filename) if preload else None
			if pre and pre.ptr and pre.size:
				self.preload_ref, self._memory_ref = pre, (pre.data, pre.c_buf)
				with control.preload_mutex: pre.ref += 1; pre.t = time.monotonic() * 1000.0
				self.handle = bass.BASS_StreamCreateFile(True, pre.ptr, 0, pre.size, fl)
				if not self.handle and bass.BASS_ErrorGetCode() == 41:
					m_fl = fl | bass.BASS_MUSIC_PRESCAN | bass.BASS_MUSIC_POSRESETEX | bass.BASS_MUSIC_RAMP
					self.handle = bass.BASS_MusicLoad(True, pre.ptr, 0, pre.size, m_fl, int(self.freq))
					if self.handle: self._is_music = True
			else:
				c_path, u_fl = control.encode_path(filename)
				self.handle = bass.BASS_StreamCreateFile(False, c_path, 0, 0, fl | u_fl | control.BASS_ASYNCFILE)
				if not self.handle and bass.BASS_ErrorGetCode() == 41:
					m_fl = fl | u_fl | bass.BASS_MUSIC_PRESCAN | bass.BASS_MUSIC_POSRESETEX | bass.BASS_MUSIC_RAMP
					self.handle = bass.BASS_MusicLoad(False, c_path, 0, 0, m_fl, int(self.freq))
					if self.handle: self._is_music = True
		if not self.handle and bass.BASS_ErrorGetCode() == 41 and not control.loaded_plugins:
			control.load_codec_plugins()
			if not draw and filename and utils.is_url(filename):
				self.handle = bass.BASS_StreamCreateURL(str(filename).strip().encode("utf-8"), 0, fl | getattr(bass, "BASS_STREAM_STATUS", 0x800000), None, None)
			elif mem_src is not None:
				self.handle = bass.BASS_StreamCreateFile(True, mem_src[0], 0, mem_src[1], fl)
			else:
				c_path, u_fl = control.encode_path(filename)
				self.handle = bass.BASS_StreamCreateFile(False, c_path, 0, 0, fl | u_fl | control.BASS_ASYNCFILE)
		if not self.handle:
			err = bass.BASS_ErrorGetCode(); self.close()
			raise RuntimeError(f"Cannot open stream {filename!r}: BASS error {err}")
		# Optional BASS_FX Reverse & Tempo wrappers (preserving decode flag for downstream HRTF if needed)
		fx_free_src = getattr(bass_fx, "BASS_FX_FREESOURCE", 0x10000)
		if reverse:
			rev_dec = control.BASS_STREAM_DECODE if (tempo or decode or need_hrtf_stream) else 0
			rev_h = bass_fx.BASS_FX_ReverseCreate(self.handle, 2.0, fx_free_src | rev_dec)
			if not rev_h:
				err = bass.BASS_ErrorGetCode(); self.close()
				raise RuntimeError(f"Cannot create reverse stream: BASS error {err}")
			self.handle = rev_h
			self._reverse_handle = rev_h
		if tempo:
			tmp_dec = control.BASS_STREAM_DECODE if (decode or need_hrtf_stream) else 0
			tmp_h = bass_fx.BASS_FX_TempoCreate(self.handle, fx_free_src | tmp_dec)
			if not tmp_h:
				err = bass.BASS_ErrorGetCode(); self.close()
				raise RuntimeError(f"Cannot create tempo stream: BASS error {err}")
			self.handle = tmp_h
			self._tempo_handle = tmp_h
		ci = bass.BASS_CHANNELINFO()
		if bass.BASS_ChannelGetInfo(self.handle, ctypes.byref(ci)):
			self.freq, self.chans = ci.freq, ci.chans
		self.store_entry = control.register_hstream(self.handle)
		try:
			if ThreeD:
				if use_dsp_hrtf and not need_hrtf_stream:
					# If file is 1-channel mono, wrap via _attach_hrtf so output is 2-channel stereo binaural
					if self.chans == 1 and not draw:
						if not (ci.flags & control.BASS_STREAM_DECODE):
							if self._is_music: bass.BASS_MusicFree(self.handle)
							else: bass.BASS_StreamFree(self.handle)
							control.unregister_hstream(self.store_entry); self.store_entry = None
							fl_dec = fl | control.BASS_STREAM_DECODE
							if mem_src is not None:
								self.handle = bass.BASS_MusicLoad(True, mem_src[0], 0, mem_src[1], fl_dec, int(self.freq)) if self._is_music else bass.BASS_StreamCreateFile(True, mem_src[0], 0, mem_src[1], fl_dec)
							elif self.preload_ref:
								self.handle = bass.BASS_MusicLoad(True, self.preload_ref.ptr, 0, self.preload_ref.size, fl_dec, int(self.freq)) if self._is_music else bass.BASS_StreamCreateFile(True, self.preload_ref.ptr, 0, self.preload_ref.size, fl_dec)
							else:
								c_path, u_fl = control.encode_path(filename)
								self.handle = bass.BASS_MusicLoad(False, c_path, 0, 0, fl_dec | u_fl, int(self.freq)) if self._is_music else bass.BASS_StreamCreateFile(False, c_path, 0, 0, fl_dec | u_fl | control.BASS_ASYNCFILE)
							self.store_entry = control.register_hstream(self.handle)
						self._attach_hrtf(decode=decode)
					else:
						if not self.attach_hrtf_dsp():
							raise RuntimeError(f"Cannot attach HRTF DSP: BASS error {bass.BASS_ErrorGetCode()}")
				else:
					self._attach_hrtf(decode=decode)
		except Exception:
			self.close(); raise
		return int(self.get_length())

	def music(self, filename, mono=False, ThreeD=False, decode=False, autofree=False, use_dsp_hrtf=True, prescan=True, ramp=True, frame_size=None, **kwargs):
		"""Load MOD/XM/IT/S3M/MO3 tracker music (HMUSIC) with full HRTF DSP & Decode Stream compatibility."""
		if self.handle: self.close()
		buffer.hSound_poolbuffers[self.sound_token] = self
		if frame_size is not None:
			self._frame_size = max(64, min(2048, int(frame_size)))
		if isinstance(filename, os.PathLike): filename = os.fspath(filename)
		self.filename, self.mono, self._is_decode, self._is_music = filename, mono, bool(decode), True
		source_decode = bool(decode) or (ThreeD and not use_dsp_hrtf)
		if ThreeD: kwargs.setdefault("float", True)
		base_fl = (bass.BASS_MUSIC_PRESCAN if prescan else 0) | (bass.BASS_MUSIC_RAMP if ramp else 0) | bass.BASS_MUSIC_POSRESETEX
		fl = control.parse_flags(
			base_fl,
			mono=True if (ThreeD and not use_dsp_hrtf) else (False if ThreeD else mono),
			decode=source_decode,
			autofree=(autofree and not source_decode),
			**kwargs
		)
		mem_src = control.resolve_memory_source(filename)
		if mem_src is not None:
			ptr, length, self._memory_ref = mem_src
			self.handle = bass.BASS_MusicLoad(True, ptr, 0, length, fl, int(self.freq))
		else:
			c_path, u_fl = control.encode_path(filename)
			self.handle = bass.BASS_MusicLoad(False, c_path, 0, 0, fl | u_fl, int(self.freq))
		if not self.handle:
			err = bass.BASS_ErrorGetCode(); self.close()
			raise RuntimeError(f"Cannot load HMUSIC {filename!r}: BASS error {err}")
		ci = bass.BASS_CHANNELINFO()
		if bass.BASS_ChannelGetInfo(self.handle, ctypes.byref(ci)):
			self.freq, self.chans = ci.freq, ci.chans
		self.store_entry = control.register_hstream(self.handle)
		if ThreeD:
			if use_dsp_hrtf and self.chans == 2:
				if not self.attach_hrtf_dsp():
					raise RuntimeError(f"Cannot attach HRTF DSP to HMUSIC: BASS error {bass.BASS_ErrorGetCode()}")
			else:
				self._attach_hrtf(decode=decode)
		return int(self.get_length())

	def load(self, filename="", mono=False, ThreeD=False, decode=False, use_dsp_hrtf=True, frame_size=None, **kwargs):
		# Load sample via control.get_cached_sample (using BASS_SAMCHAN_STREAM) with native HSAMPLE + HRTF support
		if self.handle: self.close()
		buffer.hSound_poolbuffers[self.sound_token] = self
		if frame_size is not None:
			self._frame_size = max(64, min(2048, int(frame_size)))
		if isinstance(filename, os.PathLike): filename = os.fspath(filename)
		self.filename, self.mono, self._is_decode = filename, mono, bool(decode)
		if ThreeD: kwargs.setdefault("float", True)
		fl = control.parse_flags(0, mono=mono, **kwargs)
		need_decode_chan = bool(decode) or (ThreeD and not use_dsp_hrtf)
		ch_flags = control.BASS_SAMCHAN_STREAM | (control.BASS_STREAM_DECODE if need_decode_chan else 0)
		smp, ch, keep_ref, is_cached = control.get_cached_sample(filename, flags=fl, max_chans=64, chan_flags=ch_flags)
		if not ch:
			# Fallback to stream if file is a tracker music or uncacheable stream format
			self.stream(filename, mono=mono, ThreeD=ThreeD, decode=decode, use_dsp_hrtf=use_dsp_hrtf, frame_size=frame_size, **kwargs)
			return True
		self._sample_handle, self.handle, self._memory_ref, self._sample_cached = (smp if smp else None), ch, keep_ref, is_cached
		ci = bass.BASS_CHANNELINFO()
		if bass.BASS_ChannelGetInfo(self.handle, ctypes.byref(ci)):
			self.freq, self.chans = ci.freq, ci.chans
		self.store_entry = control.register_hstream(self.handle)
		if ThreeD:
			if use_dsp_hrtf and self.chans == 2 and not need_decode_chan:
				if not self.attach_hrtf_dsp():
					self._attach_hrtf(decode=decode)
			else:
				if not (ci.flags & control.BASS_STREAM_DECODE) and self._sample_handle:
					 dec_ch = bass.BASS_SampleGetChannel(self._sample_handle, control.BASS_SAMCHAN_STREAM | control.BASS_STREAM_DECODE)
					 if dec_ch:
						 bass.BASS_StreamFree(self.handle)
						 control.unregister_hstream(self.store_entry)
						 self.handle = dec_ch
						 self.store_entry = control.register_hstream(self.handle)
				self._attach_hrtf(decode=decode)
		return True

	def play(self, reset_loop=True):
		if not self.handle: return False
		target = self.dedata if self.dedata else self.handle
		if reset_loop:
			bass.BASS_ChannelFlags(target, 0, control.BASS_SAMPLE_LOOP)
			if self.dedata: bass.BASS_ChannelFlags(self.handle, 0, control.BASS_SAMPLE_LOOP)
		if bass.BASS_ChannelIsActive(self.handle) != BASS_ACTIVE_PLAYING and self.dedata and not self._is_live_push:
			bass.BASS_ChannelSetPosition(self.dedata, 0, control.BASS_POS_BYTE)
		self.paused = False
		if bassmix.BASS_Mixer_ChannelGetMixer(self.handle):
			if bass.BASS_ChannelIsActive(self.handle) != BASS_ACTIVE_PLAYING and not self._is_live_push:
				bassmix.BASS_Mixer_ChannelSetPosition(self.handle, 0, control.BASS_POS_BYTE)
			bassmix.BASS_Mixer_ChannelFlags(self.handle, 0, control.BASS_MIXER_CHAN_PAUSE)
			return True
		return bool(control.bass_call(bass.BASS_ChannelPlay, self.handle, False, check_error=True))

	def play_looped(self):
		# Apply BASS_SAMPLE_LOOP to both underlying decode source and wrapper handle
		if not self.handle: return False
		target = self.dedata if self.dedata else self.handle
		bass.BASS_ChannelFlags(target, control.BASS_SAMPLE_LOOP, control.BASS_SAMPLE_LOOP)
		if self.dedata: bass.BASS_ChannelFlags(self.handle, control.BASS_SAMPLE_LOOP, control.BASS_SAMPLE_LOOP)
		return self.play(reset_loop=False)

	def stop(self):
		if self.handle:
			if bassmix.BASS_Mixer_ChannelGetMixer(self.handle):
				bassmix.BASS_Mixer_ChannelFlags(self.handle, control.BASS_MIXER_CHAN_PAUSE, control.BASS_MIXER_CHAN_PAUSE)
				bassmix.BASS_Mixer_ChannelSetPosition(self.handle, 0, control.BASS_POS_BYTE)
			else:
				bass.BASS_ChannelStop(self.handle); bass.BASS_ChannelSetPosition(self.handle, 0, control.BASS_POS_BYTE)
		if self.dedata: bass.BASS_ChannelStop(self.dedata); bass.BASS_ChannelSetPosition(self.dedata, 0, control.BASS_POS_BYTE)
		if (self._hrtf_stream or self._hrtf_dsp) and _hrtf: _hrtf.BASS_HRTF_Reset(self._get_raw_channel_handle())

	def _free_channel_handle(self, ch):
		if not ch: return
		if self._is_music:
			if not bass.BASS_MusicFree(ch): bass.BASS_StreamFree(ch)
		else:
			bass.BASS_StreamFree(ch)

	def close(self):
		# Safe single-pass resource cleanup preventing double-free crashes
		self.clear_syncs()
		self.stop_loudness()
		self.stop_encode()
		if self._pitch_shift_fx and self.handle:
			try: bass.BASS_ChannelRemoveFX(self.handle, self._pitch_shift_fx)
			except Exception: pass
		self._pitch_shift_fx = None
		self.remove_all_fx()
		self.detach_hrtf_dsp()
		if self.store_entry: control.unregister_hstream(self.store_entry); self.store_entry = None
		if self.parent_mixer: self.set_mixer(None)
		if self._sample_handle:
			if self.handle:
				bass.BASS_ChannelStop(self.handle)
				bass.BASS_StreamFree(self.handle)
			if self.dedata and self.dedata != self.handle:
				bass.BASS_ChannelStop(self.dedata)
				bass.BASS_StreamFree(self.dedata)
			if not self._sample_cached: bass.BASS_SampleFree(self._sample_handle)
			else: control.release_sample(self._sample_handle)
		else:
			if self.handle:
				if self._hrtf_stream: bass.BASS_StreamFree(self.handle)
				else: self._free_channel_handle(self.handle)
			if self.dedata and self.dedata != self.handle:
				self._free_channel_handle(self.dedata)
		if self.preload_ref: control.sound_preload_release(self.preload_ref); self.preload_ref = None
		control.sound_preloads_clean()
		self.handle, self.dedata, self._sample_handle, self._memory_ref = None, None, None, None
		self._tempo_handle, self._reverse_handle = None, None
		self._sample_cached, self._hrtf_stream, self._is_music, self._is_decode, self._is_live_push, self._is_url, self.paused = False, False, False, False, False, False, False
		self._last_vol, self._last_pan, self._last_pitch, self._last_tempo, self._last_tone, self._last_hrtf_args = None, None, None, 100.0, 100.0, None
		self._fade_state.clear(); self._slide3d_key, self._slide3d_info = None, None
		self.active_fx_handles.clear(); self.active_steam_fx.clear(); self._fx_param_cache.clear()
		buffer.hSound_poolbuffers.pop(self.sound_token, None)

	def push(self, data):
		target = self.dedata if self.dedata else self.handle
		if not target: return 0
		raw_data = bytes(data)
		res = bass.BASS_StreamPutData(target, raw_data, len(raw_data))
		if res == 0xFFFFFFFF: raise RuntimeError(f"Cannot push stream data: BASS error {bass.BASS_ErrorGetCode()}")
		return res

	def read_pcm(self, num_bytes=960):
		"""Read decoded PCM bytes from a decode=True stream (returns b'' on EOF)."""
		if not self.handle: return b""
		n = max(2, int(num_bytes))
		buf = ctypes.create_string_buffer(n)
		got = bass.BASS_ChannelGetData(self.handle, buf, n)
		if got in (0, 0xFFFFFFFF) or got < 0:
			return b""
		return buf.raw[:int(got)]


class music(sound):
	"""Dedicated HMUSIC wrapper class for tracker music (.mod, .xm, .it, .s3m, .mo3) with HRTF & FX."""
	def load(self, filename="", mono=False, ThreeD=False, decode=False, use_dsp_hrtf=True, **kwargs):
		return self.music(filename, mono=mono, ThreeD=ThreeD, decode=decode, use_dsp_hrtf=use_dsp_hrtf, **kwargs)

	def stream(self, filename="", mono=False, ThreeD=False, decode=False, use_dsp_hrtf=True, **kwargs):
		return self.music(filename, mono=mono, ThreeD=ThreeD, decode=decode, use_dsp_hrtf=use_dsp_hrtf, **kwargs)


def clean_oneshots(force=False):
	# Reclaim finished one-shot channels to prevent handle and RAM leaks
	for i in range(len(_oneshot_pool) - 1, -1, -1):
		s = _oneshot_pool[i]
		if force or s.stopped: s.close(); _oneshot_pool.pop(i)

def playsingle(filename, volume=100, pitch=100, pan=0, mono=False, ThreeD=False, **kwargs):
	if not filename: return None
	if len(_oneshot_pool) > 32: clean_oneshots()
	s = sound()
	s.load(filename, mono=mono, ThreeD=ThreeD, **kwargs)
	s.volume, s.pitch, s.pan = volume, pitch, pan
	s.play(); _oneshot_pool.append(s)
	return s


class WasapiManager:
	"""Windows WASAPI low-latency output & loopback capture wrapper (pybasswasapi)."""
	@staticmethod
	def devices():
		if not control._IS_WIN: return []
		res, idx = [], 0
		info = pybasswasapi.BASS_WASAPI_DEVICEINFO()
		while pybasswasapi.BASS_WASAPI_GetDeviceInfo(idx, ctypes.byref(info)):
			if info.flags & getattr(pybasswasapi, "BASS_DEVICE_ENABLED", 1):
				res.append({
					"index": idx,
					"name": (info.name or b"").decode("mbcs", errors="replace").strip(),
					"id": (info.id or b"").decode("mbcs", errors="replace"),
					"flags": int(info.flags),
					"is_input": bool(info.flags & getattr(pybasswasapi, "BASS_DEVICE_INPUT", 16)),
					"is_loopback": bool(info.flags & getattr(pybasswasapi, "BASS_DEVICE_LOOPBACK", 8)),
					"freq": int(info.mixfreq),
					"chans": int(info.mixchans),
				})
			idx += 1
		return res

	@staticmethod
	def init(device=-1, freq=0, chans=0, flags=0, buffer_sec=0.05, period_sec=0.0, proc=None, user=None):
		if not control._IS_WIN: return False
		return bool(pybasswasapi.BASS_WASAPI_Init(int(device), int(freq), int(chans), int(flags), float(buffer_sec), float(period_sec), proc, user))

	@staticmethod
	def start(): return bool(control._IS_WIN and pybasswasapi.BASS_WASAPI_Start())

	@staticmethod
	def stop(reset=False): return bool(control._IS_WIN and pybasswasapi.BASS_WASAPI_Stop(1 if reset else 0))

	@staticmethod
	def free(): return bool(control._IS_WIN and pybasswasapi.BASS_WASAPI_Free())

	@staticmethod
	def get_volume(mode=0): return float(pybasswasapi.BASS_WASAPI_GetVolume(int(mode))) if control._IS_WIN else 0.0

	@staticmethod
	def set_volume(volume, mode=0): return bool(control._IS_WIN and pybasswasapi.BASS_WASAPI_SetVolume(int(mode), float(volume)))

	@staticmethod
	def set_mute(mute=True, mode=0): return bool(control._IS_WIN and pybasswasapi.BASS_WASAPI_SetMute(int(mode), 1 if mute else 0))
