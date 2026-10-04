extends SceneTree

# Monja Basica native asset gate.

func _init() -> void:
	call_deferred("_run_probe")

func _fail(code: int, message: String) -> void:
	push_error("ROUND_ZOMBIE_PROBE: " + message)
	quit(code)

func _run_probe() -> void:
	var packed: PackedScene = load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(2, "main scene missing")
		return

	var scene: Node = packed.instantiate()
	root.add_child(scene)
	await process_frame
	await physics_frame
	await physics_frame

	var player: Node = scene.get_node_or_null("Player")
	var round_manager: Node = scene.get_node_or_null("RoundManager")
	if player == null or round_manager == null:
		_fail(3, "player or round manager missing")
		return

	round_manager.set("auto_start", false)

	var expected_round_counts := {
		1: 6,
		2: 8,
		3: 13,
		4: 18,
		5: 24,
		10: 33,
		20: 60,
		30: 105,
	}
	for round_id: int in expected_round_counts:
		var actual_count: int = int(round_manager.call("zombies_for_round", round_id, 1))
		if actual_count != int(expected_round_counts[round_id]):
			_fail(46, "classic zombie count wrong R%d: %d" % [round_id, actual_count])
			return
	if int(round_manager.call("get_simultaneous_cap")) != 24:
		_fail(47, "classic simultaneous cap must be 24")
		return
	var expected_health := {1: 150, 9: 950, 10: 1045, 20: 2710}
	for round_id: int in expected_health:
		var actual_health: int = int(round_manager.call("zombie_health_for_round", round_id))
		if actual_health != int(expected_health[round_id]):
			_fail(48, "classic zombie health wrong R%d: %d" % [round_id, actual_health])
			return
	print("XZOGOT_CLASSIC_ROUND_FLOW_GREEN counts=", expected_round_counts)
	print("XZOGOT_CLASSIC_ZOMBIE_HEALTH_GREEN ", expected_health)
	print("XZOGOT_CLASSIC_SIMULTANEOUS_CAP_GREEN 24")

	var expected_coop := {
		2: {1: 7, 5: 27, 10: 42, 20: 96},
		3: {1: 9, 5: 32, 10: 60, 20: 168},
		4: {1: 10, 5: 37, 10: 78, 20: 240},
	}
	for player_count: int in expected_coop:
		var player_rounds: Dictionary = expected_coop[player_count] as Dictionary
		for round_id: int in player_rounds:
			var actual_count: int = int(round_manager.call("zombies_for_round", round_id, player_count))
			if actual_count != int(player_rounds[round_id]):
				_fail(
					50,
					"classic co-op count wrong P%d R%d: %d" % [
						player_count,
						round_id,
						actual_count,
					]
				)
				return
	print("XZOGOT_CLASSIC_COOP_ROUND_FLOW_GREEN ", expected_coop)

	var barricades: Array[Node] = get_nodes_in_group("zombie_barricade")
	if barricades.size() != 8:
		_fail(4, "expected 8 barricades, got %d" % barricades.size())
		return

	var barricade: Node = barricades[0]
	var path_networks: Array[Node] = get_nodes_in_group("zombie_path_network")
	if path_networks.size() != 1:
		_fail(39, "expected one zombie path network")
		return
	if int(round_manager.call("get_direct_spawn_count")) != 8:
		_fail(40, "expected eight selective direct spawns")
		return
	if int(barricade.call("get_boards")) != 6:
		_fail(5, "barricade did not start with 3 boards")
		return

	barricade.call("zombie_damage", 300.0)
	if not bool(barricade.call("is_broken")) or int(barricade.call("get_boards")) != 0:
		_fail(6, "zombie damage did not break barricade")
		return

	var points_before_repair: int = int(player.call("get_points"))
	if not bool(barricade.call("interact", player)):
		_fail(7, "repair interaction failed")
		return
	if int(barricade.call("get_boards")) != 1:
		_fail(8, "repair did not restore exactly one board")
		return
	if int(player.call("get_points")) != points_before_repair + 10:
		_fail(9, "repair reward wrong")
		return

	# Break it again so the first spawned zombie can transition through the socket.
	barricade.call("zombie_damage", 50.0)
	await physics_frame
	if not bool(barricade.call("is_broken")):
		_fail(10, "repaired barricade did not break again")
		return

	round_manager.call("start_next_round")
	round_manager.set("_spawn_timer", 999.0)
	if int(round_manager.call("get_round")) != 1:
		_fail(11, "round 1 did not start")
		return
	if int(round_manager.call("get_remaining_to_spawn")) != 6:
		_fail(12, "round 1 zombie count wrong")
		return

	var zombie: Node = round_manager.call("spawn_from_barricade", barricade) as Node
	if zombie == null:
		_fail(13, "round manager failed to spawn zombie")
		return
	if int(round_manager.call("get_alive")) != 1:
		_fail(14, "alive count wrong after spawn")
		return
	if int(round_manager.call("get_remaining_to_spawn")) != 5:
		_fail(15, "remaining spawn count wrong")
		return
	if zombie.get_node_or_null("MonjaBasicaVisual") == null:
		_fail(21, "Monja Basica visual was not instantiated")
		return
	if absf(float(zombie.call("get_health")) - 150.0) > 0.01:
		_fail(49, "round 1 classic health was not applied")
		return
	var monja_model: String = str(zombie.get_meta("zombie_model", ""))
	if monja_model not in [
		"monja_basica",
		"monja_basica_rigged",
		"monja_basica_rigged_dismember",
		"monja_basica_rigid_rig",
	]:
		_fail(22, "Monja Basica model metadata missing: " + monja_model)
		return
	if ResourceLoader.exists("res://assets/zombies/monja_rigid/monja_basica_rigid_rig.gltf"):
		if monja_model != "monja_basica_rigid_rig":
			_fail(42, "full-density rigid Monja exists but runtime did not select it")
			return
		if not bool(zombie.get_meta("zombie_rigged_asset", false)):
			_fail(43, "rigid Monja was not marked rigged")
			return
		if not bool(zombie.get_meta("zombie_rigid_region_rig", false)):
			_fail(44, "rigid-region rig marker missing")
			return
		if zombie.get_node_or_null("MonjaBasicaVisual") == null:
			_fail(45, "rigged Monja visual missing")
			return
	if str(zombie.get_meta("motion_profile", "")).is_empty():
		_fail(41, "Monja Basica motion profile missing")
		return
	var fitted_height: float = float(zombie.get_meta("zombie_visual_height_m", 0.0))
	var fitted_width: float = float(zombie.get_meta("zombie_visual_width_m", 0.0))
	var fitted_depth: float = float(zombie.get_meta("zombie_visual_depth_m", 0.0))
	if fitted_height < 1.79 or fitted_height > 1.81:
		_fail(23, "Monja Basica fitted height out of range: %s" % fitted_height)
		return
	if fitted_width < 0.89 or fitted_width > 0.91:
		_fail(24, "Monja Basica fitted width out of range: %s" % fitted_width)
		return
	if fitted_depth < 0.71 or fitted_depth > 0.73:
		_fail(25, "Monja Basica fitted depth out of range: %s" % fitted_depth)
		return
	if not bool(zombie.get_meta("zombie_visual_centered_on_feet", false)):
		_fail(26, "Monja Basica is not foot-centered")
		return
	var zombie_collider: CollisionShape3D = zombie.get_node_or_null("ZombieCollider") as CollisionShape3D
	if zombie_collider == null:
		_fail(27, "Monja Basica collider missing")
		return
	var zombie_capsule: CapsuleShape3D = zombie_collider.shape as CapsuleShape3D
	if zombie_capsule == null:
		_fail(28, "Monja Basica capsule missing")
		return
	if absf(zombie_capsule.radius - 0.34) > 0.001 or absf(zombie_capsule.height - 1.78) > 0.001:
		_fail(29, "Monja Basica collider dimensions wrong")
		return
	if absf(float(zombie.get("headshot_height_ratio")) - 0.84) > 0.001:
		_fail(38, "Monja Basica headshot height ratio wrong")
		return

	var spawn_position: Vector3 = (zombie as Node3D).global_position
	var inside_point: Vector3 = barricade.call("get_inside_point") as Vector3

	await physics_frame
	await physics_frame
	if int(zombie.call("get_phase")) != 4:
		_fail(16, "zombie skipped physical CROSS_WINDOW phase")
		return
	if (zombie as Node3D).global_position.distance_to(inside_point) < 0.35:
		_fail(30, "zombie teleported through the window instead of traversing it")
		return

	var crossed_physically: bool = false
	for i in range(180):
		await physics_frame
		if not is_instance_valid(zombie):
			_fail(31, "zombie vanished during window traversal")
			return
		if int(zombie.call("get_phase")) == 2:
			crossed_physically = true
			break

	if not crossed_physically:
		var stuck_position: Vector3 = (zombie as Node3D).global_position
		var world: World3D = (zombie as Node3D).get_world_3d()
		var blocker_name: String = "none"
		if world != null:
			var from: Vector3 = stuck_position + Vector3(0.0, 0.85, 0.0)
			var to: Vector3 = inside_point + Vector3(0.0, 0.85, 0.0)
			var ray := PhysicsRayQueryParameters3D.create(from, to)
			ray.exclude = [(zombie as CollisionObject3D).get_rid()]
			var hit: Dictionary = world.direct_space_state.intersect_ray(ray)
			if not hit.is_empty():
				var blocker: Object = hit.get("collider") as Object
				if blocker != null:
					blocker_name = str(blocker.get("name"))
		_fail(
			32,
			"zombie could not physically cross; stuck=%s inside=%s blocker=%s" % [
				stuck_position,
				inside_point,
				blocker_name
			]
		)
		return

	var crossed_position: Vector3 = (zombie as Node3D).global_position
	if crossed_position.distance_to(inside_point) > 0.45:
		_fail(33, "zombie entered chase phase before reaching the interior side")
		return
	if crossed_position.distance_to(spawn_position) < 2.0:
		_fail(34, "zombie did not actually travel through the wall opening")
		return

	print("XZOGOT_WINDOW_PHYSICAL_CROSS_GREEN")

	var points_before_kill: int = int(player.call("get_points"))

	# Body hit: 30 damage, +10 points. Round 1 starts at classic 150 HP.
	zombie.call("apply_damage", 30.0, player)
	if absf(float(zombie.call("get_health")) - 120.0) > 0.01:
		_fail(35, "body damage amount wrong")
		return

	# Head hit: 30 x 2 damage, +10 hit +10 headshot bonus.
	var head_position: Vector3 = (zombie as Node3D).global_position + Vector3(0.0, 1.56, 0.0)
	zombie.call("apply_hitscan_damage", 30.0, player, head_position)
	if not bool(zombie.get_meta("last_hit_headshot", false)):
		_fail(36, "head impact was not classified as headshot")
		return
	if absf(float(zombie.call("get_health")) - 60.0) > 0.01:
		_fail(37, "headshot multiplier wrong")
		return

	# Final body hit kills. Total award stays 100 points:
	# 10 body + 20 headshot + 10 final hit + 60 kill.
	zombie.call("apply_damage", 60.0, player)
	await process_frame
	if int(round_manager.call("get_alive")) != 0:
		_fail(17, "round manager did not receive zombie death")
		return
	if int(player.call("get_points")) != points_before_kill + 100:
		_fail(18, "body/headshot/kill points accounting wrong")
		return
	print("XZOGOT_ENEMY_SCALE_PROBE_GREEN")
	print("XZOGOT_HEADSHOT_PROBE_GREEN")

	player.call("heal_full")
	player.call("apply_damage", 20.0)
	if absf(float(player.call("get_health")) - 80.0) > 0.01:
		_fail(19, "player health damage wrong")
		return
	player.call("apply_damage", 80.0)
	if not bool(player.call("is_downed")):
		_fail(20, "player did not enter downed state")
		return

	print("XZOGOT_ZOMBIE_PATHING_PROBE_GREEN")
	print("XZOGOT_ZOMBIE_MOTION_PROFILE_GREEN ", zombie if is_instance_valid(zombie) else "freed")
	print("XZOGOT_ROUND_ZOMBIE_PROBE_GREEN")
	scene.queue_free()
	await process_frame
	quit(0)
