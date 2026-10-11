#!/usr/bin/env python3
"""Bake ORIGINAL authored Oct-02 Sanctum V2 Blender shaders to Android-friendly GLB.

No semantic textures, replacement image libraries, colored geometry guessing,
or Blender->GLB->Blender reconstruction. Source .blend must be generated from
the exact Oct-02 authoring script before glTF loses procedural nodes.
Adapted from previously GREEN bake_hero_blend_for_xzsm.py in this same repo.
"""
import bpy
from pathlib import Path
import os
import json
import re
from collections import Counter

source=Path(os.environ["XZIEL_V2_SOURCE_BLEND"]).resolve()
out=Path(os.environ.get("XZIEL_V2_BAKED_OUT","sanctum-v2-authored-bake")).resolve()
out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(source))
scene=bpy.context.scene
original=[obj for obj in bpy.data.objects if obj.type=="MESH" and bool(obj.get("xziel_restore_materials",False))]
if len(original)<35:
    raise SystemExit("ORIGINAL_SANCTUM_V2_BAKE_FAIL: missing original tagged authoring meshes")

def material_base(mat):
    if mat and mat.use_nodes and mat.node_tree:
        return next((n.inputs.get("Base Color") for n in mat.node_tree.nodes if n.type=="BSDF_PRINCIPLED"),None)
    return None

def find_linked_image(socket,seen=None):
    if not socket or not getattr(socket,"is_linked",False): return None
    seen=set() if seen is None else seen
    for link in socket.links:
        n=link.from_node
        if not n or n.as_pointer() in seen:continue
        seen.add(n.as_pointer())
        if n.type=="TEX_IMAGE" and n.image and n.image.size[0]>0 and n.image.size[1]>0:
            return n.image
        for sub in getattr(n,"inputs",[]):
            found=find_linked_image(sub,seen)
            if found:return found
    return None

colors={}
def flat_image(mat,value):
    rgb=tuple(round(float(x),6) for x in value[:4])
    if len(rgb)!=4:rgb=tuple(rgb[:3])+(1.0,)
    if rgb in colors:return colors[rgb]
    name=re.sub('[^a-zA-Z0-9_]','_',mat.name if mat else 'missing')[:40]
    img=bpy.data.images.new("XZIEL_AUTHORED_FLAT_"+name,width=8,height=8,alpha=True)
    img.pixels=list(rgb)*64
    img.pack()
    colors[rgb]=img
    return img

def has_procedural(mat):
    """Ensure faithful material Base Color, preserving CC0 legacy diffuse."""
    if mat is None: return False
    if not mat.use_nodes:
        before=tuple(float(x) for x in mat.diffuse_color)
        mat.use_nodes=True
        nt=mat.node_tree
        shader=next((n for n in nt.nodes if n.type=='BSDF_PRINCIPLED'),None)
        if shader is None:shader=nt.nodes.new("ShaderNodeBsdfPrincipled")
        tex=nt.nodes.new("ShaderNodeTexImage")
        tex.image=flat_image(mat,before)
        sock=shader.inputs.get("Base Color")
        if sock:
            for link in list(sock.links):nt.links.remove(link)
            nt.links.new(tex.outputs["Color"],sock)
        mat.diffuse_color=before
        return False
    base=material_base(mat)
    if base is None:
        # Material remains original; if not Principled, baking requires it.
        return True
    if find_linked_image(base):
        return False
    if base.is_linked:
        # Actual procedural nodes (Brick, Noise, Wave, Mix, etc.) must be baked.
        return True
    tex=mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image=flat_image(mat,tuple(base.default_value))
    mat.node_tree.links.new(tex.outputs["Color"],base)
    return False

procedural=[]
counter=Counter()
for obj in original:
    proc=False
    for slot in obj.material_slots:
        if slot.material:
            if has_procedural(slot.material):
                proc=True
                counter['procedural_material_slots']+=1
            else:counter['image_or_flat_material_slots']+=1
    if proc:procedural.append(obj)

