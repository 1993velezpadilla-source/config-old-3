#!/usr/bin/env python3
"""EXPERIMENTAL first MP40 bone->Quake MDL geometry/skin/frame compiler.

Takes the REAL hybrid Blender project (stock Vril hands & animations, actual
Aether gun). Builds a 46-pose Quake MDL v6 plus 2048x1024 external skin
placeholder requirement. The 83-to-46 action sampling is provisional,
so this stage NEVER authorizes shipment. QuakeC frame/camera/ADS alignment and
licensing are further mandatory gates. Binary is local to CI, NOT published.
"""
import bpy
import json
import math
import struct
import sys
from pathlib import Path
from mathutils import Vector

args=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
if len(args)!=1: raise SystemExit("Expected output directory")
dest=Path(args[0]).resolve()
dest.mkdir(parents=True,exist_ok=True)
stock=bpy.data.objects.get("NZP_Original_Animated_Hands_ONLY")
gun=bpy.data.objects.get("Aether_HD_MP40_On_Vril_Rig")
if stock is None or gun is None:
    raise SystemExit("MP40_ALIAS_EXPORT_RED hybrid parts missing")
rig=next((m.object for m in gun.modifiers if m.type=="ARMATURE"),None)
if rig is None or not rig.animation_data or not rig.animation_data.action:
    raise SystemExit("MP40_ALIAS_EXPORT_RED stock animation armature missing")
base_action=rig.animation_data.action
lo,hi=base_action.frame_range
if hi-lo < 40: raise SystemExit("MP40_ALIAS_EXPORT_RED no usable stock animation")
# Original source was authored at 1-83, published NZ:P MDL contains exactly
# 46 poses. We DO NOT know authoritative timewarp -- all poses are provisional.
MODEL_POSES=46
WIDTH,HEIGHT=2048,1024
objects=[(stock,0),(gun,1)]
corner_vertex_map=[]
stverts=[]
triangles=[]
face_ranges={}
for obj,side in objects:
    mesh=obj.data
    uv=mesh.uv_layers.active
    if uv is None: raise SystemExit("MP40_ALIAS_EXPORT_RED missing UV map on "+obj.name)
    face_start=len(triangles)
    for poly in mesh.polygons:
        if len(poly.loop_indices)!=3:
            raise SystemExit("MP40_ALIAS_EXPORT_RED triangulate first "+obj.name)
        corners=[]
        for loopid in poly.loop_indices:
            loop=mesh.loops[loopid]
            value=uv.data[loopid].uv
            u=float(value.x); v=float(value.y)
            if not math.isfinite(u) or not math.isfinite(v):
                raise SystemExit("MP40_ALIAS_EXPORT_RED nonfinite UV")
            # Quake MDL stores whole-pixel atlas coordinates per vertex.
            u=min(1,max(0,u))
            v=min(1,max(0,v))
            s=min(WIDTH-1,max(0,round((side+u)*WIDTH/2)-1))
            t=min(HEIGHT-1,max(0,round((1-v)*HEIGHT)-1))
            vid=len(corner_vertex_map)
            corner_vertex_map.append((obj.name,int(loop.vertex_index)))
            stverts.append((0,s,t))
            corners.append(vid)
        triangles.append((1, *corners))
    face_ranges[obj.name]=len(triangles)-face_start

verts=len(stverts)
tris=len(triangles)
if not (4000<=verts<=16384 and 3200<=tris<=16384):
    raise SystemExit("MP40_ALIAS_EXPORT_RED exceeds Vril alias limits "+str((verts,tris)))
if face_ranges.get(stock.name)!=364 or face_ranges.get(gun.name)!=3229:
    raise SystemExit("MP40_ALIAS_EXPORT_RED hybrid triangle identity drift "+str(face_ranges))
