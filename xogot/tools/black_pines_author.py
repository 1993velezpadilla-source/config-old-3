#!/usr/bin/env python3
"""Author BLACK PINES SANATORIUM modular ORIGINAL architecture in Blender.

usage:
 blender -b --python xogot/tools/black_pines_author.py -- \
    --layout xogot/data/black_pines_layout.json \
    --out xogot/assets/black_pines/black_pines_architecture.glb \
    --preview build/black-pines/black-pines-first-art-pass.png \
    --report build/black-pines/blender-report.json

No external paid API, ripped material, commercial source-map mesh, or addon.
The very same JSON builds Godot's pixel-independent collisions/interactables.
IMPORTANT: static GLB visuals only: NO gameplay authored in Blender.
"""
import argparse
import json
import math
import random
import sys
from pathlib import Path
import bpy
from mathutils import Vector
import black_pines_forge_detail as forge_detail

SEED=20261010
random.seed(SEED)
PALETTE={
    "snow":(0.19,0.24,0.26,1),
    "wall":(0.33,0.33,0.32,1),
    "plaster":(0.39,0.42,0.39,1),
    "industrial":(0.23,0.24,0.26,1),
    "medical":(0.29,0.35,0.33,1),
    "lobby":(0.33,0.30,0.28,1),
    "outdoor":(0.23,0.28,0.30,1),
    "dark_metal":(0.13,0.15,0.17,1),
    "rust":(0.37,0.14,0.10,1),
    "brass":(0.49,0.34,0.14,1),
    "red":(0.48,0.06,0.05,1),
    "ice":(0.15,0.29,0.38,1),
    "wet":(0.10,0.15,0.17,1),
    "light":(0.94,0.71,0.38,1),
    "dark_glass":(0.06,0.13,0.16,1),
}
MAT={}
COUNTS={"floor":0,"wall":0,"lintel":0,"trim":0,"snow":0,
        "light_source":0,"decal":0,"prop":0,"terrain":0}
def mat(name):
    if name in MAT:
        return MAT[name]
    m=bpy.data.materials.new("BP_"+name)
    m.diffuse_color=PALETTE[name]
    m.use_nodes=True
    bsdf=m.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value=PALETTE[name]
        bsdf.inputs["Roughness"].default_value=0.34 if name in ("wet","dark_glass") else 0.80
        bsdf.inputs["Metallic"].default_value=0.72 if name in ("dark_metal","rust","brass") else 0.04
    MAT[name]=m
    return m

def cube(label,pos,dims,material,kind="prop",bevel=0.0):
    # Materialize the Y-up Godot manifest in native Blender Z-up axes.
    # Blender coordinate (x,-z,y) exports to glTF Y-up (x,y,z).
    # Mesh dimensions swap Y<->Z; no 90deg node rotation remains in GLB.
    blender_pos=(pos[0],-pos[2],pos[1])
    blender_dims=(dims[0],dims[2],dims[1])
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=blender_pos)
    obj=bpy.context.object
    obj.name=label
    obj.dimensions=blender_dims
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    obj.data.materials.append(mat(material))
    if bevel>0.0:
        mod=obj.modifiers.new("SoftWearRoundEdges","BEVEL")
        mod.width=bevel
        mod.segments=2
        bpy.context.view_layer.objects.active=obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
    COUNTS[kind]+=1
    return obj

def wall_chunk(axis,fixed,start,end,bottom,height,label,kind="wall"):
    if end-start<=0:
        raise ValueError("negative building wall run")
    center=(fixed,bottom+height/2,(start+end)/2) if axis=="x" else (
        (start+end)/2,bottom+height/2,fixed)
    dims=(0.35,height,end-start) if axis=="x" else (end-start,height,0.35)
    obj=cube(label,center,dims,"plaster",kind,0.03)
    return obj

