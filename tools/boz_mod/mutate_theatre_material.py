#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

BLOCK_OBJECTS = 0xDC3C2177

def iw_hash_string(value: str) -> int:
    h = 0x1505
    for byte in value.encode("latin1"):
        if 0x41 <= byte <= 0x5A:
            byte += 0x20
        h = (byte + h * 0x21) & 0xFFFFFFFF
    return h

H_MATERIAL = iw_hash_string("CIwMaterial")

def find_resource_block(data: bytes) -> int:
    needle = struct.pack("<I", BLOCK_OBJECTS)
    pos = data.find(needle, 6)
    if pos < 0:
        raise ValueError("ResourceObjects block not found")
    if pos + 12 > len(data):
        raise ValueError("ResourceObjects block truncated")
    return pos + 8

def mutate_material(data: bytes) -> tuple[bytes, dict]:
    out = bytearray(data)
    q = find_resource_block(data)

    num_types = struct.unpack_from("<I", data, q)[0]
    q += 4
    if not (1 <= num_types <= 1024):
        raise ValueError(f"implausible resource type count {num_types}")

    for type_index in range(num_types):
        if q + 10 > len(data):
            raise ValueError(f"class header {type_index} out of range")
        class_hash, count = struct.unpack_from("<II", data, q)
        names_omitted = data[q + 8]
        has_size = data[q + 9]
        q += 10

        if has_size != 1:
            raise ValueError(f"class 0x{class_hash:08x} lacks per-resource size")

        for resource_index in range(count):
            start = q
            if q + 4 > len(data):
                raise ValueError("resource size out of range")
            size = struct.unpack_from("<I", data, q)[0]
            if size < 8 or start + size > len(data):
                raise ValueError(
                    f"invalid resource size {size} class=0x{class_hash:08x} "
                    f"index={resource_index} start=0x{start:x}"
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
            body = data[body_start:body_end]

            if class_hash == H_MATERIAL and len(body) >= 25 and body[0] == 0:
                original = {
                    "ambient": list(body[9:13]),
                    "emissive": list(body[13:17]),
                    "specular": list(body[17:21]),
                    "colour4": list(body[21:25]),
                }
                marker = bytes((255, 0, 255, 255))
                out[body_start + 9: body_start + 13] = marker
                out[body_start + 13: body_start + 17] = marker
                out[body_start + 17: body_start + 21] = marker
                out[body_start + 21: body_start + 25] = marker

                report = {
                    "resourceType": "CIwMaterial",
                    "typeIndex": type_index,
                    "resourceIndex": resource_index,
                    "nameHash": None if name_hash is None else f"0x{name_hash:08x}",
                    "inGroupHash": f"0x{in_group_hash:08x}",
                    "resourceStart": start,
                    "bodyStart": body_start,
                    "bodyBytes": len(body),
                    "originalColours": original,
                    "newColours": {
                        "ambient": list(marker),
                        "emissive": list(marker),
                        "specular": list(marker),
                        "colour4": list(marker),
                    },
                    "lengthPreserved": True,
                    "inputBytes": len(data),
                    "outputBytes": len(out),
                }
                return bytes(out), report

            q = body_end

    raise ValueError("no mutable non-default CIwMaterial found")

def verify_mutation(data: bytes, report: dict) -> None:
    body_start = int(report["bodyStart"])
    marker = bytes((255, 0, 255, 255))
    for off in (9, 13, 17, 21):
        got = data[body_start + off: body_start + off + 4]
        if got != marker:
            raise ValueError(f"marker mismatch at body+{off}: {got.hex()}")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--report", required=True, type=Path)
    args = ap.parse_args()

    src = args.input.read_bytes()
    mutated, report = mutate_material(src)
    verify_mutation(mutated, report)

    if len(src) != len(mutated):
        raise SystemExit("size changed unexpectedly")
    if src == mutated:
        raise SystemExit("mutation produced no byte changes")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(mutated)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("XZIEL_BOZ_THEATRE_MATERIAL_MUTATION_OK")
    print("RESOURCE_INDEX", report["resourceIndex"])
    print("IN_GROUP_HASH", report["inGroupHash"])
    print("BODY_START", hex(report["bodyStart"]))
    print("INPUT_BYTES", report["inputBytes"])
    print("OUTPUT_BYTES", report["outputBytes"])
    print("NEW_RGBA", "255,0,255,255")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
