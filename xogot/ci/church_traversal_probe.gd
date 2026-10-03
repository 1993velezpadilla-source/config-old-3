extends SceneTree

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("CHURCH_TRAVERSAL_PROBE: " + message)
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
	await physics_frame

	var round_manager: Node = scene.get_node_or_null("RoundManager")
	if round_manager != null:
		round_manager.set("auto_start", false)

	if scene.get_node_or_null("LeftWall") != null or scene.get_node_or_null("RightWall") != null:
		_fail(3, "legacy monolithic side wall still exists")
		return

	var window_ramps: Array[Node] = get_nodes_in_group("zombie_window_ramp")
	if window_ramps.size() != 8:
		_fail(4, "expected 8 physical window threshold ramps, got %d" % window_ramps.size())
		return

	var stair_ramps: Array[Node] = get_nodes_in_group("walkable_stair_ramp")
	if stair_ramps.size() != 1:
		_fail(5, "expected one continuous balcony stair ramp")
		return
	var world_scale: float = float(scene.get_meta("world_scale", 1.0))
	if world_scale < 0.77 or world_scale > 0.79:
		_fail(12, "unexpected human world scale: %s" % world_scale)
		return

	var player: CharacterBody3D = scene.get_node_or_null("Player") as CharacterBody3D
	if player == null:
		_fail(6, "player missing")
		return

	var balcony_gate: Node = scene.get_node_or_null("BalconyGate")
	if balcony_gate == null:
		_fail(9, "BalconyGate missing")
		return
	player.call("add_points", 1000)
	if not bool(balcony_gate.call("interact", player)):
		_fail(10, "BalconyGate could not be purchased/opened")
		return
	await physics_frame
	if not bool(balcony_gate.call("was_used")):
		_fail(11, "BalconyGate did not enter opened state")
		return

	player.global_position = Vector3(-8.0 * world_scale, 0.38, 0.10 * world_scale)
	player.rotation.y = 0.0
	player.set("_move_touch", 909)
	player.set("_move_vector", Vector2(0.0, 1.0))

	var reached_balcony: bool = false
	var max_height: float = player.global_position.y
	for i in range(240):
		await physics_frame
		max_height = maxf(max_height, player.global_position.y)
		if player.global_position.z >= 8.35 * world_scale and player.global_position.y >= 4.55 * world_scale:
			reached_balcony = true
			break

	player.set("_move_touch", -1)
	player.set("_move_vector", Vector2.ZERO)

	if not reached_balcony:
		_fail(
			7,
			"player failed stair traversal; pos=%s max_y=%s" % [
				player.global_position,
				max_height
			]
		)
		return

	await physics_frame
	if player.global_position.y < 4.45 * world_scale:
		_fail(8, "player fell through balcony after reaching top")
		return

	var floor_node: Node3D = scene.get_node_or_null("ChurchFloor") as Node3D
	if floor_node == null:
		_fail(13, "ChurchFloor missing")
		return
	var floor_mesh_instance: MeshInstance3D = floor_node.get_child(0) as MeshInstance3D
	if floor_mesh_instance == null or not (floor_mesh_instance.mesh is BoxMesh):
		_fail(14, "ChurchFloor mesh missing")
		return
	var floor_size: Vector3 = (floor_mesh_instance.mesh as BoxMesh).size
	if absf(floor_size.x - 17.16) > 0.05 or absf(floor_size.z - 29.64) > 0.05:
		_fail(15, "human scale floor dimensions wrong: %s" % floor_size)
		return

	print("XZOGOT_HUMAN_SCALE_GREEN ", floor_size)
	print("XZOGOT_BALCONY_TRAVERSAL_GREEN ", player.global_position)
	print("XZOGOT_CHURCH_TRAVERSAL_PROBE_GREEN")
	scene.queue_free()
	await process_frame
	quit(0)
