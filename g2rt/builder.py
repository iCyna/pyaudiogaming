# -*- coding: utf-8 -*-
# Copyright (c) 2025-2026 ihcyna (Labubu) <phucnggo29@gmail.com>. All rights reserved.
"""
PyAudioGaming Multi-Arch G2RT Stuffer
Builds standalone G2RT packages for Android, Linux, macOS, and iOS across multiple CPU architectures
directly from Windows (zero Gradle, zero JDK, zero Android SDK/NDK, zero Xcode, zero GCC!).

G2RT Container Format (unified with Windows G2RT):
  - All app payload (app_meta.json + ChaCha20 app.vault + data.zip + site_packages.zip)
    is packed into a single XOR-masked `g2rt.dat` with the exact 20-byte `G2RT` footer:
    b"G2RT" + struct.pack("<QII", offset=0, rhash_u32, xkey_u32)
  - BASS / Steam Audio / Tags native libs are injected per-arch from `pyaudiogaming/lib/<subdir>/`
    at build time (never duplicated inside shells).
"""

import hashlib
import importlib.util
import io
import json
import marshal
import os
import plistlib
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile
import zlib
from pathlib import Path

from pyaudiogaming.g2rt.apk_tools import (
    patch_android_manifest_axml,
    sign_apk_v2,
    write_aligned_zip,
)
from pyaudiogaming.g2rt.bootstrap import _chacha20_xor


G2RT_DIR = Path(__file__).resolve().parent
ROOT = G2RT_DIR.parent

_CACHE_BASE = Path(
    os.environ.get("PYAG_TOOLCHAIN_HOME")
    or (
        Path(os.environ.get("LOCALAPPDATA", "")) / "PyAudioGaming"
        if os.name == "nt" and os.environ.get("LOCALAPPDATA")
        else Path.home() / ".cache" / "pyaudiogaming"
    )
)
RUNTIME_CACHE_DIR = _CACHE_BASE / "runtimes"
WHEEL_CACHE_DIR = _CACHE_BASE / "wheel_cache"
DATA_CACHE_DIR = _CACHE_BASE / "data_cache"
DEFAULT_KEYSTORE_PEM = _CACHE_BASE / "g2rt_debug_key.pem"

# Unified Multi-Arch Profiles: (os, arch) -> profile dict
DEFAULT_ARCH_BY_OS = {
    "android": "arm64",
    "linux": "x64",
    "macos": "arm64",
    "ios": "arm64",
}

ARCH_PROFILES = {
    # Linux
    ("linux", "x64"): {
        "runtime": "g2rt_linux_x64.tar.gz",
        "lib_dir": "x64",
        "lib_ext": ".so",
        "pip_tags": ["manylinux2014_x86_64", "manylinux_2_17_x86_64", "linux_x86_64"],
        "suffix": "linux_x64.tar.gz",
        "can_local_forge": True,
    },
    ("linux", "arm64"): {
        "runtime": "g2rt_linux_aarch64.tar.gz",
        "lib_dir": "aarch64",
        "lib_ext": ".so",
        "pip_tags": ["manylinux2014_aarch64", "manylinux_2_17_aarch64", "linux_aarch64"],
        "suffix": "linux_aarch64.tar.gz",
        "can_local_forge": True,
    },
    ("linux", "armhf"): {
        "runtime": "g2rt_linux_armhf.tar.gz",
        "lib_dir": "armhf",
        "lib_ext": ".so",
        "pip_tags": ["manylinux2014_armv7l", "linux_armv7l"],
        "suffix": "linux_armhf.tar.gz",
        "can_local_forge": True,
    },
    # macOS
    ("macos", "arm64"): {
        "runtime": "g2rt_macos_arm64.zip",
        "lib_dir": "mac",
        "lib_ext": ".dylib",
        "pip_tags": ["macosx_11_0_arm64", "macosx_12_0_arm64", "macosx_10_15_universal2"],
        "suffix": "macos_arm64.zip",
        "can_local_forge": True,
    },
    ("macos", "x64"): {
        "runtime": "g2rt_macos_x64.zip",
        "lib_dir": "mac",
        "lib_ext": ".dylib",
        "pip_tags": ["macosx_10_15_x86_64", "macosx_11_0_x86_64", "macosx_10_15_universal2"],
        "suffix": "macos_x64.zip",
        "can_local_forge": True,
    },
    # Android (Python 3.12 supports 64-bit ABIs)
    ("android", "arm64"): {
        "runtime": "g2rt_android_arm64-v8a.apk",
        "abi": "arm64-v8a",
        "lib_dir": "arm64-v8a",
        "lib_ext": ".so",
        "pip_tags": ["android_24_arm64_v8a", "linux_aarch64"],
        "suffix": "android_arm64-v8a.apk",
        "can_local_forge": False,
    },
    ("android", "x86_64"): {
        "runtime": "g2rt_android_x86_64.apk",
        "abi": "x86_64",
        "lib_dir": "a64",
        "lib_ext": ".so",
        "pip_tags": ["android_24_x86_64", "linux_x86_64"],
        "suffix": "android_x86_64.apk",
        "can_local_forge": False,
    },
    # iOS
    ("ios", "arm64"): {
        "runtime": "g2rt_ios_arm64.ipa",
        "lib_dir": "ios",
        "lib_ext": "*",
        "pip_tags": [],
        "suffix": "ios_arm64_unsigned.ipa",
        "can_local_forge": False,
    },
    ("ios", "simulator"): {
        "runtime": "g2rt_ios_simulator.ipa",
        "lib_dir": "iosimulator",
        "lib_ext": "*",
        "pip_tags": [],
        "suffix": "ios_sim_unsigned.ipa",
        "can_local_forge": False,
    },
}

