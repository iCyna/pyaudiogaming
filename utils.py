# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# Core utility toolkit: URL detection, tokens, and SPAK archive packing.
# Supports Windows, Linux, macOS, Android, and iOS.

import platform
import os
import sys
import subprocess
import shutil
import secrets
import string
import random
from . import system

try:
	unicode = unicode
except NameError:
	unicode = str

def convert_to_unicode(name):
	if platform.system() == 'Darwin':return name
	if isinstance(name, str):
		return unicode(name.encode(sys.getfilesystemencoding()))
	return None

def token(min=4, max=12, more=""):
	# make a random code token
    length = random.randint(min, max)
    if length < 4:
        raise ValueError("length phải >= 4")

    lower = string.ascii_lowercase
    upper = string.ascii_uppercase
    digits = string.digits
    special = "!@#$%^&*"+more
    result = [
        secrets.choice(lower),
        secrets.choice(upper),
        secrets.choice(digits),
        secrets.choice(special)
    ]

    all_chars = lower + upper + digits + special
    result += [secrets.choice(all_chars) for _ in range(length - 4)]

    random.shuffle(result)

    return str(r''.join(result))

def run(cmd, sh=False):
	# run command line
	print("Executing: %s" % cmd)
	subprocess.call(cmd.split(),shell=sh)

def mkdir(fld):
	sys.stdout.write("Checking directory: %s ... " % fld)
	if os.path.isdir(fld):
		sys.stdout.write("exists\n")
		return
	else:
		os.mkdir(fld)
		sys.stdout.write("created\n")

def get_window():
	# get pointer window to access more
	from .buffer import frame as bf
	return bf

def is_url(path_string):
	# Convert to lowercase and check the prefix
	prefixes = ('http://', 'https://', 'ftp://')
   
	if str(path_string).strip().lower().startswith(prefixes):
		return True
	else:
		return False


# ==============================================================================
# SPAK (Sound Package) Binary Container, Fast Header/Head Encryption & Cast System
# ==============================================================================
import struct
import json
import zlib
import hashlib
import threading

_SPAK_MAGIC = b"SPAK"
_SPAK_VERSION = 2
_SPAK_FLAG_ZLIB = 0x01
_SPAK_FLAG_ENC = 0x02
_SPAK_FLAG_MAC = 0x04
_SPAK_ENTRY_ZLIB = 0x01
_SPAK_DEFAULT_EXTS = (".ogg", ".wav", ".mp3", ".flac", ".mid", ".midi", ".sf2", ".opus")


def _norm_spak_path(p):
	if not isinstance(p, str):
		p = os.fsdecode(p) if isinstance(p, bytes) else str(p)
	s = p.replace("\\", "/").strip()
	while s.startswith("./"):
		s = s[2:]
	while "//" in s:
		s = s.replace("//", "/")
	return s.strip("/")


def _derive_spak_key(password, salt):
	pw_bytes = (password if isinstance(password, str) else str(password or "")).encode("utf-8")
	return hashlib.blake2b(pw_bytes, salt=salt[:16], person=b"AGY_SPAK", digest_size=32).digest()


