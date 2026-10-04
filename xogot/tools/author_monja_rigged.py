import bpy
import json
import sys
from pathlib import Path
from mathutils import Vector, Matrix

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "monja-rigged"
OUT.mkdir(parents=True, exist_ok=True)
MONJA = ROOT / "assets" / "zombies" / "monja_basica.glb"
DONOR = ROOT / "assets" / "zombie_mocap" / "retarget" / "UAL2_Standard.glb"
OUT_GLB = OUT / "monja_basica_rigged.glb"
REPORT = OUT / "monja_rigged_report.json"
PIPELINE_VERSION = "rig-v3-rna-safe"

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def meshes(objs):
    return [o for o in objs if o.type == "MESH"]

def bounds(objs):
    pts=[]
    for o in objs:
        for c in o.bound_box:
            pts.append(o.matrix_world @ Vector(c))
    if not pts:
        return None
    mn=Vector(pts[0]); mx=Vector(pts[0])
    for p in pts[1:]:
        mn.x=min(mn.x,p.x); mn.y=min(mn.y,p.y); mn.z=min(mn.z,p.z)
        mx.x=max(mx.x,p.x); mx.y=max(mx.y,p.y); mx.z=max(mx.z,p.z)
    return mn,mx

def snapshot():
    return set(bpy.context.scene.objects)

reset()

# Import the already-rigged CC0 donor first. Its armature/actions are the animation authority.
before=snapshot()
bpy.ops.import_scene.gltf(filepath=str(DONOR))
donor_objs=list(snapshot()-before)
donor_arms=[o for o in donor_objs if o.type=="ARMATURE"]
donor_meshes=meshes(donor_objs)
if not donor_arms:
    raise SystemExit("No donor armature found")
arm=donor_arms[0]

skinned=[]
for o in donor_meshes:
    if o.vertex_groups and any(m.type=="ARMATURE" for m in o.modifiers):
        skinned.append(o)
if not skinned:
    skinned=[o for o in donor_meshes if o.vertex_groups]
if not skinned:
    raise SystemExit("No weighted donor mesh found")
source=max(skinned,key=lambda o:len(o.data.vertices))

db=bounds(donor_meshes)
if not db:
    raise SystemExit("No donor bounds")
dmn,dmx=db
dsize=dmx-dmn
dcenter=(dmn+dmx)*0.5

# Import high-density Monja.
before=snapshot()
bpy.ops.import_scene.gltf(filepath=str(MONJA))
monja_objs=list(snapshot()-before)
monja_meshes=meshes(monja_objs)
if not monja_meshes:
    raise SystemExit("No Monja meshes found")

mb=bounds(monja_meshes)
mmn,mmx=mb
msize=mmx-mmn
mcenter=(mmn+mmx)*0.5
if msize.y <= 1e-6:
    raise SystemExit("Bad Monja height")

# Fit Monja to donor skeleton in world space. Runtime later scales the exported
# character back to the gameplay target 1.80 m exactly.
scale=float(dsize.y/msize.y)
scaled_center=Vector((mcenter.x*scale,mcenter.y*scale,mcenter.z*scale))
scaled_min_y=mmn.y*scale
delta=Vector((dcenter.x-scaled_center.x, dmn.y-scaled_min_y, dcenter.z-scaled_center.z))
align=Matrix.Translation(delta) @ Matrix.Scale(scale,4)

for o in monja_meshes:
    o.matrix_world = align @ o.matrix_world

# Transfer donor skin weights in C through Blender's Data Transfer modifier.
# This preserves the Monja geometry; only vertex-group weights are created.
src_groups=[g.name for g in source.vertex_groups]
transfer_report=[]
for target in monja_meshes:
    for name in src_groups:
        if target.vertex_groups.get(name) is None:
            target.vertex_groups.new(name=name)

    bpy.context.view_layer.objects.active=target
    target.select_set(True)
    mod=target.modifiers.new(name="XZ_WeightTransfer",type="DATA_TRANSFER")
    mod.object=source
    mod.use_vert_data=True
    mod.data_types_verts={'VGROUP_WEIGHTS'}
    mod.vert_mapping='POLYINTERP_NEAREST'
    mod.layers_vgroup_select_src='ALL'
    mod.layers_vgroup_select_dst='NAME'
    try:
        bpy.ops.object.modifier_apply(modifier=mod.name)
    except Exception as exc:
        raise SystemExit(f"Weight transfer failed for {target.name}: {exc!r}")
    target.select_set(False)

    arm_mod=target.modifiers.new(name="XZ_Armature",type="ARMATURE")
    arm_mod.object=arm
    world=target.matrix_world.copy()
    target.parent=arm
    target.matrix_parent_inverse=arm.matrix_world.inverted()
    target.matrix_world=world

    weighted_vertices=0
    for v in target.data.vertices:
        if len(v.groups):
            weighted_vertices += 1
    transfer_report.append({
        "mesh":target.name,
        "vertices":len(target.data.vertices),
        "polygons":len(target.data.polygons),
        "vertex_groups":len(target.vertex_groups),
        "weighted_vertices":weighted_vertices,
    })
    if weighted_vertices < max(1,int(len(target.data.vertices)*0.90)):
        raise SystemExit(f"Insufficient transferred weights on {target.name}: {weighted_vertices}/{len(target.data.vertices)}")