ANDROID_PLACEHOLDERS = {
    "pkg": "com.pyaudiogaming.shell.placeholder",
    "name": "PYAG_SHELL_APP_NAME_PLACEHOLDER",
}

EXCLUDE_BUILD_FILES = {
    "compile.py", "compile_2.py", "builder.py", "android_build.py", "setup.py",
    "buildapp.py", "buildtranslation.py", "@build.py",
    "shell_stuffer.py", "shell_apk_tools.py", "forge_shells_local.py",
}

EXCLUDE_DIRS = {
    "__pycache__", "android", "build", "dist", "venv", ".venv", "env",
    ".git", ".github", ".idea", ".vscode", "logs", "server", "tools", "runtimes", "shells",
}

UNCOMPRESSED_EXTS = {
    ".ogg", ".mp3", ".wav", ".flac", ".opus", ".aac", ".m4a",
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".zip", ".pak", ".7z",
}


def normalize_arch_list(target_os, arch=None):
    """Normalize arch string/list into canonical arch keys supported by target_os."""
    norm_os = "macos" if target_os == "darwin" else target_os
    default_a = DEFAULT_ARCH_BY_OS.get(norm_os, "x64")
    if not arch:
        return [default_a]
    raw_list = arch if isinstance(arch, (list, tuple)) else [arch]
    alias_map = {
        "amd64": "x64",
        "x86_64": "x86_64" if norm_os == "android" else "x64",
        "x64": "x86_64" if norm_os == "android" else "x64",
        "intel": "x64",
        "aarch64": "arm64",
        "arm64-v8a": "arm64",
        "arm64": "arm64",
        "a64": "arm64",
        "m1": "arm64",
        "apple_silicon": "arm64",
        "armv7": "armhf",
        "armv7l": "armhf",
        "arm": "armhf",
        "armhf": "armhf",
        "sim": "simulator",
        "iosimulator": "simulator",
        "simulator": "simulator",
        "device": "arm64",
        "iphoneos": "arm64",
    }
    out = []
    for item in raw_list:
        s = str(item or "").strip().lower()
        if not s or s in ("null", "none", "auto"):
            cand = default_a
        else:
            cand = alias_map.get(s, s)
        if (norm_os, cand) not in ARCH_PROFILES:
            supported = [a for (o, a) in ARCH_PROFILES if o == norm_os]
            raise ValueError(
                f"[G2RT] Unsupported arch '{item}' for '{norm_os}'. Supported: {supported}"
            )
        if cand not in out:
            out.append(cand)
    return out or [default_a]


def _make_slug(name):
    slug = re.sub(r"[^a-z0-9]+", "_", str(name or "app").lower()).strip("_")
    return slug or "app"


def _make_bundle_id(name, custom_pkg=None):
    if custom_pkg:
        return custom_pkg.strip()
    slug = re.sub(r"[^a-z0-9]", "", str(name or "app").lower()) or "app"
    if slug[0].isdigit():
        slug = "app" + slug
    return f"com.pyaudiogaming.{slug}"


def _resolve_runtime_file(target_os, arch, runtime_path=None, runtime_base_url=None):
    """Locate pre-built G2RT runtime template locally, download from Releases, or auto-forge on-demand."""
    norm_os = "macos" if target_os == "darwin" else target_os
    profile = ARCH_PROFILES[(norm_os, arch)]
    fname = profile["runtime"]

    candidates = []
    if runtime_path:
        p = Path(runtime_path)
        candidates.append(p / fname if p.is_dir() else p)
    candidates.append(ROOT / "include" / "g2rt_toolkit" / fname)
    candidates.append(ROOT / "runtimes" / fname)
    candidates.append(Path.cwd() / "runtimes" / fname)
    candidates.append(RUNTIME_CACHE_DIR / fname)

    for c in candidates:
        if c.is_file():
            print(f"[G2RT] Runtime ready ({norm_os}/{arch}).")
            return c

    # Auto-extract from bundled archive (supports .g2rt, .bin, .pak, .tar.xz)
    for tk_name in ("g2rt_toolkit.g2rt", "g2rt_toolkit.bin", "g2rt_toolkit.pak", "g2rt_toolkit.tar.xz"):
        toolkit_xz = ROOT / "include" / tk_name
        if toolkit_xz.is_file():
            from pyaudiogaming.g2rt.toolkit_pack import unpack_toolkit_to_cache
            try:
                extracted = unpack_toolkit_to_cache(toolkit_xz, RUNTIME_CACHE_DIR, target_runtime=fname)
                if extracted and Path(extracted).is_file():
                    print(f"[G2RT] Runtime ready ({norm_os}/{arch}).")
                    return Path(extracted)
            except KeyError:
                pass
            break

    base_url = (runtime_base_url or os.environ.get("PYAG_G2RT_BASE_URL") or "").rstrip("/")
    if base_url:
        url = f"{base_url}/{fname}"
        dest = RUNTIME_CACHE_DIR / fname
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"[G2RT] Downloading runtime ({norm_os}/{arch})...")
        tmp_dest = dest.with_suffix(dest.suffix + ".part")
        urllib.request.urlretrieve(url, tmp_dest)
        shutil.move(str(tmp_dest), str(dest))
        print(f"[G2RT] Runtime ready ({norm_os}/{arch}).")
        return dest

    if profile.get("can_local_forge"):
        print(f"[G2RT] Preparing runtime ({norm_os}/{arch})...")
        from pyaudiogaming.g2rt.forge import forge_linux_runtime, forge_macos_runtime
        if norm_os == "linux":
            return forge_linux_runtime(arch=arch, out_dir=RUNTIME_CACHE_DIR)
        if norm_os == "macos":
            return forge_macos_runtime(arch=arch, out_dir=RUNTIME_CACHE_DIR)

    raise FileNotFoundError(
        f"[G2RT] Runtime template '{fname}' not found!\n"
        f"Searched:\n"
        + "\n".join(f"  - {c}" for c in candidates)
        + "\n\nHow to get it:\n"
        f"  - For Android: python pyaudiogaming/g2rt/forge.py android:{arch}\n"
        f"  - For iOS: run GitHub Actions '.github/workflows/build_g2rt_runtimes.yml' (macos-latest runner)\n"
        f"  - Or set PYAG_G2RT_BASE_URL=https://github.com/<user>/<repo>/releases/download/<tag>"
    )


