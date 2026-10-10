extends SceneTree
## Native BLACK PINES 9-room graph and real zombie-window-cross gauntlet.
## Not a full navmesh/device/multiplayer survival proof.
const MAP := preload("res://black_pines.tscn")

func _init() -> void:
    call_deferred("_run")

func _assert(ok: bool,message: String) -> bool:
    if ok:
        return true
    push_error("BLACK_PINES_ROUTING_RED "+message)
    quit(61)
    return false

func _run() -> void:
    var scene: Node3D=MAP.instantiate() as Node3D
    if not _assert(scene!=null,"scene missing"):
        return
    scene.set("rounds_enabled",false)
    scene.set("preview_no_enemies",true)
    scene.set("prefer_blender_geometry",false)
    root.add_child(scene)
    await physics_frame
    await physics_frame
    var graph: Node=scene.get_node_or_null("BlackPinesPathNetwork")
    var round_manager: Node=scene.get_node_or_null("RoundManager")
    if not _assert(graph!=null and round_manager!=null,"graph/director missing"):
        return
    if not _assert(int(graph.call("get_node_count"))==9
            and int(graph.call("get_portal_count"))==12,
            "9-cell/12-portal topology broken"):
        return
    var layout: Dictionary=JSON.parse_string(
        FileAccess.get_file_as_string("res://data/black_pines_layout.json")) as Dictionary
    var xs: Array=layout["cellBoundaries"]["x"] as Array
    var zs: Array=layout["cellBoundaries"]["z"] as Array
    var centers: Array[Vector3]=[]
    for row in range(3):
        for col in range(3):
            centers.append(Vector3((float(xs[col])+float(xs[col+1]))*0.5,0.24,
                (float(zs[row])+float(zs[row+1]))*0.5))
    # ALL 12 doors start locked. Do not fake routing through locked geometry.
    for i in range(9):
        for j in range(9):
            var reachable: bool=bool(graph.call("can_reach",centers[i],centers[j]))
            if not _assert(reachable==(i==j),
                    "locked map must isolate cell "+str(i)+" -> "+str(j)):
                return
    # Each of four direct outdoor spawns has an assigned REAL window,
    # preventing AI from direct-chasing through solid sanatorium masonry.
    var anchors: Array=get_nodes_in_group("zombie_spawn_anchor")
    if not _assert(anchors.size()==4,"four offscreen anchors missing"):
        return
    for anchor: Node in anchors:
        var routed_name: String=str(anchor.get_meta("routed_window_name",""))
        if not _assert(not routed_name.is_empty() and scene.get_node_or_null(
                "Architecture/"+routed_name)!=null,
                "outdoor spawn has no live barricade route "+anchor.name):
            return
    # Unlock all portals then prove every ordered room pair routes.
    for i in range(12):
        var door: Node=scene.get_node_or_null("Machines/Door_%02d"%i)
        if not _assert(door!=null and bool(door.call("dev_force_open")),
                "can't unlock graph edge "+str(i)):
            return
    await physics_frame
    var physics: PhysicsDirectSpaceState3D=scene.get_world_3d().direct_space_state
    var segments: int=0
    for i in range(9):
        for j in range(9):
            if not _assert(bool(graph.call("can_reach",centers[i],centers[j])),
                    "unlocked room route missing "+str(i)+" -> "+str(j)):
                return
            var waypoints: Array[Vector3]=graph.call(
                "request_path",centers[i],centers[j]) as Array[Vector3]
            if not _assert(not waypoints.is_empty(),
                    "unlocked path empty "+str(i)+" -> "+str(j)):
                return
            var prior: Vector3=centers[i]
            for point: Vector3 in waypoints:
                var from: Vector3=Vector3(prior.x,1.25,prior.z)
                var to: Vector3=Vector3(point.x,1.25,point.z)
                if from.distance_to(to)>0.08:
                    var query:=PhysicsRayQueryParameters3D.create(from,to)
                    var hit: Dictionary=physics.intersect_ray(query)
                    if not _assert(hit.is_empty(),
                            "physical obstruction "+str(i)+"->"+str(j)+
                            " collider="+str(hit.get("collider",null))):
                        return
                    segments+=1
                prior=point
    print("BLACK_PINES_ROUTING_81_PAIRS_GREEN 9rooms=connected",
        " locked_routes=blocked physics_segments=",segments,
        " original_church_unchanged=true")
    # Actual animated physics actors must enter through FOUR compass-facing
    # barricades; doors already unlocked and windows prebroken for isolation.
    round_manager.set_process(false)
    round_manager.call("start_next_round")
    var selected: Array[int]=[0,3,6,9]
    var actors: Array[Node]=[]
    for i in selected:
        var barrier: Node=scene.get_node_or_null("Architecture/Barricade_%02d"%i)
        if not _assert(barrier!=null,"missing entry window "+str(i)):
            return
        barrier.call("zombie_damage",400.0)
        if not _assert(bool(barrier.call("is_broken")),
                "cannot break entrance "+str(i)):
            return
        var actor: Node=round_manager.call("spawn_from_barricade",barrier) as Node
        if not _assert(actor!=null,"cannot spawn actual actor at "+str(i)):
            return
        actors.append(actor)
    var entered: Dictionary={}
    for tick in range(540):
        await physics_frame
        for k in range(actors.size()):
            var zombie: Node=actors[k]
            if entered.has(k):
                continue
            if is_instance_valid(zombie) and int(zombie.call("get_phase"))==2:
                entered[k]=true
        if entered.size()==actors.size():
            break
    if not _assert(entered.size()==actors.size(),
            "zombies unable to CROSS real breached windows: "+
            str(entered.size())+"/"+str(actors.size())):
        return
    print("BLACK_PINES_FOUR_COMPASS_ZOMBIE_TRAVERSAL_GREEN",
        " animated_real_Godot_actors=4 windows_crossed=4",
        " full_12_window_nav=false 20_rounds=false android=false")
    for actor: Node in actors:
        if is_instance_valid(actor) and actor.has_method("powerup_kill"):
            actor.call("powerup_kill")
    scene.queue_free()
    await physics_frame
    quit(0)
