extends Node3D
## BLACK PINES SANATORIUM — independent *original* horror survival playtest map.
## One-level nine-zone loop.  Read the same layout JSON as Blender. Never
## change any Nacht/Church scene, shader, benchmark, or main.tscn.
## Reuses only pre-existing game systems: zombies, 6 perks, powerups, barriers,
## wallbuys, PAP, player touch HUD, network manager. Art is ORIGINAL procedural
## fallback; third-party source test zombies are NOT cleared for public APK.
const BLUEPRINT := "res://data/black_pines_layout.json"
const INTERACTABLE_SCRIPT := preload("res://scripts/interactable.gd")
const BARRICADE_SCRIPT := preload("res://scripts/barricade.gd")
const MYSTERY_SCRIPT := preload("res://scripts/black_pines_mystery.gd")
const PERK_CATALOG := preload("res://scripts/perk_catalog.gd")
const BLENDER_SCENE := "res://assets/black_pines/black_pines_architecture.glb"

@export var rounds_enabled: bool = true
@export var show_roof: bool = true
@export var prefer_blender_geometry: bool = true
@export var preview_no_enemies: bool = false

var _layout: Dictionary = {}
var _props_root: Node3D
var _geometry_root: Node3D
var _machine_root: Node3D
var _roof_root: Node3D
var _materials: Dictionary = {}
var _doors: Array[StaticBody3D] = []
var _barricades: Array[StaticBody3D] = []
var _machines: Array[StaticBody3D] = []
var _mystery: StaticBody3D

func _ready() -> void:
    get_tree().set_meta("active_map_id","black_pines")
    get_tree().set_meta("power_on",false)
    get_tree().set_meta("black_pines_gameplay_ready",false)
    var parsed: Variant=JSON.parse_string(FileAccess.get_file_as_string(BLUEPRINT))
    if not parsed is Dictionary:
        push_error("BLACK_PINES_RED invalid source-independent layout JSON")
        return
    _layout=parsed as Dictionary
    if not _verify_layout_contract():
        return
    _build_materials()
    _geometry_root=Node3D.new()
    _geometry_root.name="Architecture"
    add_child(_geometry_root)
    _props_root=Node3D.new()
    _props_root.name="Scenery"
    add_child(_props_root)
    _machine_root=Node3D.new()
    _machine_root.name="Machines"
    add_child(_machine_root)
    _roof_root=Node3D.new()
    _roof_root.name="Roof"
    add_child(_roof_root)
    # Runtime fallback always has reliable Godot-native colliders.  A Blender
    # GLB replaces ONLY static visuals and cannot affect gameplay authority.
    var visuals_from_blender: bool=false
    if prefer_blender_geometry and ResourceLoader.exists(BLENDER_SCENE):
        var packed: PackedScene=load(BLENDER_SCENE) as PackedScene
        if packed!=null:
            var authored: Node3D=packed.instantiate() as Node3D
            if authored!=null:
                authored.name="BlenderOriginalArchitecturalVisuals"
                _geometry_root.add_child(authored)
                visuals_from_blender=true
    _build_structure(not visuals_from_blender)
    _build_original_props(not visuals_from_blender)
    _build_interactive_doors()
    _build_window_barricades()
    _build_machines_and_wallbuys()
    _build_mystery_box()
    _build_light_and_mood()
    _build_spawn_markers()
    _build_roof()
    set_roof_visible(show_roof)
    var manager: Node=get_node_or_null("RoundManager")
    if manager!=null:
        # Do not let original imported sheep substitute zombie-only round 5.
        # This option is scoped to Black Pines; other scenes keep defaults.
        manager.set("special_rounds_enabled",false)
        manager.set("auto_start",rounds_enabled and not preview_no_enemies)
        if manager.has_method("reset_network_match"):
            manager.call("reset_network_match")
    var player: Node3D=get_node_or_null("Player") as Node3D
    if player!=null:
        player.global_position=_vector(_layout["playerSpawn"])
    set_meta("black_pines_structural_ready",true)
    set_meta("black_pines_placed_door_count",_doors.size())
    set_meta("black_pines_barricade_count",_barricades.size())
    set_meta("black_pines_machine_count",_machines.size())
    set_meta("black_pines_blender_visuals_mounted",visuals_from_blender)
    get_tree().set_meta("black_pines_gameplay_ready",true)
    print("BLACK_PINES_PHASE1_SCENE_GREEN zones=9 doors=",_doors.size(),
        " windows=",_barricades.size()," perks=6 wallbuys=5",
        " mystery_spots=4 blender_visuals=",visuals_from_blender)

