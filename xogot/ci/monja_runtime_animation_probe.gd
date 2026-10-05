extends SceneTree

func _init() -> void:
	call_deferred("_run_probe")

func _fail(code: int, message: String) -> void:
	push_error("MONJA_RUNTIME_ANIMATION_PROBE: " + message)
	quit(code)

func _run_probe() -> void:
	var packed: PackedScene = load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(2, "main scene missing")
		return

	var scene := packed.instantiate()
	root.add_child(scene)
	await process_frame
	await physics_frame

	var player: Node = scene.get_node_or_null("Player")
	var round_manager: Node = scene.get_node_or_null("RoundManager")
	var barricades: Array[Node] = get_nodes_in_group("zombie_barricade")
	if player == null or round_manager == null or barricades.is_empty():
		_fail(3, "player/round manager/barricade missing")
		return

	round_manager.set("auto_start", false)
	var barricade: Node = barricades[0]
	barricade.call("repair_full_no_reward")
	round_manager.call("start_next_round")
	round_manager.set("_spawn_timer", 999.0)
	var zombie: Node = round_manager.call("spawn_from_barricade", barricade) as Node
	if zombie == null:
		_fail(4, "failed to spawn normal zombie")
		return
	await process_frame

	if str(zombie.get_meta("zombie_model", "")) != "monja_clean":
		_fail(5, "normal zombie is not clean V4 monja: " + str(zombie.get_meta("zombie_model", "")))
		return
	if not bool(zombie.get_meta("zombie_rig_ready", false)):
		_fail(6, "clean monja rig not runtime-ready")
		return

	var expected := {
		"idle": "idle",
		"walk": "walk",
		"attack": "attack",
		"hit": "hit",
		"death": "death",
	}
	for state: String in expected:
		zombie.set("_motion_state", "")
		zombie.call("_play_motion_state", state)
		var active := str(zombie.get_meta("active_animation", "")).to_lower()
		if not active.contains(str(expected[state])):
			_fail(7, "state " + state + " resolved to wrong clip " + active)
			return
		print("XZOGOT_MONJA_STATE_GREEN ", state, " -> ", active)

	var health_before := float(player.call("get_health"))
	(zombie as Node3D).global_position = (player as Node3D).global_position + Vector3(0.0, 0.0, 1.0)
	zombie.set("phase", 2)
	zombie.set("_attack_timer", 0.0)
	zombie.call("_tick_chase")
	if float(player.call("get_health")) != health_before:
		_fail(8, "player damage happened before attack animation impact")
		return
	if not bool(zombie.get_meta("player_attack_pending", false)):
		_fail(9, "attack impact was not queued")
		return
	zombie.call("_update_player_attack_impact", float(zombie.get("player_attack_impact_delay")) + 0.02)
	if float(player.call("get_health")) >= health_before:
		_fail(10, "queued attack never applied damage")
		return

	print("XZOGOT_MONJA_ATTACK_IMPACT_SYNC_GREEN")
	print("XZOGOT_MONJA_RUNTIME_ANIMATION_GATE_GREEN")
	scene.queue_free()
	await process_frame
	quit(0)
