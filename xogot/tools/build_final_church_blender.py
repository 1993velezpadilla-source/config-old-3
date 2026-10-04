import bpy
import json
import math
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "build" / "final-church-blender"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_GLB = OUT_DIR / "church_final_architecture.glb"
REPORT = OUT_DIR / "church_final_architecture.report.json"
BLEND = OUT_DIR / "church_final_architecture.blend"
RENDER_DIR = OUT_DIR / "renders"
RENDER_DIR.mkdir(parents=True, exist_ok=True)

# Author in gameplay meters. Blender uses Z-up; Godot/glTF uses Y-up.
# This transform makes (x, y_up, z_depth) land as expected after glTF export.
def B(x, y, z):
    return (x, -z, y)

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def mat(name, color, rough=0.8, metallic=0.0, emission=None, emission_strength=0.0):
    m=bpy.data.materials.new(name)
    m.diffuse_color=(*color,1.0)
    m.use_nodes=True
    bsdf=m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value=(*color,1.0)
    bsdf.inputs["Roughness"].default_value=rough
    bsdf.inputs["Metallic"].default_value=metallic
    if emission is not None:
        # Blender 3.x/4.x compatibility.
        if "Emission" in bsdf.inputs:
            bsdf.inputs["Emission"].default_value=(*emission,1.0)
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value=(*emission,1.0)
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value=emission_strength
    return m

MATS={}

def make_materials():
    MATS["stone"]=mat("Stone_Mid",(0.105,0.098,0.086),0.92)
    MATS["stone_dark"]=mat("Stone_Dark",(0.055,0.052,0.048),0.96)
    MATS["trim"]=mat("Stone_Trim",(0.165,0.150,0.125),0.82)
    MATS["wood"]=mat("Old_Dark_Wood",(0.065,0.030,0.013),0.78)
    MATS["roof"]=mat("Slate_Roof",(0.025,0.030,0.038),0.90)
    MATS["metal"]=mat("Aged_Metal",(0.090,0.068,0.045),0.55,0.55)
    MATS["glass_blue"]=mat("StainedGlass_Blue",(0.055,0.18,0.42),0.32,0.05,(0.04,0.16,0.55),1.8)
    MATS["glass_red"]=mat("StainedGlass_Red",(0.42,0.045,0.035),0.32,0.05,(0.60,0.045,0.025),1.5)
    MATS["glass_gold"]=mat("StainedGlass_Gold",(0.42,0.22,0.045),0.35,0.05,(0.60,0.28,0.035),1.4)

def set_mat(obj,key):
    obj.data.materials.clear()
    obj.data.materials.append(MATS[key])
    obj["xz_material_group"]=key

def add_box(name,size,pos,material="stone",bevel=0.05,rot=(0,0,0)):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=B(*pos))
    o=bpy.context.object
    o.name=name
    # Blender dimensions correspond x, -z(depth), y(up)
    o.dimensions=(size[0],size[2],size[1])
    o.rotation_euler=(math.radians(rot[0]),math.radians(rot[2]),math.radians(-rot[1]))
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if bevel>0:
        mod=o.modifiers.new("SoftStoneEdges","BEVEL")
        mod.width=bevel
        mod.segments=3
        mod.limit_method="ANGLE"
        bpy.context.view_layer.objects.active=o
        bpy.ops.object.modifier_apply(modifier=mod.name)
    set_mat(o,material)
    return o

def add_cylinder(name,radius,height,pos,material="stone",verts=16,bevel=0.03):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=height, location=B(*pos))
    o=bpy.context.object
    o.name=name
    # cylinder defaults along Blender Z, which maps to Godot Y as desired.
    if bevel>0:
        mod=o.modifiers.new("CylinderBevel","BEVEL")
        mod.width=bevel
        mod.segments=2
        bpy.context.view_layer.objects.active=o
        bpy.ops.object.modifier_apply(modifier=mod.name)
    set_mat(o,material)
    return o