func _vector(value: Variant) -> Vector3:
    var a: Array=value as Array
    return Vector3(float(a[0]),float(a[1]),float(a[2]))

func _verify_layout_contract() -> bool:
    var gates: Dictionary=_layout.get("technicalGates",{}) as Dictionary
    var checks: bool=(
        int(_layout.get("schemaVersion",0))==1
        and str(_layout.get("mapId",""))=="black_pines_sanatorium"
        and (_layout.get("cells",[]) as Array).size()==9
        and (_layout.get("portals",[]) as Array).size()==12
        and (_layout.get("windows",[]) as Array).size()==12
        and (_layout.get("perks",[]) as Array).size()==6
        and (_layout.get("wallbuys",[]) as Array).size()==5
        and (_layout.get("mysterySpots",[]) as Array).size()==4
        and not bool(gates.get("gobblegumEnabled",true))
        and not bool(gates.get("originalChurchFilesMayChange",true))
    )
    if not checks:
        push_error("BLACK_PINES_RED gameplay station placement contract changed")
    return checks

func _build_materials() -> void:
    var definitions: Dictionary={
        "snow":Color(0.18,0.24,0.27),
        "stone":Color(0.17,0.19,0.20),
        "wall":Color(0.27,0.29,0.27),
        "plaster":Color(0.42,0.43,0.37),
        "medical":Color(0.29,0.34,0.32),
        "industrial":Color(0.25,0.27,0.29),
        "lobby":Color(0.37,0.32,0.28),
        "outdoor":Color(0.25,0.29,0.31),
        "dark_metal":Color(0.09,0.115,0.13),
        "brass":Color(0.52,0.35,0.14),
        "rust":Color(0.36,0.15,0.105),
        "red":Color(0.63,0.11,0.075),
        "blue":Color(0.09,0.30,0.43),
        "glass":Color(0.16,0.36,0.41),
        "wet":Color(0.14,0.18,0.21)
    }
    for key: String in definitions:
        var mat:=StandardMaterial3D.new()
        mat.albedo_color=definitions[key] as Color
        mat.roughness=0.35 if key=="wet" else 0.78
        mat.metallic=0.65 if key in ["dark_metal","brass","rust"] else 0.0
        _materials[key]=mat

func _box(parent: Node3D,label: String,where: Vector3,dimensions: Vector3,
        material_id: String,solid: bool=false,render: bool=true) -> Node3D:
    var root: Node3D
    if solid:
        root=StaticBody3D.new()
    else:
        root=Node3D.new()
    root.name=label
    root.position=where
    parent.add_child(root)
    if render:
        var mesh_instance:=MeshInstance3D.new()
        mesh_instance.name="OriginalProceduralVisual"
        var mesh:=BoxMesh.new()
        mesh.size=dimensions
        mesh.material=_materials[material_id] as Material
        mesh_instance.mesh=mesh
        root.add_child(mesh_instance)
    if solid:
        var collision:=CollisionShape3D.new()
        var shape:=BoxShape3D.new()
        shape.size=dimensions
        collision.shape=shape
        root.add_child(collision)
    return root

