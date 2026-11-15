# -*- coding: utf-8 -*-
# instant support utility toolkit
# copyright 2025 belong ihcyna (Labubu)<phucnggo29@gmail.com>.

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
_SPAK_VERSION = 1
_SPAK_FLAG_ZLIB = 0x01
_SPAK_FLAG_ENC = 0x02
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


def _spak_stream_xor(data_bytes, key32, context_bytes):
	# Ultra-fast C-backed integer XOR stream cipher using BLAKE2b counter blocks
	length = len(data_bytes)
	if length == 0:
		return b""
	# Generate up to 4096 bytes of unique keystream per context, then cycle if full-file encryption is used
	block_cap = min(length, 4096)
	n_blocks = (block_cap + 63) // 64
	ks_parts = [
		hashlib.blake2b(context_bytes + struct.pack("<I", i), key=key32, digest_size=64).digest()
		for i in range(n_blocks)
	]
	ks = b"".join(ks_parts)
	if length > len(ks):
		ks = (ks * ((length // len(ks)) + 1))[:length]
	else:
		ks = ks[:length]
	return (int.from_bytes(data_bytes, "little") ^ int.from_bytes(ks, "little")).to_bytes(length, "little")


def _transform_spak_chunk(raw_bytes, enc_len, key32, rel_offset, size):
	if enc_len <= 0 or not raw_bytes:
		return bytes(raw_bytes)
	actual_enc = min(len(raw_bytes), int(enc_len))
	ctx = struct.pack("<QQ", int(rel_offset), int(size))
	head_dec = _spak_stream_xor(bytes(raw_bytes[:actual_enc]), key32, ctx)
	if actual_enc >= len(raw_bytes):
		return head_dec
	if isinstance(raw_bytes, memoryview):
		out = bytearray(raw_bytes)
		out[:actual_enc] = head_dec
		return bytes(out)
	return head_dec + bytes(raw_bytes[actual_enc:])


class SpakArchive:
	"""Manages a loaded .spak package and provides thread-safe O(1) seek & slice reading."""
	def __init__(self, spak_path, data_offset, key32, header_info):
		self.spak_path = os.fspath(spak_path)
		self.data_offset = int(data_offset)
		self.key32 = key32
		self.header_info = header_info
		self._lock = threading.RLock()
		self._fobj = open(self.spak_path, "rb")

	def read_entry(self, rel_offset, size, enc_len):
		with self._lock:
			if self._fobj is None or self._fobj.closed:
				self._fobj = open(self.spak_path, "rb")
			self._fobj.seek(self.data_offset + int(rel_offset))
			chunk = self._fobj.read(int(size))
		return _transform_spak_chunk(chunk, enc_len, self.key32, rel_offset, size)

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
	encrypt_bytes=256,
):
	"""
	Đóng gói một thư mục âm thanh (bao gồm toàn bộ thư mục con) hoặc danh sách/dict các file
	thành 1 gói .spak duy nhất (hoặc tách kèm file header.inf nếu truyền header_path).

	- source: Đường dẫn thư mục (quét đệ quy mọi thư mục con, tự động kẹp tên thư mục phía trước tên file),
	          hoặc list đường dẫn file, hoặc dict {tên_file_ảo: đường_dẫn_hoặc_bytes}.
	- output_path: Đường dẫn file gói đầu ra (mặc định: <tên_thư_mục>.spak).
	- password: Mật khẩu mã hóa gói (mã hóa 100% header + mã hóa phần đầu mỗi file âm thanh).
	- header_path: Nếu None (mặc định) -> nhúng thẳng header vào đầu file .spak.
	               Nếu truyền đường dẫn (ví dụ "header.inf") hoặc True -> xuất file header.inf riêng.
	- prefix: Tiền tố thư mục tùy chọn muốn gắn vào trước tên từng file trong gói.
	- extensions: Tuple các đuôi file âm thanh cần gom (None = lấy mọi file).
	- encrypt_bytes: Số byte đầu của mỗi file .ogg cần mã hóa để phá header OggS/Vorbis và giải mã tức thì
	                 (mặc định 256 byte; truyền -1 nếu muốn mã hóa toàn bộ 100% dung lượng từng file).
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
		size = len(raw_data)
		if encrypt_bytes is None or int(encrypt_bytes) == 0:
			enc_len = 0
		elif int(encrypt_bytes) < 0:
			enc_len = size
		else:
			enc_len = min(size, int(encrypt_bytes))

		enc_chunk = _transform_spak_chunk(raw_data, enc_len, key32, curr_offset, size)
		encrypted_chunks.append(enc_chunk)
		file_entries.append([vname, curr_offset, size, enc_len])
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
	enc_header = _spak_stream_xor(comp_header, key32, b"SPAK_HEADER_V1")

	flags = _SPAK_FLAG_ZLIB | _SPAK_FLAG_ENC
	header_envelope = struct.pack("<4sBBI16s", _SPAK_MAGIC, _SPAK_VERSION, flags, len(enc_header), salt) + enc_header

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
		comp_hdr = _spak_stream_xor(enc_hdr, key32, b"SPAK_HEADER_V1") if (flags & _SPAK_FLAG_ENC) else enc_hdr
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
		archive = SpakArchive(spak_path, data_offset, key32, header_info)
		total = len(file_entries)
		for idx, item in enumerate(file_entries, 1):
			vname, rel_offset, size, enc_len = item[0], item[1], item[2], item[3]
			primary_key, aliases = _build_spak_aliases(vname, root_prefix, orig_spak_arg, custom_prefix=prefix)

			def _make_loader(arc=archive, roff=rel_offset, sz=size, elen=enc_len):
				return lambda: arc.read_entry(roff, sz, elen)

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
			primary_key, aliases = _build_spak_aliases(vname, root_prefix, orig_spak_arg, custom_prefix=prefix)
			raw_slice = blob[rel_offset : rel_offset + size]
			dec_bytes = _transform_spak_chunk(raw_slice, enc_len, key32, rel_offset, size)
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