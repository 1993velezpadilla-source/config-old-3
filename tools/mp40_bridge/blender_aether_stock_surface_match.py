#!/usr/bin/env python3
"""Find Aether gun -> original NZP gun positions by REAL mesh correspondence.

Never aligns HD gun by eye or "center bounding boxes". Uses evaluated stock
Body/Clip/Slide-weighted triangles and original Aether weapon vertices,
48 orthogonal axis initializations + robust trimmed nearest-neighbor ICP.

A good fit is measured, NOT ASSUMED. This script does not ship a model.
"""
import bpy,json,itertools,math,sys
from pathlib import Path
from collections import Counter
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree
args=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
if len(args)!=1:raise SystemExit("EXPECTED output-dir")
out=Path(args[0]).resolve();out.mkdir(parents=True,exist_ok=True)
old=bpy.data.objects.get("nzp_hands.ms3d.mo")
source=bpy.data.objects.get("MP40_SM")
if old is None or source is None:raise RuntimeError("MP40_AETHER_MATCH_RED source meshes missing")
scene=bpy.context.scene
scene.frame_set(1);bpy.context.view_layer.update()
groups={g.index:g.name for g in old.vertex_groups}
weapon_bones={"Body","Slide","Clip"}
targets=set()
for poly in old.data.polygons:
    weight=Counter()
    for index in poly.vertices:
        for membership in old.data.vertices[index].groups:
            if membership.weight>.01:
                weight[groups[membership.group]]+=membership.weight
    if weight and weight.most_common(1)[0][0] in weapon_bones:
        targets.update(poly.vertices)
depe=bpy.context.evaluated_depsgraph_get()
obj=old.evaluated_get(depe)
me=obj.to_mesh()
target=np.array([list(obj.matrix_world@me.vertices[v].co) for v in sorted(targets)],dtype=float)
obj.to_mesh_clear()
raw=np.array([list(source.matrix_world@v.co) for v in source.data.vertices],dtype=float)
# Repeated UV vertices in modern meshes add no extra geometric information.
# Use deterministic ~900 source points for CI runtime stability.
stride=max(1,int(math.ceil(len(raw)/950)))
src=raw[::stride]
if len(target)<100 or len(src)<300:raise RuntimeError("MP40_AETHER_MATCH_RED insufficient actual geometry points")
kd=KDTree(len(target))
for i,p in enumerate(target):kd.insert(Vector(p),i)
kd.balance()
def nearest(points):
    ii=[];ds=[]
    for p in points:
        q,j,d=kd.find(Vector(p))
        ii.append(j);ds.append(d)
    return np.array(ii),np.array(ds)
scenter=src.mean(axis=0);tcenter=target.mean(axis=0)
isotropic=float(np.sqrt(((target-tcenter)**2).sum(axis=1).mean()) /
                np.sqrt(((src-scenter)**2).sum(axis=1).mean()))
tdiam=float(np.linalg.norm(target.max(axis=0)-target.min(axis=0)))
fits=[]
for perm in itertools.permutations(range(3)):
    for signs in itertools.product([-1,1],repeat=3):
        R=np.zeros((3,3))
        for i,k in enumerate(perm):R[i,k]=signs[i]
        parity=float(round(np.linalg.det(R)))
        scale=isotropic
        shift=tcenter-scale*scenter@R
        for it in range(8):
            xyz=scale*(src@R)+shift
            nearest_i,dist=nearest(xyz)
            selected=dist<=np.quantile(dist,.72)
            left=src[selected];right=target[nearest_i[selected]]
            a=left.mean(axis=0);b=right.mean(axis=0)
            u,sv,vt=np.linalg.svd((left-a).T@(right-b))
            sgn=np.diag([1.,1.,parity*float(np.linalg.det(u@vt))])
            R=u@sgn@vt
            proposed_scale=float((sv*np.diag(sgn)).sum()/max(1.e-12,((left-a)**2).sum()))
            if not .5<proposed_scale<1000:break
            # Prevent degenerate ICP solutions which collapse the whole Aether
            # model onto a tiny portion of the original gun, showing falsely
            # excellent one-way nearest-neighbor error. Both represent an MP40
            # so their whole-gun geometric scale must remain near the actual
            # measured point-cloud RMS ratio (not an arbitrary scene constant).
            scale=min(isotropic*1.15,max(isotropic*.85,proposed_scale))
            shift=b-scale*a@R
        else:
            predicted=scale*(src@R)+shift
            idx,d=nearest(predicted)
            # Bidirectional coverage: original MP40 ALSO has to find a close
            # counterpart on Aether; one-way ICP can silently collapse onto
            # one easy-to-fit tiny region while the rest disappears.
            source_kd=KDTree(len(predicted))
            for q,p in enumerate(predicted):source_kd.insert(Vector(p),q)
            source_kd.balance()
            backward=[float(source_kd.find(Vector(p))[2]) for p in target]
            fits.append({"median":float(np.median(d)),"p90":float(np.quantile(d,.9)),
                         "rms":float(np.sqrt(np.mean(d*d))),
                         "reverse_p90":float(np.quantile(backward,.9)),
                         "reverse_median":float(np.median(backward)),
                         "scale":scale,"scale_ratio_to_initial_geometry":scale/isotropic,
                         "rotation":R.tolist(),"translation":shift.tolist(),
                         "parity":parity,"initial_perm":perm,"initial_signs":signs})
if not fits:raise RuntimeError("MP40_AETHER_MATCH_RED no converged skin")
fits.sort(key=lambda x:(x["p90"]+x["reverse_p90"],x["median"]+x["reverse_median"]))
best=fits[0]
relative={"median":best["median"]/tdiam,"p90":best["p90"]/tdiam,
          "reverse_p90":best["reverse_p90"]/tdiam,
          "reverse_median":best["reverse_median"]/tdiam,
          "rms":best["rms"]/tdiam}
report={"schema":1,"method":"actual weapon-only face weighted source geometry, robust ICP",
        "stock_reference_mesh":old.name,"aether_reference_mesh":source.name,
        "original_stock_gun_vertices":len(target),"aether_source_vertices":len(raw),
        "aether_fitted_samples":len(src),"axis_candidates":48,
        "converged_candidates":len(fits),"original_stock_bbox_diagonal":tdiam,
        "initial_actual_rms_geometry_scale":isotropic,
        "symmetric_coverage_required":True,
        "measured_aether_to_stock":best,"normalized_fit_errors":relative,
        "precision_gate_p90_lt_5_percent":relative["p90"]<.05 and relative["reverse_p90"]<.05,
        "precision_gate_p90_lt_10_percent":relative["p90"]<.1 and relative["reverse_p90"]<.1,
        "positions_eyeballed":False,"source_game_data_used":True,
        "automatic_original_animation_alignment_proven":False}
(out/"aether-to-stock-actual-gun-surface-fit.json").write_text(json.dumps(report,indent=2))
print("MP40_AETHER_GUN_TO_ORIGINAL_NZP_SURFACE_MATRIX_MEASURED_GREEN",json.dumps({"relative":relative,"scale":best["scale"],"translation":best["translation"],"R":best["rotation"]}))
print("MP40_AETHER_TO_STOCK_PRECISION_BIDIRECTIONAL", "PASS_5_PERCENT" if report["precision_gate_p90_lt_5_percent"] else ("PASS_10_PERCENT" if report["precision_gate_p90_lt_10_percent"] else "REJECT_POOR_MATCH"))
