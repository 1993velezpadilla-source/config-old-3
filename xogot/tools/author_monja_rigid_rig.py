import bpy
import bmesh
import json
import re
from pathlib import Path
from mathutils import Vector, Matrix

ROOT=Path(__file__).resolve().parents[1]
MONJA=ROOT/"assets/zombies/monja_basica.glb"
DONOR=ROOT/"assets/zombie_mocap/retarget/UAL2_Standard.glb"
OUT=ROOT/"build/monja-rigid-rig"
OUT.mkdir(parents=True,exist_ok=True)
OUT_GLB=OUT/"monja_basica_rigid_rig.glb"
REPORT=OUT/"monja_basica_rigid_rig.report.json"

PART_NAMES={
 "torso":"Dismember_Torso",
 "head":"Dismember_Head",
 "left_arm":"Dismember_LeftArm",
 "right_arm":"Dismember_RightArm",
 "left_leg":"Dismember_LeftLeg",
 "right_leg":"Dismember_RightLeg",
}

def fail(msg):
    print("XZOGOT_MONJA_RIGID_RIG_FAIL",msg)
    raise SystemExit(2)

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def meshes(objs):
    return [o for o in objs if o.type=="MESH"]

def snapshot():
    return set(bpy.context.scene.objects)

def bounds(objs):
    pts=[]
    for o in objs:
        pts.extend([o.matrix_world @ Vector(c) for c in o.bound_box])
    if not pts: fail("no bounds")
    mn=Vector(pts[0]); mx=Vector(pts[0])
    for p in pts[1:]:
        for a in range(3):
            mn[a]=min(mn[a],p[a]); mx[a]=max(mx[a],p[a])
    return mn,mx

def canonical(name):
    s=name.lower()
    s=re.sub(r"mixamorig[:_\- ]*","",s)
    s=re.sub(r"[^a-z0-9]","",s)
    swaps={
      "pelvis":"hips","hip":"hips",
      "spine01":"spine","spine02":"spine1","spine03":"spine2",
      "leftupperarm":"leftarm","lupperarm":"leftarm",
      "rightupperarm":"rightarm","rupperarm":"rightarm",
      "leftthigh":"leftupleg","lthigh":"leftupleg",
      "rightthigh":"rightupleg","rthigh":"rightupleg",
    }
    return swaps.get(s,s)

def choose_bone(arm,key):
    prefs={
      "torso":["spine2","spine1","spine","hips"],
      "head":["head","neck"],
      "left_arm":["leftarm","leftupperarm","leftshoulder"],
      "right_arm":["rightarm","rightupperarm","rightshoulder"],
      "left_leg":["leftupleg","leftthigh","leftleg"],
      "right_leg":["rightupleg","rightthigh","rightleg"],
    }[key]
    bones=list(arm.data.bones)
    by={canonical(b.name):b.name for b in bones}
    for p in prefs:
        cp=canonical(p)
        if cp in by:return by[cp]
    # fuzzy fallback
    for p in prefs:
        cp=canonical(p)
        for b in bones:
            cb=canonical(b.name)
            if cp in cb or cb in cp:
                return b.name
    fail(f"no donor bone for {key}; bones={[b.name for b in bones]}")

def classify(center,mn,mx,up,side):
    size=mx-mn
    h=max(size[up],1e-8)
    nz=(center[up]-mn[up])/h
    cx=(mn[side]+mx[side])*0.5
    half=max(size[side]*0.5,1e-8)
    nx=(center[side]-cx)/half
    if nz>=0.825:return "head"
    if 0.405<=nz<0.825 and abs(nx)>=0.48:
        return "left_arm" if nx<0 else "right_arm"
    if nz<0.405:
        return "left_leg" if nx<0 else "right_leg"
    return "torso"

def duplicate_region(src,key,mn,mx,up,side):
    dup=src.copy(); dup.data=src.data.copy()
    dup.name=PART_NAMES[key]+"_"+src.name
    dup.data.name=dup.name+"_Mesh"
    bpy.context.scene.collection.objects.link(dup)
    bm=bmesh.new(); bm.from_mesh(dup.data); bm.faces.ensure_lookup_table()
    remove=[]
    for face in bm.faces:
        wc=dup.matrix_world @ face.calc_center_median()
        if classify(wc,mn,mx,up,side)!=key:
            remove.append(face)
    if remove:bmesh.ops.delete(bm,geom=remove,context="FACES")
    loose=[v for v in bm.verts if not v.link_faces]
    if loose:bmesh.ops.delete(bm,geom=loose,context="VERTS")
    bm.to_mesh(dup.data); bm.free(); dup.data.update()
    if not dup.data.polygons:
        bpy.data.objects.remove(dup,do_unlink=True); return None
    dup["xogot_dismember_part"]=key
    dup["xogot_rigid_bone_rig"]=True
    return dup

reset()

# Animated donor.
before=snapshot()
bpy.ops.import_scene.gltf(filepath=str(DONOR))
donor_objs=list(snapshot()-before)
arms=[o for o in donor_objs if o.type=="ARMATURE"]
donor_mesh=meshes(donor_objs)
if not arms:fail("donor armature missing")
arm=arms[0]
db=bounds(donor_mesh); dmn,dmx=db; dsize=dmx-dmn; dcenter=(dmn+dmx)*0.5

