extends SceneTree

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("CHURCH_EXPANSION_PROBE: " + message)
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

	var expected_zones: Array[String] = [
		"FrontCourtyard",
		"WestOuterLoop",
		"EastOuterLoop",
		"RearRuinsYard",
		"GraveyardPath",
		"BellTowerAccessYard",
		"Sacristy",
		"CryptAccess",
	]
	for zone_name: String in expected_zones:
		if scene.get_node_or_null("Zone_" + zone_name) == null:
			_fail(3, "missing gameplay zone: " + zone_name)
			return

	var zones: Array[Node] = get_nodes_in_group("gameplay_zone")
	if zones.size() != 8:
		_fail(4, "expected 8 gameplay zones, got %d" % zones.size())
		return

	var ramps: Array[Node] = get_nodes_in_group("expansion_walkable_ramp")
	if ramps.size() != 3:
		_fail(5, "expected 3 expansion ramps (crypt + 2 tower), got %d" % ramps.size())
		return

	var required_nodes: Array[String] = [
		"FrontCourtyardFloor",
		"WestOuterLoopFloor",
		"EastOuterLoopFloor",
		"RearRuinsYardFloor",
		"CryptBasementFloor",
		"BellTowerLowerFloor",
		"BellTowerMidLanding",
		"BellTowerTopLanding",
		"ChurchBellBody",
	]
	for node_name: String in required_nodes:
		if scene.get_node_or_null(node_name) == null:
			_fail(6, "missing expansion node: " + node_name)
			return

	var player: CharacterBody3D = scene.get_node_or_null("Player") as CharacterBody3D
	if player == null:
		_fail(7, "player missing")
		return

	var gates: Array[String] = [
		"WestOuterGate",
		"EastOuterGate",
		"RearRuinsGate",
		"BellTowerGate",
	]
	for gate_name: String in gates:
		var gate: Node = scene.get_node_or_null(gate_name)
		if gate == null:
			_fail(8, "missing buy gate: " + gate_name)
			return
		if not gate.has_method("interact") or not gate.has_method("was_used"):
			_fail(9, "gate interaction API missing: " + gate_name)
			return

	player.call("add_points", 1250)
	var bell_gate: Node = scene.get_node_or_null("BellTowerGate")
	if not bool(bell_gate.call("interact", player)):
		_fail(10, "BellTowerGate purchase failed")
		return
	await physics_frame
	if not bool(bell_gate.call("was_used")):
		_fail(11, "BellTowerGate did not open")
		return

	var ground: Node3D = scene.get_node_or_null("Ground") as Node3D
	if ground == null:
		_fail(12, "Ground missing")
		return
	var ground_mesh_instance: MeshInstance3D = ground.get_child(0) as MeshInstance3D
	if ground_mesh_instance == null or not (ground_mesh_instance.mesh is BoxMesh):
		_fail(13, "Ground mesh missing")
		return
	var ground_size: Vector3 = (ground_mesh_instance.mesh as BoxMesh).size
	if ground_size.x < 87.0 or ground_size.z < 91.0:
		_fail(14, "expanded playable ground too small: %s" % ground_size)
		return

	print("XZOGOT_EXPANSION_GROUND_GREEN ", ground_size)
	print("XZOGOT_EXPANSION_ZONES_PROBE_GREEN ", zones.size())
	print("XZOGOT_EXPANSION_RAMPS_PROBE_GREEN ", ramps.size())
	print("XZOGOT_EXPANSION_BUY_GATE_PROBE_GREEN")
	print("XZOGOT_BELL_TOWER_PROBE_GREEN")
	print("XZOGOT_CHURCH_EXPANSION_PROBE_GREEN")
	scene.queue_free()
	await process_frame
	quit(0)
