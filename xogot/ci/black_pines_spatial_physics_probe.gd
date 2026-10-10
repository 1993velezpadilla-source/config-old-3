extends SceneTree
## BLACK PINES: physical player-height collision acceptance.
## Not a navmesh, 20-round, or Android FPS certificate.
## Tests EVERY one of the 12 paid portals and 12 destructible windows.
const MAP_SCENE := preload("res://black_pines.tscn")
const BLUEPRINT := "res://data/black_pines_layout.json"

func _init() -> void:
    call_deferred("_run")

func _assert(condition: bool, message: String) -> bool:
    if condition:
        return true
    push_error("BLACK_PINES_SPATIAL_RED " + message)
    quit(51)
    return false

func _cast(state: PhysicsDirectSpaceState3D, from: Vector3,
        to: Vector3) -> Dictionary:
    var query := PhysicsRayQueryParameters3D.create(from, to)
    query.collide_with_bodies = true
    query.collide_with_areas = false
    return state.intersect_ray(query)

func _run() -> void:
    var raw: Variant=JSON.parse_string(FileAccess.get_file_as_string(BLUEPRINT))
    if not _assert(raw is Dictionary, "bad authored JSON"):
        return
    var layout: Dictionary=raw as Dictionary
    var scene: Node3D=MAP_SCENE.instantiate() as Node3D
    if not _assert(scene!=null, "cannot instantiate scene"):
        return
    scene.set("rounds_enabled", false)
    scene.set("preview_no_enemies", true)
    scene.set("prefer_blender_geometry", false)
    root.add_child(scene)
    await physics_frame
    await physics_frame
    var space: PhysicsDirectSpaceState3D=scene.get_world_3d().direct_space_state
    var doors: Array=layout["portals"] as Array
    var windows: Array=layout["windows"] as Array
    if not _assert(doors.size()==12 and windows.size()==12,
        "portal or window count mismatch"):
        return
    for i in range(doors.size()):
        var data: Dictionary=doors[i] as Dictionary
        var axis: String=str(data["axis"])
        var coord: float=float(data["coord"])
        var at: float=float(data["at"])
        var center: Vector3=Vector3(coord,1.25,at) if axis=="x" else Vector3(at,1.25,coord)
        var offset: Vector3=Vector3(1.9,0,0) if axis=="x" else Vector3(0,0,1.9)
        var door: Node=scene.get_node_or_null("Machines/Door_%02d"%i)
        if not _assert(door!=null, "missing door "+str(i)):
            return
        for lane: float in [-0.65,0.0,0.65]:
            var lateral: Vector3=Vector3(0,0,lane) if axis=="x" else Vector3(lane,0,0)
            var blocked: Dictionary=_cast(space,center-offset+lateral,center+offset+lateral)
            if not _assert(blocked.get("collider",null)==door,
                "closed portal "+str(i)+" lane="+str(lane)+" hit="+str(blocked.get("collider",null))):
                return
        if not _assert(bool(door.call("dev_force_open")),
            "cannot open paid door "+str(i)):
            return
        await physics_frame
        for lane: float in [-0.65,0.0,0.65]:
            var lateral: Vector3=Vector3(0,0,lane) if axis=="x" else Vector3(lane,0,0)
            var opened: Dictionary=_cast(space,center-offset+lateral,center+offset+lateral)
            if not _assert(opened.is_empty(),
                "opened portal "+str(i)+" lane="+str(lane)+" hit="+str(opened.get("collider",null))):
                return
    for i in range(windows.size()):
        var barrier: Node=scene.get_node_or_null("Architecture/Barricade_%02d"%i)
        if not _assert(barrier!=null, "missing barricade "+str(i)):
            return
        var outside: Vector3=barrier.call("get_outside_approach")
        var inside: Vector3=barrier.call("get_inside_point")
        outside.y=1.25
        inside.y=1.25
        var axis: String=str((windows[i] as Dictionary)["axis"])
        for lane: float in [-0.65,0.0,0.65]:
            var lateral: Vector3=Vector3(0,0,lane) if axis=="x" else Vector3(lane,0,0)
            var blocked: Dictionary=_cast(space,outside+lateral,inside+lateral)
            if not _assert(blocked.get("collider",null)==barrier,
                "intact window "+str(i)+" lane="+str(lane)+" hit="+str(blocked.get("collider",null))):
                return
        barrier.call("zombie_damage",400.0)
        if not _assert(bool(barrier.call("is_broken")),
            "barricade damage did not destroy boards "+str(i)):
            return
        await physics_frame
        for lane: float in [-0.65,0.0,0.65]:
            var lateral: Vector3=Vector3(0,0,lane) if axis=="x" else Vector3(lane,0,0)
            var opened: Dictionary=_cast(space,outside+lateral,inside+lateral)
            if not _assert(opened.is_empty(),
                "breached window "+str(i)+" lane="+str(lane)+" hit="+str(opened.get("collider",null))):
                return
    print("BLACK_PINES_SPATIAL_PHYSICS_GREEN 12_closed_then_open_doors=true",
        " 12_closed_then_breached_windows=true",
        " three_lateral_rays_each=true real_Godot_raycast=true",
        " full_20_round_navmesh=false physical_android=false")
    scene.queue_free()
    await process_frame
    quit(0)
