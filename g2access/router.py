# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# High-performance OS-filtered speech/braille Router with active-driver caching.
# Supports Windows, Linux, macOS, Android, and iOS.

import time
from .. import system
from .core import Provider


class Router:
	"""Lightweight speech/braille router selecting the best active driver per OS."""
	_PROBE_TTL = 0.35

	def __init__(self):
		self._os = system.get_platform()["os"]
		self._providers = self._load_os_providers()
		self._by_name = {}
		for p in self._providers:
			self._by_name[p.name.lower()] = p
			self._by_name[p.__class__.__name__.lower()] = p
			for al in getattr(p, "aliases", ()):
				self._by_name[str(al).lower()] = p
		self._forced = None
		self._cached_active = None
		self._cached_ts = 0.0

	def _load_os_providers(self):
		if self._os == "windows":
			from .windows import create_providers
			items = create_providers()
		elif self._os == "android":
			from .android import create_providers
			items = create_providers()
		elif self._os == "ios":
			from .ios import create_providers
			items = create_providers()
		elif self._os == "macos":
			from .macos import create_providers
			items = create_providers()
		elif self._os == "linux":
			from .linux import create_providers
			items = create_providers()
		else:
			items = []
		items.sort(key=lambda p: (p.is_system_output, p.priority))
		return items

	def _pick(self, force_refresh=False):
		if self._forced is not None:
			return self._forced
		now = time.monotonic()
		if not force_refresh and self._cached_active is not None and (now - self._cached_ts) < self._PROBE_TTL:
			return self._cached_active
		chosen = None
		for p in self._providers:
			try:
				if p.is_active():
					chosen = p
					break
			except Exception:
				continue
		self._cached_active = chosen
		self._cached_ts = now
		return chosen

	def output(self, text, interrupt=False):
		p = self._pick()
		if p is not None:
			p.speak(text, interrupt=interrupt)
			p.braille(text)

	def speak(self, text, interrupt=False):
		p = self._pick()
		if p is not None:
			p.speak(text, interrupt=interrupt)

	def braille(self, text):
		p = self._pick()
		if p is not None:
			p.braille(text)

	def silence(self):
		p = self._pick()
		if p is not None:
			p.silence()

	def speak3d(self, text, lx, ly, lz, sx, sy, sz, interrupt=False, **kwargs):
		p = self._pick()
		if p is not None:
			p.speak3d(text, lx, ly, lz, sx, sy, sz, interrupt=interrupt, **kwargs)

	def get_outputs(self, active_only=False):
		if not active_only:
			return [p.name for p in self._providers]
		return [p.name for p in self._providers if p.is_active()]

	def get_output(self):
		return self._forced.name if self._forced is not None else "auto"

	def get_active_output(self):
		p = self._pick(force_refresh=True)
		return p.name if p is not None else None

	def set_output(self, name=None):
		prev = self._forced or self._cached_active
		if not name or str(name).strip().lower() == "auto":
			if prev is not None:
				try: prev.silence()
				except Exception: pass
			self._forced = None
			self._cached_active = None
			return True
		key = str(name).strip().lower()
		target = self._by_name.get(key)
		if target is None:
			return False
		if prev is not None and prev is not target:
			try: prev.silence()
			except Exception: pass
		self._forced = target
		return True

	def get_capabilities(self):
		p = self._pick(force_refresh=True)
		return p.get_capabilities() if p is not None else dict(Provider.capabilities)

	def list_fx(self):
		try:
			from ..sound_fx import Basic
			b = Basic()
			return sorted(set(b.fxs.keys()) | set(b.filters.keys()) | set(b.steam_fxs.keys()))
		except Exception:
			return []

	def _call(self, method, *args, default=None):
		p = self._pick()
		if p is None:
			return default
		fn = getattr(p, method, None)
		return fn(*args) if callable(fn) else default

	def get_sound(self): return self._call("get_sound")
	def get_volume(self): return self._call("get_volume")
	def set_volume(self, v): return self._call("set_volume", v, default=False)
	def get_pitch(self): return self._call("get_pitch")
	def set_pitch(self, v): return self._call("set_pitch", v, default=False)
	def get_rate(self): return self._call("get_rate")
	def set_rate(self, v): return self._call("set_rate", v, default=False)
	def get_voice(self): return self._call("get_voice")
	def set_voice(self, v): return self._call("set_voice", v, default=False)
	def get_pan(self): return self._call("get_pan", default=0.0)
	def set_pan(self, v): return self._call("set_pan", v, default=False)
	def get_sound_pitch(self): return self._call("get_sound_pitch", default=100.0)
	def set_sound_pitch(self, v): return self._call("set_sound_pitch", v, default=False)
	def get_output_device(self): return self._call("get_output_device", default=-1)
	def set_output_device(self, v): return self._call("set_output_device", v, default=False)
	def get_mono(self): return self._call("get_mono", default=False)
	def set_mono(self, v): return self._call("set_mono", v, default=False)
	def get_hrtf(self): return self._call("get_hrtf", default=False)
	def set_hrtf(self, v): return self._call("set_hrtf", v, default=False)
	def get_fx(self): return self._call("get_fx")
	def set_fx(self, v): return self._call("set_fx", v, default=False)
	def set_zone_fx_provider(self, provider):
		for p in self._providers:
			try: p.set_zone_fx_provider(provider)
			except Exception: pass
		return True
	def get_auto_pause(self): return self._call("get_auto_pause", default=False)
	def set_auto_pause(self, v): return self._call("set_auto_pause", v, default=False)
	def list_voices(self): return self._call("list_voices", default=[])
	def list_engines(self): return self._call("list_engines", default=[])
	def get_engine(self): return self._call("get_engine")
	def set_engine(self, v): return self._call("set_engine", v, default=False)
	def list_voice_languages(self): return self._call("list_voice_languages", default=[])
	def get_voice_language(self): return self._call("get_voice_language")
	def set_voice_language(self, v): return self._call("set_voice_language", v, default=False)
	def get_use_system_default(self): return self._call("get_use_system_default", default=False)
	def set_use_system_default(self, v): return self._call("set_use_system_default", v, default=False)


Auto = Router
