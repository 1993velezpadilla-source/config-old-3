#!/usr/bin/env python3
"""Preserve UE4 source actor affine transforms after Meridian's lossy TRS export."""
import argparse
import json
from pathlib import Path
import struct

C = [[1.,0,0,0],[0,0,1.,0],[0,-1.,0,0],[0,0,0,1.]]
CT = [list(row) for row in zip(*C)]


def dot(a,b):
    return [[sum(a[i][k]*b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--scene",type=Path,required=True)
    ap.add_argument("--glb",type=Path,required=True)
    args=ap.parse_args()
    source=json.loads(args.scene.read_text())
    if source.get("format")!="xziel_visual_scene_v1":
        raise ValueError("only verified UE4.21 XZIEL source accepted")
    rows={r["instanceId"]:r["matrixRowMajor"] for r in source["instances"]}
    if len(rows)!=len(source["instances"]):
        raise ValueError("duplicate native actors")
    payload=args.glb.read_bytes()
    if payload[:4]!=b"glTF" or struct.unpack_from("<I",payload,4)[0]!=2:
        raise ValueError("unsupported GLB")
    length,kind=struct.unpack_from("<II",payload,12)
    if kind!=0x4E4F534A:
        raise ValueError("missing GLB JSON")
    doc=json.loads(payload[20:20+length])
    restored=set()
    for node in doc["nodes"]:
        name=node.get("name")
        if name not in rows:
            continue
        raw=rows[name]
        if len(raw)!=16:
            raise ValueError("source matrix missing")
        m=[list(map(float,raw[4*i:4*i+4])) for i in range(4)]
        if m[3]!=[0.,0.,0.,1.]:
            raise ValueError("nonaffine source matrix")
        target=dot(dot(C,m),CT)
        for prop in ("rotation","translation","scale"):
            node.pop(prop,None)
        node["matrix"]=[target[i][j] for j in range(4) for i in range(4)]
        restored.add(name)
    if restored!=set(rows):
        raise ValueError("Meridian actor loss or mismatched source IDs")
    doc.setdefault("extras",{})["xziel_source_affine_restored"]=len(restored)
    data=json.dumps(doc,separators=(",",":"),allow_nan=False).encode()
    data+=b" "*((-len(data))%4)
    tail=payload[20+length:]
    total=20+len(data)+len(tail)
    args.glb.write_bytes(struct.pack("<III",0x46546C67,2,total)+
                         struct.pack("<II",len(data),0x4E4F534A)+data+tail)
    print("XZOGOT_NACHT_SOURCE_ORIGINAL_AFFINE_GREEN",len(restored))


if __name__=="__main__":
    main()
