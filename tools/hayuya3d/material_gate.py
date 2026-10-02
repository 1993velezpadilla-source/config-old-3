#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import struct
from dataclasses import asdict,dataclass
from pathlib import Path

JSON_CHUNK=0x4E4F534A

@dataclass
class Report:
    schema:int
    path:str
    images:int
    textures:int
    materials:int
    triangle_primitives:int
    texcoord_primitives:int
    color_primitives:int
    base_color_texture_materials:int
    passed:bool
    reasons:list[str]

def _doc(path:Path):
    b=path.read_bytes()
    if len(b)<20 or b[:4]!=b"glTF":
        raise ValueError("not_a_glb")
    _,total=struct.unpack_from("<II",b,4)
    off=12
    while off+8<=total:
        n,k=struct.unpack_from("<II",b,off); off+=8
        chunk=b[off:off+n]; off+=n
        if k==JSON_CHUNK:
            return json.loads(chunk.rstrip(b"\x00 \t\r\n").decode("utf-8"))
    raise ValueError("missing_json_chunk")

def inspect(path:Path,require_texture:bool)->Report:
    reasons=[]
    d=_doc(path)
    images=len(d.get("images",[]) or [])
    textures=len(d.get("textures",[]) or [])
    materials=d.get("materials",[]) or []
    tri=uv=col=0
    for mesh in d.get("meshes",[]) or []:
        for prim in mesh.get("primitives",[]) or []:
            if int(prim.get("mode",4))!=4:
                continue
            tri+=1
            attrs=prim.get("attributes",{}) or {}
            if "TEXCOORD_0" in attrs:
                uv+=1
            if "COLOR_0" in attrs:
                col+=1
    base_tex=0
    for mat in materials:
        pbr=mat.get("pbrMetallicRoughness",{}) or {}
        if isinstance(pbr.get("baseColorTexture"),dict):
            base_tex+=1
    if require_texture:
        if images<1:
            reasons.append("no_embedded_texture_images")
        if textures<1:
            reasons.append("no_gltf_textures")
        if base_tex<1:
            reasons.append("no_base_color_texture")
        if tri and uv<tri:
            reasons.append(f"missing_uvs:{uv}/{tri}")
    return Report(1,str(path),images,textures,len(materials),tri,uv,col,base_tex,not reasons,reasons)

def main()->int:
    p=argparse.ArgumentParser(description="Reject clay/vertex-color-only GLBs before HAYUYA visual approval.")
    p.add_argument("glb",type=Path)
    p.add_argument("--require-texture",action="store_true")
    p.add_argument("--json",type=Path)
    a=p.parse_args()
    try:
        r=inspect(a.glb,a.require_texture)
        payload=json.dumps(asdict(r),indent=2)
        code=0 if r.passed else 4
    except Exception as exc:
        payload=json.dumps({"schema":1,"path":str(a.glb),"passed":False,"reasons":[f"{type(exc).__name__}:{exc}"]},indent=2)
        code=4
    print(payload)
    if a.json:
        a.json.parent.mkdir(parents=True,exist_ok=True)
        a.json.write_text(payload+"\n",encoding="utf-8")
    return code

if __name__=="__main__":
    raise SystemExit(main())
