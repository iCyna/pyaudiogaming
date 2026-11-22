# -*- coding: utf-8 -*-
# Copyright (c) 2025-2026 ihcyna (Labubu) <phucnggo29@gmail.com>. All rights reserved.
"""
Pure-Python Android APK Patcher (AXML), Zipaligner & APK Signature Scheme v2 Signer.
Zero JDK, zero Android SDK, zero Gradle required on the build machine.
"""

import datetime
import hashlib
import io
import os
import struct
import zipfile
from pathlib import Path


# ==============================================================================
# 1. Android Binary XML (AXML) String Pool Patcher
# ==============================================================================
_RES_XML_TYPE = 0x0003
_RES_STRING_POOL_TYPE = 0x0001
_UTF8_FLAG = 1 << 8


def _encode_utf8_len(val):
    if val < 0x80:
        return bytes([val])
    return bytes([0x80 | ((val >> 8) & 0x7F), val & 0xFF])


def _encode_utf16_len(val):
    if val < 0x8000:
        return struct.pack("<H", val)
    return struct.pack("<HH", 0x8000 | ((val >> 16) & 0x7FFF), val & 0xFFFF)


def _decode_utf8_str(buf, offset):
    # Length in UTF-16 code units
    b0 = buf[offset]
    offset += 1
    if b0 & 0x80:
        offset += 1
    # Length in UTF-8 bytes
    b1 = buf[offset]
    offset += 1
    if b1 & 0x80:
        byte_len = ((b1 & 0x7F) << 8) | buf[offset]
        offset += 1
    else:
        byte_len = b1
    return buf[offset:offset + byte_len].decode("utf-8", errors="surrogatepass")


def _decode_utf16_str(buf, offset):
    u0 = struct.unpack_from("<H", buf, offset)[0]
    offset += 2
    if u0 & 0x8000:
        u1 = struct.unpack_from("<H", buf, offset)[0]
        offset += 2
        char_len = ((u0 & 0x7FFF) << 16) | u1
    else:
        char_len = u0
    raw = buf[offset:offset + char_len * 2]
    return raw.decode("utf-16-le", errors="surrogatepass")


