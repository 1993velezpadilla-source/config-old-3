#!/usr/bin/env python3
"""Recover NZ:P's published 46 MP40 pose timing by matching ORIGINAL geometry.

The Blender MP40 source has ~83 timeline frames, but the SHIPPING NZ:P Quake
MDL has 46 published poses. Taking 46 evenly-spaced Blender frames repeats
a magazine pull/insert inside QC's 4..31 reload interval.

Match original *full* skinned mesh geometry against each shipped MDL pose,
using source->Quake calibration already measured from REAL geometry. Find
the closest source timeline for each authoritative pose, then forbid
nonmonotonic motion within each QuakeC animation region.

This script never invents offsets. Emits exact source timeline matches
and residuals so an unreliable match is a RED gate, not a silent fallback.
"""
import bpy,json,math,struct,sys
from pathlib import Path
from mathutils import Vector
from mathutils.kdtree import KDTree
import numpy as np

args=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
if len(args)!=3:raise SystemExit("USAGE <real-original-v_mp40.mdl> <measured-source-to-mdl.json> <report.json>")
mdl_path,fit_path,out=map(lambda p:Path(p).resolve(),args)
d=mdl_path.read_bytes()
if d[:4]!=b"IDPO" or struct.unpack_from("<i",d,4)[0]!=6:raise RuntimeError("MP40_FRAME_AUTHORITY_RED stock MDL not v6")
sc=np.array(struct.unpack_from("<3f",d,8));origin=np.array(struct.unpack_from("<3f",d,20))
sk,w,h,verts,tris,frames=struct.unpack_from("<6i",d,48)
if frames!=46:raise RuntimeError("MP40_FRAME_AUTHORITY_RED unexpected QuakeC pose count")
p=84
for n in range(sk):
    kind,=struct.unpack_from("<i",d,p)
    if kind:raise RuntimeError("MP40_FRAME_AUTHORITY_RED group skin unsupported")
    p+=4+w*h
p+=verts*12+tris*16
published=[]
for frame in range(frames):
    ftype,=struct.unpack_from("<i",d,p);p+=4
    if ftype:raise RuntimeError("MP40_FRAME_AUTHORITY_RED grouped pose")
    name=d[p+8:p+24].split(b"\0")[0].decode("latin1");p+=24
    points=np.array([[float(d[p+4*i+j])*sc[j]+origin[j] for j in range(3)] for i in range(verts)])
    p+=verts*4
    published.append({"name":name,"points":points})
if p!=len(d):raise RuntimeError("MP40_FRAME_AUTHORITY_RED residual MDL data")
cal=json.loads(fit_path.read_text())
import hashlib
if cal["reference_mdl_sha256"]!=hashlib.sha256(d).hexdigest():raise RuntimeError("MP40_FRAME_AUTHORITY_RED stock geometry checksum differs")
tf=cal["best"];S=float(tf["scale"]);R=np.array(tf["rotation"],float);T=np.array(tf["translation"],float)
model=bpy.data.objects.get("nzp_hands.ms3d.mo")
arm=[o for o in bpy.data.objects if o.type=="ARMATURE"]
if model is None or len(arm)!=1:raise RuntimeError("MP40_FRAME_AUTHORITY_RED authored source model/rig missing")
rig=arm[0]
if not rig.animation_data or not rig.animation_data.action:raise RuntimeError("MP40_FRAME_AUTHORITY_RED authored 83-pose clip missing")
lo,hi=rig.animation_data.action.frame_range
if int(lo)!=1 or int(hi)!=83:raise RuntimeError("MP40_FRAME_AUTHORITY_RED original motion differs from expected 1..83")
bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
ref=model.evaluated_get(bpy.context.evaluated_depsgraph_get())
mesh=ref.to_mesh();original=np.array([list(ref.matrix_world@v.co) for v in mesh.vertices]);ref.to_mesh_clear()
original=original@R*S+T
# Stable correspondence of original Blender source vertices to shipped alias
# MDL first pose. This absorbs MDL duplicated UV seam vertices.
kd=KDTree(len(published[0]["points"]))
for i,v in enumerate(published[0]["points"]):kd.insert(Vector(v),i)
kd.balance()
indices=[];initial=[]
for v in original:
    _,i,dist=kd.find(Vector(v));indices.append(i);initial.append(dist)
