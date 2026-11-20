# -*- coding: utf-8 -*-
# app build tool (Unified Desktop & Android BeeWare Builder)
# Idea from Yukio Nozawa and continue edit and fix by ihcyna(Labubu)

import os
import sys
import re
import shutil
import glob
import ast
import struct
import sysconfig
import subprocess
import zipfile
import zlib
from pathlib import Path

# Chặn đứng ngay lập tức nếu tiến trình con của Briefcase/Gradle vô tình gọi ngược vào file này
if os.environ.get("PYAG_BUILDING_ANDROID") == "1" or os.environ.get("PYAG_BUILDING_BEEWARE") == "1":
	if __name__ == "__main__":
		sys.exit(0)

try:
	from pyaudiogaming import utils as common
	from pyaudiogaming.file import *
	from pyaudiogaming import system as sys_checker
except ImportError:
	sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
	from pyaudiogaming import utils as common
	from pyaudiogaming.file import *
	from pyaudiogaming import system as sys_checker


# ==============================================================================
# PHẦN 1: ANDROID BEEWARE (BRIEFCASE) BUILDER (Tích hợp từ android_build.py)
# ==============================================================================

ROOT = Path(__file__).resolve().parent
ABIS = {"arm64-v8a", "armeabi-v7a", "x86", "x86_64"}

# Thư mục chứa Toolchain di động (SDK, NDK, JDK, Gradle dùng chung cho mọi dự án)
PORTABLE_HOME = ROOT / "include" / "android" / "toolchain"

# Danh sách các file trình biên dịch cần loại trừ tuyệt đối khi copy vào project Android
EXCLUDE_BUILD_FILES = {
	"compile.py", "compile_2.py", "builder.py", "android_build.py", "setup.py",
	"buildapp.py", "buildtranslation.py", "@build.py"
}

EXCLUDE_DIRS = {
	"__pycache__", "android", "build", "dist", "venv", ".venv", "env", ".git", ".idea", ".vscode", "logs"
}

DESKTOP_BIN_PATTERNS = (
	"*.dll", "*.exe", "*.pyd", "*.dylib", "*.chm", "*.pdb", "*.lib", "*.exp", "*.obj", "*.a", "*.bat", "*.cmd"
)


def _save_text(content, path):
	path = Path(path)
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(str(content), encoding="utf-8")


def _load_text(path):
	return Path(path).read_text(encoding="utf-8")


def _find_real_python():
	"""Tìm trình thông dịch Python thật để tránh trường hợp sys.executable trỏ vào file đã đóng gói của compile.py."""
	exe = Path(sys.executable).resolve()
	if exe.stem.lower().startswith("python"):
		return str(exe)

	for cand in ("python3", "python", "py"):
		found = shutil.which(cand)
		if found and Path(found).resolve() != exe:
			return found

	for rel in ("python.exe", "bin/python3", "bin/python"):
		base_py = Path(sys.base_prefix) / rel
		if base_py.exists():
			return str(base_py)

	return str(exe)


def _get_portable_env():
	PORTABLE_HOME.mkdir(parents=True, exist_ok=True)
	gradle_home = PORTABLE_HOME / "gradle_cache"
	gradle_home.mkdir(parents=True, exist_ok=True)

	env = os.environ.copy()
	env.pop("PYTHONPATH", None)
	env.pop("PYTHONHOME", None)
	env.pop("PYTHONSTARTUP", None)
	env["PYTHONNOUSERSITE"] = "1"
	env["PYTHONUTF8"] = "1"
	env["PYTHONIOENCODING"] = "utf-8"
	env["BRIEFCASE_HOME"] = str(PORTABLE_HOME)
	env["GRADLE_USER_HOME"] = str(gradle_home)
	env["PYAG_BUILDING_ANDROID"] = "1"
	env["PYAG_BUILDING_BEEWARE"] = "1"

	tools_dir = PORTABLE_HOME / "tools"
	if tools_dir.is_dir():
		for jdk_cand in sorted(tools_dir.glob("java*"), reverse=True):
			if (jdk_cand / "bin").is_dir():
				env["JAVA_HOME"] = str(jdk_cand)
				env["PATH"] = str(jdk_cand / "bin") + os.pathsep + env.get("PATH", "")
				break
		sdk_cand = tools_dir / "android_sdk"
		if sdk_cand.is_dir():
			env["ANDROID_HOME"] = str(sdk_cand)
			env["ANDROID_SDK_ROOT"] = str(sdk_cand)

	return env


def _ensure_briefcase(env=None):
	run_env = env or _get_portable_env()
	py_exe = _find_real_python()
	try:
		subprocess.run(
			[py_exe, "-I", "-m", "briefcase", "--version"],
			stdout=subprocess.DEVNULL,
			stderr=subprocess.DEVNULL,
			env=run_env,
			check=True
		)
	except (subprocess.CalledProcessError, FileNotFoundError):
		print("[BeeWare] Installing Briefcase automatically...")
		subprocess.run(
			[py_exe, "-I", "-m", "pip", "install", "briefcase"],
			env=run_env,
			check=True
		)


def _run_briefcase(args_list, cwd, env):
	py_exe = _find_real_python()
	# Chạy với cờ -I (Isolated Mode) để cô lập hoàn toàn khỏi thư mục hiện tại và tránh gọi nhầm compile.py
	cmd = [py_exe, "-I", "-m", "briefcase"] + list(args_list)
	res = subprocess.run(cmd, cwd=cwd, env=env)
	if res.returncode != 0:
		raise RuntimeError(
			f"Briefcase failed at command: briefcase {' '.join(args_list)} (exit code {res.returncode})"
		)


def _normalize_abis(arch=None):
	raw = arch if isinstance(arch, list) else [arch or "arm64-v8a"]
	# Lưu ý: nhiều người dùng để arch="x64" từ cấu hình Windows, trên đt Android cần ưu tiên arm64-v8a
	aliases = {
		"a64": "arm64-v8a",
		"arm64": "arm64-v8a",
		"aarch64": "arm64-v8a",
		"x64": "arm64-v8a",
		"arm": "armeabi-v7a",
		"armv7": "armeabi-v7a",
		"a86": "x86"
	}
	abis = []
	for a in raw:
		if not a or str(a).lower() in ("null", "none", "auto"):
			abis.append("arm64-v8a")
		else:
			abis.append(aliases.get(str(a).lower().strip(), str(a).strip()))
	abis = list(dict.fromkeys(abis))
	if any(a not in ABIS for a in abis):
		raise ValueError(f"Unsupported Android ABI: {abis}")
	if sys.version_info >= (3, 12):
		supported_64 = [a for a in abis if a in ("arm64-v8a", "x86_64")]
		if supported_64 != abis:
			print(
				f"[BeeWare] Notice: Python {sys.version_info.major}.{sys.version_info.minor} on Android "
				f"only supports 64-bit ABIs. Adjusting ABIs {abis} -> {supported_64 or ['arm64-v8a']}"
			)
			abis = supported_64 or ["arm64-v8a"]
	return abis


def _collect_and_verify_libs(abis, app_root, staging_native_dir, package_lib_dir):
	if staging_native_dir.exists():
		shutil.rmtree(staging_native_dir)
	staging_native_dir.mkdir(parents=True, exist_ok=True)
	if package_lib_dir.exists():
		shutil.rmtree(package_lib_dir)

	for abi in abis:
		src_dirs = [
			ROOT / "lib" / abi,
			app_root / "lib" / abi,
			app_root / "pyaudiogaming" / "lib" / abi
		]
		target_jni = staging_native_dir / abi
		target_jni.mkdir(parents=True, exist_ok=True)

		copied_files = set()
		for sdir in src_dirs:
			if not sdir.is_dir():
				continue
			for so_file in sdir.glob("*.so"):
				fname = so_file.name
				lib_fname = fname if fname.startswith("lib") else f"lib{fname}"
				shutil.copy2(so_file, target_jni / lib_fname)
				copied_files.add(lib_fname)

		for required in ("libbass.so", "libbassmix.so", "libbass_fx.so"):
			if required not in copied_files:
				raise ValueError(
					f"Missing required Android library '{required}' for ABI '{abi}'. "
					f"Expected inside: {ROOT / 'lib' / abi}"
				)


def _patch_android_manifest(manifest_path):
	if not manifest_path.exists():
		return
	text = _load_text(manifest_path)
	# Sửa các quyền bị thiếu tiền tố android.permission.
	for short_perm in ("INTERNET", "ACCESS_NETWORK_STATE", "RECORD_AUDIO", "MODIFY_AUDIO_SETTINGS", "WAKE_LOCK", "VIBRATE", "POST_NOTIFICATIONS", "USE_FULL_SCREEN_INTENT"):
		bad_tag = f'<uses-permission android:name="{short_perm}"/>'
		good_tag = f'<uses-permission android:name="android.permission.{short_perm}"/>'
		if bad_tag in text:
			if good_tag in text:
				text = text.replace(bad_tag, "")
			else:
				text = text.replace(bad_tag, good_tag)
	if 'android:extractNativeLibs=' not in text and '<application' in text:
		text = text.replace('<application', '<application\n        android:extractNativeLibs="true"', 1)
	if 'android:showWhenLocked=' not in text and '<activity' in text:
		text = text.replace('<activity', '<activity\n            android:showWhenLocked="true"\n            android:turnScreenOn="true"', 1)
	_save_text(text, manifest_path)


def _inject_gradle_jnilibs(workspace, slug, staging_native_dir, abis):
	gradle_app_dir = workspace / "build" / slug / "android" / "gradle" / "app"
	if not gradle_app_dir.exists():
		raise RuntimeError(f"Gradle project directory not found at: {gradle_app_dir}")

	jni_libs_dir = gradle_app_dir / "src" / "main" / "jniLibs"
	if jni_libs_dir.exists():
		shutil.rmtree(jni_libs_dir)
	jni_libs_dir.mkdir(parents=True, exist_ok=True)

	for abi in abis:
		src_abi = staging_native_dir / abi
		dst_abi = jni_libs_dir / abi
		if src_abi.is_dir():
			shutil.copytree(src_abi, dst_abi, dirs_exist_ok=True)
			so_list = [p.name for p in dst_abi.glob("*.so")]
			print(f"[BeeWare] Injected {len(so_list)} native libraries into jniLibs/{abi}: {', '.join(so_list)}")

	java_src_dir = ROOT / "pygame_shim" / "java"
	if not java_src_dir.is_dir():
		java_src_dir = ROOT / "include" / "android" / "java"
	if java_src_dir.is_dir():
		gradle_java_dir = gradle_app_dir / "src" / "main" / "java"
		shutil.copytree(java_src_dir, gradle_java_dir, dirs_exist_ok=True)
		java_files = [p.name for p in java_src_dir.rglob("*.java")]
		if java_files:
			print(f"[BeeWare] Injected Android native Java bridge: {', '.join(java_files)}")

	_patch_android_manifest(gradle_app_dir / "src" / "main" / "AndroidManifest.xml")

	build_gradle_path = gradle_app_dir / "build.gradle"
	if build_gradle_path.exists():
		gradle_text = _load_text(build_gradle_path)
		marker = "// [PYAUDIOGAMING_JNILIBS_PATCH]"
		if marker in gradle_text:
			gradle_text = gradle_text.split(marker)[0].rstrip()

		abi_filters = ", ".join(f'"{a}"' for a in abis)
		patch_block = f"""
{marker}
android {{
    defaultConfig {{
        targetSdkVersion 34
        ndk {{
            abiFilters.clear()
            abiFilters {abi_filters}
        }}
        python {{
            extractPackages "*"
            pyc {{
                src true
            }}
        }}
    }}
    buildTypes {{
        release {{
            signingConfig signingConfigs.debug
        }}
    }}
    packagingOptions {{
        jniLibs {{
            useLegacyPackaging true
        }}
    }}
}}
"""
		_save_text(gradle_text + "\n" + patch_block, build_gradle_path)


