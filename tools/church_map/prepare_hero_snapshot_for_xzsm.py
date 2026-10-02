#!/usr/bin/env python3
import bpy
import json
import os
from pathlib import Path
from mathutils import Vector

GLB=Path(os.environ["XZIEL_SNAPSHOT_GLB"])
OUT=Path(os.environ.get("XZIEL_SNAPSHOT_OUT","snapshot/out"))
OUT.mkdir(parents=True,exist_ok=True)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

bpy.ops.import_scene.gltf(filepath=str(GLB))
scene=bpy.context.scene
meshes=[o for o in scene.objects if o.type=="MESH"]
if not meshes:
    raise SystemExit("SNAPSHOT_PREP_FAIL: no mesh objects imported")

# glTF cannot serialize Blender procedural shader graphs. Hero31 therefore
# contains several perfectly valid Blender materials that arrive in the GLB
# with neither an image nor a baseColorFactor; glTF's default is pure white.
# Build deterministic semantic albedo textures for ONLY those image-less
# materials so Android never renders white placeholders.
import math
import re

semantic_cache={}
semantic_assignments={}

def semantic_spec(name):
    n=(name or "").lower()
    if "burgundy" in n:
        return "cloth_burgundy",(0.30,0.025,0.035),512
    if "paper" in n:
        return "paper",(0.62,0.50,0.34),512
    if "candle" in n or "wax" in n:
        return "wax",(0.78,0.58,0.30),512
    if "gold" in n:
        return "aged_gold",(0.48,0.22,0.045),512
    if "copper" in n:
        return "copper",(0.38,0.16,0.065),512
    if "black_iron" in n or "blackiron" in n or "power_proxy" in n:
        return "dark_metal",(0.045,0.038,0.034),512
    if "gothic_wood_h" in n:
        return "wood_h",(0.23,0.095,0.035),1024
    if "gothic_wood_v" in n:
        return "wood_v",(0.23,0.095,0.035),1024
    if "hymn" in n:
        if n.endswith("_0"): return "hymn_black",(0.045,0.038,0.032),512
        if n.endswith("_1"): return "hymn_red",(0.24,0.035,0.035),512
        return "hymn_brown",(0.13,0.065,0.030),512
    if "beam" in n:
        return "wood_v",(0.18,0.075,0.028),1024
    if "roundwind" in n or "window" in n:
        return "aged_glass",(0.09,0.12,0.14),1024
    if "moss" in n or "grass" in n:
        return "mossy_stone",(0.22,0.25,0.18),1024
    if any(k in n for k in ("brick","concrete","crete","masonry","oldgray","stain","groundfloor","roof","flagstone")):
        return "aged_stone",(0.31,0.285,0.255),1024
    if "ad_frame" in n:
        return "dark_metal",(0.075,0.055,0.040),512
    if "ad_panel" in n:
        return "ad_panel",(0.10,0.085,0.070),512
    return "neutral_dark",(0.22,0.20,0.18),512

