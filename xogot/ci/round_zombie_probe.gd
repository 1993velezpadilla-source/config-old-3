extends SceneTree

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
	var barricades: Array[Node] = get_nodes_in_group("zombie_barricade")
	if barricades.size() != 8:
		_fail(4, "expected 8 barricades, got %d" % barricades.size())
		return

	var barricade: Node = barricades[0]
	if int(barricade.call("get_boards")) != 3:
		_fail(5, "barricade did not start with 3 boards")
		return

	for i in range(6):
		barricade.call("zombie_damage", 25.0)
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
	if not bool(barricade.call("is_broken")):
		_fail(10, "repaired barricade did not break again")
		return

	round_manager.call("start_next_round")
	round_manager.set("_spawn_timer", 999.0)
	if int(round_manager.call("get_round")) != 1:
		_fail(11, "round 1 did not start")
		return
	if int(round_manager.call("get_remaining_to_spawn")) != 4:
		_fail(12, "round 1 zombie count wrong")
		return

	var zombie: Node = round_manager.call("spawn_one") as Node
	if zombie == null:
		_fail(13, "round manager failed to spawn zombie")
		return
	if int(round_manager.call("get_alive")) != 1:
		_fail(14, "alive count wrong after spawn")
		return
	if int(round_manager.call("get_remaining_to_spawn")) != 3:
		_fail(15, "remaining spawn count wrong")
		return

	await physics_frame
	await physics_frame
	if int(zombie.call("get_phase")) != 2:
		_fail(16, "zombie did not cross broken barricade into chase phase")
		return

	var points_before_kill: int = int(player.call("get_points"))
	for i in range(4):
		zombie.call("apply_damage", 30.0, player)
	await process_frame
	if int(round_manager.call("get_alive")) != 0:
		_fail(17, "round manager did not receive zombie death")
		return
	if int(player.call("get_points")) != points_before_kill + 100:
		_fail(18, "hit + kill points wrong")
		return

	player.call("heal_full")
	player.call("apply_damage", 20.0)
	if absf(float(player.call("get_health")) - 80.0) > 0.01:
		_fail(19, "player health damage wrong")
		return
	player.call("apply_damage", 80.0)
	if not bool(player.call("is_downed")):
		_fail(20, "player did not enter downed state")
		return

	print("XZOGOT_ROUND_ZOMBIE_PROBE_GREEN")
	scene.queue_free()
	await process_frame
	quit(0)
