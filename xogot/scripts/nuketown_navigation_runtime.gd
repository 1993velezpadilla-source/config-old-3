extends Node3D
class_name NuketownNavigationRuntime

signal navigation_ready(polygons: int, spawn_anchors: int)
signal navigation_failed(reason: String)

@export var source_collision_group: StringName = &"nuketown_world_collision"
@export var desired_spawn_count: int = 10

var _region: NavigationRegion3D
var _navigation_mesh: NavigationMesh
var _ready: bool = false
var _spawn_anchor_count: int = 0
var _bake_started: bool = false

func _ready() -> void:
	add_to_group("zombie_path_network")
	add_to_group("nuketown_navigation_runtime")
	set_meta("navigation_ready", false)
	set_meta("source_geometry", "STATIC_COLLIDERS")
	set_meta("source_collision_group", str(source_collision_group))

func begin_bake() -> void:
	if _bake_started:
		return
	_bake_started = true

	var source_nodes := get_tree().get_nodes_in_group(source_collision_group)
	if source_nodes.is_empty():
		_fail("NO_SOURCE_COLLIDERS")
		return

	_navigation_mesh = NavigationMesh.new()
	_navigation_mesh.agent_height = 1.78
	_navigation_mesh.agent_radius = 0.36
	_navigation_mesh.agent_max_climb = 0.46
	_navigation_mesh.agent_max_slope = 52.0
	_navigation_mesh.cell_size = 0.40
	_navigation_mesh.cell_height = 0.20
	_navigation_mesh.region_min_size = 2.0
	_navigation_mesh.region_merge_size = 20.0
	_navigation_mesh.sample_partition_type = NavigationMesh.SAMPLE_PARTITION_MONOTONE
	_navigation_mesh.geometry_parsed_geometry_type = NavigationMesh.PARSED_GEOMETRY_STATIC_COLLIDERS
	_navigation_mesh.geometry_source_geometry_mode = NavigationMesh.SOURCE_GEOMETRY_GROUPS_EXPLICIT
	_navigation_mesh.geometry_source_group_name = source_collision_group
	_navigation_mesh.geometry_collision_mask = 1
	_navigation_mesh.filter_low_hanging_obstacles = true
	_navigation_mesh.filter_ledge_spans = true
	_navigation_mesh.filter_walkable_low_height_spans = true

	_region = NavigationRegion3D.new()
	_region.name = "SourceNavigationRegion"
	_region.navigation_mesh = _navigation_mesh
	add_child(_region)

	if not _region.bake_finished.is_connected(_on_bake_finished):
		_region.bake_finished.connect(_on_bake_finished, CONNECT_ONE_SHOT)

	print(
		"XZOGOT_NUKETOWN_NAV_BAKE_START colliders=",
		source_nodes.size(),
		" cell=", _navigation_mesh.cell_size,
		" agent_radius=", _navigation_mesh.agent_radius
	)
	_region.bake_navigation_mesh(true)

func _on_bake_finished() -> void:
	if _navigation_mesh == null:
		_fail("NAVIGATION_MESH_MISSING_AFTER_BAKE")
		return
	var polygons := _navigation_mesh.get_polygon_count()
	var vertices := _navigation_mesh.get_vertices()
	if polygons <= 0 or vertices.is_empty():
		_fail("NAVIGATION_BAKE_EMPTY")
		return

	# NavigationServer changes synchronize on a physics frame. Do not advertise
	# readiness until the map has actually consumed the baked region.
	for _attempt in range(120):
		await get_tree().physics_frame
		var map := get_world_3d().get_navigation_map()
		if map.is_valid() and NavigationServer3D.map_get_iteration_id(map) > 0:
			break

	var nav_map := get_world_3d().get_navigation_map()
	if not nav_map.is_valid() or NavigationServer3D.map_get_iteration_id(nav_map) <= 0:
		_fail("NAVIGATION_MAP_NEVER_SYNCHRONIZED")
		return

	_spawn_anchor_count = _build_perimeter_spawn_anchors(vertices)
	if _spawn_anchor_count < 4:
		_fail("INSUFFICIENT_NAV_SPAWN_ANCHORS_" + str(_spawn_anchor_count))
		return

	_ready = true
	set_meta("navigation_ready", true)
	set_meta("navigation_polygon_count", polygons)
	set_meta("navigation_vertex_count", vertices.size())
	set_meta("zombie_spawn_anchor_count", _spawn_anchor_count)
	print(
		"XZOGOT_NUKETOWN_NAV_GREEN polygons=", polygons,
		" vertices=", vertices.size(),
		" spawns=", _spawn_anchor_count,
		" iteration=", NavigationServer3D.map_get_iteration_id(nav_map)
	)
	navigation_ready.emit(polygons, _spawn_anchor_count)

