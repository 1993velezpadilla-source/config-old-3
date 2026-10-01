import bpy
import json
import math
import os
from pathlib import Path
from mathutils import Vector

OUT = Path(os.environ.get("SANCTUM_V2_PROBE_OUT", "sanctum-v2-probe"))
OUT.mkdir(parents=True, exist_ok=True)

TARGET_NAME = "Catehdral"

def get_target():
    obj = bpy.data.objects.get(TARGET_NAME)
    if obj is None:
        raise SystemExit(f"Missing upstream cathedral object {TARGET_NAME!r}")
    return obj

def evaluated_mesh_stats(obj):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    mesh = ev.to_mesh()
    try:
        verts = [ev.matrix_world @ v.co for v in mesh.vertices]
        if not verts:
            raise SystemExit("Cathedral evaluated mesh has no vertices")
        mn = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
        mx = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
        return {
            "vertices": len(mesh.vertices),
            "polygons": len(mesh.polygons),
            "center": list((mn+mx)*0.5),
            "min": list(mn),
            "max": list(mx),
            "size": list(mx-mn),
        }
    finally:
        ev.to_mesh_clear()

def ensure_cam(scene):
    data=bpy.data.cameras.get("SANCTUM_V2_PROBE_CAMERA_DATA") or bpy.data.cameras.new("SANCTUM_V2_PROBE_CAMERA_DATA")
    cam=bpy.data.objects.get("SANCTUM_V2_PROBE_CAMERA") or bpy.data.objects.new("SANCTUM_V2_PROBE_CAMERA",data)
    if cam.name not in scene.collection.objects:
        try: scene.collection.objects.link(cam)
        except RuntimeError: pass
    scene.camera=cam
    cam.data.lens=38
    return cam

def point(cam, target):
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat("-Z","Y").to_euler()

def ensure_world(scene):
    if scene.world is None:
        scene.world=bpy.data.worlds.new("SANCTUM_V2_PROBE_WORLD")
    scene.world.use_nodes=True
    bg=scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value=(0.035,0.04,0.055,1)
        bg.inputs["Strength"].default_value=0.55

def ensure_lights(scene, center, size):
    lights=[]
    configs=[
        ("KEY", Vector((0.7,-0.8,1.1)), 2400, max(size.x,size.y,size.z)*0.5),
        ("FILL", Vector((-0.8,0.2,0.65)), 1400, max(size.x,size.y,size.z)*0.7),
        ("RIM", Vector((0.1,0.8,1.3)), 1800, max(size.x,size.y,size.z)*0.45),
    ]
    ext=max(size.x,size.y,size.z)
    for name,off,energy,area in configs:
        ld=bpy.data.lights.get(f"SANCTUM_V2_{name}_DATA") or bpy.data.lights.new(f"SANCTUM_V2_{name}_DATA","AREA")
        lo=bpy.data.objects.get(f"SANCTUM_V2_{name}") or bpy.data.objects.new(f"SANCTUM_V2_{name}",ld)
        if lo.name not in scene.collection.objects:
            try: scene.collection.objects.link(lo)
            except RuntimeError: pass
        lo.location=center+off*ext
        ld.energy=energy
        ld.shape="DISK"
        ld.size=max(area,2.0)
        lo.rotation_euler=(center-lo.location).to_track_quat("-Z","Y").to_euler()
        lights.append(lo)
    return lights

def isolate(scene, target, cam, lights):
    for o in scene.objects:
        if hasattr(o,"hide_render"):
            o.hide_render = o not in [target,cam,*lights]
    target.hide_render=False

def render(scene, cam, name, pos, target):
    cam.location=Vector(pos)
    point(cam,target)
    scene.render.filepath=str(OUT/name)
    bpy.ops.render.render(write_still=True)

scene=bpy.context.scene
target=get_target()
stats=evaluated_mesh_stats(target)
center=Vector(stats["center"])
mn=Vector(stats["min"])
mx=Vector(stats["max"])
size=Vector(stats["size"])

scene.render.engine="BLENDER_EEVEE"
scene.render.image_settings.media_type="IMAGE"
scene.render.image_settings.file_format="PNG"
scene.render.resolution_x=1280
scene.render.resolution_y=800
scene.render.resolution_percentage=100
ensure_world(scene)
cam=ensure_cam(scene)
lights=ensure_lights(scene,center,size)
isolate(scene,target,cam,lights)

# Existing authored cathedral only. These are review cameras, not geometry changes.
ext=max(size.x,size.y,size.z)
render(scene,cam,"01-exterior-front-3q.png", center+Vector((ext*0.9,-ext*0.9,ext*0.55)), center+Vector((0,0,size.z*0.05)))
render(scene,cam,"02-exterior-rear-3q.png", center+Vector((-ext*0.9,ext*0.9,ext*0.5)), center)
render(scene,cam,"03-exterior-side.png", center+Vector((ext*1.15,0,ext*0.3)), center)

# Interior probes: sample points along the authored bounding volume. No mesh edits.
interior_z=mn.z+max(1.7,size.z*0.08)
interior_points=[
    ("04-interior-center.png", Vector((center.x,center.y,interior_z)), Vector((center.x,center.y+min(size.y*0.3,8.0),interior_z+1.0))),
    ("05-interior-nave-a.png", Vector((center.x,center.y-size.y*0.18,interior_z)), Vector((center.x,center.y+size.y*0.25,interior_z+1.0))),
    ("06-interior-nave-b.png", Vector((center.x,center.y+size.y*0.18,interior_z)), Vector((center.x,center.y-size.y*0.25,interior_z+1.0))),
]
for name,pos,look in interior_points:
    render(scene,cam,name,pos,look)

# Export untouched evaluated cathedral as GLB candidate.
for o in bpy.context.selected_objects:
    o.select_set(False)
target.select_set(True)
bpy.context.view_layer.objects.active=target
glb=OUT/"upstream-cathedral-candidate.glb"
bpy.ops.export_scene.gltf(
    filepath=str(glb),
    export_format="GLB",
    use_selection=True,
    export_apply=True,
)

report={
    "source_object":target.name,
    "geometry_nodes":[m.node_group.name for m in target.modifiers if m.type=="NODES" and m.node_group],
    "stats":stats,
    "renders":[
        "01-exterior-front-3q.png","02-exterior-rear-3q.png","03-exterior-side.png",
        "04-interior-center.png","05-interior-nave-a.png","06-interior-nave-b.png"
    ],
    "glb":glb.name,
    "glb_bytes":glb.stat().st_size,
}
(OUT/"probe-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("SANCTUM_V2_CATHEDRAL_PROBE_OK")
print(json.dumps(report,indent=2))
