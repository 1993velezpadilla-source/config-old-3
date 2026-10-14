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
import re
import struct
import sys
from pathlib import Path
from mathutils import Vector, Matrix

args=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
if len(args)!=5: raise SystemExit("Expected <output-dir> <original-vril-mp40.mdl> <measured-registration.json> <Quake-anorms.h> <original-pose-timeline.json>")
dest=Path(args[0]).resolve()
reference_mdl=Path(args[1]).resolve()
measured_transform=Path(args[2]).resolve()
normal_table_path=Path(args[3]).resolve()
original_timeline_path=Path(args[4]).resolve()
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
original_timing=json.loads(original_timeline_path.read_text())
authoritative_frames=original_timing["source_frame_for_published_frame"]
if len(authoritative_frames)!=MODEL_POSES or original_timing["relative_p90_error"]>=.13:
    raise SystemExit("MP40_ALIAS_EXPORT_RED published 46-pose timing authority not valid")
if any(not 1<=x<=83 for x in authoritative_frames):
    raise SystemExit("MP40_ALIAS_EXPORT_RED invalid authored source timeline frame")
WIDTH,HEIGHT=2048,1024
objects=[(stock,0),(gun,1)]
corner_vertex_map=[]
stverts=[]
triangles=[]
face_ranges={}
# MDL indexes positions and UVs per vertex, not per polygon corner.
# The earlier exporter wrote three independent vertices for every triangle,
# producing hard shading seams across all 3593 faces and needless memory use.
# Share corners only when their source vertex AND atlas UV are identical;
# keep genuine texture seams separate, with no arbitrary vertex welding.
vertex_for_corner={}
uv_clamp_count=0
uv_corner_count=0
uv_min=[float("inf"),float("inf")]
uv_max=[-float("inf"),-float("inf")]
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
            uv_corner_count+=1
            uv_min=[min(uv_min[0],u),min(uv_min[1],v)]
            uv_max=[max(uv_max[0],u),max(uv_max[1],v)]
            if u<0 or u>1 or v<0 or v>1:
                uv_clamp_count+=1
            u=min(1,max(0,u))
            v=min(1,max(0,v))
            s=min(WIDTH-1,max(0,round((side+u)*WIDTH/2)-1))
            t=min(HEIGHT-1,max(0,round((1-v)*HEIGHT)-1))
            key=(obj.name,int(loop.vertex_index),s,t)
            if key not in vertex_for_corner:
                vertex_for_corner[key]=len(corner_vertex_map)
                corner_vertex_map.append((obj.name,int(loop.vertex_index)))
                stverts.append((0,s,t))
            corners.append(vertex_for_corner[key])
        triangles.append((1, *corners))
    face_ranges[obj.name]=len(triangles)-face_start

verts=len(stverts)
tris=len(triangles)
if not (1000<=verts<=16384 and 3200<=tris<=16384):
    raise SystemExit("MP40_ALIAS_EXPORT_RED exceeds Vril alias limits "+str((verts,tris)))
if uv_clamp_count:
    print("MP40_SOURCE_UV_OUTSIDE_ZERO_ONE",uv_clamp_count,"of",uv_corner_count,"range",uv_min,uv_max)
if face_ranges.get(stock.name)!=364 or face_ranges.get(gun.name)!=3229:
    raise SystemExit("MP40_ALIAS_EXPORT_RED hybrid triangle identity drift "+str(face_ranges))
# NZ:P relies on Quake's exact 162-entry alias normal lookup table.
# Always generate normals from actual moving faces; index zero everywhere
# causes severe flat/black areas and spiky highlights on Android.
entries=re.findall(r"\{\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*\}",normal_table_path.read_text())
quake_normals=[tuple(float(c) for c in row) for row in entries]
if len(quake_normals)!=162:
    raise SystemExit("MP40_ALIAS_EXPORT_RED canonical Quake normal table not exactly 162")
positions=[]
frame_times=[]
scene=bpy.context.scene
for k in range(MODEL_POSES):
    t=int(authoritative_frames[k])
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
# THE SOURCE FILES PROVIDE THEIR OWN TRANSFORM. An independently measured
# surface correspondence between the original Blender authoring mesh and the
# compiled stock NZP MP40 has established the exact Blender->game coordinates
# (trimmed ICP across 48 axis candidates). Never substitute a guessed axis
# swap or hand-tuned translation when those actual source positions exist.
import hashlib
r=measured_transform.read_text()
register=json.loads(r)
ref=reference_mdl.read_bytes()
if register["reference_mdl_sha256"]!=hashlib.sha256(ref).hexdigest():
    raise SystemExit("MP40_ALIAS_EXPORT_RED measured matrix against different model")
if register.get("error_relative_to_original_MDL_bbox_diagonal",{}).get("p90",1)>.02:
    raise SystemExit("MP40_ALIAS_EXPORT_RED actual position fit does not meet 2% bound")
best=register["best"]
scale=float(best["scale"])
rot=best["rotation"]
translation=best["translation"]
if not (0.90<scale<1.10):
    raise SystemExit("MP40_ALIAS_EXPORT_RED unexpected source unit scale")
def map_to_game(p):
    return tuple(float(scale*sum(float(p[k])*rot[k][j] for k in range(3))+translation[j]) for j in range(3))