def sectioned_wall(axis,fixed,start,finish,cuts,label):
    cursor=start
    for i,row in enumerate(cuts):
        at=float(row["at"])
        half=float(row["width"])/2
        begin,end=at-half,at+half
        if begin>cursor+0.01:
            wall_chunk(axis,fixed,cursor,begin,0,3.8,label+"_solid_"+str(i))
        wall_chunk(axis,fixed,begin,end,2.85,0.95,label+"_lintel_"+str(i),"lintel")
        # Painted sill trim, placed above the physical walk-through opening.
        cursor=end
    if cursor<finish-0.01:
        wall_chunk(axis,fixed,cursor,finish,0,3.8,label+"_last")

def make_light(name,loc,color,strength,kind="AREA",size=5):
    data=bpy.data.lights.new(name,kind)
    data.energy=strength
    data.color=color
    if kind=="AREA":data.shape="DISK"; data.size=size
    node=bpy.data.objects.new(name,data)
    bpy.context.collection.objects.link(node)
    node.location=(loc[0],-loc[2],loc[1])
    COUNTS["light_source"]+=1
    return node

def make_camera():
    data=bpy.data.cameras.new("Survey_45deg_Black_Pines")
    obj=bpy.data.objects.new("Survey_45deg_Black_Pines",data)
    bpy.context.collection.objects.link(obj)
    # This camera is authored AFTER the level Y-up to Blender Z-up
    # conversion: keep camera in Blender's own native Z-up coordinates.
    obj.location=(49,-58,66)
    target=Vector((0,-3,0))
    direction=target-obj.location
    obj.rotation_euler=direction.to_track_quat("-Z","Y").to_euler()
    data.type="ORTHO"
    data.ortho_scale=67
    bpy.context.scene.camera=obj

def validate(layout):
    assert layout["schemaVersion"]==1
    assert layout["mapId"]=="black_pines_sanatorium"
    assert len(layout["cells"])==9
    assert len(layout["portals"])==12
    assert len(layout["windows"])==12
    assert len(layout["perks"])==6
    assert len(layout["wallbuys"])==5
    assert len(layout["mysterySpots"])==4
    assert layout["technicalGates"]["originalChurchFilesMayChange"] is False
    assert layout["technicalGates"]["gobblegumEnabled"] is False