def _is_apk_signed(apk_path):
	apk_path = Path(apk_path)
	if not apk_path.is_file() or apk_path.name.lower().endswith("-unsigned.apk"):
		return False
	try:
		with zipfile.ZipFile(apk_path, "r") as zf:
			names = zf.namelist()
			if any(
				n.startswith("META-INF/") and n.upper().endswith((".RSA", ".DSA", ".EC"))
				for n in names
			):
				return True
		with apk_path.open("rb") as f:
			size = apk_path.stat().st_size
			read_len = min(size, 65536 + 1024)
			f.seek(max(0, size - read_len))
			tail = f.read()
			if b"APK Sig Block 42" in tail:
				return True
	except Exception:
		return False
	return False


def _ensure_apk_signed(apk_path, env):
	apk_path = Path(apk_path)
	if _is_apk_signed(apk_path):
		return apk_path

	print(f"[BeeWare] APK '{apk_path.name}' is unsigned. Signing with Android debug keystore...")
	sdk_dir = PORTABLE_HOME / "tools" / "android_sdk"
	signers = sorted(sdk_dir.glob("build-tools/*/apksigner.bat"), reverse=True) if sdk_dir.exists() else []
	if not signers:
		raise RuntimeError(f"APK '{apk_path}' is unsigned and apksigner was not found in {sdk_dir}")

	keystore = Path.home() / ".android" / "debug.keystore"
	if not keystore.exists():
		keystore = PORTABLE_HOME / "debug.keystore"
	if not keystore.exists():
		keystore.parent.mkdir(parents=True, exist_ok=True)
		keytool_cands = sorted((PORTABLE_HOME / "tools").glob("java*/bin/keytool.exe"), reverse=True)
		keytool = str(keytool_cands[0]) if keytool_cands else "keytool"
		subprocess.run(
			[
				keytool, "-genkeypair", "-v",
				"-keystore", str(keystore),
				"-storepass", "android",
				"-alias", "androiddebugkey",
				"-keypass", "android",
				"-keyalg", "RSA",
				"-keysize", "2048",
				"-validity", "10000",
				"-dname", "CN=Android Debug,O=Android,C=US"
			],
			env=env,
			check=True
		)

	subprocess.run(
		[
			str(signers[0]), "sign",
			"--ks", str(keystore),
			"--ks-pass", "pass:android",
			"--ks-key-alias", "androiddebugkey",
			"--key-pass", "pass:android",
			str(apk_path)
		],
		env=env,
		check=True
	)
	return apk_path


def _chacha20_xor(key, nonce, data, counter=1):
	"""Pure-Python RFC 8439 ChaCha20 stream cipher (matches native C vault byte-for-byte)."""
	if len(key) != 32 or len(nonce) != 12:
		raise ValueError("ChaCha20 requires 32-byte key and 12-byte nonce")
	consts = (0x61707865, 0x3320646E, 0x79622D32, 0x6B206574)
	k_words = struct.unpack("<8I", key)
	n_words = struct.unpack("<3I", nonce)
	out = bytearray(len(data))
	pos = 0
	n = len(data)
	blk_cnt = counter & 0xFFFFFFFF
	while pos < n:
		st = [
			consts[0], consts[1], consts[2], consts[3],
			k_words[0], k_words[1], k_words[2], k_words[3],
			k_words[4], k_words[5], k_words[6], k_words[7],
			blk_cnt, n_words[0], n_words[1], n_words[2],
		]
		x = st[:]
		for _ in range(10):
			for a, b, c, d in (
				(0, 4, 8, 12), (1, 5, 9, 13), (2, 6, 10, 14), (3, 7, 11, 15),
				(0, 5, 10, 15), (1, 6, 11, 12), (2, 7, 8, 13), (3, 4, 9, 14),
			):
				x[a] = (x[a] + x[b]) & 0xFFFFFFFF; v = x[d] ^ x[a]; x[d] = ((v << 16) | (v >> 16)) & 0xFFFFFFFF
				x[c] = (x[c] + x[d]) & 0xFFFFFFFF; v = x[b] ^ x[c]; x[b] = ((v << 12) | (v >> 20)) & 0xFFFFFFFF
				x[a] = (x[a] + x[b]) & 0xFFFFFFFF; v = x[d] ^ x[a]; x[d] = ((v << 8) | (v >> 24)) & 0xFFFFFFFF
				x[c] = (x[c] + x[d]) & 0xFFFFFFFF; v = x[b] ^ x[c]; x[b] = ((v << 7) | (v >> 25)) & 0xFFFFFFFF
		ks = struct.pack("<16I", *(((x[i] + st[i]) & 0xFFFFFFFF) for i in range(16)))
		chunk = min(64, n - pos)
		for i in range(chunk):
			out[pos + i] = data[pos + i] ^ ks[i]
		pos += chunk
		blk_cnt = (blk_cnt + 1) & 0xFFFFFFFF
	return bytes(out)


def _find_android_ndk_bin():
	"""Locate Android NDK LLVM prebuilt bin directory if installed."""
	candidates = []
	for env_var in ("ANDROID_NDK_HOME", "ANDROID_NDK_ROOT", "NDK_HOME"):
		val = os.environ.get(env_var)
		if val:
			candidates.append(Path(val))
	for sdk_root in (
		PORTABLE_HOME / "tools" / "android_sdk",
		Path(os.environ.get("ANDROID_HOME", "")) if os.environ.get("ANDROID_HOME") else None,
		Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" if os.environ.get("LOCALAPPDATA") else None,
	):
		if sdk_root and (sdk_root / "ndk").is_dir():
			candidates.extend(sorted((sdk_root / "ndk").iterdir(), reverse=True))
	host_tag = "windows-x86_64" if os.name == "nt" else ("darwin-x86_64" if sys.platform == "darwin" else "linux-x86_64")
	for ndk_dir in candidates:
		if not ndk_dir or not ndk_dir.is_dir():
			continue
		bin_dir = ndk_dir / "toolchains" / "llvm" / "prebuilt" / host_tag / "bin"
		if bin_dir.is_dir():
			return bin_dir
	return None


