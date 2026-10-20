#!/usr/bin/env python3
"""Read actual GLB material tables without Blender or decompressing geometry."""
from pathlib import Path
import struct, json
p=Path("xogot/assets/environment/church")
for src in [p/"bench.glb",p/"altar.glb"]:
    with src.open("rb") as f:
        header=f.read(20)
        magic, version, length, json_size, kind=struct.unpack("<4sIIII",header)
        assert magic==b"glTF" and version==2 and kind==0x4e4f534a
        data=json.loads(f.read(json_size))
        f.seek(20+json_size)
        bin_size,bin_kind=struct.unpack("<II",f.read(8))
    print("GLB_DIAG",src,"materials",len(data.get("materials",[])),
          "images",len(data.get("images",[])), "textures",len(data.get("textures",[])),
          "meshes",len(data.get("meshes",[])),"bufbytes",bin_size,
          "extensions",data.get("extensionsUsed",[]))
    for i,m in enumerate(data.get("materials",[])):
        print("GLB_MAT",i,json.dumps({
            "name":m.get("name"),"pbr":m.get("pbrMetallicRoughness"),
            "alphaMode":m.get("alphaMode"),"doubleSided":m.get("doubleSided"),
            "ext":m.get("extensions")
        })[:1800])
    for i,img in enumerate(data.get("images",[])):
        print("GLB_IMAGE",i,img)
    for i,m in enumerate(data.get("meshes",[])):
        print("GLB_MESH",i,"primitives",len(m.get("primitives",[])),
            [{"material":v.get("material"),"attributes":list(v.get("attributes",{})),"mode":v.get("mode")} for v in m.get("primitives",[])][:4])
