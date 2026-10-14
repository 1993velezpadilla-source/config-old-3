#!/usr/bin/env python3
"""Read REAL NZ:P MP40 MDL and Project Aether MP40 GLB byte structures.

This tool is intentionally READ ONLY. It never extracts/converts copyrighted
geometry into an Android APK; it generates a provenance/compatibility report.
No GREEN can be claimed here for skinned animation or visual phone quality.
"""
import argparse
import hashlib
import json
import math
import re
import struct
from pathlib import Path


def require(test, why):
    if not test:
        raise ValueError("MP40_BRIDGE_RED: " + why)


def hash_file(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def mdl_audit(path):
    blob = path.read_bytes()
    require(len(blob) >= 84, "MDL truncated header")
    ident, version = struct.unpack_from("<4sI", blob, 0)
    require(ident == b"IDPO" and version == 6, "stock asset is not Quake MDL v6")
    skins, width, height, vertices, tris, frames, synctype, flags = struct.unpack_from("<8i", blob, 48)
    require(0 < skins < 32, "invalid skin count")
    require(0 < width <= 4096 and 0 < height <= 4096, "invalid embedded atlas")
    require(0 < vertices <= 16384 and 0 < tris <= 16384, "invalid stock geometry")
    require(0 < frames <= 2048, "invalid frame count")
    pos = 84
    skin_types = []
    for _ in range(skins):
        require(pos + 4 <= len(blob), "skin header truncated")
        kind, = struct.unpack_from("<i", blob, pos)
        pos += 4
        require(kind in (0, 1), "unsupported stock skin type")
        skin_types.append(kind)
        if kind == 0:
            pos += width * height
        else:
            require(pos + 4 <= len(blob), "skin-group truncated")
            count, = struct.unpack_from("<i", blob, pos)
            require(0 < count < 1024, "invalid skin group length")
            pos += 4 + count * 4 + count * width * height
    st_offset = pos
    pos += vertices * 12
    triangles_offset = pos
    pos += tris * 16
    require(pos < len(blob), "invalid MDL geometry block")
    faces = []
    for j in range(tris):
        facefront, a, b, c = struct.unpack_from("<4i", blob, triangles_offset + 16*j)
        require(all(0 <= v < vertices for v in (a,b,c)), "out of range MDL face")
        faces.append((a,b,c))
    triangle_indices = len(set(v for face in faces for v in face))
    parsed_names, frame_types = [], []
    for frame_id in range(frames):
        require(pos + 4 <= len(blob), "truncated frame discriminator")
        kind, = struct.unpack_from("<i", blob, pos)
        pos += 4
        frame_types.append(kind)
        if kind == 0:
            require(pos + 24 + vertices*4 <= len(blob), "MDL pose truncated")
            name = blob[pos+8:pos+24].split(b"\0",1)[0].decode("latin1")
            parsed_names.append(name)
            pos += 24 + vertices * 4
        elif kind == 1:
            require(pos + 12 <= len(blob), "MDL group header truncated")
            count, = struct.unpack_from("<i", blob, pos)
            require(0 < count < 1024, "invalid frame group")
            pos += 12 + 4*count + count * (24+4*vertices)
            parsed_names.append("group("+str(count)+")")
        else:
            raise ValueError("MP40_BRIDGE_RED: unknown MDL pose type "+str(kind))
    require(pos == len(blob), "MDL trailing bytes or misparsed frames %d vs %d" % (pos, len(blob)))
    scale = list(struct.unpack_from("<3f",blob,8))
    origin = list(struct.unpack_from("<3f",blob,20))
    return {
        "format":"Quake alias MDL v6",
        "bytes":len(blob),"sha256":hash_file(path),
        "vertices":vertices,"triangles":tris,"frames":frames,
        "unique_indexed_vertices":triangle_indices,
        "embedded_skins":skins,"skin_atlas_size":[width,height],
        "skin_types":skin_types,"scale":scale,"translate":origin,
        "frame_names":parsed_names,"frame_types":frame_types,
        "all_faces_index_valid":True,
    }


def glb_audit(path):
    blob = path.read_bytes()
    require(len(blob)>=20, "GLB too small")
    magic,version,total = struct.unpack_from("<4sII",blob,0)
    require(magic==b"glTF" and version==2 and total==len(blob), "not complete glTF2 GLB")
    n,kind=struct.unpack_from("<II",blob,12)
    require(kind==0x4e4f534a and 20+n<=len(blob), "GLB JSON chunk corrupt")
    doc=json.loads(blob[20:20+n].decode("utf-8").strip("\0 \t\r\n"))
    require(doc.get("meshes"), "Aether viewmodel has no mesh")
    mesh_counts=[]
    for mesh in doc["meshes"]:
        for primitive in mesh["primitives"]:
            require(primitive.get("mode",4)==4, "non-triangle mesh primitive")
            ai=primitive.get("indices")
            require(ai is not None,"nonindexed input not supported")
            accessor=doc["accessors"][ai]
            require(accessor["count"]%3==0,"index count not tri-aligned")
            attrs=primitive["attributes"]
            mesh_counts.append({
                "vertices":doc["accessors"][attrs["POSITION"]]["count"],
                "triangles":accessor["count"]//3,
                "skinned":all(x in attrs for x in ["JOINTS_0","WEIGHTS_0"]),
                "uv":("TEXCOORD_0" in attrs),
                "normal":("NORMAL" in attrs),
                "source_material":primitive.get("material"),
                "uv_sets":sorted(k for k in attrs if k.startswith("TEXCOORD_")),
                "position_bounds":[doc["accessors"][attrs["POSITION"]].get("min"),
                                   doc["accessors"][attrs["POSITION"]].get("max")],
            })
    skel=doc.get("skins",[])
    action=[a.get("name","") for a in doc.get("animations",[])]
    nodes=doc.get("nodes",[])
    joints=[nodes[index].get("name","") for skin in skel for index in skin["joints"]]
    names_lower=" ".join(action).lower()
    role_patterns={
        "idle":["idle"], "fire":["_fire","lastshot"],
        "reload":["_reload"],"reload_empty":["reload_empty"],
        "equip":["equip","raise"],"unequip":["unequip"],
    }
    roles={key:any(w in names_lower for w in opts) for key,opts in role_patterns.items()}
    require(all(roles.values()), "Aether source animations missing mandatory action")
    return {
        "format":"glTF2/GLB skinned triangle mesh",
        "bytes":len(blob),"sha256":hash_file(path),
        "meshes":len(doc["meshes"]),"primitives":mesh_counts,
        "total_vertices":sum(x["vertices"] for x in mesh_counts),
        "total_triangles":sum(x["triangles"] for x in mesh_counts),
        "skins":len(skel),"joint_names":joints,
        "clips":len(action),"animation_names":action,
        "animation_roles_present":roles,
        "materials": [m.get("name","") for m in doc.get("materials",[])],
        "embedded_images":len(doc.get("images",[])),
        "textures":len(doc.get("textures",[])),
        "external_pbr_atlas_required":len(doc.get("images",[]))==0,
        "node_count":len(nodes),
        "extensions_required":doc.get("extensionsRequired",[]),
        "actual_animation_motion_in_vril":False,
    }


def png_info(path):
    blob=path.read_bytes()
    require(blob[:8]==b"\x89PNG\r\n\x1a\n","invalid PNG " + str(path))
    width,height=struct.unpack_from(">II",blob,16)
    return {"name":path.name,"bytes":len(blob),"sha256":hash_file(path),"width":width,"height":height}


def quakec_audit(path):
    text=path.read_text()
    block=re.search(r"case W_MP40:\s*case W_AFTERBURNER:\s*switch\s*\(frametype\)\s*\{(.+?)\}\s*break;",text,re.S)
    require(block is not None,"QuakeC MP40 frame table not located in pinned source")
    rows=dict((k,int(v)) for k,v in re.findall(r"case\s+(\w+):\s*return\s+(\d+);",block.group(1)))
    required=["FIRE_START","FIRE_END","RELOAD_START","RELOAD_END","TAKE_OUT_START","TAKE_OUT_END","SPRINT_IN_START","SPRINT_IN_END","SPRINT_OUT_START","SPRINT_OUT_END","RELOAD_CANCEL"]
    require(all(x in rows for x in required),"QuakeC MP40 expected frame mapping missing")
    return rows


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--stock",type=Path,required=True)
    ap.add_argument("--aether",type=Path,required=True)
    ap.add_argument("--texture",type=Path,action="append",default=[])
    ap.add_argument("--quakec",type=Path,required=True)
    ap.add_argument("--report",type=Path,required=True)
    args=ap.parse_args()
    stock=mdl_audit(args.stock)
    aether=glb_audit(args.aether)
    textures=[png_info(t) for t in args.texture]
    frames=quakec_audit(args.quakec)
    report={
        "experiment":"VRIL_MP40_AETHER_FIRST_BINARY_AUDIT",
        "stock_vril":stock,"aether":aether,
        "aether_external_pbr_textures":textures,
        "quakec_frame_contract":frames,
        "baseline_unpatched_vril":{"MAXALIASVERTS":2048,"MAXALIASTRIS":2048},
        "experimental_vril_16k":{"MAXALIASVERTS":16384,"MAXALIASTRIS":16384},
        "triangles_fit_unpatched":aether["total_triangles"]<=2048,
        "triangles_fit_16k_patch":aether["total_triangles"]<=16384,
        "vertices_fit_16k_patch":aether["total_vertices"]<=16384,
        "frame_contract_gte_mdl_frame_count":max(frames.values())>=stock["frames"],
        "uv_layout_directly_interchangeable":False,
        "automatic_animation_retarget_proven":False,
        "unchanged_original_deadcell_apk":True,
        "production_or_commercial_distribution_approved":False,
    }
    require(aether["total_triangles"]>stock["triangles"],"source is not higher polygon")
    require(report["triangles_fit_16k_patch"] and report["vertices_fit_16k_patch"],
            "high-detail MP40 exceeds 16k patch")
    require(stock["frames"]>=40 and aether["clips"]>=10,"unexpected animation timeline")
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+"\n")
    print("MP40_REAL_BINARY_GATES_GREEN stock_tris=%d aether_tris=%d stock_frames=%d aether_clips=%d"%
          (stock["triangles"],aether["total_triangles"],stock["frames"],aether["clips"]))
    print("MP40_16K_CAPACITY_ONLY_GREEN; NO ANIMATION OR RENDER CLAIM")
    print("MP40_BONE_FRAME_BRIDGE_PENDING conversion of 18 skeletal clips to exact QuakeC frame map")
    print("MP40_PBR_UV_BRIDGE_PENDING source atlases are NOT embedded in Aether GLB")
    print("MP40_LICENSE_GATE_REQUIRED assets from Project Aether cannot be sold without clearance")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