func _build_structure(render: bool) -> void:
    # Even when Blender supplies the visual GLB, the same JSON geometry
    # creates native collision (without double-drawing the walls).
    _box(_geometry_root,"Snowfield",Vector3(0,-0.40,3),Vector3(56,0.40,62),
        "snow",true,render)
    var xs: Array=_layout["cellBoundaries"]["x"] as Array
    var zs: Array=_layout["cellBoundaries"]["z"] as Array
    for row: Dictionary in _layout["cells"]:
        var c: int=int(row["col"])
        var r: int=int(row["row"])
        var left: float=float(xs[c])
        var right: float=float(xs[c+1])
        var north: float=float(zs[r])
        var south: float=float(zs[r+1])
        var floor_label: String=str(row["id"])
        _box(_geometry_root,"Floor_"+floor_label,
            Vector3((left+right)*0.5,-0.16,(north+south)*0.5),
            Vector3(right-left,0.32,south-north),str(row["floor"]),true,render)
    for x: float in [-7.0,7.0]:
        for row_id: int in range(3):
            var z_min: float=float(zs[row_id])
            var z_max: float=float(zs[row_id+1])
            var mid: float=(z_min+z_max)*0.5
            _wall_with_openings("x",x,z_min,z_max,
                [{"at":mid,"width":3.1}],"InnerPartition",render)
    for z: float in [-3.0,9.0]:
        for col_id: int in range(3):
            var x_min: float=float(xs[col_id])
            var x_max: float=float(xs[col_id+1])
            var mid: float=(x_min+x_max)*0.5
            _wall_with_openings("z",z,x_min,x_max,
                [{"at":mid,"width":3.1}],"CrossWard",render)
    for x: float in [-18.0,18.0]:
        _wall_with_openings("x",x,-15.0,21.0,
            [{"at":-9.0,"width":2.65},{"at":3.0,"width":2.65},
            {"at":15.0,"width":2.65}],"ExternalWestEast",render)
    for z: float in [-15.0,21.0]:
        _wall_with_openings("z",z,-18.0,18.0,
            [{"at":-12.5,"width":2.65},{"at":0.0,"width":2.65},
            {"at":12.5,"width":2.65}],"ExternalNorthSouth",render)
    # Perimeter fence marks the map limits but never blocks exterior zombie
    # nav access to all 12 window bays.
    for x: float in [-26.0,26.0]:
        _box(_geometry_root,"FenceSide",Vector3(x,1.1,3.0),
            Vector3(0.22,2.2,56.0),"dark_metal",true,render)
    for z: float in [-25.0,31.0]:
        _box(_geometry_root,"FenceEnd",Vector3(0,1.1,z),
            Vector3(52.0,2.2,0.22),"dark_metal",true,render)

func _wall_with_openings(axis: String,fixed: float,start: float,finish: float,
        apertures: Array,label: String,render: bool) -> void:
    var cursor: float=start
    var index: int=0
    for opening: Dictionary in apertures:
        var at: float=float(opening["at"])
        var half_width: float=float(opening["width"])*0.5
        var begin: float=at-half_width
        var end: float=at+half_width
        if begin>cursor:
            _wall_segment(axis,fixed,cursor,begin,0.0,3.8,
                label+"_Solid_"+str(index),render)
        # Top beam makes the gate/window look like an architectural opening
        # instead of a missing wall slab.  All exits remain at floor level.
        _wall_segment(axis,fixed,begin,end,2.85,0.95,
            label+"_Lintel_"+str(index),render)
        cursor=end
        index+=1
    if finish>cursor:
        _wall_segment(axis,fixed,cursor,finish,0.0,3.8,
            label+"_Tail",render)

func _wall_segment(axis: String,fixed: float,start: float,end: float,
        bottom: float,height: float,label: String,render: bool) -> void:
    var center: Vector3=Vector3(fixed,bottom+height*0.5,(start+end)*0.5)
    var extents: Vector3=Vector3(0.35,height,end-start)
    if axis=="z":
        center=Vector3((start+end)*0.5,bottom+height*0.5,fixed)
        extents=Vector3(end-start,height,0.35)
    _box(_geometry_root,label,center,extents,"plaster",true,render)

