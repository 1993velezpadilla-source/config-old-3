import bpy
import json
import math
import os
from pathlib import Path
from mathutils import Vector

OUT = Path(os.environ.get("SANCTUM_V2_MATERIAL_OUT", "sanctum-v2-material-probe"))
ASSETS = Path(os.environ.get("SANCTUM_V2_POLYHAVEN_DIR", "polyhaven-assets"))
OUT.mkdir(parents=True, exist_ok=True)

TARGET_NAME = "Catehdral"
REQUIRED_MATERIALS = {"GroundFloorWalls", "FakeRoof", "BeamFakeTextureVertical"}

def image_node(nodes, path, noncolor=False):
    img = bpy.data.images.load(str(path), check_existing=True)
    if noncolor:
        img.colorspace_settings.name = "Non-Color"
    n = nodes.new("ShaderNodeTexImage")
    n.image = img
    n.extension = "REPEAT"
    return n

def build_pbr_material(mat, diffuse, roughness, normal):
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    tex = image_node(nodes, diffuse, False)
    rough = image_node(nodes, roughness, True)
    norm_tex = image_node(nodes, normal, True)
    norm = nodes.new("ShaderNodeNormalMap")

    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(rough.outputs["Color"], bsdf.inputs["Roughness"])
    links.new(norm_tex.outputs["Color"], norm.inputs["Color"])
    links.new(norm.outputs["Normal"], bsdf.inputs["Normal"])
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

def replace_upstream_materials():
    mats = {m.name: m for m in bpy.data.materials}
    missing = sorted(REQUIRED_MATERIALS - set(mats))
    if missing:
        raise SystemExit(f"Missing expected upstream materials: {missing}; available={sorted(mats)}")

    build_pbr_material(
        mats["GroundFloorWalls"],
        ASSETS/"stone_wall_04"/"diffuse.png",
        ASSETS/"stone_wall_04"/"rough.png",
        ASSETS/"stone_wall_04"/"normal_gl.png",
    )
    build_pbr_material(
        mats["BeamFakeTextureVertical"],
        ASSETS/"stone_wall_04"/"diffuse.png",
        ASSETS/"stone_wall_04"/"rough.png",
        ASSETS/"stone_wall_04"/"normal_gl.png",
    )
    build_pbr_material(
        mats["FakeRoof"],
        ASSETS/"roof_slates_03"/"diffuse.png",
        ASSETS/"roof_slates_03"/"rough.png",
        ASSETS/"roof_slates_03"/"normal_gl.png",
    )

def evaluated_stats(obj):
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
            "uv_layers": len(mesh.uv_layers),
        }
    finally:
        ev.to_mesh_clear()

def ensure_cam(scene):
    data = bpy.data.cameras.get("SANCTUM_V2_MATERIAL_CAMERA_DATA") or bpy.data.cameras.new("SANCTUM_V2_MATERIAL_CAMERA_DATA")
    cam = bpy.data.objects.get("SANCTUM_V2_MATERIAL_CAMERA") or bpy.data.objects.new("SANCTUM_V2_MATERIAL_CAMERA", data)
    if cam.name not in scene.collection.objects:
        scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.lens = 38
    return cam

def point(cam, target):
    cam.rotation_euler = (Vector(target)-cam.location).to_track_quat("-Z","Y").to_euler()

def setup_hdri(scene):
    world = scene.world or bpy.data.worlds.new("SANCTUM_V2_POLYHAVEN_WORLD")
    scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputWorld")
    bg = nodes.new("ShaderNodeBackground")
    env = nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(str(ASSETS/"graaff_reinet_groote_kerk"/"church_4k.hdr"), check_existing=True)
    bg.inputs["Strength"].default_value = 0.38
    links.new(env.outputs["Color"], bg.inputs["Color"])
    links.new(bg.outputs["Background"], out.inputs["Surface"])

def isolate(scene, target, cam):
    for o in scene.objects:
        if hasattr(o, "hide_render"):
            o.hide_render = o not in (target, cam)
    target.hide_render = False
    cam.hide_render = False

def render(scene, cam, name, pos, look):
    cam.location = Vector(pos)
    point(cam, look)
    scene.render.filepath = str(OUT/name)
    bpy.ops.render.render(write_still=True)

scene = bpy.context.scene
target = bpy.data.objects.get(TARGET_NAME)
if target is None:
    raise SystemExit(f"Missing upstream cathedral object {TARGET_NAME!r}")

replace_upstream_materials()
stats = evaluated_stats(target)
if stats["uv_layers"] < 1:
    raise SystemExit(f"Upstream cathedral has no UVs: {stats}")

scene.render.engine = "BLENDER_EEVEE"
scene.render.image_settings.media_type = "IMAGE"
scene.render.image_settings.file_format = "PNG"
scene.render.resolution_x = 1280
scene.render.resolution_y = 800
scene.render.resolution_percentage = 100
setup_hdri(scene)
cam = ensure_cam(scene)
isolate(scene, target, cam)

center = Vector(stats["center"])
mn = Vector(stats["min"])
size = Vector(stats["size"])
ext = max(size.x, size.y, size.z)
interior_z = mn.z + max(1.7, size.z*0.08)

views = [
    ("01-exterior-front-3q.png", center+Vector((ext*0.9,-ext*0.9,ext*0.55)), center+Vector((0,0,size.z*0.05))),
    ("02-exterior-rear-3q.png", center+Vector((-ext*0.9,ext*0.9,ext*0.5)), center),
    ("03-exterior-side.png", center+Vector((ext*1.15,0,ext*0.3)), center),
    ("04-interior-center.png", Vector((center.x,center.y,interior_z)), Vector((center.x,center.y+min(size.y*0.3,8.0),interior_z+1.0))),
    ("05-interior-nave-a.png", Vector((center.x,center.y-size.y*0.18,interior_z)), Vector((center.x,center.y+size.y*0.25,interior_z+1.0))),
    ("06-interior-nave-b.png", Vector((center.x,center.y+size.y*0.18,interior_z)), Vector((center.x,center.y-size.y*0.25,interior_z+1.0))),
]
for name, pos, look in views:
    render(scene, cam, name, pos, look)

report = {
    "source_object": target.name,
    "geometry_nodes": [m.node_group.name for m in target.modifiers if m.type=="NODES" and m.node_group],
    "stats": stats,
    "material_replacements": {
        "GroundFloorWalls": "Poly Haven stone_wall_04 4K CC0",
        "BeamFakeTextureVertical": "Poly Haven stone_wall_04 4K CC0",
        "FakeRoof": "Poly Haven roof_slates_03 4K CC0",
    },
    "lighting": "Poly Haven graaff_reinet_groote_kerk 4K HDR CC0",
    "renders": [v[0] for v in views],
}
(OUT/"material-probe-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("SANCTUM_V2_POLYHAVEN_4K_PROBE_OK")
print(json.dumps(report, indent=2))