def _compile_native_vault_so(key, abis, staging_native_dir):
	"""Auto-compile libpyag_vault.so with obfuscated random key for each ABI using Android NDK."""
	ndk_bin = _find_android_ndk_bin()
	if ndk_bin is None:
		return False

	abi_clang = {
		"arm64-v8a": "aarch64-linux-android21-clang",
		"armeabi-v7a": "armv7a-linux-androideabi21-clang",
		"x86_64": "x86_64-linux-android21-clang",
		"x86": "i686-linux-android21-clang",
	}
	ext = ".cmd" if os.name == "nt" else ""
	strip_exe = ndk_bin / ("llvm-strip.exe" if os.name == "nt" else "llvm-strip")

	mask = os.urandom(32)
	obf = bytes(key[i] ^ mask[i] for i in range(32))
	obf_c = ", ".join(str(b) for b in obf)
	mask_c = ", ".join(str(b) for b in mask)

	c_code = f"""#include <stdint.h>
#include <stddef.h>

static inline uint32_t rotl32(uint32_t v, int c) {{ return (v << c) | (v >> (32 - c)); }}
static inline uint32_t load32(const uint8_t *p) {{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}}
static inline void store32(uint8_t *p, uint32_t v) {{
    p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); p[2] = (uint8_t)(v >> 16); p[3] = (uint8_t)(v >> 24);
}}
static void qr(uint32_t *x, int a, int b, int c, int d) {{
    x[a] += x[b]; x[d] = rotl32(x[d] ^ x[a], 16);
    x[c] += x[d]; x[b] = rotl32(x[b] ^ x[c], 12);
    x[a] += x[b]; x[d] = rotl32(x[d] ^ x[a], 8);
    x[c] += x[d]; x[b] = rotl32(x[b] ^ x[c], 7);
}}

__attribute__((visibility("default")))
int pyag_unlock(const uint8_t *nonce12, uint8_t *buf, size_t len) {{
    if (!nonce12 || !buf) return -1;
    static const uint8_t k_a[32] = {{{obf_c}}};
    static const uint8_t k_b[32] = {{{mask_c}}};
    uint8_t key[32];
    for (int i = 0; i < 32; i++) key[i] = (uint8_t)(k_a[i] ^ k_b[i]);
    uint32_t st[16];
    st[0] = 0x61707865u; st[1] = 0x3320646eu; st[2] = 0x79622d32u; st[3] = 0x6b206574u;
    for (int i = 0; i < 8; i++) st[4 + i] = load32(key + i * 4);
    st[12] = 1u;
    st[13] = load32(nonce12);
    st[14] = load32(nonce12 + 4);
    st[15] = load32(nonce12 + 8);
    size_t pos = 0;
    while (pos < len) {{
        uint32_t x[16];
        for (int i = 0; i < 16; i++) x[i] = st[i];
        for (int r = 0; r < 10; r++) {{
            qr(x, 0, 4, 8, 12); qr(x, 1, 5, 9, 13); qr(x, 2, 6, 10, 14); qr(x, 3, 7, 11, 15);
            qr(x, 0, 5, 10, 15); qr(x, 1, 6, 11, 12); qr(x, 2, 7, 8, 13); qr(x, 3, 4, 9, 14);
        }}
        uint8_t ks[64];
        for (int i = 0; i < 16; i++) store32(ks + i * 4, x[i] + st[i]);
        size_t chunk = (len - pos < 64) ? (len - pos) : 64;
        for (size_t i = 0; i < chunk; i++) buf[pos + i] ^= ks[i];
        pos += chunk;
        st[12]++;
    }}
    for (int i = 0; i < 32; i++) key[i] = 0;
    return 0;
}}
"""
	tmp_c = staging_native_dir / "_pyag_vault_tmp.c"
	tmp_c.write_text(c_code, encoding="utf-8")
	try:
		for abi in abis:
			clang_name = abi_clang.get(abi)
			if not clang_name:
				return False
			clang_exe = ndk_bin / (clang_name + ext)
			if not clang_exe.exists():
				clang_exe = ndk_bin / clang_name
			if not clang_exe.exists():
				return False
			out_so = staging_native_dir / abi / "libpyag_vault.so"
			out_so.parent.mkdir(parents=True, exist_ok=True)
			cmd = [
				str(clang_exe), "-shared", "-fPIC", "-O3",
				"-fvisibility=hidden", "-s",
				str(tmp_c), "-o", str(out_so)
			]
			res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			if res.returncode != 0 or not out_so.is_file():
				return False
			if strip_exe.exists():
				subprocess.run([str(strip_exe), "--strip-unneeded", str(out_so)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
		return True
	finally:
		try:
			if tmp_c.exists():
				tmp_c.unlink()
		except OSError:
			pass


def _pack_android_sources(app_src, abis, staging_native_dir):
	"""Encrypt all game .py modules into _app.pkg with a per-build random 256-bit key and remove plaintext .py files."""
	skip_top = {"pyaudiogaming", "pygame", "res", "lib", "include", "utils"}
	entries = []
	py_files_to_remove = []

	for py_path in sorted(app_src.rglob("*.py")):
		rel = py_path.relative_to(app_src)
		if rel.parts[0] in skip_top:
			continue
		if len(rel.parts) == 1 and rel.name in ("__init__.py", "__main__.py"):
			continue
		is_pkg = (rel.name == "__init__.py")
		if is_pkg:
			mod_name = ".".join(rel.parts[:-1])
		else:
			mod_name = ".".join(rel.with_suffix("").parts)
		if not mod_name:
			continue
		src_bytes = py_path.read_bytes()
		rel_posix = rel.as_posix()
		entries.append((mod_name, is_pkg, rel_posix, src_bytes))
		py_files_to_remove.append(py_path)

	if not entries:
		return "none", None

	buf = bytearray()
	buf.extend(struct.pack("<I", len(entries)))
	for mod_name, is_pkg, rel_posix, src_bytes in entries:
		nb = mod_name.encode("utf-8")
		rb = rel_posix.encode("utf-8")
		buf.extend(struct.pack("<H", len(nb)))
		buf.extend(nb)
		buf.append(1 if is_pkg else 0)
		buf.extend(struct.pack("<H", len(rb)))
		buf.extend(rb)
		buf.extend(struct.pack("<I", len(src_bytes)))
		buf.extend(src_bytes)

	compressed = zlib.compress(bytes(buf), 9)
	key = os.urandom(32)
	nonce = os.urandom(12)
	ciphertext = _chacha20_xor(key, nonce, compressed, counter=1)

	pkg_path = app_src / "_app.pkg"
	pkg_path.write_bytes(b"PYAG" + nonce + ciphertext)

	# Remove all packed plaintext .py files and clean empty package directories
	for py_path in py_files_to_remove:
		try:
			py_path.unlink()
		except OSError:
			pass
	for dir_path in sorted(app_src.rglob("*"), reverse=True):
		if dir_path.is_dir() and dir_path.relative_to(app_src).parts[0] not in skip_top:
			try:
				if not any(dir_path.iterdir()):
					dir_path.rmdir()
			except OSError:
				pass

	native_ok = _compile_native_vault_so(key, abis, staging_native_dir)
	if native_ok:
		print(f"[BeeWare] Protected {len(entries)} Python modules into _app.pkg (native C ChaCha20 libpyag_vault.so + random 256-bit key).")
		return "native", None

	print(f"[BeeWare] Protected {len(entries)} Python modules into _app.pkg (ChaCha20 + random 256-bit key; install Android NDK to auto-compile native libpyag_vault.so).")
	return "py", key


def _build_vault_bootstrap_snippet(vault_mode, vault_key):
	"""Generate RAM-only sys.meta_path import hook snippet for __main__.py."""
	if vault_mode == "none":
		return ""
	if vault_mode == "native":
		unlock_fn = r"""def _vault_decrypt(nonce, raw):
    import ctypes
    lib = None
    for _cand in ("libpyag_vault.so", "pyag_vault"):
        try:
            lib = ctypes.CDLL(_cand)
            break
        except Exception:
            pass
    if lib is None:
        from pyaudiogaming import system as _sys_chk
        lib = _sys_chk.load_dll("libpyag_vault")
    buf = ctypes.create_string_buffer(raw, len(raw))
    fn = lib.pyag_unlock
    fn.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
    fn.restype = ctypes.c_int
    if fn(nonce, buf, len(raw)) != 0:
        raise RuntimeError("Native vault unlock failed")
    return buf.raw
"""
	else:
		mask = os.urandom(32)
		obf = bytes(vault_key[i] ^ mask[i] for i in range(32))
		unlock_fn = f"""_VAULT_A = {list(obf)!r}
_VAULT_B = {list(mask)!r}


def _vault_decrypt(nonce, raw):
    import struct
    key = bytes(_VAULT_A[i] ^ _VAULT_B[i] for i in range(32))
    consts = (0x61707865, 0x3320646E, 0x79622D32, 0x6B206574)
    kw = struct.unpack("<8I", key)
    nw = struct.unpack("<3I", nonce)
    out = bytearray(len(raw))
    pos, n, cnt = 0, len(raw), 1
    while pos < n:
        st = [consts[0], consts[1], consts[2], consts[3], kw[0], kw[1], kw[2], kw[3], kw[4], kw[5], kw[6], kw[7], cnt, nw[0], nw[1], nw[2]]
        x = st[:]
        for _ in range(10):
            for a, b, c, d in ((0,4,8,12),(1,5,9,13),(2,6,10,14),(3,7,11,15),(0,5,10,15),(1,6,11,12),(2,7,8,13),(3,4,9,14)):
                x[a] = (x[a] + x[b]) & 0xFFFFFFFF; v = x[d] ^ x[a]; x[d] = ((v << 16) | (v >> 16)) & 0xFFFFFFFF
                x[c] = (x[c] + x[d]) & 0xFFFFFFFF; v = x[b] ^ x[c]; x[b] = ((v << 12) | (v >> 20)) & 0xFFFFFFFF
                x[a] = (x[a] + x[b]) & 0xFFFFFFFF; v = x[d] ^ x[a]; x[d] = ((v << 8) | (v >> 24)) & 0xFFFFFFFF
                x[c] = (x[c] + x[d]) & 0xFFFFFFFF; v = x[b] ^ x[c]; x[b] = ((v << 7) | (v >> 25)) & 0xFFFFFFFF
        ks = struct.pack("<16I", *(((x[i] + st[i]) & 0xFFFFFFFF) for i in range(16)))
        ch = min(64, n - pos)
        for i in range(ch):
            out[pos + i] = raw[pos + i] ^ ks[i]
        pos += ch
        cnt = (cnt + 1) & 0xFFFFFFFF
    return bytes(out)
"""

	loader_code = r"""
class _VaultLoader:
    def __init__(self, fullname, is_pkg, rel_path, src_bytes, app_dir):
        self.fullname = fullname
        self.is_pkg = is_pkg
        self.rel_path = rel_path
        self.src_bytes = src_bytes
        self.app_dir = app_dir

    def create_module(self, spec):
        return None

    def get_code(self, fullname):
        return compile(self.src_bytes, f"<{self.fullname}>", "exec")

    def get_source(self, fullname):
        return None

    def is_package(self, fullname):
        return self.is_pkg

    def exec_module(self, module):
        module.__file__ = os.path.join(self.app_dir, self.rel_path)
        if self.is_pkg:
            module.__path__ = [os.path.dirname(module.__file__)]
            module.__package__ = self.fullname
        else:
            module.__package__ = self.fullname.rpartition(".")[0]
        exec(self.get_code(self.fullname), module.__dict__)


class _VaultFinder:
    def __init__(self, mods, app_dir):
        self._mods = mods
        self._app_dir = app_dir

    def find_spec(self, fullname, path=None, target=None):
        entry = self._mods.get(fullname)
        if entry is None:
            return None
        import importlib.machinery
        is_pkg, rel_path, src_bytes = entry
        loader = _VaultLoader(fullname, is_pkg, rel_path, src_bytes, self._app_dir)
        spec = importlib.machinery.ModuleSpec(fullname, loader, is_package=is_pkg)
        if is_pkg:
            spec.submodule_search_locations = [os.path.dirname(os.path.join(self._app_dir, rel_path))]
        return spec


def _install_vault_hook():
    import struct, zlib
    pkg_file = os.path.join(_APP_DIR, "_app.pkg")
    if not os.path.isfile(pkg_file):
        return
    with open(pkg_file, "rb") as _f:
        blob = _f.read()
    if len(blob) < 16 or blob[:4] != b"PYAG":
        raise RuntimeError("Invalid encrypted application bundle")
    nonce, enc = blob[4:16], blob[16:]
    plain = zlib.decompress(_vault_decrypt(nonce, enc))
    off = 0
    (count,) = struct.unpack_from("<I", plain, off); off += 4
    mods = {}
    for _ in range(count):
        (nlen,) = struct.unpack_from("<H", plain, off); off += 2
        mname = plain[off:off + nlen].decode("utf-8"); off += nlen
        is_pkg = bool(plain[off]); off += 1
        (rlen,) = struct.unpack_from("<H", plain, off); off += 2
        rpath = plain[off:off + rlen].decode("utf-8"); off += rlen
        (slen,) = struct.unpack_from("<I", plain, off); off += 4
        sbytes = plain[off:off + slen]; off += slen
        mods[mname] = (is_pkg, rpath, sbytes)
    sys.meta_path.insert(0, _VaultFinder(mods, _APP_DIR))


_install_vault_hook()
"""
	return unlock_fn + loader_code


def _is_ignored_app_dir(item_path, root_path):
	if item_path.resolve() == root_path.resolve():
		return True
	name_low = item_path.name.lower()
	if name_low in EXCLUDE_DIRS or name_low in ("pyaudiogaming", "server", "lib", "include", "scripts"):
		return True
	if name_low.startswith((".", "#", "@", "venv")):
		return True
	if (item_path / "pyvenv.cfg").exists() or (item_path / "Lib" / "site-packages").exists():
		return True
	return False


def prepare_android(project, name, data=(), arch=None, extra_reqs=()):
	entry = Path(str(project) + ".py").resolve()
	if not entry.is_file():
		raise ValueError(f"Entry script does not exist: {entry}")

	abis = _normalize_abis(arch)
	slug = re.sub(r"[^a-z0-9_]", "", str(name).lower().replace(" ", "_"))
	slug = re.sub(r"_+", "_", slug).strip("_")
	if not slug or not slug[0].isalpha():
		slug = "app_" + slug
	if slug in ("main", "test", "app", "sys", "os", "pyaudiogaming"):
		slug = "app_" + slug
	if any(c in str(name) for c in "\r\n"):
		raise ValueError("Application name must be a single line")

	workspace = ROOT / "include" / "android" / "projects" / slug
	app_src = workspace / "src" / slug

	if app_src.exists():
		shutil.rmtree(app_src)
	app_src.mkdir(parents=True, exist_ok=True)

	package = app_src / "pyaudiogaming"
	package.mkdir(parents=True, exist_ok=True)
	for item in ROOT.glob("*.py"):
		if item.name.lower() not in EXCLUDE_BUILD_FILES and not item.name.lower().startswith("compile"):
			shutil.copy2(item, package / item.name)

	for folder in ("sound_modules", "accessible_output2", "include", "utils"):
		src_folder = ROOT / folder
		if src_folder.is_dir():
			ignore_fn = shutil.ignore_patterns(
				"__pycache__", "*.pyc", "desktop.ini", "android",
				"compile*.py", "android_build.py", "builder.py",
				*DESKTOP_BIN_PATTERNS
			)
			shutil.copytree(src_folder, package / folder, dirs_exist_ok=True, ignore=ignore_fn)

	app_root = entry.parent
	for item in app_root.iterdir():
		if item.is_file() and item.suffix == ".py":
			fname_low = item.name.lower()
			if (
				fname_low not in EXCLUDE_BUILD_FILES
				and not fname_low.startswith(("compile", "#", "@"))
			):
				shutil.copy2(item, app_src / item.name)
		elif item.is_dir() and (item / "__init__.py").exists() and not _is_ignored_app_dir(item, ROOT):
			shutil.copytree(
				item,
				app_src / item.name,
				dirs_exist_ok=True,
				ignore=shutil.ignore_patterns(
					"__pycache__", "*.pyc", "desktop.ini",
					"compile*.py", "android_build.py", "builder.py",
					"Lib", "Scripts", "Include",
					*DESKTOP_BIN_PATTERNS
				)
			)

	shutil.copy2(entry, app_src / "main.py")
	shutil.copy2(entry, app_src / "_pyag_entry.py")

	pygame_shim_src = ROOT / "pygame_shim"
	if pygame_shim_src.is_dir():
		shutil.copytree(
			pygame_shim_src,
			app_src / "pygame",
			dirs_exist_ok=True,
			ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "desktop.ini", "java")
		)
		print("[BeeWare] Embedded native Android pygame shim into app package.")

	staging_native_dir = workspace / "native_libs"
	package_lib_dir = package / "lib"
	_collect_and_verify_libs(abis, app_root, staging_native_dir, package_lib_dir)

	vault_mode, vault_key = _pack_android_sources(app_src, abis, staging_native_dir)
	vault_snippet = _build_vault_bootstrap_snippet(vault_mode, vault_key)

	_save_text("# Auto-generated package init\n", app_src / "__init__.py")
	bootstrap_code = r"""# -*- coding: utf-8 -*-
import os
import runpy
import sys
import threading
import traceback

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)
sys.frozen = True
try:
    os.chdir(_APP_DIR)
except Exception:
    pass

_ANDROID_UI = False
try:
    import pygame
    if hasattr(pygame, "_android_bridge") and pygame._android_bridge.is_android_java_available():
        _ANDROID_UI = bool(pygame._android_bridge.bootstrap_android())
except Exception as _e:
    print(f"[Bootstrap] Warning initializing Android pygame view: {_e}")
    traceback.print_exc()

try:
    from pyaudiogaming import system as _sys_chk
    if _sys_chk.get_platform().get("os") == "android":
        for _core_lib in ("libbass", "libbassmix", "libbass_fx"):
            try:
                _sys_chk.load_dll(_core_lib)
            except Exception as _e:
                print(f"[Bootstrap] Warning preloading {_core_lib}: {_e}")
except Exception:
    pass
""" + "\n" + vault_snippet + r"""

def _show_android_status(msg, is_error=False):
    try:
        import pygame
        if hasattr(pygame, "_android_bridge") and hasattr(pygame._android_bridge, "set_overlay_text"):
            pygame._android_bridge.set_overlay_text(msg, is_error=is_error)
    except Exception:
        pass


def _shutdown_android_app():
    try:
        from pyaudiogaming.sound_modules import control as _snd_ctrl
        _snd_ctrl.shutdown_sound()
    except Exception:
        pass
    try:
        import pygame
        if hasattr(pygame, "_android_bridge") and hasattr(pygame._android_bridge, "close_app"):
            pygame._android_bridge.close_app()
    except Exception:
        pass


def _show_android_error(title, tb):
    try:
        import pygame
        if hasattr(pygame, "_android_bridge") and hasattr(pygame._android_bridge, "show_error_dialog"):
            if pygame._android_bridge.show_error_dialog(title, tb):
                return
    except Exception:
        pass
    _show_android_status(title + ":\n" + tb, is_error=True)


def _run_entry():
    _clean_exit = False
    try:
        _show_android_status("Starting application...", is_error=False)
        runpy.run_module("_pyag_entry", run_name="__main__", alter_sys=True)
        _clean_exit = True
    except SystemExit:
        _clean_exit = True
    except Exception:
        tb = traceback.format_exc()
        print(tb)
        _show_android_error("Startup Error", tb)
    if _clean_exit:
        _shutdown_android_app()


if _ANDROID_UI:
    _GAME_THREAD = threading.Thread(target=_run_entry, name="PyAudioGamingMain", daemon=True)
    _GAME_THREAD.start()
else:
    _run_entry()
"""
	_save_text(bootstrap_code, app_src / "__main__.py")

	for value in (data or ()):
		relative = Path(value)
		if relative.is_absolute() or ".." in relative.parts:
			raise ValueError(f"Data must be a relative path inside the application: {value}")
		if relative.suffix.lower() in (".dll", ".exe", ".pyd", ".dylib", ".lib", ".pdb"):
			print(f"[BeeWare] Skipping desktop binary in Android data: {value}")
			continue
		original = app_root / relative
		if not original.exists():
			original = Path(value).resolve()
		if not original.exists():
			raise ValueError(f"Missing application data: {original}")
		destination = app_src / relative
		if original.is_dir():
			data_ignore = shutil.ignore_patterns(
				"__pycache__", "*.pyc", "desktop.ini",
				"x64", "x86", "mac", "ios", "iosimulator", "armhf", "aarch64", "a86",
				*DESKTOP_BIN_PATTERNS
			)
			shutil.copytree(original, destination, dirs_exist_ok=True, ignore=data_ignore)
		else:
			destination.parent.mkdir(parents=True, exist_ok=True)
			shutil.copy2(original, destination)

	_save_text("MIT License\n", workspace / "LICENSE")

	default_reqs = ["pycryptodome", "cryptography", "polib"]
	for r in (extra_reqs or ()):
		r_clean = str(r).strip()
		if r_clean and not r_clean.startswith("-") and r_clean not in default_reqs:
			default_reqs.append(r_clean)

	req_formatted = ",\n    ".join(f'"{r}"' for r in default_reqs)
	abis_formatted = ", ".join(f'"{a}"' for a in abis)
	safe_name = str(name).replace('"', '\\"')
	pyproject_content = f"""[build-system]
requires = ["briefcase"]

[tool.briefcase]
project_name = "{safe_name}"
bundle = "org.pyaudiogaming"
version = "0.1.0"
url = "https://pyaudiogaming.org"
license = "MIT"
license-files = ["LICENSE"]
author = "PyAudioGaming"
author_email = "dev@pyaudiogaming.org"

[tool.briefcase.app.{slug}]
formal_name = "{safe_name}"
description = "{safe_name} built with PyAudioGaming BeeWare Backend"
sources = ["src/{slug}"]
requires = [
    {req_formatted}
]

[tool.briefcase.app.{slug}.android]
requires = []
android_abis = [{abis_formatted}]
build_gradle_dependencies = [
    "androidx.appcompat:appcompat:1.0.2",
    "androidx.constraintlayout:constraintlayout:1.1.3",
    "androidx.swiperefreshlayout:swiperefreshlayout:1.1.0",
]

[tool.briefcase.app.{slug}.android.permission]
"android.permission.INTERNET" = true
"android.permission.ACCESS_NETWORK_STATE" = true
"android.permission.RECORD_AUDIO" = true
"android.permission.MODIFY_AUDIO_SETTINGS" = true
"android.permission.WAKE_LOCK" = true
"android.permission.VIBRATE" = true
"android.permission.POST_NOTIFICATIONS" = true
"android.permission.USE_FULL_SCREEN_INTENT" = true
"""
	_save_text(pyproject_content, workspace / "pyproject.toml")
	return workspace, slug, abis, staging_native_dir, app_root


def build_android(project, name, data=(), arch=None, args=(), prepare_only=False, rename_file=None, out_dir=None):
	extra_reqs = [a for a in (args or ()) if not str(a).startswith("-")]
	clean_rebuild = "--clean" in (args or ()) or "--clean" in sys.argv

	workspace, slug, abis, staging_native_dir, app_root = prepare_android(
		project, name, data, arch, extra_reqs=extra_reqs
	)
	print(f"[BeeWare] Android workspace prepared: {workspace}")
	print(f"[BeeWare] Portable Toolchain location: {PORTABLE_HOME}")

	if prepare_only:
		return True

	env = _get_portable_env()
	_ensure_briefcase(env)

	gradle_project_dir = workspace / "build" / slug / "android" / "gradle"
	if clean_rebuild and (workspace / "build" / slug / "android").exists():
		print("[BeeWare] Cleaning previous Android build cache...")
		shutil.rmtree(workspace / "build" / slug / "android")

	# Xóa các file APK cũ (đặc biệt là APK unsigned từ lần build trước) trong workspace/dist
	if (workspace / "dist").exists():
		shutil.rmtree(workspace / "dist")

	if not gradle_project_dir.exists():
		if (workspace / "build" / slug / "android").exists():
			shutil.rmtree(workspace / "build" / slug / "android")
		print("[BeeWare] Step 1/4: Creating Android project template...")
		_run_briefcase(["create", "android", "--no-input"], cwd=workspace, env=env)
	else:
		print("[BeeWare] Step 1/4: Updating existing Android project sources...")
		_run_briefcase(["update", "android", "-r", "--no-input"], cwd=workspace, env=env)

	print("[BeeWare] Step 2/4: Embedding native .so libraries into Android jniLibs...")
	_inject_gradle_jnilibs(workspace, slug, staging_native_dir, abis)

	print("[BeeWare] Step 3/4: Building Android project via Gradle...")
	_run_briefcase(["build", "android", "--no-input"], cwd=workspace, env=env)

	print("[BeeWare] Step 4/4: Packaging signed standalone APK...")
	_run_briefcase(
		["package", "android", "--packaging-format", "debug-apk", "--no-input"],
		cwd=workspace, env=env
	)

	found_apks = []
	for search_root in (workspace / "dist", gradle_project_dir / "app" / "build" / "outputs" / "apk"):
		if search_root.exists():
			for p in search_root.rglob("*.apk"):
				if not p.name.lower().endswith("-unsigned.apk"):
					found_apks.append(p)

	if not found_apks:
		raise RuntimeError("Briefcase finished but no signed .apk file was found in outputs!")

	found_apks.sort(key=lambda p: (_is_apk_signed(p), p.stat().st_mtime), reverse=True)
	best_apk = _ensure_apk_signed(found_apks[0], env)

	target_dist = Path(out_dir) if out_dir else (app_root / "dist" / str(name))
	target_dist.mkdir(parents=True, exist_ok=True)

	apk_base = rename_file if rename_file else slug
	if not str(apk_base).lower().endswith(".apk"):
		apk_base = f"{apk_base}.apk"

	final_apk_path = target_dist / apk_base
	shutil.copy2(best_apk, final_apk_path)

	print("=" * 60)
	print(f"[BeeWare] Standalone signed APK successfully generated:")
	print(f" -> {final_apk_path.resolve()}")
	print("=" * 60)
	return True


# ==============================================================================
# PHẦN 1B: MULTI-PLATFORM BEEWARE (BRIEFCASE) BUILDER (iOS, macOS, Linux, Windows, Web)
# ==============================================================================

_BEEWARE_TARGET_MAP = {
	"ios": "iOS",
	"macos": "macOS",
	"darwin": "macOS",
	"linux": "linux",
	"windows": "windows",
	"win": "windows",
	"web": "web",
}


def _make_app_slug(name):
	slug = re.sub(r"[^a-z0-9_]", "", str(name).lower().replace(" ", "_"))
	slug = re.sub(r"_+", "_", slug).strip("_")
	if not slug or not slug[0].isalpha():
		slug = "app_" + slug
	if slug in ("main", "test", "app", "sys", "os", "pyaudiogaming"):
		slug = "app_" + slug
	if any(c in str(name) for c in "\r\n"):
		raise ValueError("Application name must be a single line")
	return slug


def _prepare_beeware_native_libs(package_dir, target_os, arch=None):
	"""Sao chép đúng thư viện native (BASS, Phonon, Screen Reader...) vào gói pyaudiogaming/lib theo target_os."""
	target_os = target_os.lower()
	if target_os == "web":
		return
	src_lib = ROOT / "lib"
	if not src_lib.is_dir():
		return

	ext, arch_dirs = get_target_lib_info(target_os, arch)
	dst_lib = package_dir / "lib"
	dst_lib.mkdir(parents=True, exist_ok=True)

	# Copy top-level libs matching target extension (e.g., screen-reader DLLs on Windows)
	for item in src_lib.iterdir():
		if item.is_file() and item.name.lower().endswith(ext):
			shutil.copy2(item, dst_lib / item.name)

	# On iOS also allow static libs (.a) or frameworks if present
	allowed_exts = (ext, ".a") if target_os == "ios" else (ext,)
	extra_dirs = list(arch_dirs)
	if target_os == "ios" and "iosimulator" not in extra_dirs:
		extra_dirs.append("iosimulator")

	for sub in extra_dirs:
		s_sub = src_lib / sub
		if s_sub.is_dir():
			d_sub = dst_lib / sub
			d_sub.mkdir(parents=True, exist_ok=True)
			for root_dir, _, files in os.walk(s_sub):
				rel = os.path.relpath(root_dir, s_sub)
				t_sub = d_sub / rel if rel != "." else d_sub
				t_sub.mkdir(parents=True, exist_ok=True)
				for fname in files:
					if fname.lower().endswith(allowed_exts):
						shutil.copy2(os.path.join(root_dir, fname), t_sub / fname)


def prepare_beeware(project, name, target_os, data=(), arch=None, extra_reqs=()):
	"""Chuẩn bị workspace Briefcase hoàn chỉnh cho iOS, macOS, Linux, Windows hoặc Web."""
	target_os = target_os.lower().strip()
	if target_os not in _BEEWARE_TARGET_MAP:
		raise ValueError(f"Unsupported BeeWare target platform: {target_os}")

	entry = Path(str(project) + ".py").resolve()
	if not entry.is_file():
		raise ValueError(f"Entry script does not exist: {entry}")

	slug = _make_app_slug(name)
	workspace = ROOT / "include" / "beeware" / "projects" / f"{slug}_{target_os}"
	app_src = workspace / "src" / slug

	if app_src.exists():
		shutil.rmtree(app_src)
	app_src.mkdir(parents=True, exist_ok=True)

	# 1. Copy pyaudiogaming package
	package = app_src / "pyaudiogaming"
	package.mkdir(parents=True, exist_ok=True)
	for item in ROOT.glob("*.py"):
		if item.name.lower() not in EXCLUDE_BUILD_FILES and not item.name.lower().startswith("compile"):
			shutil.copy2(item, package / item.name)

	ignore_bin = DESKTOP_BIN_PATTERNS if target_os in ("ios", "web") else ("*.pdb", "*.lib", "*.exp", "*.obj", "*.bat", "*.cmd")
	for folder in ("sound_modules", "accessible_output2", "include", "utils"):
		src_folder = ROOT / folder
		if src_folder.is_dir():
			ignore_fn = shutil.ignore_patterns(
				"__pycache__", "*.pyc", "desktop.ini", "android", "beeware",
				"compile*.py", "android_build.py", "builder.py",
				*ignore_bin
			)
			shutil.copytree(src_folder, package / folder, dirs_exist_ok=True, ignore=ignore_fn)

	_prepare_beeware_native_libs(package, target_os, arch)

	# 2. Copy user project scripts & packages
	app_root = entry.parent
	for item in app_root.iterdir():
		if item.is_file() and item.suffix == ".py":
			fname_low = item.name.lower()
			if fname_low not in EXCLUDE_BUILD_FILES and not fname_low.startswith(("compile", "#", "@")):
				shutil.copy2(item, app_src / item.name)
		elif item.is_dir() and (item / "__init__.py").exists() and not _is_ignored_app_dir(item, ROOT):
			shutil.copytree(
				item,
				app_src / item.name,
				dirs_exist_ok=True,
				ignore=shutil.ignore_patterns(
					"__pycache__", "*.pyc", "desktop.ini",
					"compile*.py", "android_build.py", "builder.py",
					"Lib", "Scripts", "Include",
					*ignore_bin
				)
			)

	shutil.copy2(entry, app_src / "main.py")
	shutil.copy2(entry, app_src / "_pyag_entry.py")

	# On iOS / Web embed pygame shim if available so pygame imports don't crash where SDL2 wheel is absent
	if target_os in ("ios", "web"):
		pygame_shim_src = ROOT / "pygame_shim"
		if pygame_shim_src.is_dir():
			shutil.copytree(
				pygame_shim_src,
				app_src / "pygame",
				dirs_exist_ok=True,
				ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "desktop.ini", "java")
			)

	# 3. Copy user data files/folders
	skip_exts = {
		"ios": (".dll", ".exe", ".pyd", ".so", ".lib", ".pdb"),
		"macos": (".dll", ".exe", ".pyd", ".so", ".lib", ".pdb"),
		"linux": (".dll", ".exe", ".pyd", ".dylib", ".lib", ".pdb"),
		"windows": (".so", ".dylib"),
		"web": (".dll", ".exe", ".pyd", ".so", ".dylib", ".lib", ".pdb"),
	}.get(target_os, ())

	for value in (data or ()):
		relative = Path(value)
		if relative.is_absolute() or ".." in relative.parts:
			raise ValueError(f"Data must be a relative path inside the application: {value}")
		if relative.suffix.lower() in skip_exts:
			print(f"[BeeWare:{target_os}] Skipping incompatible binary in data: {value}")
			continue
		original = app_root / relative
		if not original.exists():
			original = Path(value).resolve()
		if not original.exists():
			raise ValueError(f"Missing application data: {original}")
		destination = app_src / relative
		if original.is_dir():
			shutil.copytree(
				original,
				destination,
				dirs_exist_ok=True,
				ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "desktop.ini")
			)
		else:
			destination.parent.mkdir(parents=True, exist_ok=True)
			shutil.copy2(original, destination)

	# 4. Generate __init__.py & __main__.py bootstrap
	_save_text("# Auto-generated package init\n", app_src / "__init__.py")
	bootstrap_code = """# -*- coding: utf-8 -*-
import os
import runpy
import sys
import traceback

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)
sys.frozen = True
try:
    os.chdir(_APP_DIR)
except Exception:
    pass

try:
    runpy.run_module("_pyag_entry", run_name="__main__", alter_sys=True)
except SystemExit:
    raise
except Exception:
    traceback.print_exc()
    raise
"""
	_save_text(bootstrap_code, app_src / "__main__.py")
	_save_text("MIT License\n", workspace / "LICENSE")

	# 5. Generate pyproject.toml
	default_reqs = ["pycryptodome", "cryptography", "polib"]
	if target_os in ("windows", "linux", "macos"):
		default_reqs.append("pygame")
	for r in (extra_reqs or ()):
		r_clean = str(r).strip()
		if r_clean and not r_clean.startswith("-") and r_clean not in default_reqs:
			default_reqs.append(r_clean)

	req_formatted = ",\n    ".join(f'"{r}"' for r in default_reqs)
	safe_name = str(name).replace('"', '\\"')
	bw_section = _BEEWARE_TARGET_MAP[target_os]

	platform_block = f"""
[tool.briefcase.app.{slug}.{bw_section}]
requires = []
"""
	if target_os == "ios":
		platform_block += f"""
[tool.briefcase.app.{slug}.iOS.info]
NSMicrophoneUsageDescription = "{safe_name} requires microphone access for voice chat and audio features."
"""
	elif target_os == "macos":
		platform_block += f"""universal_build = true

[tool.briefcase.app.{slug}.macOS.info]
NSMicrophoneUsageDescription = "{safe_name} requires microphone access for voice chat and audio features."
"""
	elif target_os == "linux":
		platform_block += """
[tool.briefcase.app.""" + slug + """.linux.system.debian]
system_requires = []
system_runtime_requires = ["libasound2", "libsdl2-2.0-0"]
"""

	pyproject_content = f"""[build-system]
requires = ["briefcase"]

[tool.briefcase]
project_name = "{safe_name}"
bundle = "org.pyaudiogaming"
version = "0.1.0"
url = "https://pyaudiogaming.org"
license = "MIT"
license-files = ["LICENSE"]
author = "PyAudioGaming"
author_email = "dev@pyaudiogaming.org"

[tool.briefcase.app.{slug}]
formal_name = "{safe_name}"
description = "{safe_name} built with PyAudioGaming BeeWare Backend"
sources = ["src/{slug}"]
requires = [
    {req_formatted}
]
{platform_block}
"""
	_save_text(pyproject_content, workspace / "pyproject.toml")
	return workspace, slug, app_root


