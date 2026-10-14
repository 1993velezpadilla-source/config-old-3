#!/usr/bin/env python3
"""MP40 original NZ:P authoring mesh -> glove-first ORIGINAL-rig visual prototype.

No BO3 mesh, no inferred hand poses, and no weapon/animation retargeting.
Keep the authored weapon faces and ALL original hand/finger bone weights.
Turn the 364 original hand+arm triangles into 1456 small triangles (one
edge subdivision), shade the glove fingers smoothly, and preview on the
unchanged 83-frame source action. NOT a shipping Android asset.
"""
import bpy,bmesh,json,math,sys
from collections import Counter
from pathlib import Path
from mathutils import Vector

args=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
if len(args)!=2:raise SystemExit("USAGE -- <original-stock-mp40-skin.png> <output-dir>")
original_skin,out=map(lambda p:Path(p).resolve(),args)
if not original_skin.is_file():raise SystemExit("GLOVES_RED missing original hand/weapon image")
out.mkdir(parents=True,exist_ok=True)
stock=bpy.data.objects.get("nzp_hands.ms3d.mo")
if stock is None or stock.type!="MESH":raise SystemExit("GLOVES_RED authored gun+hands missing")
arms=[o for o in bpy.data.objects if o.type=="ARMATURE"]
if len(arms)!=1 or not arms[0].animation_data or not arms[0].animation_data.action:
    raise SystemExit("GLOVES_RED original animated rig missing")
rig=arms[0]
groups={g.index:g.name for g in stock.vertex_groups}
weapon_bones={"Body","Clip","Slide"}
original_triangles=sum(len(p.vertices)-2 for p in stock.data.polygons)
if original_triangles!=881:raise SystemExit("GLOVES_RED MP40 source changed: "+str(original_triangles))
is_weapon=[]
for face in stock.data.polygons:
    weights=Counter()
    for vi in face.vertices:
        for link in stock.data.vertices[vi].groups:
            if link.weight>0.01:weights[groups[link.group]]+=float(link.weight)
    is_weapon.append(weights.most_common(1)[0][0] in weapon_bones if weights else False)
source_gun=sum((len(p.vertices)-2) for p,w in zip(stock.data.polygons,is_weapon) if w)
source_hand=original_triangles-source_gun
if (source_gun,source_hand)!=(517,364):
    raise SystemExit("GLOVES_RED unexpected original gun/hand identity: "+repr((source_gun,source_hand)))

def keep_faces(name,keep):
    obj=stock.copy();obj.data=stock.data.copy();obj.name=name
    bpy.context.collection.objects.link(obj)
    obj.matrix_world=stock.matrix_world.copy()
    bm=bmesh.new();bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    remove=[face for i,face in enumerate(bm.faces) if not keep(is_weapon[i])]
    bmesh.ops.delete(bm,geom=remove,context="FACES")
    orphans=[v for v in bm.verts if not v.link_faces]
    if orphans:bmesh.ops.delete(bm,geom=orphans,context="VERTS")
    bm.to_mesh(obj.data);bm.free()
    for modifier in obj.modifiers:
        if modifier.type=="ARMATURE":modifier.object=rig
    return obj

gloves=keep_faces("NZP_Original_Rig_Gloved_Hands",lambda weapon:not weapon)
gun=keep_faces("NZP_Original_MP40_GUN_UNCHANGED",lambda weapon:weapon)
stock.hide_render=True;stock.hide_set(True)
# Subdivide only hand and sleeve geometry. The gun's 517 triangles are never
# touched, so stock first-person grip / clip / bolt positions remain source.
bm=bmesh.new();bm.from_mesh(gloves.data)
bmesh.ops.subdivide_edges(bm,edges=list(bm.edges),cuts=1,use_grid_fill=True)
bm.to_mesh(gloves.data);bm.free();gloves.data.update()
for face in gloves.data.polygons:face.use_smooth=True
# One subtle smooth pass on hands only. This DOES NOT modify the underlying
# skeleton or poses. Review frame renders before considering an export.
shape=gloves.modifiers.new("GloveSurfaceSoftnessVisualTest",type="SMOOTH")
shape.factor=.12;shape.iterations=1

