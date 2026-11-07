# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# Core BASS controller, cross-platform zero-copy preload, HSAMPLE cache & direct stream manager.

import os, sys, time, mmap, struct, ctypes, threading
from .. import system, buffer as global_buffer
from . import pybass as bass, pybassmix as bassmix, pybass_fx as bass_fx

# Fallback constants for BASS / BASSmix / BASS_FX
BASS_CONFIG_UPDATEPERIOD = getattr(bass, 'BASS_CONFIG_UPDATEPERIOD', 1)
BASS_CONFIG_BUFFER = getattr(bass, 'BASS_CONFIG_BUFFER', 0)
BASS_CONFIG_FLOATDSP = getattr(bass, 'BASS_CONFIG_FLOATDSP', 11)
BASS_CONFIG_UPDATETHREADS = getattr(bass, 'BASS_CONFIG_UPDATETHREADS', 24)
BASS_CONFIG_ASYNCFILE_BUFFER = getattr(bass, 'BASS_CONFIG_ASYNCFILE_BUFFER', 45)
BASS_CONFIG_DEV_DEFAULT = getattr(bass, 'BASS_CONFIG_DEV_DEFAULT', 36)
BASS_CONFIG_DEV_PERIOD = getattr(bass, 'BASS_CONFIG_DEV_PERIOD', 53)
BASS_CONFIG_MIXER_BUFFER = getattr(bassmix, 'BASS_CONFIG_MIXER_BUFFER', 0x10601)
BASS_ATTRIB_BUFFER = getattr(bass, 'BASS_ATTRIB_BUFFER', 13)
BASS_ATTRIB_GRANULE = getattr(bass, 'BASS_ATTRIB_GRANULE', 14)
BASS_UNICODE = getattr(bass, 'BASS_UNICODE', 0x80000000)
BASS_SAMPLE_FLOAT = getattr(bass, 'BASS_SAMPLE_FLOAT', 0x100)
BASS_SAMPLE_MONO = getattr(bass, 'BASS_SAMPLE_MONO', 2)
BASS_SAMPLE_LOOP = getattr(bass, 'BASS_SAMPLE_LOOP', 4)
BASS_SAMPLE_3D = getattr(bass, 'BASS_SAMPLE_3D', 8)
BASS_SAMPLE_OVER_POS = getattr(bass, 'BASS_SAMPLE_OVER_POS', 0x20000)
BASS_STREAM_DECODE = getattr(bass, 'BASS_STREAM_DECODE', 0x200000)
BASS_STREAM_AUTOFREE = getattr(bass, 'BASS_STREAM_AUTOFREE', 0x40000)
BASS_STREAM_PRESCAN = getattr(bass, 'BASS_STREAM_PRESCAN', 0x20000)
BASS_ASYNCFILE = getattr(bass, 'BASS_ASYNCFILE', 0x40000000)
BASS_MIXER_NONSTOP = getattr(bassmix, 'BASS_MIXER_NONSTOP', 0x20000)
BASS_MIXER_RESUME = getattr(bassmix, 'BASS_MIXER_RESUME', 0x1000)
BASS_MIXER_CHAN_NORAMPIN = getattr(bassmix, 'BASS_MIXER_CHAN_NORAMPIN', 0x800000)
BASS_MIXER_CHAN_PAUSE, BASS_MIXER_PAUSE = 0x2000, 0x2000
BASS_DATA_FLOAT = getattr(bass, 'BASS_DATA_FLOAT', 0x40000000)
BASS_DATA_AVAILABLE = getattr(bass, 'BASS_DATA_AVAILABLE', 0)
BASS_POS_BYTE = getattr(bass, 'BASS_POS_BYTE', 0)

# Global states, limits & caches
PCM_LIMIT, CACHE_LIMIT, SYNC_PRELOAD_LIMIT, MMAP_LIMIT = 100 * 1024 * 1024, 256 * 1024 * 1024, 2 * 1024 * 1024, 128 * 1024 * 1024
sound_initialized, master_output, default_mixer, last_channel, _clean_counter = False, None, None, None, 0
preload_mutex = threading.RLock()
sound_preloads, encoded_preloads, mem_buffers, ptr_lookup, sample_cache, _path_cache = {}, {}, {}, {}, {}, {}
_IS_WIN = (os.name == "nt" or sys.platform.startswith("win"))