# ==============================================================================
# 1. Code -> .pyc Bytecode -> ChaCha20 app.vault (PGV1 format)
# ==============================================================================
def build_app_vault(app_root, entry_script, out_vault_path, extra_py_dirs=(), embed_pygame_shim=False):
    app_root = Path(app_root).resolve()
    vault_key = os.urandom(32)
    hasher = hashlib.sha256()
    entries = []
    seen = set()

    def _add_py_file(py_path, fullname, is_pkg):
        if fullname in seen:
            return
        seen.add(fullname)
        src = py_path.read_text(encoding="utf-8", errors="replace")
        hasher.update(fullname.encode("utf-8"))
        hasher.update(src.encode("utf-8"))
        try:
            code_obj = compile(src, f"<app:{fullname}>", "exec", optimize=1)
            payload = b"\x00" * 16 + marshal.dumps(code_obj)
            is_pyc = True
        except SyntaxError:
            payload = src.encode("utf-8")
            is_pyc = False
        entries.append((fullname, is_pkg, is_pyc, payload))

    def _scan_dir(base_dir, pkg_prefix=""):
        base_dir = Path(base_dir)
        if not base_dir.is_dir():
            return
        for item in sorted(base_dir.iterdir()):
            if item.name.startswith("."):
                continue
            if item.is_dir():
                if item.name.lower() in EXCLUDE_DIRS:
                    continue
                init_py = item / "__init__.py"
                if init_py.is_file():
                    sub_pkg = f"{pkg_prefix}.{item.name}" if pkg_prefix else item.name
                    _add_py_file(init_py, sub_pkg, True)
                    _scan_dir(item, sub_pkg)
            elif item.is_file() and item.suffix == ".py":
                if item.name.lower() in EXCLUDE_BUILD_FILES or item.name == "__init__.py":
                    continue
                mod_name = f"{pkg_prefix}.{item.stem}" if pkg_prefix else item.stem
                _add_py_file(item, mod_name, False)

    # On Android / iOS, embed pyaudiogaming/pygame_shim as top-level 'pygame' package
    if embed_pygame_shim:
        shim_dir = ROOT / "pygame_shim"
        if shim_dir.is_dir():
            shim_init = shim_dir / "__init__.py"
            if shim_init.is_file():
                _add_py_file(shim_init, "pygame", True)
            _scan_dir(shim_dir, "pygame")

    _scan_dir(app_root)
    entry_stem = Path(str(entry_script)).stem
    entry_file = app_root / f"{entry_stem}.py"
    if entry_file.is_file() and entry_stem not in seen:
        _add_py_file(entry_file, entry_stem, False)

    for d in extra_py_dirs:
        _scan_dir(d)

    out_buf = bytearray()
    out_buf.extend(b"PGV1")
    out_buf.extend(struct.pack("<I", len(entries)))
    for fullname, is_pkg, is_pyc, raw_payload in entries:
        name_b = fullname.encode("utf-8")
        flags = (1 if is_pkg else 0) | (2 if is_pyc else 0)
        nonce = os.urandom(12)
        compressed = zlib.compress(raw_payload, level=6)
        cipher = _chacha20_xor(vault_key, nonce, compressed)
        out_buf.extend(struct.pack("<H", len(name_b)))
        out_buf.extend(name_b)
        out_buf.append(flags)
        out_buf.extend(nonce)
        out_buf.extend(struct.pack("<I", len(cipher)))
        out_buf.extend(cipher)

    Path(out_vault_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_vault_path).write_bytes(bytes(out_buf))
    return vault_key.hex(), hasher.hexdigest()[:12], len(entries)


# ==============================================================================
# 2. Data Packing (data.zip) & G2RT XOR-Masked Container (g2rt.dat)
# ==============================================================================
def build_data_zip(app_root, data_items, out_zip_path):
    """Pack game data with incremental mtime/size caching in DATA_CACHE_DIR (0s on unchanged rebuilds!)."""
    app_root = Path(app_root).resolve()
    files_to_pack = []
    hasher = hashlib.sha256()
    for item in (data_items or ()):
        src = Path(item) if Path(item).is_absolute() else (app_root / item)
        if not src.exists():
            print(f"[G2RT] Warning: data path not found, skipping: {item}")
            continue
        if src.is_file():
            rel = Path(item).as_posix().lstrip("/")
            st = src.stat()
            hasher.update(f"{rel}:{st.st_size}:{int(st.st_mtime)}".encode("utf-8"))
            files_to_pack.append((src, rel))
        else:
            for f in sorted(src.rglob("*")):
                if f.is_file():
                    rel = f.relative_to(app_root).as_posix() if str(f).startswith(str(app_root)) else (Path(item) / f.relative_to(src)).as_posix()
                    st = f.stat()
                    hasher.update(f"{rel}:{st.st_size}:{int(st.st_mtime)}".encode("utf-8"))
                    files_to_pack.append((f, rel))

    if not files_to_pack:
        return None, "nodata"

    data_hash = hasher.hexdigest()[:12]
    DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached_zip = DATA_CACHE_DIR / f"data_{data_hash}.zip"
    if cached_zip.is_file():
        print(f"[G2RT] Using cached assets ({cached_zip.stat().st_size // 1024} KB).")
        return cached_zip, data_hash

    tmp_zip = cached_zip.with_suffix(".zip.part")
    with zipfile.ZipFile(tmp_zip, "w", compresslevel=1) as zf:
        for src_file, arcname in files_to_pack:
            comp = zipfile.ZIP_STORED if src_file.suffix.lower() in UNCOMPRESSED_EXTS else zipfile.ZIP_DEFLATED
            zf.write(src_file, arcname, compress_type=comp)
    shutil.move(str(tmp_zip), str(cached_zip))
    return cached_zip, data_hash