def patch_android_manifest_axml(axml_bytes, replacements):
    """
    Replace exact or substring placeholders in an Android Binary XML (AXML) string pool.
    `replacements`: dict[str, str], e.g. {
        "com.pyaudiogaming.shell.placeholder": "com.mygame.app",
        "PYAG_SHELL_APP_NAME_PLACEHOLDER": "My Audio Game",
    }
    Returns patched AXML bytes.
    """
    if not replacements or len(axml_bytes) < 36:
        return axml_bytes

    file_type, file_hdr_size, _file_size = struct.unpack_from("<HHI", axml_bytes, 0)
    if file_type != _RES_XML_TYPE:
        raise ValueError(f"Not a valid Android Binary XML file (magic=0x{file_type:04x})")

    sp_pos = file_hdr_size
    sp_type, sp_hdr_size, sp_chunk_size = struct.unpack_from("<HHI", axml_bytes, sp_pos)
    if sp_type != _RES_STRING_POOL_TYPE:
        raise ValueError(f"Expected RES_STRING_POOL_TYPE at offset {sp_pos}, got 0x{sp_type:04x}")

    string_count, style_count, flags, strings_start, styles_start = struct.unpack_from(
        "<IIIII", axml_bytes, sp_pos + 8
    )
    is_utf8 = bool(flags & _UTF8_FLAG)

    offsets_pos = sp_pos + sp_hdr_size
    str_offsets = list(struct.unpack_from(f"<{string_count}I", axml_bytes, offsets_pos))
    style_offsets_bytes = axml_bytes[
        offsets_pos + string_count * 4 : offsets_pos + (string_count + style_count) * 4
    ]

    strings_base = sp_pos + strings_start
    strings_end = (sp_pos + styles_start) if style_count > 0 else (sp_pos + sp_chunk_size)
    styles_data = axml_bytes[strings_end : sp_pos + sp_chunk_size] if style_count > 0 else b""
    rest_of_file = axml_bytes[sp_pos + sp_chunk_size :]

    # Decode and patch strings
    decoded = []
    changed = False
    for off in str_offsets:
        s = _decode_utf8_str(axml_bytes, strings_base + off) if is_utf8 else _decode_utf16_str(axml_bytes, strings_base + off)
        new_s = s
        for old_val, new_val in replacements.items():
            if old_val and old_val in new_s:
                new_s = new_s.replace(old_val, new_val)
        if new_s != s:
            changed = True
        decoded.append(new_s)

    if not changed:
        return axml_bytes

    # Re-encode string pool
    new_str_offsets = []
    str_blob = bytearray()
    for s in decoded:
        new_str_offsets.append(len(str_blob))
        if is_utf8:
            utf16_units = len(s.encode("utf-16-le")) // 2
            utf8_bytes = s.encode("utf-8")
            str_blob.extend(_encode_utf8_len(utf16_units))
            str_blob.extend(_encode_utf8_len(len(utf8_bytes)))
            str_blob.extend(utf8_bytes)
            str_blob.append(0)
        else:
            utf16_bytes = s.encode("utf-16-le")
            str_blob.extend(_encode_utf16_len(len(utf16_bytes) // 2))
            str_blob.extend(utf16_bytes)
            str_blob.extend(b"\x00\x00")

    # 4-byte align string data
    while len(str_blob) % 4 != 0:
        str_blob.append(0)

    new_strings_start = sp_hdr_size + (string_count + style_count) * 4
    new_styles_start = (new_strings_start + len(str_blob)) if style_count > 0 else 0
    new_sp_chunk_size = new_strings_start + len(str_blob) + len(styles_data)

    new_sp_header = struct.pack(
        "<HHIIIIII",
        _RES_STRING_POOL_TYPE,
        sp_hdr_size,
        new_sp_chunk_size,
        string_count,
        style_count,
        flags,
        new_strings_start,
        new_styles_start,
    )
    if sp_hdr_size > 28:
        new_sp_header += axml_bytes[sp_pos + 28 : sp_pos + sp_hdr_size]

    new_offsets_bytes = struct.pack(f"<{string_count}I", *new_str_offsets)
    new_body = new_sp_header + new_offsets_bytes + style_offsets_bytes + bytes(str_blob) + styles_data + rest_of_file
    new_file_size = file_hdr_size + len(new_body)
    new_file_header = struct.pack("<HHI", file_type, file_hdr_size, new_file_size)
    if file_hdr_size > 8:
        new_file_header += axml_bytes[8:file_hdr_size]

    return new_file_header + new_body


# ==============================================================================
# 2. Pure-Python Self-Signed RSA-2048 Debug Keystore (cached PEM)
# ==============================================================================
def ensure_signing_key_and_cert(pem_path):
    """
    Load or generate a self-signed RSA-2048 private key + X.509 certificate (PEM)
    using `cryptography`. Returns (private_key, cert_der_bytes).
    """
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    pem_path = Path(pem_path)
    if pem_path.is_file():
        pem_data = pem_path.read_bytes()
        private_key = serialization.load_pem_private_key(pem_data, password=None)
        cert = x509.load_pem_x509_certificate(pem_data)
        return private_key, cert.public_bytes(serialization.Encoding.DER)

    pem_path.parent.mkdir(parents=True, exist_ok=True)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "PyAudioGaming Shell Signer"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "PyAudioGaming"),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650 * 3))
        .sign(private_key, hashes.SHA256())
    )
    key_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    pem_path.write_bytes(key_pem + cert_pem)
    return private_key, cert.public_bytes(serialization.Encoding.DER)


# ==============================================================================
# 3. Aligned ZIP Writer + APK Signature Scheme v2 Signer
# ==============================================================================
_APK_SIG_BLOCK_MAGIC = b"APK Sig Block 42"
_APK_SIGNATURE_SCHEME_V2_BLOCK_ID = 0x7109871A
_VERITY_PADDING_BLOCK_ID = 0x42726577
_SIG_ALGO_RSA_PKCS1_V1_5_SHA256 = 0x0103
_CHUNK_SIZE = 1024 * 1024  # 1 MiB


def _lp(data):
    """Length-prefixed (uint32 LE) bytes."""
    return struct.pack("<I", len(data)) + data


