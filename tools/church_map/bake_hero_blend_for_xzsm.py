#!/usr/bin/env python3
"""Prepare the exact Hero Blender scene for the Android XZSM bridge.

Image-backed materials remain image-backed. Flat authored colors become tiny
textures of the exact authored value. Procedural Base Color graphs are baked
from the actual Blender shader on each object, preserving the look instead of
falling back to white or to a guessed semantic palette.
"""
import bpy
import json
import os
import re
from pathlib import Path
from mathutils import Vector

SRC=Path(os.environ["XZIEL_HERO_BLEND"])
OUT=Path(os.environ.get("XZIEL_SNAPSHOT_OUT","snapshot/out"))
OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(SRC))
scene=bpy.context.scene

export_objects=[
    o for o in scene.objects
    if o.type=="MESH" and bool(o.get("xziel_snapshot_export",False))
]
if not export_objects:
    raise SystemExit("HERO_BLEND_BAKE_FAIL: xziel_snapshot_export meshes missing")

def bounds(objects):
    pts=[]
    for o in objects:
        pts.extend(o.matrix_world @ Vector(c) for c in o.bound_box)
    return (
        Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts))),
        Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts))),
    )

def base_socket(mat):
    if not mat or not mat.use_nodes or not mat.node_tree:
        return None
    bsdf=next((n for n in mat.node_tree.nodes if n.type=="BSDF_PRINCIPLED"),None)
    return bsdf.inputs.get("Base Color") if bsdf else None

def linked_image(sock,seen=None):
    if sock is None or not getattr(sock,"is_linked",False):
        return None
    seen=set() if seen is None else seen
    for link in sock.links:
        node=link.from_node
        if node is None or node.as_pointer() in seen:
            continue
        seen.add(node.as_pointer())
        if node.type=="TEX_IMAGE" and node.image and int(node.image.size[0])>0 and int(node.image.size[1])>0:
            return node.image
        for inp in getattr(node,"inputs",[]):
            img=linked_image(inp,seen)
            if img:
                return img
    return None

flat_cache={}
def flat_image(mat,color):
    key=tuple(round(float(x),6) for x in color[:4])
    if key in flat_cache:
        return flat_cache[key]
    safe=re.sub(r"[^A-Za-z0-9_]+","_",mat.name if mat else "flat")[:48]
    img=bpy.data.images.new("XZIEL_AUTHORED_FLAT_"+safe,width=16,height=16,alpha=True)
    rgba=[float(color[0]),float(color[1]),float(color[2]),float(color[3] if len(color)>3 else 1.0)]
    img.pixels=list(rgba)*256
    img.pack()
    flat_cache[key]=img
    return img

def ensure_image_material(mat):
    """Return ('image', image), ('procedural', None), or ('flat', image)."""
    if mat is None:
        img=flat_image(None,(0.18,0.18,0.18,1.0))
        return "flat",img

    # Older CC0 .blend assets (notably the 3TD ruins apse) still carry their
    # authored look in Material.diffuse_color with use_nodes=False. Enabling
    # nodes first creates a fresh Principled BSDF at Blender's default 0.8 gray,
    # which was flattening every moss/brick/concrete material to RGB 204.
    # Capture the legacy color BEFORE switching the material to nodes.
    if not mat.use_nodes:
        legacy_color=tuple(float(x) for x in mat.diffuse_color)
        mat.use_nodes=True
        nt=mat.node_tree
        bsdf=next((n for n in nt.nodes if n.type=="BSDF_PRINCIPLED"),None)
        if bsdf is None:
            bsdf=nt.nodes.new("ShaderNodeBsdfPrincipled")
        img=flat_image(mat,legacy_color)
        tex=nt.nodes.new("ShaderNodeTexImage")
        tex.name="XZIEL_LEGACY_DIFFUSE_IMAGE"
        tex.image=img
        sock=bsdf.inputs.get("Base Color")
        if sock is not None:
            for link in list(sock.links):
                nt.links.remove(link)
            nt.links.new(tex.outputs["Color"],sock)
        bsdf.inputs["Roughness"].default_value=0.62
        mat.diffuse_color=legacy_color
        return "flat",img

    nt=mat.node_tree
    bsdf=next((n for n in nt.nodes if n.type=="BSDF_PRINCIPLED"),None)
    if bsdf is None:
        bsdf=nt.nodes.new("ShaderNodeBsdfPrincipled")
    sock=bsdf.inputs.get("Base Color")
    img=linked_image(sock)
    if img:
        return "image",img
    if sock is not None and sock.is_linked:
        return "procedural",None
    color=tuple(sock.default_value) if sock is not None else tuple(mat.diffuse_color)
    img=flat_image(mat,color)
    tex=nt.nodes.new("ShaderNodeTexImage")
    tex.name="XZIEL_AUTHORED_FLAT_IMAGE"
    tex.image=img
    if sock is not None:
        for link in list(sock.links):
            nt.links.remove(link)
        nt.links.new(tex.outputs["Color"],sock)
    return "flat",img

