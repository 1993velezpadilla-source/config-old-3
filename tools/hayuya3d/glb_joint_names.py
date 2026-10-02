#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,struct
from pathlib import Path

def load_glb(path:Path):
    b=path.read_bytes()
    if b[:4]!=b"glTF": raise SystemExit("not glb")
    total=struct.unpack_from("<I",b,8)[0]
    off=12
    while off+8<=total:
        n,t=struct.unpack_from("<II",b,off);off+=8
        chunk=b[off:off+n];off+=n
        if t==0x4E4F534A:
            return json.loads(chunk.rstrip(b"\x00 \t\r\n"))
    raise SystemExit("no json")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("glb",type=Path)
    a=p.parse_args()
    d=load_glb(a.glb)
    nodes=d.get("nodes",[])
    joints=[]
    for si,skin in enumerate(d.get("skins",[])):
        names=[]
        for idx in skin.get("joints",[]):
            if isinstance(idx,int) and idx<len(nodes):
                names.append(nodes[idx].get("name",f"node_{idx}"))
        joints.append({"skin":si,"joints":names})
    print(json.dumps({"path":str(a.glb),"skins":joints},indent=2))
if __name__=="__main__": main()