def build_g2rt_dat(meta_dict, vault_path, version_hash):
    """
    Pack ONLY app_meta.json + ChaCha20 app.vault (~0.5-2 MB) into XOR-masked `g2rt.dat`
    with 20-byte `G2RT` footer so bootstrap unmasks it 100% in RAM in <0.03s!
    """
    inner_buf = io.BytesIO()
    with zipfile.ZipFile(inner_buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
        zf.writestr("app_meta.json", json.dumps(meta_dict, ensure_ascii=False).encode("utf-8"))
        zf.writestr("app.vault", Path(vault_path).read_bytes(), compress_type=zipfile.ZIP_STORED)

    raw_zip = inner_buf.getvalue()
    rhash_u32 = int(hashlib.sha256(f"{version_hash}:{len(raw_zip)}".encode("utf-8")).hexdigest()[:8], 16) & 0xFFFFFFFF
    xkey_u32 = struct.unpack("<I", os.urandom(4))[0] or 0xA55A3C69
    kbytes = struct.pack("<I", xkey_u32)
    xlat = [bytes(b ^ kbytes[i] for b in range(256)) for i in range(4)]

    ba = bytearray(raw_zip)
    for rem in range(4):
        ba[rem::4] = bytes(ba[rem::4]).translate(xlat[rem])

    footer = b"G2RT" + struct.pack("<QII", 0, rhash_u32, xkey_u32)
    return bytes(ba) + footer


def _pack_site_packages_zip_bytes(site_dir, exclude_so=False):
    if not site_dir or not Path(site_dir).is_dir():
        return None
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as zsp:
        for f in sorted(Path(site_dir).rglob("*")):
            if f.is_file() and (not exclude_so or f.suffix != ".so"):
                zsp.write(f, f.relative_to(site_dir).as_posix())
    return buf.getvalue() if buf.tell() > 22 else None


# ==============================================================================
# 3. Cross-Platform Wheel Fetcher (per-arch pip download --platform)
# ==============================================================================
def fetch_cross_wheels(target_os, arch, requirements, work_dir, py_version="3.12"):
    reqs = sorted({r.strip() for r in (requirements or ()) if r and not str(r).startswith("-")})
    if not reqs:
        return None, {}

    norm_os = "macos" if target_os == "darwin" else target_os
    profile = ARCH_PROFILES[(norm_os, arch)]
    req_sig = hashlib.sha256(f"{norm_os}:{arch}:{py_version}:{','.join(reqs)}".encode("utf-8")).hexdigest()[:12]
    site_dir = WHEEL_CACHE_DIR / f"{norm_os}_{arch}_{req_sig}"
    stamp = site_dir / ".wheels_ready"

    if not stamp.is_file():
        whl_dir = Path(work_dir) / f"wheels_{norm_os}_{arch}"
        whl_dir.mkdir(parents=True, exist_ok=True)
        if site_dir.exists():
            shutil.rmtree(site_dir, ignore_errors=True)
        site_dir.mkdir(parents=True, exist_ok=True)

        py_tag = py_version.replace(".", "")
        cmd = [
            sys.executable, "-m", "pip", "download",
            "--dest", str(whl_dir),
            "--only-binary=:all:",
            "--python-version", py_version,
            "--implementation", "cp",
            "--abi", f"cp{py_tag}",
        ]
        for plat_tag in profile["pip_tags"]:
            cmd.extend(["--platform", plat_tag])
        if norm_os == "android":
            cmd.extend(["--extra-index-url", "https://chaquo.com/pypi-13.1"])
        cmd.extend(reqs)

        print(f"[G2RT:{norm_os}:{arch}] Resolving dependencies: {', '.join(reqs)}")
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            shutil.rmtree(site_dir, ignore_errors=True)
            raise RuntimeError(
                f"[G2RT] Failed to resolve dependencies for '{norm_os}/{arch}'.\n"
                f"pip stderr:\n{res.stderr}"
            )

        for whl in sorted(whl_dir.glob("*.whl")):
            with zipfile.ZipFile(whl, "r") as zf:
                zf.extractall(site_dir)
        for di in list(site_dir.glob("*.dist-info")):
            shutil.rmtree(di, ignore_errors=True)
        stamp.write_text(req_sig, encoding="utf-8")
    else:
        print(f"[G2RT:{norm_os}:{arch}] Using cached dependencies.")

    android_so_map = {}
    if norm_os == "android":
        for so_file in sorted(site_dir.rglob("*.so")):
            rel = so_file.relative_to(site_dir)
            parts = list(rel.parts)
            # Shared C libs like libffi.so must keep their exact SONAME in lib/<abi>/!
            if so_file.name.startswith("lib") and ".cpython-" not in so_file.name and ".abi3" not in so_file.name:
                android_so_map[f"__shared__:{so_file.name}"] = (so_file.name, so_file)
                continue
            parts[-1] = parts[-1].split(".")[0]
            fullname = ".".join(parts)
            safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", fullname)
            mapped_so = f"lib__pymod__{safe_name}.so"
            android_so_map[fullname] = (mapped_so, so_file)

    return site_dir, android_so_map


# ==============================================================================
# 4. Platform Stuffers (Android, Linux, macOS, iOS) with G2RT g2rt.dat Container
# ==============================================================================
def _compile_hardened_bootstrap_pyc(vault_key_hex, filename="<g2rt_boot>"):
    """
    Embed the 256-bit ChaCha20 vault_key as two random XOR split shares (_G2RT_K1 ^ _G2RT_K2)
    directly inside bootstrap bytecode (optimize=2) so vault_key NEVER appears in JSON or plaintext.
    """
    raw_key = bytes.fromhex(vault_key_hex)
    k1 = os.urandom(len(raw_key))
    k2 = bytes(a ^ b for a, b in zip(raw_key, k1))
    src = (G2RT_DIR / "bootstrap.py").read_text(encoding="utf-8")
    src = src.replace('_G2RT_K1 = b""', f"_G2RT_K1 = {k1!r}", 1)
    src = src.replace('_G2RT_K2 = b""', f"_G2RT_K2 = {k2!r}", 1)
    code_obj = compile(src, filename, "exec", optimize=2)
    return (
        importlib.util.MAGIC_NUMBER
        + struct.pack("<III", 0, 0, len(src.encode("utf-8")) & 0xFFFFFFFF)
        + marshal.dumps(code_obj)
    )


def _refresh_chaquopy_app_imy(orig_imy_bytes, vault_key_hex):
    pyc_bytes = _compile_hardened_bootstrap_pyc(vault_key_hex, filename="placeholder/__main__.py")
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(orig_imy_bytes), "r") as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            if info.filename == "placeholder/__main__.pyc":
                zout.writestr(info, pyc_bytes)
            else:
                zout.writestr(info, zin.read(info.filename))
    new_bytes = out.getvalue()
    return new_bytes, hashlib.sha1(new_bytes).hexdigest()


