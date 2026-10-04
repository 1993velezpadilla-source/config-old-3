extends Node3D

const WORLD_SCALE: float = 0.78

var _nodes: Dictionary = {}
var _edges: Dictionary = {}

func _ready() -> void:
	add_to_group("zombie_path_network")
	_build_graph()
	print("XZOGOT_ZOMBIE_PATH_NETWORK_READY ", _nodes.size())

func _p(v: Vector3) -> Vector3:
	return v * WORLD_SCALE

func _add_node(id: int, label: String, pos: Vector3) -> void:
	_nodes[id] = {"label": label, "pos": _p(pos)}
	_edges[id] = []

func _link(a: int, b: int, requires_gate: String = "") -> void:
	_edges[a].append({"to": b, "gate": requires_gate})
	_edges[b].append({"to": a, "gate": requires_gate})

func _build_graph() -> void:
	# Ground floor / church core.
	_add_node(0, "NaveCenter", Vector3(0.0, 0.50, -3.0))
	_add_node(1, "NaveFront", Vector3(0.0, 0.50, 10.5))
	_add_node(2, "NaveRear", Vector3(0.0, 0.50, -18.5))
	_add_node(3, "FrontCourtyard", Vector3(0.0, 0.30, 25.0))
	_add_node(4, "WestGate", Vector3(-13.8, 0.30, 18.0))
	_add_node(5, "WestFront", Vector3(-17.0, 0.30, 13.0))
	_add_node(6, "WestMid", Vector3(-17.0, 0.30, -4.0))
	_add_node(7, "WestRear", Vector3(-17.0, 0.30, -28.0))
	_add_node(8, "RearRuins", Vector3(0.0, 0.30, -34.0))
	_add_node(9, "EastRear", Vector3(17.0, 0.30, -28.0))
	_add_node(10, "EastMid", Vector3(17.0, 0.30, -4.0))
	_add_node(11, "EastFront", Vector3(17.0, 0.30, 13.0))
	_add_node(12, "EastGate", Vector3(13.8, 0.30, 18.0))
	_add_node(13, "Graveyard", Vector3(23.0, 0.30, -18.0))
	_add_node(14, "WestTraining", Vector3(-25.0, 0.30, -19.0))
	_add_node(15, "BellYard", Vector3(-25.0, 0.30, 10.0))
	_add_node(16, "Sacristy", Vector3(15.0, 0.50, -15.0))
	_add_node(17, "CryptAccess", Vector3(15.0, 0.50, -3.0))
	_add_node(18, "CryptBottom", Vector3(16.0, -2.80, -12.5))

	# Existing balcony + new full second-floor loop.
	_add_node(19, "BalconyRearWest", Vector3(-8.0, 5.25, 9.0))
	_add_node(20, "SecondWest", Vector3(-8.35, 5.25, -6.0))
	_add_node(21, "SecondChoir", Vector3(0.0, 5.25, -18.15))
	_add_node(22, "SecondEast", Vector3(8.35, 5.25, -6.0))
	_add_node(23, "BalconyRearEast", Vector3(8.35, 5.25, 9.0))

	# Bell tower vertical route.
	_add_node(24, "BellLower", Vector3(-25.0, 0.35, 9.0))
	_add_node(25, "BellMid", Vector3(-25.0, 4.25, 12.0))
	_add_node(26, "BellTop", Vector3(-25.0, 8.25, 6.0))
	_add_node(27, "SecondMidWest", Vector3(-8.35, 5.25, -0.10))
	_add_node(28, "SecondMidEast", Vector3(8.35, 5.25, -0.10))
	_add_node(29, "ReliquaryEntry", Vector3(16.0, -2.80, -22.6))
	_add_node(30, "ReliquaryCenter", Vector3(8.0, -2.80, -26.0))

	_link(0, 1)
	_link(0, 2)
	_link(1, 3, "RearDoor")
	_link(3, 4, "WestOuterGate")
	_link(4, 5, "WestOuterGate")
	_link(5, 6)
	_link(6, 7)
	_link(7, 14)
	_link(14, 15)
	_link(15, 24, "BellTowerGate")
	_link(7, 8, "RearRuinsGate")
	_link(8, 9, "RearRuinsGate")
	_link(9, 10)
	_link(10, 11)
	_link(11, 12, "EastOuterGate")
	_link(12, 3, "EastOuterGate")
	_link(9, 13)
	_link(13, 10)

	# Side rooms connect to nave through the same openings used by gameplay geometry.
	_link(0, 17)
	_link(17, 16)
	_link(17, 18, "CryptGate")
	_link(18, 29)
	_link(29, 30)

	# Upper church route. BalconyGate is the first-floor progression choke.
	_link(1, 19, "BalconyGate")
	# Rear balcony feeds the east gallery; west side is intentionally cut open
	# over the stairwell for head clearance.
	_link(19, 23)
	_link(23, 22)
	_link(22, 21)
	_link(21, 20)
	# Mid bridge closes the second-floor loop without crossing the stair opening.
	_link(20, 27)
	_link(27, 28)
	_link(28, 22)

	# Bell tower switchback.
	_link(24, 25)
	_link(25, 26)