# Full-density Monja.
before=snapshot()
bpy.ops.import_scene.gltf(filepath=str(MONJA))
monja_objs=list(snapshot()-before)
src_meshes=meshes(monja_objs)
if not src_meshes:fail("monja mesh missing")
mmn,mmx=bounds(src_meshes); msize=mmx-mmn; mcenter=(mmn+mmx)*0.5

# Match donor height/center first.
up=max(range(3),key=lambda i:msize[i])
other=[i for i in range(3) if i!=up]
side=max(other,key=lambda i:msize[i])
scale=float(max(dsize)/max(msize)) if max(msize)>1e-8 else 1.0
scaled_center=mcenter*scale
delta=dcenter-scaled_center
align=Matrix.Translation(delta) @ Matrix.Scale(scale,4)
for o in src_meshes:o.matrix_world=align @ o.matrix_world

# Recompute aligned bounds, split by region.
mn,mx=bounds(src_meshes)
size=mx-mn
up=max(range(3),key=lambda i:size[i])
side=max([i for i in range(3) if i!=up],key=lambda i:size[i])

generated=[]
part_polys={k:0 for k in PART_NAMES}
part_bones={}
for src in list(src_meshes):
    for key in PART_NAMES:
        dup=duplicate_region(src,key,mn,mx,up,side)
        if dup:
            generated.append((key,dup))
            part_polys[key]+=len(dup.data.polygons)

source_polys=sum(len(o.data.polygons) for o in src_meshes)
if sum(part_polys.values())!=source_polys:
    fail(f"polygon conservation {sum(part_polys.values())}/{source_polys}")
if any(v<=0 for v in part_polys.values()):
    fail(f"empty rigid part {part_polys}")

# Delete original Monja mesh and donor visible mesh.
for o in src_meshes+donor_mesh:
    if bpy.data.objects.get(o.name) is not None:
        bpy.data.objects.remove(bpy.data.objects.get(o.name),do_unlink=True)

# Parent each full-poly region rigidly to an animated donor bone.
for key,obj in generated:
    bone=choose_bone(arm,key)
    part_bones[key]=bone
    world=obj.matrix_world.copy()
    obj.parent=arm
    obj.parent_type='BONE'
    obj.parent_bone=bone
    obj.matrix_world=world
    obj["xogot_rigid_parent_bone"]=bone

actions=[a.name for a in bpy.data.actions]
required=["Zombie_Idle_Loop","Zombie_Scratch","Zombie_Walk_Fwd_Loop"]
found=[n for n in actions if any(k.lower() in n.lower() for k in required)]
if len(found)<3:fail(f"required animations missing {actions}")

bpy.ops.object.select_all(action='DESELECT')
arm.select_set(True)
for _,o in generated:o.select_set(True)
bpy.context.view_layer.objects.active=arm

bpy.ops.export_scene.gltf(
    filepath=str(OUT_GLB),export_format='GLB',use_selection=True,
    export_animations=True,export_skins=True,export_nla_strips=True,
    export_apply=False,export_extras=True,export_texcoords=True,
    export_normals=True,export_tangents=True,export_materials='EXPORT'
)
if not OUT_GLB.is_file():fail("export missing")
size_bytes=OUT_GLB.stat().st_size

# Reimport validation.
reset(); bpy.ops.import_scene.gltf(filepath=str(OUT_GLB))
out_mesh=[o for o in bpy.context.scene.objects if o.type=="MESH"]
out_arms=[o for o in bpy.context.scene.objects if o.type=="ARMATURE"]
out_actions=[a.name for a in bpy.data.actions]
out_polys=sum(len(o.data.polygons) for o in out_mesh)
semantic={k:sum(PART_NAMES[k].lower() in o.name.lower() for o in out_mesh) for k in PART_NAMES}

report={
 "source_polygons":source_polys,
 "output_polygons":out_polys,
 "polygon_conservation_ok":out_polys==source_polys,
 "armatures":len(out_arms),
 "actions":out_actions,
 "required_actions":[n for n in out_actions if any(k.lower() in n.lower() for k in required)],
 "semantic_mesh_counts":semantic,
 "part_polygons":part_polys,
 "part_bones":part_bones,
 "output_bytes":size_bytes,
 "decimation":False,
 "rig_mode":"rigid_region_bone_parenting",
}
REPORT.write_text(json.dumps(report,indent=2)+"\n")
if not report["polygon_conservation_ok"]:fail("reimport polygon mismatch")
if not out_arms:fail("reimport armature missing")
if len(report["required_actions"])<3:fail("reimport actions missing")
if any(v<=0 for v in semantic.values()):fail(f"semantic parts missing {semantic}")

print("XZOGOT_MONJA_RIGID_RIG_PARTS_GREEN",semantic)
print("XZOGOT_MONJA_RIGID_RIG_ANIMS_GREEN",report["required_actions"])
print("XZOGOT_MONJA_RIGID_RIG_POLYGONS_GREEN",out_polys)
print("XZOGOT_MONJA_RIGID_RIG_BYTES",size_bytes)
print("XZOGOT_MONJA_RIGID_RIG_GREEN")