func _build_interactive_doors() -> void:
    var i: int=0
    for portal: Dictionary in _layout["portals"]:
        var axis: String=str(portal["axis"])
        var place: Vector3=Vector3(
            float(portal["coord"]) if axis=="x" else float(portal["at"]),
            1.25,
            float(portal["at"]) if axis=="x" else float(portal["coord"]))
        var size: Vector3=(Vector3(0.30,2.5,3.02) if axis=="x"
            else Vector3(3.02,2.5,0.30))
        var body: StaticBody3D=_make_interaction("Door_%02d"%i,0,
            place,size,"rust",int(portal["price"]),
            "UNLOCK "+str(portal["label"]),true)
        body.set_meta("door_mechanism",str(portal["type"]))
        body.set_meta("black_pines_gate_number",i)
        _add_3d_label(body,str(portal["type"]).to_upper(),Vector3(0,0.25,0))
        _doors.append(body)
        i+=1

func _build_window_barricades() -> void:
    var i: int=0
    for data: Dictionary in _layout["windows"]:
        var axis: String=str(data["axis"])
        var outside: float=1.0 if float(data["coord"])>0.0 else -1.0
        var pos: Vector3=Vector3(
            float(data["coord"]) if axis=="x" else float(data["at"]),
            1.25,
            float(data["at"]) if axis=="x" else float(data["coord"]))
        var exterior: Vector3=Vector3(pos.x,pos.y-1.13,pos.z)
        var approach: Vector3=exterior
        var interior: Vector3=exterior
        if axis=="x":
            exterior.x+=outside*3.35
            approach.x+=outside*1.70
            interior.x-=outside*1.65
        else:
            exterior.z+=outside*3.35
            approach.z+=outside*1.70
            interior.z-=outside*1.65
        var barrier:=StaticBody3D.new()
        barrier.name="Barricade_%02d"%i
        barrier.position=pos
        barrier.rotation_degrees.y=90.0 if axis=="z" else 0.0
        barrier.set_script(BARRICADE_SCRIPT)
        barrier.set_meta("window_id",i)
        barrier.set_meta("outside_spawn",exterior)
        barrier.set_meta("outside_approach",approach)
        barrier.set_meta("inside_point",interior)
        _geometry_root.add_child(barrier)
        _barricades.append(barrier)
        i+=1

func _make_interaction(label: String,kind: int,at: Vector3,
        size: Vector3,material_id: String,price: int,prompt: String,
        one_shot: bool=false) -> StaticBody3D:
    var body:=StaticBody3D.new()
    body.set_script(INTERACTABLE_SCRIPT)
    body.name=label
    body.position=at
    body.set("interaction_kind",kind)
    body.set("price",price)
    body.set("one_shot",one_shot)
    body.set("prompt_text",prompt)
    body.add_to_group("black_pines_interaction")
    var model:=MeshInstance3D.new()
    model.name="MachineBody"
    var mesh:=BoxMesh.new()
    mesh.size=size
    mesh.material=_materials[material_id] as Material
    model.mesh=mesh
    body.add_child(model)
    var shape:=BoxShape3D.new()
    shape.size=size
    var collision:=CollisionShape3D.new()
    collision.shape=shape
    body.add_child(collision)
    _machine_root.add_child(body)
    return body

func _add_3d_label(owner: Node3D,content: String,local: Vector3) -> void:
    var label:=Label3D.new()
    label.name="Identification"
    label.text=content
    label.font_size=45
    label.pixel_size=0.0028
    label.outline_size=12
    label.modulate=Color(0.90,0.85,0.73)
    label.position=local+Vector3(0,0.7,0)
    label.billboard=BaseMaterial3D.BILLBOARD_ENABLED
    owner.add_child(label)

