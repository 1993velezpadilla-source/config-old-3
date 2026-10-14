#!/usr/bin/env python3
"""Experimental Aether MP40 geometry -> NZ:P existing Blender hand rig.

Produces an INTERNAL Blender diagnostic, NOT an Android model or a game-ready
Quake MDL. It keeps stock hand animations, classifies/removes stock weapon
faces, and binds Aether gun / clip / bolt to original stock rig bone groups.
The result must still pass visual alignment, deform, export and license gates.
"""
import bpy
import bmesh
import json
import math
import sys
from collections import Counter
from mathutils import Vector
from pathlib import Path

params=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
if len(params)!=3:
    raise SystemExit("expected <aether.glb> <basecolor.png> <output-dir>")
aether,albedo,out=map(lambda p:Path(p).resolve(),params)
out.mkdir(parents=True,exist_ok=True)

stock_meshes=[o for o in bpy.data.objects if o.type=="MESH"]
stock_arms=[o for o in bpy.data.objects if o.type=="ARMATURE"]
if len(stock_meshes)!=1 or len(stock_arms)!=1:
    raise SystemExit("MP40_HYBRID_RED unexpected baseline objects")
stock=stock_meshes[0]
stock_arm=stock_arms[0]
bone_names={b.name for b in stock_arm.data.bones}
if not {"Body","Slide","Clip"}.issubset(bone_names):
    raise SystemExit("MP40_HYBRID_RED original rig does not expose gun/bolt/magazine")
stock_action=(stock_arm.animation_data.action if stock_arm.animation_data else None)
stock_original_action=stock_action.name if stock_action else "NLA_ONLY"

# A single NZ:P mesh combines hands and gun. Classify polygon ownership by
# predominant weighted bone; don't remove the user's hand/arm geometry.
gun_groups={"Body","Slide","Clip"}
labels={g.index:g.name for g in stock.vertex_groups}
is_gun=[]
for poly in stock.data.polygons:
    tally=Counter()
    for index in poly.vertices:
        for g in stock.data.vertices[index].groups:
            if g.weight>0.01:
                tally[labels[g.group]]+=g.weight
    label=tally.most_common(1)[0][0] if tally else ""
    is_gun.append(label in gun_groups)
original_triangles=sum(max(0,len(poly.vertices)-2) for poly in stock.data.polygons)
removed_triangles=sum(max(0,len(poly.vertices)-2) for poly,cut in zip(stock.data.polygons,is_gun) if cut)
remaining=original_triangles-removed_triangles
if not (60<removed_triangles<original_triangles*0.65 and remaining>original_triangles*0.45):
    raise SystemExit("MP40_HYBRID_RED gun segmentation unsafe "+
                     repr((original_triangles,removed_triangles,remaining)))
gun_verts={v for poly,cut in zip(stock.data.polygons,is_gun) if cut for v in poly.vertices}
stock_gun_points=[stock.matrix_world @ stock.data.vertices[v].co for v in gun_verts]
lo=Vector((min(p.x for p in stock_gun_points),
           min(p.y for p in stock_gun_points),
           min(p.z for p in stock_gun_points)))
hi=Vector((max(p.x for p in stock_gun_points),
           max(p.y for p in stock_gun_points),
           max(p.z for p in stock_gun_points)))
stock_center=(lo+hi)*0.5
stock_diameter=(hi-lo).length

# Copy source mesh preserving ALL old armature weights and animation setup,
# then delete only triangles predominantly belonging to stock gun/bolt/clip.
hands=stock.copy()
hands.data=stock.data.copy()
hands.name="NZP_Original_Animated_Hands_ONLY"
bpy.context.collection.objects.link(hands)
hands.matrix_world=stock.matrix_world.copy()
bm=bmesh.new()
bm.from_mesh(hands.data)
bm.faces.ensure_lookup_table()
bm.faces.index_update()
faces_to_delete=[bm.faces[i] for i,cut in enumerate(is_gun) if cut]
bmesh.ops.delete(bm,geom=faces_to_delete,context="FACES")
orphan=[v for v in bm.verts if not v.link_faces]
if orphan:
    bmesh.ops.delete(bm,geom=orphan,context="VERTS")
bm.to_mesh(hands.data)
bm.free()
stock.hide_render=True
stock.hide_set(True)

# Aether original high-density geometry: do not substitute a stock remesh.
before=set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=str(aether))
added=list(set(bpy.data.objects)-before)
aether_meshes=[o for o in added if o.type=="MESH"]
aether_arms=[o for o in added if o.type=="ARMATURE"]
if len(aether_meshes)!=1 or not aether_arms:
    raise SystemExit("MP40_HYBRID_RED imported Aether gun/rig missing")
gun=aether_meshes[0]
modern_vertex_count=len(gun.data.vertices)
modern_triangles=sum(max(0,len(p.vertices)-2) for p in gun.data.polygons)
if modern_vertex_count<3000 or modern_triangles<3000:
    raise SystemExit("MP40_HYBRID_RED high-definition Aether geometry lost")

aether_world=[gun.matrix_world @ v.co for v in gun.data.vertices]
alow=Vector((min(p.x for p in aether_world),
            min(p.y for p in aether_world),
            min(p.z for p in aether_world)))
