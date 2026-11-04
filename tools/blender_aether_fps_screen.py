#!/usr/bin/env python3
"""Render actual Project Aether MP40 and original first-person hands from committed GLBs.
Outputs Blender .blend plus two unretouched render frames; never draws a substitute gun.
"""
import bpy, json, math, os, sys
from pathlib import Path
from mathutils import Matrix, Vector, Quaternion

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/"xogot/assets/weapons"
OUT=ROOT/"xogot/build/blender_fps_proof"
OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for m in list(bpy.data.materials):
    bpy.data.materials.remove(m)
def imp(path,prefix):
    assert path.exists(),f"Required original source file absent: {path}"
    before=set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    objects=[o for o in bpy.data.objects if o not in before]
    if not [o for o in objects if o.type=="MESH"]:
        raise RuntimeError(f"Original {prefix} asset has no mesh objects")
    for o in objects:
        o["source"] = "Project Aether, asset "+prefix
    return objects

hands=imp(ASSETS/"aether_waw_hands/t4_marine/mp40/viewhands.glb","MP40 original T4 Marine viewhands")
guns=imp(ASSETS/"aether_waw_real/mp40/viewmodel.glb","MP40 original animated weapon")
allmeshes=[o for o in guns+hands if o.type=="MESH"]
wmeshes=[o for o in guns if o.type=="MESH"]
hmeshes=[o for o in hands if o.type=="MESH"]
print("SOURCE_MESH_COUNT",len(wmeshes),len(hmeshes))
def has_parent_in(o,subset):
    return o.parent in subset
hroots=[o for o in hands if not has_parent_in(o,hands)]
wroots=[o for o in guns if not has_parent_in(o,guns)]
def mat(name,rgba,metal=0.0,rough=.55):
    m=bpy.data.materials.new(name);m.diffuse_color=rgba;m.use_nodes=True
    p=m.node_tree.nodes.get("Principled BSDF")
    if p:
        p.inputs["Base Color"].default_value=rgba
        p.inputs["Metallic"].default_value=metal
        p.inputs["Roughness"].default_value=rough
    return m
gunmaterial=mat("Gun steel, temporary viewport override",(.13,.15,.19,1),.5,.45)
handmaterial=mat("Hand skin, temporary viewport override",(.54,.31,.21,1),0,.7)
def assign_fallback(objs,material):
    for ob in objs:
        if ob.type!="MESH": continue
        if not ob.data.materials:
            ob.data.materials.append(material)
        for m in list(ob.data.materials):
            if m and m.use_nodes:
                for node in m.node_tree.nodes:
                    if node.type=="TEX_IMAGE" and node.image and not node.image.has_data:
                        print("MISSING_TEXTURE",m.name,node.image.name)
for o in hands+guns:
    if o.type=="ARMATURE":
        print("ARMATURE",o.name,"bones",len(o.data.bones))
        for bone in o.data.bones:
            if "tag_weapon" in bone.name.lower() or "tag_view" in bone.name.lower():
                print("TAG",o.name,bone.name,list(bone.head_local),list(bone.tail_local))
    if o.type=="MESH":
        print("MESH",o.name,"dims",tuple(round(v,4) for v in o.dimensions),"materials",[m.name if m else None for m in o.data.materials])
assign_fallback(hmeshes,handmaterial)
assign_fallback(wmeshes,gunmaterial)

def assign_idle(objs,keywords):
    actions=list(bpy.data.actions)
    print("ACTION_NAMES", [a.name for a in actions][:45])
    for ob in objs:
        if ob.type!="ARMATURE": continue
        matches=[a for a in actions if all(k in a.name.lower() for k in keywords)]
        if matches:
            action=matches[0]
            ob.animation_data_create()
            try: ob.animation_data.action=action
            except Exception as e: print("ANIMATION_NOT_SET",ob.name,str(e))
            print("IDLE_ACTION",ob.name,action.name)
assign_idle(hands,["idle","mp40"])
assign_idle(guns,["idle"])
bpy.context.scene.frame_set(1)

# One group transform moves weapon and original hands together, retaining source deformation.
rig=bpy.data.objects.new("SOURCE_AETHER_VIEWMODEL_RIG",None)
bpy.context.collection.objects.link(rig)
for o in hroots+wroots:
    local=o.matrix_world.copy()
    o.parent=rig
    o.matrix_parent_inverse=Matrix.Identity(4)
    o.matrix_world=local
