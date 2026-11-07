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
_hrtf, _hrtf_sample_rate, _oneshot_pool = None, None, []
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

def _initialize_hrtf(sample_rate=None):
	# Initialize native HRTF addon on demand
	global _hrtf, _hrtf_sample_rate
	if _hrtf is None:
		from .sound_modules import pybass_hrtf
		_hrtf = pybass_hrtf
	if sample_rate is None: sample_rate = getattr(buffer.hAudiobuffers.get("output"), "frequency", 44100)
	if _hrtf_sample_rate is None:
		if not _hrtf.BASS_HRTF_InitEx(int(sample_rate), os.fsencode(system.get_path("bass")), os.fsencode(system.get_path("phonon")), None, 0x040500):
			raise RuntimeError("BASS_HRTF_Init failed; check bass_hrtf and phonon libraries")
		_hrtf_sample_rate = int(sample_rate)
	elif int(sample_rate) != _hrtf_sample_rate:
		raise RuntimeError("HRTF already initialized with a different sample rate")
	return _hrtf

def set_hrtf_distance_model(min_dist=1.0, max_dist=50.0, rolloff=0.12, blend_step=0.25):
	_initialize_hrtf().BASS_HRTF_SetDistanceModel(float(min_dist), float(max_dist), float(rolloff), float(blend_step))

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
			else:
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


def output(period=10, bbuffer=500, ThreeD=False, sample_rate=44100, dev=-1, **kwargs):
	hrtf = kwargs.pop("hrtf", False)
	out = OutputManager(device=dev, frequency=sample_rate, period=period, bbuffer=bbuffer, **kwargs)
	buffer.hAudiobuffers["output"], buffer.hfxbuffers["basic"] = out, Basic()
	set_focus(_focused)
	if ThreeD or hrtf: _initialize_hrtf(sample_rate)
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
	# Base class for all sound, mixer, musical, record, and VST objects
	def __init__(self):
		self.handle, self.dedata, self.parent_mixer, self.store_entry = None, None, None, None
		self.active_fx_handles, self.mono, self.freq, self.paused = {}, False, 44100, False
		self._pitch_shift_fx, self._tone_semitones, self._hrtf_stream, self._hrtf_dsp, self._3d = None, 0.0, False, 0, None
		self.user_volume_offset, self.user_pan_offset, self.user_pitch_offset = 0.0, 0.0, 0.0
		self._last_vol, self._last_pan, self._last_pitch = None, None, None

	@property
	def channel(self): return self.handle

	def _get_raw_channel_handle(self):
		if not self.handle: return 0
		raw = getattr(self.handle, "handle", self.handle)
		try: return int(raw.value if hasattr(raw, "value") else raw)
		except Exception: return 0

	def _resolve_attr(self, attr): return ATTR_MAP.get(attr, attr) if isinstance(attr, str) else int(attr)

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

	def attach_hrtf_dsp(self, priority=0):
		# Attach HRTF DSP directly to channel without intermediate sub-mixer latency
		if self._hrtf_stream or self._hrtf_dsp: return True
		raw = self._get_raw_channel_handle()
		if not raw: return False
		dsp = _initialize_hrtf().BASS_HRTF_AttachDSP(raw, int(priority))
		if dsp: self._hrtf_dsp = dsp; return True
		return False

	def detach_hrtf_dsp(self):
		if not self._hrtf_dsp: return False
		raw = self._get_raw_channel_handle()
		if _hrtf and raw: _hrtf.BASS_HRTF_DetachDSP(raw)
		self._hrtf_dsp = 0; return True

	def set_hrtf_enabled(self, enabled=True):
		raw = self._get_raw_channel_handle()
		return bool(raw and _hrtf and _hrtf.BASS_HRTF_SetEnabled(raw, 1 if enabled else 0))

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
		if self.handle and self.playing:
			t = type.lower() if isinstance(type, str) else "volume"
			attr = self._resolve_attr(t)
			if t in ("volume", "vol"):
				v = max(0.0, min(100.0, float(value))) / 100.0
			elif t == "pan":
				v = max(-100.0, min(100.0, float(value))) / 100.0
			elif t in ("pitch", "frequency", "freq"):
				v = (float(value) / 100.0) * float(self.freq)
			else:
				v = float(value)
			bass.BASS_ChannelSlideAttribute(self.handle, attr, ctypes.c_float(v), int(max(0, fadetime)))

	def fadeout(self, fadetime, value=0, type="volume"):
		if self.handle and self.playing:
			v = float(value) / 100.0 if type in ("volume", "vol", "pan") and abs(value) > 1.0 else float(value)
			return self.fade(fadetime, value, type=type)

	def fadein(self, fadetime, value=100, type="volume"):
		if self.handle and self.playing:
			return self.fade(fadetime, value, type=type)

	def setfx(self, fx_key, priority=0):
		if not self.handle: return False
		fx_engine = buffer.hfxbuffers.get("basic") or Basic()
		target = fx_engine.fxs.get(fx_key) or fx_engine.filters.get(fx_key)
		if not target: return False
		if fx_key in self.active_fx_handles:
			try: bass.BASS_ChannelRemoveFX(self.handle, self.active_fx_handles[fx_key])
			except Exception: pass
		fx_alloc = bass.BASS_ChannelSetFX(self.handle, target["name"], priority)
		if not fx_alloc: return False
		params = target["param"]()
		bass.BASS_FXSetParameters(fx_alloc, ctypes.byref(params) if hasattr(params, "_fields_") else params)
		self.active_fx_handles[fx_key] = fx_alloc
		return True

	def remove_all_fx(self):
		if not self.handle: return
		for fx_h in list(self.active_fx_handles.values()):
			try: bass.BASS_ChannelRemoveFX(self.handle, fx_h)
			except Exception: pass
		self.active_fx_handles.clear()

	def get_data(self, frame_size=512, data_type="raw"):
		ch = self.dedata if self.dedata else self.handle
		if not ch: return None
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
		val = ctypes.c_float(0.0)
		bass.BASS_ChannelGetAttribute(self.handle, BASS_ATTRIB_VOL, ctypes.byref(val))
		return val.value * 100.0

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
		val = ctypes.c_float(0.0)
		bass.BASS_ChannelGetAttribute(self.handle, BASS_ATTRIB_FREQ, ctypes.byref(val))
		return (val.value / self.freq) * 100.0

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
		val = ctypes.c_float(0.0)
		bass.BASS_ChannelGetAttribute(self.handle, BASS_ATTRIB_PAN, ctypes.byref(val))
		return val.value * 100.0

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
			if not self.attach_hrtf_dsp() and hasattr(self, "_attach_hrtf"): self._attach_hrtf()
		raw = self._get_raw_channel_handle()
		if not raw: return False
		dx, dy, dz = self._compute_rotated_delta(listener_x, listener_y, listener_z, source_x, source_y, source_z, rotation)
		dist = math.sqrt(dx * dx + dy * dy + dz * dz)
		atten = 1.0 if volume_step <= 0 else max(0.0, 1.0 - dist * (float(volume_step) / 100.0))
		if not _initialize_hrtf().BASS_HRTF_Set3D(raw, dx, dy, dz, float(atten), 1 if bilinear else 0): return False
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


