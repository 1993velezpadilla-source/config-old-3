#!/usr/bin/env python3
"""Verify weapon viewmodel is actual animated 3D GLB, not fallback primitives.
Pixel-accurate iron sight alignment needs separate rendered-frame audit."""
import json
import struct
import sys
from pathlib import Path
root=Path(sys.argv[1])
weapon_ids=["colt","mp40","m1","thompson","trench","kar98k","gewehr","ppsh","type100","stg","fg42"]
for weapon in weapon_ids:
    path=root/"assets/weapons/aether_waw_real"/weapon/"viewmodel.glb"
    data=path.read_bytes()
    if data[:4]!=b"glTF" or struct.unpack_from("<I",data,4)[0]!=2:
        raise RuntimeError("REAL_GLB_MISSING "+weapon)
    length,kind=struct.unpack_from("<II",data,12)
    if kind!=0x4e4f534a: raise RuntimeError("GLB_JSON_MISSING "+weapon)
    info=json.loads(data[20:20+length].rstrip(b" \x00"))
    if not info.get("meshes") or not info.get("animations") or not info.get("nodes"):
        raise RuntimeError("NO_REAL_ANIMATED_VIEWMODEL "+weapon)
    print("XZOGOT_REAL_WEAPON_3D",weapon,"meshes",len(info["meshes"]),"clips",len(info["animations"]))
print("XZOGOT_CHURCH_11_REAL_GUN_MODELS_GREEN")
print("XZOGOT_CHURCH_IRON_SIGHTS_VISUAL_VALIDATION_PENDING")