def build_beeware(project, name, target_os, data=(), arch=None, args=(), prepare_only=False, rename_file=None, out_dir=None):
	"""Build ứng dụng qua BeeWare (Briefcase) cho iOS, macOS, Linux, Windows hoặc Web."""
	target_os = target_os.lower().strip()
	if target_os == "android":
		return build_android(project, name, data=data, arch=arch, args=args, prepare_only=prepare_only, rename_file=rename_file, out_dir=out_dir)

	bw_plat = _BEEWARE_TARGET_MAP.get(target_os)
	if not bw_plat:
		raise ValueError(f"Unsupported BeeWare target platform: {target_os}")

	host_os = sys_checker.get_platform()["os"].lower()
	extra_reqs = [a for a in (args or ()) if not str(a).startswith("-")]
	clean_rebuild = "--clean" in (args or ()) or "--clean" in sys.argv
	use_docker = "--docker" in (args or ()) or "--use-docker" in (args or ())

	workspace, slug, app_root = prepare_beeware(
		project, name, target_os, data=data, arch=arch, extra_reqs=extra_reqs
	)
	print(f"[BeeWare:{bw_plat}] Workspace prepared: {workspace}")

	if prepare_only:
		return True

	# Kiểm tra điều kiện host OS bắt buộc của từng nền tảng
	if target_os in ("ios", "macos") and host_os != "macos":
		print("=" * 64)
		print(f"[BeeWare:{bw_plat}] Workspace is ready at: {workspace}")
		print(f"Notice: Building/packaging '{bw_plat}' requires a macOS host with Xcode installed.")
		print("You can copy the prepared workspace above to a Mac (or run on GitHub Actions 'macos-latest')")
		print(f"and execute: briefcase create {bw_plat} && briefcase build {bw_plat} && briefcase package {bw_plat}")
		print("=" * 64)
		return True

	if target_os == "windows" and host_os != "windows":
		print("=" * 64)
		print(f"[BeeWare:{bw_plat}] Workspace is ready at: {workspace}")
		print("Notice: Packaging Windows MSI via BeeWare requires running on a Windows host.")
		print("=" * 64)
		return True

	if target_os == "linux" and host_os != "linux" and not (use_docker and shutil.which("docker")):
		print("=" * 64)
		print(f"[BeeWare:{bw_plat}] Workspace is ready at: {workspace}")
		print("Notice: Packaging Linux via BeeWare requires a Linux host (or pass '--docker' with Docker installed).")
		print(f"On Linux, run inside workspace: briefcase create linux && briefcase build linux && briefcase package linux")
		print("=" * 64)
		return True

	env = _get_portable_env()
	_ensure_briefcase(env)

	plat_build_dir = workspace / "build" / slug / target_os
	if clean_rebuild and plat_build_dir.exists():
		print(f"[BeeWare:{bw_plat}] Cleaning previous build cache...")
		shutil.rmtree(plat_build_dir)

	if (workspace / "dist").exists():
		shutil.rmtree(workspace / "dist")

	extra_bw_flags = []
	if target_os == "linux" and host_os != "linux" and use_docker:
		extra_bw_flags.append("--use-docker")

	if not plat_build_dir.exists():
		print(f"[BeeWare:{bw_plat}] Step 1/3: Creating {bw_plat} project template...")
		_run_briefcase(["create", bw_plat, "--no-input"] + extra_bw_flags, cwd=workspace, env=env)
	else:
		print(f"[BeeWare:{bw_plat}] Step 1/3: Updating {bw_plat} project sources...")
		_run_briefcase(["update", bw_plat, "-r", "--no-input"] + extra_bw_flags, cwd=workspace, env=env)

	print(f"[BeeWare:{bw_plat}] Step 2/3: Building {bw_plat} project...")
	_run_briefcase(["build", bw_plat, "--no-input"] + extra_bw_flags, cwd=workspace, env=env)

	print(f"[BeeWare:{bw_plat}] Step 3/3: Packaging {bw_plat} distributable...")
	pkg_cmd = ["package", bw_plat, "--no-input"] + extra_bw_flags
	if target_os == "macos" and "--adhoc-sign" not in pkg_cmd:
		pkg_cmd.append("--adhoc-sign")
	elif target_os == "ios":
		# On iOS, package may require signing identity; fall back gracefully if no Apple Dev cert is present
		try:
			_run_briefcase(pkg_cmd, cwd=workspace, env=env)
		except RuntimeError as e:
			print(f"[BeeWare:iOS] Packaging note (code signing may be required for .ipa): {e}")
			print(f"[BeeWare:iOS] Xcode project built successfully at: {workspace / 'build' / slug / 'ios'}")
			pkg_cmd = None
	if pkg_cmd is not None:
		_run_briefcase(pkg_cmd, cwd=workspace, env=env)

	target_dist = Path(out_dir) if out_dir else (app_root / "dist" / str(name))
	target_dist.mkdir(parents=True, exist_ok=True)

	copied = []
	ws_dist = workspace / "dist"
	if ws_dist.is_dir():
		for item in ws_dist.iterdir():
			dst_item = target_dist / item.name
			if item.is_dir():
				shutil.copytree(item, dst_item, dirs_exist_ok=True)
			else:
				shutil.copy2(item, dst_item)
			copied.append(dst_item)

	print("=" * 60)
	if copied:
		print(f"[BeeWare:{bw_plat}] Build artifacts copied to:")
		for c in copied:
			print(f" -> {c.resolve()}")
	else:
		print(f"[BeeWare:{bw_plat}] Build finished. Check workspace build directory:")
		print(f" -> {workspace.resolve()}")
	print("=" * 60)
	return True