class vst(SoundBase):
	def __init__(self):
		super().__init__()
		self.sound_token = utils.token(max=25)
		buffer.hSound_poolbuffers[self.sound_token] = self
		self.handle, self.vst_handle, self._target_channel, self.freq, self.chans = None, None, None, 44100, 2

	def create_instrument(self, dll_path, frequency=44100, channels=2, flags=0, ThreeD=False, **kwargs):
		self.close(); self.freq, self.chans = frequency, channels
		c_path, u_fl = control.encode_path(dll_path)
		self.vst_handle = pybassvst.BASS_VST_ChannelCreate(frequency, channels, c_path, control.parse_flags(flags | u_fl, ThreeD=ThreeD, **kwargs))
		if not self.vst_handle: return False
		self.handle, self.store_entry = self.vst_handle, control.register_hstream(self.vst_handle)
		if ThreeD: self.attach_hrtf_dsp()
		return True

	def play(self):
		if self.handle: bass.BASS_ChannelPlay(self.handle, False)

	def stop(self):
		if self.handle: bass.BASS_ChannelStop(self.handle); bass.BASS_ChannelSetPosition(self.handle, 0, control.BASS_POS_BYTE)

	def close(self):
		try:
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
		kwargs.setdefault("decode", bool(target_parent)); kwargs.setdefault("float", True)
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

	def stream(self, filename, draw=False, mono=False, ThreeD=False, decode=False, autofree=False, use_dsp_hrtf=True, preload=True, **kwargs):
		if self.handle: self.close()
		buffer.hSound_poolbuffers[self.sound_token] = self
		if isinstance(filename, os.PathLike): filename = os.fspath(filename)
		self.filename, self.mono, source_decode = filename, mono, decode or (ThreeD and not use_dsp_hrtf)
		if ThreeD: kwargs["float"] = True
		fl = control.parse_flags(0, mono=True if (ThreeD and not use_dsp_hrtf) else mono, decode=source_decode, autofree=(autofree and not source_decode), **kwargs)
		mem_src = None if draw else control.resolve_memory_source(filename)
		if draw: self.handle = bass.BASS_StreamCreate(int(self.freq), 1 if mono or (ThreeD and not use_dsp_hrtf) else 2, fl, STREAMPROC_PUSH, None)
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
		if bass.BASS_ChannelGetInfo(self.handle, ctypes.byref(ci)): self.freq = ci.freq
		self.store_entry = control.register_hstream(self.handle)
		if ThreeD:
			if use_dsp_hrtf or not hasattr(self, "_attach_hrtf"): self.attach_hrtf_dsp()
			else: self._attach_hrtf()
		return int(self.get_length())

	def get_sample(self): return bytes(self._sample_data)
	def clear_sample(self): self._sample_data = bytearray()

	def stop(self):
		if self.encoder: pybassenc.BASS_Encode_Stop(self.encoder); self.encoder = None
		if self.handle: bass.BASS_ChannelStop(self.handle); self.handle = None
		self._c_proc = None

	def close(self):
		try:
			self.stop(); self._memory_ref = None
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

	def stream(self, filename, mono=False, ThreeD=False, **kwargs):
		if self.handle: self.close()
		c_path, u_fl = control.encode_path(filename)
		self.handle = pybassmidi.BASS_MIDI_StreamCreateFile(False, c_path, 0, 0, control.parse_flags(u_fl, mono=False if ThreeD else mono, ThreeD=ThreeD, **kwargs), int(self.freq))
		if self.handle:
			self.store_entry = control.register_hstream(self.handle)
			if ThreeD: self.attach_hrtf_dsp()
			return int(bass.BASS_ChannelBytes2Seconds(self.handle, bass.BASS_ChannelGetLength(self.handle, control.BASS_POS_BYTE)) * 1000)
		return 0

	def play(self):
		if self.handle: bass.BASS_ChannelPlay(self.handle, False)

	def stop(self):
		if self.handle: bass.BASS_ChannelStop(self.handle); bass.BASS_ChannelSetPosition(self.handle, 0, control.BASS_POS_BYTE)

	def close(self):
		try:
			self.detach_hrtf_dsp()
			if self.store_entry: control.unregister_hstream(self.store_entry); self.store_entry = None
			if self.handle: bass.BASS_StreamFree(self.handle); self.handle = None
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

	def stream(self, filename, draw=False, mono=False, ThreeD=False, decode=False, autofree=False, use_dsp_hrtf=False, preload=True, **kwargs):
		# Zero-stutter direct streaming using zero-copy preload/mmap or BASS_ASYNCFILE
		if self.handle: self.close()
		buffer.hSound_poolbuffers[self.sound_token] = self
		if isinstance(filename, os.PathLike): filename = os.fspath(filename)
		self.filename, self.mono, source_decode = filename, mono, decode or (ThreeD and not use_dsp_hrtf)
		if ThreeD: kwargs["float"] = True
		fl = control.parse_flags(0, mono=True if (ThreeD and not use_dsp_hrtf) else mono, decode=source_decode, autofree=(autofree and not source_decode), **kwargs)
		mem_src = None if draw else control.resolve_memory_source(filename)
		if draw:
			self.handle = bass.BASS_StreamCreate(int(self.freq), 1 if mono or (ThreeD and not use_dsp_hrtf) else 2, fl, STREAMPROC_PUSH, None)
		elif mem_src is not None:
			ptr, length, self._memory_ref = mem_src
			self.handle = bass.BASS_StreamCreateFile(True, ptr, 0, length, fl)
		else:
			pre = control.preload_encoded(filename) if preload else None
			if pre and pre.ptr and pre.size:
				self.preload_ref, self._memory_ref = pre, (pre.data, pre.c_buf)
				with control.preload_mutex: pre.ref += 1; pre.t = time.monotonic() * 1000.0
				self.handle = bass.BASS_StreamCreateFile(True, pre.ptr, 0, pre.size, fl)
			else:
				c_path, u_fl = control.encode_path(filename)
				self.handle = bass.BASS_StreamCreateFile(False, c_path, 0, 0, fl | u_fl | control.BASS_ASYNCFILE)
		if not self.handle:
			err = bass.BASS_ErrorGetCode(); self.close()
			raise RuntimeError(f"Cannot open stream {filename!r}: BASS error {err}")
		ci = bass.BASS_CHANNELINFO()
		if bass.BASS_ChannelGetInfo(self.handle, ctypes.byref(ci)): self.freq = ci.freq
		self.store_entry = control.register_hstream(self.handle)
		try:
			if ThreeD:
				if use_dsp_hrtf:
					if not self.attach_hrtf_dsp(): raise RuntimeError(f"Cannot attach HRTF DSP: BASS error {bass.BASS_ErrorGetCode()}")
				else: self._attach_hrtf()
		except Exception:
			self.close(); raise
		return int(self.get_length())

	def load(self, filename="", mono=False, ThreeD=False, **kwargs):
		if ThreeD:
			self.stream(filename, mono=mono, ThreeD=True, **kwargs)
			return True
		# Load sample via control.get_cached_sample for O(1) channel spawning
		if self.handle: self.close()
		buffer.hSound_poolbuffers[self.sound_token] = self
		if isinstance(filename, os.PathLike): filename = os.fspath(filename)
		fl = control.parse_flags(0, mono=mono, **kwargs)
		smp, ch, keep_ref, is_cached = control.get_cached_sample(filename, flags=fl, max_chans=64)
		self._sample_handle, self.handle, self._memory_ref, self._sample_cached = (smp if smp else None), ch, keep_ref, is_cached
		if not self.handle: raise RuntimeError(f"Cannot load sample {filename!r}: BASS error {bass.BASS_ErrorGetCode()}")
		ci = bass.BASS_CHANNELINFO()
		if bass.BASS_ChannelGetInfo(self.handle, ctypes.byref(ci)): self.freq = ci.freq
		self.store_entry = control.register_hstream(self.handle)
		return True

	def _attach_hrtf(self):
		rendered = _initialize_hrtf().BASS_HRTF_StreamCreate(self.handle, 0)
		if rendered:
			control.unregister_hstream(self.store_entry)
			self.dedata, self.handle, self._hrtf_stream = self.handle, rendered, True
			self.store_entry = control.register_hstream(self.handle)
		else:
			raise RuntimeError(f"Cannot create HRTF stream: BASS error {bass.BASS_ErrorGetCode()}")

	def play(self, reset_loop=True):
		if not self.handle: return False
		target = self.dedata if self.dedata else self.handle
		if reset_loop:
			bass.BASS_ChannelFlags(target, 0, control.BASS_SAMPLE_LOOP)
			if self.dedata: bass.BASS_ChannelFlags(self.handle, 0, control.BASS_SAMPLE_LOOP)
		if bass.BASS_ChannelIsActive(self.handle) != BASS_ACTIVE_PLAYING and self.dedata:
			bass.BASS_ChannelSetPosition(self.dedata, 0, control.BASS_POS_BYTE)
		self.paused = False
		if bassmix.BASS_Mixer_ChannelGetMixer(self.handle):
			if bass.BASS_ChannelIsActive(self.handle) != BASS_ACTIVE_PLAYING:
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

	def close(self):
		# Safe single-pass resource cleanup preventing double-free crashes
		self.detach_hrtf_dsp()
		if self.store_entry: control.unregister_hstream(self.store_entry); self.store_entry = None
		if self.parent_mixer: self.set_mixer(None)
		if self._sample_handle:
			if not self._sample_cached: bass.BASS_SampleFree(self._sample_handle)
			elif self.handle:
				bass.BASS_ChannelStop(self.handle); control.release_sample(self._sample_handle)
		elif self.handle:
			bass.BASS_StreamFree(self.handle)
		if self.dedata and self.dedata != self.handle: bass.BASS_StreamFree(self.dedata)
		if self.preload_ref: control.sound_preload_release(self.preload_ref); self.preload_ref = None
		control.sound_preloads_clean()
		self.handle, self.dedata, self._sample_handle, self._memory_ref = None, None, None, None
		self._sample_cached, self._hrtf_stream, self.paused = False, False, False
		self._last_vol, self._last_pan, self._last_pitch = None, None, None
		self.active_fx_handles.clear()
		buffer.hSound_poolbuffers.pop(self.sound_token, None)

	def push(self, data):
		target = self.dedata if self.dedata else self.handle
		if not target: return 0
		raw_data = bytes(data)
		res = bass.BASS_StreamPutData(target, raw_data, len(raw_data))
		if res == 0xFFFFFFFF: raise RuntimeError(f"Cannot push stream data: BASS error {bass.BASS_ErrorGetCode()}")
		return res


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