procedural_objects=[]
flat_materials=0
image_materials=0

for obj in export_objects:
    has_proc=False
    for slot in obj.material_slots:
        kind,_=ensure_image_material(slot.material)
        if kind=="procedural":
            has_proc=True
        elif kind=="flat":
            flat_materials+=1
        else:
            image_materials+=1
    # The authored 3TD apse uses legacy/mixed material wiring that Blender
    # renders correctly but our simple Base Color classifier can mistake for
    # flat colors. Force the whole apse through a real 4K Blender bake so the
    # Android snapshot preserves the same ruin material visible in the Hero
    # proof render instead of a pale concrete placeholder.
    if has_proc or obj.name=="SANCTUM_HERO_APSE_RUIN":
        procedural_objects.append(obj)

# Diffuse COLOR bake does not need lighting convergence. One Cycles sample
# evaluates the authored shader color exactly while avoiding thousands of
# unnecessary path-tracing samples. Resolution remains 4K/2K.
scene.render.engine="CYCLES"
scene.cycles.device="CPU"
scene.cycles.samples=1
scene.cycles.preview_samples=1
scene.cycles.use_adaptive_sampling=False
scene.cycles.use_denoising=False
scene.render.bake.use_clear=True
scene.render.bake.margin=12
bake_records=[]
bake_root=OUT/"material-bakes"
bake_root.mkdir(parents=True,exist_ok=True)