# ==============================================================================
# PHẦN 2: TRÌNH BIÊN DỊCH CHÍNH & CẤU HÌNH (compile.py)
# ==============================================================================

def parse_val(val):
	val = val.strip()
	if val.lower() in ("null", "none", ""):
		return None
	if val in ("1", "true", "True", "yes"):
		return True
	if val in ("0", "false", "False", "no"):
		return False
	if (val.startswith("[") and val.endswith("]")) or (val.startswith("(") and val.endswith(")")):
		try:
			parsed = ast.literal_eval(val)
			return [str(x).strip() for x in parsed]
		except Exception:
			content = val[1:-1].strip()
			if not content:
				return []
			return [x.strip().strip("'\"") for x in content.split(",") if x.strip()]
	if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
		return val[1:-1]
	return val


def get_target_lib_info(os_name, arch_override=None):
	os_name = os_name.lower()
	info = sys_checker.get_arch()
	bit = info.get("bit", 64)
	machine = info.get("machine", "").lower()

	ext_map = {
		"windows": ".dll",
		"linux": ".so",
		"android": ".so",
		"macos": ".dylib",
		"ios": ".dylib"
	}
	ext = ext_map.get(os_name, ".dll")
	arch_dirs = []

	if arch_override:
		if isinstance(arch_override, list):
			arch_dirs = arch_override
		else:
			arch_dirs = [str(arch_override)]
	else:
		if os_name == "windows":
			arch_dirs = ["x64" if bit == 64 else "x86"]
		elif os_name == "macos":
			arch_dirs = ["mac"]
		elif os_name == "linux":
			if "aarch64" in machine or "arm64" in machine:
				arch_dirs = ["aarch64"]
			elif "arm" in machine:
				arch_dirs = ["armhf"]
			else:
				arch_dirs = ["x64" if bit == 64 else "x86"]
		elif os_name == "android":
			arch_dirs = ["arm64-v8a", "armeabi-v7a", "a64", "a86", "aarch64", "x86", "x64"]
		elif os_name == "ios":
			arch_dirs = ["ios", "arm64"]

	return ext, arch_dirs


