import bpy
import json
import math
import os
from pathlib import Path
from mathutils import Vector

OUT=Path(os.environ.get("SANCTUM_V2_RELIEF_OUT","sanctum-v2-relief-glass"))
ASSETS=Path(os.environ.get("SANCTUM_V2_RELIEF_ASSETS","sanctum-v2-relief-assets"))
MANIFEST=ASSETS/"SOURCE_MANIFEST.json"
OUT.mkdir(parents=True,exist_ok=True)

TARGET="Catehdral"
UV_NAME="UVMap"
REQUIRED={"GroundFloorWalls","FakeRoof","BeamFakeTextureVertical","RoundWindwos"}

def load_manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))

def tile_meters(manifest,asset):
    dims=manifest["polyhaven"][asset]["dimensions_mm"]
    vals=[float(v)/1000.0 for v in dims[:2] if float(v)>0]
    if len(vals)<2:
        raise SystemExit(f"Missing 2D physical dimensions for {asset}: {dims}")
    return math.sqrt(vals[0]*vals[1])

def load_image(path,noncolor=False):
    img=bpy.data.images.load(str(path),check_existing=True)
    if noncolor:
        img.colorspace_settings.name="Non-Color"
    return img

def box_tex(nodes,img):
    n=nodes.new("ShaderNodeTexImage")
    n.image=img
    n.extension="REPEAT"
    n.projection="BOX"
    n.projection_blend=0.2
    return n

def build_relief_box_material(mat,diffuse,roughness,displacement,tile_m,resolution):
    mat.use_nodes=True
    nodes=mat.node_tree.nodes
    links=mat.node_tree.links
    nodes.clear()

    out=nodes.new("ShaderNodeOutputMaterial")
    bsdf=nodes.new("ShaderNodeBsdfPrincipled")
    texcoord=nodes.new("ShaderNodeTexCoord")
    mapping=nodes.new("ShaderNodeMapping")

    repeat=1.0/tile_m
    mapping.inputs["Scale"].default_value=(repeat,repeat,repeat)

    diff=box_tex(nodes,load_image(diffuse,False))
    rough=box_tex(nodes,load_image(roughness,True))
    disp=box_tex(nodes,load_image(displacement,True))
    bump=nodes.new("ShaderNodeBump")

    # Physical, data-derived bump distance: one source texel in world units.
    bump.inputs["Distance"].default_value=tile_m/float(resolution)

    links.new(texcoord.outputs["Object"],mapping.inputs["Vector"])
    for n in (diff,rough,disp):
        links.new(mapping.outputs["Vector"],n.inputs["Vector"])

    links.new(diff.outputs["Color"],bsdf.inputs["Base Color"])
    links.new(rough.outputs["Color"],bsdf.inputs["Roughness"])
    links.new(disp.outputs["Color"],bump.inputs["Height"])
    links.new(bump.outputs["Normal"],bsdf.inputs["Normal"])
    links.new(bsdf.outputs["BSDF"],out.inputs["Surface"])