def add_arch_curve(name,half_width,spring_y,apex_y,z,depth=0.16,material="trim",resolution=18):
    # Pointed gothic arch: two quadratic arcs meeting at apex.
    pts=[]
    # left jamb spring -> apex
    for i in range(resolution+1):
        t=i/resolution
        # Quadratic Bezier gives a sharper gothic shoulder than a semicircle.
        x=(1-t)*(1-t)*(-half_width)+2*(1-t)*t*(-half_width*0.52)+t*t*0.0
        y=(1-t)*(1-t)*spring_y+2*(1-t)*t*(apex_y*0.89)+t*t*apex_y
        pts.append((x,y,z))
    # apex -> right jamb spring
    for i in range(1,resolution+1):
        t=i/resolution
        x=(1-t)*(1-t)*0.0+2*(1-t)*t*(half_width*0.52)+t*t*half_width
        y=(1-t)*(1-t)*apex_y+2*(1-t)*t*(apex_y*0.89)+t*t*spring_y
        pts.append((x,y,z))

    curve=bpy.data.curves.new(name+"_Curve","CURVE")
    curve.dimensions="3D"
    curve.resolution_u=1
    curve.bevel_depth=depth
    curve.bevel_resolution=2
    spl=curve.splines.new("POLY")
    spl.points.add(len(pts)-1)
    for p,co in zip(spl.points,pts):
        b=B(*co)
        p.co=(b[0],b[1],b[2],1.0)
    o=bpy.data.objects.new(name,curve)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(MATS[material])
    o["xz_material_group"]=material
    return o

def add_pointed_window_frame(name,x,z,side,scale=1.0,glass=False):
    # Window opening baseline around current zombie aperture: 2.8m wide x 3.35m high.
    w=1.55*scale
    spring=2.05*scale
    apex=3.55*scale
    frame_depth=0.15
    # jambs
    add_box(name+"_JambA",(0.22,2.10*scale,0.26),(x,1.05*scale,z-w), "trim",0.025)
    add_box(name+"_JambB",(0.22,2.10*scale,0.26),(x,1.05*scale,z+w), "trim",0.025)
    # sill
    add_box(name+"_Sill",(0.28,0.18,3.35*scale),(x,0.16,z),"trim",0.025)
    # arch in plane x fixed: author curve in local X/Z then rotate to side wall.
    arch=add_arch_curve(name+"_Arch",w,spring,apex,0.0,frame_depth,"trim",18)
    # Curve initially spans Godot X/Y at z=0. Rotate around Godot Y to lie along depth/up plane and place at wall x.
    # In Blender: rotate around Z then position via B.
    arch.rotation_euler[2]=math.radians(90.0 if side<0 else -90.0)
    arch.location=Vector(B(x,0,z))
    if glass:
        # Thin stained glass plate inset behind frame.
        add_box(name+"_Glass",(0.08,2.65*scale,2.55*scale),(x-(0.10*side),1.55*scale,z),
                "glass_blue" if int(abs(z))%3==0 else ("glass_red" if side>0 else "glass_gold"),0.01)

def add_rib_vault(z):
    # Two diagonal ribs from wall spring to center boss.
    y0=5.45; y1=7.55
    # Curves in x/y(up), fixed depth z.
    for side in (-1,1):
        curve=bpy.data.curves.new(f"VaultRib_{z}_{side}_Curve","CURVE")
        curve.dimensions="3D"; curve.bevel_depth=0.10; curve.bevel_resolution=2
        spl=curve.splines.new("BEZIER"); spl.bezier_points.add(2)
        coords=[
            (9.7*side,y0,z),
            (5.0*side,7.25,z),
            (0.0,y1,z),
        ]
        for bp,co in zip(spl.bezier_points,coords):
            bp.co=B(*co); bp.handle_left_type="AUTO"; bp.handle_right_type="AUTO"
        o=bpy.data.objects.new(f"VaultRib_{'L' if side<0 else 'R'}_{z}",curve)
        bpy.context.collection.objects.link(o); o.data.materials.append(MATS["trim"]); o["xz_material_group"]="trim"
    add_cylinder(f"VaultBoss_{z}",0.23,0.24,(0,y1,z),"trim",12,0.02)

def add_roof_panel(name,x,rot_z_deg,size,zcenter=-5.0):
    # Long roof slab. rot_z_deg here means slope around Godot Z, which maps to Blender X.
    o=add_box(name,size,(x,9.65,zcenter),"roof",0.04)
    o.rotation_euler[1]=0.0
    # slope across church width: Blender Y/Z relation -> rotate around Blender Y?
    # Simpler visual gable: rotate around Blender Y which maps to Godot Z.
    o.rotation_euler[1]=math.radians(rot_z_deg)
    return o