def stuff_android(shell_apk, out_apk, app_name, package_id, entry, vault_path, vault_key_hex,
                  version_hash, arch="arm64", data_zip=None, site_dir=None, android_so_map=None,
                  error_mode=1, keystore_pem=None):
    profile = ARCH_PROFILES[("android", arch)]
    abi = profile["abi"]
    android_so_map = android_so_map or {}
    native_map_json = {
        mod: mapped for mod, (mapped, _) in android_so_map.items()
        if not mod.startswith("__shared__:")
    }

    meta = {
        "entry": entry,
        "app_name": app_name,
        "package_id": package_id,
        "arch": arch,
        "version_hash": version_hash,
        "error_mode": error_mode,
        "native_map": native_map_json,
    }
    g2rt_dat_bytes = build_g2rt_dat(meta, vault_path, version_hash)
    sp_zip_bytes = _pack_site_packages_zip_bytes(site_dir, exclude_so=True)

    entries = []
    injected_names = {"assets/g2rt.dat", "assets/app_meta.json", "assets/app.vault", "assets/data.zip", "assets/site_packages.zip"}
    for mapped_so, _ in android_so_map.values():
        injected_names.add(f"lib/{abi}/{mapped_so}")

    replacements = {
        ANDROID_PLACEHOLDERS["pkg"]: package_id,
        ANDROID_PLACEHOLDERS["name"]: app_name,
    }

    new_app_imy_sha1 = None
    build_json_idx = None

    with zipfile.ZipFile(shell_apk, "r") as zin:
        for info in zin.infolist():
            name = info.filename
            if name.startswith("META-INF/") and (
                name.endswith((".SF", ".RSA", ".DSA", ".EC")) or name == "META-INF/MANIFEST.MF"
            ):
                continue
            if name in injected_names:
                continue
            raw = zin.read(name)
            if name == "AndroidManifest.xml":
                raw = patch_android_manifest_axml(raw, replacements)
            elif name == "assets/chaquopy/app.imy":
                raw, new_app_imy_sha1 = _refresh_chaquopy_app_imy(raw, vault_key_hex)
            elif name == "assets/chaquopy/build.json":
                build_json_idx = len(entries)
            comp = zipfile.ZIP_STORED if (name.endswith(".so") or name == "resources.arsc") else info.compress_type
            entries.append((name, raw, comp))

    if new_app_imy_sha1 and build_json_idx is not None:
        bj_name, bj_raw, bj_comp = entries[build_json_idx]
        bj = json.loads(bj_raw.decode("utf-8"))
        if isinstance(bj.get("assets"), dict) and "app.imy" in bj["assets"]:
            bj["assets"]["app.imy"] = new_app_imy_sha1
            entries[build_json_idx] = (bj_name, json.dumps(bj, indent=4).encode("utf-8"), bj_comp)

    # Inject lightweight RAM-only G2RT container + separate data.zip / site_packages.zip (0s warm boot!)
    entries.append(("assets/g2rt.dat", g2rt_dat_bytes, zipfile.ZIP_STORED))
    if data_zip and Path(data_zip).is_file():
        entries.append(("assets/data.zip", Path(data_zip).read_bytes(), zipfile.ZIP_STORED))
    if sp_zip_bytes:
        entries.append(("assets/site_packages.zip", sp_zip_bytes, zipfile.ZIP_STORED))

    # Inject per-arch BASS / Steam Audio / Tags libs AT BUILD TIME
    existing_arcnames = {e[0] for e in entries}
    android_lib_dir = ROOT / "lib" / profile["lib_dir"]
    if android_lib_dir.is_dir():
        for so in sorted(android_lib_dir.glob("*.so")):
            arc = f"lib/{abi}/{so.name}"
            if arc not in existing_arcnames:
                entries.append((arc, so.read_bytes(), zipfile.ZIP_STORED))
                existing_arcnames.add(arc)

    for _mod, (mapped_so, so_path) in android_so_map.items():
        arc = f"lib/{abi}/{mapped_so}"
        if arc not in existing_arcnames:
            entries.append((arc, Path(so_path).read_bytes(), zipfile.ZIP_STORED))
            existing_arcnames.add(arc)

    unsigned_apk = Path(out_apk).with_suffix(".unsigned.apk")
    write_aligned_zip(entries, unsigned_apk)
    sign_apk_v2(unsigned_apk, out_apk, keystore_pem or DEFAULT_KEYSTORE_PEM)
    unsigned_apk.unlink(missing_ok=True)
    return Path(out_apk)


