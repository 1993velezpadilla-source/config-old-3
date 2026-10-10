"""Black Pines Forge — procedural environment dressing and measurable fidelity gates.

Blender-only module. ZERO external assets/APIs. Uses the exact authored manifest.
Never changes Godot collision, zombie spawns, portal positions, or gameplay.
Both GUI and headless GitHub CI invoke this SAME authoring pass.
"""
import bpy
import math
from mathutils import Vector
import black_pines_forge_surface as forge_surface
import black_pines_forge_materials as forge_materials
import black_pines_forge_hospital_kit as hospital_kit

LANDMARKS = {}
ADDED_NAMES = []
MAX_SCENE_MESH_OBJECTS = 850
MAX_SCENE_TRIANGLES = 190000


def godot_to_blender(pos):
    return (pos[0], -pos[2], pos[1])


def add_box(api, label, pos, dims, material, bevel=0.018, category="prop"):
    obj = api.cube("Forge_" + label, pos, dims, material, category, bevel)
    ADDED_NAMES.append(obj.name)
    return obj


def tube(api, label, start, end, radius, material, segments=9):
    a, b = Vector(godot_to_blender(start)), Vector(godot_to_blender(end))
    line = b-a
    if line.length < 0.05:
        raise ValueError("Zero-length Forge pipe: " + label)
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=segments, radius=radius, depth=line.length,
        location=(a+b)*.5)
    obj = bpy.context.object
    obj.rotation_euler = line.to_track_quat('Z', 'Y').to_euler()
    obj.name = "Forge_" + label
    obj.data.materials.append(api.mat(material))
    api.COUNTS["prop"] += 1
    ADDED_NAMES.append(obj.name)
    return obj


def _label(api, label, pos, title, size=.28, material="light",
           face_negative_z=False):
    # Interior room signs on north/far walls face INTO their room (negative
    # Godot Z). The old X+90 rotation faced them outward: letters appeared
    # mirrored when seen from the gameplay side. Exterior signage retains +Z.
    # An original dark plaque keeps signs readable against weathered plaster.
    # It is visual-only and does not interfere with zombie collision openings.
    width=min(8.70,max(1.05,len(title)*size*.59+.46))
    plaque=api.cube("Forge_Plaque_"+label,
                    (pos[0],pos[1]+size*.13,
                     pos[2]+(.075 if face_negative_z else -.075)),
                    (width,size*1.42,.075),"dark_metal","trim",.023)
    ADDED_NAMES.append(plaque.name)
    # Text converted to an ORIGINAL mesh so glTF selected-MESH export includes
    # it. Avoid externally shipped font files or proprietary text assets.
    bpy.ops.object.text_add(location=godot_to_blender(pos))
    obj = bpy.context.object
    obj.name = "Forge_Sign_" + label
    obj.data.body = title
    obj.data.size = size
    obj.data.extrude = .003
    obj.data.align_x = 'CENTER'
    # Native Blender font plane XY -> vertical XZ; viewed along its front.
    obj.rotation_euler = (math.pi/2, 0, math.pi if face_negative_z else 0)
    bpy.ops.object.convert(target="MESH")
    obj.data.materials.append(api.mat(material))
    api.COUNTS["trim"] += 1
    ADDED_NAMES.append(obj.name)
    return obj


def _set_landmark(room_id, names):
    LANDMARKS[room_id] = tuple(names)


