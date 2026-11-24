# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# Platform detection and native shared library path resolver.
# Supports Windows, Linux, macOS, Android, and iOS.

import platform
import os
import sys
import ctypes
import struct

def is_frozen():
	return bool(getattr(sys, "frozen", False))

def embedded_data_path():
	if is_frozen() and get_platform()["os"] not in ("android", "ios") and sys.executable:
		return os.path.dirname(sys.executable)
	f = globals().get("__file__")
	return os.path.dirname(f) if f else os.getcwd()

def abspath(path):
	return os.path.abspath(path)

def match(*args, abspath=True):
	path = os.path.join(*args)
	if abspath:
		path = os.path.abspath(path)
	return path

def module_path():
	f = globals().get("__file__")
	return os.path.dirname(f) if f else os.getcwd()

def get_functype():
	return ctypes.CFUNCTYPE

def get_path(name):
	ext = get_ext()
	os_name = get_platform()["os"].lower()
	candidates = _candidate_filenames(name, os_name, ext)
	env_native = os.environ.get("PYAG_NATIVE_LIB_DIR")
	if env_native and os.path.isdir(env_native):
		for fname in candidates:
			p = os.path.join(env_native, fname)
			if os.path.exists(p):
				return p
	arch_dir = get_arch_dir()
	if arch_dir:
		for fname in candidates:
			p = os.path.join(embedded_data_path(), "lib", arch_dir, fname)
			if os.path.exists(p):
				return p
	for fname in candidates:
		p = os.path.join(embedded_data_path(), "lib", fname)
		if os.path.exists(p):
			return p
	return os.path.join(embedded_data_path(), "lib", candidates[0])

def get_platform():
	system = platform.system().lower()
	machine = platform.machine().lower()
	result = {
		"os": "unknown",
		"arch": machine,
		"is_emulator": False
	}

	if sys.platform in ("emscripten", "wasi") or "pyodide" in sys.modules:
		result["os"] = "web"
	elif sys.platform == "ios":
		result["os"] = "ios"
		if os.environ.get("SIMULATOR_DEVICE_NAME"):
			result["is_emulator"] = True
	elif system == "windows":
		result["os"] = "windows"
	elif system == "linux":
		if (
			"ANDROID_ROOT" in os.environ
			or "ANDROID_ARGUMENT" in os.environ
			or "ANDROID_DATA" in os.environ
			or hasattr(sys, "getandroidapilevel")
			or "chaquopy" in os.path.abspath(__file__).lower()
		):
			result["os"] = "android"
			if "generic" in os.environ.get("BUILD_FINGERPRINT", "").lower():
				result["is_emulator"] = True
		else:
			result["os"] = "linux"
	elif system == "darwin":
		if os.environ.get("SIMULATOR_DEVICE_NAME"):
			result["os"] = "ios"
			result["is_emulator"] = True
		else:
			result["os"] = "macos"

	return result


def get_android_activity():
	"""Return ``(activity, bridge_name)`` on Android (Chaquopy or pyjnius), else ``(None, None)``."""
	if get_platform()["os"] != "android":
		return None, None
	try:
		from .pygame_shim import _android_bridge
		act = _android_bridge.get_activity()
		if act is not None:
			return act, "chaquopy"
	except Exception:
		pass
	try:
		from jnius import autoclass
		act = autoclass("org.kivy.android.PythonActivity").mActivity
		if act is not None:
			return act, "pyjnius"
	except Exception:
		pass
	return None, None

def get_arch() -> dict:
	machine = platform.machine().lower()
	is_arm = any(keyword in machine for keyword in ["arm", "aarch64", "v7a", "v8a"])
	return {"bit": struct.calcsize("P") * 8, "machine": machine, "is arm": is_arm}

def get_arch_dir():
	arch_dir = None
	info = get_platform()
	os_name = info["os"].lower()
	arch = get_arch()
	bit = arch.get("bit", 64)
	machine = arch.get("machine", "").lower()

	if os_name == "windows":
		arch_dir = "x64" if bit == 64 else "x86"
	elif os_name == "macos":
		arch_dir = "mac"
	elif os_name == "ios":
		arch_dir = "iosimulator" if info.get("is_emulator") else "ios"
	elif os_name == "android":
		if "aarch64" in machine or "arm64" in machine or "v8a" in machine:
			arch_dir = "arm64-v8a"
		elif "arm" in machine or "v7a" in machine:
			arch_dir = "armeabi-v7a"
		elif "x86_64" in machine or "amd64" in machine:
			arch_dir = "x86_64"
		else:
			arch_dir = "x86"
	elif os_name == "linux":
		if "aarch64" in machine or "arm64" in machine:
			arch_dir = "aarch64"
		elif "arm" in machine:
			arch_dir = "armhf"
		else:
			arch_dir = "x64" if bit == 64 else "x86"
	return arch_dir

