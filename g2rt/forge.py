# -*- coding: utf-8 -*-
# Copyright (c) 2025-2026 ihcyna (Labubu) <phucnggo29@gmail.com>. All rights reserved.
"""
Forge ULTRA-SLIM G2RT-style multi-arch PyAudioGaming runtime shells directly on Windows:
  Linux:   shell_linux_x64.tar.gz, shell_linux_arm64.tar.gz, shell_linux_armhf.tar.gz
  macOS:   shell_macos_arm64.zip, shell_macos_x64.zip
  Android: shell_android_arm64.apk, shell_android_x86_64.apk

G2RT Slim Rules applied to ALL platforms & architectures:
  - NO BASS / Steam Audio (phonon) / tags native libs embedded in shells!
  - Strips Python stdlib bloat (test, tkinter, tcl/tk, idlelib, ensurepip, venv, pydoc_data,
    include, share, *.a, pip, __pycache__, etc.).
  - Streams python-build-standalone in memory so Unix symlinks & +x permissions are 100% preserved.
"""

import io
import json
import os
import plistlib
import re
import shutil
import stat
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

G2RT_DIR = Path(__file__).resolve().parent
ROOT = G2RT_DIR.parent
RUNTIMES_DIR = ROOT / "runtimes"
RUNTIMES_DIR.mkdir(parents=True, exist_ok=True)

_SKIP_PATH_PARTS = {
    "test", "tests", "idlelib", "tkinter", "turtledemo", "ensurepip",
    "venv", "pydoc_data", "lib2to3", "__pycache__", "include", "share",
    "tcl8", "tcl8.6", "tk8.6", "itcl4.2.4", "sqlite3.45.3", "tdbc1.1.7",
    "thread2.8.9", "pip", "setuptools", "wheel", "pkg_resources",
}
_SKIP_FILE_PREFIXES = ("_tkinter", "libtcl", "libtk", "tcl", "tk")
_SKIP_FILE_EXTS = (".a", ".pyc", ".pyo", ".pdb", ".h", ".pc")

LINUX_ARCH_PBS = {
    "x64": ("x86_64-unknown-linux-gnu-install_only_stripped", "g2rt_linux_x64.tar.gz"),
    "arm64": ("aarch64-unknown-linux-gnu-install_only_stripped", "g2rt_linux_aarch64.tar.gz"),
    "armhf": ("armv7-unknown-linux-gnueabihf-install_only_stripped", "g2rt_linux_armhf.tar.gz"),
}

MACOS_ARCH_PBS = {
    "arm64": ("aarch64-apple-darwin-install_only_stripped", "g2rt_macos_arm64.zip"),
    "x64": ("x86_64-apple-darwin-install_only_stripped", "g2rt_macos_x64.zip"),
}

ANDROID_ARCH_ABI = {
    "arm64": ("arm64-v8a", "g2rt_android_arm64-v8a.apk"),
    "x86_64": ("x86_64", "g2rt_android_x86_64.apk"),
}


def _should_skip_pbs_member(member_name):
    parts = Path(member_name).parts
    for p in parts:
        pl = p.lower()
        if pl in _SKIP_PATH_PARTS or pl.endswith(".dist-info") or pl.startswith(("tcl", "tk", "config-3.")):
            return True
    fname = parts[-1].lower() if parts else ""
    if fname.endswith(_SKIP_FILE_EXTS):
        return True
    if fname.startswith(_SKIP_FILE_PREFIXES) and fname.endswith((".so", ".dylib")):
        return True
    if len(parts) >= 3 and parts[-2] == "bin" and fname not in ("python3", "python3.12", "python"):
        return True
    return False