def build_forge_detail(api, layout):
    """Author art only. Do not instantiate gameplay/collision geometry."""
    LANDMARKS.clear()
    ADDED_NAMES.clear()
    # Consistent bevelled skirting / chair rail on walls that already exist
    # in the ORIGINAL Blender authority, never through empty door apertures.
    wall_meshes = [
        o for o in list(bpy.data.objects) if o.type == "MESH"
        and (o.name.startswith("WardPartition") or o.name.startswith("Outer"))
    ]
    for wall in wall_meshes:
        if "lintel" in wall.name.lower():
            continue
        x = float(wall.location.x)
        z = -float(wall.location.y)
        dimx, dimz = float(wall.dimensions.x), float(wall.dimensions.y)
        # The source has only 35cm-thick walls, and portals are cut as gaps.
        if max(dimx, dimz) < .65:
            continue
        if dimx > dimz:
            dims = (max(.08, dimx-.04), .18, .43)
            for y, name in ((.20, "Base"), (2.74, "Rail")):
                add_box(api, wall.name + name, (x,y,z), dims,
                        "dark_metal" if y<1 else "lobby", .016, "trim")
        else:
            dims = (.43, .18, max(.08, dimz-.04))
            for y, name in ((.20, "Base"), (2.74, "Rail")):
                add_box(api, wall.name + name, (x,y,z), dims,
                        "dark_metal" if y<1 else "lobby", .016, "trim")

    # All twelve doors get matching plausible steel jambs and overhead
    # security transoms. Open width remains >=3.1m: jambs OUTSIDE gap.
    for i, p in enumerate(layout["portals"]):
        a, v = float(p["at"]), float(p["coord"])
        for side in (-1, 1):
            if p["axis"] == "x":
                loc, dim = (v, 1.42, a+side*1.68), (.46, 2.81, .20)
            else:
                loc, dim = (a+side*1.68, 1.42, v), (.20, 2.81, .46)
            add_box(api, "Door_%02d_Jamb_%+d"%(i,side), loc, dim,
                    "dark_metal", .035, "trim")
        if p["axis"] == "x":
            transom, size = (v, 2.91, a), (.46,.16,3.5)
        else:
            transom, size = (a, 2.91, v), (3.5,.16,.46)
        add_box(api, "Door_%02d_Transom"%i, transom, size,
                "brass", .019, "trim")

    # Every ORIGINAL zone obtains a named focal composition / 3D landmarks.
    # Place props near physical perimeter, well outside 3.1m door funnels.
    # Lighting is already Godot-native; these are glTF mesh visuals only.
    # Generator house: switch cabinets, copper pipe network, cooling vent.
    _set_landmark("generator", [
        add_box(api,"Generator_Switchboard",(-16.0,1.25,-12.9),
                (.40,2.15,1.7),"industrial",.05).name,
        add_box(api,"Generator_ControlLamp",(-15.75,1.90,-12.9),
                (.11,.16,.20),"red").name,
        add_box(api,"Generator_Tank",(-9.15,.74,-12.8),
                (1.2,1.48,1.1),"rust",.14).name,
        tube(api,"Generator_OverheadPipe",(-16,3.2,-13),
             (-9.2,3.2,-13),.11,"brass").name,
        tube(api,"Generator_Downpipe",(-9.2,3.2,-13),
             (-9.2,1.6,-13),.09,"rust").name,
        _label(api,"GENERATOR",(-12.6,3.17,-14.68),
               "BLACK PINES  /  POWER",.28).name,
    ])

    # Isolation ward: patient quarantine equipment, medical rail, observation.
    _set_landmark("isolation", [
        add_box(api,"Isolation_WallLocker",(-5.6,1.05,-12.9),
                (.52,1.95,.92),"medical",.045).name,
        add_box(api,"Isolation_InspectionPanel",(-5.23,1.45,-12.9),
                (.06,.53,.49),"dark_glass",.015).name,
        add_box(api,"Isolation_ExamBench",(3.9,.70,-12.4),
                (1.38,.16,.72),"medical",.075).name,
        tube(api,"Isolation_IVPole",(4.9,.1,-11.7),
             (4.9,2.1,-11.7),.026,"brass").name,
        tube(api,"Isolation_IVHook",(4.7,2.06,-11.7),
             (5.1,2.06,-11.7),.022,"brass").name,
        _label(api,"ISOLATION",(0.0,3.17,-14.68),
               "QUARANTINE  /  1948",.32).name,
    ])

    # Surgical theatre: distinct articulated operating lamp and blue consoles.
    _set_landmark("surgery", [
        add_box(api,"Surgery_Monitor",(16.0,1.50,-13.4),
                (.74,.66,.18),"dark_glass",.025).name,
        add_box(api,"Surgery_ScreenGlow",(16.0,1.52,-13.27),
                (.61,.50,.025),"ice",.01).name,
        tube(api,"Surgery_LampStem",(13.8,3.50,-9.6),
             (13.8,2.32,-9.6),.050,"dark_metal").name,
        tube(api,"Surgery_LampArm",(13.8,2.32,-9.6),
             (14.8,2.42,-9.6),.054,"brass").name,
        add_box(api,"Surgery_SpotLamp",(14.8,2.33,-9.6),
                (.75,.14,.50),"light",.06).name,
        _label(api,"SURGERY",(12.3,3.17,-14.68),
               "SURGICAL THEATRE",.26).name,
    ])

    # Patient wing: separate bed headboards and IV treatment racks.
    patient_names=[]
    for i, z in enumerate((-11.,-7.3,0.,4.2)):
        patient_names.append(add_box(api,"Patient_%02d_SafetyRail"%i,
            (-14.0,1.02,z+.46),(1.78,.070,.070),"brass",.025).name)
        patient_names.append(tube(api,"Patient_%02d_IV"%i,
            (-12.8,.05,z+.62),(-12.8,1.85,z+.62),.027,"dark_metal").name)
    _set_landmark("patients",patient_names+[
        _label(api,"PATIENTS",(-12.5,2.68,7.7),
               "PATIENT WING  /  WARD B",.26,face_negative_z=True).name])

    # Triage: wall roster, oxygen line, medicine dispenser.
    _set_landmark("triage", [
        add_box(api,"Triage_AdmissionsBoard",(-5.50,1.56,7.65),
                (.08,1.45,1.95),"lobby",.025).name,
        add_box(api,"Triage_AdmissionsPaper",(-5.43,1.56,7.65),
                (.014,1.18,1.55),"medical",.003).name,
        add_box(api,"Triage_FirstAidCabinet",(5.3,1.32,7.45),
                (.47,1.30,.94),"rust",.04).name,
        tube(api,"Triage_OxygenLine",(-4.7,3.02,8.6),
             (4.6,3.02,8.6),.065,"brass").name,
        _label(api,"TRIAGE",(0.,2.72,7.8),
               "BLACK PINES  /  ADMISSIONS",.26,face_negative_z=True).name,
    ])

    # Dining hall: institutional stainless counter and exposed service trays.
    _set_landmark("cafeteria", [
        add_box(api,"Dining_ServiceCounter",(10.0,.73,7.1),
                (3.2,1.43,.64),"industrial",.035).name,
        add_box(api,"Dining_TrayStack",(9.1,1.53,7.0),
                (.9,.13,.44),"brass",.02).name,
        add_box(api,"Dining_Tiling",(15.9,1.75,7.7),
                (.12,1.25,2.15),"medical",.012).name,
        _label(api,"DINING",(12.25,2.72,7.8),
               "MESS HALL  /  02",.27,face_negative_z=True).name,
    ])

    # Security office: wired CCTV housing, equipment cage, lockers.
    _set_landmark("security", [
        add_box(api,"Security_WallOfMonitors",(-16.8,1.58,18.7),
                (.30,1.23,1.88),"dark_glass",.035).name,
        add_box(api,"Security_RadioBank",(-9.2,.96,18.4),
                (.92,.78,.45),"industrial",.045).name,
        tube(api,"Security_CameraArm",(-15.8,3.2,10.2),
             (-15.2,3.2,10.2),.045,"brass").name,
        add_box(api,"Security_Camera",(-15.1,3.2,10.2),
                (.54,.23,.24),"dark_metal",.03).name,
        _label(api,"SECURITY",(-12.4,2.65,19.8),
               "SECURITY  /  RESTRICTED",.24,face_negative_z=True).name,
    ])

    # Ambulance court: original lamps and industrial crowd control; leave
    # floor fully walkable during gameplay (visual-only dressing first).
    _set_landmark("yard", [
        tube(api,"Yard_LampPostWest",(-5.8,.05,19.4),
             (-5.8,4.75,19.4),.11,"dark_metal").name,
        tube(api,"Yard_LampPostEast",(5.8,.05,19.4),
             (5.8,4.75,19.4),.11,"dark_metal").name,
        add_box(api,"Yard_LampWest",(-5.8,4.65,19.4),
                (.62,.16,.38),"light",.05).name,
        add_box(api,"Yard_LampEast",(5.8,4.65,19.4),
                (.62,.16,.38),"light",.05).name,
        _label(api,"COURT",(0.0,2.72,20.0),
               "EMERGENCY  /  KEEP CLEAR",.29,face_negative_z=True).name,
    ])

    # Garage: roll-up mechanical guides, mechanical workbench, tire stacks.
    _set_landmark("garage", [
        add_box(api,"Garage_ToolChest",(15.7,.82,19.0),
                (.95,1.47,.46),"rust",.06).name,
        add_box(api,"Garage_LiftControl",(17.25,1.72,18.0),
                (.20,1.1,.45),"dark_metal",.025).name,
        add_box(api,"Garage_Workbench",(9.6,.68,19.2),
                (2.1,.14,.72),"industrial",.03).name,
        tube(api,"Garage_AirPipe",(9.2,3.15,19.55),
             (16.8,3.15,19.55),.092,"brass").name,
        _label(api,"GARAGE",(12.5,2.72,19.8),
               "MAINTENANCE  /  GARAGE",.25,face_negative_z=True).name,
    ])

    surface = forge_surface.build_surfaces(api,layout,add_box,tube,_label)
    hero_props = hospital_kit.build(api,layout,add_box,tube)
    # Real yard screenshot audit: the source ambulance bumper touched the
    # garage divider at x=7.0. Move the COMPLETE cohesive vehicle left by
    # 0.75m (not merely cab windows) so physical hull and body no longer
    # intersect the partition. Preserve all door and window positions.
    ambulance_meshes = 0
    for obj in bpy.data.objects:
        if obj.type == "MESH" and "ambulance" in obj.name.lower():
            obj.location.x -= .75
            ambulance_meshes += 1
    if ambulance_meshes < 30:
        raise RuntimeError("BLACK_PINES_AMBULANCE_RED partial vehicle move "+
                           str(ambulance_meshes))
    # Blender world matrices remain stale in headless mode after modifying
    # object.location without depsgraph evaluation. Refresh BEFORE
    # fidelity_pass reads transformed bounding boxes / export culling.
    bpy.context.view_layer.update()
    pbr = forge_materials.apply(api)
    return {
        "forgeGuiBackend": True,
        "surfacePass": surface,
        "ambulanceRepositionMeters":0.75,
        "ambulanceMovedMeshes":ambulance_meshes,
        "originalHospitalKit": hero_props,
        "pbrSourceWear": pbr,
        "distinctRoomLandmarks": {k: len(v) for k, v in LANDMARKS.items()},
        "fidelityGateType": "measurable_composition_not_human_visual_perfection",
    }


