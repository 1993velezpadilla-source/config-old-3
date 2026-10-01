import bpy
import json
import math
import os
from pathlib import Path
from mathutils import Vector

OUT=Path(os.environ.get("SANCTUM_V2_RELIEF_OUT","sanctum-v2-relief-glass"))
ASSETS=Path(os.environ.get("SANCTUM_V2_RELIEF_ASSETS","sanctum-v2-relief-assets"))
MANIFEST=ASSETS/"SOURCE_MANIFEST.json"
SHADER_LIB=Path(os.environ["SANCTUM_V2_GLASS_SHADER_LIB"])
SHADER_NAME="Crown Glass for windows"
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

def load_authored_glass_shader():
    if not SHADER_LIB.is_file():
        raise SystemExit(f"Missing authored shader library: {SHADER_LIB}")
    with bpy.data.libraries.load(str(SHADER_LIB), link=False) as (data_from, data_to):
        if SHADER_NAME not in data_from.materials:
            raise SystemExit(f"Missing authored shader {SHADER_NAME!r}")
        data_to.materials=[SHADER_NAME]
    mat=bpy.data.materials.get(SHADER_NAME)
    if mat is None or not mat.use_nodes or not mat.node_tree:
        raise SystemExit(f"Authored shader {SHADER_NAME!r} has no node tree")
    nodes=[n for n in mat.node_tree.nodes if n.bl_idname=="ShaderNodeBsdfPrincipled"]
    if len(nodes)!=1:
        raise SystemExit(f"Expected one Principled BSDF in {SHADER_NAME!r}, got {len(nodes)}")
    return mat,nodes[0]

def copy_socket_default(dst,src):
    if not hasattr(src,"default_value") or not hasattr(dst,"default_value"):
        return
    v=src.default_value
    try:
        if hasattr(v,"__len__") and not isinstance(v,str):
            dst.default_value=tuple(v)
        else:
            dst.default_value=v
    except Exception as e:
        raise SystemExit(f"Could not copy authored socket {src.name!r}: {e}")

def apply_stained_glass_authored_shader(mat,color_path,normal_path,expected_size):
    if not mat.use_nodes or not mat.node_tree:
        raise SystemExit("RoundWindwos has no node tree")
    nodes=mat.node_tree.nodes
    links=mat.node_tree.links
    bsdfs=[n for n in nodes if n.bl_idname=="ShaderNodeBsdfPrincipled"]
    if not bsdfs:
        raise SystemExit("RoundWindwos has no Principled BSDF")

    src_mat,src_bsdf=load_authored_glass_shader()

    # Copy authored Principled parameters from the external CC0 shader at runtime.
    copied={}
    for dst_bsdf in bsdfs:
        for src_in in src_bsdf.inputs:
            if src_in.is_linked:
                continue
            dst_in=dst_bsdf.inputs.get(src_in.name)
            if dst_in is None:
                continue
            copy_socket_default(dst_in,src_in)
            if src_in.name in ("IOR","Roughness","Transmission Weight","Specular IOR Level","Coat Roughness"):
                v=src_in.default_value
                try:
                    copied[src_in.name]=float(v)
                except Exception:
                    copied[src_in.name]=str(v)

    color_img=load_image(color_path,False)
    normal_img=load_image(normal_path,True)
    actual=list(color_img.size)
    normal_size=list(normal_img.size)
    if actual!=list(expected_size):
        raise SystemExit(f"Unexpected stained-glass color dimensions: {actual} expected={expected_size}")
    if normal_size!=actual:
        raise SystemExit(f"Stained-glass normal dimensions mismatch: color={actual} normal={normal_size}")

    uv=nodes.new("ShaderNodeUVMap")
    uv.uv_map=UV_NAME
    tex_color=nodes.new("ShaderNodeTexImage")
    tex_color.image=color_img
    tex_color.extension="REPEAT"
    tex_color.projection="FLAT"

    tex_normal=nodes.new("ShaderNodeTexImage")
    tex_normal.image=normal_img
    tex_normal.extension="REPEAT"
    tex_normal.projection="FLAT"
    nmap=nodes.new("ShaderNodeNormalMap")

    links.new(uv.outputs["UV"],tex_color.inputs["Vector"])
    links.new(uv.outputs["UV"],tex_normal.inputs["Vector"])
    links.new(tex_normal.outputs["Color"],nmap.inputs["Color"])

    for bsdf in bsdfs:
        links.new(tex_color.outputs["Color"],bsdf.inputs["Base Color"])
        links.new(nmap.outputs["Normal"],bsdf.inputs["Normal"])

    return {
        "source_library":str(SHADER_LIB),
        "source_material":src_mat.name,
        "copied_principled_defaults":copied,
    }

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

