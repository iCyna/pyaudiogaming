# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# Persistent app storage paths and ConfigStore manager.
# Supports Windows, Linux, macOS, Android, and iOS.

import json
import os
import pickle
import re
import shutil
import sys
from pathlib import Path

from . import system

__all__ = [
	"Storage",
	"ConfigStore",
	"get_platform_data_dir",
	"atomic_write_bytes",
	"atomic_write_text",
]


def _sanitize_app_name(app_name: str) -> str:
	clean = re.sub(r"[^a-zA-Z0-9._-]", "_", str(app_name or "pyaudiogaming_app").strip())
	return clean.strip("._") or "pyaudiogaming_app"


def get_platform_data_dir(app_name: str, portable: bool = False, portable_dir: str = "res") -> Path:
	"""Return a guaranteed-writable persistent directory for ``app_name`` on any OS."""
	safe = _sanitize_app_name(app_name)
	os_name = system.get_platform()["os"]

	if os_name in ("android", "ios"):
		base = os.environ.get("HOME") or os.path.expanduser("~")
		if not base or base == "/":
			base = os.getcwd()
		root = Path(base) / safe
	elif portable:
		root = Path(portable_dir).resolve()
	elif os_name == "windows":
		base = os.environ.get("APPDATA") or os.path.expanduser("~")
		root = Path(base) / safe
	elif os_name == "macos":
		root = Path.home() / "Library" / "Application Support" / safe
	elif os_name == "web":
		base = os.environ.get("HOME") or "/tmp"
		root = Path(base) / safe
	else:
		base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
		root = Path(base) / safe

	root.mkdir(parents=True, exist_ok=True)
	return root


def atomic_write_bytes(path, data: bytes, backup: bool = True):
	"""Write bytes atomically via ``.tmp`` + ``fsync`` + ``os.replace``."""
	target = Path(path)
	target.parent.mkdir(parents=True, exist_ok=True)
	tmp = target.with_name(target.name + ".tmp")
	with open(tmp, "wb") as f:
		f.write(data)
		f.flush()
		try:
			os.fsync(f.fileno())
		except Exception:
			pass
	if backup and target.is_file():
		bak = target.with_name(target.name + ".bak")
		try:
			shutil.copy2(target, bak)
		except Exception:
			pass
	os.replace(tmp, target)


def atomic_write_text(path, text: str, encoding: str = "utf-8", backup: bool = True):
	atomic_write_bytes(path, str(text).encode(encoding), backup=backup)


class Storage:
	"""Cross-platform user data storage manager (JSON, Pickle, text, binary, AES-encrypted)."""

	def __init__(self, app_name: str, portable: bool = False, portable_dir: str = "res"):
		self.app_name = app_name
		self.root = get_platform_data_dir(app_name, portable=portable, portable_dir=portable_dir)
		self.data_dir = self.root / "data"
		self.cache_dir = self.root / "cache"
		self.log_dir = self.root / "logs"
		self.data_dir.mkdir(parents=True, exist_ok=True)

	def path(self, *parts, ensure_parent: bool = True, ensure_dir: bool = False) -> Path:
		p = self.root.joinpath(*parts)
		if ensure_dir:
			p.mkdir(parents=True, exist_ok=True)
		elif ensure_parent:
			p.parent.mkdir(parents=True, exist_ok=True)
		return p

	def exists(self, *parts) -> bool:
		return self.root.joinpath(*parts).exists()

	def delete(self, *parts) -> bool:
		p = self.root.joinpath(*parts)
		if p.is_file():
			p.unlink()
			return True
		if p.is_dir():
			shutil.rmtree(p)
			return True
		return False

	def list_files(self, *parts, suffix: str = None) -> list:
		d = self.root.joinpath(*parts)
		if not d.is_dir():
			return []
		out = []
		for item in sorted(d.iterdir()):
			if item.is_file():
				if suffix is None or item.name.lower().endswith(suffix.lower()):
					out.append(item)
		return out

	# --- Raw bytes & text ---
	def save_bytes(self, rel_path, data: bytes, backup: bool = True) -> Path:
		p = self.path(rel_path)
		atomic_write_bytes(p, data, backup=backup)
		return p

	def load_bytes(self, rel_path, default=None):
		p = self.root / rel_path
		for cand in (p, p.with_name(p.name + ".bak")):
			if cand.is_file():
				try:
					return cand.read_bytes()
				except Exception:
					continue
		return default

	def save_text(self, rel_path, text: str, encoding: str = "utf-8", backup: bool = True) -> Path:
		p = self.path(rel_path)
		atomic_write_text(p, text, encoding=encoding, backup=backup)
		return p

	def load_text(self, rel_path, default="", encoding: str = "utf-8"):
		raw = self.load_bytes(rel_path, default=None)
		if raw is None:
			return default
		try:
			return raw.decode(encoding)
		except Exception:
			return default

	# --- JSON ---
	def save_json(self, rel_path, obj, indent: int = 2, backup: bool = True) -> Path:
		text = json.dumps(obj, ensure_ascii=False, indent=indent)
		return self.save_text(rel_path, text, backup=backup)

	def load_json(self, rel_path, default=None):
		p = self.root / rel_path
		for cand in (p, p.with_name(p.name + ".bak")):
			if cand.is_file():
				try:
					return json.loads(cand.read_text(encoding="utf-8"))
				except Exception:
					continue
		return default

	# --- Pickle ---
	def save_pickle(self, rel_path, obj, backup: bool = True) -> Path:
		return self.save_bytes(rel_path, pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL), backup=backup)

	def load_pickle(self, rel_path, default=None):
		p = self.root / rel_path
		for cand in (p, p.with_name(p.name + ".bak")):
			if cand.is_file():
				try:
					return pickle.loads(cand.read_bytes())
				except Exception:
					continue
		return default

	# --- AES/Fernet encrypted (via pyaudiogaming.file.File) ---
	def save_encrypted(self, rel_path, obj, password: str, fmt: str = "json", aes: bool = True, backup: bool = True) -> Path:
		from .file import File
		encoder = File(password=password, encode=True, aes=aes)
		if fmt == "json":
			payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
		elif fmt == "pickle":
			payload = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
		else:
			payload = str(obj).encode("utf-8")
		enc = encoder.cipher.encrypt(payload)
		if aes:
			enc = encoder.aes_encrypt(enc)
		return self.save_bytes(rel_path, enc, backup=backup)

	def load_encrypted(self, rel_path, password: str, fmt: str = "json", aes: bool = True, default=None):
		from .file import File
		encoder = File(password=password, encode=True, aes=aes)
		p = self.root / rel_path
		for cand in (p, p.with_name(p.name + ".bak")):
			if not cand.is_file():
				continue
			try:
				raw = cand.read_bytes()
				if aes:
					raw = encoder.aes_decrypt(raw)
				dec = encoder.cipher.decrypt(raw)
				if fmt == "json":
					return json.loads(dec.decode("utf-8"))
				if fmt == "pickle":
					return pickle.loads(dec)
				return dec.decode("utf-8")
			except Exception:
				continue
		return default


