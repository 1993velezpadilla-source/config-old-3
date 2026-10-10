#!/usr/bin/env python3
"""Expected triangle counts for *all reachable* raw GLB Mesh nodes in Godot.

This counts real indexed (or unindexed) triangle primitives, once per actual
actor chunk node, to compare against Godot 4.6 runtime MeshInstance3D surfaces.
"""
import argparse
import json
from pathlib import Path
import struct
import sys


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--glb",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    with a.glb.open("rb") as file:
        head=file.read(20)
        if len(head)!=20:
            raise ValueError("GLB truncated header")
        magic,ver,size,njson,typ=struct.unpack("<IIIII",head)
        if magic!=0x46546C67 or ver!=2 or typ!=0x4E4F534A or size!=a.glb.stat().st_size:
            raise ValueError("not valid glTF v2 GLB")
        doc=json.loads(file.read(njson))
    if (doc.get("extras",{})
           .get("xziel_native_glb_geometry_lossless_reinjected",{})
           .get("original_static_glb_passthrough") is not True):
        raise ValueError("this must be the new source-native lossless GLB")
    mesh_faces={}
    for i,mesh in enumerate(doc["meshes"]):
        total=0
        for prim in mesh["primitives"]:
            if prim.get("mode",4)!=4:
                raise ValueError("unsupported nontriangle GLB primitive")
            accessor=prim.get("indices",prim["attributes"]["POSITION"])
            count=doc["accessors"][accessor]["count"]
            if count%3:
                raise ValueError("triangle primitive length invalid")
            total+=count//3
        mesh_faces[i]=total
    visited=set()
    reachable_meshes=[]
    source_actors=set()
    def visit(i):
        if i<0 or i>=len(doc["nodes"]) or i in visited:
            raise ValueError("invalid GLB scene node graph")
        visited.add(i)
        node=doc["nodes"][i]
        if node.get("name","").startswith("ue_instance_") and "_native_exact_" not in node.get("name",""):
            source_actors.add(node["name"])
        if "mesh" in node:
            reachable_meshes.append(int(node["mesh"]))
        for child in node.get("children",[]):
            visit(child)
    for idx in doc["scenes"][doc.get("scene",0)]["nodes"]:
        visit(idx)
    if len(source_actors)!=10793 or len(reachable_meshes)<10793:
        raise ValueError(
            f"source actor or actual mesh node loss: actors={len(source_actors)} "
            f"mesh_nodes={len(reachable_meshes)}"
        )
    triangles=sum(mesh_faces[idx] for idx in reachable_meshes)
    payload={"authority":"archived Pavlov UE4.21 raw original indexed GLB",
             "original_bo3_t7":False,
             "expected_actor_nodes":len(source_actors),
             "expected_reachable_mesh_instances":len(reachable_meshes),
             "expected_total_reachable_surface_triangles":triangles,
             "mesh_instances_with_zero_triangles":sum(mesh_faces[idx]==0 for idx in reachable_meshes),
             "godot_import_was_not_checked_by_this_script":True}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(payload,indent=2)+"\n")
    print("XZOGOT_NACHT_RAW_LOSSLESS_TOTAL_TRIANGLE_BASELINE_GREEN",
          "actors",len(source_actors),
          "meshes",len(reachable_meshes),"triangles",triangles)


if __name__=="__main__":
    sys.exit(main())