FLAG_MAP = {
	"mono": BASS_SAMPLE_MONO, "loop": BASS_SAMPLE_LOOP, "native_3d": BASS_SAMPLE_3D,
	"float": BASS_SAMPLE_FLOAT, "decode": BASS_STREAM_DECODE, "autofree": BASS_STREAM_AUTOFREE,
	"prescan": BASS_STREAM_PRESCAN, "asyncfile": BASS_ASYNCFILE, "unicode": BASS_UNICODE,
	"nonstop": BASS_MIXER_NONSTOP, "resume": BASS_MIXER_RESUME, "norampin": BASS_MIXER_CHAN_NORAMPIN,
	"pause": BASS_MIXER_CHAN_PAUSE, "fx_freSource": getattr(bass_fx, 'BASS_FX_FREESOURCE', 0x10000)
}

ERROR_MAP = {
	0: "OK", 1: "MEM", 2: "FILEOPEN", 3: "DRIVER", 4: "BUFLOST", 5: "HANDLE",
	6: "FORMAT", 7: "POSITION", 8: "INIT", 9: "START", 14: "ALREADY", 18: "NOCHAN",
	19: "ILLTYPE", 20: "ILLPARAM", 21: "NO3D", 22: "NOEAX", 23: "DEVICE", 24: "NOPLAY",
	25: "FREQ", 27: "NOTFILE", 29: "NOHW", 31: "EMPTY", 32: "NONET", 33: "CREATE",
	34: "NOFX", 37: "NOTAVAIL", 38: "DECODE", 39: "DX", 40: "TIMEOUT", 41: "FILEFORM",
	42: "SPEAKER", 43: "VERSION", 44: "CODEC", 45: "ENDED", 46: "BUSY", -1: "UNKNOWN"
}

def parse_flags(base_flags=0, **kwargs):
	# Resolve boolean kwargs into BASS bitmask flags
	flags = int(base_flags) | int(kwargs.get("flags", 0))
	for k, v in kwargs.items():
		if k in FLAG_MAP and v: flags |= FLAG_MAP[k]
	return flags

def bass_call(func, *args, check_error=False, default=0):
	# Centralized BASS C-call wrapper
	res = func(*args)
	if check_error and not res:
		err = bass.BASS_ErrorGetCode()
		raise RuntimeError(f"BASS Error [{err} - {ERROR_MAP.get(err, 'ERR')}] in {getattr(func, '__name__', type(func).__name__)}")
	return res if res is not None else default

def encode_path(path):
	# Cross-platform path encoding (UTF-16LE on Windows, UTF-8 bytes on Linux/macOS/Android)
	if isinstance(path, bytes): return path, 0
	if _IS_WIN: return ctypes.create_unicode_buffer(os.fspath(path)), BASS_UNICODE
	return os.fsencode(os.fspath(path)), 0

class HStreamEntry:
	# Doubly-linked list node for tracking active channels
	__slots__ = ("p", "n", "channel")
	def __init__(self, ch, p=None): self.channel, self.p, self.n = int(ch), p, None

def register_hstream(channel):
	global last_channel
	if not channel: return None
	e = HStreamEntry(channel, last_channel)
	if last_channel: last_channel.n = e
	last_channel = e
	return e

def unregister_hstream(e):
	global last_channel
	if not e: return
	if last_channel == e: last_channel = e.p
	if e.p: e.p.n = e.n
	if e.n: e.n.p = e.p
	e.p = e.n = None

class SoundPreload:
	# Cross-platform zero-copy C-buffer & mmap preload container
	__slots__ = ("fn", "data", "c_buf", "ptr", "size", "ref", "t", "_fobj")
	def __init__(self, fn, data=None, c_buf=None, ptr=None, size=0, fobj=None):
		self.fn, self.data, self.c_buf, self.ptr, self.size, self.ref, self.t, self._fobj = fn, data, c_buf, ptr, size, 0, time.monotonic() * 1000.0, fobj

	def close(self):
		self.c_buf = self.ptr = None
		if isinstance(self.data, mmap.mmap):
			try: self.data.close()
			except Exception: pass
		if self._fobj:
			try: self._fobj.close()
			except Exception: pass
		self.data = self._fobj = None