class ConfigStore:
	"""Dict-like persistent configuration store with defaults, auto-recovery & versioning.

	Example::

		cfg = ConfigStore("thousand_battles", defaults={"vol": 90.0, "lang": "vi"}, portable=True)
		cfg.load()
		cfg["vol"] = 75.0
		cfg.save()
	"""

	def __init__(
		self,
		app_name: str,
		filename: str = "data/config.json",
		defaults: dict = None,
		fmt: str = "json",
		password: str = None,
		portable: bool = False,
		portable_dir: str = "res",
		version: int = 1,
		auto_save: bool = False,
	):
		self.storage = Storage(app_name, portable=portable, portable_dir=portable_dir)
		self.filename = filename
		self.defaults = dict(defaults or {})
		self.fmt = fmt.lower().strip()
		self.password = password
		self.version = int(version)
		self.auto_save = bool(auto_save)
		self._data = dict(self.defaults)
		self._dirty = False

	def load(self, migrate_fn=None) -> dict:
		loaded = None
		if self.password:
			loaded = self.storage.load_encrypted(self.filename, self.password, fmt=self.fmt, default=None)
		elif self.fmt == "pickle":
			loaded = self.storage.load_pickle(self.filename, default=None)
		else:
			loaded = self.storage.load_json(self.filename, default=None)

		self._data = dict(self.defaults)
		if isinstance(loaded, dict):
			old_ver = int(loaded.get("_schema_version", 1))
			if migrate_fn and old_ver < self.version:
				loaded = migrate_fn(dict(loaded), old_ver, self.version) or loaded
			for k, v in loaded.items():
				if k != "_schema_version":
					self._data[k] = v
		self._dirty = False
		return self._data

	def save(self) -> Path:
		payload = dict(self._data)
		payload["_schema_version"] = self.version
		if self.password:
			p = self.storage.save_encrypted(self.filename, payload, self.password, fmt=self.fmt)
		elif self.fmt == "pickle":
			p = self.storage.save_pickle(self.filename, payload)
		else:
			p = self.storage.save_json(self.filename, payload)
		self._dirty = False
		return p

	def save_if_dirty(self):
		if self._dirty:
			return self.save()
		return None

	def reset_to_defaults(self, save_now: bool = False):
		self._data = dict(self.defaults)
		self._dirty = True
		if save_now or self.auto_save:
			self.save()

	def get(self, key, default=None):
		return self._data.get(key, self.defaults.get(key, default))

	def set(self, key, value):
		self._data[key] = value
		self._dirty = True
		if self.auto_save:
			self.save()

	def update(self, mapping: dict):
		self._data.update(mapping)
		self._dirty = True
		if self.auto_save:
			self.save()

	def to_dict(self) -> dict:
		return dict(self._data)

	@property
	def dirty(self) -> bool:
		return self._dirty

	def __getitem__(self, key):
		return self._data[key]

	def __setitem__(self, key, value):
		self.set(key, value)

	def __contains__(self, key) -> bool:
		return key in self._data

	def __repr__(self) -> str:
		return f"ConfigStore(path={self.storage.root / self.filename}, keys={len(self._data)}, dirty={self._dirty})"
