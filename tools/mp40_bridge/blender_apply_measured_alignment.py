#!/usr/bin/env python3
"""Apply measured Aether->NZP surface transform to the REAL hybrid MP40.

No bounding-box or hand-tuned coordinates. Source mesh vertex positions and
one independently measured, *bidirectional* ICP matrix determine locations.
Original stock hand mesh and stock animation rig are left intact.
Quantify first-pose visual mismatch, reject if alignment gets worse.
This is an experimental authoring operation, not proof of Android quality.
"""
import bpy
import json
import math
import sys
from pathlib import Path
from mathutils import Vector

args=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
if len(args)!=2:
    raise SystemExit("USAGE <actual-aether-surface-fit.json> <output-dir>")
report_path,out=map(lambda x:Path(x).resolve(),args)
out.mkdir(parents=True,exist_ok=True)
report=json.loads(report_path.read_text())
if report.get("positions_eyeballed") is not False or report.get("axis_candidates")!=48:
    raise SystemExit("MP40_MEASURED_ALIGN_RED missing authentic alignment provenance")
# 10% is a measured geometric-similarity ceiling, NOT an assertion that
# two distinct weapon meshes have identical shapes.
if not report.get("precision_gate_p90_lt_10_percent",False):
    raise SystemExit("MP40_MEASURED_ALIGN_RED stock and Aether gun source meshes disagree >10%")
if not report.get("symmetric_coverage_required",False):
    raise SystemExit("MP40_MEASURED_ALIGN_RED require reverse-coverage test")
fit=report["measured_aether_to_stock"]
s=float(fit["scale"])
r=fit["rotation"]
t=fit["translation"]
if not 0.1<s<1000 or len(r)!=3 or any(len(row)!=3 for row in r) or len(t)!=3:
    raise SystemExit("MP40_MEASURED_ALIGN_RED invalid transform")
if any(not math.isfinite(v) for row in r for v in row) or any(not math.isfinite(v) for v in t):
    raise SystemExit("MP40_MEASURED_ALIGN_RED nan transform")
scene=bpy.context.scene
scene.frame_set(1);bpy.context.view_layer.update()
original=bpy.data.objects.get("MP40_SM")
new=bpy.data.objects.get("Aether_HD_MP40_On_Vril_Rig")
hands=bpy.data.objects.get("NZP_Original_Animated_Hands_ONLY")
stock=bpy.data.objects.get("nzp_hands.ms3d.mo")
if not original or not new or not hands or not stock:
    raise SystemExit("MP40_MEASURED_ALIGN_RED expected real hybrid source objects missing")
if len(original.data.vertices)!=len(new.data.vertices) or len(new.data.vertices)<3000:
    raise SystemExit("MP40_MEASURED_ALIGN_RED vertex-index correspondence lost")
rig=next((m.object for m in new.modifiers if m.type=="ARMATURE"),None)
if rig is None:
    raise SystemExit("MP40_MEASURED_ALIGN_RED animated stock rig missing")

def evaluate(obj):
    deps=bpy.context.evaluated_depsgraph_get()
    ev=obj.evaluated_get(deps);mesh=ev.to_mesh()
    p=[ev.matrix_world@v.co for v in mesh.vertices]
    ev.to_mesh_clear()
    return p

def transform(pt):
    p=tuple(pt)
    return Vector(tuple(s*sum(p[k]*r[k][i] for k in range(3))+t[i] for i in range(3)))
reference=[transform(original.matrix_world@v.co) for v in original.data.vertices]
before=evaluate(new)
def residual(x):
    dist=[(p-q).length for p,q in zip(x,reference)]
    dist.sort()
    return {
       "median":dist[len(dist)//2],
       "p90":dist[int(.9*(len(dist)-1))],
       "rms":math.sqrt(sum(v*v for v in dist)/len(dist)),
       "max":dist[-1],
    }

before_error=residual(before)
inv=new.matrix_world.inverted()
for index,world_target in enumerate(reference):
    new.data.vertices[index].co=inv@world_target
new.data.update()
bpy.context.view_layer.update()
after=evaluate(new)
after_error=residual(after)
# Preserve 3D target from independently measured source geometry. A poor
# Blender armature pose is another measurable problem, not a reason to retune.
gun_diameter=float(report["original_stock_bbox_diagonal"])
norm_after=after_error["p90"]/max(1.0,gun_diameter)
norm_before=before_error["p90"]/max(1.0,gun_diameter)
result={
 "schema":1,
 "input_fit_p90_percent":100*float(report["normalized_fit_errors"]["p90"]),
 "input_fit_reverse_p90_percent":100*float(report["normalized_fit_errors"]["reverse_p90"]),
 "input_symmetric_coverage":True,
 "source":"Aether original weapon-only vertices in original GLB",
 "target":"original NZP authored weapon surface in Blender, via measured 48-axis bidirectional ICP",
 "matrix_scale":s,"matrix_rotation_row_space":r,"matrix_translation":t,
 "source_armature":rig.name,
 "source_hands_preserved":hands.name,
 "before_pose1_vertex_target_error":before_error,
 "after_pose1_vertex_target_error":after_error,
 "before_pose1_p90_relative":norm_before,
 "after_pose1_p90_relative":norm_after,
 "improves_actual_alignment":after_error["p90"]<before_error["p90"],
 "passes_strict_pose1_target_5pct":norm_after<.05,
 "positions_guessed":False,
 "clip_retiming_validated":False,
 "real_android_playtest":False,
 "commercial_licensing_cleared":False,
}
(out/"applied-aether-to-nzp-measured-alignment.json").write_text(json.dumps(result,indent=2))
print("MP40_MEASURED_ALIGNMENT_ACTUAL_VERTEX_GATE",
      "before_p90",round(norm_before*100,2),"after_p90",round(norm_after*100,2),
      "stock_ref_symmetric_pct",100*report["normalized_fit_errors"]["p90"])
if not result["improves_actual_alignment"]:
    raise SystemExit("MP40_MEASURED_ALIGN_RED computed transform failed to improve pose1 evaluated geometry")
if not result["passes_strict_pose1_target_5pct"]:
    raise SystemExit("MP40_MEASURED_ALIGN_RED pose1 skinned mesh not aligned within 5%; must resolve bind")
output=out/"mp40-hybrid-MEASURED-SOURCE-ALIGNMENT.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(output))
print("MP40_SOURCE_TRANSFORM_APPLIED_TO_ACTUAL_HYBRID_GREEN")
print("MP40_LEGACY_RELOAD_ALIGNMENT_STILL_UNCERTIFIED")