def build_nave():
    # Base courses and cornices.
    add_box("NaveBaseCourse_L",(0.42,0.52,37.0),(-10.63,0.40,-5.0),"stone_dark",0.04)
    add_box("NaveBaseCourse_R",(0.42,0.52,37.0),(10.63,0.40,-5.0),"stone_dark",0.04)
    add_box("NaveStringCourse_L",(0.35,0.20,37.0),(-10.58,2.28,-5.0),"trim",0.035)
    add_box("NaveStringCourse_R",(0.35,0.20,37.0),(10.58,2.28,-5.0),"trim",0.035)
    add_box("NaveCornice_L",(0.46,0.30,37.0),(-10.58,5.58,-5.0),"trim",0.045)
    add_box("NaveCornice_R",(0.46,0.30,37.0),(10.58,5.58,-5.0),"trim",0.045)

    pier_z=[-20.5,-13.0,-5.0,3.0,10.0]
    for iz,z in enumerate(pier_z):
        for side in (-1,1):
            x=10.35*side
            tag=f"{'L' if side<0 else 'R'}_{iz:02d}"
            add_cylinder("NavePilaster_"+tag,0.31,4.65,(x,2.85,z),"stone",16,0.025)
            add_box("NavePilasterBase_"+tag,(0.95,0.38,0.98),(x,0.42,z),"stone_dark",0.06)
            add_box("NavePilasterCapital_"+tag,(0.92,0.34,0.95),(x,5.18,z),"trim",0.06)
            add_box("NavePilasterAbacus_"+tag,(1.08,0.17,1.08),(x,5.43,z),"trim",0.04)

    for i,z in enumerate([-17.0,-9.0,-1.0,7.0]):
        add_pointed_window_frame(f"ZombieWindow_L_{i:02d}",-10.72,z,-1,1.0,False)
        add_pointed_window_frame(f"ZombieWindow_R_{i:02d}",10.72,z,1,1.0,False)

    # Upper clerestory decorative windows: true gothic rhythm, visual-only.
    for i,z in enumerate([-19.0,-13.0,-7.0,-1.0,5.0,10.0]):
        for side in (-1,1):
            x=10.69*side
            add_pointed_window_frame(f"Clerestory_{'L' if side<0 else 'R'}_{i:02d}",x,z,side,0.55,True)

    for z in [-18.0,-12.0,-6.0,0.0,6.0,11.0]:
        add_rib_vault(z)

    # Timber roof truss rhythm, with angled braces.
    for i,z in enumerate([-18.0,-12.0,-6.0,0.0,6.0,11.0]):
        add_box(f"RoofTie_{i:02d}",(18.8,0.22,0.28),(0,6.30,z),"wood",0.025)
        add_box(f"RoofKingPost_{i:02d}",(0.24,2.4,0.24),(0,7.45,z),"wood",0.025)
        add_box(f"RoofBraceL_{i:02d}",(7.1,0.22,0.25),(-3.45,7.25,z),"wood",0.025,(0,0,-19))
        add_box(f"RoofBraceR_{i:02d}",(7.1,0.22,0.25),(3.45,7.25,z),"wood",0.025,(0,0,19))

    # Exterior stepped buttresses.
    for i,z in enumerate([-19.0,-11.0,-3.0,5.0,12.0]):
        for side in (-1,1):
            x=11.75*side
            tag=f"{'L' if side<0 else 'R'}_{i:02d}"
            add_box("ButtressFoot_"+tag,(1.65,1.30,2.25),(x,0.72,z),"stone_dark",0.08)
            add_box("ButtressBody_"+tag,(1.28,3.65,1.85),(x,2.55,z),"stone",0.07)
            add_box("ButtressShoulder_"+tag,(1.10,0.75,1.60),(x,4.68,z),"trim",0.06)
            # small cap slope simulated with beveled cap
            add_box("ButtressCap_"+tag,(1.18,0.25,1.68),(x,5.12,z),"trim",0.07)

