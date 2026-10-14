#!/usr/bin/env python3
"""Measure REAL rest-bone landmarks to avoid inventing MP40 offsets.

Runs inside real Blender hybrid .blend with both original NZP armature and
the original imported Aether GLB armature still present. Fits similarity
transforms against three actual corresponding gun features, reports residual.
Does not declare a valid alignment if landmarks are geometrically divergent.
"""
import bpy
import json
import math
import sys
from pathlib import Path
from mathutils import Vector, Matrix
import numpy as np

args=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
if len(args)!=1: raise SystemExit("USAGE: blender ... -- <output-dir>")
out=Path(args[0]);out.mkdir(parents=True,exist_ok=True)
stock_mesh=bpy.data.objects.get("NZP_Original_Animated_Hands_ONLY")
gun=bpy.data.objects.get("Aether_HD_MP40_On_Vril_Rig")
if stock_mesh is None or gun is None: raise SystemExit("MP40_BONE_MATCH_RED missing hybrid")
rig=next((m.object for m in gun.modifiers if m.type=="ARMATURE"),None)
other=[o for o in bpy.data.objects if o.type=="ARMATURE" and o!=rig]
src=next((o for o in other if {"j_gun","j_clip","j_bolt"}.issubset(set(o.data.bones))),None)
if rig is None or src is None: raise SystemExit("MP40_BONE_MATCH_RED missing original Aether/NZP rigs")
mapping=[("j_gun","Body"),("j_clip","Clip"),("j_bolt","Slide")]
def world_rest(arm,name):
    return arm.matrix_world @ arm.data.bones[name].matrix_local.translation
source=np.array([list(world_rest(src,a)) for a,b in mapping],dtype=float)
target=np.array([list(world_rest(rig,b)) for a,b in mapping],dtype=float)
require=lambda cond,msg: (None if cond else (_ for _ in ()).throw(RuntimeError("MP40_BONE_MATCH_RED "+msg)))
require(np.isfinite(source).all() and np.isfinite(target).all(),"non-finite anchors")
s_center=source.mean(axis=0);t_center=target.mean(axis=0)
s=source-s_center;t=target-t_center
ss=(s*s).sum()
require(ss>1e-12,"Aether skeletal bone heads coincide")
h=s.T@t
u,sv,vt=np.linalg.svd(h)
reflect=np.linalg.det(u@vt)
diag=np.diag([1.0,1.0,1.0 if reflect>=0 else -1.0])
R=u@diag@vt  # row-space orthogonal rotation (src @ R)
scale=(sv*np.diag(diag)).sum()/ss
require(scale>0 and np.isfinite(scale),"invalid landmark scale")
trans=t_center-scale*(s_center@R)
fit=scale*(source@R)+trans
errors=np.linalg.norm(fit-target,axis=1)
armsrc=np.linalg.norm(source[None,:,:]-source[:,None,:],axis=2)
armtgt=np.linalg.norm(target[None,:,:]-target[:,None,:],axis=2)
mean_dst_span=float(max(1.e-12,np.max(armtgt)))
rel=float(np.sqrt(np.mean(errors**2))/mean_dst_span)
# This exactly contrasts *actual* bone heads. It does NOT imply those
# anatomical axes have the same semantic location in the two game assets.
report={"schema":1,"source_armature":src.name,"stock_armature":rig.name,
        "pairs":[{"aether":a,"nzp":b,"aether_rest_world":source[i].tolist(),
                  "nzp_rest_world":target[i].tolist(),"fitted_world":fit[i].tolist(),
                  "absolute_error":float(errors[i])} for i,(a,b) in enumerate(mapping)],
        "similarity_fit":{"scale":float(scale),"rotation_row_space":R.tolist(),
                          "translation":trans.tolist(),"mean_relative_rms":rel,
                          "mean_absolute_rms":float(np.sqrt(np.mean(errors**2))),
                          "normalization_span":mean_dst_span,"reflection_rejected":True},
        "independently_measured":True,"uses_guessed_positions":False,
        "existing_bbox_based_fit_is_not_authoritative":True,
        "closeness_quality_gate_10_percent":rel<=.10,
        "human_visual_confirmation":False}
(out/"mp40-original-bone-landmarks.json").write_text(json.dumps(report,indent=2))
for entry in report["pairs"]: print("MP40_EXACT_BONE_ANCHOR",json.dumps(entry))
print("MP40_EXACT_SKELETAL_ALIGNMENT_FIT",json.dumps(report["similarity_fit"]))
print("MP40_BONE_MATCH_MEASURED_GREEN source and target real armature rest bones")
if rel>.10:
    print("MP40_BONE_MATCH_GEOMETRY_WARNING mapped rest-bone landmarks have %.2f%% residual"% (rel*100))
else:
    print("MP40_BONE_MATCH_REST_LANDMARKS_TOLERANCE_GREEN %.2f%% residual"%(rel*100))
