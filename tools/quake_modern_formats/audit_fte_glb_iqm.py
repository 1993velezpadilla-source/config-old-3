#!/usr/bin/env python3
"""Compare real GLB source against FTE's IQM and MDL converters without shipping art.

All quantities from binary headers. Geometry, animation and UV metrics are
reported; a "successful converter invocation" is NOT Android gameplay proof.
"""
import json,struct,sys,hashlib
from pathlib import Path

if len(sys.argv)!=5:
    raise SystemExit("usage: input.glb candidate.iqm candidate.mdl converter.log output.json")
source,iqm,mdl,logs,out=map(Path,sys.argv[1:])
record={"schema":1,"conversion_test":"FTEQW native IQM tool / actual Aether MP40",
        "model_commercial_license_verified":False,
        "android_vril_supports_iqm":False,
        "format_conversion_does_not_validate_binding_or_gameplay":True}
data=source.read_bytes()
assert len(data)>20 and data[:4]==b"glTF" and struct.unpack_from("<I",data,4)[0]==2
jlen,jtype=struct.unpack_from("<II",data,12)
assert jtype==0x4e4f534a
gltf=json.loads(data[20:20+jlen].decode("utf-8"))
glb_tris=0
for mesh in gltf.get("meshes",[]):
    for p in mesh.get("primitives",[]):
        if p.get("mode",4)!=4:
            continue
        if "indices" in p:
            ct=gltf["accessors"][p["indices"]]["count"]
        else:
            ct=gltf["accessors"][p["attributes"]["POSITION"]]["count"]
        glb_tris+=ct//3
record["glb"]={"sha256":hashlib.sha256(data).hexdigest(),
               "bytes":len(data),"triangles":glb_tris,
               "mesh_count":len(gltf.get("meshes",[])),
               "skins":len(gltf.get("skins",[])),
               "animation_clips":len(gltf.get("animations",[])),
               "materials":len(gltf.get("materials",[])),
               "images":len(gltf.get("images",[]))}
record["converter_logs"]=[line[:500] for line in logs.read_text(errors="replace").splitlines()[-50:]]
if iqm.is_file() and iqm.stat().st_size>=124:
    raw=iqm.read_bytes()
    if raw[:16]==b"INTERQUAKEMODEL\x00":
        hdr=struct.unpack_from("<27I",raw,16)
        record["iqm"]={"valid_magic":True,"version":hdr[0],"bytes":len(raw),
             "vertices":hdr[8],"triangles":hdr[10],
             "joints":hdr[13],"poses":hdr[15],"animation_clips":hdr[17],
             "animation_frames":hdr[19],"preserves_triangle_count":hdr[10]==glb_tris}
    else:record["iqm"]={"valid_magic":False,"bytes":len(raw)}
else:record["iqm"]={"present":False}
if mdl.is_file() and mdl.stat().st_size>=84:
    raw=mdl.read_bytes()
    if raw[:4]==b"IDPO" and struct.unpack_from("<I",raw,4)[0]==6:
        nskin,sw,sh,nvert,ntri,nframe=struct.unpack_from("<6i",raw,48)
        record["mdl"]={"valid_magic":True,"version":6,"bytes":len(raw),
                       "skins":nskin,"skin_size":[sw,sh],"vertices":nvert,
                       "triangles":ntri,"frames":nframe,
                       "preserves_triangle_count":ntri==glb_tris}
    else:record["mdl"]={"valid_magic":False,"bytes":len(raw)}
else:record["mdl"]={"present":False}
record["glb_to_iqm_geometry_gate"]=bool(record["iqm"].get("preserves_triangle_count"))
record["glb_to_mdl_geometry_gate"]=bool(record["mdl"].get("preserves_triangle_count"))
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(record,indent=2))
print("XZIEL_FTE_GLB_CONVERTER_REAL_BINARY_AUDIT",json.dumps({k:record[k] for k in ("glb","iqm","mdl","glb_to_iqm_geometry_gate","glb_to_mdl_geometry_gate")}))
if not record["glb_to_iqm_geometry_gate"]:
    raise SystemExit("XZIEL_FTE_GLB_TO_IQM_GATE_RED: converter does not preserve source triangles")
print("XZIEL_FTE_GLB_TO_IQM_GEOMETRY_GREEN_ANDROID_UNPROVEN")
