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
		"SecondFloorWest",
		"SecondFloorEast",
		"SecondFloorChoir",
		"ReliquaryOssuary",
		"WestOssuaryGarden",
		"EastPilgrimCloister",
	]
	for zone_name: String in expected_zones:
		if scene.get_node_or_null("Zone_" + zone_name) == null:
			_fail(3, "missing gameplay zone: " + zone_name)
			return

	var zones: Array[Node] = get_nodes_in_group("gameplay_zone")
	if zones.size() != 14:
		_fail(4, "expected 14 gameplay zones, got %d" % zones.size())
		return
	if get_nodes_in_group("second_floor_zone").size() != 3:
		_fail(5, "expected 3 second-floor zones")
		return

	if get_nodes_in_group("church_revival_zone").size() != 2:
		_fail(29, "both revival courtyards must be true gameplay zones")
		return
	for wing_name: String in ["WestOssuaryGarden", "EastPilgrimCloister"]:
		var floor_node: Node = scene.get_node_or_null(wing_name + "Floor")
		var outer_wall: Node = scene.get_node_or_null(wing_name + "OuterWall")
		if not (floor_node is StaticBody3D and outer_wall is StaticBody3D):
			_fail(30, "missing physical floor/wall in " + wing_name)
			return
	print("XZOGOT_REVIVAL_TWO_WALKABLE_COURTYARDS_GREEN")

	var ramps: Array[Node] = get_nodes_in_group("expansion_walkable_ramp")
	if ramps.size() != 3:
		_fail(6, "expected 3 expansion ramps (crypt + 2 tower), got %d" % ramps.size())
		return

	var required_nodes: Array[String] = [
		"FrontCourtyardFloor",
		"WestOuterLoopFloor",
		"EastOuterLoopFloor",
		"RearRuinsYardFloor",
		"CryptBasementFloor",
		"ReliquaryCorridorFloor",
		"ReliquaryFloor",
		"GeneratorBase",
		"SecondFloorWestGallery",
		"SecondFloorEastGallery",
		"SecondFloorChoirBridge",
		"BellTowerLowerFloor",
		"BellTowerMidLanding",
		"BellTowerTopLanding",
		"ChurchBellBody",
	]
	for node_name: String in required_nodes:
		if scene.get_node_or_null(node_name) == null:
			_fail(7, "missing expansion node: " + node_name)
			return

	var networks: Array[Node] = get_nodes_in_group("zombie_path_network")
	if networks.size() != 1:
		_fail(8, "expected one zombie path network")
		return
	if int(networks[0].call("get_node_count")) < 31:
		_fail(9, "path network node count too small for Reliquary route")
		return
	if get_nodes_in_group("zombie_spawn_anchor").size() != 8:
		_fail(10, "expected 8 selective non-window spawn anchors")
		return

	var last_rites: Node3D = scene.get_node_or_null("Perk_last_rites") as Node3D
	if last_rites == null:
		_fail(19, "Last Rites machine missing")
		return
	if last_rites.global_position.y > -1.0:
		_fail(20, "Last Rites must be in underground Reliquary")
		return
	var power_switch: Node3D = scene.get_node_or_null("PowerSwitch") as Node3D
	if power_switch == null:
		_fail(21, "Power switch missing")
		return
	if power_switch.global_position.x > -5.0:
		_fail(22, "Power switch was not moved into west Generator Room")
		return

	var player: CharacterBody3D = scene.get_node_or_null("Player") as CharacterBody3D
	if player == null:
		_fail(11, "player missing")
		return

	var gates: Array[String] = [
		"WestOuterGate",
		"EastOuterGate",
		"RearRuinsGate",
		"BellTowerGate",
		"CryptGate",
	]
	for gate_name: String in gates:
		var gate: Node = scene.get_node_or_null(gate_name)
		if gate == null:
			_fail(12, "missing buy gate: " + gate_name)
			return
		if not gate.has_method("interact") or not gate.has_method("was_used"):
			_fail(13, "gate interaction API missing: " + gate_name)
			return

	player.call("add_points", 1250)
	var bell_gate: Node = scene.get_node_or_null("BellTowerGate")
	if not bool(bell_gate.call("interact", player)):
		_fail(14, "BellTowerGate purchase failed")
		return
	await physics_frame
	if not bool(bell_gate.call("was_used")):
		_fail(15, "BellTowerGate did not open")
		return

	var ground_segments: Array[String] = [
		"Ground",
		"GroundEast",
		"GroundCryptNorth",
		"GroundCryptSouth",
	]
	for ground_name: String in ground_segments:
		var segment: Node3D = scene.get_node_or_null(ground_name) as Node3D
		if segment == null:
			_fail(16, "ground segment missing: " + ground_name)
			return
		var mesh_instance: MeshInstance3D = segment.get_child(0) as MeshInstance3D
		if mesh_instance == null or not (mesh_instance.mesh is BoxMesh):
			_fail(17, "ground segment mesh missing: " + ground_name)
			return

	var ground_main: Node3D = scene.get_node_or_null("Ground") as Node3D
	var main_mesh: MeshInstance3D = ground_main.get_child(0) as MeshInstance3D
	var ground_size: Vector3 = (main_mesh.mesh as BoxMesh).size
	if ground_size.z < 91.0:
		_fail(18, "segmented ground no longer spans full map depth: %s" % ground_size)
		return

	var shaft: Marker3D = scene.get_node_or_null("CryptGroundShaft") as Marker3D
	if shaft == null:
		_fail(23, "CryptGroundShaft marker missing")
		return
	if absf(float(shaft.get_meta("opening_width_m", 0.0)) - 2.8) > 0.01:
		_fail(24, "crypt shaft width changed")
		return
	if get_nodes_in_group("crypt_traversal_shaft").size() != 1:
		_fail(25, "expected one crypt traversal shaft")
		return

	print("XZOGOT_EXPANSION_GROUND_GREEN segmented=4 depth=", ground_size.z)
	print("XZOGOT_CRYPT_SHAFT_GEOMETRY_GREEN width=2.8")
	print("XZOGOT_SECOND_FLOOR_PROBE_GREEN")
	print("XZOGOT_EXPANSION_ZONES_PROBE_GREEN ", zones.size())
	print("XZOGOT_EXPANSION_RAMPS_PROBE_GREEN ", ramps.size())
	print("XZOGOT_EXPANSION_BUY_GATE_PROBE_GREEN")
	print("XZOGOT_SELECTIVE_SPAWN_PROBE_GREEN")
	print("XZOGOT_BELL_TOWER_PROBE_GREEN")
	print("XZOGOT_RELIQUARY_GENERATOR_PROBE_GREEN")
	print("XZOGOT_CHURCH_EXPANSION_PROBE_GREEN")
	scene.queue_free()
	await process_frame
	quit(0)
