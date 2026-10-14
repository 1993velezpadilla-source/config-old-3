#!/usr/bin/env python3
"""Blender-only truth probe for the original NZ:P MP40 authoring file.
No export and no user-facing changes. Identifies whether hands, gun and magazine
are separate animated surfaces, which dictates if a geometry transplant is safe.
"""
import bpy
import json
from pathlib import Path
objs=[]
for o in bpy.data.objects:
    row={"name":o.name,"type":o.type,"parent":o.parent.name if o.parent else None,
         "dimensions":list(o.dimensions),
         "animation":o.animation_data.action.name if o.animation_data and o.animation_data.action else None}
    if o.type=="MESH":
        row.update({"vertices":len(o.data.vertices),"faces":len(o.data.polygons),
                    "triangles":sum(len(p.vertices)-2 for p in o.data.polygons),
                    "materials":[m.name if m else "UNASSIGNED" for m in o.data.materials],
                    "vertex_groups":[g.name for g in o.vertex_groups],
                    "uv_maps":[u.name for u in o.data.uv_layers],
                    "shape_keys":[k.name for k in o.data.shape_keys.key_blocks] if o.data.shape_keys else []})
    if o.type=="ARMATURE":
        row["bones"]=[b.name for b in o.data.bones]
    objs.append(row)
actions=[{"name":a.name,"frame_range":list(a.frame_range)} for a in bpy.data.actions]
d={"file":bpy.data.filepath,"objects":objs,"actions":actions,
   "original_hands_gun_mesh_separated":any(o["type"]=="MESH" and "hand" in o["name"].lower() for o in objs) and any(o["type"]=="MESH" and ("gun" in o["name"].lower() or "mp40" in o["name"].lower()) for o in objs)}
out=Path("/tmp/mp40-authoring-census.json")
out.write_text(json.dumps(d,indent=2))
print("MP40_NZP_SOURCE_AUTHORING_CENSUS",json.dumps({"objects":len(objs),"actions":len(actions),"meshes":[{"name":x["name"],"vertices":x.get("vertices"),"triangles":x.get("triangles"),"vertex_groups":x.get("vertex_groups")} for x in objs if x["type"]=="MESH"],"hands_gun_separate":d["original_hands_gun_mesh_separated"]}))