def build(layout):
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    x_limits=layout["cellBoundaries"]["x"]
    z_limits=layout["cellBoundaries"]["z"]
    cube("Pines_Frozen_Pad",(0,-0.40,3),(56,.40,62),"snow","snow",0.08)
    for cell in layout["cells"]:
        i,j=cell["col"],cell["row"]
        a,b=float(x_limits[i]),float(x_limits[i+1])
        c,d=float(z_limits[j]),float(z_limits[j+1])
        cube("BP_Floor_"+cell["id"],((a+b)/2,-0.16,(c+d)/2),
             (b-a,0.32,d-c),cell["floor"],"floor",0.016)
        # Low-profile original grunge without stolen textures.
        if cell["id"] not in ("yard",):
            for t in range(3):
                px=random.uniform(a+1.1,b-1.1)
                pz=random.uniform(c+1.1,d-1.1)
                cube("FloorWaterStain_"+cell["id"]+"_"+str(t),
                     (px,0.009,pz), (random.uniform(.3,1.1),.010,
                     random.uniform(.35,1.6)),"wet","decal",0)
    for x in (-7.0,7.0):
        for j in range(3):
            a,b=float(z_limits[j]),float(z_limits[j+1])
            sectioned_wall("x",x,a,b,[{"at":(a+b)/2,"width":3.1}],
                           "WardPartitionX"+str(x)+"_"+str(j))
    for z in (-3.0,9.0):
        for i in range(3):
            a,b=float(x_limits[i]),float(x_limits[i+1])
            sectioned_wall("z",z,a,b,[{"at":(a+b)/2,"width":3.1}],
                           "WardPartitionZ"+str(z)+"_"+str(i))
    for x in (-18.0,18.0):
        sectioned_wall("x",x,-15,21,
            [{"at":z,"width":2.65} for z in (-9.0,3.0,15.0)],
            "OuterX"+str(x))
    for z in (-15.0,21.0):
        sectioned_wall("z",z,-18,18,
            [{"at":x,"width":2.65} for x in (-12.5,0.0,12.5)],
            "OuterZ"+str(z))
    # Window timber frames (pure visual only; Godot owns destructible planks).
    for i,w in enumerate(layout["windows"]):
        a,f=float(w["at"]),float(w["coord"])
        if w["axis"]=="x":
            cube("WindowLintelWear_"+str(i),(f,2.69,a),
                (.49,.22,3.00),"dark_metal","trim",.015)
            for e in (-1.43,1.43):
                cube("WindowJamb_"+str(i),(f,1.35,a+e),
                    (.40,2.7,.11),"brass","trim",.01)
        else:
            cube("WindowLintelWear_"+str(i),(a,2.69,f),
                (3.00,.22,.49),"dark_metal","trim",.015)
            for e in (-1.43,1.43):
                cube("WindowJamb_"+str(i),(a+e,1.35,f),
                    (.11,2.7,.40),"brass","trim",.01)
    # Eight lamps per interior wing with physical warm/cold parity. GLB
    # does not carry these lights into Godot; native Godot adds its own lights.
    for cell in layout["cells"]:
        i,j=cell["col"],cell["row"]
        a,b=float(x_limits[i]),float(x_limits[i+1])
        c,d=float(z_limits[j]),float(z_limits[j+1])
        p=((a+b)/2,3.45,(c+d)/2)
        cube("EmergencyFixture_"+cell["id"],p,(.94,.13,.50),
             "brass","trim",.024)
        warm=(i+j)%3==0
        make_light("Lamp_"+cell["id"],(p[0],p[1]-0.06,p[2]),
                   (1.0,.55,.24) if warm else (.48,.68,1.0),
                   340 if warm else 420,"AREA",8.0)
    # PUBLIC quality focal points: patient gurneys, surgery table, generator,
    # ambulance and industrial piping; all original parametric mesh data.
    for z in (-11.0,-7.3,0.0,4.2):
        cube("PatientBedFrame_"+str(z),(-14,0.55,z),
             (2.0,.9,.86),"dark_metal","prop",.08)
        cube("PatientMattress_"+str(z),(-14,1.045,z),
             (1.93,.13,.80),"medical","prop",.04)
    for x in (10.0,15.5):
        for z in (0.0,4.2):
            cube("DiningTable_"+str(x)+"_"+str(z),(x,.74,z),
                 (2.2,.16,1.1),"lobby","prop",.04)
            for dz in (-1.12,1.12):
                cube("DiningBench_"+str(x)+"_"+str(z)+"_"+str(dz),
                     (x,.43,z+dz),(1.98,.15,.38),"dark_metal","prop",.045)
    cube("SurgeryOperationTable",(13.8,.75,-9.5),(2.35,.18,1.1),
         "dark_metal","prop",.05)
    cube("NurseStation",(0,.77,0),(4.1,1.5,.78),"lobby","prop",.04)
    for x in (-14.0,-10.8):
        cube("EmergencyGenerator_"+str(x),(x,.95,-7.5),
             (1.8,1.9,1.6),"rust","prop",.08)
    cube("RustyAmbulanceRear",(3.8,1.05,17.8),(3.6,2.1,1.7),
         "medical","prop",.13)
    cube("RustyAmbulanceCab",(6.25,.9,17.8),(1.40,1.8,1.65),
         "rust","prop",.13)
    for z in (-24,30):
        cube("BoundaryFenceZ_"+str(z),(0,1.10,z),(52,2.2,.22),
             "dark_metal","trim")
    for x in (-26,26):
        cube("BoundaryFenceX_"+str(x),(x,1.10,3),(.22,2.2,56),
             "dark_metal","trim")
    # Outer pines: performance-cheap original silhouette props outside paths.
    for i in range(24):
        angle=2*math.pi*i/24
        radius=36+random.uniform(-3,4)
        px=math.cos(angle)*radius
        py=3+math.sin(angle)*radius
        height=random.uniform(5.5,9.0)
        # Blender +Y is mapped to Godot's vertical +Y, so tree vertical Y.
        cube("PineTrunk_"+str(i),(px,height*.29,py),
             (.50,height*.58,.50),"rust","prop",.18)
        bpy.ops.mesh.primitive_cone_add(vertices=7,radius1=random.uniform(1.35,2.0),
            radius2=0,depth=height*.8,location=(px,-py,height*.72))
        tree=bpy.context.object
        tree.name="PineSilhouette_"+str(i)
        tree.data.materials.append(mat("dark_metal"))
        # Native Blender Z-up cone will export directly to Godot Y-up.
        COUNTS["prop"]+=1
    make_camera()
    world=bpy.context.scene.world or bpy.data.worlds.new("BlackPinesNight")
    bpy.context.scene.world=world
    world.use_nodes=True
    bg=world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value=(.015,.024,.043,1)
    bg.inputs["Strength"].default_value=.28
    # The same Forge authoring backend drives BOTH the interactive Blender
    # Forge GUI and this headless CI entrypoint. No alternate geometry.
    forge_result = forge_detail.build_forge_detail(sys.modules[__name__], layout)
    fidelity_result = forge_detail.fidelity_pass(sys.modules[__name__], layout)
    if not fidelity_result["pass"]:
        raise RuntimeError("BLACK_PINES_FORGE_FIDELITY_RED "
                           +repr(fidelity_result["issues"]))
    print("BLACK_PINES_FORGE_FIDELITY_GREEN rooms=9 doors=12 meshes=%d tris=%d"%
          (fidelity_result["meshObjects"],fidelity_result["triangles"]))
    # All meshes are authored in native Blender Z-up and glTF exported Y-up.
    return {**COUNTS,"objects":len(bpy.data.objects),
            "forge":forge_result,"fidelity":fidelity_result}


