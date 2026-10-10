extends SceneTree
## Black Pines real Godot 3D physics: nine authored hero-prop colliders.
## Thin proxy boxes avoid heavyweight triangle mesh on Android. This is
## geometry acceptance, not a physically measured Android FPS certificate.
const SCENE:=preload("res://black_pines.tscn")
const MANIFEST: String="res://data/black_pines_layout.json"
func _init() -> void:
    call_deferred("_run")

func _require(ok: bool, why: String) -> bool:
    if ok:
        return true
    push_error("BLACK_PINES_HERO_COLLIDER_RED "+why)
    quit(74)
    return false

func _cast(world: PhysicsDirectSpaceState3D,
        start: Vector3,end: Vector3) -> Dictionary:
    var ray:=PhysicsRayQueryParameters3D.create(start,end)
    ray.collide_with_bodies=true
    return world.intersect_ray(ray)

func _vec(a: Array) -> Vector3:
    return Vector3(float(a[0]),float(a[1]),float(a[2]))

func _run() -> void:
    var raw: Variant=JSON.parse_string(FileAccess.get_file_as_string(MANIFEST))
    if not _require(raw is Dictionary,"no original shared layout"):
        return
    var layout: Dictionary=raw as Dictionary
    var fixtures: Array=layout["heroCollisionProxies"] as Array
    var level: Node3D=SCENE.instantiate() as Node3D
    if not _require(level!=null,"original map missing"):
        return
    level.set("rounds_enabled",false)
    level.set("preview_no_enemies",true)
    level.set("prefer_blender_geometry",false)
    root.add_child(level)
    await physics_frame
    await physics_frame
    if not _require(fixtures.size()==9,"incorrect fixture manifest count"):
        return
    var contract: Dictionary=level.call("get_black_pines_contract") as Dictionary
    if not _require(int(contract.get("heroSolidCollisionCount",0))==9,
            "original scene missing nine physical hero proxies"):
        return
    var space: PhysicsDirectSpaceState3D=level.get_world_3d().direct_space_state
    var ids: Dictionary={}
    for fixture: Dictionary in fixtures:
        var id: String=str(fixture["id"])
        if not _require(not ids.has(id),"duplicate authored hero "+id):
            return
        ids[id]=true
        var name: String="Scenery/HeroSolid_"+id
        var body: StaticBody3D=level.get_node_or_null(name) as StaticBody3D
        if not _require(body!=null and body.collision_layer!=0,
                "missing physical hero "+name):
            return
        var shape_node: CollisionShape3D=body.get_node_or_null(
            "CollisionShape3D") as CollisionShape3D
        if not _require(shape_node!=null and shape_node.shape is BoxShape3D,
                "hero has no mobile BoxShape3D "+id):
            return
        var center: Vector3=_vec(fixture["center"])
        var dims: Vector3=_vec(fixture["size"])
        if not _require(body.global_position.distance_to(center)<0.02
            and (shape_node.shape as BoxShape3D).size.distance_to(dims)<0.02,
                "visual/physics authority drifts "+id):
            return
        var from: Vector3=center-Vector3(dims.x*.5+.28,0,0)
        var to: Vector3=center+Vector3(dims.x*.5+.28,0,0)
        var hit: Dictionary=_cast(space,from,to)
        if not _require(hit.get("collider",null)==body,
                "walk-through hero fixture "+id+" got "+str(hit.get("collider",null))):
            return
    # Open all 12 purchased gates. No hero collision may block any of the
    # three real player-height ray lanes through the open portals.
    var portals: Array=layout["portals"] as Array
    for idx in range(portals.size()):
        var door: Node=level.get_node_or_null("Machines/Door_%02d"%idx)
        if not _require(door!=null and bool(door.call("dev_force_open")),
                "paid portal unavailable "+str(idx)):
            return
    await physics_frame
    var ray_count: int=0
    for data: Dictionary in portals:
        var is_x: bool=str(data["axis"])=="x"
        var center: Vector3=Vector3(float(data["coord"]),1.25,float(data["at"])) if is_x else (
            Vector3(float(data["at"]),1.25,float(data["coord"])))
        var normal: Vector3=Vector3(1.9,0,0) if is_x else Vector3(0,0,1.9)
        for lane: float in [-.65,0.0,.65]:
            var lateral: Vector3=Vector3(0,0,lane) if is_x else Vector3(lane,0,0)
            var hit: Dictionary=_cast(space,center-normal+lateral,center+normal+lateral)
            if not _require(hit.is_empty(),
                    "hero furniture blocks open portal "+str(data)):
                return
            ray_count+=1
    print("BLACK_PINES_NINE_REAL_HERO_COLLIDERS_GREEN",
        " 9_physical_3D_boxes=true 36_open_portal_rays_clear=",ray_count,
        " native_mesh_duplication=none shared_blender_manifest=true",
        " Android_physical_test=false")
    level.queue_free()
    await process_frame
    quit(0)