def stuff_linux(shell_tar, out_tar, app_name, entry, vault_path, vault_key_hex,
                version_hash, arch="x64", data_zip=None, site_dir=None, error_mode=1):
    profile = ARCH_PROFILES[("linux", arch)]
    meta = {
        "entry": entry,
        "app_name": app_name,
        "arch": arch,
        "version_hash": version_hash,
        "error_mode": error_mode,
        "native_map": {},
    }
    g2rt_dat_bytes = build_g2rt_dat(meta, vault_path, version_hash)
    sp_zip_bytes = _pack_site_packages_zip_bytes(site_dir, exclude_so=False)
    boot_pyc = _compile_hardened_bootstrap_pyc(vault_key_hex, filename="bootstrap.py")
    root_folder = f"{_make_slug(app_name)}_{arch}"
    Path(out_tar).parent.mkdir(parents=True, exist_ok=True)

    with tarfile.open(shell_tar, "r:gz") as tin, tarfile.open(out_tar, "w:gz", compresslevel=1) as tout:
        members = tin.getmembers()
        old_prefix = members[0].name.split("/")[0] if members else "pyag_shell"
        for m in members:
            rel = m.name[len(old_prefix):].lstrip("/") if m.name.startswith(old_prefix) else m.name
            if rel in ("app/bootstrap.py", "app/bootstrap.pyc"):
                continue
            new_m = tarfile.TarInfo(name=f"{root_folder}/{rel}" if rel else root_folder)
            new_m.mode = m.mode
            new_m.mtime = int(time.time())
            new_m.type = m.type
            new_m.linkname = m.linkname
            if m.isfile():
                data = tin.extractfile(m).read()
                if rel == "run.sh":
                    data = data.replace(b"bootstrap.py", b"bootstrap.pyc")
                new_m.size = len(data)
                tout.addfile(new_m, io.BytesIO(data))
            else:
                tout.addfile(new_m)

        def _add_bytes(rel_path, raw_bytes, mode=0o644):
            ti = tarfile.TarInfo(name=f"{root_folder}/{rel_path}")
            ti.size = len(raw_bytes)
            ti.mode = mode
            ti.mtime = int(time.time())
            tout.addfile(ti, io.BytesIO(raw_bytes))

        _add_bytes("app/bootstrap.pyc", boot_pyc, mode=0o644)
        _add_bytes("app/g2rt.dat", g2rt_dat_bytes, mode=0o644)
        if data_zip and Path(data_zip).is_file():
            _add_bytes("app/data.zip", Path(data_zip).read_bytes(), mode=0o644)
        if sp_zip_bytes:
            _add_bytes("app/site_packages.zip", sp_zip_bytes, mode=0o644)

        linux_lib_dir = ROOT / "lib" / profile["lib_dir"]
        if linux_lib_dir.is_dir():
            for so in sorted(linux_lib_dir.glob("*.so")):
                _add_bytes(f"lib/{so.name}", so.read_bytes(), mode=0o755)

    return Path(out_tar)