# Capture names before deleting anything. Blender invalidates StructRNA
# object proxies immediately after bpy.data.objects.remove(), so iterating old
# object references after deletion can raise ReferenceError.
arm_name=arm.name
donor_mesh_names=[o.name for o in donor_meshes]
monja_mesh_names={o.name for o in monja_meshes}
donor_helper_names=[
    o.name for o in donor_objs
    if o.name != arm_name and o.name not in donor_mesh_names
    and o.name not in monja_mesh_names and o.type!="ARMATURE"
]

# Keep donor armature/actions, remove donor visible geometry.
for name in donor_mesh_names:
    o=bpy.data.objects.get(name)
    if o is not None:
        bpy.data.objects.remove(o,do_unlink=True)

# Remove imported donor non-armature helpers that are not needed by the exported rig.
for name in donor_helper_names:
    o=bpy.data.objects.get(name)
    if o is not None:
        bpy.data.objects.remove(o,do_unlink=True)

# Reacquire the surviving armature by name after removals to avoid stale RNA.
arm=bpy.data.objects.get(arm_name)
if arm is None or arm.type!="ARMATURE":
    raise SystemExit("Donor armature vanished during donor cleanup")

# Select exactly Monja geometry + donor armature.
bpy.ops.object.select_all(action='DESELECT')
arm.select_set(True)
for o in monja_meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active=arm

actions=[a.name for a in bpy.data.actions]
zombie_actions=[n for n in actions if n in {"Zombie_Idle_Loop","Zombie_Scratch","Zombie_Walk_Fwd_Loop"}]
if len(zombie_actions) < 3:
    # Imported GLB action names can receive armature prefixes; accept substring matches.
    zombie_actions=[n for n in actions if any(k.lower() in n.lower() for k in ("Zombie_Idle_Loop","Zombie_Scratch","Zombie_Walk_Fwd_Loop"))]
if len(zombie_actions) < 3:
    raise SystemExit(f"Required donor zombie actions missing: {actions}")

bpy.ops.export_scene.gltf(
    filepath=str(OUT_GLB),
    export_format='GLB',
    use_selection=True,
    export_animations=True,
    export_skins=True,
    export_nla_strips=True,
    export_apply=False,
)

poly_before=sum(len(o.data.polygons) for o in monja_meshes)
vert_before=sum(len(o.data.vertices) for o in monja_meshes)
size_bytes=OUT_GLB.stat().st_size
print("XZOGOT_MONJA_RIGGED_EXPORT_BYTES",size_bytes)

# Re-open the result so the gate validates the actual file Godot will ingest.
reset()
bpy.ops.import_scene.gltf(filepath=str(OUT_GLB))
out_objs=list(bpy.context.scene.objects)
out_meshes=meshes(out_objs)
out_arms=[o for o in out_objs if o.type=="ARMATURE"]
out_actions=[a.name for a in bpy.data.actions]
out_poly=sum(len(o.data.polygons) for o in out_meshes)
out_vert=sum(len(o.data.vertices) for o in out_meshes)
out_zombie=[n for n in out_actions if any(k.lower() in n.lower() for k in ("Zombie_Idle_Loop","Zombie_Scratch","Zombie_Walk_Fwd_Loop"))]

report={
    "source_monja":str(MONJA.relative_to(ROOT)),
    "donor":str(DONOR.relative_to(ROOT)),
    "source_vertices":vert_before,
    "source_polygons":poly_before,
    "output_vertices":out_vert,
    "output_polygons":out_poly,
    "polygon_conservation_ok":out_poly==poly_before,
    "armatures":len(out_arms),
    "actions":out_actions,
    "required_zombie_actions":out_zombie,
    "transfer":transfer_report,
    "output_bytes":size_bytes,
    "alignment":{
        "scale_to_donor":scale,
        "translation":[delta.x,delta.y,delta.z],
        "donor_size":[dsize.x,dsize.y,dsize.z],
        "monja_source_size":[msize.x,msize.y,msize.z],
    }
}
REPORT.write_text(json.dumps(report,indent=2),encoding="utf-8")

if not report["polygon_conservation_ok"]:
    raise SystemExit(f"Polygon conservation failed {out_poly}/{poly_before}")
if len(out_arms) < 1:
    raise SystemExit("Exported rig missing armature")
if len(out_zombie) < 3:
    raise SystemExit(f"Exported rig missing required zombie animations: {out_actions}")
if size_bytes >= 99_000_000:
    print("XZOGOT_MONJA_RIGGED_TOO_LARGE_FOR_NORMAL_GIT",size_bytes)
else:
    print("XZOGOT_MONJA_RIGGED_GIT_SIZE_OK",size_bytes)

print("XZOGOT_MONJA_RIGGED_WEIGHT_TRANSFER_GREEN",len(transfer_report))
print("XZOGOT_MONJA_RIGGED_ANIMATIONS_GREEN",out_zombie)
print("XZOGOT_MONJA_RIGGED_POLYGONS_GREEN",out_poly)
