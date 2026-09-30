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

H_MATERIAL = iw_hash_string("CIwMaterial")

def resource_payload_offset(data: bytes) -> int:
    pos = data.find(struct.pack("<I", H_RESOURCES), 6)
    if pos < 0:
        raise ValueError("ResGroupResources block not found")
    return pos + 8

def patch(data: bytes) -> tuple[bytes, list[dict]]:
    out = bytearray(data)
    q = resource_payload_offset(data)
    num_types = struct.unpack_from("<I", data, q)[0]
    q += 4
    changed=[]

    for _ in range(num_types):
        class_hash, count = struct.unpack_from("<II", data, q)
        names_omitted = data[q+8]
        has_size = data[q+9]
        q += 10
        if not has_size:
            raise ValueError(f"class 0x{class_hash:08x} lacks size prefix")

        for index in range(count):
            start=q
            size=struct.unpack_from("<I", data, q)[0]
            if size < 8 or start + size > len(data):
                raise ValueError(
                    f"invalid resource size class=0x{class_hash:08x} "
                    f"index={index} size={size} start=0x{start:x}"
                )
            q += 4
            name_hash=None
            if not names_omitted:
                name_hash=struct.unpack_from("<I", data, q)[0]
                q += 4
            in_group_hash=struct.unpack_from("<I", data, q)[0]
            q += 4
            body_start=q
            body_end=start+size

            if class_hash == H_MATERIAL:
                body=data[body_start:body_end]
                if len(body) >= 25 and body[0] == 0:
                    # same(1), flags(4), two u16(4), then four RGBA channels.
                    color_start=body_start + 9
                    before=bytes(out[color_start:color_start+16])
                    pattern=bytes([
                        255,0,255,255,   # ambient
                        64,0,64,255,     # emissive
                        255,255,255,255, # specular
                        255,0,255,255,   # colour4
                    ])
                    out[color_start:color_start+16]=pattern
                    after=bytes(out[color_start:color_start+16])
                    if before != after:
                        changed.append({
                            "index": index,
                            "nameHash": f"0x{(name_hash if name_hash is not None else in_group_hash):08x}",
                            "bodyOffset": body_start,
                            "bodyBytes": len(body),
                            "colorOffset": color_start,
                            "beforeHex": before.hex(),
                            "afterHex": after.hex(),
                        })
            q=body_end

    return bytes(out),changed

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("input",type=Path)
    ap.add_argument("output",type=Path)
    ap.add_argument("--report",type=Path,required=True)
    args=ap.parse_args()

    original=args.input.read_bytes()
    patched,changed=patch(original)
    if len(original)!=len(patched):
        raise SystemExit("SIZE_CHANGED")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes(patched)

    report={
        "schemaVersion":1,
        "inputBytes":len(original),
        "outputBytes":len(patched),
        "inputSha256":hashlib.sha256(original).hexdigest(),
        "outputSha256":hashlib.sha256(patched).hexdigest(),
        "materialsChanged":len(changed),
        "materials":changed,
    }
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2),encoding="utf-8")

    print("THEATRE_BYTES",len(original))
    print("MATERIALS_CHANGED",len(changed))
    for m in changed[:20]:
        print("MATERIAL",m["index"],m["nameHash"],"colorOffset",hex(m["colorOffset"]))
    if not changed:
        raise SystemExit("NO_MATERIALS_CHANGED")
    if original==patched:
        raise SystemExit("PATCH_DID_NOT_CHANGE_BYTES")
    print("XZIEL_BOZ_THEATRE_MATERIAL_PATCH_OK")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