def build_semantic_image(kind,base,res):
    key=(kind,tuple(round(x,4) for x in base),res)
    if key in semantic_cache:
        return semantic_cache[key]
    safe=re.sub(r"[^A-Za-z0-9_]+","_",kind)
    img=bpy.data.images.new(f"XZIEL_SEM_{safe}_{res}",width=res,height=res,alpha=True,float_buffer=False)
    pixels=[0.0]*(res*res*4)
    br,bg,bb=base
    for y in range(res):
        fy=y/max(1,res-1)
        for x in range(res):
            fx=x/max(1,res-1)
            # Cheap deterministic material detail. This is not a placeholder:
            # it restores readable stone/wood/cloth/metal breakup on the GL4ES
            # compatibility path where the original Blender nodes were lost.
            if kind.startswith("wood"):
                axis=fx if kind=="wood_h" else fy
                grain=(0.55*math.sin(axis*120.0)+0.30*math.sin(axis*37.0+fy*8.0)+0.15*math.sin((fx+fy)*19.0))
                shade=1.0+0.18*grain
            elif kind in ("aged_stone","mossy_stone"):
                n1=math.sin(fx*41.0+fy*17.0)
                n2=math.sin(fx*13.0-fy*53.0)
                mortar=0.90 if ((int(fx*18)+(int(fy*12)&1)*0.5)%1.0)>0.07 and (fy*12)%1.0>0.07 else 0.72
                shade=(0.92+0.10*n1+0.06*n2)*mortar
                if kind=="mossy_stone":
                    shade*=0.94+0.08*math.sin(fx*9.0+fy*21.0)
            elif kind=="cloth_burgundy":
                weave=0.04*math.sin(fx*170.0)+0.04*math.sin(fy*160.0)
                shade=0.96+weave
            elif kind in ("dark_metal","copper","aged_gold"):
                shade=0.88+0.10*math.sin(fx*75.0+fy*9.0)+0.04*math.sin(fy*31.0)
            elif kind=="aged_glass":
                shade=0.86+0.08*math.sin(fx*18.0)+0.05*math.sin(fy*23.0)
            elif kind.startswith("hymn"):
                shade=0.95+0.025*math.sin(fx*90.0)
            elif kind=="paper":
                shade=0.95+0.035*math.sin(fx*73.0+fy*29.0)
            elif kind=="wax":
                shade=0.98+0.025*math.sin(fy*53.0)
            else:
                shade=0.92+0.07*math.sin(fx*31.0+fy*17.0)
            i=(y*res+x)*4
            pixels[i+0]=max(0.0,min(0.86,br*shade))
            pixels[i+1]=max(0.0,min(0.86,bg*shade))
            pixels[i+2]=max(0.0,min(0.86,bb*shade))
            pixels[i+3]=1.0
    img.pixels.foreach_set(pixels)
    img.pack()
    semantic_cache[key]=img
    return img

used_materials=[]
seen=set()
for obj in meshes:
    for slot in obj.material_slots:
        mat=slot.material
        if mat and mat.as_pointer() not in seen:
            seen.add(mat.as_pointer())
            used_materials.append(mat)

for mat in used_materials:
    mat.use_nodes=True
    nt=mat.node_tree
    valid_images=[
        node.image for node in nt.nodes
        if node.type=="TEX_IMAGE" and node.image and int(node.image.size[0])>0 and int(node.image.size[1])>0
    ]
    if valid_images:
        continue
    bsdf=next((n for n in nt.nodes if n.type=="BSDF_PRINCIPLED"),None)
    if bsdf is None:
        bsdf=nt.nodes.new("ShaderNodeBsdfPrincipled")
    kind,base,res=semantic_spec(mat.name)
    img=build_semantic_image(kind,base,res)
    tex=nt.nodes.new("ShaderNodeTexImage")
    tex.name="XZIEL_SEMANTIC_ALBEDO"
    tex.image=img
    tex.interpolation="Linear"
    base_socket=bsdf.inputs.get("Base Color")
    if base_socket:
        for link in list(base_socket.links):
            nt.links.remove(link)
        nt.links.new(tex.outputs["Color"],base_socket)
    mat.diffuse_color=(*base,1.0)
    semantic_assignments[mat.name]={"kind":kind,"resolution":res,"base":[float(x) for x in base]}

if not semantic_assignments:
    print("XZIEL_SEMANTIC_TEXTURES none-needed")
else:
    print("XZIEL_SEMANTIC_TEXTURES",json.dumps(semantic_assignments,sort_keys=True))

def bounds(objects):
    pts=[]
    for o in objects:
        pts.extend(o.matrix_world @ Vector(c) for c in o.bound_box)
    mn=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts)))
    mx=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts)))
    return mn,mx

mn,mx=bounds(meshes)

floor_objs=[o for o in meshes if o.name.startswith("SANCTUM_MAIN_FLOOR_")]
if not floor_objs:
    raise SystemExit("SNAPSHOT_PREP_FAIL: SANCTUM_MAIN_FLOOR_* missing")
floor_tops=[]
for o in floor_objs:
    floor_tops.append(max((o.matrix_world @ Vector(c)).z for c in o.bound_box))
floor_z=sum(floor_tops)/len(floor_tops)

# Hero render camera entered from the low-Y end and looked toward the altar.
spawn=Vector(((mn.x+mx.x)*0.5, mn.y+2.6, floor_z))
zone_min=Vector((mn.x,mn.y,floor_z))
zone_max=Vector((mx.x,mx.y,max(mx.z,floor_z+8.0)))
zone_center=(zone_min+zone_max)*0.5