def fidelity_pass(api, layout):
    """Deterministic authoring guard; not a subjective AAA claim."""
    required = {cell["id"] for cell in layout["cells"]}
    actual = set(LANDMARKS)
    issues = forge_materials.fidelity_gate() + hospital_kit.guard(layout)
    if actual != required:
        issues.append("missing/double landmark rooms: " + str(required^actual))
    for room, labels in LANDMARKS.items():
        if len(labels)<4:
            issues.append("insufficient landmarks for "+room)
        for name in labels:
            if bpy.data.objects.get(name) is None:
                issues.append("missing authored geometry "+name)
    for room_id in required:
        floor = bpy.data.objects.get("Forge_TiledFloor_"+room_id)
        if floor is None or floor.type!="MESH" or len(floor.data.polygons)<70:
            issues.append("missing original batched tiled flooring "+room_id)
    if bpy.data.objects.get("Forge_Facade_MarqueeBack") is None:
        issues.append("missing original main entrance branded facade")
    if bpy.data.objects.get("Forge_Sign_FACADE") is None:
        issues.append("missing branded Black Pines sign")
    # Signature props were reviewed in the genuine in-game screenshot:
    # the source ambulance must not revert to a wheeled opaque cuboid.
    for side in ("NORTH","SOUTH"):
        for name in ("Forge_Sign_AMBULANCE_"+side,
                     "Forge_AmbulanceVisual_SideCabWindow_"+side,
                     "Forge_AmbulanceVisual_SideStripe_"+side,
                     "Forge_AmbulanceVisual_SideDoorSeam_"+side):
            if bpy.data.objects.get(name) is None:
                issues.append("missing ambulatory-livery detail "+name)
    # Prove the optimized original ambulance stays separated from the
    # garage wall. The x=7 divider starts physically at x=6.825.
    for obj in bpy.data.objects:
        if obj.type != "MESH" or "ambulance" not in obj.name.lower():
            continue
        bounds=[obj.matrix_world @ Vector(p) for p in obj.bound_box]
        if max(v.x for v in bounds)>6.66:
            issues.append("ambulance penetrates garage divider: "+obj.name)
    for shell in ("RustyAmbulanceRear","RustyAmbulanceCab"):
        candidate=bpy.data.objects.get(shell)
        if candidate is None or candidate.type!="MESH" or len(candidate.data.polygons)<25:
            issues.append("ambulance returned to blocky cube: "+shell)
    windscreen=bpy.data.objects.get("Forge_AmbulanceVisual_CabWindshield")
    if windscreen is None or windscreen.type!="MESH" or (
            len(windscreen.data.vertices)!=4):
        issues.append("not a real diagonal ambulance windshield mesh")
    elif abs(float(windscreen.data.vertices[0].co.z)
             -float(windscreen.data.vertices[2].co.z))<.50:
        issues.append("ambulance windshield lost its angled silhouette")
    for name in ("Forge_AmbulanceVisual_CabWindshield",
                 "Forge_AmbulanceVisual_FrontGrille",
                 "Forge_AmbulanceVisual_FrontHeadlamp_0",
                 "Forge_AmbulanceVisual_FrontHeadlamp_1",
                 "Forge_AmbulanceVisual_RearServiceSplit"):
        if bpy.data.objects.get(name) is None:
            issues.append("ambulance silhouette regressed "+name)
    # Converted text mesh orientation is preserved in Blender mesh vertices,
    # while object.rotation_euler carries the sign's authored facing direction.
    # North-wall signs previously faced away from the player and appeared
    # mirror-written in real Godot screenshots. Check facing on every pass.
    for name in ("PATIENTS","TRIAGE","DINING","SECURITY","COURT","GARAGE"):
        sign = bpy.data.objects.get("Forge_Sign_"+name)
        if sign is None:
            issues.append("missing north-wall sign "+name)
        else:
            front = sign.rotation_euler.to_matrix() @ Vector((0,0,1))
            if front.y < .50:  # Blender +Y = Godot -Z, facing into the room
                issues.append("mirrored room sign: "+name)
    for i in range(12):
        n = "Forge_Door_%02d_Transom"%i
        if bpy.data.objects.get(n) is None:
            issues.append("missing 12-door frame "+n)
    meshes = [obj for obj in bpy.data.objects if obj.type=="MESH"]
    triangle_count = 0
    for obj in meshes:
        obj.data.calc_loop_triangles()
        triangle_count += len(obj.data.loop_triangles)
    if len(meshes)>MAX_SCENE_MESH_OBJECTS:
        issues.append("excessive draw nodes %d>%d"%(len(meshes),MAX_SCENE_MESH_OBJECTS))
    if triangle_count>MAX_SCENE_TRIANGLES:
        issues.append("excessive triangles %d>%d"%(triangle_count,MAX_SCENE_TRIANGLES))
    if triangle_count<5000:
        issues.append("implausibly empty scene")
    return {
        "pass": len(issues)==0,
        "status": "GREEN" if not issues else "RED",
        "issues": issues,
        "roomLandmarkCount": len(LANDMARKS),
        "roomLandmarks": {k:list(v) for k,v in LANDMARKS.items()},
        "doorFrameCount":sum(1 for i in range(12) if bpy.data.objects.get("Forge_Door_%02d_Transom"%i) is not None),
        "meshObjects":len(meshes),
        "triangles":triangle_count,
        "meshObjectBudget":MAX_SCENE_MESH_OBJECTS,
        "triangleBudget":MAX_SCENE_TRIANGLES,
        "collisionBackedForDecoration":False,
        "humanReferenceVisualMatchProven":False,
        "androidDeviceFramerateProven":False,
    }