def enable_raytraced_glass(scene,mat):
    applied={}
    if hasattr(scene,"eevee") and scene.eevee is not None:
        if hasattr(scene.eevee,"use_raytracing"):
            scene.eevee.use_raytracing=True
            applied["scene.eevee.use_raytracing"]=True
        if hasattr(scene.eevee,"ray_tracing_method"):
            scene.eevee.ray_tracing_method="SCREEN"
            applied["scene.eevee.ray_tracing_method"]="SCREEN"
    if hasattr(mat,"surface_render_method"):
        mat.surface_render_method="DITHERED"
        applied["material.surface_render_method"]="DITHERED"
    if hasattr(mat,"use_raytrace_refraction"):
        mat.use_raytrace_refraction=True
        applied["material.use_raytrace_refraction"]=True
    if hasattr(mat,"use_screen_refraction"):
        mat.use_screen_refraction=True
        applied["material.use_screen_refraction"]=True
    return applied

def ensure_window_backlights(scene,center,size):
    # Reuse the proven three-light review rig powers; only positions are moved inside
    # the cathedral so the glass receives illumination from behind.
    proven_powers=(2400.0,1400.0,1800.0)
    energy=sum(proven_powers)/len(proven_powers)
    z0=center.z
    offsets=(
        Vector((0,-size.y*0.22,0)),
        Vector((0,0,size.z*0.12)),
        Vector((0,size.y*0.22,0)),
    )
    lights=[]
    for idx,off in enumerate(offsets,1):
        ld=bpy.data.lights.get(f"SANCTUM_V2_GLASS_BACKLIGHT_{idx}_DATA") or bpy.data.lights.new(f"SANCTUM_V2_GLASS_BACKLIGHT_{idx}_DATA","POINT")
        lo=bpy.data.objects.get(f"SANCTUM_V2_GLASS_BACKLIGHT_{idx}") or bpy.data.objects.new(f"SANCTUM_V2_GLASS_BACKLIGHT_{idx}",ld)
        if lo.name not in scene.collection.objects:
            scene.collection.objects.link(lo)
        lo.location=center+off
        ld.energy=energy
        lights.append(lo)
    return lights,{"count":len(lights),"energy_each":energy,"source_powers":list(proven_powers)}