def _spak_stream_xor(data_bytes, key32, context_bytes, version=1):
	# Ultra-fast C-backed integer XOR stream cipher using BLAKE2b counter blocks
	length = len(data_bytes)
	if length == 0:
		return b""
	if version >= 2:
		# SPAK v2: Full non-repeating BLAKE2b-512 counter stream (zero keystream reuse)
		n_blocks = (length + 63) // 64
		ks = b"".join(
			hashlib.blake2b(context_bytes + struct.pack("<I", i), key=key32, digest_size=64).digest()
			for i in range(n_blocks)
		)[:length]
	else:
		# SPAK v1 legacy compatibility (4096-byte cyclic keystream)
		block_cap = min(length, 4096)
		n_blocks = (block_cap + 63) // 64
		ks = b"".join(
			hashlib.blake2b(context_bytes + struct.pack("<I", i), key=key32, digest_size=64).digest()
			for i in range(n_blocks)
		)
		if length > len(ks):
			ks = (ks * ((length // len(ks)) + 1))[:length]
		else:
			ks = ks[:length]
	return (int.from_bytes(data_bytes, "little") ^ int.from_bytes(ks, "little")).to_bytes(length, "little")


def _transform_spak_chunk(raw_bytes, enc_len, key32, rel_offset, size, version=1, entry_flags=0):
	if enc_len <= 0 or not raw_bytes:
		return bytes(raw_bytes)
	actual_enc = min(len(raw_bytes), int(enc_len))
	ctx = struct.pack("<QQI", int(rel_offset), int(size), int(entry_flags)) if version >= 2 else struct.pack("<QQ", int(rel_offset), int(size))
	head_dec = _spak_stream_xor(bytes(raw_bytes[:actual_enc]), key32, ctx, version=version)
	if actual_enc >= len(raw_bytes):
		return head_dec
	if isinstance(raw_bytes, memoryview):
		out = bytearray(raw_bytes)
		out[:actual_enc] = head_dec
		return bytes(out)
	return head_dec + bytes(raw_bytes[actual_enc:])


class SpakArchive:
	"""Manages a loaded .spak package and provides thread-safe O(1) seek & slice reading."""
	def __init__(self, spak_path, data_offset, key32, header_info, version=1):
		self.spak_path = os.fspath(spak_path)
		self.data_offset = int(data_offset)
		self.key32 = key32
		self.header_info = header_info
		self.version = int(version)
		self._lock = threading.RLock()
		self._fobj = open(self.spak_path, "rb")

	def read_entry(self, rel_offset, size, enc_len, entry_flags=0):
		with self._lock:
			if self._fobj is None or self._fobj.closed:
				self._fobj = open(self.spak_path, "rb")
			self._fobj.seek(self.data_offset + int(rel_offset))
			chunk = self._fobj.read(int(size))
		data = _transform_spak_chunk(chunk, enc_len, self.key32, rel_offset, size, version=self.version, entry_flags=entry_flags)
		if entry_flags & _SPAK_ENTRY_ZLIB:
			data = zlib.decompress(data)
		return data

	def close(self):
		with self._lock:
			if self._fobj and not self._fobj.closed:
				try:
					self._fobj.close()
				except Exception:
					pass
			self._fobj = None


def make_spak(
	source,
	output_path=None,
	password="",
	header_path=None,
	prefix=None,
	extensions=_SPAK_DEFAULT_EXTS,
	encrypt_bytes=-1,
):
	"""
	Đóng gói một thư mục âm thanh (bao gồm toàn bộ thư mục con) hoặc danh sách/dict các file
	thành 1 gói .spak duy nhất (hoặc tách kèm file header.inf nếu truyền header_path).

	- source: Đường dẫn thư mục (quét đệ quy mọi thư mục con, tự động kẹp tên thư mục phía trước tên file),
	          hoặc list đường dẫn file, hoặc dict {tên_file_ảo: đường_dẫn_hoặc_bytes}.
	- output_path: Đường dẫn file gói đầu ra (mặc định: <tên_thư_mục>.spak).
	- password: Mật khẩu mã hóa gói (tự động nén thông minh từng file + mã hóa 100% header & dữ liệu + MAC xác thực).
	- header_path: Nếu None (mặc định) -> nhúng thẳng header vào đầu file .spak.
	               Nếu truyền đường dẫn (ví dụ "header.inf") hoặc True -> xuất file header.inf riêng.
	- prefix: Tiền tố thư mục tùy chọn muốn gắn vào trước tên từng file trong gói.
	- extensions: Tuple các đuôi file âm thanh cần gom (None = lấy mọi file).
	- encrypt_bytes: Số byte mã hóa mỗi file (mặc định -1 = mã hóa 100% toàn bộ dung lượng từng file).
	"""
	items = []  # List of (virtual_rel_name, raw_bytes)
	root_prefix = ""

	ext_set = tuple(e.lower() for e in extensions) if extensions else None

	if isinstance(source, dict):
		for k, v in source.items():
			vname = _norm_spak_path(k)
			if isinstance(v, (bytes, bytearray, memoryview)):
				data = bytes(v)
			else:
				with open(v, "rb") as f:
					data = f.read()
			items.append((vname, data))
		if not output_path:
			output_path = "sounds.spak"
	elif isinstance(source, (list, tuple, set)):
		for fpath in source:
			if not os.path.isfile(fpath):
				continue
			vname = _norm_spak_path(os.path.basename(fpath))
			with open(fpath, "rb") as f:
				items.append((vname, f.read()))
		if not output_path:
			output_path = "sounds.spak"
	elif isinstance(source, (str, bytes, os.PathLike)):
		src_path = os.fspath(source)
		if os.path.isfile(src_path):
			vname = _norm_spak_path(os.path.basename(src_path))
			with open(src_path, "rb") as f:
				items.append((vname, f.read()))
			if not output_path:
				output_path = os.path.splitext(src_path)[0] + ".spak"
		elif os.path.isdir(src_path):
			norm_src = _norm_spak_path(src_path)
			if not os.path.isabs(src_path):
				root_prefix = norm_src
			if not output_path:
				output_path = src_path.rstrip("/\\") + ".spak"
			abs_out = os.path.normcase(os.path.abspath(output_path))
			abs_hdr = (
				os.path.normcase(os.path.abspath(header_path))
				if isinstance(header_path, (str, bytes, os.PathLike))
				else None
			)
			for dirpath, dirnames, filenames in os.walk(src_path):
				dirnames.sort()
				filenames.sort()
				for fn in filenames:
					full_p = os.path.join(dirpath, fn)
					abs_p = os.path.normcase(os.path.abspath(full_p))
					if abs_p == abs_out or (abs_hdr and abs_p == abs_hdr):
						continue
					low_fn = fn.lower()
					if low_fn.endswith((".spak", ".inf", ".zsp", ".zp")):
						continue
					if ext_set and not low_fn.endswith(ext_set):
						continue
					# Kẹp tên thư mục con phía trước tên file (chuẩn hóa dấu /)
					rel_p = _norm_spak_path(os.path.relpath(full_p, src_path))
					with open(full_p, "rb") as f:
						items.append((rel_p, f.read()))
		else:
			raise FileNotFoundError(f"Source path not found: {src_path!r}")
	else:
		raise TypeError(f"Unsupported source type for make_spak: {type(source).__name__}")

	if prefix is not None:
		norm_pref = _norm_spak_path(prefix)
		root_prefix = norm_pref
		if norm_pref:
			items = [
				(f"{norm_pref}/{name}" if not name.startswith(norm_pref + "/") else name, data)
				for name, data in items
			]

	salt = secrets.token_bytes(16)
	key32 = _derive_spak_key(password, salt)

	file_entries = []
	encrypted_chunks = []
	curr_offset = 0

	for vname, raw_data in items:
		# Smart compression: only store zlib-compressed if it saves >= 5% (shrinks WAV/SF2/JSON; skips already-compressed OGG/OPUS/MP3)
		entry_flags = 0
		payload = raw_data
		if len(raw_data) >= 64:
			comp = zlib.compress(raw_data, level=9)
			if len(comp) < int(len(raw_data) * 0.95):
				payload = comp
				entry_flags |= _SPAK_ENTRY_ZLIB

		size = len(payload)
		if encrypt_bytes is None or int(encrypt_bytes) == 0:
			enc_len = 0
		elif int(encrypt_bytes) < 0:
			enc_len = size
		else:
			enc_len = min(size, int(encrypt_bytes))

		enc_chunk = _transform_spak_chunk(payload, enc_len, key32, curr_offset, size, version=_SPAK_VERSION, entry_flags=entry_flags)
		encrypted_chunks.append(enc_chunk)
		file_entries.append([vname, curr_offset, size, enc_len, entry_flags])
		curr_offset += size

	header_dict = {
		"v": _SPAK_VERSION,
		"root": root_prefix,
		"count": len(file_entries),
		"total_size": curr_offset,
		"files": file_entries,
	}
	raw_header = json.dumps(header_dict, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
	comp_header = zlib.compress(raw_header, level=9)
	enc_header = _spak_stream_xor(comp_header, key32, b"SPAK_HEADER_V2", version=_SPAK_VERSION)
	hdr_mac = hashlib.blake2b(salt + enc_header, key=key32, digest_size=16).digest()
	enc_header_with_mac = hdr_mac + enc_header

	flags = _SPAK_FLAG_ZLIB | _SPAK_FLAG_ENC | _SPAK_FLAG_MAC
	header_envelope = struct.pack("<4sBBI16s", _SPAK_MAGIC, _SPAK_VERSION, flags, len(enc_header_with_mac), salt) + enc_header_with_mac

	out_dir = os.path.dirname(os.path.abspath(output_path))
	if out_dir and not os.path.exists(out_dir):
		os.makedirs(out_dir, exist_ok=True)

	if header_path:
		if header_path is True:
			header_path = os.path.splitext(output_path)[0] + ".inf"
		hdr_dir = os.path.dirname(os.path.abspath(header_path))
		if hdr_dir and not os.path.exists(hdr_dir):
			os.makedirs(hdr_dir, exist_ok=True)
		with open(header_path, "wb") as hf:
			hf.write(header_envelope)
		with open(output_path, "wb") as df:
			for ch in encrypted_chunks:
				df.write(ch)
	else:
		with open(output_path, "wb") as f:
			f.write(header_envelope)
			for ch in encrypted_chunks:
				f.write(ch)

	return {
		"spak_path": output_path,
		"header_path": header_path if isinstance(header_path, str) else None,
		"count": len(file_entries),
		"total_size": curr_offset,
		"files": [e[0] for e in file_entries],
	}


def _build_spak_aliases(vname, root_prefix, spak_path, custom_prefix=None):
	vname = _norm_spak_path(vname)
	aliases = {vname}

	if custom_prefix is not None:
		cp = _norm_spak_path(custom_prefix)
		if cp:
			aliases.add(f"{cp}/{vname}" if not vname.startswith(cp + "/") else vname)
		primary = f"{cp}/{vname}" if (cp and not vname.startswith(cp + "/")) else vname
	elif root_prefix:
		rp = _norm_spak_path(root_prefix)
		primary = f"{rp}/{vname}" if not vname.startswith(rp + "/") else vname
		aliases.add(primary)
	else:
		primary = vname

	if spak_path:
		sp_norm = _norm_spak_path(spak_path)
		sp_dir = _norm_spak_path(os.path.dirname(sp_norm))
		sp_stem = os.path.splitext(os.path.basename(sp_norm))[0]
		if sp_dir and not os.path.isabs(spak_path):
			aliases.add(f"{sp_dir}/{vname}" if not vname.startswith(sp_dir + "/") else vname)
			stem_pref = f"{sp_dir}/{sp_stem}"
			aliases.add(f"{stem_pref}/{vname}" if not vname.startswith(stem_pref + "/") else vname)
			if primary == vname:
				primary = f"{sp_dir}/{vname}"
		elif sp_stem:
			aliases.add(f"{sp_stem}/{vname}" if not vname.startswith(sp_stem + "/") else vname)

	# Also add Windows backslash variants for direct dict inspection compatibility
	win_aliases = {k.replace("/", "\\") for k in aliases}
	aliases.update(win_aliases)
	return primary, tuple(aliases)


def _resolve_cross_platform_path(path_val):
	# Resolve file path across Windows, Linux, macOS, Android (APK/private storage), and frozen builds
	p = os.fspath(path_val)
	if isinstance(p, bytes):
		p = os.fsdecode(p)
	p_norm = p.replace("\\", os.sep).replace("/", os.sep)
	if os.path.isfile(p_norm):
		return p_norm
	search_bases = [
		os.getcwd(),
		os.environ.get("ANDROID_ARGUMENT", ""),
		os.environ.get("ANDROID_PRIVATE", ""),
		system.embedded_data_path(),
		os.path.join(system.embedded_data_path(), ".."),
	]
	for base in search_bases:
		if not base:
			continue
		cand = os.path.join(base, p_norm)
		if os.path.isfile(cand):
			return cand
	return p_norm


def load_spak(
	spak_path,
	password="",
	mode="lazy",
	target="both",
	prefix=None,
	header_path=None,
	preload_sample=False,
	callback=None,
):
	"""
	Đọc gói âm thanh .spak (hoặc gói .ogg + header.inf) và cast vào hệ thống âm thanh (hsample / hstream).

	Hỗ trợ 2 chế độ (`mode`):
	- mode="lazy" (hoặc mode=1, lazy=True - Mặc định):
	    Chỉ đọc và giải mã Header (< 1ms), ghi nhận vị trí (offset, size) của từng file.
	    Khi game gọi sound.load(), sound.stream() hoặc playsingle() tới file nào thì mới
	    nhảy seek(offset) đọc đúng mảnh đó, giải mã tức thì và cast sang hsample/hstream.
	- mode="eager" / "all" (hoặc mode=2, lazy=False):
	    Đọc toàn bộ các file trong gói, giải mã và sound_cast (save_mem_buffer) ngay lập tức
	    vào hsamplebuffers / hstreambuffers.

	- target: "both" (mặc định, dùng chung 1 vùng nhớ cho cả hsample và hstream), "hsample", hoặc "hstream".
	- prefix: Tiền tố thư mục gắn thêm vào tên file khi đăng ký (ví dụ "res/sounds").
	- header_path: Đường dẫn file header.inf rời (nếu lúc make_spak tách riêng header).
	"""
	from .sound_modules import control

	orig_spak_arg = os.fsdecode(spak_path) if isinstance(spak_path, bytes) else str(spak_path)
	spak_path = _resolve_cross_platform_path(spak_path)
	if not os.path.isfile(spak_path):
		raise FileNotFoundError(f"SPAK file not found: {spak_path!r}")

	# Xác định vị trí đọc Header (nhúng trong spak_path hay nằm ở file header.inf riêng)
	data_offset = 0
	hdr_raw_source = None

	if header_path:
		if header_path is True:
			header_path = os.path.splitext(spak_path)[0] + ".inf"
		else:
			header_path = _resolve_cross_platform_path(header_path)
		with open(header_path, "rb") as hf:
			hdr_raw_source = hf.read()
		data_offset = 0
	else:
		with open(spak_path, "rb") as sf:
			head_probe = sf.read(26)
			if len(head_probe) >= 26 and head_probe[:4] == _SPAK_MAGIC:
				_, ver, flags, hdr_len, salt = struct.unpack("<4sBBI16s", head_probe)
				enc_hdr = sf.read(hdr_len)
				hdr_raw_source = head_probe + enc_hdr
				data_offset = 26 + hdr_len
			else:
				# Tự động tìm file <stem>.inf hoặc header.inf cùng thư mục nếu gói không nhúng header
				cand1 = os.path.splitext(spak_path)[0] + ".inf"
				cand2 = os.path.join(os.path.dirname(spak_path), "header.inf")
				found_inf = cand1 if os.path.isfile(cand1) else (cand2 if os.path.isfile(cand2) else None)
				if not found_inf:
					raise ValueError(f"Invalid SPAK header in {spak_path!r} and no .inf header found.")
				with open(found_inf, "rb") as hf:
					hdr_raw_source = hf.read()
				data_offset = 0

	if len(hdr_raw_source) < 26 or hdr_raw_source[:4] != _SPAK_MAGIC:
		raise ValueError(f"Invalid SPAK magic signature in {spak_path!r}")

	_, ver, flags, hdr_len, salt = struct.unpack("<4sBBI16s", hdr_raw_source[:26])
	enc_hdr = hdr_raw_source[26 : 26 + hdr_len]
	key32 = _derive_spak_key(password, salt)

	try:
		if flags & _SPAK_FLAG_MAC:
			if len(enc_hdr) < 16:
				raise ValueError("Truncated SPAK MAC")
			got_mac, enc_body = enc_hdr[:16], enc_hdr[16:]
			exp_mac = hashlib.blake2b(salt + enc_body, key=key32, digest_size=16).digest()
			if not secrets.compare_digest(got_mac, exp_mac):
				raise ValueError("MAC verification failed")
		else:
			enc_body = enc_hdr
		hdr_ctx = b"SPAK_HEADER_V2" if ver >= 2 else b"SPAK_HEADER_V1"
		comp_hdr = _spak_stream_xor(enc_body, key32, hdr_ctx, version=ver) if (flags & _SPAK_FLAG_ENC) else enc_body
		raw_hdr = zlib.decompress(comp_hdr) if (flags & _SPAK_FLAG_ZLIB) else comp_hdr
		header_info = json.loads(raw_hdr.decode("utf-8"))
	except Exception as ex:
		raise ValueError(f"Cannot decrypt or parse SPAK header (wrong password or corrupted file): {ex}") from ex

	root_prefix = header_info.get("root", "")
	file_entries = header_info.get("files", [])

	# Chuẩn hóa tham số mode
	if isinstance(mode, bool):
		is_lazy = mode
	elif isinstance(mode, int):
		is_lazy = (mode == 1)
	else:
		is_lazy = str(mode).strip().lower() in ("lazy", "ondemand", "on_demand", "stream", "1", "gradual")

	registered_keys = []

	if is_lazy:
		archive = SpakArchive(spak_path, data_offset, key32, header_info, version=ver)
		total = len(file_entries)
		for idx, item in enumerate(file_entries, 1):
			vname, rel_offset, size, enc_len = item[0], item[1], item[2], item[3]
			eflags = item[4] if len(item) > 4 else 0
			primary_key, aliases = _build_spak_aliases(vname, root_prefix, orig_spak_arg, custom_prefix=prefix)

			def _make_loader(arc=archive, roff=rel_offset, sz=size, elen=enc_len, flg=eflags):
				return lambda: arc.read_entry(roff, sz, elen, flg)

			control.register_spak_lazy(primary_key, aliases, _make_loader(), target=target, archive_obj=archive)
			registered_keys.append(primary_key)
			if callback:
				callback(primary_key, idx, total)
	else:
		with open(spak_path, "rb") as df:
			df.seek(data_offset)
			blob = memoryview(df.read())
		total = len(file_entries)
		for idx, item in enumerate(file_entries, 1):
			vname, rel_offset, size, enc_len = item[0], item[1], item[2], item[3]
			eflags = item[4] if len(item) > 4 else 0
			primary_key, aliases = _build_spak_aliases(vname, root_prefix, orig_spak_arg, custom_prefix=prefix)
			raw_slice = blob[rel_offset : rel_offset + size]
			dec_bytes = _transform_spak_chunk(raw_slice, enc_len, key32, rel_offset, size, version=ver, entry_flags=eflags)
			if eflags & _SPAK_ENTRY_ZLIB:
				dec_bytes = zlib.decompress(dec_bytes)
			control.save_mem_buffer(primary_key, dec_bytes, target=target, aliases=aliases)
			if preload_sample and target in ("hsample", "both") and control.sound_initialized:
				smp, ch, _, _ = control.get_cached_sample(primary_key)
				if smp:
					control.release_sample(smp)
			registered_keys.append(primary_key)
			if callback:
				callback(primary_key, idx, total)

	return {
		"mode": "lazy" if is_lazy else "eager",
		"count": len(registered_keys),
		"files": registered_keys,
		"root": root_prefix,
	}



# ==============================================================================
# GENERAL-PURPOSE GAME, AUDIO, MATH, TEXT, DATA & PLATFORM UTILITIES
# ==============================================================================
import ctypes
import math
import re
import socket
import time as _time
import unicodedata
import webbrowser


# --- Math, Spatial & Audio Conversions ---

def clamp(val, low, high):
	"""Clamp ``val`` to the inclusive range ``[low, high]``."""
	if low > high:
		low, high = high, low
	return low if val < low else (high if val > high else val)


def lerp(a, b, t):
	"""Linear interpolation between ``a`` and ``b`` by factor ``t``."""
	return a + (b - a) * t


def inv_lerp(a, b, value):
	"""Inverse linear interpolation: return ``t`` such that ``lerp(a, b, t) == value``."""
	if a == b:
		return 0.0
	return (value - a) / (b - a)


def remap(val, in_min, in_max, out_min, out_max, clamp_out=False):
	"""Remap ``val`` from range ``[in_min, in_max]`` to ``[out_min, out_max]``."""
	t = inv_lerp(in_min, in_max, val)
	if clamp_out:
		t = clamp(t, 0.0, 1.0)
	return lerp(out_min, out_max, t)


def smoothstep(edge0, edge1, x):
	"""Smooth Hermite interpolation between 0 and 1."""
	t = clamp(inv_lerp(edge0, edge1, x), 0.0, 1.0)
	return t * t * (3.0 - 2.0 * t)


def distance_2d(x1, y1, x2, y2):
	return math.hypot(x2 - x1, y2 - y1)


def distance_3d(x1, y1, z1, x2, y2, z2):
	return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2)


def angle_2d(x1, y1, x2, y2):
	"""Return clockwise bearing in degrees ``[0, 360)`` where North (+Y) = 0, East (+X) = 90."""
	deg = math.degrees(math.atan2(x2 - x1, y2 - y1))
	return deg % 360.0


def clock_direction(dx, dy):
	"""Convert a 2D delta ``(dx, dy)`` (North = +Y, East = +X) to clock hour ``1..12``."""
	if dx == 0 and dy == 0:
		return 12
	deg = math.degrees(math.atan2(dx, dy)) % 360.0
	hour = int(((deg + 15.0) % 360.0) // 30.0)
	return 12 if hour == 0 else hour


def db_to_linear(db):
	"""Convert decibels (e.g. ``-6.0``) to linear amplitude (``0.0..1.0+``)."""
	if db <= -120.0:
		return 0.0
	return 10.0 ** (float(db) / 20.0)


def linear_to_db(amp, floor_db=-120.0):
	"""Convert linear amplitude to decibels."""
	amp = float(amp)
	if amp <= 0.0:
		return float(floor_db)
	return max(float(floor_db), 20.0 * math.log10(amp))


def percent(value, total, decimals=1):
	"""Return percentage ``0.0..100.0`` safely (returns ``0.0`` if ``total == 0``)."""
	if not total:
		return 0.0
	return round((float(value) / float(total)) * 100.0, decimals)


# --- Random & Probability ---

def chance(prob_percent):
	"""Return ``True`` with probability ``prob_percent``% (0..100)."""
	p = float(prob_percent)
	if p <= 0.0:
		return False
	if p >= 100.0:
		return True
	return random.random() * 100.0 < p


def weighted_choice(items):
	"""Pick one item by weight. Accepts ``{item: weight}`` or ``[(item, weight), ...]``."""
	pairs = list(items.items()) if isinstance(items, dict) else list(items)
	if not pairs:
		raise ValueError("weighted_choice requires a non-empty mapping or sequence")
	vals = [p[0] for p in pairs]
	weights = [max(0.0, float(p[1])) for p in pairs]
	if sum(weights) <= 0.0:
		return random.choice(vals)
	return random.choices(vals, weights=weights, k=1)[0]


def roll_dice(count=1, sides=6, bonus=0):
	"""Roll ``count`` dice with ``sides`` faces and add ``bonus``."""
	return sum(random.randint(1, max(1, int(sides))) for _ in range(max(0, int(count)))) + int(bonus)


def shuffle_copy(seq):
	"""Return a newly shuffled list without modifying the original sequence."""
	out = list(seq)
	random.shuffle(out)
	return out


# --- String, Formatting & Search ---

def format_bytes(num_bytes, decimals=2):
	"""Format byte count into human-readable units (B, KB, MB, GB, TB)."""
	val = float(num_bytes)
	sign = "-" if val < 0 else ""
	val = abs(val)
	for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
		if val < 1024.0 or unit == "PB":
			if unit == "B":
				return f"{sign}{int(val)} B"
			return f"{sign}{val:.{decimals}f} {unit}"
		val /= 1024.0
	return f"{sign}{val:.{decimals}f} PB"


def format_number(num, sep=","):
	"""Format integer/float with thousands separators."""
	if isinstance(num, int):
		return f"{num:,}".replace(",", sep)
	return f"{float(num):,.2f}".replace(",", sep)


def truncate(text, max_len, suffix="..."):
	"""Truncate text cleanly to at most ``max_len`` characters."""
	s = str(text)
	if max_len <= 0 or len(s) <= max_len:
		return s
	if len(suffix) >= max_len:
		return s[:max_len]
	return s[: max_len - len(suffix)] + suffix


def strip_accents(text):
	"""Remove diacritical marks for accent-insensitive search/comparison."""
	s = str(text or "")
	decomposed = unicodedata.normalize("NFKD", s)
	out = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
	return out.replace("đ", "d").replace("Đ", "D")


def slugify(text, sep="_"):
	"""Convert arbitrary text into a clean ASCII filename/identifier slug."""
	base = strip_accents(str(text or "")).lower()
	cleaned = re.sub(r"[^a-z0-9]+", sep, base).strip(sep)
	return cleaned or "item"


def natural_sort_key(text):
	"""Sort key so ``'item2'`` comes before ``'item10'``."""
	return [int(tok) if tok.isdigit() else tok.lower() for tok in re.split(r"(\d+)", str(text))]


def fuzzy_match(query, candidates, limit=10):
	"""Accent-insensitive ranked search returning up to ``limit`` matching candidates."""
	q = strip_accents(str(query or "")).strip().lower()
	if not q:
		return list(candidates)[:limit]
	scored = []
	for item in candidates:
		raw = str(item)
		norm = strip_accents(raw).lower()
		if norm == q:
			scored.append((0, len(raw), item))
		elif norm.startswith(q):
			scored.append((1, len(raw), item))
		elif q in norm:
			scored.append((2, norm.index(q), item))
		else:
			# Subsequence check
			qi = 0
			for ch in norm:
				if ch == q[qi]:
					qi += 1
					if qi == len(q):
						scored.append((3, len(raw), item))
						break
	scored.sort(key=lambda x: (x[0], x[1]))
	return [x[2] for x in scored[:limit]]


# --- Data, Type Conversion & Collections ---

def deep_merge(base, override):
	"""Recursively merge two dictionaries without mutating ``base`` or ``override``."""
	out = dict(base or {})
	for k, v in (override or {}).items():
		if k in out and isinstance(out[k], dict) and isinstance(v, dict):
			out[k] = deep_merge(out[k], v)
		else:
			out[k] = v
	return out


def flatten(nested):
	"""Recursively flatten nested lists/tuples into a single list."""
	out = []
	for item in nested:
		if isinstance(item, (list, tuple)):
			out.extend(flatten(item))
		else:
			out.append(item)
	return out


def chunked(seq, size):
	"""Yield consecutive chunks of length ``size`` from ``seq``."""
	size = max(1, int(size))
	seq = list(seq)
	for i in range(0, len(seq), size):
		yield seq[i : i + size]


def safe_int(val, default=0):
	try:
		return int(float(val))
	except (TypeError, ValueError):
		return default


def safe_float(val, default=0.0):
	try:
		return float(val)
	except (TypeError, ValueError):
		return default


def safe_bool(val, default=False):
	if isinstance(val, bool):
		return val
	if isinstance(val, (int, float)):
		return val != 0
	s = str(val or "").strip().lower()
	if s in ("1", "true", "yes", "on", "y"):
		return True
	if s in ("0", "false", "no", "off", "n", ""):
		return False
	return default


# --- Files, Hashing, Network, Clipboard & Retry ---

def ensure_dir(path):
	"""Create directory (including parents) if missing and return the path."""
	os.makedirs(path, exist_ok=True)
	return path


def file_hash(filepath, algo="sha256", chunk_size=65536):
	"""Compute hexadecimal hash digest of a file efficiently in chunks."""
	h = hashlib.new(algo)
	with open(filepath, "rb") as f:
		while True:
			chunk = f.read(chunk_size)
			if not chunk:
				break
			h.update(chunk)
	return h.hexdigest()


def open_url(url):
	"""Open a URL in the default browser on Windows, macOS, Linux, and Android."""
	url = str(url or "").strip()
	if not url:
		return False
	try:
		if system.get_platform()["os"] == "android":
			act, bridge = system.get_android_activity()
			if act is not None:
				jcls = (lambda n: __import__("java").jclass(n)) if bridge == "chaquopy" else (lambda n: __import__("jnius").autoclass(n))
				Intent = jcls("android.content.Intent")
				Uri = jcls("android.net.Uri")
				intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
				intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
				act.startActivity(intent)
				return True
	except Exception:
		pass
	try:
		return bool(webbrowser.open(url))
	except Exception:
		return False


def copy_text(text):
	"""Copy UTF-8 text to system clipboard (Windows, Android, macOS, Linux) with zero external dependencies."""
	s = str(text)
	if system.get_platform()["os"] == "android":
		try:
			from .pygame_shim import _android_bridge
			if _android_bridge.is_android_java_available():
				_android_bridge.set_clipboard(s)
				return True
		except Exception:
			pass
	if os.name == "nt":
		try:
			CF_UNICODETEXT = 13
			GMEM_MOVEABLE = 0x0002
			u32 = ctypes.windll.user32
			k32 = ctypes.windll.kernel32
			k32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
			k32.GlobalAlloc.restype = ctypes.c_void_p
			k32.GlobalLock.argtypes = [ctypes.c_void_p]
			k32.GlobalLock.restype = ctypes.c_void_p
			k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
			u32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
			u32.SetClipboardData.restype = ctypes.c_void_p
			data = (s + "\x00").encode("utf-16-le")
			if not u32.OpenClipboard(0):
				return False
			try:
				u32.EmptyClipboard()
				hmem = k32.GlobalAlloc(GMEM_MOVEABLE, len(data))
				if not hmem:
					return False
				ptr = k32.GlobalLock(hmem)
				ctypes.memmove(ptr, data, len(data))
				k32.GlobalUnlock(hmem)
				u32.SetClipboardData(CF_UNICODETEXT, hmem)
				return True
			finally:
				u32.CloseClipboard()
		except Exception:
			return False
	if sys.platform == "darwin":
		try:
			subprocess.run(["pbcopy"], input=s.encode("utf-8"), check=True)
			return True
		except Exception:
			return False
	for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]):
		if shutil.which(cmd[0]):
			try:
				subprocess.run(cmd, input=s.encode("utf-8"), check=True)
				return True
			except Exception:
				continue
	return False


def paste_text():
	"""Read UTF-8 text from system clipboard (Windows, Android, macOS, Linux)."""
	if system.get_platform()["os"] == "android":
		try:
			from .pygame_shim import _android_bridge
			if _android_bridge.is_android_java_available():
				return _android_bridge.get_clipboard() or ""
		except Exception:
			pass
	if os.name == "nt":
		try:
			CF_UNICODETEXT = 13
			u32 = ctypes.windll.user32
			k32 = ctypes.windll.kernel32
			u32.GetClipboardData.argtypes = [ctypes.c_uint]
			u32.GetClipboardData.restype = ctypes.c_void_p
			k32.GlobalLock.argtypes = [ctypes.c_void_p]
			k32.GlobalLock.restype = ctypes.c_void_p
			k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
			if not u32.OpenClipboard(0):
				return ""
			try:
				hmem = u32.GetClipboardData(CF_UNICODETEXT)
				if not hmem:
					return ""
				ptr = k32.GlobalLock(hmem)
				if not ptr:
					return ""
				try:
					return ctypes.wstring_at(ptr)
				finally:
					k32.GlobalUnlock(hmem)
			finally:
				u32.CloseClipboard()
		except Exception:
			return ""
	if sys.platform == "darwin":
		try:
			return subprocess.check_output(["pbpaste"]).decode("utf-8", errors="replace")
		except Exception:
			return ""
	for cmd in (["wl-paste", "--no-newline"], ["xclip", "-selection", "clipboard", "-o"], ["xsel", "--clipboard", "--output"]):
		if shutil.which(cmd[0]):
			try:
				return subprocess.check_output(cmd).decode("utf-8", errors="replace")
			except Exception:
				continue
	return ""


def is_online(host="1.1.1.1", port=53, timeout=1.5):
	"""Quick check whether network connectivity is available."""
	try:
		with socket.create_connection((host, int(port)), timeout=float(timeout)):
			return True
	except OSError:
		return False


def retry(fn, retries=3, delay_ms=100, exceptions=(Exception,)):
	"""Call ``fn()`` up to ``retries`` times with ``delay_ms`` pause between failures."""
	last_err = None
	for attempt in range(max(1, int(retries))):
		try:
			return fn()
		except exceptions as exc:
			last_err = exc
			if attempt + 1 < retries and delay_ms > 0:
				_time.sleep(delay_ms / 1000.0)
	raise last_err