for idx,obj in enumerate(procedural_objects,1):
    # Work on a unique mesh/material copy because Object coordinates make the
    # procedural pattern object-specific.
    obj.data=obj.data.copy()
    for si,slot in enumerate(obj.material_slots):
        if slot.material:
            slot.material=slot.material.copy()

    bpy.ops.object.select_all(action="DESELECT")
    obj.hide_viewport=False
    obj.hide_render=False
    obj.select_set(True)
    bpy.context.view_layer.objects.active=obj

    # Dedicated non-overlapping UVs for the bake.
    uv=obj.data.uv_layers.get("XZIEL_ANDROID_BAKE_UV")
    if uv is None:
        uv=obj.data.uv_layers.new(name="XZIEL_ANDROID_BAKE_UV")
    obj.data.uv_layers.active=uv
    obj.data.uv_layers.active_index=list(obj.data.uv_layers).index(uv)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    try:
        bpy.ops.uv.smart_project(angle_limit=1.15192,island_margin=0.015,area_weight=0.0,correct_aspect=True,scale_to_bounds=False)
    except TypeError:
        bpy.ops.uv.smart_project(island_margin=0.015)
    bpy.ops.object.mode_set(mode="OBJECT")

    n=obj.name.upper()
    # Architecture/key surfaces stay 4K; small detail stays 2K.
    high=any(k in n for k in ("FLOOR","WALL","APSE","STEP","WOOD_BASE","PEW","ALTAR_SLAB"))
    res=4096 if high else 2048
    safe=re.sub(r"[^A-Za-z0-9_]+","_",obj.name)[:64]
    img=bpy.data.images.new(f"XZIEL_BAKED_{safe}",width=res,height=res,alpha=True,float_buffer=False)
    img.file_format="PNG"
    img.filepath_raw=str(bake_root/f"{idx:03d}_{safe}.png")

    # Blender bake requires the target image node to be active in every
    # material slot on the object. We bake only Diffuse COLOR: no guessed
    # lighting and no replacement palette.
    for slot in obj.material_slots:
        mat=slot.material
        if mat is None:
            mat=bpy.data.materials.new(f"XZIEL_TEMP_{safe}")
            mat.use_nodes=True
            slot.material=mat
        mat.use_nodes=True
        nt=mat.node_tree
        node=nt.nodes.new("ShaderNodeTexImage")
        node.name="XZIEL_BAKE_TARGET"
        node.image=img
        nt.nodes.active=node
        node.select=True

    # COLOR-only bake: exact procedural Base Color, no direct/indirect light.
    bpy.ops.object.bake(type="DIFFUSE",pass_filter={"COLOR"},use_clear=True,margin=12)

    img.save()
    img.pack()

    baked=bpy.data.materials.new(f"XZIEL_BAKED_MAT_{safe}")
    baked.use_nodes=True
    nt=baked.node_tree
    bsdf=nt.nodes.get("Principled BSDF")
    tex=nt.nodes.new("ShaderNodeTexImage")
    tex.image=img
    nt.links.new(tex.outputs["Color"],bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value=0.55
    obj.data.materials.clear()
    obj.data.materials.append(baked)
    for poly in obj.data.polygons:
        poly.material_index=0

    bake_records.append({
        "object":obj.name,
        "resolution":res,
        "image":img.name,
        "file":img.filepath_raw,
    })
    print("XZIEL_BAKED_REAL_MATERIAL",idx,len(procedural_objects),obj.name,res)

# Create the collection contract consumed by export_vril_static_mesh.py.
old=bpy.data.collections.get("GAME_CHURCH_LOD0")
if old:
    for o in list(old.objects):
        old.objects.unlink(o)
    bpy.data.collections.remove(old)
lod=bpy.data.collections.new("GAME_CHURCH_LOD0")
scene.collection.children.link(lod)
for obj in export_objects:
    if obj.name not in lod.objects:
        lod.objects.link(obj)

# Do not classify anything as additive dressing: the full Hero scene is the
# authoritative visual mesh for this snapshot.
dress=bpy.data.collections.get("SANCTUM_DRESSING_V1")
if dress:
    for o in list(dress.objects):
        dress.objects.unlink(o)

mn,mx=bounds(export_objects)
floor_objs=[o for o in export_objects if o.name.startswith("SANCTUM_MAIN_FLOOR_")]
if not floor_objs:
    floor_objs=[o for o in export_objects if "FLOOR" in o.name.upper()]
if not floor_objs:
    raise SystemExit("HERO_BLEND_BAKE_FAIL: main floor objects missing")
floor_z=sum(max((o.matrix_world@Vector(c)).z for c in o.bound_box) for o in floor_objs)/len(floor_objs)
spawn=Vector(((mn.x+mx.x)*0.5,mn.y+2.6,floor_z))
zone_min=Vector((mn.x,mn.y,floor_z))
zone_max=Vector((mx.x,mx.y,max(mx.z,floor_z+8.0)))
zone_center=(zone_min+zone_max)*0.5

plan={"working_title":"XZIEL CHURCH SNAPSHOT EXACT HERO MATERIALS","zones":{"main_church":{
    "min":[float(x) for x in zone_min],
    "max":[float(x) for x in zone_max],
    "center":[float(x) for x in zone_center],
}}}
(OUT/"snapshot_plan.json").write_text(json.dumps(plan,indent=2),encoding="utf-8")
pkg=OUT/"package"; pkg.mkdir(exist_ok=True)
(pkg/"zones.json").write_text(json.dumps({"zones":[{"id":"zone_main_church","neighbors":[]}]},indent=2),encoding="utf-8")
(pkg/"entities.json").write_text(json.dumps({"entities":[{
    "type":"player_spawn",
    "transform":{"position":{"x":float(spawn.x),"y":float(spawn.y),"z":float(spawn.z)}},
    "properties":{"snapshot":"exact_hero_blend"}
}]},indent=2),encoding="utf-8")
(pkg/"spawns.json").write_text(json.dumps({"spawns":[]},indent=2),encoding="utf-8")
(OUT/"fitted.json").write_text(json.dumps({"barricades":[]},indent=2),encoding="utf-8")

try:
    bpy.ops.file.pack_all()
except Exception as exc:
    print("WARN bake pack_all",exc)
dst=OUT/"hero31_android_baked.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(dst))

report={
    "status":"PASS",
    "source_blend":str(SRC),
    "output_blend":str(dst),
    "export_meshes":len(export_objects),
    "image_material_slots":image_materials,
    "flat_material_slots":flat_materials,
    "procedural_objects_baked":len(procedural_objects),
    "forced_legacy_bakes":[o.name for o in procedural_objects if o.name=="SANCTUM_HERO_APSE_RUIN"],
    "bakes":bake_records,
    "floor_z":float(floor_z),
    "spawn":[float(x) for x in spawn],
    "bounds_min":[float(x) for x in mn],
    "bounds_max":[float(x) for x in mx],
}
(OUT/"exact-material-bake-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("XZIEL_EXACT_HERO_MATERIAL_BAKE_PASS")
print(json.dumps({k:v for k,v in report.items() if k!="bakes"},indent=2))
