#!/usr/bin/env python3
"""Check which ORIGINAL IW3 XModels have usable glTF skeleton/vertex weights.

Audit only: does not serialize proprietary meshes or fake animated gameplay.
Used to decide next native GLSkin adapter from ACTUAL OAT exporter format.
"""
from __future__ import annotations
import argparse,json
from collections import Counter
from pathlib import Path
from iw3_glb_to_iwvm import load_glb,read_accessor


def describe(path:Path):
    doc,blob=load_glb(path)
    nodes=doc.get("nodes",[])
    skins=doc.get("skins",[])
    joints=set()
    total_joints=0
    invbind=0
    for skin in skins:
        ids=skin.get("joints",[])
        if not isinstance(ids,list):
            raise ValueError("Original glTF skin has invalid joint list")
        if any(not isinstance(i,int) or not 0<=i<len(nodes) for i in ids):
            raise ValueError("Invalid CoD4 glTF original bone index")
        total_joints+=len(ids)
        joints.update(ids)
        accessor=skin.get("inverseBindMatrices")
        if accessor is not None:
            a=doc["accessors"][accessor]
            if a["type"]!="MAT4" or a["componentType"]!=5126:
                raise ValueError("glTF inverse bind matrices incompatible")
            invbind+=a["count"]
    triangles=0
    skinned_primitives=0
    weighted_vertices=0
    incomplete_primitives=0
    for mesh in doc.get("meshes",[]):
        for primitive in mesh.get("primitives",[]):
            if primitive.get("mode",4)!=4:continue
            attributes=primitive.get("attributes",{})
            position=attributes.get("POSITION")
            if position is None:raise ValueError("No POSITION")
            count=doc["accessors"][position]["count"]
            has_joints="JOINTS_0" in attributes
            has_weights="WEIGHTS_0" in attributes
            if has_joints!=has_weights:
                incomplete_primitives+=1
            if has_joints and has_weights:
                j=doc["accessors"][attributes["JOINTS_0"]]
                w=doc["accessors"][attributes["WEIGHTS_0"]]
                if j["type"]!="VEC4" or w["type"]!="VEC4" or j["count"]!=count or w["count"]!=count:
                    raise ValueError("Original skeleton joint/weight layout mismatch")
                skinned_primitives+=1
                weighted_vertices+=count
            triangles+=1
    return {"models":len(doc.get("meshes",[])),"nodes":len(nodes),
            "skin_count":len(skins),"skinned_joints_total":total_joints,
            "inverse_bind_matrices":invbind,
            "unique_joint_nodes":len(joints),
            "triangle_primitives":triangles,
            "weighted_primitives":skinned_primitives,
            "weighted_vertices":weighted_vertices,
            "incomplete_skin_attributes":incomplete_primitives,
            "readable_skin_data":bool(skins and weighted_vertices and invbind)}


def census(root:Path,max_files:int=120):
    candidates=sorted(p for p in root.rglob("*.glb")
                      if p.name.startswith("viewmodel_") and "_lod0" in p.name)
    totals=Counter()
    sample=[]
    for p in candidates[:max_files]:
        d=describe(p)
        totals.update({k:v for k,v in d.items() if isinstance(v,int) and not isinstance(v,bool)})
        totals["usable_skin_models"]+=d["readable_skin_data"]
        if len(sample)<10:
            # Only counts, never filenames, mesh bytes or bone names.
            sample.append(d)
    return {"all_viewmodel_lod0_count":len(candidates),
            "examined":min(len(candidates),max_files),
            "aggregate":dict(totals),"anonymous_model_counts":sample,
            "original_bone_names_uploaded":False,
            "animated_IW3_GLES_renderer_implemented":False}


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("original_oat_path",type=Path)
    p.add_argument("--max-models",type=int,default=100)
    args=p.parse_args()
    if args.max_models<1 or args.max_models>1000:raise ValueError("max-models outside 1..1000")
    print(json.dumps(census(args.original_oat_path,args.max_models),indent=2))
