#!/usr/bin/env python3
"""Visual/kinematic gate for REAL NZP->Aether hybrid MP40, never ships assets.

Executed on the intermediate hybrid .blend generated from the original
NZ:P authoring rig + imported high-detail Aether gun.
Detects static gun/clip/reload and reports frame-by-frame pose/world bounds.
Saves a native Blender PNG contact sheet input (3 separate frame renders);
does NOT pretend that screenshots alone certify Android placement.
"""
import bpy, json, math, sys
from pathlib import Path
from mathutils import Vector

args = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
if len(args) != 1:
    raise SystemExit("Expected <output-dir> after --")
output=Path(args[0]).resolve()
output.mkdir(parents=True,exist_ok=True)

gun=bpy.data.objects.get("Aether_HD_MP40_On_Vril_Rig")
hands=bpy.data.objects.get("NZP_Original_Animated_Hands_ONLY")
if gun is None or hands is None:
    raise SystemExit("MP40_VISUAL_RED hybrid gun/hands not present")
rig=next((m.object for m in gun.modifiers if m.type=="ARMATURE"),None)
if rig is None:
    raise SystemExit("MP40_VISUAL_RED no stock armature")
original_actions=[{"name":a.name,"length":list(a.frame_range)} for a in bpy.data.actions]
active=rig.animation_data.action if rig.animation_data else None
nla_tracks=rig.animation_data.nla_tracks if rig.animation_data else []
print("MP40_VISUAL_RIG",rig.name,"active",active.name if active else None,
      "NLA",len(nla_tracks),"actions",json.dumps(original_actions))

def get_points(obj):
    deps=bpy.context.evaluated_depsgraph_get()
    evaluated=obj.evaluated_get(deps)
    mesh=evaluated.to_mesh()
    result=[evaluated.matrix_world@v.co.copy() for v in mesh.vertices]
    evaluated.to_mesh_clear()
    return result

def bounds(vectors):
    lo=[min(p[i] for p in vectors) for i in range(3)]
    hi=[max(p[i] for p in vectors) for i in range(3)]
    return {"lo":lo,"hi":hi,"center":[(a+b)*0.5 for a,b in zip(lo,hi)],
            "span":[b-a for a,b in zip(lo,hi)]}

def centroid(vectors):
    return sum(vectors,Vector())/max(1,len(vectors))

scene=bpy.context.scene
original_frame=scene.frame_current
frames=[1,4,7,17,25,31,39,41,46,60,83]
samples={}
ref=None
movement={}
for frame in frames:
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    gp=get_points(gun)
    hp=get_points(hands)
    record={"gun":bounds(gp),"hands":bounds(hp),"gun_centroid":list(centroid(gp)),
            "hands_centroid":list(centroid(hp))}
    for bone in ("Body","Slide","Clip"):
        if bone not in rig.pose.bones: raise SystemExit("MP40_VISUAL_RED missing "+bone)
        record[bone+"_bone_position"]=list(rig.matrix_world @ rig.pose.bones[bone].head)
    samples[str(frame)]=record
    if ref is None: ref=record

for key in ("gun_centroid","hands_centroid","Body_bone_position","Slide_bone_position","Clip_bone_position"):
    baseline=Vector(ref[key])
    movement[key]=max((Vector(r[key])-baseline).length for r in samples.values())
    print("MP40_VISUAL_BONE_MOVEMENT",key,movement[key])
if not movement["hands_centroid"]>0.0001:
    print("MP40_VISUAL_WARNING: hands centroid static under global timeline; may use action switch")
if not (movement["Slide_bone_position"]>0.0001 or movement["Clip_bone_position"]>0.0001):
    print("MP40_VISUAL_WARNING: bolt and magazine not moving on global timeline; action mapping required")

scene.frame_set(original_frame)
bpy.context.view_layer.update()

# Cosmetic rig comparison still requires camera-view rendering and approval.
# Set repeatable true first-person-side diagnostic angles, hide authoring
# helpers so source obsolete gun does not contaminate the screenshot.
for ob in bpy.data.objects:
    if ob.name in ("Aether_HD_MP40_On_Vril_Rig","NZP_Original_Animated_Hands_ONLY"):
        ob.hide_render=False
    elif ob.type in {"MESH","EMPTY"}:
        ob.hide_render=True
rig.hide_render=True

from mathutils import Euler
camera_data=bpy.data.cameras.new("MP40_AUDIT_CAMERA")
camera=bpy.data.objects.new("MP40_AUDIT_CAMERA",camera_data)
scene.collection.objects.link(camera)
scene.camera=camera
camera_data.type="ORTHO"
scene.render.engine="BLENDER_EEVEE"
scene.render.resolution_x=1100
scene.render.resolution_y=680
scene.render.resolution_percentage=100
scene.render.image_settings.file_format="PNG"
scene.render.film_transparent=False
scene.world.color=(0.12,0.12,0.12)
scene.world.use_nodes=True
background=scene.world.node_tree.nodes.get("Background")
if background is not None:
    background.inputs["Color"].default_value=(0.15,0.15,0.15,1.0)
    background.inputs["Strength"].default_value=1.2
scene.view_settings.view_transform="Standard"
scene.view_settings.exposure=1.35
scene.view_settings.gamma=1.0
amb=bpy.data.lights.new("MP40_AUDIT_KEY",type="AREA")
amb.energy=1600
amb.shape="DISK"
amb.size=8
light=bpy.data.objects.new("MP40_AUDIT_KEY",amb)
scene.collection.objects.link(light)
gu=Vector(samples["1"]["gun"]["center"])
sp=Vector(samples["1"]["gun"]["span"])
center=gu
camera_data.ortho_scale=max(0.2,max(sp)*1.7)
camera.location=center+Vector((max(sp)*1.4,-max(sp)*1.7,max(sp)*1.3))
direction=center-camera.location
camera.rotation_euler=direction.to_track_quat("-Z","Y").to_euler()
light.location=center+Vector((max(sp)*1.2,max(sp)*2,max(sp)*2))
light.rotation_euler=(center-light.location).to_track_quat("-Z","Y").to_euler()
for frame in (1,17,31):
    scene.frame_set(frame)
    scene.render.filepath=str(output/f"hybrid_mp40_frame_{frame:02d}.png")
    bpy.ops.render.render(write_still=True)

report={"schema":1,
        "real_hybrid_in_blender":True,
        "stock_rig":rig.name,
        "stock_global_action":active.name if active else None,
        "stock_nla_tracks":len(nla_tracks),
        "action_inventory":original_actions,
        "sampled_frames":samples,
        "frame_movement":movement,
        "visual_preview_png":[f"hybrid_mp40_frame_{f:02d}.png" for f in (1,17,31)],
        "model_mdl_created":False,"phone_apk_created":False,
        "visual_alignment_verified_by_human":False,
        "ready_to_distribute":False}
(output/"hybrid-visual-kinematic-report.json").write_text(json.dumps(report,indent=2))
print("MP40_REAL_HYBRID_THREE_FRAME_RENDERED_GREEN")
print("MP40_ORIGINAL_RIG_MOTION_DIAGNOSTIC_COMPLETE")
print("MP40_ANDROID_NOT_SHIPPABLE_UNTIL_ALIGNMENT_AND_ANIM_MAPPING")