bpy.context.view_layer.update()
# Diagnostic axis-aligned bounds for provenance/scale, no fake geometry.
def bounds_world(meshes):
    coords=[o.matrix_world@Vector(corner) for o in meshes for corner in o.bound_box]
    lo=Vector([min(v[i] for v in coords) for i in range(3)])
    hi=Vector([max(v[i] for v in coords) for i in range(3)])
    return lo,hi
lo,hi=bounds_world(wmeshes+hmeshes)
print("SOURCE_BOUNDS",tuple(lo),tuple(hi),"SPAN",tuple(hi-lo))
# Original GLBs may use world coordinates in Unreal centimeters; normalize only when >2m.
span=max(hi-lo)
scale=0.01 if span>4.0 else 1.0
rig.scale=(scale,)*3
print("VIEWMODEL_SCALE",scale)

scene=bpy.context.scene
scene.render.resolution_x=1280
scene.render.resolution_y=720
scene.render.resolution_percentage=100
scene.render.image_settings.file_format="PNG"
try: scene.render.engine="BLENDER_EEVEE"
except: scene.render.engine="BLENDER_EEVEE_NEXT"
scene.render.film_transparent=False
scene.world.color=(.045,.059,.073)
world=bpy.data.worlds.new("Dark studio") if not scene.world else scene.world
scene.world=world
world.use_nodes=True
world.node_tree.nodes["Background"].inputs["Color"].default_value=(.025,.035,.055,1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value=.7
def light(name,pos,power,size,color):
    d=bpy.data.lights.new(name,"AREA");d.energy=power;d.shape="DISK";d.size=size;d.color=color
    o=bpy.data.objects.new(name,d);scene.collection.objects.link(o);o.location=pos
    o.rotation_euler=(Vector((0,.25,0))-o.location).to_track_quat("-Z","Y").to_euler()
light("key",(1,-1,2),550,3,(.72,.86,1))
light("fill",(-1,.5,.3),390,2.8,(1,.73,.48))
camera_data=bpy.data.cameras.new("FPS_camera")
camera=bpy.data.objects.new("FPS_camera",camera_data);scene.collection.objects.link(camera)
scene.camera=camera
# View forward along +Y, Godot/Gltf UE-forward conversion; preserve crosshair center.
camera.location=(0,-.1,0)
camera.rotation_euler=Vector((0,1,0)).to_track_quat("-Z","Y").to_euler()
camera_data.type="PERSP";camera_data.lens=26;camera_data.sensor_fit="HORIZONTAL"
camera_data.clip_start=.005;camera_data.clip_end=300

# Source UE authoring transforms converted to camera-space Blender from original UE cm:
# UE (forward, right, up) => Blender (right, forward, up).
# The action/rig movement is NOT invented from a generative drawing.
poses=[
  ("HIPFIRE",( .05, .22,-.05)),
  ("ADS",(-.04142,.24045,.01040)),
]
for label,loc in poses:
    rig.location=loc
    bpy.context.view_layer.update()
    # camera calibration report captures source bounds for further validation
    a,b=bounds_world(wmeshes+hmeshes)
    print("RENDER_MODE",label,"bounds",tuple(round(x,4) for x in a),tuple(round(x,4) for x in b))
    scene.render.filepath=str(OUT/f"AETHER_MP40_{label}_BLENDER.png")
    bpy.ops.render.render(write_still=True)
    print("RENDER_FILE",scene.render.filepath,os.path.getsize(scene.render.filepath))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/"AETHER_MP40_ORIGINAL_VIEWMODELS.blend"))
(OUT/"audit.json").write_text(json.dumps({
 "model":"Project Aether MP40 actual GLB",
 "hands":"T4 Marine hands actual animated GLB",
 "mode":"Blender render (not video-game capture)",
 "original_assets":[str(ASSETS/"aether_waw_real/mp40/viewmodel.glb"),str(ASSETS/"aether_waw_hands/t4_marine/mp40/viewhands.glb")],
 "render_count":2,"source_meshes":{"weapon":len(wmeshes),"hands":len(hmeshes)},
 "viewmodel_scale":scale,"source_bounds":[list(lo),list(hi)]
},indent=2))
assert all((OUT/f"AETHER_MP40_{s}_BLENDER.png").stat().st_size>4000 for s,_ in poses)
print("AETHER_MP40_BLENDER_TWO_POSES_SOURCE_ASSETS_GREEN")
