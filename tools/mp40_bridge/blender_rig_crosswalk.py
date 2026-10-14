#!/usr/bin/env python3
"""Blender headless: prove which stock MP40 rig controls can drive Aether joints.

Pure non-destructive audit; never reports finished model conversion.
"""
import bpy
import json
import sys
from collections import Counter
from pathlib import Path
args=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
if len(args)!=1: raise SystemExit("expected Aether GLB path as one argument")
original=list(bpy.data.objects)
arms=[o for o in original if o.type=="ARMATURE"]
meshes=[o for o in original if o.type=="MESH"]
if not arms or not meshes: raise SystemExit("VRIL_SOURCE_RIG_RED no stock armature or skinned mesh")
source_arm=max(arms,key=lambda x:len(x.data.bones))
stock_bones={x.name for x in source_arm.data.bones}
stock_actions=[{"name":a.name,"lo":float(a.frame_range[0]),"hi":float(a.frame_range[1])} for a in bpy.data.actions]
groups=Counter()
faces=Counter()
for o in meshes:
    labels={g.index:g.name for g in o.vertex_groups}
    for v in o.data.vertices:
        for g in v.groups:
            if g.weight>0.01:
                groups[labels[g.group]]+=1
    for face in o.data.polygons:
        voting=Counter()
        for vid in face.vertices:
            for vw in o.data.vertices[vid].groups:
                if vw.weight>0.01:
                    voting[labels[vw.group]]+=vw.weight
        if voting:
            faces[voting.most_common(1)[0][0]]+=1
before=set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=str(Path(args[0]).resolve()))
imported=list(set(bpy.data.objects)-before)
aether_arms=[x for x in imported if x.type=="ARMATURE"]
if not aether_arms: raise SystemExit("AETHER_RIG_RED no imported armature")
aether_bones={b.name for arm in aether_arms for b in arm.data.bones}
mapping={"Body":"j_gun","Slide":"j_bolt","Clip":"j_clip"}
truth={src:{"source_bone":src in stock_bones,"source_weights":groups[src],
            "source_dominant_faces":faces[src],"aether_joint":dst in aether_bones}
       for src,dst in mapping.items()}
print("MP40_SOURCE_BONES",sorted(stock_bones))
print("MP40_SOURCE_ACTIONS",json.dumps(stock_actions))
print("MP40_IMPORTED_AETHER_BONES",sorted(aether_bones))
print("MP40_SOURCE_FACE_CLASSIFICATION",json.dumps(dict(faces),sort_keys=True))
report={"source_armature":source_arm.name,"source_mesh_names":[o.name for o in meshes],
        "source_actions":stock_actions,"stock_bones":sorted(stock_bones),
        "aether_bones":sorted(aether_bones),
        "source_weighted_vertex_occurrences":dict(groups),
        "source_dominant_faces":dict(faces),
        "control_rig_correspondence":truth,
        "safe_to_retarget_without_bake":False,
        "model_transplant_complete":False}
Path("/tmp/mp40-skeleton-crosswalk.json").write_text(json.dumps(report,indent=2))
if not all(x["source_bone"] and x["aether_joint"] and x["source_weights"]>0 for x in truth.values()):
    raise SystemExit("MP40_BONE_CROSSWALK_RED no authentic 3-part skeleton match")
print("MP40_RIG_SEMANTIC_CROSSWALK_GREEN: stock Body/Slide/Clip mapped to Aether j_gun/j_bolt/j_clip")
print("MP40_GUN_HAND_GEOMETRY_SEPARATION_PENDING: do not ship until region geometry preserved")