def build_front_tower():
    # Nested entrance portal at z=14/front.
    for idx,(w,spring,apex,depth) in enumerate([
        (2.55,3.20,5.75,0.22),
        (2.20,3.10,5.35,0.18),
        (1.85,3.00,4.95,0.14),
    ]):
        add_box(f"PortalJambL_{idx}",(0.34,spring,0.48),(-w,spring*0.5,13.62-idx*0.08),"trim",0.045)
        add_box(f"PortalJambR_{idx}",(0.34,spring,0.48),(w,spring*0.5,13.62-idx*0.08),"trim",0.045)
        add_arch_curve(f"PortalArch_{idx}",w,spring,apex,13.62-idx*0.08,depth,"trim",24)

    # Tower facade overlays.
    for side in (-1,1):
        x=3.15*side
        add_box(f"TowerCornerPier_{side}",(1.0,11.8,1.0),(x,6.2,10.9),"stone_dark",0.09)
        add_box(f"TowerCornerBase_{side}",(1.35,0.55,1.35),(x,0.48,10.9),"trim",0.09)
        add_box(f"TowerCornerCap_{side}",(1.28,0.38,1.28),(x,11.72,10.9),"trim",0.08)

    add_box("TowerBeltCourse",(6.9,0.34,5.5),(0,9.65,10.9),"trim",0.06)
    add_box("TowerUpperCornice",(6.3,0.42,5.4),(0,14.15,10.9),"trim",0.07)

    # Bell/rose window frame on front face.
    add_arch_curve("TowerFrontBellArch",1.48,10.7,13.2,13.50,0.20,"trim",24)
    add_cylinder("TowerRoseOuter",1.05,0.20,(0,11.62,13.42),"trim",32,0.03)
    add_cylinder("TowerRoseInner",0.72,0.18,(0,11.62,13.31),"stone_dark",32,0.02)

    # Small pinnacles.
    for x in (-2.9,2.9):
        add_cylinder(f"TowerPinnacleBase_{x}",0.32,0.75,(x,14.7,11.0),"trim",12,0.03)
        bpy.ops.mesh.primitive_cone_add(vertices=12,radius1=0.32,radius2=0.0,depth=1.55,location=B(x,15.8,11.0))
        o=bpy.context.object; o.name=f"TowerPinnacle_{x}"; set_mat(o,"stone_dark")

def build_sanctuary():
    add_box("SanctuaryBackFrame",(7.15,5.25,0.42),(0,3.05,-23.28),"stone_dark",0.08)
    add_box("SanctuaryInnerPanel",(6.45,4.65,0.22),(0,3.00,-23.00),"stone",0.05)
    for side in (-1,1):
        x=2.72*side
        add_cylinder(f"ReredosColumn_{side}",0.26,4.30,(x,2.72,-22.83),"trim",16,0.025)
        add_box(f"ReredosColumnBase_{side}",(0.72,0.34,0.64),(x,0.78,-22.83),"trim",0.045)
        add_box(f"ReredosColumnCap_{side}",(0.72,0.34,0.64),(x,4.88,-22.83),"trim",0.045)
    add_arch_curve("ReredosGothicArch",2.45,3.35,5.55,-22.68,0.17,"trim",24)
    add_box("ReredosCrown",(6.35,0.28,0.50),(0,5.52,-22.85),"trim",0.06)
    add_box("SanctuaryCrossV",(0.22,2.55,0.16),(0,3.78,-22.48),"wood",0.025)
    add_box("SanctuaryCrossH",(1.55,0.22,0.16),(0,4.24,-22.47),"wood",0.025)

def build_upper_floor():
    # Visual balustrades/spindles on second floor inner edges.
    for side in (-1,1):
        x=6.64*side
        for z in [-17,-14,-11,-8,-5,-2,1,4,7]:
            add_cylinder(f"GallerySpindle_{side}_{z}",0.075,1.25,(x,5.72,z),"wood",10,0.015)
        add_box(f"GalleryTopRail_{side}",(0.22,0.16,26.0),(x,6.34,-5.0),"wood",0.035)
        add_box(f"GalleryBottomRail_{side}",(0.18,0.14,26.0),(x,5.18,-5.0),"wood",0.025)

    # Choir bridge front/rear decorative rails.
    for z in (-16.58,-19.72):
        add_box(f"ChoirTopRail_{z}",(13.2,0.16,0.22),(0,6.34,z),"wood",0.035)
        for x in [-6.0,-4.5,-3.0,-1.5,0,1.5,3.0,4.5,6.0]:
            add_cylinder(f"ChoirSpindle_{z}_{x}",0.075,1.25,(x,5.72,z),"wood",10,0.015)

