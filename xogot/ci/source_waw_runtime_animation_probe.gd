extends SceneTree

const SOURCE_VARIANTS := {
	"honorgd": "res://assets/zombies/source_waw/honorgd/zombie.glb",
	"sumpf": "res://assets/zombies/source_waw/sumpf/zombie.glb",
}

const REQUIRED_SOURCE_ROLES := {
	"idle": ["ai_zombie_idle"],
	"walk": ["ai_zombie_walk_v", "ai_zombie_jap_walk_v"],
	"run": ["ai_zombie_run_v", "ai_zombie_jap_run_v"],
	"sprint": ["ai_zombie_sprint_v"],
	"attack": ["ai_zombie_attack", "ai_zombie_jap_attack"],
	"death": ["ai_zombie_death"],
	"traverse": ["ai_zombie_traverse"],
}

func _init() -> void:
	call_deferred("_run_probe")

func _fail(code: int, message: String) -> void:
	push_error("SOURCE_WAW_RUNTIME_PROBE: " + message)
	quit(code)

func _find_animation_player(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node as AnimationPlayer
	for child: Node in node.get_children():
		var found := _find_animation_player(child)
		if found != null:
			return found
	return null

func _role_present(names: Array[String], aliases: Array) -> bool:
	for name: String in names:
		var lower := name.to_lower()
		for alias_var: Variant in aliases:
			if lower.contains(str(alias_var).to_lower()):
				return true
	return false

func _gate_source_variant(id: String, path: String) -> bool:
	if not ResourceLoader.exists(path):
		_fail(20, id + " GLB missing: " + path)
		return false
	var packed := load(path) as PackedScene
	if packed == null:
		_fail(21, id + " GLB failed to load")
		return false
	var instance := packed.instantiate()
	if instance == null:
		_fail(22, id + " GLB failed to instantiate")
		return false
	var player := _find_animation_player(instance)
	if player == null:
		instance.free()
		_fail(23, id + " AnimationPlayer missing")
		return false
	var names: Array[String] = []
	for anim_name: StringName in player.get_animation_list():
		names.append(str(anim_name))
	for role_var: Variant in REQUIRED_SOURCE_ROLES.keys():
		var role := str(role_var)
		if not _role_present(names, REQUIRED_SOURCE_ROLES[role]):
			instance.free()
			_fail(24, id + " missing source role " + role + " names=" + str(names))
			return false
	print("XZOGOT_WAW_SOURCE_VARIANT_GREEN ", id, " anims=", names.size())
	instance.free()
	return true

func _run_probe() -> void:
	for id_var: Variant in SOURCE_VARIANTS.keys():
		var id := str(id_var)
		if not _gate_source_variant(id, str(SOURCE_VARIANTS[id])):
			return

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
		_fail(5, "normal baseline is not WaW Honor Guard: " + model_id)
		return
	if not bool(zombie.get_meta("zombie_source_waw", false)):
		_fail(6, "normal baseline is not marked source WaW")
		return
	if not bool(zombie.get_meta("zombie_source_scale_preserved", false)):
		_fail(7, "source zombie scale was not preserved")
		return
	if zombie.get_meta("zombie_visual_scale_xyz", Vector3.ZERO) != Vector3.ONE:
		_fail(8, "source zombie scale is not 1:1")
		return
	if not bool(zombie.get_meta("zombie_rig_ready", false)):
		_fail(9, "WaW source rig not runtime-ready")
		return

	var state_expect := {
		"idle": "ai_zombie_idle",
		"walk": "ai_zombie_walk",
		"attack": "ai_zombie_attack",
		"death": "ai_zombie_death",
	}
	for state_var: Variant in state_expect.keys():
		var state := str(state_var)
		zombie.set("_motion_state", "")
		zombie.call("_play_motion_state", state)
		var active := str(zombie.get_meta("active_animation", "")).to_lower()
		if not active.contains(str(state_expect[state])):
			_fail(10, "state " + state + " resolved to wrong source clip " + active)
			return
		print("XZOGOT_WAW_RUNTIME_STATE_GREEN ", state, " -> ", active)

	zombie.set("move_speed", 2.8)
	zombie.set("_motion_state", "")
	zombie.call("_play_motion_state", "walk")
	if not str(zombie.get_meta("active_animation", "")).to_lower().contains("ai_zombie_run"):
		_fail(11, "run speed did not select WaW run clip")
		return
	print("XZOGOT_WAW_RUNTIME_RUN_GREEN ", zombie.get_meta("active_animation", ""))

	zombie.set("move_speed", 4.0)
	zombie.set("_motion_state", "")
	zombie.call("_play_motion_state", "walk")
	if not str(zombie.get_meta("active_animation", "")).to_lower().contains("ai_zombie_sprint"):
		_fail(12, "sprint speed did not select WaW sprint clip")
		return
	print("XZOGOT_WAW_RUNTIME_SPRINT_GREEN ", zombie.get_meta("active_animation", ""))

	var health_before := float(player.call("get_health"))
	(zombie as Node3D).global_position = (player as Node3D).global_position + Vector3(0.0, 0.0, 1.0)
	zombie.set("phase", 2)
	zombie.set("_attack_timer", 0.0)
	zombie.call("_tick_chase")
	if float(player.call("get_health")) != health_before:
		_fail(13, "player damage happened before WaW attack animation impact")
		return
	if not bool(zombie.get_meta("player_attack_pending", false)):
		_fail(14, "WaW attack impact was not queued")
		return
	zombie.call("_update_player_attack_impact", float(zombie.get("player_attack_impact_delay")) + 0.02)
	if float(player.call("get_health")) >= health_before:
		_fail(15, "queued WaW attack never applied damage")
		return

	print("XZOGOT_WAW_ATTACK_IMPACT_SYNC_GREEN")
	print("XZOGOT_WAW_RUNTIME_ANIMATION_GATE_GREEN")
	scene.queue_free()
	await process_frame
	quit(0)
