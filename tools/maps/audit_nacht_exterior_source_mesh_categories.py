#!/usr/bin/env python3
"""Inspect 493 native Pavlov UE4.21 source mesh labels to plan SAFE exterior LOD.

No authored mesh, tree, rocks or gameplay entities are removed. Report geometry
positions and native source asset paths. Source != original BO3 T7.
"""
import argparse
import json
import collections
import math
from pathlib import Path

def xyz(row):
    mat=row["matrixRowMajor"]
    if len(mat)!=16:raise ValueError("bad source 4x4")
    return (-float(mat[7]), float(mat[11]), -float(mat[3]))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--scene",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    src=json.loads(args.scene.read_text())
    meshes=src["meshes"];actors=src["instances"]
    if src.get("format")!="xziel_visual_scene_v1" or len(meshes)!=493 or len(actors)!=10793:
        raise ValueError("unverified original source geometry")
    count=collections.Counter(int(r["meshIndex"]) for r in actors)
    coords=[xyz(r) for r in actors]
    meshrows=[]
    for m in meshes:
        idx=int(m["index"])
        text=" ".join(str(v) for k,v in m.items() if k not in ("matrixRowMajor","bytes"))
        meshrows.append({"index":idx,"actors":count[idx],"sourceDescription":text[:650],
                         "keys":sorted(m)})
    bounds={"min":[min(p[i] for p in coords) for i in range(3)],
            "max":[max(p[i] for p in coords) for i in range(3)]}
    tokens=("tree","foliage","grass","bush","leaf","leaves","rock","shrub","branch",
            "hill","cliff","mountain","pine","spruce","oak","weed","plant",
            "house","wall","floor","roof","concrete","rubble","ruin","road",
            "building","window","door","debris","barricade","interactive",
            "skysphere","sky","terrain")
    found={}
    for term in tokens:
        matches=[r for r in meshrows if term in r["sourceDescription"].lower()]
        found[term]={"sourceMeshTypes":len(matches),"placedActors":sum(x["actors"] for x in matches),
                     "samples":matches[:12]}
    out={"authority":"archived Pavlov UE4.21 Nacht reconstruction, not BO3 T7",
         "mesh_count":len(meshes),"actor_count":len(actors),
         "meshes_top_keys":dict(collections.Counter(k for m in meshes for k in m.keys())),
         "actors_top_keys":dict(collections.Counter(k for a in actors for k in a.keys())),
         "actor_position_godot_aabb_m":bounds,
         "mesh_by_frequency":sorted(meshrows,key=lambda x:x["actors"],reverse=True),
         "asset_categories":found,
         "no_geometric_changes":True,
         "center_of_playable_structure_not_independently_proven":True}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out,indent=2)+"\n")
    print("XZOGOT_NACHT_EXTERIOR_SOURCE_MESH_LABELS_AND_WORLD_AABB_GREEN",
          "meshes",len(meshes),"actors",len(actors),"bounds",bounds)
    for k,v in found.items():
        if v["sourceMeshTypes"]:
            print("XZOGOT_NACHT_EXTERIOR_SOURCE_CATEGORY",k,
                  "types",v["sourceMeshTypes"],"placed",v["placedActors"],
                  "sample",[(e["index"],e["sourceDescription"][:95]) for e in v["samples"][:3]])
    print("XZOGOT_NACHT_MOST_FREQUENT_NATIVE_SOURCE_MESH_TYPES",
          [(r["index"],r["actors"],r["sourceDescription"][:115]) for r in out["mesh_by_frequency"][:25]])
if __name__=="__main__":
    main()