def copy_platform_libs(src_root, dst_root, target_os, arch_override=None):
	ext, arch_dirs = get_target_lib_info(target_os, arch_override)
	
	for folder in ["include", "utils"]:
		src_dir = os.path.join(src_root, folder)
		if os.path.exists(src_dir):
			shutil.copytree(
				src_dir,
				os.path.join(dst_root, folder),
				dirs_exist_ok=True,
				ignore=shutil.ignore_patterns("android", "__pycache__", "*.pyc")
			)

	src_lib = os.path.join(src_root, "lib")
	dst_lib = os.path.join(dst_root, "lib")
	if not os.path.exists(src_lib):
		return

	os.makedirs(dst_lib, exist_ok=True)

	for item in os.listdir(src_lib):
		s_item = os.path.join(src_lib, item)
		if os.path.isfile(s_item) and item.lower().endswith(ext):
			shutil.copy2(s_item, os.path.join(dst_lib, item))

	for sub in arch_dirs:
		s_sub = os.path.join(src_lib, sub)
		if os.path.exists(s_sub) and os.path.isdir(s_sub):
			d_sub = os.path.join(dst_lib, sub)
			os.makedirs(d_sub, exist_ok=True)
			for root, dirs, files in os.walk(s_sub):
				rel = os.path.relpath(root, s_sub)
				target_sub = os.path.join(d_sub, rel) if rel != "." else d_sub
				os.makedirs(target_sub, exist_ok=True)
				for file in files:
					if file.lower().endswith(ext):
						shutil.copy2(os.path.join(root, file), os.path.join(target_sub, file))


def dopackage(PROJECT, PROJECT_FULL_NAME, target_os="windows"):
	print(f"Creating installer/package for {target_os}...")
	dist_dir = f"dist/{PROJECT_FULL_NAME}"
	
	if target_os == "windows":
		rar_path = r"C:\Program Files\WinRAR\rar.exe"
		if not os.path.exists(rar_path):
			print("Error: WinRAR not found at %s" % rar_path)
			return
		f = File(password="", encode=False, aes=False)
		cmd_bat = "\"%s\" a -cfg- -ed -ep1 -k -m5 -r -sfx \"-ztools\\rar_options.txt\" \"%s.exe\" \"%s\\*\"" % (rar_path, PROJECT_FULL_NAME, dist_dir)
		f.save(cmd_bat, "_build.bat", mode="w+", type="txt")
		common.run("cmd /c _build.bat")
		if os.path.exists("_build.bat"):
			os.remove("_build.bat")
	else:
		shutil.make_archive(PROJECT_FULL_NAME, 'zip', dist_dir)
		print(f"Created archive: {PROJECT_FULL_NAME}.zip")


def quote_arg(path_str):
	path_str = str(path_str).strip()
	if " " in path_str and not (path_str.startswith('"') and path_str.endswith('"')):
		return f'"{path_str}"'
	return path_str


def find_local_gcc_or_clang(is_cpp=False):
	exe_gcc = "g++.exe" if is_cpp else "gcc.exe"
	exe_clang = "clang++.exe" if is_cpp else "clang.exe"

	if shutil.which(exe_gcc[:-4]):
		return exe_gcc[:-4]
	if shutil.which(exe_clang[:-4]):
		return exe_clang[:-4]

	search_patterns = [
		rf"C:\MinGW\bin\{exe_gcc}",
		rf"C:\MinGW64\bin\{exe_gcc}",
		rf"C:\mingw64\bin\{exe_gcc}",
		rf"C:\mingw32\bin\{exe_gcc}",
		rf"C:\TDM-GCC-64\bin\{exe_gcc}",
		rf"C:\TDM-GCC-32\bin\{exe_gcc}",
		rf"C:\msys64\mingw64\bin\{exe_gcc}",
		rf"C:\msys64\ucrt64\bin\{exe_gcc}",
		rf"C:\msys64\mingw32\bin\{exe_gcc}",
		rf"C:\msys64\usr\bin\{exe_gcc}",
		rf"C:\cygwin64\bin\{exe_gcc}",
		rf"C:\w64devkit\bin\{exe_gcc}",
		rf"C:\Program Files\mingw-w64\*\mingw64\bin\{exe_gcc}",
		rf"C:\Program Files (x86)\mingw-w64\*\mingw32\bin\{exe_gcc}",
		rf"C:\Program Files\LLVM\bin\{exe_clang}",
		rf"C:\Program Files (x86)\LLVM\bin\{exe_clang}",
		rf"C:\Program Files (x86)\Microsoft Visual Studio\*\*\VC\Tools\Llvm\x64\bin\{exe_clang}",
		rf"C:\Program Files (x86)\Microsoft Visual Studio\*\*\VC\Tools\Llvm\bin\{exe_clang}",
		rf"C:\Program Files\Microsoft Visual Studio\*\*\VC\Tools\Llvm\x64\bin\{exe_clang}",
		rf"C:\Program Files\Microsoft Visual Studio\*\*\VC\Tools\Llvm\bin\{exe_clang}",
		rf"C:\Program Files (x86)\CodeBlocks\MinGW\bin\{exe_gcc}",
		rf"C:\Program Files\CodeBlocks\MinGW\bin\{exe_gcc}",
		rf"C:\Program Files (x86)\Dev-Cpp\MinGW64\bin\{exe_gcc}",
		rf"C:\Program Files\Dev-Cpp\MinGW64\bin\{exe_gcc}"
	]
	for pattern in search_patterns:
		matches = glob.glob(pattern)
		if matches:
			return quote_arg(matches[0])
	return None


def find_vs_vcvars(arch=None):
	arch_str = str(arch).lower() if arch else "x64"
	bat_name = "vcvars32.bat" if arch_str == "x86" else "vcvars64.bat"
	
	vs_roots = [
		os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
		os.environ.get("ProgramFiles", r"C:\Program Files")
	]
	
	for root in vs_roots:
		vswhere = os.path.join(root, "Microsoft Visual Studio", "Installer", "vswhere.exe")
		if os.path.exists(vswhere):
			for year in ["2022", "2019", "2017", "*"]:
				for ed in ["BuildTools", "Community", "Professional", "Enterprise", "*"]:
					pattern = os.path.join(root, "Microsoft Visual Studio", year, ed, "VC", "Auxiliary", "Build", bat_name)
					matches = glob.glob(pattern)
					if matches:
						return matches[0]

	for root in vs_roots:
		if not root or not os.path.exists(root):
			continue
		patterns = [
			os.path.join(root, "Microsoft Visual Studio", "*", "*", "VC", "Auxiliary", "Build", bat_name),
			os.path.join(root, "Microsoft Visual Studio", "*", "VC", "Auxiliary", "Build", bat_name),
			os.path.join(root, "Microsoft Visual Studio *", "VC", "bin", "amd64" if bat_name == "vcvars64.bat" else "", bat_name)
		]
		for p in patterns:
			matches = glob.glob(p)
			if matches:
				return matches[0]
	return None


