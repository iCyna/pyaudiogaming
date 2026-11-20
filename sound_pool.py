# -*- coding: utf-8 -*-
# Sound system multifunctional
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.

import math, os, time, ctypes, importlib
from .sound_modules import control, pybass as bass, pybassmix as bassmix, pybass_fx as bass_fx
from . import system, utils, buffer
from .sound_fx import *

class _OptionalAddon:
	# Lazy loader for optional BASS addons
	def __init__(self, name): self.name = name
	def __getattr__(self, attr): return getattr(importlib.import_module(".sound_modules." + self.name, __package__), attr)

pybassvst, pybassmidi, pybassenc = _OptionalAddon("pybassvst"), _OptionalAddon("pybassmidi"), _OptionalAddon("pybassenc")
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

def _initialize_hrtf(sample_rate=None, frame_size=None):
	# Initialize native HRTF addon on demand
	global _hrtf, _hrtf_sample_rate, _hrtf_frame_size
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
	if ThreeD or hrtf: _initialize_hrtf(sample_rate, frame_size=frame_size)
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
		self._is_decode, self._is_live_push, self._is_music, self._frame_size = False, False, False, None
		self._pitch_shift_fx, self._tone_semitones, self._hrtf_stream, self._hrtf_dsp, self._3d = None, 0.0, False, 0, None
		self.user_volume_offset, self.user_pan_offset, self.user_pitch_offset = 0.0, 0.0, 0.0
		self._last_vol, self._last_pan, self._last_pitch, self._last_hrtf_args = None, None, None, None
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
			else:
				cur_v, v = target_v, target_v
			if ft_ms > 0:
				if nt in self._fade_state: cur_v = self.get_faded_value(nt, cur_v)
				self._fade_state[nt] = (float(cur_v), float(target_v), time.monotonic(), ft_ms / 1000.0)
				bass.BASS_ChannelSlideAttribute(self.handle, attr, ctypes.c_float(v), ft_ms)
			else:
				self._fade_state.pop(nt, None)
				bass.BASS_ChannelSetAttribute(self.handle, attr, ctypes.c_float(v))

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
		if self._slide3d_key != s_key:
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

	def play(self):
		if self.handle: bass.BASS_ChannelPlay(self.handle, False)

	def stop(self):
		if self.handle: bass.BASS_ChannelStop(self.handle); bass.BASS_ChannelSetPosition(self.handle, 0, control.BASS_POS_BYTE)

	def close(self):
		try:
			self.remove_all_fx()
			self.detach_hrtf_dsp()
			if self.vst_handle: pybassvst.BASS_VST_ChannelFree(self.vst_handle); self.vst_handle = None
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


class record(SoundBase):
	def __init__(self):
		super().__init__()
		self.sound_token, self.encoder_token = utils.token(max=25), utils.token(max=25)
		buffer.hrecordthreadbuffers[self.sound_token] = self
		self.encoder, self._sample_data, self._c_proc, self._memory_ref = None, bytearray(), None, None

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

	def get_sample(self): return bytes(self._sample_data)
	def clear_sample(self): self._sample_data = bytearray()

	def stop(self):
		if self.encoder: pybassenc.BASS_Encode_Stop(self.encoder); self.encoder = None
		if self.handle: bass.BASS_ChannelStop(self.handle); self.handle = None
		if self.dedata: bass.BASS_ChannelStop(self.dedata); self.dedata = None
		self._c_proc = None

	def close(self):
		try:
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

	def stream(self, filename, mono=False, ThreeD=False, decode=False, use_dsp_hrtf=True, **kwargs):
		if self.handle: self.close()
		self._is_decode = bool(decode)
		source_decode = bool(decode) or (ThreeD and not use_dsp_hrtf)
		c_path, u_fl = control.encode_path(filename)
		self.handle = pybassmidi.BASS_MIDI_StreamCreateFile(False, c_path, 0, 0, control.parse_flags(u_fl, mono=False if (ThreeD and use_dsp_hrtf) else mono, ThreeD=ThreeD, decode=source_decode, **kwargs), int(self.freq))
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

	def stream(self, filename="", draw=False, mono=False, ThreeD=False, decode=False, autofree=False, use_dsp_hrtf=False, preload=False, frame_size=None, **kwargs):
		# Zero-stutter direct streaming using zero-copy preload/mmap, BASS_ASYNCFILE, Push Stream, or HMUSIC fallback
		if self.handle: self.close()
		buffer.hSound_poolbuffers[self.sound_token] = self
		if frame_size is not None:
			self._frame_size = max(64, min(2048, int(frame_size)))
		if isinstance(filename, os.PathLike): filename = os.fspath(filename)
		self.filename, self.mono, self._is_decode, self._is_live_push = filename, mono, bool(decode), bool(draw)

		# If draw=True (real-time voice chat push stream) and mono=True, use HRTF Stream Mode so 1-ch push data renders to 2-ch stereo HRTF
		need_hrtf_stream = ThreeD and (not use_dsp_hrtf or (draw and mono))
		source_decode = bool(decode) or need_hrtf_stream
		if ThreeD and not draw:
			kwargs.setdefault("float", True)

		fl = control.parse_flags(
			0,
			mono=True if (ThreeD and not use_dsp_hrtf and not draw) else (mono if not (ThreeD and use_dsp_hrtf and not draw) else False),
			decode=source_decode,
			autofree=(autofree and not source_decode),
			**kwargs
		)
		mem_src = None if draw else control.resolve_memory_source(filename)
		if draw:
			chans = 1 if (mono or need_hrtf_stream) else 2
			self.handle = bass.BASS_StreamCreate(int(self.freq), chans, fl, STREAMPROC_PUSH, None)
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
		if not self.handle:
			err = bass.BASS_ErrorGetCode(); self.close()
			raise RuntimeError(f"Cannot open stream {filename!r}: BASS error {err}")
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
		self._sample_cached, self._hrtf_stream, self._is_music, self._is_decode, self._is_live_push, self.paused = False, False, False, False, False, False
		self._last_vol, self._last_pan, self._last_pitch, self._last_hrtf_args = None, None, None, None
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
