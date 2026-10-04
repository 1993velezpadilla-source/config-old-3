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

	# Physical crypt -> basement -> reliquary traversal. This is deliberately
	# driven through CharacterBody3D movement instead of teleport-only node checks.
	var crypt_gate: Node = scene.get_node_or_null("CryptGate")
	if crypt_gate == null:
		_fail(16, "CryptGate missing")
		return
	player.call("add_points", 1250)
	if not bool(crypt_gate.call("interact", player)):
		_fail(17, "CryptGate could not be purchased/opened")
		return
	await physics_frame

	# Begin just beyond the opened gate, on the descending ramp. The gate
	# purchase itself is verified above; this avoids starting the capsule while
	# it is still touching the door's deferred-disabled collision volume.
	player.global_position = Vector3(16.0 * world_scale, -0.05, -2.20 * world_scale)
	player.rotation.y = 0.0
	player.set("_move_touch", 910)
	player.set("_move_vector", Vector2(0.0, -1.0))

	var reached_reliquary_corridor: bool = false
	var crypt_min_y: float = player.global_position.y
	for i in range(360):
		await physics_frame
		crypt_min_y = minf(crypt_min_y, player.global_position.y)
		if (
			# ReliquaryCorridorFloor begins near local z=-19.1. Requiring
			# local z<=-20 proves the player fully cleared the descending ramp.
			player.global_position.z <= -20.0 * world_scale
			and player.global_position.y <= -1.70
		):
			reached_reliquary_corridor = true
			break

	if not reached_reliquary_corridor:
		player.set("_move_touch", -1)
		player.set("_move_vector", Vector2.ZERO)
		_fail(
			18,
			"player failed crypt descent/reliquary corridor; pos=%s min_y=%s" % [
				player.global_position,
				crypt_min_y,
			]
		)
		return

	# Turn west into the reliquary chamber after clearing the 2.9m doorway.
	player.set("_move_vector", Vector2(-1.0, 0.0))
	var reached_ossuary: bool = false
	for i in range(220):
		await physics_frame
		if (
			player.global_position.x <= 11.0 * world_scale
			and player.global_position.z <= -25.6 * world_scale
			and player.global_position.y <= -1.70
		):
			reached_ossuary = true
			break

	player.set("_move_touch", -1)
	player.set("_move_vector", Vector2.ZERO)
	if not reached_ossuary:
		_fail(19, "player failed physical entry into Reliquary/Ossuary; pos=%s" % player.global_position)
		return

	var reliquary_zone: Node3D = scene.get_node_or_null("Zone_ReliquaryOssuary") as Node3D
	if reliquary_zone == null:
		_fail(20, "Reliquary zone marker missing")
		return
	if player.global_position.distance_to(reliquary_zone.global_position) > 9.5 * world_scale:
		_fail(21, "player traversal ended outside Reliquary zone: %s" % player.global_position)
		return

	print("XZOGOT_CRYPT_RELIQUARY_TRAVERSAL_GREEN ", player.global_position, " min_y=", crypt_min_y)
	print("XZOGOT_HUMAN_SCALE_GREEN ", floor_size)
	print("XZOGOT_BALCONY_TRAVERSAL_GREEN ", player.global_position)
	print("XZOGOT_CHURCH_TRAVERSAL_PROBE_GREEN")
	scene.queue_free()
	await process_frame
	quit(0)