func _gate_open(gate_name: String) -> bool:
	if gate_name.is_empty():
		return true
	var scene_root: Node = get_parent()
	if scene_root == null:
		return false
	var gate: Node = scene_root.get_node_or_null(gate_name)
	if gate == null:
		return false
	if gate.has_method("was_used"):
		return bool(gate.call("was_used"))
	return false

func _nearest_node_id(world_pos: Vector3) -> int:
	var best_id: int = -1
	var best_dist: float = INF
	for id_var: Variant in _nodes.keys():
		var id: int = int(id_var)
		var pos: Vector3 = _nodes[id]["pos"] as Vector3
		var d: float = world_pos.distance_squared_to(pos)
		if d < best_dist:
			best_dist = d
			best_id = id
	return best_id

func request_path(from_world: Vector3, to_world: Vector3) -> Array[Vector3]:
	var start_id: int = _nearest_node_id(from_world)
	var goal_id: int = _nearest_node_id(to_world)
	if start_id < 0 or goal_id < 0:
		return [to_world]
	if start_id == goal_id:
		return [to_world]

	var dist: Dictionary = {}
	var prev: Dictionary = {}
	var open: Array[int] = []
	for id_var: Variant in _nodes.keys():
		var id: int = int(id_var)
		dist[id] = INF
	dist[start_id] = 0.0
	open.append(start_id)

	while not open.is_empty():
		var best_index: int = 0
		var current: int = open[0]
		for i in range(1, open.size()):
			var candidate: int = open[i]
			if float(dist[candidate]) < float(dist[current]):
				current = candidate
				best_index = i
		open.remove_at(best_index)
		if current == goal_id:
			break

		for edge_var: Variant in _edges[current]:
			var edge: Dictionary = edge_var as Dictionary
			var gate: String = str(edge.get("gate", ""))
			if not _gate_open(gate):
				continue
			var nxt: int = int(edge["to"])
			var a: Vector3 = _nodes[current]["pos"] as Vector3
			var b: Vector3 = _nodes[nxt]["pos"] as Vector3
			var nd: float = float(dist[current]) + a.distance_to(b)
			if nd < float(dist[nxt]):
				dist[nxt] = nd
				prev[nxt] = current
				if not open.has(nxt):
					open.append(nxt)

	if not prev.has(goal_id):
		# If topology is temporarily sealed by a paid door, chase the nearest
		# reachable graph point rather than jittering against a wall.
		var fallback: int = start_id
		var best_goal_dist: float = (_nodes[start_id]["pos"] as Vector3).distance_squared_to(to_world)
		for id_var: Variant in dist.keys():
			var id: int = int(id_var)
			if is_inf(float(dist[id])):
				continue
			var d: float = (_nodes[id]["pos"] as Vector3).distance_squared_to(to_world)
			if d < best_goal_dist:
				best_goal_dist = d
				fallback = id
		goal_id = fallback

	var ids: Array[int] = [goal_id]
	var cursor: int = goal_id
	while cursor != start_id and prev.has(cursor):
		cursor = int(prev[cursor])
		ids.push_front(cursor)

	var result: Array[Vector3] = []
	for i in range(1, ids.size()):
		result.append(_nodes[ids[i]]["pos"] as Vector3)
	result.append(to_world)
	return result

func recovery_point(world_pos: Vector3, target_world: Vector3) -> Vector3:
	var path: Array[Vector3] = request_path(world_pos, target_world)
	if path.is_empty():
		return target_world
	for p: Vector3 in path:
		if world_pos.distance_to(p) > 0.45:
			return p
	return target_world

func get_node_count() -> int:
	return _nodes.size()