def apply_stained_glass_seamless(mat,image_path):
    if not mat.use_nodes or not mat.node_tree:
        raise SystemExit("RoundWindwos has no authored node tree to preserve")
    nodes=mat.node_tree.nodes
    links=mat.node_tree.links
    bsdfs=[n for n in nodes if n.bl_idname=="ShaderNodeBsdfPrincipled"]
    if not bsdfs:
        raise SystemExit("RoundWindwos has no Principled BSDF")
    img=load_image(image_path,False)
    if tuple(img.size)!=(1024,1024):
        raise SystemExit(f"Unexpected seamless stained-glass dimensions: {tuple(img.size)}")

    uv=nodes.new("ShaderNodeUVMap")
    uv.uv_map=UV_NAME
    mapping=nodes.new("ShaderNodeMapping")
    # Source author explicitly recommends repeating this seamless texture 2x-4x.
    mapping.inputs["Scale"].default_value=(2.0,2.0,2.0)

    tex=nodes.new("ShaderNodeTexImage")
    tex.image=img
    tex.extension="REPEAT"
    tex.projection="FLAT"

    links.new(uv.outputs["UV"],mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"],tex.inputs["Vector"])
    for bsdf in bsdfs:
        links.new(tex.outputs["Color"],bsdf.inputs["Base Color"])

def evaluated_stats(obj):
    deps=bpy.context.evaluated_depsgraph_get()
    ev=obj.evaluated_get(deps)
    mesh=ev.to_mesh()
    try:
        verts=[ev.matrix_world@v.co for v in mesh.vertices]
        mn=Vector((min(v.x for v in verts),min(v.y for v in verts),min(v.z for v in verts)))
        mx=Vector((max(v.x for v in verts),max(v.y for v in verts),max(v.z for v in verts)))
        return {
            "vertices":len(mesh.vertices),
            "polygons":len(mesh.polygons),
            "uv_layers":[x.name for x in mesh.uv_layers],
            "center":list((mn+mx)*0.5),
            "min":list(mn),
            "max":list(mx),
            "size":list(mx-mn),
        }
    finally:
        ev.to_mesh_clear()

def ensure_cam(scene):
    data=bpy.data.cameras.get("SANCTUM_V2_RELIEF_CAMERA_DATA") or bpy.data.cameras.new("SANCTUM_V2_RELIEF_CAMERA_DATA")
    cam=bpy.data.objects.get("SANCTUM_V2_RELIEF_CAMERA") or bpy.data.objects.new("SANCTUM_V2_RELIEF_CAMERA",data)
    if cam.name not in scene.collection.objects:
        scene.collection.objects.link(cam)
    scene.camera=cam
    cam.data.lens=38
    return cam

def point(cam,target):
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat("-Z","Y").to_euler()

def ensure_world(scene):
    if scene.world is None:
        scene.world=bpy.data.worlds.new("SANCTUM_V2_RELIEF_WORLD")
    scene.world.use_nodes=True
    bg=scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value=(0.035,0.04,0.055,1)
        bg.inputs["Strength"].default_value=0.55

def ensure_lights(scene,center,size):
    lights=[]
    ext=max(size.x,size.y,size.z)
    configs=[
        ("KEY",Vector((0.7,-0.8,1.1)),2400,ext*0.5),
        ("FILL",Vector((-0.8,0.2,0.65)),1400,ext*0.7),
        ("RIM",Vector((0.1,0.8,1.3)),1800,ext*0.45),
    ]
    for name,off,energy,area in configs:
        ld=bpy.data.lights.get(f"SANCTUM_V2_RELIEF_{name}_DATA") or bpy.data.lights.new(f"SANCTUM_V2_RELIEF_{name}_DATA","AREA")
        lo=bpy.data.objects.get(f"SANCTUM_V2_RELIEF_{name}") or bpy.data.objects.new(f"SANCTUM_V2_RELIEF_{name}",ld)
        if lo.name not in scene.collection.objects:
            scene.collection.objects.link(lo)
        lo.location=center+off*ext
        ld.energy=energy
        ld.shape="DISK"
        ld.size=max(area,2.0)
        lo.rotation_euler=(center-lo.location).to_track_quat("-Z","Y").to_euler()
        lights.append(lo)
    return lights

def render(scene,cam,name,pos,look):
    cam.location=Vector(pos)
    point(cam,look)
    scene.render.filepath=str(OUT/name)
    bpy.ops.render.render(write_still=True)

scene=bpy.context.scene
obj=bpy.data.objects.get(TARGET)
if obj is None:
    raise SystemExit(f"Missing {TARGET!r}")

manifest=load_manifest()
mats={m.name:m for m in bpy.data.materials}
missing=sorted(REQUIRED-set(mats))
if missing:
    raise SystemExit(f"Missing materials: {missing}")

stone_tile=tile_meters(manifest,"stone_wall_04")
roof_tile=tile_meters(manifest,"roof_slates_03")
resolution=4096

for name in ("GroundFloorWalls","BeamFakeTextureVertical"):
    build_relief_box_material(
        mats[name],
        ASSETS/"stone_wall_04"/"diffuse.png",
        ASSETS/"stone_wall_04"/"rough.png",
        ASSETS/"stone_wall_04"/"displacement.png",
        stone_tile,
        resolution,
    )
build_relief_box_material(
    mats["FakeRoof"],
    ASSETS/"roof_slates_03"/"diffuse.png",
    ASSETS/"roof_slates_03"/"rough.png",
    ASSETS/"roof_slates_03"/"displacement.png",
    roof_tile,
    resolution,
)
apply_stained_glass_seamless(
    mats["RoundWindwos"],
    ASSETS/"stained_glass"/"color.png",
)

st=evaluated_stats(obj)
if UV_NAME not in st["uv_layers"]:
    raise SystemExit(f"Expected UV layer {UV_NAME!r}: {st['uv_layers']}")

center=Vector(st["center"])
mn=Vector(st["min"])
size=Vector(st["size"])
ext=max(size.x,size.y,size.z)

scene.render.engine="BLENDER_EEVEE"
scene.render.image_settings.media_type="IMAGE"
scene.render.image_settings.file_format="PNG"
scene.render.resolution_x=1280
scene.render.resolution_y=800
scene.render.resolution_percentage=100

ensure_world(scene)
cam=ensure_cam(scene)
lights=ensure_lights(scene,center,size)
for o in scene.objects:
    if hasattr(o,"hide_render"):
        o.hide_render=o not in [obj,cam,*lights]
obj.hide_render=False
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
    render(scene,cam,name,pos,look)

report={
    "source_object":obj.name,
    "geometry_nodes":[m.node_group.name for m in obj.modifiers if m.type=="NODES" and m.node_group],
    "stats":st,
    "mapping":{
        "stone":"BOX/Object + Poly Haven physical dimensions",
        "roof":"BOX/Object + Poly Haven physical dimensions",
        "stained_glass":"existing UVMap + seamless REPEAT 2x",
    },
    "relief":{
        "source":"Poly Haven 4K displacement maps",
        "method":"Bump from displacement",
        "distance_rule":"one source texel in world units",
        "stone_bump_distance_m":stone_tile/resolution,
        "roof_bump_distance_m":roof_tile/resolution,
    },
    "stained_glass":{
        "source":"3DTextures Glass Stained Panel Window seamless CC0 material",
        "preserved_authored_shader":True,
        "source_dimensions":[1024,1024],
        "repeat":"2x as recommended by source author",
    },
    "renders":[v[0] for v in views],
}
(OUT/"relief-glass-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("SANCTUM_V2_RELIEF_GLASS_OK")
print(json.dumps(report,indent=2))

# SEAMLESS_CC0_SOURCE_GATE_V2

# SEAMLESS_CC0_SOURCE_GATE_V3
