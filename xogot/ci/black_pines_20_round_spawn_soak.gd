extends SceneTree
## Black Pines LIVE Godot round-director spawn/death soak.
## NOT a substitute for 20 played rounds or actual Android framerate.
## Every scheduled enemy from rounds 1..20 is instantiated with the REAL
## round manager, connected to an existing window and killed using its REAL
## zombie death event. Director cap of 24 is verified on the late-wave burst.
const MAP_SCENE:=preload("res://black_pines.tscn")
const FINAL_ROUND: int=20
const SIMULTANEOUS_CAP: int=24
var _seen_rounds: Array[int]=[]
var _cleared_rounds: Array[int]=[]

func _init() -> void:
    call_deferred("_run")

func _check(ok: bool, why: String) -> bool:
    if ok:
        return true
    push_error("BLACK_PINES_20_ROUND_SOAK_RED "+why)
    quit(71)
    return false

func _on_started(number: int,_total: int) -> void:
    _seen_rounds.append(number)

func _on_cleared(number: int) -> void:
    _cleared_rounds.append(number)

func _kill_real_enemy(enemy: Node) -> bool:
    if not _check(enemy != null and enemy.has_method("powerup_kill"),
            "missing actual zombie death method"):
        return false
    # This routes through zombie_dummy.gd::_die() -> signal died and the
    # actual manager's _on_zombie_died callback.
    enemy.set_process(false)
    enemy.set_physics_process(false)
    enemy.call("powerup_kill")
    enemy.queue_free()
    return true

func _run() -> void:
    var level: Node3D=MAP_SCENE.instantiate() as Node3D
    if not _check(level!=null,"cannot instantiate playable Black Pines"):
        return
    level.set("rounds_enabled",false)
    level.set("preview_no_enemies",true)
    level.set("prefer_blender_geometry",false)
    root.add_child(level)
    await process_frame
    await physics_frame
    var director: Node=level.get_node_or_null("RoundManager")
    if not _check(director!=null,"director missing"):
        return
    if not _check(not bool(director.get("special_rounds_enabled")),
            "sheep rounds leaked into original Black Pines"):
        return
    director.set_process(false)  # skip timers, but keep genuine spawn()/signals
    director.connect("round_started",Callable(self,"_on_started"))
    director.connect("round_cleared",Callable(self,"_on_cleared"))
    var player: Node3D=level.get_node_or_null("Player") as Node3D
    if not _check(player!=null,"missing real player spawn target"):
        return
    player.set_process(false)
    player.set_physics_process(false)
    var global_spawned: int=0
    var late_cap_tested: bool=false
    var serial_at_start: int=0
    var max_concurrent_observed: int=0
    for round_no in range(1,FINAL_ROUND+1):
        director.call("start_next_round")
        var actual_round: int=int(director.call("get_round"))
        if not _check(actual_round==round_no,
                "round skipped or repeated expected="+str(round_no)+" actual="+str(actual_round)):
            return
        var expected: int=int(director.call("get_round_total"))
        if not _check(expected>0 and expected<200,
                "invalid director wave population r="+str(round_no)+"/"+str(expected)):
            return
        var deaths_before: int=_cleared_rounds.size()
        var killed: int=0
        if round_no==FINAL_ROUND:
            # A true burst exercises the MAX-ALIVE 24 guard rather than
            # relying exclusively on single-zombie spawn/death simulation.
            var burst: Array[Node]=[]
            for i in range(SIMULTANEOUS_CAP):
                var enemy: Node=director.call("spawn_one") as Node
                if not _check(enemy!=null,"round20 cannot fill 24 actor cap"):
                    return
                enemy.set_process(false)
                enemy.set_physics_process(false)
                burst.append(enemy)
            max_concurrent_observed=maxi(max_concurrent_observed,
                                          int(director.call("get_alive")))
            if not _check(int(director.call("get_alive"))==SIMULTANEOUS_CAP
                and director.call("spawn_one")==null,
                    "max 24 simultaneous zombie cap not enforced"):
                return
            if not _check(int(director.call("get_remaining_to_spawn"))==expected-SIMULTANEOUS_CAP,
                    "24 actor cap accidentally consumed unspawned actors"):
                return
            late_cap_tested=true
            for enemy: Node in burst:
                if not _kill_real_enemy(enemy):
                    return
                killed+=1
            await process_frame
        while int(director.call("get_remaining_to_spawn"))>0:
            var enemy: Node=director.call("spawn_one") as Node
            if not _check(enemy!=null,
                    "real spawn blocked at round "+str(round_no)+" index "+str(killed)):
                return
            if not _check(str(enemy.get_meta("round_number",""))==str(round_no),
                    "actual enemy round metadata wrong"):
                return
            max_concurrent_observed=maxi(max_concurrent_observed,
                                          int(director.call("get_alive")))
            if not _kill_real_enemy(enemy):
                return
            killed+=1
            if killed%12==0:
                await process_frame
        if not _check(killed==expected and int(director.call("get_alive"))==0
                and int(director.call("get_remaining_to_spawn"))==0
                and int(director.call("get_round_spawned"))==expected,
                "undead or count mismatch r="+str(round_no)+
                " actual="+str(killed)+" planned="+str(expected)):
            return
        if not _check(_cleared_rounds.size()==deaths_before+1
                and _cleared_rounds.back()==round_no,
                "round clear not emitted exactly once r="+str(round_no)):
            return
        global_spawned+=killed
        await process_frame
        print("BLACK_PINES_20_ROUND_SOAK_WAVE_GREEN round=",round_no,
              " spawned_and_killed=",killed," total=",global_spawned)
    if not _check(_seen_rounds.size()==FINAL_ROUND
        and _cleared_rounds.size()==FINAL_ROUND
        and late_cap_tested and max_concurrent_observed==SIMULTANEOUS_CAP,
            "director rounds, simultaneous cap or completion inconsistent"):
        return
    print("BLACK_PINES_20_ROUND_DIRECTOR_SOAK_GREEN",
        " rounds=20 spawned_and_killed=",global_spawned,
        " cap=24 cap_blocked_at_round20=true actual_zombie_actor_deaths=true",
        " true_physical_20_round_android_gameplay=false")
    level.queue_free()
    await process_frame
    quit(0)