scene.render.engine="CYCLES"
scene.cycles.device="CPU"
scene.cycles.samples=1
scene.cycles.preview_samples=1
scene.cycles.use_adaptive_sampling=False
scene.render.bake.margin=8
scene.render.bake.use_clear=True
records=[]
work=out/"source-shader-bakes"
work.mkdir(exist_ok=True)
for idx,obj in enumerate(procedural,1):
    # Copy object and material data: Object-coordinates texture varies by mesh.
    obj.data=obj.data.copy()
    for slot in obj.material_slots:
        if slot.material:slot.material=slot.material.copy()
    bpy.ops.object.select_all(action="DESELECT")
    obj.hide_render=False
    obj.hide_viewport=False
    obj.select_set(True)
    bpy.context.view_layer.objects.active=obj
    uv=obj.data.uv_layers.get("XZIEL_V2_AUTHORED_BAKE")
    if uv is None:uv=obj.data.uv_layers.new(name="XZIEL_V2_AUTHORED_BAKE")
    obj.data.uv_layers.active=uv
    obj.data.uv_layers.active_index=list(obj.data.uv_layers).index(uv)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    try:bpy.ops.uv.smart_project(angle_limit=1.15192,island_margin=.012,area_weight=0.0)
    except TypeError:bpy.ops.uv.smart_project(island_margin=.012)
    bpy.ops.object.mode_set(mode="OBJECT")
    n=obj.name.upper()
    # 2K major architectural surfaces, 1K wood and floors, 512 small details
    res=2048 if ("OUTER_BAKED" in n or "WALL" in n) else (1024 if any(t in n for t in ("ROOF","FLOOR","PEW","UPPER","RAMP","BRIDGE","ALTAR","APSE")) else 512)
    safe=re.sub('[^a-zA-Z0-9_]','_',obj.name)[:48]
    img=bpy.data.images.new(f"XZIEL_V2_BAKED_{idx:03d}_{safe}",width=res,height=res,alpha=True)
    img.file_format="PNG"
    img.filepath_raw=str(work/f"{idx:03d}_{safe}.png")
    for slot in obj.material_slots:
        mat=slot.material
        if mat is None:
            mat=bpy.data.materials.new("XZIEL_UNASSIGNED_"+safe)
            mat.use_nodes=True
            slot.material=mat
        mat.use_nodes=True
        nt=mat.node_tree
        tex=nt.nodes.new("ShaderNodeTexImage")
        tex.name="XZIEL_V2_AUTHORED_DIFFUSE_BAKE_TARGET"
        tex.image=img
        nt.nodes.active=tex
    bpy.ops.object.bake(type="DIFFUSE",pass_filter={"COLOR"},use_clear=True,margin=8)
    img.save()
    img.pack()
    baked=bpy.data.materials.new(f"XZIEL_V2_AUTHORED_MAT_{idx:03d}_{safe}")
    baked.use_nodes=True
    nt=baked.node_tree
    bsdf=nt.nodes.get("Principled BSDF")
    if bsdf is None:
        bsdf=nt.nodes.new("ShaderNodeBsdfPrincipled")
        out_shader=nt.nodes.get("Material Output")
        if out_shader:nt.links.new(bsdf.outputs["BSDF"],out_shader.inputs["Surface"])
    tex=nt.nodes.new("ShaderNodeTexImage")
    tex.image=img
    nt.links.new(tex.outputs["Color"],bsdf.inputs["Base Color"])
    obj.data.materials.clear()
    obj.data.materials.append(baked)
    for poly in obj.data.polygons:poly.material_index=0
    records.append({"object":obj.name,"resolution":res,"file":str(img.filepath_raw),
                    "faces":len(obj.data.polygons),"png_bytes":Path(img.filepath_raw).stat().st_size})
    print("SANCTUM_V2_AUTHORING_SHADER_BAKED",idx,len(procedural),obj.name,res,flush=True)

# Respect only exact Oct-02 selected architecture and walkable meshes.
bpy.ops.object.select_all(action="DESELECT")
for obj in original:
    obj.hide_viewport=False
    obj.hide_render=False
    obj.select_set(True)
bpy.context.view_layer.objects.active=original[0]
glb=out/"sanctum-v2-real-authored-materials.glb"
bpy.ops.export_scene.gltf(filepath=str(glb),export_format="GLB",
                          use_selection=True,export_apply=True,export_extras=True)
if glb.stat().st_size<2_000_000:raise SystemExit("Bake failure: exported GLB too small")
counter['source_meshes']=len(original)
counter['procedural_meshes_baked']=len(procedural)
counter['baked_faces']=sum(r['faces'] for r in records)
counter['baked_png_bytes']=sum(r['png_bytes'] for r in records)
counter['glb_bytes']=glb.stat().st_size
if counter['baked_faces']<280_000:
    raise SystemExit("Insufficient actual source procedural shaders baked, expected GroundFloorWalls + roof: "+str(counter))
report={"status":"AUTHORED_SHADER_BAKED_REQUIRES_VRIL_RUNTIME_VALIDATION",
        "original_authority_blend":str(source),
        "original_source":"Oct-02 source build with packed CC0 + Blender procedurals",
        "glb":str(glb),"totals":dict(counter),"objects":records}
(out/"sanctum-v2-real-material-bake-report.json").write_text(json.dumps(report,indent=2))
print("SANCTUM_V2_REAL_AUTHORED_MATERIALS_BAKED",json.dumps(dict(counter),sort_keys=True))