if np.quantile(initial,.9)>2.5:
    raise RuntimeError("MP40_FRAME_AUTHORITY_RED published model cannot be indexed from source")
sample_indices=np.array(indices,dtype=int)
# Each authored timeline tick mapped using same original armature, SAME world
# transform and SAME original vertex identity over all 83 source poses.
observed=[]
for frame in range(1,84):
    bpy.context.scene.frame_set(frame);bpy.context.view_layer.update()
    ob=model.evaluated_get(bpy.context.evaluated_depsgraph_get());m=ob.to_mesh()
    sample=np.array([list(ob.matrix_world@v.co) for v in m.vertices])@R*S+T
    ob.to_mesh_clear()
    observed.append(sample)
expected=np.stack([p["points"][sample_indices] for p in published])
actual=np.stack(observed)
# Differences normalized to the FULL original weapon geometry span.
diag=float(np.linalg.norm(published[0]["points"].max(axis=0)-published[0]["points"].min(axis=0)))
error=np.sqrt(np.mean(np.sum((expected[:,None,:,:]-actual[None,:,:,:])**2,axis=3),axis=2))
names=[p["name"] for p in published]
regions={"pre_reload":[0,3],"reload":[3,30],"post_reload":[31,45]}
# dynamic-programming monotonic mapping per region with small timeline
# transition penalty, preserving actual original frame semantics rather than
# 83/46 linear timewarp. Order can restart between nonreload sequences.
ranges={}
choices={}
for key,(a,b) in regions.items():
    E=error[a:b+1,:]
    rows,candidates=E.shape
    # Avoid freezing all neighboring compiled poses on one authored sample
    # unless its geometry genuinely stays stationary.
    dp=np.full((rows,candidates),float("inf"))
    prev=np.full((rows,candidates),-1,dtype=int)
    dp[0,:]=E[0,:]
    for i in range(1,rows):
        for f in range(candidates):
            if f<1:continue
            # The strongest constraint: no reverse time within a published
            # reload. Duplicate source frames are permitted only when equally
            # good visually (idle loops are allowed).
            earlier=dp[i-1,:f+1]+.015*np.abs(np.arange(f+1)-f)
            k=int(np.argmin(earlier))
            dp[i,f]=earlier[k]+E[i,f]
            prev[i,f]=k
    end=int(np.argmin(dp[-1]));seq=[end]
    for i in range(rows-1,0,-1):
        end=int(prev[i,end]);seq.append(end)
    seq=list(reversed(seq))
    choices[key]=seq
    ranges[key]={"stock_index_zero_based":[a,b],"source_frame_sequence":[f+1 for f in seq],
                 "residuals":[float(E[i,f]) for i,f in enumerate(seq)],
                 "relative_p90":float(np.quantile([E[i,f] for i,f in enumerate(seq)],.9)/diag)}
mapping=[None]*46
for key,(a,b) in regions.items():
    for i,index in enumerate(choices[key]):
        if mapping[a+i] is not None and mapping[a+i]!=index+1:
            raise RuntimeError("MP40_FRAME_AUTHORITY_RED region overlap disagrees")
        mapping[a+i]=index+1
if None in mapping:raise RuntimeError("MP40_FRAME_AUTHORITY_RED unmapped published poses")
p90=float(np.quantile([error[i,f-1] for i,f in enumerate(mapping)],.9)/diag)
out.parent.mkdir(parents=True,exist_ok=True)
report={"schema":1,"authority":"original NZP shipping 46 pose MDL matched against original Blender authored armature motion",
"published_frame_names":names,"authored_action":rig.animation_data.action.name,"authored_frames":[1,83],
"source_frame_for_published_frame":mapping,"regions":ranges,
"relative_p90_error":p90,"measured_error":True,
"first_pose_authority_position_error":float(np.quantile(initial,.9)),
"linear_even_spaced_83_to_46_rejected":True,
"finished_in_game_reload_verified":False}
out.write_text(json.dumps(report,indent=2))
print("MP40_ORIGINAL_46_POSE_TIME_MATCH_MEASURED",json.dumps({"p90":p90,"reload_sequence":mapping[3:31],"frame0":mapping[0]}))
if p90>.13:
    raise RuntimeError("MP40_FRAME_AUTHORITY_RED source motion mismatch >13%; no linear fallback")
print("MP40_REAL_SOURCE_RELOAD_TIMELINE_GREEN")
