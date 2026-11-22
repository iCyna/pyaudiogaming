# -*- coding: utf-8 -*-
# Copyright (c) 2025-2026 ihcyna (Labubu) <phucnggo29@gmail.com>. All rights reserved.
"""
Content-Addressable Deduplicated Solid LZMA2 Packer/Unpacker for G2RT Runtimes.
Compresses all 9 multi-arch runtimes (~163 MB) into a single ultra-compact
`pyaudiogaming/include/g2rt_toolkit.tar.xz` by:
  1. Extracting entries from all 9 archives (.apk, .ipa, .zip, .tar.gz)
  2. Deduplicating identical files across ALL OSes & architectures by SHA-256
  3. Sorting unique blobs by extension/size for maximum Solid LZMA2 dictionary efficiency
  4. Reconstructing exact runtime archives on-demand into %LOCALAPPDATA%/PyAudioGaming/runtimes/
Pure Python stdlib only (lzma + tarfile + zipfile) - zero external tools required.
"""

import hashlib
import io
import json
import lzma
import os
import shutil
import tarfile
import time
import zipfile
from pathlib import Path

G2RT_DIR = Path(__file__).resolve().parent
ROOT = G2RT_DIR.parent
DEFAULT_TOOLKIT_ARCHIVE = ROOT / "include" / "g2rt_toolkit.g2rt"


def pack_runtimes_to_toolkit(runtimes_dir, out_archive=None):
    """Pack all g2rt_* archives in `runtimes_dir` into a deduplicated Solid LZMA2 .tar.xz."""
    t0 = time.time()
    runtimes_dir = Path(runtimes_dir)
    out_archive = Path(out_archive or DEFAULT_TOOLKIT_ARCHIVE)
    out_archive.parent.mkdir(parents=True, exist_ok=True)

    runtime_files = sorted(
        p for p in runtimes_dir.iterdir()
        if p.is_file() and p.name.startswith("g2rt_")
    )
    if not runtime_files:
        raise FileNotFoundError(f"No g2rt_* runtime files found in {runtimes_dir}")

    orig_total = sum(p.stat().st_size for p in runtime_files)
    blobs = {}       # sha256_hex -> (ext_hint, raw_bytes)
    manifests = {}   # runtime_filename -> {"format": "zip"|"targz", "entries": [...]}
    dup_saved = 0

    for rf in runtime_files:
        print(f"  [Scan] {rf.name} ({rf.stat().st_size / (1024*1024):.1f} MB)...")
        entries = []
        if rf.name.endswith(".tar.gz"):
            fmt = "targz"
            with tarfile.open(rf, "r:gz") as tf:
                for m in tf.getmembers():
                    if m.isfile():
                        data = tf.extractfile(m).read()
                        h = hashlib.sha256(data).hexdigest()[:24]
                        if h in blobs:
                            dup_saved += len(data)
                        else:
                            blobs[h] = (Path(m.name).suffix.lower(), data)
                        entries.append({
                            "n": m.name, "t": "f", "m": m.mode, "h": h,
                        })
                    elif m.issym():
                        entries.append({
                            "n": m.name, "t": "l", "m": m.mode, "lnk": m.linkname,
                        })
                    elif m.isdir():
                        entries.append({
                            "n": m.name, "t": "d", "m": m.mode,
                        })
        else:
            fmt = "zip"
            with zipfile.ZipFile(rf, "r") as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        entries.append({
                            "n": info.filename, "t": "d",
                            "a": info.external_attr, "cs": info.create_system,
                        })
                    else:
                        data = zf.read(info.filename)
                        h = hashlib.sha256(data).hexdigest()[:24]
                        if h in blobs:
                            dup_saved += len(data)
                        else:
                            blobs[h] = (Path(info.filename).suffix.lower(), data)
                        entries.append({
                            "n": info.filename, "t": "f",
                            "a": info.external_attr, "cs": info.create_system,
                            "c": info.compress_type, "h": h,
                        })
        manifests[rf.name] = {"format": fmt, "entries": entries}

    unique_raw = sum(len(v[1]) for v in blobs.values())
    print(f"  [Dedup] Unique blobs: {len(blobs)} ({unique_raw / (1024*1024):.1f} MB), deduplicated: {dup_saved / (1024*1024):.1f} MB")
    print(f"  [LZMA2] Compressing solid stream into {out_archive.name} (this takes ~20-45s)...")

    # Sort blobs by (extension, size) so LZMA2 solid dictionary matches similar binaries/scripts!
    sorted_hashes = sorted(blobs.keys(), key=lambda k: (blobs[k][0], len(blobs[k][1])))

    filters = [{"id": lzma.FILTER_LZMA2, "preset": 7, "dict_size": 64 * 1024 * 1024}]
    import tempfile
    tmp_out = Path(tempfile.gettempdir()) / f"{out_archive.name}.part"
    with lzma.open(tmp_out, "wb", format=lzma.FORMAT_XZ, filters=filters) as xzf:
        with tarfile.open(fileobj=xzf, mode="w|") as tf:
            def _add(name, raw_bytes):
                ti = tarfile.TarInfo(name=name)
                ti.size = len(raw_bytes)
                ti.mode = 0o644
                tf.addfile(ti, io.BytesIO(raw_bytes))

            _add("manifests.json", json.dumps(manifests, separators=(",", ":")).encode("utf-8"))
            for h in sorted_hashes:
                _add(f"blobs/{h}", blobs[h][1])

    shutil.move(str(tmp_out), str(out_archive))
    final_mb = out_archive.stat().st_size / (1024 * 1024)
    orig_mb = orig_total / (1024 * 1024)
    ratio = (1.0 - final_mb / orig_mb) * 100.0
    print(
        f"[OK] Packed {len(runtime_files)} runtimes: {orig_mb:.1f} MB -> {final_mb:.1f} MB "
        f"(-{ratio:.1f}%) in {time.time() - t0:.1f}s -> {out_archive}"
    )
    return out_archive


