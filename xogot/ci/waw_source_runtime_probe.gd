extends SceneTree

func _init() -> void:
	call_deferred("_run_probe")

func _fail(code: int, message: String) -> void:
	push_error("WAW_SOURCE_RUNTIME_PROBE: " + message)
	quit(code)

func _expect_source_state(zombie: Node, state: String, speed: float, token: String) -> bool:
	zombie.set("move_speed", speed)
	zombie.set("_motion_state", "")
	zombie.call("_play_motion_state", state)
	var active := str(zombie.get_meta("active_animation", "")).to_lower()
	if not active.contains(token.to_lower()):
		_fail(20, "state %s resolved to %s; expected token %s" % [state, active, token])
		return false
	print("XZOGOT_WAW_SOURCE_STATE_GREEN ", state, " -> ", active)
	return true

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
		_fail(4, "failed to spawn source zombie")
		return
	await process_frame

	var model_id := str(zombie.get_meta("zombie_model", ""))
	if model_id != "waw_honorgd":
		_fail(5, "normal zombie is not WaW Honor Guard source baseline: " + model_id)
		return
	if not bool(zombie.get_meta("zombie_source_waw", false)):
		_fail(6, "WaW source authority metadata missing")
		return
	if not bool(zombie.get_meta("zombie_rig_ready", false)):
		_fail(7, "WaW source rig not runtime-ready")
		return
	if not bool(zombie.get_meta("zombie_source_scale_preserved", false)):
		_fail(8, "WaW source scale was not preserved 1:1")
		return
	var scale_xyz: Vector3 = zombie.get_meta("zombie_visual_scale_xyz", Vector3.ZERO) as Vector3
	if not scale_xyz.is_equal_approx(Vector3.ONE):
		_fail(9, "WaW source visual was heuristically rescaled: " + str(scale_xyz))
		return
	print("XZOGOT_WAW_SOURCE_MODEL_GREEN ", model_id, " scale=", scale_xyz)

	if not _expect_source_state(zombie, "idle", 1.85, "ai_zombie_idle_v1_delta"):
		return
	if not _expect_source_state(zombie, "walk", 1.85, "ai_zombie_walk_v1"):
		return
	if not _expect_source_state(zombie, "walk", 2.20, "ai_zombie_walk_fast_v1"):
		return
	if not _expect_source_state(zombie, "walk", 2.80, "ai_zombie_run_v1"):
		return
	if not _expect_source_state(zombie, "walk", 3.80, "ai_zombie_sprint_v1"):
		return
	if not _expect_source_state(zombie, "attack", 1.85, "ai_zombie_attack"):
		return
	if not _expect_source_state(zombie, "death", 1.85, "ai_zombie_death"):
		return
	if not _expect_source_state(zombie, "traverse", 1.85, "ai_zombie_traverse"):
		return

	# The validated 57-PSA WaW set has no dedicated hit-reaction or crawler clip.
	# Hit flinch remains procedural and crawler visual stays source-pending rather
	# than substituting an unrelated animation.
	zombie.set("_motion_state", "")
	zombie.call("_play_motion_state", "hit")
	print("XZOGOT_WAW_SOURCE_HIT_PROCEDURAL_GREEN")
	zombie.set_meta("motion_override", "crawl")
	zombie.set("_motion_state", "")
	zombie.call("_play_motion_state", "walk")
	if not bool(zombie.get_meta("crawler_visual_source_pending", false)):
		_fail(10, "crawler source-pending guard missing")
		return
	zombie.set_meta("motion_override", "")
	print("XZOGOT_WAW_SOURCE_CRAWLER_PENDING_TRUTHFUL_GREEN")

	# Preserve the existing gameplay contract: player damage lands only after
	# the authored attack begins, never immediately on proximity.
	var health_before := float(player.call("get_health"))
	(zombie as Node3D).global_position = (player as Node3D).global_position + Vector3(0.0, 0.0, 1.0)
	zombie.set("phase", 2)
	zombie.set("_attack_timer", 0.0)
	zombie.set("_motion_state", "")
	zombie.call("_tick_chase")
	if float(player.call("get_health")) != health_before:
		_fail(11, "player damage happened before source attack impact")
		return
	if not bool(zombie.get_meta("player_attack_pending", false)):
		_fail(12, "source attack impact was not queued")
		return
	zombie.call("_update_player_attack_impact", float(zombie.get("player_attack_impact_delay")) + 0.02)
	if float(player.call("get_health")) >= health_before:
		_fail(13, "queued source attack never applied damage")
		return

	print("XZOGOT_WAW_SOURCE_ATTACK_IMPACT_SYNC_GREEN")
	print("XZOGOT_WAW_SOURCE_RUNTIME_GATE_GREEN")
	scene.queue_free()
	await process_frame
	quit(0)
