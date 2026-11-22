# -*- coding: utf-8 -*-
# Copyright (c) 2025-2026 ihcyna (Labubu) <phucnggo29@gmail.com>. All rights reserved.
"""
PyAudioGaming Universal G2RT Bootstrapper (Fast-Boot Edition)
Runs inside Android, iOS, Linux, and macOS G2RT runtimes:
  - Unmasks XOR `g2rt.dat` (app_meta.json + ChaCha20 app.vault) 100% IN RAM (zero disk writes!)
  - Checks 16-byte `g2rt.ver` before touching `data.zip` or `site_packages.zip` (<0.2s warm boot!)
  - Uses Python built-in `zipimport` for pure-Python `site_packages.zip` on Android/iOS (0s unpack!)
  - Initializes Android PygameView + preloads BASS + runs game on daemon thread (prevents ANR)
Pure Python stdlib only - zero external dependencies required to boot.
"""

import importlib.abc
import importlib.machinery
import importlib.util
import io
import json
import marshal
import os
import runpy
import shutil
import struct
import sys
import traceback
import zipfile
import zlib
from pathlib import Path


# ------------------------------------------------------------------------------
# Pure-Python ChaCha20 (RFC 8439)
# ------------------------------------------------------------------------------
def _rotl32(v, c):
    return ((v << c) & 0xFFFFFFFF) | (v >> (32 - c))


def _chacha20_block(key, counter, nonce):
    state = [
        0x61707865, 0x3320646E, 0x79622D32, 0x6B206574,
        *struct.unpack("<8I", key),
        counter & 0xFFFFFFFF,
        *struct.unpack("<3I", nonce),
    ]
    w = list(state)
    for _ in range(10):
        for a, b, c, d in ((0, 4, 8, 12), (1, 5, 9, 13), (2, 6, 10, 14), (3, 7, 11, 15)):
            w[a] = (w[a] + w[b]) & 0xFFFFFFFF; w[d] = _rotl32(w[d] ^ w[a], 16)
            w[c] = (w[c] + w[d]) & 0xFFFFFFFF; w[b] = _rotl32(w[b] ^ w[c], 12)
            w[a] = (w[a] + w[b]) & 0xFFFFFFFF; w[d] = _rotl32(w[d] ^ w[a], 8)
            w[c] = (w[c] + w[d]) & 0xFFFFFFFF; w[b] = _rotl32(w[b] ^ w[c], 7)
        for a, b, c, d in ((0, 5, 10, 15), (1, 6, 11, 12), (2, 7, 8, 13), (3, 4, 9, 14)):
            w[a] = (w[a] + w[b]) & 0xFFFFFFFF; w[d] = _rotl32(w[d] ^ w[a], 16)
            w[c] = (w[c] + w[d]) & 0xFFFFFFFF; w[b] = _rotl32(w[b] ^ w[c], 12)
            w[a] = (w[a] + w[b]) & 0xFFFFFFFF; w[d] = _rotl32(w[d] ^ w[a], 8)
            w[c] = (w[c] + w[d]) & 0xFFFFFFFF; w[b] = _rotl32(w[b] ^ w[c], 7)
    out = [(w[i] + state[i]) & 0xFFFFFFFF for i in range(16)]
    return struct.pack("<16I", *out)


def _chacha20_xor_py(key, nonce, data, counter=1):
    out = bytearray(len(data))
    mv = memoryview(data)
    pos = 0
    blk = counter
    n = len(data)
    while pos < n:
        ks = _chacha20_block(key, blk, nonce)
        chunk = mv[pos:pos + 64]
        clen = len(chunk)
        for i in range(clen):
            out[pos + i] = chunk[i] ^ ks[i]
        pos += clen
        blk = (blk + 1) & 0xFFFFFFFF
    return bytes(out)


_FAST_CHACHA20 = None  # Lazily resolved: "cryptography", "pycryptodome", or "py"