positions=[]
frame_times=[]
scene=bpy.context.scene
for k in range(MODEL_POSES):
    t=int(round(float(lo)+float(k)/(MODEL_POSES-1)*(float(hi)-float(lo))))
    scene.frame_set(t)
    bpy.context.view_layer.update()
    deps=bpy.context.evaluated_depsgraph_get()
    cache={}
    for obj,side in objects:
        e=obj.evaluated_get(deps)
        m=e.to_mesh()
        cache[obj.name]=(e.matrix_world.copy(),[v.co.copy() for v in m.vertices])
        e.to_mesh_clear()
    frame=[]
    for name,source_vid in corner_vertex_map:
        mat,coords=cache[name]
        v=mat@coords[source_vid]
        if not all(math.isfinite(q) for q in v):
            raise SystemExit("MP40_ALIAS_EXPORT_RED invalid skinned vertex frame "+str(k))
        frame.append((float(v.x),float(v.y),float(v.z)))
    positions.append(frame)
    frame_times.append(t)
# Quantize ALL real skinned frames using one stable bounding range.
vmin=[min(p[j] for frame in positions for p in frame) for j in range(3)]
vmax=[max(p[j] for frame in positions for p in frame) for j in range(3)]
scale=[max(0.000001,(vmax[i]-vmin[i])/255) for i in range(3)]
radius=math.sqrt(sum(max(abs(a),abs(b))**2 for a,b in zip(vmin,vmax)))
# All vertex normals currently index=0, so geometry/animation correctness
# can be examined independently of visual shading; this is NOT release art.
out=bytearray()
out+=struct.pack("<4sI3f3ff3f8if",b"IDPO",6,
                 *scale,*vmin,radius,0.,0.,0.,
                 2,WIDTH,HEIGHT,verts,tris,MODEL_POSES,0,0,float(max(vmax[i]-vmin[i] for i in range(3))))
for i in range(2):
    out+=struct.pack("<i",0)
    out+=b"\x00"*(WIDTH*HEIGHT)  # external TGA REQUIRED to see textures
for row in stverts: out+=struct.pack("<iii",*row)
for row in triangles: out+=struct.pack("<iiii",*row)
motions=[]
first=positions[0]
for k,frame in enumerate(positions):
    packed=[]
    for p in frame:
        packed.append(tuple(min(255,max(0,int(round((p[j]-vmin[j])/scale[j])))) for j in range(3)))
    lo_q=[min(p[j] for p in packed) for j in range(3)]
    hi_q=[max(p[j] for p in packed) for j in range(3)]
    name=("f%02d"%k).encode().ljust(16,b"\x00")
    out+=struct.pack("<i4B4B16s",0,*lo_q,0,*hi_q,0,name)
    for p in packed: out+=struct.pack("<4B",*p,0)
    delta=sum(math.dist(p,q) for p,q in zip(frame,first))/len(frame)
    motions.append(delta)
assert len(out)==84+2*(4+WIDTH*HEIGHT)+verts*12+tris*16+MODEL_POSES*(4+8+16+verts*4)
path=dest/"v_mp40_aether_hybrid_EXPERIMENT_ONLY.mdl"
path.write_bytes(out)
displacements=[abs(m-motions[0]) for m in motions]
if max(displacements)<0.1: raise SystemExit("MP40_ALIAS_EXPORT_RED all poses static")
report={
  "schema":1,"format":"Quake MDL v6","experimental_only":True,
  "vertex_count":verts,"triangle_count":tris,"frame_count":MODEL_POSES,
  "skin_count":2,"embedded_skin_size":[WIDTH,HEIGHT],
  "texture_override_tga_required":True,
  "source_mesh_face_counts":face_ranges,"source_action":base_action.name,
  "source_action_range":[float(lo),float(hi)],
  "sampled_source_frames":frame_times,
  "time_mapping_authoritative":False,
  "pose_avg_displacements":motions,
  "largest_avg_pose_delta":max(displacements),
  "all_frames_real_rigged_mesh_evaluation":True,
  "normals_authoritative":False,
  "in_game_playtested":False,
  "commercial_distribution_approved":False,
  "bytes":len(out)
}
(dest/"alias-export-report.json").write_text(json.dumps(report,indent=2))
print("MP40_46_FRAME_REAL_GEOMETRY_ALIAS_EXPERIMENT_GREEN",verts,tris,MODEL_POSES,len(out))
print("MP40_SKIN_AND_ANIMATION_AUTHORITY_PENDING; NEVER SHIP THIS MODEL")
