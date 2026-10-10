extends SceneTree
## Native gameplay acceptance without a baked commercial source map.
## GREEN here is functionally scoped: physical Android long-play NOT measured.
const MAP_SCENE := preload("res://black_pines.tscn")

func _init() -> void:
    call_deferred("_run")

func _assert(check: bool,message: String) -> bool:
    if check:
        return true
    push_error("BLACK_PINES_PHASE1_RED "+message)
    quit(37)
    return false

func _run() -> void:
    var scene: Node3D=MAP_SCENE.instantiate() as Node3D
    if not _assert(scene!=null,"scene failed to instantiate"):
        return
    scene.set("rounds_enabled",false)
    scene.set("prefer_blender_geometry",false)
    root.add_child(scene)
    await process_frame
    await physics_frame
    var report: Dictionary=scene.call("get_black_pines_contract") as Dictionary
    for entry: Array in [["zoneCount",9],["purchasableDoorCount",12],
        ["repairableWindowCount",12],["perkMachineCount",6],
        ["wallBuyCount",5],["mysterySpots",4]]:
        if not _assert(int(report.get(str(entry[0]),-1))==int(entry[1]),
            "contract mismatch "+str(entry[0])+": "+str(report.get(str(entry[0]),null))):
            return
    if not _assert(
        bool(report.get("gobblegumExcluded",false))
        and not bool(report.get("publicCopyrightAssetClearanceComplete",true))
        and not bool(report.get("real20RoundCompletionValidated",true))
        and not bool(report.get("actualAndroidPhysicalPerformanceValidated",true)),
        "shipping / goal status falsely claimed"):
        return
    var player: Node=scene.get_node_or_null("Player")
    var round_manager: Node=scene.get_node_or_null("RoundManager")
    var pickup_manager: Node=scene.get_node_or_null("PowerUpManager")
    var power: Node=scene.get_node_or_null("Machines/PowerSwitch")
    var perk: Node=scene.get_node_or_null("Machines/Perk_martyrs_blood")
    var pack: Node=scene.get_node_or_null("Machines/PackAPunch")
    var mystery: Node=scene.get_node_or_null("Machines/MysteryBox")
    var doors: Array=scene.get_node("Machines").get_children().filter(
        func(n: Node) -> bool: return n.name.begins_with("Door_"))
    var windows: Array=get_nodes_in_group("zombie_barricade")
    if not _assert(player!=null and round_manager!=null and pickup_manager!=null
        and power!=null and perk!=null and pack!=null and mystery!=null
        and doors.size()==12 and windows.size()==12,
        "gameplay shared nodes or new independent map actor family absent"):
        return
    player.call("add_points",50000)
    var initial: int=int(player.call("get_points"))
    if not _assert(not bool(perk.call("interact",player))
        and int(player.call("get_points"))==initial,
        "perk charged/purchased without power"):
        return
    if not _assert(bool(power.call("interact",player)) and
        bool(get_meta("power_on",false)),
        "switch power and source perk API not connected"):
        return
    if not _assert(bool(perk.call("interact",player)) and
        bool(player.call("has_perk","martyrs_blood")),
        "powered perk purchase/health modifier not applied"):
        return
    var perk_owned_price: int=int(player.call("get_points"))
    if not _assert(not bool(perk.call("interact",player)) and
        int(player.call("get_points"))==perk_owned_price,
        "duplicate perk incorrectly charged"):
        return
    var first_door: Node=doors[0] as Node
    if not _assert(bool(first_door.call("interact",player))
        and bool(first_door.call("was_used")),
        "buyable original room gate unusable"):
        return
    var barrier: Node=windows[0] as Node
    barrier.call("zombie_damage",400.0)
    if not _assert(bool(barrier.call("is_broken")),
        "zombie board physical state cannot be broken"):
        return
    var before_boards: int=int(barrier.call("get_boards"))
    if not _assert(bool(barrier.call("interact",player)) and
        int(barrier.call("get_boards"))==before_boards+1,
        "player repair interaction failed"):
        return
    pickup_manager.call("collect_powerup","carpenter",player)
    if not _assert(int(barrier.call("get_boards"))==6,
        "Carpenter fails full repair"):
        return
    pickup_manager.call("collect_powerup","double_points",player)
    if not _assert(bool(pickup_manager.call("is_double_points_active")),
        "double points not active"):
        return
    pickup_manager.call("collect_powerup","insta_kill",player)
    if not _assert(bool(pickup_manager.call("is_insta_kill_active")),
        "insta kill not active"):
        return
    if not _assert(int(round_manager.call("get_direct_spawn_count"))==4,
        "independent source-map non-window spawn anchors not registered"):
        return
    # Verify original World at War baseline anim inventory remains present.
    var files: Array[String]=[
        "res://assets/zombies/source_waw/honorgd/zombie.glb",
        "res://assets/zombies/source_waw/sumpf/zombie.glb"]
    for path: String in files:
        if not _assert(ResourceLoader.exists(path),
            "internal-only zombie animated GLB missing "+path):
            return
    print("BLACK_PINES_PHASE1_GAMEPLAY_GREEN zones=9 doors=12 windows=12",
        " perks=6 wallbuys=5 mystery=4",
        " power=true repair=true carpenter=true insta=true double=true",
        " WaW_test_only=true public_ship=false 20round_untested=true")
    scene.queue_free()
    await process_frame
    quit(0)