def _chacha20_xor(key, nonce, data, counter=1):
    """RFC 8439 ChaCha20 (counter=1). Uses C/Rust backend (~50-100x faster) with pure-Python fallback."""
    global _FAST_CHACHA20
    if _FAST_CHACHA20 is None:
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms  # noqa: F401
            _FAST_CHACHA20 = "cryptography"
        except Exception:
            try:
                from Crypto.Cipher import ChaCha20 as _PyCryptoChaCha20  # noqa: F401
                _FAST_CHACHA20 = "pycryptodome"
            except Exception:
                _FAST_CHACHA20 = "py"

    if _FAST_CHACHA20 == "cryptography":
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
            nonce16 = struct.pack("<I", counter & 0xFFFFFFFF) + nonce
            dec = Cipher(algorithms.ChaCha20(key, nonce16), mode=None).decryptor()
            return dec.update(data) + dec.finalize()
        except Exception:
            pass
    elif _FAST_CHACHA20 == "pycryptodome":
        try:
            from Crypto.Cipher import ChaCha20 as _PyCryptoChaCha20
            c = _PyCryptoChaCha20.new(key=key, nonce=nonce)
            if counter:
                c.seek((counter & 0xFFFFFFFF) * 64)
            return c.decrypt(data)
        except Exception:
            pass
    return _chacha20_xor_py(key, nonce, data, counter=counter)


# ------------------------------------------------------------------------------
# G2RT XOR-Masked Container Reader (100% IN RAM - never writes vault/meta to disk!)
# ------------------------------------------------------------------------------
def _read_g2rt_dat_in_ram(raw_bytes):
    """Unmask XOR `g2rt.dat` bytes in memory and return (meta_dict, vault_bytes)."""
    if len(raw_bytes) < 20 or raw_bytes[-20:-16] != b"G2RT":
        raise RuntimeError("Invalid G2RT container (missing 20-byte G2RT footer)")
    offset, _rhash_u32, xkey_u32 = struct.unpack_from("<QII", raw_bytes, len(raw_bytes) - 16)
    masked = raw_bytes[offset : len(raw_bytes) - 20]
    kbytes = struct.pack("<I", xkey_u32)
    xlat = [bytes(b ^ kbytes[i] for b in range(256)) for i in range(4)]
    ba = bytearray(masked)
    for rem in range(4):
        ba[rem::4] = bytes(ba[rem::4]).translate(xlat[rem])
    with zipfile.ZipFile(io.BytesIO(ba), "r") as zf:
        meta = json.loads(zf.read("app_meta.json").decode("utf-8"))
        vault_bytes = zf.read("app.vault") if "app.vault" in zf.namelist() else b""
    return meta, vault_bytes


# ------------------------------------------------------------------------------
# In-RAM ChaCha20 Vault Loader (with realistic virtual __file__ for all modules)
# ------------------------------------------------------------------------------
class _ShellVaultLoader(importlib.abc.InspectLoader):
    def __init__(self, vault_key, entry_info, virtual_file):
        self._key = vault_key
        self._is_pkg, self._is_pyc, self._nonce, self._cipher = entry_info
        self._virtual_file = virtual_file

    def is_package(self, fullname):
        return self._is_pkg

    def get_source(self, fullname):
        return None

    def get_code(self, fullname):
        raw = zlib.decompress(_chacha20_xor(self._key, self._nonce, self._cipher))
        if self._is_pyc:
            return marshal.loads(raw[16:] if len(raw) > 16 and raw[16:17] in (b"\xe3", b"c") else raw)
        return compile(raw, f"<vault:{fullname}>", "exec")

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        module.__file__ = self._virtual_file
        if self._is_pkg:
            module.__path__ = [str(Path(self._virtual_file).parent)]
            module.__package__ = module.__name__
        else:
            module.__package__ = module.__name__.rpartition(".")[0]
        code_obj = self.get_code(module.__name__)
        exec(code_obj, module.__dict__)