def build_bell_tower():
    cx=-25.0; cz=9.0
    # Decorative outer skin around collision piers.
    for sx in (-1,1):
        for sz in (-1,1):
            x=cx+3.8*sx; z=cz+3.8*sz
            add_box(f"BellTowerPierSkin_{sx}_{sz}",(1.18,12.9,1.18),(x,6.45,z),"stone",0.08)
            add_box(f"BellTowerPierBase_{sx}_{sz}",(1.55,0.48,1.55),(x,0.48,z),"stone_dark",0.08)
            add_box(f"BellTowerPierCap_{sx}_{sz}",(1.45,0.42,1.45),(x,12.35,z),"trim",0.07)
    # Upper arched openings on four sides.
    for face,dx,dz in [
        ("N",0,-3.86),("S",0,3.86),("W",-3.86,0),("E",3.86,0)
    ]:
        if dx==0:
            add_arch_curve(f"BellOpening_{face}",2.1,8.4,11.65,cz+dz,0.18,"trim",20).location += Vector(B(cx,0,0))
        else:
            a=add_arch_curve(f"BellOpening_{face}",2.1,8.4,11.65,0,0.18,"trim",20)
            a.rotation_euler[2]=math.radians(90 if dx<0 else -90)
            a.location=Vector(B(cx+dx,0,cz))
    add_box("BellTowerCornice",(8.8,0.38,8.8),(cx,12.25,cz),"trim",0.08)
    # Bell frame and bell.
    add_box("BellFrameTop",(7.4,0.42,0.42),(cx,11.2,cz),"wood",0.035)
    add_box("BellFrameL",(0.42,5.8,0.42),(cx-2.8,9.0,cz),"wood",0.035)
    add_box("BellFrameR",(0.42,5.8,0.42),(cx+2.8,9.0,cz),"wood",0.035)
    add_cylinder("BellBody",1.35,1.45,(cx,9.25,cz),"metal",32,0.06)
    add_cylinder("BellLip",1.62,0.24,(cx,8.50,cz),"metal",32,0.04)

def build_side_rooms():
    # Sacristy cornices / chapel arch.
    add_box("SacristyCornice",(8.0,0.22,0.30),(15.0,4.35,-15.0),"trim",0.04)
    add_arch_curve("SacristyDoorArch",1.25,2.15,3.35,-9.45,0.15,"trim",18)
    # Crypt entry pointed frame.
    add_arch_curve("CryptDoorArch",1.30,2.0,3.15,0.96,0.16,"stone_dark",18)
    # West hall power route framing.
    add_arch_curve("WestHallArch",1.35,2.1,3.35,-4.40,0.16,"trim",18).location += Vector(B(-14.5,0,0))

def convert_curves():
    for o in list(bpy.context.scene.objects):
        if o.type=="CURVE":
            bpy.context.view_layer.objects.active=o
            o.select_set(True)
            bpy.ops.object.convert(target="MESH")
            o.select_set(False)

def join_by_material_group():
    # Collapse hundreds of authored details into a handful of runtime meshes.
    groups={}
    for o in bpy.context.scene.objects:
        if o.type=="MESH" and "xz_material_group" in o:
            groups.setdefault(o["xz_material_group"],[]).append(o)
    for key,objs in groups.items():
        bpy.ops.object.select_all(action="DESELECT")
        for o in objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active=objs[0]
        if len(objs)>1:
            bpy.ops.object.join()
        obj=bpy.context.view_layer.objects.active
        obj.name="Architecture_"+key
        obj["xz_material_group"]=key

def add_preview_lighting():
    world=bpy.data.worlds.new("ChurchWorld")
    bpy.context.scene.world=world
    world.use_nodes=True
    bg=world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value=(0.004,0.006,0.012,1)
    bg.inputs["Strength"].default_value=0.15

    # moon
    bpy.ops.object.light_add(type="SUN", location=B(0,18,0))
    sun=bpy.context.object; sun.name="PreviewMoon"; sun.rotation_euler=(math.radians(42),0,math.radians(-28))
    sun.data.energy=2.0; sun.data.color=(0.28,0.38,0.65)

    # altar warm
    for x in (-2.2,2.2):
        bpy.ops.object.light_add(type="POINT", location=B(x,2.5,-20))
        l=bpy.context.object; l.data.energy=450; l.data.color=(1.0,0.24,0.06); l.data.shadow_soft_size=1.2

    # nave low warm accents
    for z in (-12,-3,6):
        bpy.ops.object.light_add(type="POINT", location=B(0,4.5,z))
        l=bpy.context.object; l.data.energy=180; l.data.color=(1.0,0.35,0.12); l.data.shadow_soft_size=1.0

def point_camera(cam, target):
    direction=Vector(B(*target))-cam.location
    cam.rotation_euler=direction.to_track_quat("-Z","Y").to_euler()