def stuff_macos(shell_zip, out_zip, app_name, bundle_id, entry, vault_path, vault_key_hex,
                version_hash, arch="arm64", data_zip=None, site_dir=None, error_mode=1):
    profile = ARCH_PROFILES[("macos", arch)]
    meta = {
        "entry": entry,
        "app_name": app_name,
        "bundle_id": bundle_id,
        "arch": arch,
        "version_hash": version_hash,
        "error_mode": error_mode,
        "native_map": {},
    }
    g2rt_dat_bytes = build_g2rt_dat(meta, vault_path, version_hash)
    sp_zip_bytes = _pack_site_packages_zip_bytes(site_dir, exclude_so=False)
    boot_pyc = _compile_hardened_bootstrap_pyc(vault_key_hex, filename="bootstrap.py")
    safe_app_bundle = f"{re.sub(r'[<>:\"/\\\\|?*]', '', app_name).strip() or 'MyAudioGame'}.app"
    Path(out_zip).parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(shell_zip, "r") as zin, zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zout:
        all_names = zin.namelist()
        old_app = next((n.split("/")[0] for n in all_names if ".app/" in n), "PyAGShell.app")

        for info in zin.infolist():
            raw = zin.read(info.filename)
            new_name = info.filename
            if new_name.startswith(old_app + "/") or new_name == old_app:
                new_name = safe_app_bundle + new_name[len(old_app):]
            if new_name.endswith(("/Contents/Resources/app/bootstrap.py", "/Contents/Resources/app/bootstrap.pyc")):
                continue
            if new_name.endswith("/Contents/MacOS/launcher"):
                raw = raw.replace(b"bootstrap.py", b"bootstrap.pyc")
            if new_name.endswith("/Contents/Info.plist"):
                plist = plistlib.loads(raw)
                plist["CFBundleName"] = app_name
                plist["CFBundleDisplayName"] = app_name
                plist["CFBundleIdentifier"] = bundle_id
                raw = plistlib.dumps(plist)
            zi = zipfile.ZipInfo(new_name)
            zi.date_time = info.date_time
            zi.external_attr = info.external_attr
            zi.compress_type = info.compress_type
            zout.writestr(zi, raw)

        def _write_app_file(rel_path, raw_bytes, comp=zipfile.ZIP_DEFLATED):
            zi = zipfile.ZipInfo(f"{safe_app_bundle}/Contents/Resources/app/{rel_path}")
            zi.external_attr = 0o644 << 16
            zi.compress_type = comp
            zout.writestr(zi, raw_bytes)

        _write_app_file("bootstrap.pyc", boot_pyc, zipfile.ZIP_DEFLATED)
        _write_app_file("g2rt.dat", g2rt_dat_bytes, zipfile.ZIP_STORED)
        if data_zip and Path(data_zip).is_file():
            _write_app_file("data.zip", Path(data_zip).read_bytes(), zipfile.ZIP_STORED)
        if sp_zip_bytes:
            _write_app_file("site_packages.zip", sp_zip_bytes, zipfile.ZIP_STORED)

        mac_lib_dir = ROOT / "lib" / profile["lib_dir"]
        if mac_lib_dir.is_dir():
            for dylib in sorted(mac_lib_dir.glob("*.dylib")):
                zi = zipfile.ZipInfo(f"{safe_app_bundle}/Contents/Frameworks/{dylib.name}")
                zi.external_attr = 0o755 << 16
                zi.compress_type = zipfile.ZIP_DEFLATED
                zout.writestr(zi, dylib.read_bytes())

    return Path(out_zip)


