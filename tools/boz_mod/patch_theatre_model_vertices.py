#!/usr/bin/env python3
from __future__ import annotations

import argparse
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

H_MODEL = iw_hash_string("CIwModel")
H_VERTS = iw_hash_string("CIwModelBlockVerts")

def clamp16(v: int) -> int:
    return max(-32768, min(32767, v))

def resource_payload_offset(data: bytes) -> int:
    pos = data.find(struct.pack("<I", H_RESOURCES), 6)
    if pos < 0:
        raise ValueError("ResGroupResources block not found")
    return pos + 8

def patch_first_model(data: bytes) -> tuple[bytes, dict]:
    out = bytearray(data)
    q = resource_payload_offset(data)
    num_types = struct.unpack_from("<I", data, q)[0]
    q += 4

    for _ in range(num_types):
        class_hash, count = struct.unpack_from("<II", data, q)
        names_omitted = data[q + 8]
        has_size = data[q + 9]
        q += 10
        if not has_size:
            raise ValueError(f"class 0x{class_hash:08x} lacks size prefix")

        for index in range(count):
            start = q
            size = struct.unpack_from("<I", data, q)[0]
            if size < 8 or start + size > len(data):
                raise ValueError(
                    f"invalid resource size class=0x{class_hash:08x} "
                    f"index={index} size={size} start=0x{start:x}"
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

            if class_hash == H_MODEL:
                body = data[body_start:body_end]
                rel = body.find(struct.pack("<I", H_VERTS))
                if rel >= 0 and rel + 0x10 <= len(body):
                    count_v = struct.unpack_from("<H", body, rel + 0x0A)[0]
                    vd = rel + 0x10
                    if 3 <= count_v <= 8192 and vd + count_v * 6 <= len(body):
                        before = []
                        after = []
                        for i in range(count_v):
                            x, y, z = struct.unpack_from("<hhh", body, vd + i * 6)
                            if i < 8:
                                before.append([x, y, z])

                            # Deliberately obvious but topology-safe deformation:
                            # widen X, stretch height, push upward.
                            nx = clamp16(int(x * 2))
                            ny = clamp16(int(y * 2))
                            nz = clamp16(int(z * 2 + 192))
                            struct.pack_into(
                                "<hhh",
                                out,
                                body_start + vd + i * 6,
                                nx, ny, nz,
                            )
                            if i < 8:
                                after.append([nx, ny, nz])

                        all_after = [
                            struct.unpack_from("<hhh", out, body_start + vd + i * 6)
                            for i in range(count_v)
                        ]
                        xs = [v[0] for v in all_after]
                        ys = [v[1] for v in all_after]
                        zs = [v[2] for v in all_after]
                        report = {
                            "modelIndex": index,
                            "nameHash": f"0x{(name_hash if name_hash is not None else in_group_hash):08x}",
                            "bodyStart": body_start,
                            "bodyBytes": len(body),
                            "vertsBlockOffset": body_start + rel,
                            "vertexCount": count_v,
                            "firstVerticesBefore": before,
                            "firstVerticesAfter": after,
                            "afterBounds": {
                                "min": [min(xs), min(ys), min(zs)],
                                "max": [max(xs), max(ys), max(zs)],
                            },
                            "inputBytes": len(data),
                            "outputBytes": len(out),
                            "topologyPreserved": True,
                            "uvsPreserved": True,
                            "indicesPreserved": True,
                        }
                        return bytes(out), report

            q = body_end

    raise ValueError("no suitable CIwModel with vertex block found")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()

    original = args.input.read_bytes()
    patched, report = patch_first_model(original)

    if len(original) != len(patched):
        raise SystemExit("SIZE_CHANGED")
    if original == patched:
        raise SystemExit("GEOMETRY_UNCHANGED")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patched)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("XZIEL_BOZ_THEATRE_MODEL_VERTEX_PATCH_OK")
    print("MODEL_INDEX", report["modelIndex"])
    print("MODEL_HASH", report["nameHash"])
    print("VERTEX_COUNT", report["vertexCount"])
    print("AFTER_BOUNDS", report["afterBounds"])
    print("GROUP_BYTES", len(original))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
