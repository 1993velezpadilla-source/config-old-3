import bpy
import json
import os
from pathlib import Path
from mathutils import Vector

OUT = Path(os.environ.get("SANCTUM_V2_MATERIAL_ID_OUT", "sanctum-v2-material-id"))
OUT.mkdir(parents=True, exist_ok=True)
TARGET_NAME = "Catehdral"

PALETTE = {
    "GroundFloorWalls": (0.90, 0.16, 0.12, 1.0),
    "FakeRoof": (0.12, 0.55, 0.92, 1.0),
    "RoundWindwos": (0.22, 0.80, 0.30, 1.0),
    "BeamFakeTextureVertical": (0.95, 0.72, 0.12, 1.0),
    "Copper": (0.72, 0.28, 0.88, 1.0),
    "<None>": (0.55, 0.55, 0.55, 1.0),
}

def evaluated_stats(obj):
    deps=bpy.context.evaluated_depsgraph_get()
    ev=obj.evaluated_get(deps)
    mesh=ev.to_mesh()
    try:
        verts=[ev.matrix_world @ v.co for v in mesh.vertices]
        mn=Vector((min(v.x for v in verts),min(v.y for v in verts),min(v.z for v in verts)))
        mx=Vector((max(v.x for v in verts),max(v.y for v in verts),max(v.z for v in verts)))
        return {"center":list((mn+mx)*0.5),"min":list(mn),"max":list(mx),"size":list(mx-mn)}
    finally:
        ev.to_mesh_clear()

def ensure_cam(scene):
    data=bpy.data.cameras.get("SANCTUM_V2_MATERIAL_ID_CAMERA_DATA") or bpy.data.cameras.new("SANCTUM_V2_MATERIAL_ID_CAMERA_DATA")
    cam=bpy.data.objects.get("SANCTUM_V2_MATERIAL_ID_CAMERA") or bpy.data.objects.new("SANCTUM_V2_MATERIAL_ID_CAMERA",data)
    if cam.name not in scene.collection.objects:
        scene.collection.objects.link(cam)
    scene.camera=cam
    cam.data.lens=38
    return cam

def point(cam,target):
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat("-Z","Y").to_euler()

def make_emission(mat,color):
    if mat is None:
        return
    mat.use_nodes=True
    nodes=mat.node_tree.nodes
    links=mat.node_tree.links
    nodes.clear()
    out=nodes.new("ShaderNodeOutputMaterial")
    em=nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value=color
    em.inputs["Strength"].default_value=1.0
    links.new(em.outputs["Emission"],out.inputs["Surface"])

scene=bpy.context.scene
target=bpy.data.objects.get(TARGET_NAME)
if target is None:
    raise SystemExit(f"Missing upstream cathedral object {TARGET_NAME!r}")

# Replace only shader appearance for diagnostic rendering; geometry remains untouched.
for mat in bpy.data.materials:
    if mat.name in PALETTE:
        make_emission(mat,PALETTE[mat.name])

stats=evaluated_stats(target)
center=Vector(stats["center"])
mn=Vector(stats["min"])
size=Vector(stats["size"])
ext=max(size.x,size.y,size.z)

scene.render.engine="BLENDER_EEVEE"
scene.render.image_settings.media_type="IMAGE"
scene.render.image_settings.file_format="PNG"
scene.render.resolution_x=1280
scene.render.resolution_y=800
scene.render.resolution_percentage=100

if scene.world is None:
    scene.world=bpy.data.worlds.new("SANCTUM_V2_MATERIAL_ID_WORLD")
scene.world.use_nodes=True
bg=scene.world.node_tree.nodes.get("Background")
if bg:
    bg.inputs["Color"].default_value=(0.02,0.02,0.02,1)
    bg.inputs["Strength"].default_value=0.05

cam=ensure_cam(scene)
for o in scene.objects:
    if hasattr(o,"hide_render"):
        o.hide_render=o not in (target,cam)
target.hide_render=False
cam.hide_render=False

interior_z=mn.z+max(1.7,size.z*0.08)
views=[
    ("01-exterior-front-3q.png",center+Vector((ext*0.9,-ext*0.9,ext*0.55)),center+Vector((0,0,size.z*0.05))),
    ("02-exterior-rear-3q.png",center+Vector((-ext*0.9,ext*0.9,ext*0.5)),center),
    ("03-exterior-side.png",center+Vector((ext*1.15,0,ext*0.3)),center),
    ("04-interior-center.png",Vector((center.x,center.y,interior_z)),Vector((center.x,center.y+min(size.y*0.3,8.0),interior_z+1.0))),
    ("05-interior-nave-a.png",Vector((center.x,center.y-size.y*0.18,interior_z)),Vector((center.x,center.y+size.y*0.25,interior_z+1.0))),
    ("06-interior-nave-b.png",Vector((center.x,center.y+size.y*0.18,interior_z)),Vector((center.x,center.y-size.y*0.25,interior_z+1.0))),
]
for name,pos,look in views:
    cam.location=Vector(pos)
    point(cam,look)
    scene.render.filepath=str(OUT/name)
    bpy.ops.render.render(write_still=True)

report={"source_object":target.name,"palette":{k:list(v) for k,v in PALETTE.items()},"renders":[v[0] for v in views]}
(OUT/"material-id-map.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("SANCTUM_V2_MATERIAL_ID_OK")
print(json.dumps(report,indent=2))
