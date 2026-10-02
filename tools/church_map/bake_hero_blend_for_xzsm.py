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
import runpy
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

# ---------------------------------------------------------------------------
# POLISH PASS 01
# Reuse the exact Hero scene, then add only authored gameplay-readable visual
# geometry that the BSP cannot show because XZSM is the sole visual authority.
# ---------------------------------------------------------------------------
NAV_PATH=Path(os.environ.get("XZIEL_NAV_SKELETON","tools/church_map/sanctum_nav_skeleton_apk9.v1.json"))
nav_doc=json.loads(NAV_PATH.read_text(encoding="utf-8")) if NAV_PATH.is_file() else None
polish_objects=[]
removed_pews=[]
spawner_windows=[]

refmat=runpy.run_path("tools/sanctum_v2/reference_materials.py")
REF=refmat["material_set"]()
POLISH_FLOOR=REF["floor"]
POLISH_WOOD=REF["wood_h"]
POLISH_GLASS=REF["glass"]

def flat_polish_material(name,color,roughness=0.75):
    mat=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes=True
    bsdf=mat.node_tree.nodes.get("Principled BSDF") if mat.node_tree else None
    if bsdf:
        bsdf.inputs["Base Color"].default_value=(*color,1.0)
        bsdf.inputs["Roughness"].default_value=roughness
    mat.diffuse_color=(*color,1.0)
    return mat

BOARD_MAT=flat_polish_material("SANCTUM_SPAWNER_BOARD_WOOD",(0.105,0.030,0.012),0.86)

def make_quad_object(name, rects, material):
    # rects are 4-tuples of world-space corners. Multiple quads become one
    # object/material so Android gets one texture rather than dozens.
    verts=[]; faces=[]
    for rect in rects:
        base=len(verts)
        verts.extend(tuple(float(x) for x in p) for p in rect)
        faces.append((base,base+1,base+2,base+3))
    mesh=bpy.data.meshes.new(name+"_MESH")
    mesh.from_pydata(verts,[],faces)
    mesh.update()
    obj=bpy.data.objects.new(name,mesh)
    scene.collection.objects.link(obj)
    mesh.materials.append(material)
    obj["xziel_role"]="polish_visual"
    obj["xziel_collision"]=False
    polish_objects.append(obj)
    return obj

def object_world_bounds(obj):
    pts=[obj.matrix_world @ Vector(c) for c in obj.bound_box]
    return (
        Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts))),
        Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts))),
    )