def resolve_gcc_binary(host_os, target_os, arch=None, is_cpp=False):
	base_compiler = "g++" if is_cpp else "gcc"
	clang_compiler = "clang++" if is_cpp else "clang"
	arch_str = str(arch).lower() if arch else "x64"

	if host_os != target_os:
		candidates = []
		if target_os == "linux":
			if arch_str in ("arm64", "aarch64", "a64"):
				candidates = [f"aarch64-linux-gnu-{base_compiler}", f"aarch64-linux-musl-{base_compiler}"]
			elif arch_str in ("arm", "armhf", "armeabi-v7a"):
				candidates = [f"arm-linux-gnueabihf-{base_compiler}"]
			elif arch_str == "x86":
				candidates = [f"i686-linux-gnu-{base_compiler}"]
			else:
				candidates = [f"x86_64-linux-gnu-{base_compiler}", f"x86_64-linux-musl-{base_compiler}"]
		elif target_os == "macos":
			if arch_str in ("arm64", "aarch64", "m1", "m2"):
				candidates = [f"oa64-{clang_compiler}", f"arm64-apple-darwin-{base_compiler}"]
			else:
				candidates = [f"o64-{clang_compiler}", f"x86_64-apple-darwin-{base_compiler}"]
		elif target_os == "windows":
			candidates = [f"i686-w64-mingw32-{base_compiler}" if arch_str == "x86" else f"x86_64-w64-mingw32-{base_compiler}"]
		elif target_os == "android":
			candidates = [
				f"aarch64-linux-android21-{clang_compiler}" if arch_str in ("arm64-v8a", "a64", "aarch64") else f"armv7a-linux-androideabi21-{clang_compiler}",
				f"x86_64-linux-android21-{clang_compiler}" if arch_str == "x64" else f"i686-linux-android21-{clang_compiler}"
			]
		for cand in candidates:
			if shutil.which(cand.split()[0]):
				return ("gcc", cand)

	if host_os == "windows":
		found_gcc = find_local_gcc_or_clang(is_cpp)
		if found_gcc:
			return ("gcc", found_gcc)
		vcvars = find_vs_vcvars(arch)
		if vcvars:
			print(f"-> Found Visual Studio Build Tools: {vcvars}")
			return ("msvc", vcvars)

	return ("gcc", base_compiler)


def build_command(tool, PROJECT, PROJECT_FULL_NAME, rename_file, args_compile, zstandard, target_os, arch=None):
	tool = tool.lower().strip()
	host_os = sys_checker.get_platform()["os"].lower()
	if target_os in ("android", "ios", "web"):
		raise ValueError(f"'{target_os}' builds must use the dedicated BeeWare backend")
	args = list(args_compile) if isinstance(args_compile, list) else []
	if host_os != "windows":
		args = [a for a in args if a.strip().lower() != "--mingw64"]
	out_dir = f"dist/{PROJECT_FULL_NAME}"
	ext_bin = ".exe" if target_os == "windows" else ""
	py_exe = _find_real_python()

	if host_os != target_os and tool in ("pyinstaller", "nuitka", "cx_freeze"):
		raise RuntimeError(
			f"'{tool}' cannot cross-compile from '{host_os}' to '{target_os}'. "
			f"To build for '{target_os}', run compile.py on a '{target_os}' machine (or CI/GitHub Actions), "
			f"or set 'mode = beeware' to prepare a portable BeeWare project workspace."
		)

	if tool == "pyinstaller":
		if zstandard:
			if not any(a.strip().startswith(("--onefile", "-F", "--onedir", "-D")) for a in args):
				args.append("--onefile")
			args = [a for a in args if not a.strip().startswith(("--name", "--distpath"))]
			args.append(f"--name {quote_arg(rename_file)}")
			args.append(f"--distpath {quote_arg(out_dir)}")
		return f"{quote_arg(py_exe)} -m PyInstaller {' '.join(args)} {quote_arg(f'{PROJECT}.py')}"

	elif tool == "nuitka":
		if zstandard:
			if not any(a.strip().startswith(("--onefile", "--standalone")) for a in args):
				args.append("--onefile")
			args = [a for a in args if not a.strip().startswith(("--output-dir", "--output-filename", "-o"))]
			args.append(f"--output-dir={quote_arg(out_dir)}")
			args.append(f"--output-filename={quote_arg(f'{rename_file}{ext_bin}')}")
		return f"{quote_arg(py_exe)} -m nuitka {' '.join(args)} {quote_arg(f'{PROJECT}.py')}"

	elif tool in ("gcc", "g++", "clang", "msvc", "cl", "cython"):
		os.makedirs(out_dir, exist_ok=True)
		is_cpp = (tool == "g++") or os.path.exists(f"{PROJECT}.cpp")
		
		if tool in ("msvc", "cl"):
			vcvars = find_vs_vcvars(arch)
			comp_type, compiler = ("msvc", vcvars) if vcvars else ("msvc", "cl")
		elif tool == "clang" and shutil.which("clang"):
			comp_type, compiler = ("gcc", "clang")
		else:
			comp_type, compiler = resolve_gcc_binary(host_os, target_os, arch, is_cpp)

		if host_os != target_os and comp_type == "msvc":
			raise RuntimeError(
				f"Cannot cross-compile from '{host_os}' to '{target_os}' using Windows MSVC. "
				f"Install a target cross-compiler or build natively on '{target_os}'."
			)

		out_file = os.path.normpath(f"{out_dir}/{rename_file}{ext_bin}")

		need_cython = False
		if tool != "cython" and os.path.exists(f"{PROJECT}.c"):
			src_file = f"{PROJECT}.c"
		elif tool != "cython" and os.path.exists(f"{PROJECT}.cpp"):
			src_file = f"{PROJECT}.cpp"
		else:
			need_cython = True
			src_file = f"{PROJECT}.c"

		cmds = []
		if need_cython:
			py_file = f"{PROJECT}.py"
			cython_bin = "cython" if shutil.which("cython") else f"{quote_arg(py_exe)} -m cython"
			cmds.append(f"{cython_bin} --embed -o {quote_arg(src_file)} {quote_arg(py_file)}")

		if comp_type == "msvc":
			inc_dir = sysconfig.get_path("include")
			libs_dir = os.path.join(sys.base_prefix, "libs")
			py_ver_num = f"{sys.version_info.major}{sys.version_info.minor}"
			
			msvc_flags = []
			if inc_dir and os.path.exists(inc_dir):
				msvc_flags.append(f'/I"{inc_dir}"')
			if libs_dir and os.path.exists(libs_dir):
				msvc_flags.append(f'/link /LIBPATH:"{libs_dir}" python{py_ver_num}.lib')

			py_flags = " ".join(msvc_flags) if need_cython else ""
			extra_args = " ".join(args)
			
			if compiler != "cl" and os.path.exists(compiler):
				bat_content = f'@echo off\ncall "{compiler}"\ncl /nologo /O2 {extra_args} {quote_arg(src_file)} {py_flags} /Fe:{quote_arg(out_file)}\n'
				f = File(password="", encode=False, aes=False)
				f.save(bat_content, "_vs_build.bat", mode="w+", type="txt")
				cmds.append("cmd /c _vs_build.bat")
			else:
				cmds.append(f"cl /nologo /O2 {extra_args} {quote_arg(src_file)} {py_flags} /Fe:{quote_arg(out_file)}")
		else:
			arch_flag = ""
			if arch and str(arch).lower() == "x86" and "-m32" not in compiler and "-m32" not in args:
				arch_flag = "-m32"
			elif arch and str(arch).lower() == "x64" and "-m64" not in compiler and "-m64" not in args and "arm" not in compiler and "aarch64" not in compiler:
				arch_flag = "-m64"
			extra_args = " ".join(filter(None, [arch_flag] + args))
			
			inc_dir = sysconfig.get_path("include")
			gcc_flags = []
			if inc_dir and os.path.exists(inc_dir):
				gcc_flags.append(f'-I"{inc_dir}"')
			if host_os == "windows":
				libs_dir = os.path.join(sys.base_prefix, "libs")
				py_ver_num = f"{sys.version_info.major}{sys.version_info.minor}"
				if os.path.exists(libs_dir):
					gcc_flags.append(f'-L"{libs_dir}"')
				gcc_flags.append(f'-lpython{py_ver_num}')
			else:
				libs_dir = sysconfig.get_config_var("LIBDIR") or ""
				if libs_dir and os.path.exists(libs_dir):
					gcc_flags.append(f'-L"{libs_dir}"')
				ldlib = sysconfig.get_config_var("LDLIBRARY") or ""
				py_lib_flag = f"-lpython{sys.version_info.major}.{sys.version_info.minor}"
				if ldlib.startswith("lib"):
					stem = ldlib[3:]
					for suf in (".so", ".dylib", ".a"):
						if stem.endswith(suf):
							stem = stem[:-len(suf)]
							break
					if stem:
						py_lib_flag = f"-l{stem}"
				gcc_flags.append(py_lib_flag)
				extra_ld = sysconfig.get_config_var("LIBS") or ""
				if extra_ld:
					gcc_flags.append(extra_ld)
			py_flags = " ".join(gcc_flags) if need_cython else ""
			
			win_def = "-DMS_WIN64" if (host_os == "windows" and need_cython) else ""
			cmds.append(f"{compiler} {extra_args} {quote_arg(src_file)} {py_flags} {win_def} -o {quote_arg(out_file)}".strip())

		return cmds

	elif tool == "cx_freeze":
		return f"cxfreeze {quote_arg(f'{PROJECT}.py')} --target-dir {quote_arg(out_dir)} --target-name {quote_arg(f'{rename_file}{ext_bin}')} {' '.join(args)}"

	elif tool in ("beeware", "briefcase"):
		bw_plat = _BEEWARE_TARGET_MAP.get(target_os, "android")
		return f"{quote_arg(py_exe)} -I -m briefcase package {bw_plat} --no-input"

	else:
		return f"{tool} {' '.join(args)} {PROJECT}.py"


def run_build_step(cmd_or_list, project_name):
	cmds = cmd_or_list if isinstance(cmd_or_list, list) else [c.strip() for c in cmd_or_list.split("&&") if c.strip()]
	for idx, single_cmd in enumerate(cmds):
		subprocess.run(single_cmd, shell=True, check=True)
		if idx == 0 and len(cmds) > 1 and "--embed" in single_cmd:
			c_file = f"{project_name}.c"
			if not os.path.exists(c_file):
				print(f"Error: Cython failed to generate '{c_file}'. Stopping compile step.")
				return False
	if os.path.exists("_vs_build.bat"):
		try:
			os.remove("_vs_build.bat")
		except Exception:
			pass
	if os.path.exists(f"{project_name}.obj"):
		try:
			os.remove(f"{project_name}.obj")
		except Exception:
			pass
	return True


