#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

H_RESOURCES = 0xDC3C2177

def iw_hash_string(value: str) -> int:
    h = 0x1505
    for byte in value.encode("ascii"):
        if 0x41 <= byte <= 0x5A:
            byte += 0x20
        h = (byte + h * 0x21) & 0xFFFFFFFF
    return h

H_TEXTURE = iw_hash_string("CIwTexture")

def locate_resource_payload(data: bytes) -> int:
    needle = struct.pack("<I", H_RESOURCES)
    pos = data.find(needle, 6)
    if pos < 0:
        raise ValueError("ResGroupResources block not found")
    if pos + 12 > len(data):
        raise ValueError("truncated ResGroupResources header")
    return pos + 8

def locate_texels(body: bytes) -> tuple[int,int,int,int,int]:
    n = len(body)
    for off in range(4, 40):
        if off + 9 > n:
            break
        w = struct.unpack_from("<H", body, off + 3)[0]
        h = struct.unpack_from("<H", body, off + 5)[0]
        pitch = struct.unpack_from("<H", body, off + 7)[0]
        if not (0 < w <= 8192 and 0 < h <= 8192 and pitch > 0):
            continue
        if pitch % w:
            continue
        bpp = pitch // w
        if bpp not in (1,2,3,4):
            continue
        texsize = pitch * h
        texoff = n - texsize
        if 12 <= texoff <= 40 and texsize > 0:
            return texoff, w, h, pitch, bpp
    raise ValueError("texture texel layout not found")

def patch_texels(buf: bytearray, start: int, w: int, h: int, pitch: int, bpp: int) -> None:
    for y in range(h):
        for x in range(w):
            checker = ((x // 16) ^ (y // 16)) & 1
            p = start + y * pitch + x * bpp
            if bpp == 4:
                rgba = (255, 0, 255, 255) if checker == 0 else (0, 255, 64, 255)
                buf[p:p+4] = bytes(rgba)
            elif bpp == 3:
                rgb = (255, 0, 255) if checker == 0 else (0, 255, 64)
                buf[p:p+3] = bytes(rgb)
            elif bpp == 2:
                # RGB565: magenta / green.
                value = 0xF81F if checker == 0 else 0x07E0
                struct.pack_into("<H", buf, p, value)
            else:
                buf[p] = 255 if checker == 0 else 32

def parse_and_patch(data: bytes) -> tuple[bytes, list[dict]]:
    out = bytearray(data)
    q = locate_resource_payload(data)
    if q + 4 > len(data):
        raise ValueError("missing resource type count")
    num_types = struct.unpack_from("<I", data, q)[0]
    q += 4
    report = []

    for _ in range(num_types):
        if q + 10 > len(data):
            raise ValueError("resource class header out of range")
        class_hash, count = struct.unpack_from("<II", data, q)
        names_omitted = data[q+8]
        has_size = data[q+9]
        q += 10
        if not has_size:
            raise ValueError(f"class 0x{class_hash:08x} lacks size prefixes")

        for index in range(count):
            start = q
            if q + 4 > len(data):
                raise ValueError("resource size out of range")
            size = struct.unpack_from("<I", data, q)[0]
            if size < 8 or start + size > len(data):
                raise ValueError(
                    f"resource size invalid: class=0x{class_hash:08x} index={index} "
                    f"size={size} start=0x{start:x}"
                )
            q += 4
            name_hash = None
            if not names_omitted:
                name_hash = struct.unpack_from("<I", data, q)[0]
                q += 4
            in_group_hash = struct.unpack_from("<I", data, q)[0]
            q += 4
            body_start = q
            body_end = start + size

            if class_hash == H_TEXTURE:
                body = data[body_start:body_end]
                try:
                    texoff, w, h, pitch, bpp = locate_texels(body)
                except ValueError:
                    q = body_end
                    continue
                absolute = body_start + texoff
                before = hashlib.sha256(data[absolute:absolute + pitch*h]).hexdigest()
                patch_texels(out, absolute, w, h, pitch, bpp)
                after = hashlib.sha256(out[absolute:absolute + pitch*h]).hexdigest()
                report.append({
                    "index": index,
                    "nameHash": f"0x{(name_hash if name_hash is not None else in_group_hash):08x}",
                    "bodyOffset": body_start,
                    "bodyBytes": len(body),
                    "texelOffset": absolute,
                    "width": w,
                    "height": h,
                    "pitch": pitch,
                    "bpp": bpp,
                    "beforeSha256": before,
                    "afterSha256": after,
                })
            q = body_end

    return bytes(out), report

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()

    original = args.input.read_bytes()
    patched, textures = parse_and_patch(original)
    if len(patched) != len(original):
        raise SystemExit("SIZE_CHANGED")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patched)
    report = {
        "schemaVersion": 1,
        "inputBytes": len(original),
        "outputBytes": len(patched),
        "inputSha256": hashlib.sha256(original).hexdigest(),
        "outputSha256": hashlib.sha256(patched).hexdigest(),
        "texturesPatched": len(textures),
        "textures": textures,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("THEATRE_BYTES", len(original))
    print("TEXTURES_PATCHED", len(textures))
    for t in textures:
        print(
            "TEXTURE", t["index"], t["nameHash"],
            f'{t["width"]}x{t["height"]}', "bpp", t["bpp"],
            "texelOffset", hex(t["texelOffset"]),
        )
    if not textures:
        raise SystemExit("NO_RAW_TEXTURES_PATCHED")
    if original == patched:
        raise SystemExit("PATCH_DID_NOT_CHANGE_BYTES")
    print("XZIEL_BOZ_THEATRE_TEXTURE_PATCH_OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