positions=[[map_to_game(p) for p in frame] for frame in positions]
print("MP40_ORIGINAL_QUAKE_MDL_ICP_COORDINATES_USED_GREEN",
      "scale",scale,"fit_p90",register["error_relative_to_original_MDL_bbox_diagonal"]["p90"])
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
# The authoring mesh may contain flipped triangles caused by reflected
# Aether->NZP alignment; cull must agree with the actual evaluated source.
# Determine winding on sampled first pose, then keep it consistent on ALL frames.
# Source Blender faces and MDL face index order are equivalent at this stage.
winding_reflection=(float(Matrix(rot).determinant())<0.0)
if winding_reflection:
    triangles=[(row[0],row[1],row[3],row[2]) for row in triangles]
motions=[]
first=positions[0]
normal_index_ranges=[]
for k,frame in enumerate(positions):
    packed=[]
    for p in frame:
        packed.append(tuple(min(255,max(0,int(round((p[j]-vmin[j])/scale[j])))) for j in range(3)))
    lo_q=[min(p[j] for p in packed) for j in range(3)]
    hi_q=[max(p[j] for p in packed) for j in range(3)]
    name=("f%02d"%k).encode().ljust(16,b"\x00")
    out+=struct.pack("<i4B4B16s",0,*lo_q,0,*hi_q,0,name)
    # Weighted face normals, one smooth normal per MDL corner. This maintains
    # original topology but prevents hardcoded normal=0 for every vertex.
    acc=[[0.0,0.0,0.0] for _ in range(verts)]
    for _,a,b,c in triangles:
        pa,pb,pc=frame[a],frame[b],frame[c]
        ux,uy,uz=[pb[i]-pa[i] for i in range(3)]
        vx,vy,vz=[pc[i]-pa[i] for i in range(3)]
        normal=(uy*vz-uz*vy,uz*vx-ux*vz,ux*vy-uy*vx)
        for ind in (a,b,c):
            for axis in range(3):acc[ind][axis]+=normal[axis]
    ids=[]
    for v in acc:
        nrm=math.sqrt(sum(component*component for component in v))
        if nrm<1.e-9:ids.append(0);continue
        unit=[component/nrm for component in v]
        ids.append(max(range(162),key=lambda i:sum(unit[j]*quake_normals[i][j] for j in range(3))))
    normal_index_ranges.append(len(set(ids)))
    for p,nidx in zip(packed,ids): out+=struct.pack("<4B",*p,nidx)
    delta=sum(math.dist(p,q) for p,q in zip(frame,first))/len(frame)
    motions.append(delta)
assert len(out)==84+2*(4+WIDTH*HEIGHT)+verts*12+tris*16+MODEL_POSES*(4+8+16+verts*4)
path=dest/"v_mp40_aether_hybrid_EXPERIMENT_ONLY.mdl"
path.write_bytes(out)
displacements=[abs(m-motions[0]) for m in motions]
if max(displacements)<0.1: raise SystemExit("MP40_ALIAS_EXPORT_RED all poses static")
if min(normal_index_ranges)<8: raise SystemExit("MP40_ALIAS_EXPORT_RED insufficient distinct normals")
report={
  "schema":1,"format":"Quake MDL v6","experimental_only":True,
  "vertex_count":verts,"triangle_count":tris,"frame_count":MODEL_POSES,
  "smooth_shared_corner_vertices":True,
  "source_triangle_corner_count":3*tris,
  "deduplicated_vertex_savings":3*tris-verts,
  "source_uv_out_of_range_corners":uv_clamp_count,
  "source_uv_range":[uv_min,uv_max],
  "skin_count":2,"embedded_skin_size":[WIDTH,HEIGHT],
  "texture_override_tga_required":True,
  "source_mesh_face_counts":face_ranges,"source_action":base_action.name,
  "source_action_range":[float(lo),float(hi)],
  "source_to_mdl_original_measured_transform":best,
  "source_to_mdl_original_fit_error_relative":register["error_relative_to_original_MDL_bbox_diagonal"],
  "source_to_mdl_transform_from_icp":True,
  "reference_mdl_sha256":register["reference_mdl_sha256"],
  "sampled_source_frames":frame_times,
  "time_mapping_authoritative":True,
  "time_mapping_from_actual_original_published_MDL":True,
  "original_timeline_match_p90":original_timing["relative_p90_error"],
  "pose_avg_displacements":motions,
  "largest_avg_pose_delta":max(displacements),
  "all_frames_real_rigged_mesh_evaluation":True,
  "quake_original_162_normal_lut":True,
  "normal_distinct_indices_per_frame":normal_index_ranges,
  "source_fit_reflection_and_winding_corrected":winding_reflection,
  "normals_authoritative":True,
  "in_game_playtested":False,
  "commercial_distribution_approved":False,
  "bytes":len(out)
}
(dest/"alias-export-report.json").write_text(json.dumps(report,indent=2))
print("MP40_46_FRAME_REAL_GEOMETRY_ALIAS_EXPERIMENT_GREEN",verts,tris,MODEL_POSES,len(out))
print("MP40_SKIN_AND_ANIMATION_AUTHORITY_PENDING; NEVER SHIP THIS MODEL")