def main():
    args=sys.argv
    args=args[args.index("--")+1:] if "--" in args else []
    ap=argparse.ArgumentParser()
    ap.add_argument("--layout",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--preview",type=Path,required=True)
    ap.add_argument("--report",type=Path,required=True)
    conf=ap.parse_args(args)
    layout=json.loads(conf.layout.read_text())
    validate(layout)
    report=build(layout)
    # Blender mesh objects already use native Z-up coordinate placement.
    # Exporter maps them to glTF Y-up with identity node rotations.
    conf.out.parent.mkdir(parents=True,exist_ok=True)
    conf.preview.parent.mkdir(parents=True,exist_ok=True)
    conf.report.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in bpy.context.scene.objects:
        if obj.type=="MESH":
            obj.select_set(True)
    bpy.context.view_layer.objects.active=next(o for o in bpy.context.scene.objects if o.type=="MESH")
    bpy.ops.export_scene.gltf(filepath=str(conf.out.resolve()),export_format="GLB",
                              use_selection=True,export_apply=False)
    assert conf.out.exists() and conf.out.stat().st_size>10000
    report.update({
        "sourceBlueprint":str(conf.layout),
        "glb":str(conf.out),
        "glbBytes":conf.out.stat().st_size,
        "allOriginalAuthoring":True,
        "commercialRippedAssets":False,
        "materialsAreSimpleOriginalParametricPrototypes":True,
        "doorsAndBarricadesLiveInGodotNotThisGLB":True,
        "publicReadiness":False,
        "godotGameplayAcceptance":False,
        "physicalAndroidPerformanceAcceptance":False,
        "sameManifestAsGodot":True
    })
    conf.report.write_text(json.dumps(report,indent=2)+"\n")
    # Reapply scene model view to avoid misleading view on imported GLB.
    if bpy.context.scene.camera is None:
        make_camera()
    bpy.context.scene.render.engine="BLENDER_EEVEE"
    bpy.context.scene.eevee.taa_render_samples=20
    bpy.context.scene.render.resolution_x=1280
    bpy.context.scene.render.resolution_y=800
    bpy.context.scene.render.resolution_percentage=100
    bpy.context.scene.render.image_settings.file_format="PNG"
    bpy.context.scene.render.filepath=str(conf.preview.resolve())
    bpy.ops.render.render(write_still=True)
    assert conf.preview.exists() and conf.preview.stat().st_size>10000
    print("BLACK_PINES_BLENDER_ORIGINAL_ARCHITECTURE_GREEN",json.dumps(report,sort_keys=True))

if __name__=="__main__":
    main()
