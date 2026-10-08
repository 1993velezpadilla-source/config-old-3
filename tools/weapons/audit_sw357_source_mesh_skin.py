#!/usr/bin/env python3
"""Examine original Aether SW357 glTF mesh/skin, without modifying any mesh.

A six-round speedloader floats camera-right in BOTH Godot source idle and
raw bind pose. Identify joint-weighted geometry to isolate real reload props.
"""
from __future__ import annotations
import collections
import json
import math
from pathlib import Path
import struct

GLB = Path("xogot/assets/weapons/aether_waw_real/357/viewmodel.glb")
COMPONENTS = {5120:("b",1),5121:("B",1),5122:("h",2),5123:("H",2),
              5125:("I",4),5126:("f",4)}
DIMENSIONS = {"SCALAR":1,"VEC2":2,"VEC3":3,"VEC4":4,"MAT4":16}


def read_glb(path: Path):
    raw = path.read_bytes()
    magic, version, size = struct.unpack_from("<4sII", raw)
    assert magic == b"glTF" and version == 2 and size == len(raw), path
    cursor = 12
    document, binary = None, None
    while cursor < len(raw):
        block_size, block_type = struct.unpack_from("<II", raw, cursor)
        cursor += 8
        block = raw[cursor:cursor+block_size]
        cursor += block_size
        if block_type == 0x4E4F534A:
            document = json.loads(block.rstrip(b"\x00").decode("utf-8"))
        if block_type == 0x004E4942:
            binary = block
    assert document and binary is not None
    return document, binary


def accessor_values(data, blob, idx):
    a = data["accessors"][idx]
    assert "sparse" not in a
    bv = data["bufferViews"][a["bufferView"]]
    code, size = COMPONENTS[a["componentType"]]
    count = DIMENSIONS[a["type"]]
    fmt = "<"+code*count
    start = bv.get("byteOffset",0) + a.get("byteOffset",0)
    stride = bv.get("byteStride",size*count)
    return [struct.unpack_from(fmt,blob,start+i*stride) for i in range(a["count"])]


def main():
    data, blob = read_glb(GLB)
    mesh_nodes = [(i,n) for i,n in enumerate(data["nodes"]) if "mesh" in n]
    print("XZOGOT_SW357_SOURCE_GLB nodes=",len(data["nodes"]),
          " meshes=",len(data["meshes"])," skins=",len(data.get("skins",[])))
    print("XZOGOT_SW357_ANIMATION_NAMES", [x.get("name") for x in data.get("animations",[])][:40])
    for node_index,node in mesh_nodes:
        name = node.get("name",str(node_index))
        mesh = data["meshes"][node["mesh"]]
        skin = data["skins"][node["skin"]] if "skin" in node else {}
        bones = [data["nodes"][idx].get("name",str(idx)) for idx in skin.get("joints",[])]
        print("XZOGOT_SW357_MESH",name,"primitives=",len(mesh["primitives"]),
              "skinned_joints=",len(bones))
        for prim_id,prim in enumerate(mesh["primitives"]):
            attrs = prim["attributes"]
            pos=accessor_values(data,blob,attrs["POSITION"])
            joint0=accessor_values(data,blob,attrs["JOINTS_0"]) if "JOINTS_0" in attrs else []
            weight0=accessor_values(data,blob,attrs["WEIGHTS_0"]) if "WEIGHTS_0" in attrs else []
            mat = data.get("materials",[])
            matname = mat[prim["material"]].get("name","") if "material" in prim and prim["material"] < len(mat) else ""
            box=[tuple(round(float(v),4) for v in axis) for axis in zip(
                [min(p[i] for p in pos) for i in range(3)],
                [max(p[i] for p in pos) for i in range(3)])]
            print("XZOGOT_SW357_PRIMITIVE",prim_id,"material=",matname,
                  "vertices=",len(pos),"bounds_xyz=",box,
                  "has_skin=",bool(joint0 and weight0))
            perbone: dict[str,list[tuple[float,float,float]]] = collections.defaultdict(list)
            if joint0 and weight0:
                for v,j,w in zip(pos,joint0,weight0):
                    if sum(w) <= 0: continue
                    peak=max(range(4),key=lambda k:w[k])
                    if w[peak] < 0.25: continue
                    bone=bones[j[peak]] if j[peak] < len(bones) else str(j[peak])
                    perbone[bone].append(v)
            for bone, positions in sorted(perbone.items(),key=lambda x:-len(x[1])):
                mn=tuple(round(min(v[a] for v in positions),4) for a in range(3))
                mx=tuple(round(max(v[a] for v in positions),4) for a in range(3))
                print("XZOGOT_SW357_SKIN_CLUSTER",bone,
                      "verts=",len(positions),"min_xyz=",mn,"max_xyz=",mx)
    print("XZOGOT_SW357_NATIVE_MESH_AUDIT_COMPLETE original_glb_untouched=true")


if __name__=="__main__":
    main()