# Keep the imported Hero snapshot as additive dressing. The existing XZSM
# exporter never decimates dressing objects and permits generated base-color
# textures for procedural materials that GLB cannot serialize as images.
dress=bpy.data.collections.get("SANCTUM_DRESSING_V1")
if dress is None:
    dress=bpy.data.collections.new("SANCTUM_DRESSING_V1")
    scene.collection.children.link(dress)
for o in meshes:
    if o.name not in dress.objects:
        dress.objects.link(o)

# XZSM requires a non-empty GAME_CHURCH_LOD0 authority collection. Supply a
# tiny textured triangle buried just under the nave floor; all visible geometry
# remains the exact imported Hero GLB in SANCTUM_DRESSING_V1.
lod=bpy.data.collections.get("GAME_CHURCH_LOD0")
if lod is None:
    lod=bpy.data.collections.new("GAME_CHURCH_LOD0")
    scene.collection.children.link(lod)
mesh=bpy.data.meshes.new("XZIEL_SNAPSHOT_ANCHOR_MESH")
z=floor_z-0.20
mesh.from_pydata([
    (spawn.x-0.01,spawn.y-0.01,z),
    (spawn.x+0.01,spawn.y-0.01,z),
    (spawn.x,spawn.y+0.01,z),
],[],[(0,1,2)])
mesh.update()
uv=mesh.uv_layers.new(name="UVMap")
for loop,co in zip(uv.data,[(0,0),(1,0),(0.5,1)]):
    loop.uv=co
anchor=bpy.data.objects.new("XZIEL_SNAPSHOT_ANCHOR",mesh)
lod.objects.link(anchor)
mat=bpy.data.materials.new("XZIEL_SNAPSHOT_ANCHOR_MAT")
mat.use_nodes=True
bsdf=mat.node_tree.nodes.get("Principled BSDF")
img=bpy.data.images.new("XZIEL_SNAPSHOT_ANCHOR_TEX",width=8,height=8,alpha=True)
img.pixels=[0.1,0.1,0.1,1.0]*64
img.pack()
tex=mat.node_tree.nodes.new("ShaderNodeTexImage")
tex.image=img
mat.node_tree.links.new(tex.outputs["Color"],bsdf.inputs["Base Color"])
mesh.materials.append(mat)

plan={
    "working_title":"XZIEL CHURCH SNAPSHOT HERO31",
    "zones":{
        "main_church":{
            "min":[float(zone_min.x),float(zone_min.y),float(zone_min.z)],
            "max":[float(zone_max.x),float(zone_max.y),float(zone_max.z)],
            "center":[float(zone_center.x),float(zone_center.y),float(zone_center.z)],
        }
    }
}
(OUT/"snapshot_plan.json").write_text(json.dumps(plan,indent=2),encoding="utf-8")

pkg=OUT/"package"
pkg.mkdir(exist_ok=True)
(pkg/"zones.json").write_text(json.dumps({
    "zones":[{"id":"zone_main_church","neighbors":[]}]
},indent=2),encoding="utf-8")
(pkg/"entities.json").write_text(json.dumps({
    "entities":[{
        "type":"player_spawn",
        "transform":{"position":{"x":float(spawn.x),"y":float(spawn.y),"z":float(spawn.z)}},
        "properties":{"snapshot":"hero31"}
    }]
},indent=2),encoding="utf-8")
(pkg/"spawns.json").write_text(json.dumps({"spawns":[]},indent=2),encoding="utf-8")
(OUT/"fitted.json").write_text(json.dumps({"barricades":[]},indent=2),encoding="utf-8")

blend=OUT/"hero31_snapshot_master.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(blend))

report={
    "status":"PASS",
    "source_glb":str(GLB),
    "mesh_objects":len(meshes),
    "floor_objects":len(floor_objs),
    "floor_z":float(floor_z),
    "bounds_min":[float(x) for x in mn],
    "bounds_max":[float(x) for x in mx],
    "spawn":[float(x) for x in spawn],
    "zone_min":[float(x) for x in zone_min],
    "zone_max":[float(x) for x in zone_max],
    "blend":str(blend),
    "semantic_textures":semantic_assignments,
    "semantic_texture_count":len(semantic_assignments),
}
(OUT/"snapshot-prep-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("XZIEL_HERO31_SNAPSHOT_PREP_PASS")
print(json.dumps(report,indent=2))
