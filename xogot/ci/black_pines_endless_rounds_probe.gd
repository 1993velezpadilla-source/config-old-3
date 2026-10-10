extends SceneTree
## ENDLESS survival regression for BLACK PINES only.
## Real Godot director/actor spawn and death for round 21. Sample real
## director + actual zombie actors at rounds 50, 100, 255, 256, 1000,
## 10000, 1000000: test high-round math without spawning a million waves.
## NOT a million physically played rounds or an Android benchmark.
const MAP_SCENE:=preload("res://black_pines.tscn")
const FUTURE_ROUNDS: Array[int]=[50,100,255,256,1000,10000,1000000]
var cleared_rounds: Array[int]=[]
var started_rounds: Array[int]=[]

func _init() -> void:
    call_deferred("_run")

func _require(yes: bool, message: String) -> bool:
    if yes:
        return true
    push_error("BLACK_PINES_ENDLESS_RED "+message)
    quit(72)
    return false

func _on_round_start(number: int,_count: int) -> void:
    started_rounds.append(number)

func _on_round_clear(number: int) -> void:
    cleared_rounds.append(number)

func _kill(z: Node) -> bool:
    if not _require(z!=null and z.has_method("powerup_kill"),
            "missing real zombie death path"):
        return false
    z.set_process(false)
    z.set_physics_process(false)
    z.call("powerup_kill")
    z.queue_free()
    return true

func _run() -> void:
    var scene: Node3D=MAP_SCENE.instantiate() as Node3D
    if not _require(scene!=null,"original Black Pines scene missing"):
        return
    scene.set("rounds_enabled",false)
    scene.set("preview_no_enemies",true)
    scene.set("prefer_blender_geometry",false)
    root.add_child(scene)
    await process_frame
    await physics_frame
    var director: Node=scene.get_node_or_null("RoundManager")
    var player: Node=scene.get_node_or_null("Player")
    if not _require(director!=null and player!=null,"round director / player missing"):
        return
    if not _require(bool(director.call("is_endless_survival"))
            and int(director.call("get_configured_round_limit"))==0
            and not bool(director.get("special_rounds_enabled")),
            "endless gameplay not enabled on Black Pines"):
        return
    director.set_process(false)
    player.set_process(false)
    player.set_physics_process(false)
    director.connect("round_started",Callable(self,"_on_round_start"))
    director.connect("round_cleared",Callable(self,"_on_round_clear"))
    var old_player1: int=0
    # A real wave past round 20: every actual zombie is constructed, assigned
    # a routed real spawn, killed, and accounted for exactly once.
    director.call("apply_network_round_state",20,0,0,0,0.0)
    director.call("start_next_round")
    if not _require(int(director.call("get_round"))==21,
            "hard stop at round 20"):
        return
    var expected: int=int(director.call("get_round_total"))
    if not _require(expected>=60 and expected<=144,"invalid round21 population"):
        return
    var killed: int=0
    while int(director.call("get_remaining_to_spawn"))>0:
        var z: Node=director.call("spawn_one") as Node
        if not _require(z!=null and str(z.get_meta("round_number"))=="21",
                "round21 actor spawning failed at "+str(killed)):
            return
        if not _kill(z):
            return
        killed+=1
        if killed%12==0:
            await process_frame
    if not _require(killed==expected
            and int(director.call("get_remaining_to_spawn"))==0
            and int(director.call("get_alive"))==0
            and cleared_rounds==[21],
            "round21 failed to clear after actual actors"):
        return
    print("BLACK_PINES_ENDLESS_REAL_ROUND21_GREEN",
        " spawned_and_killed=",killed," cleared=21")
    await process_frame
    var samples: int=0
    for round_num: int in FUTURE_ROUNDS:
        # Snapshot synchronisation is the REAL production manager API:
        # synthetic skip is only to test arithmetic and new-wave behavior,
        # not a claim that intermediate levels have been physically played.
        director.call("apply_network_round_state",round_num-1,0,0,0,0.0)
        director.call("start_next_round")
        var actual: int=int(director.call("get_round"))
        var total: int=int(director.call("get_round_total"))
        var health: int=int(director.call("zombie_health_for_round",round_num))
        var interval: float=float(director.call("spawn_interval_for_round",round_num))
        var speed: float=float(director.call("zombie_speed_for_round",round_num,1))
        var pop4: int=int(director.call("zombies_for_round",round_num,4))
        if not _require(actual==round_num
                and total>0 and total<=144
                and pop4>=total and pop4<=192
                and health>=950 and health<=250000
                and interval>=0.30 and interval<=1.7
                and speed>0.0 and speed<=5.0,
                "high-round progression invalid r="+str(round_num)+
                " population="+str(total)+
                " HP="+str(health)+" speed="+str(speed)):
            return
        var z: Node=director.call("spawn_one") as Node
        if not _require(z!=null and int(z.get_meta("round_number",0))==round_num,
                "no actual zombie at high round "+str(round_num)):
            return
        if not _require(float(z.get("health"))>0.0
                and float(z.get("health"))<=250000.0,
                "zombie instance health overflow "+str(round_num)):
            return
        if not _kill(z):
            return
        if not _require(int(director.call("get_alive"))==0
                and int(director.call("get_remaining_to_spawn"))==total-1,
                "director bookkeeping wrong at "+str(round_num)):
            return
        director.call("dev_clear_zombies")
        samples+=1
        await process_frame
        print("BLACK_PINES_ENDLESS_HIGH_ROUND_SAMPLE_GREEN",
            " round=",round_num," population=",total,
            " four_player_population=",pop4," HP=",health)
    if not _require(samples==FUTURE_ROUNDS.size()
        and started_rounds.size()==samples+1
        and started_rounds.back()==1000000
        and cleared_rounds==[21],
            "endless sampled-round signal ordering broken"):
        return
    print("BLACK_PINES_ENDLESS_SURVIVAL_GREEN",
        " terminal_round=none verified_actual_round21=true",
        " sampled_high_rounds=",samples,
        " highest_sampled_round=1000000",
        " solo_wave_cap=144 four_player_wave_cap=192 simultaneous_cap=24",
        " android_performance_not_measured=true")
    scene.queue_free()
    await process_frame
    quit(0)