def make_wav_header(total_len, freq, bits, chans, fmt=3):
	# Build 44-byte RIFF WAV header
	block_align, data_len = chans * (bits // 8), max(0, total_len - 44)
	return struct.pack('<4sI4s4sIHHIIHH4sI', b'RIFF', total_len - 8, b'WAVE', b'fmt ', 16, fmt, chans, freq, freq * block_align, block_align, bits, b'data', data_len)

def _fast_key(filename):
	# Fast O(1) normalized path lookup without repeated os.stat syscalls
	key = _path_cache.get(filename)
	if key is None:
		raw = os.fsdecode(filename) if isinstance(filename, bytes) else os.fspath(filename)
		key = os.path.normcase(os.path.abspath(raw))
		if len(_path_cache) > 4096: _path_cache.clear()
		_path_cache[filename] = key
	return key

def get_sound_preload(filename, allow_creating=False):
	try: key = _fast_key(filename)
	except Exception: return None
	pre = encoded_preloads.get(key) or sound_preloads.get(key)
	if pre is not None: pre.t = time.monotonic() * 1000.0; return pre
	return preload_encoded(filename) if allow_creating else None

def sound_preload_perform(channel, filename):
	# Fast single-allocation decode when explicit PCM WAV preload is requested
	ci = bass.BASS_CHANNELINFO()
	if not bass.BASS_ChannelGetInfo(channel, ctypes.byref(ci)): return None
	length = bass.BASS_ChannelGetLength(channel, BASS_POS_BYTE)
	if not 0 < length <= PCM_LIMIT: return None
	buf = (ctypes.c_ubyte * (length + 44))()
	read_len = bass.BASS_ChannelGetData(channel, ctypes.cast(ctypes.byref(buf, 44), ctypes.c_void_p), length | BASS_DATA_FLOAT)
	if read_len in (0, 0xFFFFFFFF, -1): return None
	ctypes.memmove(buf, make_wav_header(read_len + 44, ci.freq, 32, ci.chans, 3), 44)
	ptr = ctypes.cast(buf, ctypes.c_void_p)
	return SoundPreload(filename, buf, buf, ptr, read_len + 44)

def preload_encoded(filename, use_mmap=True):
	# Zero-stutter cross-platform preload: RAM bytes for <=2MB, OS mmap (Copy-on-Write) for >2MB
	try: cache_key = _fast_key(filename)
	except Exception: return None
	pre = encoded_preloads.get(cache_key)
	if pre is not None: pre.t = time.monotonic() * 1000.0; return pre
	try:
		file_size = os.path.getsize(cache_key)
		if not 0 < file_size <= MMAP_LIMIT: return None
		fobj, data, c_buf = None, None, None
		if file_size <= SYNC_PRELOAD_LIMIT or not use_mmap:
			with open(cache_key, "rb") as f: data = f.read()
			if not data: return None
			c_buf = ctypes.c_char_p(data)
			ptr, actual_size = ctypes.cast(c_buf, ctypes.c_void_p), len(data)
		else:
			try:
				fobj = open(cache_key, "rb")
				data = mmap.mmap(fobj.fileno(), 0, access=mmap.ACCESS_COPY)
				c_buf = (ctypes.c_ubyte * file_size).from_buffer(data)
				ptr, actual_size = ctypes.cast(c_buf, ctypes.c_void_p), file_size
			except Exception:
				if fobj: fobj.close()
				return None
		pre = SoundPreload(filename, data, c_buf, ptr, actual_size, fobj)
		with preload_mutex:
			existing = encoded_preloads.get(cache_key)
			if existing is not None: pre.close(); return existing
			ram_size = sum(item.size for item in encoded_preloads.values() if isinstance(item.data, bytes))
			if isinstance(data, bytes) and ram_size + actual_size > CACHE_LIMIT:
				for old_k, old_v in sorted(encoded_preloads.items(), key=lambda x: x[1].t):
					if ram_size + actual_size <= CACHE_LIMIT: break
					if old_v.ref <= 0:
						if isinstance(old_v.data, bytes): ram_size -= old_v.size
						old_v.close(); del encoded_preloads[old_k]
			encoded_preloads[cache_key] = pre
		return pre
	except Exception: return None

def preload(filename):
	return preload_encoded(filename, use_mmap=True)

def trigger_preload_async(filename):
	preload_encoded(filename, use_mmap=True)

def sound_preload_release(pre):
	if pre:
		with preload_mutex: pre.ref = max(0, pre.ref - 1)

def sound_preloads_clean(force=False):
	global _clean_counter
	_clean_counter += 1
	if not force and _clean_counter < 250: return
	_clean_counter, now = 0, time.monotonic() * 1000.0
	with preload_mutex:
		for cache_dict in (sound_preloads, encoded_preloads):
			size = sum(pre.size for pre in cache_dict.values() if isinstance(pre.data, bytes))
			for cache_key, pre in sorted(cache_dict.items(), key=lambda item: item[1].t):
				if pre.ref <= 0 and (now - pre.t > 120000 or size > CACHE_LIMIT):
					if isinstance(pre.data, bytes): size -= pre.size
					pre.close(); cache_dict.pop(cache_key, None)

def extract_raw_bytes(data):
	# Normalize bytes-like or Sample objects into raw bytes
	if isinstance(data, (bytes, bytearray, memoryview)): return bytes(data)
	for attr in ("data", "buffer", "raw"):
		val = getattr(data, attr, None)
		if isinstance(val, (bytes, bytearray, memoryview)): return bytes(val)
	raise TypeError(f"Expected bytes-like object, got {type(data).__name__}")

def save_mem_buffer(key, data_bytes, target="both"):
	# Store zero-copy C-buffer in memory and register pointer lookup
	raw = extract_raw_bytes(data_bytes)
	size, c_buf = len(raw), ctypes.c_char_p(raw)
	ptr = ctypes.cast(c_buf, ctypes.c_void_p)
	entry = {"buffer": ptr, "raw": (raw, c_buf), "len": size, "time": time.monotonic()}
	with preload_mutex:
		mem_buffers[key] = entry
		if ptr.value: ptr_lookup[ptr.value] = entry
		if target in ("hstream", "both"): global_buffer.hstreambuffers[key] = entry
		if target in ("hsample", "both"): global_buffer.hsamplebuffers[key] = entry
	return entry

def resolve_memory_source(src):
	# Resolve key, dict, c_void_p, ctypes array, or bytes into (ptr, length, keep_alive_ref)
	if isinstance(src, dict) and "buffer" in src and "len" in src:
		return src["buffer"], int(src["len"]), src.get("raw", src["buffer"])
	if isinstance(src, ctypes.c_void_p):
		with preload_mutex:
			entry = ptr_lookup.get(src.value)
			if entry: return entry["buffer"], entry["len"], entry["raw"]
			for d in (global_buffer.hsamplebuffers, global_buffer.hstreambuffers):
				for v in d.values():
					if isinstance(v, dict) and getattr(v.get("buffer"), "value", None) == src.value:
						return v["buffer"], v["len"], v.get("raw", v["buffer"])
		raise ValueError(f"c_void_p({src.value}) not registered in buffer.")
	if isinstance(src, (bytes, bytearray, memoryview)):
		raw = bytes(src)
		c_buf = ctypes.c_char_p(raw)
		return ctypes.cast(c_buf, ctypes.c_void_p), len(raw), (raw, c_buf)
	if isinstance(src, ctypes.Array):
		return ctypes.cast(src, ctypes.c_void_p), ctypes.sizeof(src), src
	if isinstance(src, str):
		with preload_mutex:
			entry = mem_buffers.get(src) or global_buffer.hsamplebuffers.get(src) or global_buffer.hstreambuffers.get(src)
			if isinstance(entry, dict) and "buffer" in entry and "len" in entry:
				return entry["buffer"], entry["len"], entry.get("raw", entry["buffer"])
	return None

def get_cached_sample(filename, flags=0, max_chans=64):
	# Fast HSAMPLE cache to avoid redundant disk I/O and memory allocation
	fl, mem_src, identity = flags | BASS_SAMPLE_OVER_POS, resolve_memory_source(filename), None
	if isinstance(filename, (str, bytes, os.PathLike)):
		if mem_src is not None: identity = (filename, id(mem_src[2]))
		else:
			try: identity = _fast_key(filename)
			except Exception: identity = str(filename)
	cache_key = (identity, fl) if identity is not None else None
	with preload_mutex:
		if cache_key and cache_key in sample_cache:
			entry = sample_cache[cache_key]
			smp, ref = entry[:2]
			ch = bass.BASS_SampleGetChannel(smp, False)
			if ch:
				entry[2] += 1; entry[3] = time.monotonic()
				return smp, ch, ref, True
			sample_cache.pop(cache_key, None)
	if mem_src is not None:
		ptr, length, keep_ref = mem_src
		smp = bass.BASS_SampleLoad(True, ptr, 0, length, max_chans, fl)
	elif not isinstance(filename, (str, bytes, os.PathLike)) and hasattr(filename, "handle"):
		raw_h = int(getattr(filename.handle, "value", filename.handle))
		return 0, bass.BASS_SampleGetChannel(raw_h, False), filename, True
	else:
		pre = preload_encoded(filename, use_mmap=True)
		if pre and pre.ptr and pre.size:
			keep_ref, smp = (pre.data, pre.c_buf), bass.BASS_SampleLoad(True, pre.ptr, 0, pre.size, max_chans, fl)
		else:
			c_path, u_fl = encode_path(filename)
			keep_ref, smp = None, bass.BASS_SampleLoad(False, c_path, 0, 0, max_chans, fl | u_fl)
	if not smp: return 0, 0, None, False
	ch = bass.BASS_SampleGetChannel(smp, False)
	if not ch:
		bass.BASS_SampleFree(smp); return 0, 0, None, False
	if cache_key:
		with preload_mutex: sample_cache[cache_key] = [smp, keep_ref, 1, time.monotonic()]
		return smp, ch, keep_ref, True
	return smp, ch, keep_ref, False

def release_sample(handle):
	with preload_mutex:
		for entry in sample_cache.values():
			if entry[0] == handle:
				entry[2], entry[3] = max(0, entry[2] - 1), time.monotonic()
				break
		for cache_key, entry in sorted(sample_cache.items(), key=lambda pair: pair[1][3]):
			if len(sample_cache) <= 64: break
			if entry[2] == 0:
				bass.BASS_SampleFree(entry[0]); sample_cache.pop(cache_key, None)

def load_sound_file(filename, key=None, target="hstream"):
	cache_key = key if key is not None else filename
	with open(filename, "rb") as f: data = f.read()
	return save_mem_buffer(cache_key, data, target=target)

def get_mem_buffer(key):
	with preload_mutex: return mem_buffers.get(key) or global_buffer.hstreambuffers.get(key) or global_buffer.hsamplebuffers.get(key)

def free_mem_buffer(key):
	with preload_mutex:
		entry = mem_buffers.pop(key, None)
		if entry and entry.get("buffer") and entry["buffer"].value: ptr_lookup.pop(entry["buffer"].value, None)
		global_buffer.hstreambuffers.pop(key, None); global_buffer.hsamplebuffers.pop(key, None)

def clear_all_buffers():
	with preload_mutex:
		for entry in sample_cache.values():
			if entry[0]: bass.BASS_SampleFree(entry[0])
		for pre in list(encoded_preloads.values()) + list(sound_preloads.values()): pre.close()
		encoded_preloads.clear(); sound_preloads.clear(); sample_cache.clear()
		mem_buffers.clear(); ptr_lookup.clear(); _path_cache.clear()
		global_buffer.hstreambuffers.clear(); global_buffer.hsamplebuffers.clear()

class MixerNode:
	# Legacy mixer node kept for backward compatibility
	def __init__(self, parent=None, for_single_sound=False, for_decode=False, floatingpoint=True, freq=44100, chans=2):
		if not sound_initialized and not init_sound(freq=freq):
			raise RuntimeError(f"Cannot initialize BASS: error {bass.BASS_ErrorGetCode()}")
		self.parent_mixer, self.mixers, self.sounds, self.channel, self.store_channel = parent, set(), set(), 0, None
		fl = BASS_SAMPLE_FLOAT if floatingpoint else 0
		if self.parent_mixer is None and not for_decode:
			self.channel = bass_call(bassmix.BASS_Mixer_StreamCreate, freq, chans, BASS_MIXER_NONSTOP | fl, check_error=True)
			self.store_channel = register_hstream(self.channel)
			bass_call(bass.BASS_ChannelSetAttribute, self.channel, BASS_ATTRIB_BUFFER, ctypes.c_float(0.035), check_error=False)
			bass_call(bass.BASS_ChannelPlay, self.channel, True, check_error=True)
		else:
			m_fl = BASS_STREAM_DECODE | fl | (0 if for_single_sound else BASS_MIXER_NONSTOP)
			self.channel = bassmix.BASS_Mixer_StreamCreate(freq, chans, m_fl)
			if not for_decode and self.parent_mixer: self.set_mixer(self.parent_mixer)

	def add_mixer(self, m):
		if not self.channel or not m or not m.channel or m in self.mixers: return False
		if bassmix.BASS_Mixer_StreamAddChannel(self.channel, m.channel, BASS_MIXER_CHAN_NORAMPIN):
			m.parent_mixer = self; self.mixers.add(m); return True
		return False

	def remove_mixer(self, m, internal=False):
		if m not in self.mixers: return False
		self.mixers.discard(m); bassmix.BASS_Mixer_ChannelRemove(m.channel)
		if not internal: m.parent_mixer = None
		return True

	def add_channel(self, raw_ch, paused=False, flags=0):
		if not self.channel or not raw_ch: return False
		fl = BASS_MIXER_CHAN_NORAMPIN | (BASS_MIXER_CHAN_PAUSE if paused else 0) | flags
		if bassmix.BASS_Mixer_StreamAddChannel(self.channel, raw_ch, fl):
			self.sounds.add(raw_ch); return True
		return False

	def remove_channel(self, raw_ch):
		self.sounds.discard(raw_ch)
		return bool(bassmix.BASS_Mixer_ChannelRemove(raw_ch))

	def set_mixer(self, m=None):
		if self.parent_mixer: self.parent_mixer.remove_mixer(self, True)
		return m.add_mixer(self) if m else True

	def free(self):
		for m in list(self.mixers): self.remove_mixer(m)
		for ch in list(self.sounds): bassmix.BASS_Mixer_ChannelRemove(ch)
		self.mixers.clear(); self.sounds.clear()
		if self.channel:
			if self.parent_mixer: self.parent_mixer.remove_mixer(self, True)
			bass.BASS_StreamFree(self.channel); unregister_hstream(self.store_channel)
			self.channel, self.store_channel = 0, None

def init_sound(dev=-1, freq=44100, period=10, bbuffer=500, flags=0, clsid=None):
	global sound_initialized, master_output
	if sound_initialized: return True
	# Configure direct hardware/OS mixing pipeline without intermediate master mixer latency
	if _IS_WIN: bass.BASS_SetConfig(BASS_CONFIG_DEV_DEFAULT, 1)
	bass.BASS_SetConfig(BASS_CONFIG_ASYNCFILE_BUFFER, 262144)
	bass.BASS_SetConfig(BASS_CONFIG_DEV_PERIOD, period)
	bass.BASS_SetConfig(BASS_CONFIG_BUFFER, max(100, bbuffer))
	if bass.BASS_Init(dev, freq, flags, None, clsid) or (bass.BASS_ErrorGetCode() == 14 and bass.BASS_SetDevice(dev if dev != -1 else bass.BASS_GetDevice())):
		sound_initialized, master_output = True, None
		bass.BASS_GetVersion(); bass_fx.BASS_FX_GetVersion()
		return True
	err = bass.BASS_ErrorGetCode()
	raise RuntimeError(f"BASS_Init failed for device {dev}: [{err} - {ERROR_MAP.get(err, 'UNKNOWN')}]")

def shutdown_sound():
	global sound_initialized, master_output, last_channel
	if not sound_initialized: return True
	for obj in list(global_buffer.hSound_poolbuffers.values()): obj.close()
	for obj in list(global_buffer.hrecordthreadbuffers.values()): obj.close()
	global_buffer.hSound_poolbuffers.clear(); global_buffer.hrecordthreadbuffers.clear()
	while last_channel:
		ch = last_channel.channel
		unregister_hstream(last_channel)
		if ch: bass.BASS_StreamFree(ch)
	clear_all_buffers()
	bass.BASS_Free(); bass.BASS_RecordFree()
	sound_initialized, master_output = False, None
	return True