func _build_machines_and_wallbuys() -> void:
    for source: Dictionary in _layout["perks"]:
        var id: String=str(source["id"])
        var profile: Dictionary=PERK_CATALOG.get_perk(id)
        if profile.is_empty():
            push_error("BLACK_PINES_RED unknown perk ID "+id)
            return
        var machine: StaticBody3D=_make_interaction(
            "Perk_"+id,3,_vector(source["pos"])+Vector3.UP*1.12,
            Vector3(1.15,2.24,0.90),"dark_metal",
            int(profile["price"]),"BUY "+str(profile["display_name"]))
        machine.rotation_degrees.y=float(source["yaw"])
        machine.set("perk_id",id)
        machine.set("requires_power",true)
        machine.add_to_group("perk_machine")
        _add_3d_label(machine,str(profile["display_name"]),
            Vector3(0,0.15,0))
        var color_values: Array=profile["machine_color"] as Array
        var accent:=StandardMaterial3D.new()
        accent.albedo_color=Color(float(color_values[0]),
            float(color_values[1]),float(color_values[2]))
        var face:=MeshInstance3D.new()
        var mesh:=BoxMesh.new()
        mesh.size=Vector3(0.95,1.26,0.08)
        mesh.material=accent
        face.mesh=mesh
        face.position=Vector3(0,0,0.5)
        machine.add_child(face)
        _machines.append(machine)
    var power:=_make_interaction("PowerSwitch",4,
        _vector(_layout["powerSwitch"]),Vector3(0.6,1.30,0.55),
        "brass",0,"RESTORE ELECTRICITY",true)
    _add_3d_label(power,"POWER",Vector3.ZERO)
    var punch:=_make_interaction("PackAPunch",5,
        _vector(_layout["packAPunch"])+Vector3.UP*1.14,
        Vector3(2.1,2.28,1.15),"blue",5000,
        "PACK-A-PUNCH CURRENT WEAPON")
    punch.set("requires_power",true)
    punch.add_to_group("weapon_upgrade_machine")
    _add_3d_label(punch,"PACK-A-PUNCH",Vector3.ZERO)
    for row: Dictionary in _layout["wallbuys"]:
        var point: Vector3=_vector(row["pos"])
        var wallbuy:=_make_interaction("WallBuy_"+str(row["id"]),1,point,
            Vector3(0.20,1.12,2.15),"dark_metal",
            int(row["price"]),"BUY "+str(row["id"]).to_upper())
        wallbuy.rotation_degrees.y=float(row["yaw"])
        wallbuy.set("weapon_id",str(row["id"]))
        wallbuy.add_to_group("wallbuy_machine")
        _add_3d_label(wallbuy,str(row["id"]).to_upper(),Vector3.ZERO)

func _build_mystery_box() -> void:
    var mystery:=StaticBody3D.new()
    mystery.set_script(MYSTERY_SCRIPT)
    mystery.name="MysteryBox"
    mystery.set("interaction_kind",2)
    mystery.set("price",950)
    mystery.set("one_shot",false)
    mystery.set("prompt_text","MYSTERY BOX")
    mystery.set("locations",_layout["mysterySpots"])
    var shape:=BoxShape3D.new()
    shape.size=Vector3(1.75,1.15,1.1)
    var collision:=CollisionShape3D.new()
    collision.shape=shape
    mystery.add_child(collision)
    var box_mesh:=BoxMesh.new()
    box_mesh.size=shape.size
    box_mesh.material=_materials["brass"] as Material
    var model:=MeshInstance3D.new()
    model.name="MysteryChest"
    model.mesh=box_mesh
    mystery.add_child(model)
    mystery.position=_vector(_layout["mysterySpots"][0])+Vector3.UP*0.62
    _machine_root.add_child(mystery)
    _add_3d_label(mystery,"?  MYSTERY  ?",Vector3.ZERO)
    _mystery=mystery

