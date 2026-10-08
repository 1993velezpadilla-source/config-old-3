extends Node3D
class_name SourceNavigationRuntime

signal navigation_ready(polygons: int, vertices: int)
signal navigation_failed(reason: String)

@export var source_collision_group: StringName = &"source_world_collision"
@export var source_runtime_id: String = "source"

var _region: NavigationRegion3D
var _navigation_mesh: NavigationMesh
var _navigation_ready_state := false
var _bake_started := false

func _ready() -> void:
	add_to_group("zombie_path_network")
	add_to_group(source_runtime_id + "_navigation_runtime")
	set_meta("navigation_ready", false)
	set_meta("source_geometry", "STATIC_COLLIDERS")
	set_meta("source_collision_group", str(source_collision_group))
	set_meta("spawn_authority", "EXTERNAL_SOURCE_ACTORS")

func begin_bake() -> void:
	if _bake_started:
		return
	_bake_started = true

	var source_nodes := get_tree().get_nodes_in_group(source_collision_group)
	if source_nodes.is_empty():
		_fail("NO_SOURCE_COLLIDERS")
		return

	_navigation_mesh = NavigationMesh.new()
	_navigation_mesh.agent_height = 1.75
	_navigation_mesh.agent_radius = 0.36
	_navigation_mesh.agent_max_climb = 0.50
	_navigation_mesh.agent_max_slope = 52.0
	_navigation_mesh.cell_size = 0.40
	_navigation_mesh.cell_height = 0.25
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
	_region.name = source_runtime_id.capitalize() + "SourceNavigationRegion"
	_region.navigation_mesh = _navigation_mesh
	add_child(_region)

	if not _region.bake_finished.is_connected(_on_bake_finished):
		_region.bake_finished.connect(_on_bake_finished, CONNECT_ONE_SHOT)

	print(
		"XZOGOT_SOURCE_NAV_BAKE_START runtime=", source_runtime_id,
		" colliders=", source_nodes.size(),
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

	for _attempt in range(120):
		await get_tree().physics_frame
		var map := get_world_3d().get_navigation_map()
		if map.is_valid() and NavigationServer3D.map_get_iteration_id(map) > 0:
			break

	var nav_map := get_world_3d().get_navigation_map()
	if not nav_map.is_valid() or NavigationServer3D.map_get_iteration_id(nav_map) <= 0:
		_fail("NAVIGATION_MAP_NEVER_SYNCHRONIZED")
		return

	_navigation_ready_state = true
	set_meta("navigation_ready", true)
	set_meta("navigation_polygon_count", polygons)
	set_meta("navigation_vertex_count", vertices.size())
	set_meta("navigation_iteration_id", NavigationServer3D.map_get_iteration_id(nav_map))
	print(
		"XZOGOT_SOURCE_NAV_GREEN runtime=", source_runtime_id,
		" polygons=", polygons,
		" vertices=", vertices.size(),
		" iteration=", NavigationServer3D.map_get_iteration_id(nav_map)
	)
	navigation_ready.emit(polygons, vertices.size())

func _fail(reason: String) -> void:
	_navigation_ready_state = false
	set_meta("navigation_ready", false)
	set_meta("navigation_failure", reason)
	push_error("XZOGOT_SOURCE_NAV_FAILURE runtime=" + source_runtime_id + " reason=" + reason)
	navigation_failed.emit(reason)

func is_navigation_ready() -> bool:
	return _navigation_ready_state

func get_polygon_count() -> int:
	return _navigation_mesh.get_polygon_count() if _navigation_mesh != null else 0

func request_path(from_world: Vector3, to_world: Vector3) -> Array[Vector3]:
	var result: Array[Vector3] = []
	if not _navigation_ready_state:
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