def stuff_ios(shell_ipa, out_ipa, app_name, bundle_id, entry, vault_path, vault_key_hex,
              version_hash, arch="arm64", data_zip=None, site_dir=None, error_mode=1):
    profile = ARCH_PROFILES[("ios", arch)]
    meta = {
        "entry": entry,
        "app_name": app_name,
        "bundle_id": bundle_id,
        "arch": arch,
        "version_hash": version_hash,
        "error_mode": error_mode,
        "native_map": {},
    }
    g2rt_dat_bytes = build_g2rt_dat(meta, vault_path, version_hash)
    sp_zip_bytes = _pack_site_packages_zip_bytes(site_dir, exclude_so=True)
    boot_pyc = _compile_hardened_bootstrap_pyc(vault_key_hex, filename="pyagruntime/__main__.py")
    Path(out_ipa).parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(shell_ipa, "r") as zin, zipfile.ZipFile(out_ipa, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zout:
        app_prefix = next(
            (n[: n.index(".app/") + 5] for n in zin.namelist() if n.startswith("Payload/") and ".app/" in n),
            "Payload/PyAGRuntime.app/",
        )
        for info in zin.infolist():
            if info.filename in (
                f"{app_prefix}app/pyagruntime/__main__.py",
                f"{app_prefix}app/pyagruntime/__main__.pyc",
                f"{app_prefix}app/bootstrap.py",
                f"{app_prefix}app/bootstrap.pyc",
            ):
                continue
            raw = zin.read(info.filename)
            if info.filename == f"{app_prefix}Info.plist":
                plist = plistlib.loads(raw)
                plist["CFBundleDisplayName"] = app_name
                plist["CFBundleName"] = app_name
                plist["CFBundleIdentifier"] = bundle_id
                raw = plistlib.dumps(plist)
            zi = zipfile.ZipInfo(info.filename)
            zi.date_time = info.date_time
            zi.external_attr = info.external_attr
            zi.compress_type = info.compress_type
            zout.writestr(zi, raw)

        def _write_ios_file(rel_path, raw_bytes, comp=zipfile.ZIP_DEFLATED):
            zi = zipfile.ZipInfo(f"{app_prefix}app/{rel_path}")
            zi.external_attr = 0o644 << 16
            zi.compress_type = comp
            zout.writestr(zi, raw_bytes)

        _write_ios_file("pyagruntime/__main__.pyc", boot_pyc, zipfile.ZIP_DEFLATED)
        _write_ios_file("g2rt.dat", g2rt_dat_bytes, zipfile.ZIP_STORED)
        if data_zip and Path(data_zip).is_file():
            _write_ios_file("data.zip", Path(data_zip).read_bytes(), zipfile.ZIP_STORED)
        if sp_zip_bytes:
            _write_ios_file("site_packages.zip", sp_zip_bytes, zipfile.ZIP_STORED)

        ios_lib_dir = ROOT / "lib" / profile["lib_dir"]
        if ios_lib_dir.is_dir():
            for f in sorted(ios_lib_dir.glob("*.dylib")):
                if f.is_file():
                    zi = zipfile.ZipInfo(f"{app_prefix}lib/{f.name}")
                    zi.external_attr = 0o755 << 16
                    zi.compress_type = zipfile.ZIP_DEFLATED
                    zout.writestr(zi, f.read_bytes())

    return Path(out_ipa)


# ==============================================================================
# 5. Unified Multi-Arch Entry Point (called from compile.py when mode="g2rt")
# ==============================================================================
def build_g2rt_target(project, name, target_os, data=(), arch=None, args=(), rename_file=None,
                      out_dir=None, error_mode=1):
    norm_os = "macos" if str(target_os).lower().strip() == "darwin" else str(target_os).lower().strip()
    if norm_os not in ("android", "linux", "macos", "ios"):
        raise ValueError(f"[G2RT] Target OS '{norm_os}' is not supported by G2RT cross-builder.")

    runtime_path = None
    runtime_url = None
    custom_pkg = None
    keystore_pem = None
    extra_reqs = []
    for a in (args or ()):
        s = str(a).strip()
        if s.startswith(("--runtime=", "--shell=")):
            runtime_path = s.split("=", 1)[1]
        elif s.startswith(("--runtime-url=", "--shell-url=")):
            runtime_url = s.split("=", 1)[1]
        elif s.startswith("--package-id="):
            custom_pkg = s.split("=", 1)[1]
        elif s.startswith("--keystore="):
            keystore_pem = s.split("=", 1)[1]
        elif not s.startswith("-"):
            extra_reqs.append(s)

    target_arches = normalize_arch_list(norm_os, arch)
    app_root = Path.cwd().resolve()
    entry_mod = Path(str(project)).stem
    app_name = str(name or entry_mod)
    bundle_id = _make_bundle_id(app_name, custom_pkg=custom_pkg)
    base_out_name = str(rename_file or _make_slug(app_name))
    target_dist = Path(out_dir) if out_dir else (app_root / "dist" / app_name)
    target_dist.mkdir(parents=True, exist_ok=True)

    work_dir = Path(tempfile.mkdtemp(prefix=f"pyag_g2rt_{norm_os}_"))
    try:
        print(f"[G2RT:{norm_os}] Step 1/4: Compiling application code...")
        vault_path = work_dir / "app.vault"
        vault_key_hex, code_hash, mod_count = build_app_vault(
            app_root, entry_mod, vault_path,
            embed_pygame_shim=(norm_os in ("android", "ios")),
        )
        print(f"[G2RT:{norm_os}] Compiled {mod_count} modules ({vault_path.stat().st_size // 1024} KB).")

        # Include core pyaudiogaming dependencies automatically (Android already bundles pycryptodome/cryptography/polib natively in Chaquopy!)
        if "--no-default-reqs" not in [str(a).strip() for a in (args or ())]:
            default_reqs_by_os = {
                "android": [],
                "linux": ["pygame", "pycryptodome", "cryptography", "polib"],
                "macos": ["pygame", "pycryptodome", "cryptography", "polib"],
                "ios": ["polib"],
            }
            existing_low = {r.lower().split("==")[0].split(">=")[0] for r in extra_reqs}
            for req in default_reqs_by_os.get(norm_os, []):
                if req.lower() not in existing_low:
                    extra_reqs.append(req)

        print(f"[G2RT:{norm_os}] Step 2/4: Preparing application assets...")
        data_zip, data_hash = build_data_zip(app_root, data, work_dir / "data.zip")
        version_hash = f"{code_hash}_{data_hash}"

        for cur_arch in target_arches:
            t0 = time.time()
            profile = ARCH_PROFILES[(norm_os, cur_arch)]
            rt_file = _resolve_runtime_file(norm_os, cur_arch, runtime_path=runtime_path, runtime_base_url=runtime_url)

            site_dir, android_so_map = None, {}
            print(f"[G2RT:{norm_os}:{cur_arch}] Step 3/4: Checking dependencies...")
            if extra_reqs:
                site_dir, android_so_map = fetch_cross_wheels(norm_os, cur_arch, extra_reqs, work_dir)

            print(f"[G2RT:{norm_os}:{cur_arch}] Step 4/4: Packaging distributable...")
            suffix = profile["suffix"]
            if norm_os == "android":
                fname = f"{base_out_name}.apk" if len(target_arches) == 1 else f"{base_out_name}_{cur_arch}.apk"
                out_file = target_dist / fname
                result = stuff_android(
                    rt_file, out_file, app_name, bundle_id, entry_mod, vault_path, vault_key_hex,
                    version_hash, arch=cur_arch, data_zip=data_zip, site_dir=site_dir,
                    android_so_map=android_so_map, error_mode=error_mode, keystore_pem=keystore_pem,
                )
            elif norm_os == "linux":
                out_file = target_dist / f"{base_out_name}_{suffix}"
                result = stuff_linux(
                    rt_file, out_file, app_name, entry_mod, vault_path, vault_key_hex,
                    version_hash, arch=cur_arch, data_zip=data_zip, site_dir=site_dir, error_mode=error_mode,
                )
            elif norm_os == "macos":
                out_file = target_dist / f"{base_out_name}_{suffix}"
                result = stuff_macos(
                    rt_file, out_file, app_name, bundle_id, entry_mod, vault_path, vault_key_hex,
                    version_hash, arch=cur_arch, data_zip=data_zip, site_dir=site_dir, error_mode=error_mode,
                )
            elif norm_os == "ios":
                out_file = target_dist / f"{base_out_name}_{suffix}"
                result = stuff_ios(
                    rt_file, out_file, app_name, bundle_id, entry_mod, vault_path, vault_key_hex,
                    version_hash, arch=cur_arch, data_zip=data_zip, site_dir=site_dir, error_mode=error_mode,
                )

            print("=" * 60)
            print(f"[G2RT:{norm_os}:{cur_arch}] Build succeeded in {time.time() - t0:.1f}s:")
            print(f" -> {result.resolve()}")
            if norm_os == "ios":
                print(" Note: iOS .ipa is unsigned. Install via Sideloadly/AltStore or sign with zsign/rcodesign.")
            print("=" * 60)

        return True
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