def unpack_toolkit_to_cache(toolkit_archive, cache_dir, target_runtime=None):
    """
    Unpack `g2rt_toolkit.tar.xz` and reconstruct runtime archive(s) into `cache_dir`.
    If `target_runtime` is None, reconstructs all runtimes; otherwise reconstructs
    all missing runtimes (or specifically `target_runtime`) in one streaming pass.
    """
    toolkit_archive = Path(toolkit_archive)
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    if target_runtime and (cache_dir / target_runtime).is_file():
        return cache_dir / target_runtime

    t0 = time.time()
    print("[G2RT] Initializing runtime environment...")

    manifests = None
    needed_hashes = set()
    blobs = {}

    with lzma.open(toolkit_archive, "rb") as xzf:
        with tarfile.open(fileobj=xzf, mode="r|") as tf:
            for m in tf:
                if m.name == "manifests.json":
                    manifests = json.loads(tf.extractfile(m).read().decode("utf-8"))
                    if target_runtime:
                        if target_runtime not in manifests:
                            raise KeyError(f"Runtime '{target_runtime}' not found inside {toolkit_archive.name}")
                        rt_names = [target_runtime]
                    else:
                        rt_names = list(manifests.keys())
                    for rn in rt_names:
                        for e in manifests[rn]["entries"]:
                            if "h" in e:
                                needed_hashes.add(e["h"])
                elif m.name.startswith("blobs/"):
                    h = m.name[6:]
                    if h in needed_hashes:
                        blobs[h] = tf.extractfile(m).read()

    if not manifests:
        raise RuntimeError(f"Invalid toolkit archive (missing manifests.json): {toolkit_archive}")

    rt_to_build = [target_runtime] if target_runtime else list(manifests.keys())
    for rn in rt_to_build:
        out_path = cache_dir / rn
        if out_path.is_file():
            continue
        spec = manifests[rn]
        tmp_path = out_path.with_suffix(out_path.suffix + ".part")
        if spec["format"] == "targz":
            with tarfile.open(tmp_path, "w:gz", compresslevel=1) as tout:
                for e in spec["entries"]:
                    ti = tarfile.TarInfo(name=e["n"])
                    ti.mode = e["m"]
                    ti.mtime = 1735689600
                    if e["t"] == "f":
                        raw = blobs[e["h"]]
                        ti.size = len(raw)
                        tout.addfile(ti, io.BytesIO(raw))
                    elif e["t"] == "l":
                        ti.type = tarfile.SYMTYPE
                        ti.linkname = e["lnk"]
                        tout.addfile(ti)
                    elif e["t"] == "d":
                        ti.type = tarfile.DIRTYPE
                        tout.addfile(ti)
        else:
            with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as zout:
                for e in spec["entries"]:
                    zi = zipfile.ZipInfo(e["n"])
                    zi.date_time = (2025, 1, 1, 0, 0, 0)
                    zi.external_attr = e["a"]
                    zi.create_system = e.get("cs", 3)
                    if e["t"] == "d":
                        zout.writestr(zi, b"")
                    else:
                        comp = e.get("c", zipfile.ZIP_DEFLATED)
                        zi.compress_type = comp
                        zout.writestr(zi, blobs[e["h"]], compress_type=comp)
        shutil.move(str(tmp_path), str(out_path))

    print(f"[G2RT] Runtime initialized ({time.time() - t0:.1f}s).")
    return (cache_dir / target_runtime) if target_runtime else cache_dir


if __name__ == "__main__":
    src_dir = (ROOT / "include" / "g2rt_toolkit") if (ROOT / "include" / "g2rt_toolkit").is_dir() else (ROOT / "runtimes")
    pack_runtimes_to_toolkit(src_dir, DEFAULT_TOOLKIT_ARCHIVE)