def material(name,color,roughness=.85,fabric=False):
    mat=bpy.data.materials.new(name);mat.use_nodes=True
    shader=mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value=(*color,1)
    shader.inputs["Roughness"].default_value=roughness
    if fabric:
        tex=mat.node_tree.nodes.new("ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value=115
        tex.inputs["Detail"].default_value=2
        bump=mat.node_tree.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value=.14
        bump.inputs["Distance"].default_value=.006
        mat.node_tree.links.new(tex.outputs["Fac"],bump.inputs["Height"])
        mat.node_tree.links.new(bump.outputs["Normal"],shader.inputs["Normal"])
    return mat
glove_mat=material("WW2_Glove_Fabric_DarkOlive",(0.075,.093,.064),fabric=True)
sleeve_mat=material("WW2_Sleeve_FieldOlive",(.145,.17,.10),fabric=True)
gloves.data.materials.clear()
gloves.data.materials.append(glove_mat);gloves.data.materials.append(sleeve_mat)
glove_areas=Counter()
for face in gloves.data.polygons:
    tally=Counter()
    for vi in face.vertices:
        for link in gloves.data.vertices[vi].groups:
            if link.weight>.01:
                name=groups.get(link.group,"")
                category="sleeve" if "_Arm" in name else "glove"
                tally[category]+=float(link.weight)
    category=tally.most_common(1)[0][0] if tally else "glove"
    face.material_index=1 if category=="sleeve" else 0
    glove_areas[category]+=1
if glove_areas["glove"]<100 or glove_areas["sleeve"]<20:
    raise SystemExit("GLOVES_RED finger / sleeve ownership insufficient "+str(glove_areas))
skin=bpy.data.images.load(str(original_skin),check_existing=True)
gunmat=bpy.data.materials.new("NZP_MP40_ORIGINAL_SKIN_UNCHANGED")
gunmat.use_nodes=True
tex=gunmat.node_tree.nodes.new("ShaderNodeTexImage");tex.image=skin
shader=gunmat.node_tree.nodes.get("Principled BSDF")
gunmat.node_tree.links.new(tex.outputs["Color"],shader.inputs["Base Color"])
shader.inputs["Roughness"].default_value=.66
gun.data.materials.clear();gun.data.materials.append(gunmat)

def tri(obj):return sum(len(f.vertices)-2 for f in obj.data.polygons)
if tri(gloves)!=source_hand*4 or tri(gun)!=source_gun:
    raise SystemExit("GLOVES_RED triangle conservation failed "+
                     repr((tri(gloves),tri(gun))))
if len(gloves.vertex_groups)!=len(stock.vertex_groups):
    raise SystemExit("GLOVES_RED hand skin bone group identity changed")
assert sum(1 for m in gloves.modifiers if m.type=="ARMATURE")==1
assert sum(1 for m in gun.modifiers if m.type=="ARMATURE")==1
action_range=list(rig.animation_data.action.frame_range)
if action_range!=[1.,83.]:raise SystemExit("GLOVES_RED unknown source action")

# Render THREE genuine source-action frames to inspect fingers, seams, and
# magazine clearance before writing any .mdl or replacing the Android app.
scene=bpy.context.scene
for ob in bpy.data.objects:
    if ob.type=="MESH" and ob not in (gloves,gun):ob.hide_render=True
camera_data=bpy.data.cameras.new("MP40_GLOVE_AUDIT_CAMERA")
camera=bpy.data.objects.new("MP40_GLOVE_AUDIT_CAMERA",camera_data)
scene.collection.objects.link(camera);scene.camera=camera
camera_data.type="ORTHO"
scene.render.engine="BLENDER_EEVEE"
scene.render.resolution_x=1000;scene.render.resolution_y=670
scene.render.resolution_percentage=100
scene.render.image_settings.file_format="PNG"
scene.world.use_nodes=True
background=scene.world.node_tree.nodes.get("Background")
if background:background.inputs["Color"].default_value=(.12,.12,.12,1)
scene.view_settings.view_transform="Standard"
bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
points=[]
for ob in (gloves,gun):
    e=ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    tmp=e.to_mesh()
    points.extend([e.matrix_world@v.co for v in tmp.vertices])
    e.to_mesh_clear()
low=Vector(tuple(min(p[i] for p in points) for i in range(3)))
high=Vector(tuple(max(p[i] for p in points) for i in range(3)))
center=(low+high)*.5
span=(high-low).length
camera.location=center+Vector((1.15,-1.9,1.1))*span
camera.rotation_euler=(center-camera.location).to_track_quat("-Z","Y").to_euler()
camera_data.ortho_scale=span*1.8
l=bpy.data.lights.new("GloveInspectionLamp","AREA");l.energy=1400;l.size=span*3
lamp=bpy.data.objects.new("GloveInspectionLamp",l);scene.collection.objects.link(lamp)
lamp.location=center+Vector((1.5,2,2))*span
lamp.rotation_euler=(center-lamp.location).to_track_quat("-Z","Y").to_euler()
for f in [1,38,55]:
    scene.frame_set(f)
    scene.render.filepath=str(out/("MP40_GLOVE_%02d.png"%f))
    bpy.ops.render.render(write_still=True)
report={"schema":1,"experiment":"HD-gloved hands on ORIGINAL NZP MP40 and finger skeleton",
        "source_triangles":original_triangles,"original_gun_triangles":source_gun,
        "original_hands_triangles":source_hand,
        "post_glove_subdivision_hand_triangles":tri(gloves),
        "gun_triangles_unchanged":tri(gun),
        "total_triangles":tri(gloves)+tri(gun),
        "fits_default_2048_triangle_limit":tri(gloves)+tri(gun)<=2048,
        "original_bone_count":len(rig.data.bones),
        "glove_vertex_group_count":len(gloves.vertex_groups),
        "source_action_range":action_range,
        "source_animation_action":rig.animation_data.action.name,
        "procedural_blender_glove_material_not_baked":True,
        "mesh_exported_to_android":False,
        "renders":[f"MP40_GLOVE_{f:02d}.png" for f in [1,38,55]],
        "face_owner_counts":dict(glove_areas)}
(out/"mp40-gloves-prototype-report.json").write_text(json.dumps(report,indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(out/"mp40-glove-prototype-NOT-FOR-DISTRIBUTION.blend"))
print("MP40_ORIGINAL_GLOVE_TEST_GREEN",json.dumps(report))
print("MP40_GLOVE_PREVIEW_ONLY_NOT_ANDROID_OR_COMMERCIAL_CERTIFICATION")