def build(PROJECT=None, PROJECT_FULL_NAME=None, args_compile=[], data=[], rename_file=None, packet=False, zstandard=True, mode="pyinstaller", platforms=None, arch=None):
	if PROJECT is None and PROJECT_FULL_NAME is None:
		print("Error: you should fill full project or file name you want compile!")
		sys.exit(1)
	if PROJECT is None:
		PROJECT = PROJECT_FULL_NAME
	elif PROJECT_FULL_NAME is None:
		PROJECT_FULL_NAME = PROJECT

	if not isinstance(args_compile, list):
		args_compile = [str(args_compile)] if args_compile else []
	if not isinstance(data, list):
		data = [str(data)] if data else []
	if rename_file is None:
		rename_file = PROJECT_FULL_NAME

	if not platforms:
		target_platforms = [sys_checker.get_platform()["os"]]
	elif isinstance(platforms, str):
		target_platforms = [platforms.lower().strip()]
	elif isinstance(platforms, list):
		target_platforms = [p.lower().strip() for p in platforms]
	else:
		target_platforms = [sys_checker.get_platform()["os"]]

	for target_os in target_platforms:
		if len(target_platforms) > 1:
			current_full_name = f"{PROJECT_FULL_NAME}_{target_os}"
		else:
			current_full_name = PROJECT_FULL_NAME

		copydir = f"dist/{current_full_name}"

		if target_os == "android":
			valid_android_modes = ("beeware", "briefcase", "android", "buildozer")
			if mode.lower().strip() not in valid_android_modes:
				print(f"Notice: Mode '{mode}' is for desktop. Automatically switching to 'beeware' for Android APK build.")

			build_android(
				project=PROJECT,
				name=PROJECT_FULL_NAME,
				data=data,
				arch=arch,
				args=args_compile,
				prepare_only="--skip-compile" in sys.argv,
				rename_file=rename_file,
				out_dir=copydir
			)
			if packet:
				dopackage(PROJECT, current_full_name, target_os)
			continue

		if target_os in ("ios", "web") or (mode.lower().strip() in ("beeware", "briefcase") and target_os in _BEEWARE_TARGET_MAP):
			if target_os in ("ios", "web") and mode.lower().strip() not in ("beeware", "briefcase", "ios", "web"):
				print(f"Notice: Mode '{mode}' is not supported for '{target_os}'. Automatically switching to 'beeware'.")

			build_beeware(
				project=PROJECT,
				name=PROJECT_FULL_NAME,
				target_os=target_os,
				data=data,
				arch=arch,
				args=args_compile,
				prepare_only="--skip-compile" in sys.argv,
				rename_file=rename_file,
				out_dir=copydir
			)
			if packet:
				dopackage(PROJECT, current_full_name, target_os)
			continue

		print("=" * 50)
		print(f"Building '{PROJECT}' -> '{PROJECT_FULL_NAME}' | Tool: {mode} | Target OS: {target_os} | Arch: {arch or 'auto'}")

		if "--skip-compile" in sys.argv:
			print("Skipping compile step...")
		else:
			cmd = build_command(mode, PROJECT, current_full_name, rename_file, args_compile, zstandard, target_os, arch)
			if not run_build_step(cmd, PROJECT):
				raise RuntimeError("Build failed; packaging stopped")

		print(f"Making libraries for {target_os}...")
		try:
			copy_platform_libs("pyaudiogaming", copydir, target_os, arch)
			if data:
				for elem in data:
					if os.path.exists(elem):
						print(f"Copying data: {elem}...")
						dest_elem = os.path.join(copydir, elem)
						if os.path.isdir(elem):
							shutil.copytree(elem, dest_elem, dirs_exist_ok=True)
						else:
							os.makedirs(os.path.dirname(dest_elem), exist_ok=True)
							shutil.copy2(elem, dest_elem)
		except Exception as e:
			print(f"Warning while copying libraries/data: {e}")

		if packet:
			dopackage(PROJECT, current_full_name, target_os)

	print("Done!")


def create_template(filename="build.txt", legacy=False):
	f = File(password="", encode=False, aes=False)
	if not legacy:
		content = (
			"# PyAudioGaming Build Configuration (Key-Value Format)\n"
			"# Lines starting with #, //, !, @ will be ignored\n\n"
			"project = main\n"
			"project_full_name = MyAudioGame\n"
			"args_compile = [--noconsole]\n"
			"data = [sounds, data]\n"
			"rename_file = game\n"
			"packet = false\n"
			"zstandard = true\n"
			"mode = pyinstaller\n"
			"platforms = null\n"
			"arch = null\n"
		)
	else:
		content = (
			"# PyAudioGaming Build Configuration (Legacy Line-by-Line Format)\n"
			"# Line order: PROJECT, PROJECT_FULL_NAME, args_compile, data, rename_file, packet, zstandard, mode, platforms, arch\n\n"
			"main\n"
			"MyAudioGame\n"
			"[--noconsole]\n"
			"[sounds, data]\n"
			"game\n"
			"false\n"
			"true\n"
			"pyinstaller\n"
			"null\n"
			"null\n"
		)
	f.save(content, filename, mode="w+", type="txt")
	fmt_name = "legacy (line-by-line)" if legacy else "new (key = value)"
	print(f"Created {fmt_name} template configuration file: {filename}")


def interactive_make():
	print("=== Interactive Configuration & Build Wizard (MAKE) ===")
	print("Instructions: Type '.' to go back 1 step, '..' to go back 2 steps. Press Enter to accept the default value.\n")

	steps = [
		("PROJECT", "Main script file name (without .py, e.g., main)", "main"),
		("PROJECT_FULL_NAME", "Full project / output directory name (Press Enter to use main file name)", ""),
		("args_compile", "Compiler arguments (e.g., [--noconsole] or leave empty)", "[]"),
		("data", "Additional data files/folders to copy (e.g., [sounds, data] or leave empty)", "[]"),
		("rename_file", "Executable output name after build (Press Enter to use project name)", ""),
		("packet", "Create installer / zip archive after build? (true/false)", "false"),
		("zstandard", "Use standard automated flags (zstandard)? (true/false)", "true"),
		("mode", "Compiler tool (pyinstaller, nuitka, cython, gcc, msvc, cx_freeze, beeware for Android/iOS/Desktop/Web)", "pyinstaller"),
		("platforms", "Target OS (windows, linux, android, macos, ios, web, or null for auto-detect)", "null"),
		("arch", "Target CPU architecture (x64, x86, a64, arm64-v8a... or null for auto-detect)", "null"),
		("save_action", "Save config or build immediately? (Enter .txt filename to save only, 'both' to save & build, or press Enter to build now)", "")
	]

	answers = {}
	idx = 0
	total = len(steps)

	while idx < total:
		key, prompt_text, default_val = steps[idx]
		cur_val = answers.get(key, default_val)
		display_default = f" [{cur_val}]" if cur_val != "" else ""
		
		try:
			user_inp = input(f"({idx + 1}/{total}) {prompt_text}{display_default}: ").strip()
		except (KeyboardInterrupt, EOFError):
			print("\nMake operation cancelled.")
			sys.exit(0)

		if user_inp and all(c == "." for c in user_inp):
			back_steps = len(user_inp)
			idx = max(0, idx - back_steps)
			print(f"--> Stepped back to ({idx + 1}/{total}): {steps[idx][0]}")
			continue

		if user_inp == "":
			answers[key] = cur_val
		else:
			answers[key] = user_inp

		idx += 1

	config = {
		"PROJECT": parse_val(answers["PROJECT"]),
		"PROJECT_FULL_NAME": parse_val(answers["PROJECT_FULL_NAME"]) or parse_val(answers["PROJECT"]),
		"args_compile": parse_val(answers["args_compile"]) or [],
		"data": parse_val(answers["data"]) or [],
		"rename_file": parse_val(answers["rename_file"]) or None,
		"packet": bool(parse_val(answers["packet"])),
		"zstandard": bool(parse_val(answers["zstandard"])),
		"mode": parse_val(answers["mode"]) or "pyinstaller",
		"platforms": parse_val(answers["platforms"]),
		"arch": parse_val(answers["arch"])
	}

	save_act = answers["save_action"].strip()
	if save_act:
		f = File(password="", encode=False, aes=False)
		do_build_too = False
		if save_act.lower() == "both":
			out_txt = "build.txt"
			do_build_too = True
		else:
			out_txt = save_act if "." in save_act else f"{save_act}.txt"

		lines = [
			"# Generated by PyAudioGaming compile make",
			f"project = {config['PROJECT'] or 'null'}",
			f"project_full_name = {config['PROJECT_FULL_NAME'] or 'null'}",
			f"args_compile = [{', '.join(config['args_compile'])}]" if isinstance(config['args_compile'], list) else f"args_compile = [{config['args_compile']}]",
			f"data = [{', '.join(config['data'])}]" if isinstance(config['data'], list) else f"data = [{config['data']}]",
			f"rename_file = {config['rename_file'] or 'null'}",
			f"packet = {str(config['packet']).lower()}",
			f"zstandard = {str(config['zstandard']).lower()}",
			f"mode = {config['mode']}",
			f"platforms = {config['platforms'] or 'null'}",
			f"arch = {config['arch'] or 'null'}"
		]
		content = "\n".join(lines) + "\n"
		f.save(content, out_txt, mode="w+", type="txt")
		print(f"\nConfiguration saved to: {out_txt}")
		if not do_build_too:
			return

	print("\nStarting build process...")
	build(**config)


def work(config_file):
	# Nếu đang ở trong tiến trình con của BeeWare/Android build thì thoát êm ngay, không báo lỗi build.txt
	if os.environ.get("PYAG_BUILDING_ANDROID") == "1" or os.environ.get("PYAG_BUILDING_BEEWARE") == "1" or "briefcase" in " ".join(sys.argv).lower():
		return

	f = File(password="", encode=False, aes=False)
	if not f.check(config_file):
		# Nếu bị gọi nhầm từ thư mục workspace của BeeWare/Android thì bỏ qua, không sys.exit(1)
		cwd_lower = os.getcwd().lower()
		if "android" in cwd_lower or "beeware" in cwd_lower or "projects" in cwd_lower:
			return
		print(f"Error: Config file '{config_file}' not found!")
		return

	text = f.load(config_file, mode="r+", type="txt")
	if not text:
		return

	lines = []
	for line in text.splitlines():
		s = line.strip()
		if not s or s.startswith(("#", "//", "!", "@")):
			continue
		lines.append(s)

	if not lines:
		print("Error: Empty configuration file!")
		return

	is_kv = any("=" in line and not line.startswith("[") for line in lines)

	if is_kv:
		config = {
			"PROJECT": None,
			"PROJECT_FULL_NAME": None,
			"args_compile": [],
			"data": [],
			"rename_file": None,
			"packet": False,
			"zstandard": True,
			"mode": "pyinstaller",
			"platforms": None,
			"arch": None
		}
		key_map = {
			"project": "PROJECT",
			"file": "PROJECT",
			"project_full_name": "PROJECT_FULL_NAME",
			"full_name": "PROJECT_FULL_NAME",
			"args_compile": "args_compile",
			"args": "args_compile",
			"data": "data",
			"rename_file": "rename_file",
			"rename": "rename_file",
			"packet": "packet",
			"zstandard": "zstandard",
			"mode": "mode",
			"tool": "mode",
			"tools": "mode",
			"platform": "platforms",
			"platforms": "platforms",
			"os": "platforms",
			"arch": "arch"
		}
		for line in lines:
			if "=" not in line:
				continue
			k, v = line.split("=", 1)
			if "#" in v and not ("'" in v or '"' in v):
				v = v.split("#", 1)[0]
			k = k.strip().lower()
			val = parse_val(v)
			if k in key_map:
				config[key_map[k]] = val
		build(**config)
	else:
		if len(lines) < 6:
			print("Error: not true type of compile building config pyaudiogaming needs!")
			return
		parsed_args = [parse_val(line) for line in lines]
		build(*parsed_args)


if __name__ == "__main__":
	if len(sys.argv) < 2:
		sys.exit(0)

	user_input = sys.argv[1].strip()

	# Chặn các lệnh của Briefcase nếu bị gọi nhầm vào compile.py
	briefcase_subcommands = {"new", "dev", "upgrade", "update", "open", "build", "run", "package", "publish", "log", "--version", "-V", "--help", "-h"}
	if user_input.lower() in briefcase_subcommands:
		sys.exit(0)
	if user_input.lower() == "create" and len(sys.argv) > 2 and sys.argv[2].lower() in ("android", "ios", "windows", "linux", "macos", "web"):
		sys.exit(0)

	if user_input.lower() == "make":
		interactive_make()
	elif user_input.lower() == "create":
		target_file = sys.argv[2] if len(sys.argv) > 2 else "build.txt"
		if "." not in target_file:
			target_file += ".txt"
		create_template(target_file, legacy=False)
	elif user_input.lower() == "create2":
		target_file = sys.argv[2] if len(sys.argv) > 2 else "build.txt"
		if "." not in target_file:
			target_file += ".txt"
		create_template(target_file, legacy=True)
	else:
		config_file = user_input
		if not config_file.endswith(".txt") and os.path.exists(config_file + ".txt"):
			config_file += ".txt"
		
		config_file = os.path.abspath(config_file)
		if os.path.isfile(config_file):
			work(config_file)
		else:
			sys.exit(0)