def write_aligned_zip(entries, out_path):
    """
    Write entries [(arcname, data_bytes, compress_type), ...] to `out_path`
    with 4-byte alignment for ZIP_STORED files and 4096-byte alignment for
    stored .so / resources.arsc files (Android zipalign spec).
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=False) as zf:
        for arcname, data, comp in entries:
            zi = zipfile.ZipInfo(arcname)
            zi.compress_type = comp
            zi.date_time = (2025, 1, 1, 0, 0, 0)
            zi.external_attr = 0o644 << 16
            if comp == zipfile.ZIP_STORED:
                align = 4096 if (arcname.endswith(".so") or arcname == "resources.arsc") else 4
                # Local file header is 30 + len(filename) + len(extra)
                cur_pos = zf.fp.tell()
                name_len = len(arcname.encode("utf-8"))
                data_start = cur_pos + 30 + name_len
                rem = data_start % align
                if rem != 0:
                    pad_len = align - rem
                    # Use a valid ZIP extra field if pad_len >= 4, else raw zeros
                    if pad_len >= 4:
                        zi.extra = struct.pack("<HH", 0xD935, pad_len - 4) + (b"\x00" * (pad_len - 4))
                    else:
                        zi.extra = b"\x00" * pad_len
            zf.writestr(zi, data, compress_type=comp)


def _find_eocd(apk_bytes):
    # Search backwards for EOCD signature PK\x05\x06
    max_search = min(len(apk_bytes), 65535 + 22)
    idx = apk_bytes.rfind(b"PK\x05\x06", len(apk_bytes) - max_search)
    if idx < 0:
        raise ValueError("Invalid ZIP/APK: EOCD record not found")
    return idx


def _compute_v2_content_digest(sec1, sec3, sec4):
    """Compute APK Signature Scheme v2 SHA-256 chunked digest."""
    chunk_digests = []
    for section in (sec1, sec3, sec4):
        mv = memoryview(section)
        n = len(mv)
        if n == 0:
            continue
        pos = 0
        while pos < n:
            chunk = mv[pos : pos + _CHUNK_SIZE]
            h = hashlib.sha256()
            h.update(b"\xa5")
            h.update(struct.pack("<I", len(chunk)))
            h.update(chunk)
            chunk_digests.append(h.digest())
            pos += len(chunk)
    top = hashlib.sha256()
    top.update(b"\x5a")
    top.update(struct.pack("<I", len(chunk_digests)))
    for d in chunk_digests:
        top.update(d)
    return top.digest()


def sign_apk_v2(input_apk_path, output_apk_path, pem_key_path):
    """
    Sign an aligned APK file using APK Signature Scheme v2 (Android 7+ / 11+ / 14+ compatible)
    with RSA-2048 + SHA-256 in pure Python.
    """
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    private_key, cert_der = ensure_signing_key_and_cert(pem_key_path)
    pub_der = private_key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    apk_bytes = Path(input_apk_path).read_bytes()
    eocd_offset = _find_eocd(apk_bytes)
    cd_size, cd_offset = struct.unpack_from("<II", apk_bytes, eocd_offset + 12)

    sec1 = apk_bytes[:cd_offset]
    sec3 = apk_bytes[cd_offset:eocd_offset]
    sec4 = bytearray(apk_bytes[eocd_offset:])
    # Per v2 spec, EOCD's cd_offset in section 4 must point to the APK Signing Block (= original cd_offset)
    struct.pack_into("<I", sec4, 16, cd_offset)

    digest = _compute_v2_content_digest(sec1, sec3, bytes(sec4))

    # Build signed_data
    digest_entry = _lp(struct.pack("<I", _SIG_ALGO_RSA_PKCS1_V1_5_SHA256) + _lp(digest))
    digests_seq = _lp(digest_entry)
    certs_seq = _lp(_lp(cert_der))
    attrs_seq = _lp(b"")
    signed_data = digests_seq + certs_seq + attrs_seq

    signature = private_key.sign(signed_data, padding.PKCS1v15(), hashes.SHA256())
    sig_entry = _lp(struct.pack("<I", _SIG_ALGO_RSA_PKCS1_V1_5_SHA256) + _lp(signature))
    sigs_seq = _lp(sig_entry)

    signer = _lp(signed_data) + sigs_seq + _lp(pub_der)
    v2_value = _lp(_lp(signer))

    # Build APK Signing Block pair
    v2_pair = struct.pack("<QI", 4 + len(v2_value), _APK_SIGNATURE_SCHEME_V2_BLOCK_ID) + v2_value

    # Optional 4096-byte page alignment padding so Central Directory stays aligned
    # Total block size = 8 + len(pairs) + 8 + 16
    raw_block_len = 8 + len(v2_pair) + 24
    pad_needed = (4096 - ((cd_offset + raw_block_len) % 4096)) % 4096
    pairs = v2_pair
    if pad_needed > 0:
        if pad_needed < 12:
            pad_needed += 4096
        pad_payload = b"\x00" * (pad_needed - 12)
        pairs += struct.pack("<QI", 4 + len(pad_payload), _VERITY_PADDING_BLOCK_ID) + pad_payload

    size_of_block = len(pairs) + 8 + 16
    apk_sig_block = (
        struct.pack("<Q", size_of_block)
        + pairs
        + struct.pack("<Q", size_of_block)
        + _APK_SIG_BLOCK_MAGIC
    )

    # Update EOCD's cd_offset to point after the inserted APK Signing Block
    final_eocd = bytearray(apk_bytes[eocd_offset:])
    struct.pack_into("<I", final_eocd, 16, cd_offset + len(apk_sig_block))

    Path(output_apk_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_apk_path, "wb") as f:
        f.write(sec1)
        f.write(apk_sig_block)
        f.write(sec3)
        f.write(final_eocd)

    return Path(output_apk_path)
