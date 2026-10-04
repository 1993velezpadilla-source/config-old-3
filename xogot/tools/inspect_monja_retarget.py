import bpy
import json
import re
import sys
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "monja-rig"
OUT.mkdir(parents=True, exist_ok=True)

MONJA = ROOT / "assets" / "zombies" / "monja_basica.glb"
DONOR = ROOT / "assets" / "zombie_mocap" / "retarget" / "UAL2_Standard.glb"
CMU = sorted((ROOT / "assets" / "zombie_mocap" / "raw").rglob("*.fbx"))

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def world_bounds(meshes):
    points=[]
    for obj in meshes:
        for corner in obj.bound_box:
            points.append(obj.matrix_world @ Vector(corner))
    if not points:
        return None
    mn=Vector(points[0]); mx=Vector(points[0])
    for p in points[1:]:
        mn.x=min(mn.x,p.x); mn.y=min(mn.y,p.y); mn.z=min(mn.z,p.z)
        mx.x=max(mx.x,p.x); mx.y=max(mx.y,p.y); mx.z=max(mx.z,p.z)
    size=mx-mn
    return {
        "min":[round(v,6) for v in mn],
        "max":[round(v,6) for v in mx],
        "size":[round(v,6) for v in size],
        "center":[round(v,6) for v in ((mn+mx)*0.5)],
    }

def inspect_scene(label):
    meshes=[o for o in bpy.context.scene.objects if o.type=="MESH"]
    arms=[o for o in bpy.context.scene.objects if o.type=="ARMATURE"]
    actions=[]
    for a in bpy.data.actions:
        fr=a.frame_range
        actions.append({
            "name":a.name,
            "frame_start":float(fr[0]),
            "frame_end":float(fr[1]),
            "fcurves":len(a.fcurves),
        })
    return {
        "label":label,
        "bounds":world_bounds(meshes),
        "meshes":[{
            "name":o.name,
            "vertices":len(o.data.vertices),
            "polygons":len(o.data.polygons),
            "vertex_groups":[g.name for g in o.vertex_groups],
            "armature_modifiers":[
                {"name":m.name,"object":m.object.name if m.object else None}
                for m in o.modifiers if m.type=="ARMATURE"
            ],
        } for o in meshes],
        "armatures":[{
            "name":a.name,
            "bones":[b.name for b in a.data.bones],
            "bone_count":len(a.data.bones),
            "action":a.animation_data.action.name if a.animation_data and a.animation_data.action else None,
        } for a in arms],
        "actions":actions,
    }

def canonical(name):
    s=name.lower()
    s=re.sub(r"mixamorig[:_\- ]*","",s)
    s=re.sub(r"[^a-z0-9]","",s)
    replacements={
        "pelvis":"hips","hip":"hips",
        "spine01":"spine","spine02":"spine1","spine03":"spine2",
        "leftclavicle":"leftshoulder","lclavicle":"leftshoulder",
        "rightclavicle":"rightshoulder","rclavicle":"rightshoulder",
        "lupperarm":"leftarm","leftupperarm":"leftarm",
        "rupperarm":"rightarm","rightupperarm":"rightarm",
        "llowerarm":"leftforearm","leftlowerarm":"leftforearm",
        "rlowerarm":"rightforearm","rightlowerarm":"rightforearm",
        "lthigh":"leftupleg","leftthigh":"leftupleg",
        "rthigh":"rightupleg","rightthigh":"rightupleg",
        "lcalf":"leftleg","leftcalf":"leftleg","lshin":"leftleg",
        "rcalf":"rightleg","rightcalf":"rightleg","rshin":"rightleg",
        "lfoot":"leftfoot","rfoot":"rightfoot",
        "lhand":"lefthand","rhand":"righthand",
    }
    return replacements.get(s,s)

def suggest_map(src_bones,dst_bones):
    dst_by={}
    for d in dst_bones:
        dst_by.setdefault(canonical(d),[]).append(d)
    mapping={}
    unmatched=[]
    for s in src_bones:
        c=canonical(s)
        if c in dst_by:
            mapping[s]=dst_by[c][0]
        else:
            unmatched.append(s)
    return mapping,unmatched

report={"monja":None,"donor":None,"cmu":[],"suggested_maps":[]}

reset()
bpy.ops.import_scene.gltf(filepath=str(MONJA))
report["monja"]=inspect_scene("monja")
print("MONJA",json.dumps(report["monja"]["bounds"]))

reset()
bpy.ops.import_scene.gltf(filepath=str(DONOR))
report["donor"]=inspect_scene("ual2_donor")
donor_bones=[]
if report["donor"]["armatures"]:
    donor_bones=report["donor"]["armatures"][0]["bones"]
print("DONOR bones",len(donor_bones),"actions",len(report["donor"]["actions"]))

for path in CMU:
    reset()
    try:
        bpy.ops.import_scene.fbx(
            filepath=str(path),
            automatic_bone_orientation=False,
            use_anim=True,
        )
        info=inspect_scene(path.name)
        info["path"]=str(path.relative_to(ROOT))
        report["cmu"].append(info)
        src_bones=info["armatures"][0]["bones"] if info["armatures"] else []
        mapping,unmatched=suggest_map(src_bones,donor_bones)
        report["suggested_maps"].append({
            "path":info["path"],
            "source_bone_count":len(src_bones),
            "matched_count":len(mapping),
            "mapping":mapping,
            "unmatched":unmatched,
        })
        print("CMU",path.name,"bones",len(src_bones),"matched",len(mapping),"actions",len(info["actions"]))
    except Exception as exc:
        report["cmu"].append({"path":str(path.relative_to(ROOT)),"error":repr(exc)})
        print("CMU_ERROR",path.name,repr(exc))

# Hard gates: do not claim rig-ready if these fundamentals fail.
report["gate"]={
    "monja_has_mesh":bool(report["monja"]["meshes"]),
    "monja_has_existing_armature":bool(report["monja"]["armatures"]),
    "donor_has_armature":bool(report["donor"]["armatures"]),
    "donor_bone_count":len(donor_bones),
    "cmu_files":len(CMU),
    "cmu_with_armature":sum(1 for x in report["cmu"] if x.get("armatures")),
}
report["gate"]["ready_for_weight_transfer"]=(
    report["gate"]["monja_has_mesh"]
    and report["gate"]["donor_has_armature"]
    and report["gate"]["donor_bone_count"] >= 20
    and report["gate"]["cmu_with_armature"] == len(CMU)
)

(OUT/"retarget-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
(OUT/"summary.txt").write_text(
    "\n".join([
        f"Monja meshes: {len(report['monja']['meshes'])}",
        f"Monja existing armatures: {len(report['monja']['armatures'])}",
        f"Donor bones: {len(donor_bones)}",
        f"Donor actions: {len(report['donor']['actions'])}",
        f"CMU clips inspected: {len(CMU)}",
        f"CMU clips with armature: {report['gate']['cmu_with_armature']}",
        f"Ready for weight transfer: {report['gate']['ready_for_weight_transfer']}",
    ])+"\n",
    encoding="utf-8"
)

if not report["gate"]["ready_for_weight_transfer"]:
    print("XZOGOT_MONJA_RIG_INSPECT_NOT_READY",report["gate"])
    sys.exit(3)

print("XZOGOT_MONJA_RIG_INSPECT_GREEN",report["gate"])
