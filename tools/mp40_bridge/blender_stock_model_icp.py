#!/usr/bin/env python3
"""Register actual authored NZP MP40 Blender vertices to shipped Quake MDL verts.

NO eyeballed position. Exhaustively tries all 48 orthogonal axis permutations,
then computes a best-fit 3D similarity using trimmed ICP/Kabsch on REAL
source first-pose points and REAL MDL shipped first-pose points.

The assets need not share indices; residual/error is exposed, NOT suppressed.
This alone cannot certify reload/ADS/camera/weapon-source licensing.
"""
import bpy, json, itertools, math, struct, sys
from pathlib import Path
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree

args=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
if len(args)!=2: raise SystemExit("USAGE: -- <original-vril-mp40.mdl> <output-json>")
source_path,out=map(lambda p:Path(p).resolve(),args)
mdl=source_path.read_bytes()
if mdl[:4]!=b"IDPO" or struct.unpack_from("<I",mdl,4)[0]!=6:
    raise RuntimeError("MP40_ICP_RED original stock model not MDL v6")
m_scale=np.array(struct.unpack_from("<3f",mdl,8))
m_origin=np.array(struct.unpack_from("<3f",mdl,20))
nsk, w,h,nv,nt=struct.unpack_from("<5i",mdl,48)
if nsk<1 or nsk>8 or nv<100 or nv>2048:raise RuntimeError("MP40_ICP_RED stock header")
ptr=84
for i in range(nsk):
    sktype,=struct.unpack_from("<I",mdl,ptr)
    if sktype!=0: raise RuntimeError("MP40_ICP_RED grouped stock skin")
    ptr+=4+w*h
ptr+=nv*12+nt*16
kind,=struct.unpack_from("<I",mdl,ptr)
if kind!=0: raise RuntimeError("MP40_ICP_RED first pose grouped")
ptr+=28
target=np.array([[float(mdl[ptr+4*i+j])*m_scale[j]+m_origin[j] for j in range(3)] for i in range(nv)])
mesh=bpy.data.objects.get("nzp_hands.ms3d.mo")
if mesh is None: raise RuntimeError("MP40_ICP_RED original authored mesh missing")
bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
ev=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
m=ev.to_mesh()
src=np.array([list(ev.matrix_world@v.co) for v in m.vertices])
ev.to_mesh_clear()
if len(src)!=571: raise RuntimeError("MP40_ICP_RED unexpected source vertex topology "+str(len(src)))
kd=KDTree(len(target))
for i,x in enumerate(target): kd.insert(Vector(x),i)
kd.balance()
def lookup(x):
    idx=[]
    dst=[]
    for row in x:
        p,i,d=kd.find(Vector(row))
        idx.append(i);dst.append(d)
    return np.array(idx),np.array(dst)
src_cent=src.mean(axis=0)
tar_cent=target.mean(axis=0)
src_rms=np.sqrt(np.mean(np.sum((src-src_cent)**2,axis=1)))
tar_rms=np.sqrt(np.mean(np.sum((target-tar_cent)**2,axis=1)))
init_scale=tar_rms/src_rms
target_diam=np.linalg.norm(target.max(axis=0)-target.min(axis=0))
results=[]
for perm in itertools.permutations(range(3)):
    for signs in itertools.product([-1,1],repeat=3):
        rot=np.zeros((3,3),float)
        for i,k in enumerate(perm):rot[i,k]=signs[i]
        parity=np.linalg.det(rot)
        scale=init_scale
        trans=tar_cent-scale*src_cent@rot
        for it in range(10):
            pred=scale*(src@rot)+trans
            match_index,distance=lookup(pred)
            kept=distance<=np.quantile(distance,0.80)
            s=src[kept];t=target[match_index[kept]]
            ac=s.mean(axis=0);bc=t.mean(axis=0)
            u,sg,vt=np.linalg.svd((s-ac).T@(t-bc))
            diag=np.diag([1,1,parity*np.linalg.det(u@vt)])
            newrot=u@diag@vt
            newscale=float((sg*np.diag(diag)).sum()/np.sum((s-ac)**2))
            if not (np.isfinite(newscale) and .01<newscale<100):break
            rot,scale=newrot,newscale
            trans=bc-scale*ac@rot
        else:
            idx,dist=lookup(scale*(src@rot)+trans)
            # Penalize wrong mirrored pose or tail of mismatched raw geometry.
            results.append({"median":float(np.median(dist)),"rms":float(np.sqrt(np.mean(dist**2))),
                            "p90":float(np.quantile(dist,.90)),
                            "scale":scale,"rotation":rot.tolist(),"translation":trans.tolist(),
                            "det":float(np.linalg.det(rot)),"axis_perm":perm,"signs":signs})
if not results: raise RuntimeError("MP40_ICP_RED no successful source->MDL fits")
results.sort(key=lambda x:(x["p90"],x["rms"]))
best=results[0]
normalized={k:float(best[k]/target_diam) for k in ("median","rms","p90")}
report={"schema":1,"method":"measured source-asset vertex cloud vs shipped alias MDL, 48 initial orientations, trimmed ICP",
        "original_source_blend_mesh":mesh.name,"original_source_vertex_count":len(src),
        "original_shipped_mdl_vertex_count":len(target),
        "reference_mdl":source_path.name,"source_frame":1,"target_frame":1,
        "candidate_axis_initializations":48,"successful_fits":len(results),
        "best":best,"error_relative_to_original_MDL_bbox_diagonal":normalized,
        "target_mdl_bbox_diagonal":float(target_diam),
        "pass_max_relative_p90_5_percent":bool(normalized["p90"]<=.05),
        "pass_max_relative_p90_10_percent":bool(normalized["p90"]<=.10),
        "original_source_and_compiled_model_not_vertex_identical":len(src)!=len(target),
        "exact_source_vertices_are_measured":True,"proof_all_animation_frames":False,
        "gameplay_visual_alignment_proven":False}
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(report,indent=2))
print("MP40_SOURCE_TO_VRIL_MDL_POINTCLOUD_MATRIX_MEASURED_GREEN",json.dumps({"scale":best["scale"],"rotation":best["rotation"],"translation":best["translation"],"relative_error":normalized}))
if normalized["p90"]>.10:
    print("MP40_SOURCE_TO_VRIL_MDL_REGISTRATION_UNRELIABLE: source authoring geometry differs too much from shipping alias model")
else:
    print("MP40_SOURCE_TO_VRIL_MDL_REGISTRATION_WITHIN_10_PERCENT_GREEN")