def get_ext():
	os_name = get_platform()["os"].lower()
	if os_name == "windows":
		return ".dll"
	elif os_name in ("linux", "android"):
		return ".so"
	elif os_name in ("macos", "ios"):
		return ".dylib"
	else:
		raise RuntimeError("Unsupported OS")

def _candidate_filenames(name, os_name, ext):
	base = name if name.endswith(ext) else name + ext
	candidates = [base]
	if os_name in ("android", "linux", "macos", "ios"):
		if not base.startswith("lib"):
			candidates.insert(0, "lib" + base)
		else:
			candidates.append(base[3:])
	return list(dict.fromkeys(candidates))

def load_dll(name, ot="all", WinDLL=False):
	os_name = get_platform()["os"]
	if ot != "all" and os_name != ot:
		raise OSError(f"Library '{name}' not allowed on {os_name}, expected '{ot}'")

	ext = get_ext()
	filenames = _candidate_filenames(name, os_name, ext)
	arch_dir = get_arch_dir()
	rtld_mode = getattr(ctypes, "RTLD_GLOBAL", ctypes.DEFAULT_MODE)

	# ===== ANDROID / IOS =====
	if os_name in ("android", "ios"):
		last_err = None
		# 1. Nạp trực tiếp từ jniLibs của APK (nơi Android cấp quyền thực thi native)
		for fname in filenames:
			try:
				return ctypes.CDLL(fname, mode=rtld_mode)
			except Exception as e:
				last_err = e

		# 2. Fallback: Tìm trong PYAG_NATIVE_LIB_DIR và thư mục lib/Frameworks đi kèm gói
		search_roots = []
		env_native = os.environ.get("PYAG_NATIVE_LIB_DIR")
		if env_native and os.path.isdir(env_native):
			for fname in filenames:
				p = os.path.join(env_native, fname)
				if os.path.exists(p):
					try:
						return ctypes.CDLL(p, mode=rtld_mode)
					except Exception as e:
						last_err = e
		search_roots.extend([module_path(), embedded_data_path(), os.getcwd()])
		for root in search_roots:
			for fname in filenames:
				candidates_paths = []
				if arch_dir:
					candidates_paths.append(os.path.join(root, "lib", arch_dir, fname))
				candidates_paths.append(os.path.join(root, "lib", fname))
				if os_name == "ios":
					candidates_paths.append(os.path.join(root, "Frameworks", fname))
				for p in candidates_paths:
					if os.path.exists(p):
						try:
							return ctypes.CDLL(p, mode=rtld_mode)
						except Exception as e:
							last_err = e

		raise OSError(f"[{os_name}] Cannot load {filenames[0]}: {last_err}")

	# ===== WINDOWS / LINUX / MACOS =====
	paths = []
	env_native = os.environ.get("PYAG_NATIVE_LIB_DIR")
	for fname in filenames:
		if env_native:
			paths.append(os.path.join(env_native, fname))
		if arch_dir:
			paths.append(os.path.join(module_path(), "lib", arch_dir, fname))
			paths.append(os.path.join(embedded_data_path(), "lib", arch_dir, fname))
		paths.append(os.path.join(module_path(), "lib", fname))
		paths.append(os.path.join(embedded_data_path(), "lib", fname))

	last_error = None
	for p in paths:
		if os.path.exists(p):
			try:
				if os_name == "windows":
					return ctypes.WinDLL(p) if WinDLL else ctypes.CDLL(p)
				else:
					return ctypes.CDLL(p, mode=rtld_mode)
			except Exception as e:
				last_error = e

	for fname in filenames:
		try:
			if os_name == "windows":
				return ctypes.WinDLL(fname) if WinDLL else ctypes.CDLL(fname)
			else:
				return ctypes.CDLL(fname, mode=rtld_mode)
		except Exception as e:
			last_error = e

	print(f"Cannot load library {filenames[0]}: {last_error}")