func _build_original_props(render_native_proxies: bool) -> void:
    # When the REAL Blender GLB is mounted, it already contains gurneys,
    # surgical tables, desks and the ambulance. Drawing native proxy copies
    # on the exact same coordinates creates z-fighting, hollow-looking black
    # rectangles and needless mobile draws. Preserve fallback ONLY when GLB
    # is missing; never remove native gameplay colliders.
    if not render_native_proxies:
        set_meta("black_pines_duplicate_scenery_prevented",true)
        return
    # Original reusable modular low-poly Blender/Godot proxy parts.
    # Furniture is NOT collision-blocking for the first 20-round navigation
    # test. Only outer and partition walls, doors, windows, machine bodies
    # and terrain are authoritative colliders.
    for z: float in [-11.0,-7.3,0.0,4.2]:
        _box(_props_root,"Gurney",Vector3(-14.0,0.55,z),
            Vector3(2.0,0.90,0.85),"dark_metal")
        _box(_props_root,"Mattress",Vector3(-14.0,1.05,z),
            Vector3(1.9,0.14,0.83),"medical")
    for x: float in [10.0,15.5]:
        for z: float in [0.0,4.2]:
            _box(_props_root,"DiningTable",Vector3(x,0.72,z),
                Vector3(2.2,0.16,1.1),"lobby")
    for x: float in [-14.0,-10.8]:
        _box(_props_root,"Generator",Vector3(x,0.95,-7.5),
            Vector3(1.8,1.9,1.6),"rust")
    _box(_props_root,"SurgicalBed",Vector3(13.8,0.75,-9.5),
        Vector3(2.35,0.18,1.1),"dark_metal")
    _box(_props_root,"NurseTriageDesk",Vector3(0,0.75,0),
        Vector3(4.1,1.45,0.78),"lobby")
    _box(_props_root,"AmbulanceShell",Vector3(3.8,1.05,17.8),
        Vector3(3.6,2.1,1.7),"medical")
    _box(_props_root,"AmbulanceCab",Vector3(6.25,0.90,17.8),
        Vector3(1.4,1.8,1.65),"rust")
    for i: int in range(12):
        var x: float=-16.1+float(i%4)*10.6
        var z: float=-13.2+float(i/4)*15.5
        _box(_props_root,"FloorGrime_%02d"%i,
            Vector3(x,0.019,z),Vector3(1.6,0.01,0.72),
            "wet")
    for room: Dictionary in _layout["cells"]:
        var xs: Array=_layout["cellBoundaries"]["x"] as Array
        var zs: Array=_layout["cellBoundaries"]["z"] as Array
        var c: int=int(room["col"])
        var r: int=int(room["row"])
        var center: Vector3=Vector3(
            (float(xs[c])+float(xs[c+1]))*0.5,3.1,
            (float(zs[r])+float(zs[r+1]))*0.5)
        var anchor:=Node3D.new()
        anchor.position=center
        anchor.name="Sign_"+str(room["id"])
        _props_root.add_child(anchor)
        _add_3d_label(anchor,str(room["name"]),Vector3.ZERO)

func _build_light_and_mood() -> void:
    var env:=WorldEnvironment.new()
    var background:=Environment.new()
    background.background_mode=Environment.BG_COLOR
    background.background_color=Color(0.033,0.052,0.071)
    background.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
    background.ambient_light_color=Color(0.13,0.20,0.25)
    background.ambient_light_energy=0.78
    background.tonemap_mode=Environment.TONE_MAPPER_FILMIC
    env.environment=background
    add_child(env)
    var sun:=DirectionalLight3D.new()
    sun.name="ColdMoon"
    sun.rotation_degrees=Vector3(-50,25,0)
    sun.light_color=Color(0.42,0.57,0.75)
    sun.light_energy=0.43
    sun.shadow_enabled=false
    add_child(sun)
    for cell: Dictionary in _layout["cells"]:
        var xs: Array=_layout["cellBoundaries"]["x"] as Array
        var zs: Array=_layout["cellBoundaries"]["z"] as Array
        var i: int=int(cell["col"])
        var j: int=int(cell["row"])
        var light:=OmniLight3D.new()
        light.name="EmergencyCeilingLight_"+str(cell["id"])
        light.position=Vector3((float(xs[i])+float(xs[i+1]))*.5,
            2.85,(float(zs[j])+float(zs[j+1]))*.5)
        light.light_color=Color(1.0,0.63,0.31) if (i+j)%3==0 else Color(0.42,0.65,0.83)
        light.light_energy=1.45
        light.omni_range=12.0
        light.shadow_enabled=false
        add_child(light)
        _box(_props_root,"CeilingLuminaire",light.position+Vector3.UP*0.24,
            Vector3(0.9,0.12,0.65),"brass")
    var fog_color: Color=Color(0.12,0.18,0.23)
    set_meta("black_pines_art_direction","mountain snow, rust, emergency red, amber surgical lamps")
    set_meta("black_pines_palette_fog",fog_color)