if nav_doc:
    nave_specs=[f for f in nav_doc.get("floors",[]) if f["id"].startswith("nave_")]
    if not nave_specs:
        raise SystemExit("POLISH_FAIL: nav skeleton has no nave floor pieces")
    nx0=min(f["min"][0] for f in nave_specs); nx1=max(f["max"][0] for f in nave_specs)
    ny0=min(f["min"][1] for f in nave_specs); ny1=max(f["max"][1] for f in nave_specs)
    nave_z=max(f["max"][2] for f in nave_specs)

    # Remove only prop pews that visibly escape the playable nave footprint.
    kept=[]
    for obj in export_objects:
        n=obj.name.upper()
        if "PEW" in n:
            mn_,mx_=object_world_bounds(obj)
            outside=(mn_.x < nx0-0.18 or mx_.x > nx1+0.18 or mn_.y < ny0-0.18 or mx_.y > ny1+0.18)
            if outside:
                removed_pews.append(obj.name)
                obj.hide_render=True
                obj.hide_viewport=True
                continue
        kept.append(obj)
    export_objects=kept

    # Visible exterior apron: one object, four quads, one high-quality bake.
    ext_rects=[]
    for f in nav_doc.get("floors",[]):
        if not f["id"].startswith("exterior_"):
            continue
        x0,y0,_=f["min"]; x1,y1,z=f["max"]
        z=float(z)+0.018
        ext_rects.append(((x0,y0,z),(x1,y0,z),(x1,y1,z),(x0,y1,z)))
    if len(ext_rects)!=4:
        raise SystemExit(f"POLISH_FAIL: expected 4 exterior apron pieces, got {len(ext_rects)}")
    exterior_obj=make_quad_object("SANCTUM_EXTERIOR_FLOOR_VISUAL",ext_rects,POLISH_FLOOR)
    exterior_obj["xziel_zone"]="exterior"

    # Full visible second floor matched 1:1 to the already-proven collision deck.
    upper=next((f for f in nav_doc.get("floors",[]) if f["id"]=="upper_full_deck"),None)
    if not upper:
        raise SystemExit("POLISH_FAIL: upper_full_deck missing")
    ux0,uy0,_=upper["min"]; ux1,uy1,uz=upper["max"]; uz=float(uz)+0.018
    upper_obj=make_quad_object("SANCTUM_UPPER_FLOOR_VISUAL",[
        ((ux0,uy0,uz),(ux1,uy0,uz),(ux1,uy1,uz),(ux0,uy1,uz))
    ],POLISH_WOOD)
    upper_obj["xziel_zone"]="main_church"

    # Eight future zombie-window sockets. These are visual-only in this pass:
    # stained-glass backplates + three dark boards each. No spawn_zombie or
    # item_barricade entities are enabled yet.
    glass_rects=[]; board_rects=[]
    ys=[ny0+(ny1-ny0)*t for t in (0.18,0.38,0.62,0.82)]
    for side,x,normal in (("west",nx0-0.025,(-1.0,0.0,0.0)),("east",nx1+0.025,(1.0,0.0,0.0))):
        for slot,y in enumerate(ys,1):
            zc=nave_z+1.28
            half_w=0.92; half_h=0.88
            glass_rects.append(((x,y-half_w,zc-half_h),(x,y+half_w,zc-half_h),(x,y+half_w,zc+half_h),(x,y-half_w,zc+half_h)))
            for bi,(dz,slant) in enumerate(((-0.52,0.10),(0.0,-0.08),(0.52,0.12)),1):
                zz=zc+dz
                h=0.105
                board_rects.append(((x-normal[0]*0.012,y-half_w-0.06,zz-h-slant),
                                    (x-normal[0]*0.012,y+half_w+0.06,zz-h+slant),
                                    (x-normal[0]*0.012,y+half_w+0.06,zz+h+slant),
                                    (x-normal[0]*0.012,y-half_w-0.06,zz+h-slant)))
            inside=(x-normal[0]*0.85,y,zc-0.55)
            outside=(x+normal[0]*2.6,y,zc-0.55)
            approach=(x+normal[0]*1.25,y,zc-0.55)
            spawner_windows.append({
                "id":f"window_{side}_{slot}",
                "side":side,
                "slot":slot,
                "barricade_center":[float(x),float(y),float(zc)],
                "normal":[float(v) for v in normal],
                "inside_player_side":[float(v) for v in inside],
                "outside_spawn":[float(v) for v in outside],
                "outside_approach":[float(v) for v in approach],
                "state":"prepared_no_zombies",
            })
    window_glass=make_quad_object("SANCTUM_SPAWNER_WINDOWS_GLASS",glass_rects,POLISH_GLASS)
    window_glass["xziel_role"]="future_spawner_window"
    window_boards=make_quad_object("SANCTUM_SPAWNER_WINDOWS_BOARDS",board_rects,BOARD_MAT)
    window_boards["xziel_role"]="future_barricade_boards"

    (OUT/"window-spawner-prep.json").write_text(json.dumps({
        "schema_version":1,
        "status":"PREPARED_NO_ZOMBIES",
        "count":len(spawner_windows),
        "windows":spawner_windows,
    },indent=2),encoding="utf-8")

    export_objects.extend(polish_objects)

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
    high=any(k in n for k in ("FLOOR","WALL","APSE","STEP","WOOD_BASE","PEW","ALTAR_SLAB","SPAWNER_WINDOWS"))
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
if nav_doc:
    spawn=Vector(nav_doc.get("spawn",((mn.x+mx.x)*0.5,mn.y+2.6,floor_z)))
    zone_min=Vector(nav_doc["plan"]["min"])
    zone_max=Vector(nav_doc["plan"]["max"])
else:
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
    "polish":{
        "nav_skeleton":str(NAV_PATH) if nav_doc else None,
        "visible_exterior":bool(nav_doc),
        "visible_upper_floor":bool(nav_doc),
        "spawner_window_count":len(spawner_windows),
        "spawner_state":"prepared_no_zombies" if spawner_windows else "none",
        "removed_out_of_bounds_pews":removed_pews,
        "polish_objects":[o.name for o in polish_objects],
    },
    "bakes":bake_records,
    "floor_z":float(floor_z),
    "spawn":[float(x) for x in spawn],
    "bounds_min":[float(x) for x in mn],
    "bounds_max":[float(x) for x in mx],
}
(OUT/"exact-material-bake-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("XZIEL_EXACT_HERO_MATERIAL_BAKE_PASS")
print(json.dumps({k:v for k,v in report.items() if k!="bakes"},indent=2))