def create_emissive_window_backer(scene,obj,color_path,offset_m,building_center):
    deps=bpy.context.evaluated_depsgraph_get()
    ev=obj.evaluated_get(deps)
    mesh=ev.to_mesh()
    try:
        target_slots=[i for i,m in enumerate(mesh.materials) if m and m.name=="RoundWindwos"]
        if not target_slots:
            raise SystemExit("Evaluated cathedral has no RoundWindwos material slot")
        uv_layer=mesh.uv_layers.get(UV_NAME)
        if uv_layer is None:
            raise SystemExit(f"Evaluated cathedral has no {UV_NAME!r} for emissive backer")

        verts=[]
        faces=[]
        uv_faces=[]
        normal_matrix=ev.matrix_world.to_3x3().inverted().transposed()

        for poly in mesh.polygons:
            if poly.material_index not in target_slots:
                continue
            face=[]
            face_uv=[]
            world_center=ev.matrix_world@poly.center
            outward=(normal_matrix@poly.normal).normalized()
            radial=world_center-Vector(building_center)
            if radial.length>0 and outward.dot(radial)<0:
                outward=-outward
            inward=-outward
            for loop_index in poly.loop_indices:
                vi=mesh.loops[loop_index].vertex_index
                world_co=ev.matrix_world@mesh.vertices[vi].co
                face.append(len(verts))
                verts.append(world_co + inward*offset_m)
                face_uv.append(tuple(uv_layer.data[loop_index].uv))
            if len(face)>=3:
                faces.append(face)
                uv_faces.append(face_uv)

        if not faces:
            raise SystemExit("No RoundWindwos faces were extracted for emissive backing")

        back_mesh=bpy.data.meshes.new("SANCTUM_V2_WINDOW_EMISSIVE_BACKER_MESH")
        back_mesh.from_pydata(verts,[],faces)
        back_mesh.update()
        uv=back_mesh.uv_layers.new(name=UV_NAME)
        for poly,coords in zip(back_mesh.polygons,uv_faces):
            for li,coord in zip(poly.loop_indices,coords):
                uv.data[li].uv=coord

        back_obj=bpy.data.objects.new("SANCTUM_V2_WINDOW_EMISSIVE_BACKER",back_mesh)
        scene.collection.objects.link(back_obj)

        mat=bpy.data.materials.new("SANCTUM_V2_WINDOW_EMISSIVE_BACKER_MAT")
        mat.use_nodes=True
        nodes=mat.node_tree.nodes
        links=mat.node_tree.links
        nodes.clear()
        out=nodes.new("ShaderNodeOutputMaterial")
        emit=nodes.new("ShaderNodeEmission")
        tex=nodes.new("ShaderNodeTexImage")
        tex.image=load_image(color_path,False)
        tex.extension="REPEAT"
        uvnode=nodes.new("ShaderNodeUVMap")
        uvnode.uv_map=UV_NAME
        # Keep the authored/default emission strength: 1.0.
        emit.inputs["Strength"].default_value=1.0
        links.new(uvnode.outputs["UV"],tex.inputs["Vector"])
        links.new(tex.outputs["Color"],emit.inputs["Color"])
        links.new(emit.outputs["Emission"],out.inputs["Surface"])
        back_mesh.materials.append(mat)

        return back_obj,{
            "derived_from_material":"RoundWindwos",
            "faces":len(faces),
            "offset_rule":"one Poly Haven stone source texel in world units",
            "offset_m":offset_m,
            "emission_strength":1.0,
            "emission_strength_rule":"Blender Emission node default/base strength",
            "color_source":"same authored OpenGameArt stained-glass color map",
        }
    finally:
        ev.to_mesh_clear()

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
sg=manifest["stained_glass"]
glass_shader_report=apply_stained_glass_authored_shader(
    mats["RoundWindwos"],
    ASSETS/"stained_glass"/"color.jpg",
    ASSETS/"stained_glass"/"normal.jpg",
    sg["source_dimensions"],
)

st=evaluated_stats(obj)
if UV_NAME not in st["uv_layers"]:
    raise SystemExit(f"Expected UV layer {UV_NAME!r}: {st['uv_layers']}")

center=Vector(st["center"])
mn=Vector(st["min"])
size=Vector(st["size"])
ext=max(size.x,size.y,size.z)

scene.render.engine="BLENDER_EEVEE"
raytrace_report=enable_raytraced_glass(scene,mats["RoundWindwos"])
emissive_backer,emissive_backer_report=create_emissive_window_backer(
    scene,
    obj,
    ASSETS/"stained_glass"/"color.jpg",
    stone_tile/resolution,
    center,
)
scene.render.image_settings.media_type="IMAGE"
scene.render.image_settings.file_format="PNG"
scene.render.resolution_x=1280
scene.render.resolution_y=800
scene.render.resolution_percentage=100

ensure_world(scene)
cam=ensure_cam(scene)
lights=ensure_lights(scene,center,size)
backlights,backlight_report=ensure_window_backlights(scene,center,size)
all_lights=[*lights,*backlights]
for o in scene.objects:
    if hasattr(o,"hide_render"):
        o.hide_render=o not in [obj,cam,emissive_backer,*all_lights]
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
        "stained_glass":"existing UVMap + OpenGameArt seamless maps + external CC0 Crown Glass for windows shader",
    },
    "relief":{
        "source":"Poly Haven 4K displacement maps",
        "method":"Bump from displacement",
        "distance_rule":"one source texel in world units",
        "stone_bump_distance_m":stone_tile/resolution,
        "roof_bump_distance_m":roof_tile/resolution,
    },
    "stained_glass":{
        "source":"OpenGameArt Repeating Mini Windows - Stained Glass - Seamless texture with normalmap",
        "author":"Keith333",
        "license":"CC-BY 3.0",
        "source_dimensions":sg["source_dimensions"],
        "uses_authored_normal_map":True,
        "shader":glass_shader_report,
        "raytracing":raytrace_report,
        "backlighting":backlight_report,
        "emissive_backer":emissive_backer_report,
    },
        "renders":[v[0] for v in views],
}
(OUT/"relief-glass-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("SANCTUM_V2_EMISSIVE_BACKED_GLASS_OK")
print(json.dumps(report,indent=2))

# SEAMLESS_CC0_SOURCE_GATE_V2

# SEAMLESS_CC0_SOURCE_GATE_V3