func _fail(reason: String) -> void:
	_ready = false
	set_meta("navigation_ready", false)
	set_meta("navigation_failure", reason)
	push_error("XZOGOT_NUKETOWN_NAV_FAILURE " + reason)
	navigation_failed.emit(reason)

func _candidate_vertices(vertices: PackedVector3Array) -> Array[Vector3]:
	var result: Array[Vector3] = []
	var player := get_parent().get_node_or_null("Player") as Node3D
	var reference_y := player.global_position.y if player != null else 0.0

	# Spawn director entries belong on the main playable band. Roof navigation
	# can still exist for routing, but it must never become a zombie pop-in lane.
	for raw: Vector3 in vertices:
		var world := _region.to_global(raw)
		if absf(world.y - reference_y) <= 2.25:
			result.append(world)
	if result.size() >= 8:
		return result

	result.clear()
	for raw: Vector3 in vertices:
		result.append(_region.to_global(raw))
	return result

func _build_perimeter_spawn_anchors(vertices: PackedVector3Array) -> int:
	var candidates := _candidate_vertices(vertices)
	if candidates.is_empty():
		return 0

	var player := get_parent().get_node_or_null("Player") as Node3D
	var center := Vector3.ZERO
	for p: Vector3 in candidates:
		center += p
	center /= float(candidates.size())

	var directions: Array[Vector2] = [
		Vector2(1, 0),
		Vector2(-1, 0),
		Vector2(0, 1),
		Vector2(0, -1),
		Vector2(1, 1).normalized(),
		Vector2(1, -1).normalized(),
		Vector2(-1, 1).normalized(),
		Vector2(-1, -1).normalized(),
		Vector2(0.45, 1).normalized(),
		Vector2(-0.45, -1).normalized(),
	]

	var chosen: Array[Vector3] = []
	for dir: Vector2 in directions:
		if chosen.size() >= maxi(4, desired_spawn_count):
			break
		var best := Vector3.INF
		var best_score := -INF
		for p: Vector3 in candidates:
			if player != null and p.distance_to(player.global_position) < 10.0:
				continue
			var flat := Vector2(p.x - center.x, p.z - center.z)
			var score := flat.dot(dir) + flat.length() * 0.08
			var duplicate := false
			for existing: Vector3 in chosen:
				if existing.distance_to(p) < 5.0:
					duplicate = true
					break
			if duplicate:
				continue
			if score > best_score:
				best_score = score
				best = p
		if best != Vector3.INF:
			chosen.append(best)

	for i in range(chosen.size()):
		var anchor := Marker3D.new()
		anchor.name = "NuketownZombieSpawn_%02d" % i
		anchor.global_position = chosen[i] + Vector3.UP * 0.08
		anchor.add_to_group("zombie_spawn_anchor")
		anchor.add_to_group("nuketown_zombie_spawn_anchor")
		anchor.set_meta("spawn_id", "nuketown_nav_%02d" % i)
		anchor.set_meta("entry_kind", "offscreen")
		anchor.set_meta("zone", "nuketown_perimeter")
		anchor.set_meta("weight", 1.0 if i < 4 else 0.82)
		anchor.set_meta("min_round", 1 if i < 6 else 3)
		anchor.set_meta("source_authority", "BAKED_SOURCE_COLLISION_NAVMESH")
		add_child(anchor)

	return chosen.size()

func is_navigation_ready() -> bool:
	return _ready

func get_polygon_count() -> int:
	return _navigation_mesh.get_polygon_count() if _navigation_mesh != null else 0

func get_spawn_anchor_count() -> int:
	return _spawn_anchor_count

func request_path(from_world: Vector3, to_world: Vector3) -> Array[Vector3]:
	var result: Array[Vector3] = []
	if not _ready:
		result.append(to_world)
		return result
	var nav_map := get_world_3d().get_navigation_map()
	var start := NavigationServer3D.map_get_closest_point(nav_map, from_world)
	var goal := NavigationServer3D.map_get_closest_point(nav_map, to_world)
	var packed := NavigationServer3D.map_get_path(nav_map, start, goal, true, 1)
	for p: Vector3 in packed:
		result.append(p)
	if result.is_empty():
		result.append(goal)
	return result

func recovery_point(world_pos: Vector3, target_world: Vector3) -> Vector3:
	var path := request_path(world_pos, target_world)
	if path.is_empty():
		return target_world
	for p: Vector3 in path:
		if world_pos.distance_to(p) > 0.45:
			return p
	return target_world
