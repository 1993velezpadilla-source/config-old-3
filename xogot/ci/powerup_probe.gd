extends SceneTree

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("POWERUP_PROBE: " + message)
	quit(code)

func _run() -> void:
	var packed: PackedScene = load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(2, "main scene missing")
		return

	var scene: Node = packed.instantiate()
	root.add_child(scene)
	await process_frame
	await physics_frame

	var player: Node = scene.get_node_or_null("Player")
	var weapon: Node = scene.get_node_or_null("Player/Weapon")
	var rounds: Node = scene.get_node_or_null("RoundManager")
	var powerups: Node = scene.get_node_or_null("PowerUpManager")
	if player == null or weapon == null or rounds == null or powerups == null:
		_fail(3, "player/weapon/rounds/powerups missing")
		return

	rounds.set("auto_start", false)
	if not powerups.has_method("collect_powerup"):
		_fail(4, "powerup manager API missing")
		return

	# DOUBLE POINTS: every score award goes through Player.add_points.
	powerups.call("debug_clear_timed_effects")
	var points_before: int = int(player.call("get_points"))
	if not bool(powerups.call("collect_powerup", "double_points", player)):
		_fail(5, "double points pickup rejected")
		return
	player.call("add_points", 50)
	if int(player.call("get_points")) != points_before + 100:
		_fail(6, "double points did not double score")
		return
	if not bool(powerups.call("is_double_points_active")):
		_fail(7, "double points timer not active")
		return
	print("XZOGOT_DOUBLE_POINTS_PROBE_GREEN")
	powerups.call("debug_clear_timed_effects")

	# CARPENTER: restore every barricade without per-board repair rewards.
	var barricades: Array[Node] = get_nodes_in_group("zombie_barricade")
	if barricades.is_empty():
		_fail(8, "no barricades")
		return
	var barricade: Node = barricades[0]
	barricade.call("zombie_damage", 999.0)
	if int(barricade.call("get_boards")) != 0:
		_fail(9, "test barricade did not break")
		return
	points_before = int(player.call("get_points"))
	powerups.call("collect_powerup", "carpenter", player)
	if int(barricade.call("get_boards")) != int(barricade.call("get_max_boards")):
		_fail(10, "Carpenter did not fully restore barricade")
		return
	if int(player.call("get_points")) != points_before + 200:
		_fail(11, "Carpenter award wrong")
		return
	print("XZOGOT_CARPENTER_PROBE_GREEN")

	# INSTA-KILL: one point of damage must kill a full-health R1 Monja.
	rounds.call("start_next_round")
	rounds.set("_spawn_timer", 999.0)
	var zombie: Node = rounds.call("spawn_from_barricade", barricade) as Node
	if zombie == null:
		_fail(12, "failed to spawn insta-kill probe zombie")
		return
	if float(zombie.call("get_health")) < 149.0:
		_fail(13, "probe zombie does not have classic round health")
		return
	powerups.call("collect_powerup", "insta_kill", player)
	zombie.call("apply_damage", 1.0, player)
	await process_frame
	if int(rounds.call("get_alive")) != 0:
		_fail(14, "Insta-Kill did not kill zombie")
		return
	print("XZOGOT_INSTA_KILL_PROBE_GREEN")
	powerups.call("debug_clear_timed_effects")

	# NUKE: kill all currently alive zombies and award 400 once per player.
	for _i in range(3):
		var nuke_zombie: Node = rounds.call("spawn_from_barricade", barricade) as Node
		if nuke_zombie == null:
			_fail(15, "failed to populate Nuke test")
			return
	if int(rounds.call("get_alive")) != 3:
		_fail(16, "Nuke setup alive count wrong")
		return
	points_before = int(player.call("get_points"))
	powerups.call("collect_powerup", "nuke", player)
	await process_frame
	if int(rounds.call("get_alive")) != 0:
		_fail(17, "Nuke left zombies alive")
		return
	if int(player.call("get_points")) != points_before + 400:
		_fail(18, "Nuke score award wrong")
		return
	print("XZOGOT_NUKE_PROBE_GREEN")

	# MAX AMMO through a REAL physical drop and proximity collection.
	weapon.set("reserve_ammo", 0)
	weapon.set("_magazine", 0)
	var pickup: Node3D = powerups.call(
		"spawn_powerup",
		"max_ammo",
		(player as Node3D).global_position
	) as Node3D
	if pickup == null:
		_fail(19, "physical Max Ammo drop failed")
		return
	await process_frame
	await process_frame
	if int(weapon.call("get_magazine")) <= 0 or int(weapon.call("get_reserve")) <= 0:
		_fail(20, "physical Max Ammo did not refill weapon")
		return
	print("XZOGOT_MAX_AMMO_PHYSICAL_PICKUP_GREEN")

	# Anti-spam: never allow more than two uncollected drops at once.
	var far := (player as Node3D).global_position + Vector3(20.0, 0.0, 20.0)
	var p1: Node = powerups.call("spawn_powerup", "double_points", far) as Node
	var p2: Node = powerups.call("spawn_powerup", "insta_kill", far + Vector3(1.0, 0.0, 0.0)) as Node
	var p3: Node = powerups.call("spawn_powerup", "carpenter", far + Vector3(2.0, 0.0, 0.0)) as Node
	if p1 == null or p2 == null or p3 != null:
		_fail(21, "active drop cap is not two")
		return
	if get_nodes_in_group("xz_powerup_pickup").size() != 2:
		_fail(22, "active physical drop count wrong")
		return
	print("XZOGOT_POWERUP_ANTISPAM_GREEN")

	for node: Node in get_nodes_in_group("xz_powerup_pickup"):
		node.queue_free()
	await process_frame

	print("XZOGOT_CLASSIC_POWERUP_SYSTEM_GREEN")
	scene.queue_free()
	await process_frame
	quit(0)