def render_views():
    scene=bpy.context.scene
    scene.render.engine="BLENDER_EEVEE"
    scene.render.resolution_x=1280
    scene.render.resolution_y=720
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format="PNG"
    scene.render.film_transparent=False

    views=[
        ("01_nave_to_altar",(0,2.0,11.5),(0,2.2,-18.5),58),
        ("02_front_exterior",(18,8.2,34),(0,7.0,10.5),52),
        ("03_front_three_quarter",(-25,10.0,30),(0,7.0,5.0),55),
        ("04_overview",(38,34,42),(0,2,-6),52),
        ("05_rear_ruins",(30,8,-40),(0,3,-15),56),
        ("06_bell_tower",(-41,13,24),(-25,7,9),52),
        ("07_second_floor",(7.8,5.9,8.5),(0,4.5,-12),60),
        ("08_altar_close",(5.5,2.1,-14.5),(0,3.0,-22.4),48),
    ]
    cam_data=bpy.data.cameras.new("AuthoringCamera")
    cam=bpy.data.objects.new("AuthoringCamera",cam_data)
    bpy.context.collection.objects.link(cam)
    scene.camera=cam
    for name,pos,target,lens in views:
        cam.location=Vector(B(*pos))
        cam.data.lens=lens
        point_camera(cam,target)
        scene.render.filepath=str(RENDER_DIR/(name+".png"))
        bpy.ops.render.render(write_still=True)

def report():
    meshes=[o for o in bpy.context.scene.objects if o.type=="MESH" and o.name.startswith("Architecture_")]
    tri_total=0; vert_total=0
    objects=[]
    for o in meshes:
        deps=bpy.context.evaluated_depsgraph_get()
        ev=o.evaluated_get(deps)
        mesh=ev.to_mesh()
        tri_total+=sum(max(0,len(p.vertices)-2) for p in mesh.polygons)
        vert_total+=len(mesh.vertices)
        objects.append({"name":o.name,"vertices":len(mesh.vertices),"polygons":len(mesh.polygons)})
        ev.to_mesh_clear()
    data={
        "schema":1,
        "asset":"church_final_architecture.glb",
        "visual_only":True,
        "gameplay_collision_authority":"Godot procedural collision shell",
        "runtime_meshes":len(meshes),
        "triangles_estimated":tri_total,
        "vertices":vert_total,
        "objects":objects,
        "render_count":len(list(RENDER_DIR.glob("*.png"))),
        "features":[
            "gothic pointed zombie-window surrounds",
            "upper clerestory stained-glass frames",
            "beveled nave pilasters and buttresses",
            "rib-vault curves and timber roof trusses",
            "nested front portal",
            "front tower detailing and pinnacles",
            "sanctuary reredos and cross",
            "second-floor balustrades",
            "bell tower decorative skin and bell",
            "side-room and crypt arch framing"
        ]
    }
    REPORT.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
    print("XZOGOT_FINAL_CHURCH_BLENDER_MESHES_GREEN",len(meshes))
    print("XZOGOT_FINAL_CHURCH_BLENDER_TRIANGLES",tri_total)
    print("XZOGOT_FINAL_CHURCH_BLENDER_RENDERS_GREEN",data["render_count"])
    return data

def export_glb():
    # Export only authored architecture meshes, not preview lights/camera.
    bpy.ops.object.select_all(action="DESELECT")
    selected=[]
    for o in bpy.context.scene.objects:
        if o.type=="MESH" and o.name.startswith("Architecture_"):
            o.select_set(True); selected.append(o)
    if not selected:
        raise SystemExit("No architecture meshes")
    bpy.context.view_layer.objects.active=selected[0]
    bpy.ops.export_scene.gltf(
        filepath=str(OUT_GLB),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_extras=True,
        export_texcoords=True,
        export_normals=True,
        export_tangents=True,
        export_materials="EXPORT",
    )
    if not OUT_GLB.exists() or OUT_GLB.stat().st_size<1024:
        raise SystemExit("GLB export failed")
    print("XZOGOT_FINAL_CHURCH_GLB_GREEN",OUT_GLB.stat().st_size)

def main():
    reset(); make_materials()
    build_nave()
    build_front_tower()
    build_sanctuary()
    build_upper_floor()
    build_bell_tower()
    build_side_rooms()
    convert_curves()
    join_by_material_group()
    add_preview_lighting()
    render_views()
    export_glb()
    data=report()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    if data["runtime_meshes"]>8:
        raise SystemExit("Too many runtime architecture meshes")
    if data["render_count"]<8:
        raise SystemExit("Missing authoring renders")
    print("XZOGOT_FINAL_CHURCH_BLENDER_AUTHORING_GREEN")

if __name__=="__main__":
    main()
