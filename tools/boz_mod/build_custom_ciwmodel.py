#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

def iw_hash_string(value: str) -> int:
    h = 0x1505
    for byte in value.encode("ascii"):
        if 0x41 <= byte <= 0x5A:
            byte += 0x20
        h = (byte + h * 0x21) & 0xFFFFFFFF
    return h

def build_model(vertices, triangles, uvs=None) -> bytes:
    verts_data = b"".join(struct.pack("<hhh", *v) for v in vertices)
    verts = (
        struct.pack("<I", iw_hash_string("CIwModelBlockVerts"))
        + b"\x00" * 6
        + struct.pack("<H", len(vertices))
        + b"\x00" * 4
        + verts_data
    )

    uv_block = b""
    if uvs is not None:
        if len(uvs) != len(vertices):
            raise ValueError("UV count must equal vertex count")
        uv_data = b"".join(struct.pack("<hh", *uv) for uv in uvs)
        uv_block = (
            struct.pack("<I", iw_hash_string("CIwModelBlockGLUVs"))
            + b"\x00" * 6
            + struct.pack("<H", len(uvs))
            + b"\x00" * 4
            + uv_data
        )

    indices = [i for tri in triangles for i in tri]
    tri = bytearray(struct.pack("<I", iw_hash_string("CIwModelBlockGLTriList")))
    tri += b"\x00" * (0x12 - len(tri))
    tri += b"".join(struct.pack("<H", i) for i in indices)
    tri += b"\x00" * (0x1A - len(tri))
    tri += struct.pack("<H", len(indices))
    return bytes(verts + uv_block + tri)

def build_group(name: str, model_body: bytes, model_hash: int) -> bytes:
    # BOZ small CIwResGroups use tag 0x3d plus a versioned 5-byte header.
    # Current real groups observed by CI begin 3d0001020000.
    out = bytearray(bytes.fromhex("3d0001020000"))

    params = name.encode("latin1") + b"\0"
    out += struct.pack("<II", 0x8081E087, len(params) + 4)
    out += params

    payload = bytearray(struct.pack("<I", 1))
    payload += struct.pack("<II", iw_hash_string("CIwModel"), 1)
    payload += bytes((1, 1))
    payload += struct.pack("<II", 8 + len(model_body), model_hash)
    payload += model_body

    out += struct.pack("<II", 0xDC3C2177, len(payload) + 4)
    out += payload
    out += struct.pack("<I", 0)
    return bytes(out)

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--report",type=Path,required=True)
    args=ap.parse_args()

    # Original XChurch test geometry: a room-sized open rectangular shell
    # expressed as independent triangle vertices to keep the first writer simple.
    s=240
    h=180
    z0=0
    z1=h

    verts=[
        # floor
        (-s,-s,z0),( s,-s,z0),( s, s,z0),
        (-s,-s,z0),( s, s,z0),(-s, s,z0),
        # back wall
        (-s, s,z0),( s, s,z0),( s, s,z1),
        (-s, s,z0),( s, s,z1),(-s, s,z1),
        # left wall
        (-s,-s,z0),(-s, s,z0),(-s, s,z1),
        (-s,-s,z0),(-s, s,z1),(-s,-s,z1),
        # right wall
        ( s, s,z0),( s,-s,z0),( s,-s,z1),
        ( s, s,z0),( s,-s,z1),( s, s,z1),
        # simple altar block front
        (-60,120,0),(60,120,0),(60,155,0),
        (-60,120,0),(60,155,0),(-60,155,0),
        (-60,120,0),(-60,155,0),(-60,155,65),
        (-60,120,0),(-60,155,65),(-60,120,65),
        (60,155,0),(60,120,0),(60,120,65),
        (60,155,0),(60,120,65),(60,155,65),
        (-60,120,65),(60,120,65),(60,155,65),
        (-60,120,65),(60,155,65),(-60,155,65),
    ]
    tris=[(i,i+1,i+2) for i in range(0,len(verts),3)]
    uvs=[(0,0),(4096,0),(4096,4096)]*(len(verts)//3)

    body=build_model(verts,tris,uvs)
    name="xchurch_shell"
    group=build_group("xchurch",body,iw_hash_string(name))

    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_bytes(group)

    report={
        "schemaVersion":1,
        "group":"xchurch",
        "model":name,
        "vertices":len(verts),
        "triangles":len(tris),
        "modelBodyBytes":len(body),
        "groupBytes":len(group),
        "headHex":group[:16].hex(),
        "modelHash":f"0x{iw_hash_string(name):08x}",
        "classHash":f"0x{iw_hash_string('CIwModel'):08x}",
    }
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2),encoding="utf-8")

    print("XZIEL_BOZ_CUSTOM_MODEL_WRITTEN")
    print("GROUP_BYTES",len(group))
    print("MODEL_VERTICES",len(verts))
    print("MODEL_TRIANGLES",len(tris))
    print("CIW_MODEL_HASH",f"0x{iw_hash_string('CIwModel'):08x}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