class _ShellVaultFinder(importlib.abc.MetaPathFinder):
    def __init__(self, vault_source, vault_key, virtual_root=None):
        self._key = vault_key
        self._virtual_root = Path(virtual_root) if virtual_root else Path.cwd()
        self._entries = {}
        data = vault_source if isinstance(vault_source, (bytes, bytearray, memoryview)) else Path(vault_source).read_bytes()
        self._load_index(data)

    def _load_index(self, data):
        if len(data) < 8 or data[:4] != b"PGV1":
            raise RuntimeError("Invalid app.vault format")
        (count,) = struct.unpack_from("<I", data, 4)
        pos = 8
        for _ in range(count):
            (nlen,) = struct.unpack_from("<H", data, pos)
            pos += 2
            fullname = bytes(data[pos:pos + nlen]).decode("utf-8")
            pos += nlen
            flags = data[pos]
            pos += 1
            nonce = bytes(data[pos:pos + 12])
            pos += 12
            (clen,) = struct.unpack_from("<I", data, pos)
            pos += 4
            cipher = bytes(data[pos:pos + clen])
            pos += clen
            self._entries[fullname] = (bool(flags & 1), bool(flags & 2), nonce, cipher)

    def _virtual_file_for(self, fullname, is_pkg):
        parts = fullname.split(".")
        if is_pkg:
            return str(self._virtual_root.joinpath(*parts, "__init__.py"))
        return str(self._virtual_root.joinpath(*parts[:-1], f"{parts[-1]}.py"))

    def find_spec(self, fullname, path=None, target=None):
        info = self._entries.get(fullname)
        if info is None:
            return None
        is_pkg = info[0]
        vfile = self._virtual_file_for(fullname, is_pkg)
        loader = _ShellVaultLoader(self._key, info, vfile)
        spec = importlib.machinery.ModuleSpec(fullname, loader, origin=vfile, is_package=is_pkg)
        spec.has_location = True
        if is_pkg:
            spec.submodule_search_locations = [str(Path(vfile).parent)]
        return spec


# ------------------------------------------------------------------------------
# Dynamic Native Module Finder (Android nativeLibraryDir lib__pymod__*.so)
# ------------------------------------------------------------------------------
class _ShellNativeFinder(importlib.abc.MetaPathFinder):
    def __init__(self, native_map, native_dir):
        self._map = dict(native_map or {})
        self._dir = Path(native_dir) if native_dir else None

    def find_spec(self, fullname, path=None, target=None):
        if not self._dir or fullname not in self._map:
            return None
        so_path = self._dir / self._map[fullname]
        if not so_path.is_file():
            return None
        loader = importlib.machinery.ExtensionFileLoader(fullname, str(so_path))
        return importlib.machinery.ModuleSpec(fullname, loader, origin=str(so_path))


# ------------------------------------------------------------------------------
# Fast Android Asset Reader (checks 16-byte g2rt.ver -> zero copy on warm boot!)
# ------------------------------------------------------------------------------
def _detect_android_paths():
    try:
        from java import jclass
        activity_thread = jclass("android.app.ActivityThread")
        app = activity_thread.currentApplication()
        if app is not None:
            files_dir = Path(str(app.getFilesDir().getAbsolutePath()))
            native_dir = str(app.getApplicationInfo().nativeLibraryDir)
            return files_dir, native_dir, app.getAssets()
    except Exception:
        pass
    return None, None, None


def _read_android_asset_bytes(asset_mgr, asset_name):
    try:
        stream = asset_mgr.open(asset_name)
    except Exception:
        return None
    out = bytearray()
    buf = bytearray(65536)
    try:
        while True:
            n = stream.read(buf)
            if n <= 0:
                break
            out.extend(buf[:n])
    finally:
        try:
            stream.close()
        except Exception:
            pass
    return bytes(out)


def _copy_android_asset_to_file(asset_mgr, asset_name, out_path):
    try:
        stream = asset_mgr.open(asset_name)
    except Exception:
        return False
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    buf = bytearray(262144)
    try:
        with open(out_path, "wb") as f:
            while True:
                n = stream.read(buf)
                if n <= 0:
                    break
                f.write(memoryview(buf)[:n])
    finally:
        try:
            stream.close()
        except Exception:
            pass
    return True


