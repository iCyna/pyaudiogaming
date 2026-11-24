# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# Core provider protocol and shared BASS PCM AudioPipeline for g2access.
# Supports Windows, Linux, macOS, Android, and iOS.

from collections import OrderedDict, deque
import ctypes
import os
import platform
import struct
import threading
from .. import system


def load_native_lib(name32, name64=None):
	"""Load a native screen-reader shared library by architecture without console spam."""
	is_64 = platform.architecture()[0] == "64bit"
	target = (name64 or name32) if is_64 else name32
	base = os.path.splitext(target)[0]
	try:
		p = system.get_path(base)
		if p and os.path.isfile(p):
			return ctypes.WinDLL(p) if os.name == "nt" else ctypes.CDLL(p)
	except Exception:
		pass
	return None


def pcm_to_wav(pcm_bytes, sample_rate=22050, channels=1, bits=16):
	"""Wrap raw PCM bytes with a standard 44-byte RIFF/WAVE header."""
	n = len(pcm_bytes)
	block_align = channels * (bits // 8)
	byte_rate = sample_rate * block_align
	return struct.pack(
		"<4sI4s4sIHHIIHH4sI",
		b"RIFF", 36 + n, b"WAVE", b"fmt ", 16, 1,
		channels, sample_rate, byte_rate, block_align, bits, b"data", n
	) + pcm_bytes


class AudioPipeline:
	"""Shared zero-duplication BASS PCM playback, LRU cache, and 3D/HRTF/FX engine."""
	__slots__ = (
		"_lock", "_cond", "_queue", "_gen", "_cache", "_cache_max",
		"_sound", "_mem_seq", "_active_mem_key", "_fallback_active", "_worker", "_synth_fn", "_fallback_fn", "_stop_fallback_fn",
		"volume", "pan", "sound_pitch", "output_device",
		"mono", "hrtf", "fx", "zone_fx_provider", "auto_pause",
	)

	def __init__(self, synth_fn, fallback_fn=None, stop_fallback_fn=None, cache_max=64):
		self._lock = threading.RLock()
		self._cond = threading.Condition(self._lock)
		self._queue = deque()
		self._gen = 0
		self._cache = OrderedDict()
		self._cache_max = int(cache_max)
		self._sound = None
		self._mem_seq = 0
		self._active_mem_key = None
		self._fallback_active = False
		self._synth_fn = synth_fn
		self._fallback_fn = fallback_fn
		self._stop_fallback_fn = stop_fallback_fn
		self.volume = 100.0
		self.pan = 0.0
		self.sound_pitch = 100.0
		self.output_device = -1
		self.mono = False
		self.hrtf = False
		self.fx = None
		self.zone_fx_provider = None
		self.auto_pause = False
		self._worker = threading.Thread(target=self._loop, name="G2AccessAudio", daemon=True)
		self._worker.start()

	def clear_cache(self):
		with self._lock:
			self._cache.clear()

	def _resolve_fx(self):
		if self.fx == "zone":
			if callable(self.zone_fx_provider):
				try:
					return self.zone_fx_provider()
				except Exception:
					return None
			return None
		return self.fx

	def enqueue(self, text, cache_key, interrupt=True, spatial=None):
		if not text:
			return
		with self._cond:
			if interrupt:
				self._gen += 1
				self._queue.clear()
				self._stop_current_unlocked()
			self._queue.append((self._gen, text, cache_key, spatial, bool(interrupt)))
			self._cond.notify()

	def stop(self):
		with self._cond:
			self._gen += 1
			self._queue.clear()
			self._stop_current_unlocked()

	def _stop_current_unlocked(self, from_worker=False):
		if self._sound is not None:
			try:
				self._sound.stop()
				self._sound.close()
			except Exception:
				pass
			self._sound = None
		# Never block the main UI/game thread on COM/JNI IPC unless fallback was actually active
		if from_worker and self._fallback_active and callable(self._stop_fallback_fn):
			self._fallback_active = False
			try:
				self._stop_fallback_fn()
			except Exception:
				pass

	def get_sound(self):
		with self._lock:
			return self._sound

	def _play_wav(self, wav_bytes, spatial=None):
		from .. import buffer
		from ..sound_pool import sound as SoundCls, is_hrtf_ready, prewarm_hrtf_async
		from ..sound_modules import control as snd_ctrl, pybass as bass
		if not snd_ctrl.sound_initialized:
			return False
		with self._lock:
			self._mem_seq += 1
			mem_key = f"__g2access_mem_{id(self)}_{self._mem_seq}"
		snd_ctrl.save_mem_buffer(mem_key, wav_bytes, target="hstream")
		s = SoundCls()
		buffer.hSound_poolbuffers.pop(s.sound_token, None)
		# Match reference accessible_output2: 3D HRTF only applies to spatial (say3d) utterances when hrtf is enabled
		want_3d = bool(self.hrtf and spatial is not None)
		if want_3d and not is_hrtf_ready():
			prewarm_hrtf_async(delay=0.0)
			use_3d = False
		else:
			use_3d = want_3d
		s.stream(mem_key, mono=bool(self.mono or use_3d), ThreeD=use_3d)
		buffer.hSound_poolbuffers.pop(s.sound_token, None)
		if not getattr(s, "handle", 0):
			try:
				snd_ctrl.free_mem_buffer(mem_key)
			except Exception:
				pass
			return False
		if self.output_device is not None and int(self.output_device) >= 0 and s.handle:
			try:
				bass.BASS_ChannelSetDevice(s.handle, int(self.output_device))
			except Exception:
				pass
		vol = max(0.0, min(100.0, float(self.volume)))
		pan = max(-100.0, min(100.0, float(self.pan)))
		pitch = float(self.sound_pitch)
		spatial_fx = None
		if spatial is not None:
			lx, ly, lz, sx, sy, sz, kw = spatial
			kw_clean = dict(kw) if kw else {}
			spatial_fx = kw_clean.pop("fx", None)
			kw_clean.setdefault("start_volume", vol)
			kw_clean.setdefault("start_pan", pan)
			kw_clean.setdefault("start_pitch", pitch)
			_VALID_SET3D = {
				"rotation", "head", "pan_step", "volume_step",
				"behind_pitch_decrease", "behind_volume_decrease",
				"pitch_step", "pitch_range", "pan_range",
				"start_pan", "start_volume", "start_pitch",
				"soft", "mix_pan_with_hrtf", "bilinear",
			}
			set3d_kw = {k: v for k, v in kw_clean.items() if k in _VALID_SET3D}
			if use_3d:
				s.set_hrtf_enabled(True)
			s.set3d(lx, ly, lz, sx, sy, sz, **set3d_kw)
		else:
			s.volume = vol
			s.pan = pan
			if abs(pitch - 100.0) > 0.01:
				s.pitch = pitch
		fx_name = spatial_fx if spatial_fx is not None else self._resolve_fx()
		if fx_name:
			try:
				s.setfx(fx_name)
			except Exception:
				pass
		old_key = None
		with self._lock:
			old_key = self._active_mem_key
			self._stop_current_unlocked()
			self._sound = s
			self._active_mem_key = mem_key
		if old_key and old_key != mem_key:
			try:
				snd_ctrl.free_mem_buffer(old_key)
			except Exception:
				pass
		s.play()
		return True

	def _wait_current_finished(self, gen):
		import time
		while True:
			with self._lock:
				if gen != self._gen:
					return False
				snd = self._sound
			if snd is None:
				return True
			try:
				if not snd.playing:
					return True
			except Exception:
				return True
			time.sleep(0.015)

	def _loop(self):
		while True:
			with self._cond:
				while not self._queue:
					self._cond.wait()
				gen, text, cache_key, spatial, interrupt = self._queue.popleft()
				if gen != self._gen:
					continue
				wav = self._cache.get(cache_key)
				if wav is not None:
					self._cache.move_to_end(cache_key)
			if interrupt and self._fallback_active and callable(self._stop_fallback_fn):
				self._fallback_active = False
				try:
					self._stop_fallback_fn()
				except Exception:
					pass
			if not interrupt:
				if not self._wait_current_finished(gen):
					continue
			if wav is None:
				try:
					wav = self._synth_fn(text)
				except Exception:
					wav = None
				if not wav:
					if callable(self._fallback_fn):
						try:
							self._fallback_active = True
							self._fallback_fn(text, interrupt)
						except Exception:
							pass
					continue
				with self._lock:
					if gen != self._gen:
						continue
					self._cache[cache_key] = wav
					if len(self._cache) > self._cache_max:
						self._cache.popitem(last=False)
			with self._lock:
				if gen != self._gen:
					continue
			played = False
			try:
				played = bool(self._play_wav(wav, spatial=spatial))
			except Exception:
				played = False
			if not played and callable(self._fallback_fn):
				try:
					self._fallback_active = True
					self._fallback_fn(text, interrupt)
				except Exception:
					pass


class Provider:
	"""Minimal capability-driven base class for all g2access speech/braille drivers."""
	name = "base"
	priority = 50
	is_system_output = False
	capabilities = {
		"has_rate": False, "min_rate": 0, "max_rate": 100,
		"has_pitch": False, "min_pitch": 0, "max_pitch": 100,
		"has_volume": False, "min_volume": 0, "max_volume": 100,
		"has_voice": False, "has_pan": False, "min_pan": -100, "max_pan": 100,
		"has_output_device": False, "has_mono": False, "has_hrtf": False,
		"has_fx": False, "has_engine": False, "has_voice_language": False,
		"has_system_default": False,
	}

	def is_active(self): return False
	def speak(self, text, interrupt=False): pass
	def braille(self, text): pass
	def silence(self): pass
	def speak3d(self, text, lx, ly, lz, sx, sy, sz, interrupt=False, **kwargs):
		return self.speak(text, interrupt=interrupt)

	def get_capabilities(self): return dict(self.capabilities)
	def get_sound(self): return None
	def list_voices(self): return []
	def list_engines(self): return []
	def list_voice_languages(self): return []
	def get_rate(self): return None
	def set_rate(self, value): return False
	def get_pitch(self): return None
	def set_pitch(self, value): return False
	def get_volume(self): return None
	def set_volume(self, value): return False
	def get_voice(self): return None
	def set_voice(self, value): return False
	def get_pan(self): return 0.0
	def set_pan(self, value): return False
	def get_sound_pitch(self): return 100.0
	def set_sound_pitch(self, value): return False
	def get_output_device(self): return -1
	def set_output_device(self, value): return False
	def get_mono(self): return False
	def set_mono(self, value): return False
	def get_hrtf(self): return False
	def set_hrtf(self, value): return False
	def get_fx(self): return None
	def set_fx(self, value): return False
	def set_zone_fx_provider(self, provider): return False
	def get_auto_pause(self): return False
	def set_auto_pause(self, enabled): return False
	def get_engine(self): return None
	def set_engine(self, value): return False
	def get_voice_language(self): return None
	def set_voice_language(self, value): return False
	def get_use_system_default(self): return False
	def set_use_system_default(self, value): return False
