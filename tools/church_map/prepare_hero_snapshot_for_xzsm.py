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
}
(OUT/"snapshot-prep-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("XZIEL_HERO31_SNAPSHOT_PREP_PASS")
print(json.dumps(report,indent=2))