func _build_spawn_markers() -> void:
    # Openings are the primary original-zombie entrance paths.
    # Direct test spawns stay outdoors and are only eligible after round 5.
    for i: int in range((_layout["outsideDirectSpawns"] as Array).size()):
        var pos:=_vector(_layout["outsideDirectSpawns"][i])
        var marker:=Marker3D.new()
        marker.name="OutdoorSpawn_%02d"%i
        marker.position=pos
        marker.add_to_group("zombie_spawn_anchor")
        marker.set_meta("spawn_id",marker.name)
        marker.set_meta("min_round",6)
        marker.set_meta("weight",0.3)
        marker.set_meta("entry_kind","offscreen")
        marker.set_meta("zone","mountain_perimeter")
        # Every exterior offscreen spawn must select an actual barricade
        # entrance. Pure direct chase from outside would hit a solid wall.
        var nearest_name: String=""
        var nearest_dist: float=INF
        for barricade: StaticBody3D in _barricades:
            var approach: Vector3=barricade.call("get_outside_spawn") as Vector3
            var dist: float=Vector2(pos.x-approach.x,pos.z-approach.z).length_squared()
            if dist<nearest_dist:
                nearest_dist=dist
                nearest_name=barricade.name
        if nearest_name.is_empty() or nearest_dist>20.0:
            push_error("BLACK_PINES_SPAWN_ROUTE_RED unmatched outside anchor "+marker.name)
            return
        marker.set_meta("routed_window_name",nearest_name)
        add_child(marker)

func _build_roof() -> void:
    var xs: Array=_layout["cellBoundaries"]["x"] as Array
    var zs: Array=_layout["cellBoundaries"]["z"] as Array
    for room: Dictionary in _layout["cells"]:
        if str(room["id"])=="yard":
            continue
        var c: int=int(room["col"])
        var r: int=int(room["row"])
        var left: float=float(xs[c])
        var right: float=float(xs[c+1])
        var start: float=float(zs[r])
        var finish: float=float(zs[r+1])
        _box(_roof_root,"Roof_"+str(room["id"]),
            Vector3((left+right)*0.5,3.87,(start+finish)*0.5),
            Vector3(right-left,0.19,finish-start),"dark_metal",false)

func set_roof_visible(value: bool) -> void:
    if _roof_root!=null:
        _roof_root.visible=value
    set_meta("black_pines_roof_visible",value)

func get_black_pines_contract() -> Dictionary:
    return {
        "layoutMapId":str(_layout.get("mapId","")),
        "zoneCount":(_layout.get("cells",[]) as Array).size(),
        "purchasableDoorCount":_doors.size(),
        "repairableWindowCount":_barricades.size(),
        "perkMachineCount":_machines.size(),
        "mysterySpots":(_layout.get("mysterySpots",[]) as Array).size(),
        "wallBuyCount":(_layout.get("wallbuys",[]) as Array).size(),
        "powerSwitchPresent":get_node_or_null("Machines/PowerSwitch")!=null,
        "packAPunchPresent":get_node_or_null("Machines/PackAPunch")!=null,
        "mysteryBoxPresent":_mystery!=null,
        "originalChurchSceneUnmodified":true,
        "originalZombieAnimationTestOnly":true,
        "gobblegumExcluded":true,
        "publicCopyrightAssetClearanceComplete":false,
        "real20RoundCompletionValidated":false,
        "actualAndroidPhysicalPerformanceValidated":false
    }