ahigh=Vector((max(p.x for p in aether_world),
             max(p.y for p in aether_world),
             max(p.z for p in aether_world)))
acenter=(alow+ahigh)*0.5
adiam=(ahigh-alow).length
if adiam<0.001: raise SystemExit("MP40_HYBRID_RED Aether collapsed dimensions")
scale=stock_diameter/adiam
if not 1<scale<1000: raise SystemExit("MP40_HYBRID_RED implausible unit conversion "+str(scale))

# Preserve original glTF UV layouts and original PBR color map.
# Create armature-local vertex coordinates, then remap the modern influence
# group names onto the source armature that ALREADY animates the old MP40.
inverse_arm=stock_arm.matrix_world.inverted()
new_gun=gun.copy()
new_gun.data=gun.data.copy()
new_gun.name="Aether_HD_MP40_On_Vril_Rig"
bpy.context.collection.objects.link(new_gun)
world_points=[stock_center+(p-acenter)*scale for p in aether_world]
new_gun.matrix_world=stock_arm.matrix_world.copy()
for index,p in enumerate(world_points):
    new_gun.data.vertices[index].co=inverse_arm@p

# Standard glTF armature mod should no longer control this mesh.
for mod in list(new_gun.modifiers):
    if mod.type=="ARMATURE": new_gun.modifiers.remove(mod)
for group in list(new_gun.vertex_groups):
    new_gun.vertex_groups.remove(group)
modern_bones={g.index:g.name for g in gun.vertex_groups}
aliases={"j_gun":"Body","j_clip":"Clip","j_bolt":"Slide",
         "tag_brass":"Body","tag_flash":"Body",
         "viewmodel_ger_mp40_smg_LOD0_skel":"Body"}
for name in set(aliases.values()):
    new_gun.vertex_groups.new(name=name)
unowned=0
counts=Counter()
for v in gun.data.vertices:
    source_weights=Counter()
    for link in v.groups:
        original=modern_bones.get(link.group,"")
        role=aliases.get(original,"Body")
        source_weights[role]+=link.weight
    if sum(source_weights.values())<1e-6:
        unowned+=1
        source_weights["Body"]=1.0
    total=sum(source_weights.values())
    for name,value in source_weights.items():
        if value>1e-6:
            new_gun.vertex_groups[name].add([v.index],value/total,"REPLACE")
            counts[name]+=1
if unowned>int(modern_vertex_count*0.02):
    raise SystemExit("MP40_HYBRID_RED too many vertices without bone weights: "+str(unowned))

armature_mod=new_gun.modifiers.new(name="VrilOriginalAnimationAuthority",type="ARMATURE")
armature_mod.object=stock_arm

image=bpy.data.images.load(str(albedo),check_existing=True)
mat=bpy.data.materials.new("Aether_MP40_Original_Albedo_VisualOnly")
mat.use_nodes=True
bsdf=mat.node_tree.nodes.get("Principled BSDF")
tex=mat.node_tree.nodes.new("ShaderNodeTexImage")
tex.image=image
mat.node_tree.links.new(tex.outputs["Color"],bsdf.inputs["Base Color"])
new_gun.data.materials.clear()
new_gun.data.materials.append(mat)
gun.hide_render=True
gun.hide_set(True)

# The stock source animation rig is left intact. No attempt to claim
# the camera/grip aligns without viewport and Android screenshot testing.
bpy.context.scene.frame_set(1)
bpy.context.view_layer.update()
report={
    "schema":1,"status":"HYBRID_BLEND_EXPERIMENT_NOT_SHIPPING",
    "source_blend_stock_armature":stock_arm.name,
    "source_blend_original_action":stock_original_action,
    "original_source_triangles":original_triangles,
    "removed_stock_weapon_triangles":removed_triangles,
    "retained_original_hand_triangles":remaining,
    "actual_retained_hand_triangles":sum(len(p.vertices)-2 for p in hands.data.polygons),
    "aether_hd_vertices":modern_vertex_count,
    "aether_hd_triangles":modern_triangles,
    "aether_gpu_skin_weights":dict(counts),
    "unweighted_vertices_auto_body":unowned,
    "stock_to_aether_unit_scale":scale,
    "source_gun_bounds":[list(lo),list(hi)],
    "aether_gun_bounds":[list(alow),list(ahigh)],
    "old_animation_rig_reused":True,
    "aether_animation_playback_merged":False,
    "mdl_exported":False,"android_rendered":False,
    "first_person_visual_alignment_proven":False,
    "commercial_distribution_approved":False,
}
if report["actual_retained_hand_triangles"]!=remaining:
    raise SystemExit("MP40_HYBRID_RED hands triangle conservation failed")
output_blend=out/"mp40-hybrid-vril-hands-aether-gun-EXPERIMENT.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
(out/"hybrid-report.json").write_text(json.dumps(report,indent=2))
print("MP40_HYBRID_REAL_GUN_HAND_SEPARATION_GREEN",remaining,removed_triangles,modern_triangles)
print("MP40_HYBRID_ORIGINAL_NZP_ARMATURE_BONE_BIND_GREEN",dict(counts))
print("MP40_HYBRID_BLENDER_ONLY_PENDING_VIEWPORT_ALIGNMENT_AND_MDL_EXPORT")