def _sync_zip_cached(zip_path, dest_dir, stamp_value):
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp_file = dest_dir / ".pyag_stamp"
    if stamp_file.is_file() and stamp_file.read_text(encoding="utf-8").strip() == str(stamp_value):
        return False
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)
    stamp_file.write_text(str(stamp_value), encoding="utf-8")
    return True


def _report_error(error_mode, exc_text, log_dir):
    if error_mode == 2:
        return
    try:
        log_path = Path(log_dir) / "pyag_error.log"
        log_path.write_text(exc_text, encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.stderr.write(exc_text + "\n")
    sys.stderr.flush()


# Split-key placeholders injected & compiled to bootstrap.pyc (optimize=2) at build time
_G2RT_K1 = b""
_G2RT_K2 = b""


def _derive_vault_key(meta):
    if _G2RT_K1 and _G2RT_K2 and len(_G2RT_K1) == len(_G2RT_K2):
        return bytes(a ^ b for a, b in zip(_G2RT_K1, _G2RT_K2))
    vhex = meta.get("vault_key", "")
    return bytes.fromhex(vhex) if vhex else b""


def main():
    here = Path(__file__).resolve().parent
    payload_dir = here
    writable_dir = here
    native_dir = os.environ.get("PYAG_NATIVE_LIB_DIR")

    android_files_dir, android_native_dir, asset_mgr = _detect_android_paths()
    meta = None
    vault_bytes = b""

    if android_files_dir is not None:
        native_dir = android_native_dir or native_dir
        payload_dir = android_files_dir / "_pyag_payload"
        writable_dir = android_files_dir / "game_data"
        payload_dir.mkdir(parents=True, exist_ok=True)
        writable_dir.mkdir(parents=True, exist_ok=True)

        # Read tiny g2rt.dat (~1MB) straight into RAM - zero disk copy!
        dat_bytes = _read_android_asset_bytes(asset_mgr, "g2rt.dat") if asset_mgr else None
        if dat_bytes:
            meta, vault_bytes = _read_g2rt_dat_in_ram(dat_bytes)
        else:
            print("[G2RT] Missing assets/g2rt.dat in Android APK.")
            return

        version_hash = meta.get("version_hash", "0")
        ver_stamp = payload_dir / ".g2rt_ver"
        need_sync = not (ver_stamp.is_file() and ver_stamp.read_text(encoding="utf-8").strip() == version_hash)
        if need_sync and asset_mgr is not None:
            # Copy site_packages.zip (used directly via zipimport - 0s unpack!)
            _copy_android_asset_to_file(asset_mgr, "site_packages.zip", payload_dir / "site_packages.zip")
            # Copy & unpack data.zip ONLY ONCE per version_hash, then delete temp zip to save storage!
            tmp_data_zip = payload_dir / "data.zip"
            if _copy_android_asset_to_file(asset_mgr, "data.zip", tmp_data_zip):
                _sync_zip_cached(tmp_data_zip, writable_dir, version_hash)
                try:
                    tmp_data_zip.unlink()
                except OSError:
                    pass
            ver_stamp.write_text(version_hash, encoding="utf-8")
    else:
        for cand in (here, here.parent, here / "app"):
            if (cand / "g2rt.dat").is_file():
                payload_dir = cand
                break
        g2rt_dat = payload_dir / "g2rt.dat"
        if not g2rt_dat.is_file():
            print(f"[G2RT] No g2rt.dat found in {payload_dir}.")
            return
        meta, vault_bytes = _read_g2rt_dat_in_ram(g2rt_dat.read_bytes())
        version_hash = meta.get("version_hash", "0")
        if sys.platform == "ios":
            writable_dir = Path.home() / "Documents" / "game_data"
        else:
            writable_dir = Path.home() / ".cache" / "G2RT" / f"{meta.get('entry', 'app')}_{version_hash[:8]}"
            # Extract data.zip once per version_hash
        data_zip = payload_dir / "data.zip"
        if data_zip.is_file():
            _sync_zip_cached(data_zip, writable_dir, version_hash)
        else:
            writable_dir = payload_dir

    entry = meta.get("entry", "main")
    version_hash = meta.get("version_hash", "0")
    error_mode = int(meta.get("error_mode", 1))
    native_map = meta.get("native_map") or {}
    vault_key = _derive_vault_key(meta)

    if native_dir:
        os.environ["PYAG_NATIVE_LIB_DIR"] = str(native_dir)

    try:
        # 1. Mount site_packages.zip (0s zipimport on Android/iOS; 1-time cached unpack on Linux/macOS)
        sp_zip = payload_dir / "site_packages.zip"
        if sp_zip.is_file():
            if android_files_dir is not None or sys.platform == "ios":
                if str(sp_zip) not in sys.path:
                    sys.path.insert(0, str(sp_zip))
            else:
                sp_cache = Path.home() / ".cache" / "G2RT" / f"sp_{version_hash[:12]}"
                _sync_zip_cached(sp_zip, sp_cache, version_hash)
                if str(sp_cache) not in sys.path:
                    sys.path.insert(0, str(sp_cache))

        # 2. Install dynamic native finder (Android lib__pymod__*.so)
        if native_map and native_dir:
            sys.meta_path.insert(0, _ShellNativeFinder(native_map, native_dir))

        # 3. Install ChaCha20-encrypted app.vault finder (100% in RAM, with virtual __file__)
        if vault_bytes and vault_key:
            sys.meta_path.insert(0, _ShellVaultFinder(vault_bytes, vault_key, virtual_root=writable_dir))

        if writable_dir.is_dir():
            os.chdir(writable_dir)

        sys.frozen = True

        # 4. Android UI bridge + BASS core preload + background game thread
        if android_files_dir is not None:
            import threading
            android_ui = False
            try:
                import pygame
                if hasattr(pygame, "_android_bridge") and pygame._android_bridge.is_android_java_available():
                    android_ui = bool(pygame._android_bridge.bootstrap_android())
            except Exception as _e:
                sys.stderr.write(f"[G2RT] Warning initializing Android pygame view: {_e}\n")
                traceback.print_exc()

            def _shutdown_android_app():
                try:
                    from pyaudiogaming.sound_modules import control as _snd_ctrl
                    _snd_ctrl.shutdown_sound()
                except Exception:
                    pass
                try:
                    import pygame as _pg
                    if hasattr(_pg, "_android_bridge") and hasattr(_pg._android_bridge, "close_app"):
                        _pg._android_bridge.close_app()
                except Exception:
                    pass

            def _run_android_entry():
                clean_exit = False
                try:
                    # Preload core BASS libs inside background thread (keeps Android UI onCreate instant!)
                    try:
                        from pyaudiogaming import system as _sys_chk
                        for _core_lib in ("libbass", "libbassmix", "libbass_fx"):
                            try:
                                _sys_chk.load_dll(_core_lib)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    runpy.run_module(entry, run_name="__main__", alter_sys=True)
                    clean_exit = True
                except SystemExit:
                    clean_exit = True
                except Exception:
                    tb = traceback.format_exc()
                    _report_error(error_mode, tb, writable_dir)
                    if error_mode == 1:
                        shown = False
                        try:
                            import pygame as _pg
                            if hasattr(_pg, "_android_bridge") and hasattr(_pg._android_bridge, "show_error_dialog"):
                                shown = bool(_pg._android_bridge.show_error_dialog("Application Error", tb))
                        except Exception:
                            pass
                        if not shown:
                            _shutdown_android_app()
                    else:
                        _shutdown_android_app()
                if clean_exit:
                    _shutdown_android_app()

            if android_ui:
                t = threading.Thread(target=_run_android_entry, name="PyAudioGamingMain", daemon=True)
                t.start()
            else:
                _run_android_entry()
            return

        # 5. Launch game entry module (Desktop / iOS)
        runpy.run_module(entry, run_name="__main__", alter_sys=True)
    except SystemExit:
        raise
    except Exception:
        _report_error(error_mode, traceback.format_exc(), writable_dir)
        if error_mode != 2:
            raise


if __name__ == "__main__":
    main()