def _fetch_pbs_asset_url(substr, py_minor="3.12"):
    api_url = "https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest"
    req = urllib.request.Request(api_url, headers={"User-Agent": "PyAudioGaming-G2RT-Forge/2.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if f"cpython-{py_minor}." in name and substr in name and name.endswith(".tar.gz"):
            return asset["browser_download_url"], name
    raise RuntimeError(f"Could not find python-build-standalone asset matching '{substr}' for Python {py_minor}")


def _download_with_progress(url, dest_path):
    dest_path = Path(dest_path)
    if dest_path.is_file() and dest_path.stat().st_size > 1_000_000:
        print(f"  [Cache] Reusing {dest_path.name}")
        return dest_path
    print(f"  [Download] {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "PyAudioGaming-G2RT-Forge/2.1"})
    tmp = dest_path.with_suffix(dest_path.suffix + ".part")
    with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as f:
        while True:
            chunk = resp.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
    shutil.move(str(tmp), str(dest_path))
    print(f"  [Download] Saved {dest_path.name} ({dest_path.stat().st_size / (1024*1024):.1f} MB)")
    return dest_path


def forge_linux_runtime(cache_dir=None, arch="x64", out_dir=None, py_minor="3.12"):
    arch = arch.lower().strip()
    if arch not in LINUX_ARCH_PBS:
        raise ValueError(f"Unsupported Linux arch for local forge: {arch} (supported: {list(LINUX_ARCH_PBS)})")
    substr, shell_fname = LINUX_ARCH_PBS[arch]
    cache_dir = Path(cache_dir or (Path(tempfile.gettempdir()) / "pyag_pbs_cache"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    target_dir = Path(out_dir or RUNTIMES_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== Forging Slim G2RT Linux [{arch}] Shell ({shell_fname}) ===")
    t0 = time.time()
    url, fname = _fetch_pbs_asset_url(substr, py_minor)
    pbs_tar = _download_with_progress(url, cache_dir / fname)

    out_tar = target_dir / shell_fname
    with tarfile.open(pbs_tar, "r:gz") as tin, tarfile.open(out_tar, "w:gz", compresslevel=9) as tout:
        for m in tin.getmembers():
            if _should_skip_pbs_member(m.name):
                continue
            new_m = tarfile.TarInfo(name=f"pyag_shell/{m.name}")
            new_m.mode = m.mode
            new_m.mtime = m.mtime
            new_m.type = m.type
            new_m.linkname = m.linkname
            if m.isfile():
                data = tin.extractfile(m).read()
                new_m.size = len(data)
                tout.addfile(new_m, io.BytesIO(data))
            else:
                tout.addfile(new_m)

        def _add_bytes(rel_path, raw_bytes, mode=0o644):
            ti = tarfile.TarInfo(name=f"pyag_shell/{rel_path}")
            ti.size = len(raw_bytes)
            ti.mode = mode
            ti.mtime = int(time.time())
            tout.addfile(ti, io.BytesIO(raw_bytes))

        _add_bytes("app/bootstrap.py", (G2RT_DIR / "bootstrap.py").read_bytes(), mode=0o644)
        run_sh = (
            "#!/usr/bin/env bash\n"
            "set -e\n"
            'DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
            'export LD_LIBRARY_PATH="$DIR/lib:$DIR/python/lib:${LD_LIBRARY_PATH:-}"\n'
            'export PYAG_NATIVE_LIB_DIR="$DIR/lib"\n'
            'exec "$DIR/python/bin/python3" -s "$DIR/app/bootstrap.py" "$@"\n'
        ).encode("utf-8")
        _add_bytes("run.sh", run_sh, mode=0o755)

    print(f"[OK] Forged SLIM {out_tar} ({out_tar.stat().st_size / (1024*1024):.1f} MB) in {time.time()-t0:.1f}s")
    return out_tar


def forge_macos_runtime(cache_dir=None, arch="arm64", out_dir=None, py_minor="3.12"):
    arch = arch.lower().strip()
    if arch not in MACOS_ARCH_PBS:
        raise ValueError(f"Unsupported macOS arch for local forge: {arch} (supported: {list(MACOS_ARCH_PBS)})")
    substr, shell_fname = MACOS_ARCH_PBS[arch]
    cache_dir = Path(cache_dir or (Path(tempfile.gettempdir()) / "pyag_pbs_cache"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    target_dir = Path(out_dir or RUNTIMES_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== Forging Slim G2RT macOS [{arch}] Shell ({shell_fname}) ===")
    t0 = time.time()
    url, fname = _fetch_pbs_asset_url(substr, py_minor)
    pbs_tar = _download_with_progress(url, cache_dir / fname)

    out_zip = target_dir / shell_fname
    app_root = "PyAGShell.app"

    with tarfile.open(pbs_tar, "r:gz") as tin, zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zout:
        def _zwrite(arcname, raw_bytes, unix_mode=0o644, is_symlink=False):
            zi = zipfile.ZipInfo(arcname)
            zi.date_time = (2025, 1, 1, 0, 0, 0)
            if is_symlink:
                zi.external_attr = (stat.S_IFLNK | 0o777) << 16
                zi.create_system = 3
                zout.writestr(zi, raw_bytes, compress_type=zipfile.ZIP_STORED)
            else:
                zi.external_attr = (stat.S_IFREG | unix_mode) << 16
                zi.create_system = 3
                zout.writestr(zi, raw_bytes, compress_type=zipfile.ZIP_DEFLATED)

        for m in tin.getmembers():
            if _should_skip_pbs_member(m.name):
                continue
            arc = f"{app_root}/Contents/Resources/{m.name}"
            if m.issym():
                _zwrite(arc, m.linkname.encode("utf-8"), is_symlink=True)
            elif m.isfile():
                data = tin.extractfile(m).read()
                _zwrite(arc, data, unix_mode=(m.mode & 0o777) or 0o644)

        _zwrite(f"{app_root}/Contents/Resources/app/bootstrap.py", (G2RT_DIR / "bootstrap.py").read_bytes(), unix_mode=0o644)
        launcher_sh = (
            "#!/usr/bin/env bash\n"
            "set -e\n"
            'CONTENTS="$(cd "$(dirname "$0")/.." && pwd)"\n'
            'export DYLD_LIBRARY_PATH="$CONTENTS/Frameworks:$CONTENTS/Resources/python/lib:${DYLD_LIBRARY_PATH:-}"\n'
            'export PYAG_NATIVE_LIB_DIR="$CONTENTS/Frameworks"\n'
            'exec "$CONTENTS/Resources/python/bin/python3" -s "$CONTENTS/Resources/app/bootstrap.py" "$@"\n'
        ).encode("utf-8")
        _zwrite(f"{app_root}/Contents/MacOS/launcher", launcher_sh, unix_mode=0o755)

        plist_bytes = plistlib.dumps({
            "CFBundleName": "PyAGShell",
            "CFBundleDisplayName": "PyAGShell",
            "CFBundleIdentifier": "com.pyaudiogaming.shell",
            "CFBundleVersion": "1.0.0",
            "CFBundleShortVersionString": "1.0.0",
            "CFBundlePackageType": "APPL",
            "CFBundleExecutable": "launcher",
            "NSHighResolutionCapable": True,
        })
        _zwrite(f"{app_root}/Contents/Info.plist", plist_bytes, unix_mode=0o644)

    print(f"[OK] Forged SLIM {out_zip} ({out_zip.stat().st_size / (1024*1024):.1f} MB) in {time.time()-t0:.1f}s")
    return out_zip


def forge_android_runtime(arch="arm64", out_dir=None):
    arch = arch.lower().strip()
    if arch not in ANDROID_ARCH_ABI:
        raise ValueError(f"Unsupported Android arch for Python 3.12 forge: {arch} (supported: {list(ANDROID_ARCH_ABI)})")
    abi, shell_fname = ANDROID_ARCH_ABI[arch]
    target_dir = Path(out_dir or RUNTIMES_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== Forging Slim G2RT Android [{abi}] Shell ({shell_fname}) ===")
    t0 = time.time()
    from pyaudiogaming.compile import _get_portable_env, _ensure_briefcase, _run_briefcase

    env = _get_portable_env()
    _ensure_briefcase(env)

    ws = Path(tempfile.mkdtemp(prefix=f"pyag_forge_android_{arch}_"))
    try:
        src = ws / "src" / "placeholder"
        src.mkdir(parents=True, exist_ok=True)
        (ws / "LICENSE").write_text("MIT\n", encoding="utf-8")
        (ws / "pyproject.toml").write_text(
            '[build-system]\nrequires = ["briefcase"]\n\n'
            '[tool.briefcase]\n'
            'project_name = "PYAG_SHELL_APP_NAME_PLACEHOLDER"\n'
            'bundle = "com.pyaudiogaming.shell"\n'
            'version = "1.0.0"\n'
            'url = "https://github.com/pyaudiogaming"\n'
            'license = "MIT"\n'
            'license-files = ["LICENSE"]\n'
            'author = "PyAudioGaming"\n'
            'author_email = "dev@pyaudiogaming.local"\n\n'
            '[tool.briefcase.app.placeholder]\n'
            'formal_name = "PYAG_SHELL_APP_NAME_PLACEHOLDER"\n'
            'description = "PyAudioGaming Slim Android Shell"\n'
            'sources = ["src/placeholder"]\n'
            'requires = ["pycryptodome", "cryptography", "polib"]\n\n'
            '[tool.briefcase.app.placeholder.android]\n'
            'requires = []\n'
            f'android_abis = ["{abi}"]\n'
            'build_gradle_dependencies = [\n'
            '    "androidx.appcompat:appcompat:1.0.2",\n'
            '    "androidx.constraintlayout:constraintlayout:1.1.3",\n'
            '    "androidx.swiperefreshlayout:swiperefreshlayout:1.1.0",\n'
            ']\n\n'
            '[tool.briefcase.app.placeholder.android.permission]\n'
            '"android.permission.INTERNET" = true\n'
            '"android.permission.ACCESS_NETWORK_STATE" = true\n'
            '"android.permission.RECORD_AUDIO" = true\n'
            '"android.permission.MODIFY_AUDIO_SETTINGS" = true\n'
            '"android.permission.WAKE_LOCK" = true\n'
            '"android.permission.VIBRATE" = true\n'
            '"android.permission.POST_NOTIFICATIONS" = true\n'
            '"android.permission.USE_FULL_SCREEN_INTENT" = true\n',
            encoding="utf-8",
        )
        (src / "__init__.py").write_text("", encoding="utf-8")
        shutil.copy2(G2RT_DIR / "bootstrap.py", src / "__main__.py")

        _run_briefcase(["create", "android", "--no-input"], cwd=ws, env=env)
        gradle_dir = ws / "build" / "placeholder" / "android" / "gradle"

        # Inject org.pyaudiogaming.PygameView Java bridge into Android classes.dex!
        java_src_dir = ROOT / "pygame_shim" / "java"
        if not java_src_dir.is_dir():
            java_src_dir = ROOT / "include" / "android" / "java"
        if java_src_dir.is_dir():
            shutil.copytree(java_src_dir, gradle_dir / "app" / "src" / "main" / "java", dirs_exist_ok=True)
            print("  [Java] Injected org.pyaudiogaming.PygameView into Gradle project")

        manifest = gradle_dir / "app" / "src" / "main" / "AndroidManifest.xml"
        txt = manifest.read_text(encoding="utf-8")
        txt = re.sub(r'android:label="[^"]*"', 'android:label="PYAG_SHELL_APP_NAME_PLACEHOLDER"', txt)
        manifest.write_text(txt, encoding="utf-8")

        build_gradle = gradle_dir / "app" / "build.gradle"
        if build_gradle.is_file():
            bg = build_gradle.read_text(encoding="utf-8")
            for other_abi in ("arm64-v8a", "armeabi-v7a", "x86", "x86_64"):
                if other_abi != abi:
                    bg = bg.replace(f'"{other_abi}", ', "").replace(f', "{other_abi}"', "")
            if "useLegacyPackaging" not in bg:
                bg = bg.replace(
                    "android {",
                    "android {\n"
                    "    defaultConfig {\n"
                    "        python {\n"
                    '            extractPackages "*"\n'
                    "        }\n"
                    "    }\n"
                    "    packagingOptions {\n"
                    "        jniLibs {\n"
                    "            useLegacyPackaging = true\n"
                    "        }\n"
                    "    }\n",
                    1,
                )
            build_gradle.write_text(bg, encoding="utf-8")

        _run_briefcase(["build", "android", "--no-input"], cwd=ws, env=env)

        apks = list((gradle_dir / "app" / "build" / "outputs" / "apk").rglob("*.apk"))
        if not apks:
            raise RuntimeError("No .apk produced by briefcase build android!")
        out_apk = target_dir / shell_fname
        shutil.copy2(apks[0], out_apk)
        print(f"[OK] Forged SLIM {out_apk} ({out_apk.stat().st_size / (1024*1024):.1f} MB) in {time.time()-t0:.1f}s")
        return out_apk
    finally:
        shutil.rmtree(ws, ignore_errors=True)


if __name__ == "__main__":
    raw_targets = sys.argv[1:] or ["linux:x64", "macos:arm64", "android:arm64"]
    for item in raw_targets:
        if ":" in item:
            os_name, arch = item.split(":", 1)
        else:
            os_name = item
            arch = {"linux": "x64", "macos": "arm64", "android": "arm64"}.get(os_name, "x64")
        if os_name == "linux":
            forge_linux_runtime(arch=arch)
        elif os_name == "macos":
            forge_macos_runtime(arch=arch)
        elif os_name == "android":
            forge_android_runtime(arch=arch)
        else:
            print(f"[Skip] Unsupported local target: {item}")
