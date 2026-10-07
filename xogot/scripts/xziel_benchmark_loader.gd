class_name XzielBenchmarkLoader
extends Node3D

## Runtime bridge for the already-resolved XZIEL static-world payload.
##
## The old UE map work already produced source-authoritative geometry, transforms,
## material bindings, ASTC textures and lights. This loader consumes those files
## directly in Godot instead of reparsing cooked Unreal packages or inventing
## placements/material offsets.

@export_dir var source_root: String = "res://assets/benchmarks/nuketown_xziel"
@export var load_on_ready: bool = true
@export var build_materials: bool = true
@export var build_lights: bool = true
@export var build_skeletal_actors: bool = true
@export var cast_geometry_shadows: bool = true
@export var build_world_collision: bool = false
@export var max_instances: int = 0
@export var vfs_map_root: String = "vfs/xziel/maps/xziel_nuketown_zombies"
@export_file("*.json") var source_environment_truth_file: String = "res://data/nuketown_source_gameplay.json"
@export var source_runtime_id: String = "nuketown"
@export var visual_scene_file: String = "visual-scene.json"
@export var material_bindings_file: String = "material-binding-manifest.json"
@export var texture_report_file: String = "xzml-report.json"
@export var effective_material_report_file: String = "xzmi-report.json"
@export var complete_texture_report_file: String = "complete-xztx-report.json"
@export var light_report_file: String = "xzen-report.json"
@export var skeletal_bindings_file: String = "skeletal-runtime-bindings.json"
@export var particle_mesh_bindings_file: String = "particle-mesh-bindings.json"
const XZMS_HEADER_BYTES := 56
const XZMS_SUBMESH_BYTES := 16
const XZTX_HEADER_BYTES := 80
const XZTX_MIP_RECORD_BYTES := 24

const XZMS_ATTR_POSITION := 1 << 0
const XZMS_ATTR_NORMAL := 1 << 1
const XZMS_ATTR_UV0 := 1 << 2
const XZMS_ATTR_TANGENT := 1 << 6

var _mesh_cache: Dictionary = {}
var _particle_mesh_cache: Dictionary = {}
var _particle_mesh_bindings: Dictionary = {}
var _material_cache: Dictionary = {}
var _texture_cache: Dictionary = {}
var _material_records: Dictionary = {}
var _texture_runtime_files: Dictionary = {}
var _source_srgb_texture_paths: Array[String] = []
var _source_effective_material_paths: Dictionary = {}
var _source_material_alias_diffuse: Dictionary = {}
var _source_material_alias_conflicts: Dictionary = {}
var _source_material_resolved_alias_diffuse: Dictionary = {}
var _source_duplicate_material_parameters: Dictionary = {}
var _source_duplicate_material_conflicts: Dictionary = {}
var _source_material_alias_hits: int = 0
var _source_duplicate_material_hits: int = 0
var _source_material_exact_token_hits: int = 0
var _source_material_sibling_semantic_hits: int = 0
var _source_effective_sibling_semantic_hits: int = 0
var _source_material_textured_count: int = 0
var _source_material_flat_fallback_count: int = 0
var _source_effective_material_textured_count: int = 0
var _source_effective_material_flat_fallback_count: int = 0
var _source_effective_source_color_count: int = 0
var _source_effective_default_surface_count: int = 0
var _source_effective_engine_default_count: int = 0
var _source_effective_unresolved_fallback_count: int = 0
var _source_effective_flat_fallback_rows: Array[Dictionary] = []
var _source_texture_resource_hits: int = 0
var _source_texture_image_hits: int = 0
var _source_texture_load_failures: int = 0
var _mesh_material_paths: Dictionary = {}
var _mesh_material_slots: Dictionary = {}
var _instance_overrides: Dictionary = {}
var _runtime_root: Node3D
var _native_glb_mesh_count: int = 0
var _native_glb_chunk_count: int = 0
var _xzms_fallback_mesh_count: int = 0
var _source_skeletal_actor_count: int = 0
var _source_skeletal_actor_missing: int = 0
var _world_collision_count: int = 0

func _ready() -> void:
	if load_on_ready:
		call_deferred("_load_benchmark_world")

func _load_benchmark_world() -> void:
	if _runtime_root != null:
		_runtime_root.queue_free()
		_runtime_root = null

	var scene := _read_json(_source_path(visual_scene_file))
	if scene.is_empty():
		push_error("XZIEL benchmark: visual scene missing")
		return
	if str(scene.get("format", "")) != "xziel_visual_scene_v1":
		push_error("XZIEL benchmark: unsupported visual scene format")
		return

	_prepare_material_authority()
	_native_glb_mesh_count = 0
	_native_glb_chunk_count = 0
	_xzms_fallback_mesh_count = 0
	_world_collision_count = 0

	_runtime_root = Node3D.new()
	_runtime_root.name = "XZIELSceneRoot"
	# XZIEL runtime coordinates are meters, X,-Y,Z (Z-up).
	# Keep all child source matrices untouched and rotate the parent basis once:
	# XZIEL +X -> Godot -Z, XZIEL +Y -> Godot -X, XZIEL +Z -> Godot +Y.
	_runtime_root.basis = Basis(
		Vector3(0.0, 0.0, -1.0),
		Vector3(-1.0, 0.0, 0.0),
		Vector3(0.0, 1.0, 0.0)
	)
	add_child(_runtime_root)

	var meshes: Array = scene.get("meshes", [])
	var instances: Array = scene.get("instances", [])
	var instance_limit := instances.size()
	if max_instances > 0:
		instance_limit = mini(instance_limit, max_instances)

	var created := 0
	var missing_meshes := 0
	for instance_index in range(instance_limit):
		var instance: Dictionary = instances[instance_index]
		var mesh_index := int(instance.get("meshIndex", -1))
		if mesh_index < 0 or mesh_index >= meshes.size():
			continue
		var mesh_row: Dictionary = meshes[mesh_index]
		var runtime_file := str(mesh_row.get("runtimeFile", ""))
		var mesh_chunks: Array[ArrayMesh] = _load_benchmark_mesh_chunks(runtime_file, mesh_index)
		if mesh_chunks.is_empty():
			missing_meshes += 1
			continue

		var instance_id := str(instance.get("instanceId", "ue_instance_%06d" % instance_index))
		var instance_root := Node3D.new()
		instance_root.name = instance_id
		instance_root.transform = _transform_from_row_major(instance.get("matrixRowMajor", []))
		instance_root.set_meta("source_component_path", str(instance.get("sourceComponentPath", "")))
		instance_root.set_meta("source_scene_mesh_index", mesh_index)
		instance_root.set_meta("source_instance_index", instance.get("sourceInstanceIndex", null))
		_runtime_root.add_child(instance_root)

		var surface_offset := 0
		for chunk_index in range(mesh_chunks.size()):
			var node := MeshInstance3D.new()
			node.name = "MeshChunk_%03d" % chunk_index
			node.mesh = mesh_chunks[chunk_index]
			node.cast_shadow = (
				GeometryInstance3D.SHADOW_CASTING_SETTING_ON
				if cast_geometry_shadows
				else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			)
			node.set_meta("source_surface_offset", surface_offset)
			_apply_instance_materials(node, instance_id, mesh_index, surface_offset)
			instance_root.add_child(node)
			if build_world_collision:
				node.create_trimesh_collision()
				for child: Node in node.get_children():
					if child is StaticBody3D:
						_world_collision_count += 1
			surface_offset += node.mesh.get_surface_count()
		created += 1

	if build_skeletal_actors:
		_build_source_skeletal_actors()

	if build_lights:
		_build_source_lights()

	var summary: Dictionary = scene.get("summary", {})
	set_meta(
		"xziel_benchmark_ready",
		missing_meshes == 0
		and created == instance_limit
		and _source_skeletal_actor_missing == 0
	)
	set_meta("xziel_benchmark_mesh_count", meshes.size())
	set_meta("xziel_benchmark_instance_count", created)
	set_meta("xziel_benchmark_source_instance_count", instances.size())
	set_meta("xziel_benchmark_missing_meshes", missing_meshes)
	set_meta("xziel_benchmark_source_ready", bool(summary.get("ready", false)))
	set_meta("xziel_benchmark_native_glb_mesh_count", _native_glb_mesh_count)
	set_meta("xziel_benchmark_native_glb_chunk_count", _native_glb_chunk_count)
	set_meta("xziel_benchmark_xzms_fallback_mesh_count", _xzms_fallback_mesh_count)
	set_meta("xziel_benchmark_source_skeletal_actor_count", _source_skeletal_actor_count)
	set_meta("xziel_benchmark_source_skeletal_actor_missing", _source_skeletal_actor_missing)
	set_meta("xziel_benchmark_world_collision_count", _world_collision_count)
	set_meta("xziel_benchmark_material_alias_count", _source_material_alias_diffuse.size())
	set_meta("xziel_benchmark_material_alias_conflict_count", _source_material_alias_conflicts.size())
	set_meta("xziel_benchmark_material_alias_resolved_count", _source_material_resolved_alias_diffuse.size())
	set_meta("xziel_benchmark_material_alias_hits", _source_material_alias_hits)
	set_meta("xziel_benchmark_material_duplicate_source_hits", _source_duplicate_material_hits)
	set_meta("xziel_benchmark_material_duplicate_source_conflicts", _source_duplicate_material_conflicts.size())
	set_meta("xziel_benchmark_material_exact_token_hits", _source_material_exact_token_hits)
	set_meta("xziel_benchmark_material_sibling_semantic_hits", _source_material_sibling_semantic_hits)
	set_meta("xziel_benchmark_effective_sibling_semantic_hits", _source_effective_sibling_semantic_hits)
	set_meta("xziel_benchmark_material_textured_count", _source_material_textured_count)
	set_meta("xziel_benchmark_material_flat_fallback_count", _source_material_flat_fallback_count)
	set_meta("xziel_benchmark_effective_material_count", _source_effective_material_paths.size())
	set_meta("xziel_benchmark_effective_material_textured_count", _source_effective_material_textured_count)
	set_meta("xziel_benchmark_effective_material_flat_fallback_count", _source_effective_material_flat_fallback_count)
	set_meta("xziel_benchmark_effective_source_color_count", _source_effective_source_color_count)
	set_meta("xziel_benchmark_effective_default_surface_count", _source_effective_default_surface_count)
	set_meta("xziel_benchmark_effective_engine_default_count", _source_effective_engine_default_count)
	set_meta("xziel_benchmark_effective_unresolved_fallback_count", _source_effective_unresolved_fallback_count)
	set_meta("xziel_benchmark_texture_resource_hits", _source_texture_resource_hits)
	set_meta("xziel_benchmark_texture_image_hits", _source_texture_image_hits)
	set_meta("xziel_benchmark_texture_load_failures", _source_texture_load_failures)
	print(
		"XZOGOT_XZIEL_BENCHMARK_WORLD ",
		"meshes=", meshes.size(),
		" instances=", created,
		"/", instance_limit,
		" missing=", missing_meshes,
		" native_glb=", _native_glb_mesh_count,
		" native_chunks=", _native_glb_chunk_count,
		" xzms_fallback=", _xzms_fallback_mesh_count,
		" skeletal_actors=", _source_skeletal_actor_count,
		" skeletal_missing=", _source_skeletal_actor_missing,
		" collisions=", _world_collision_count,
		" materials=", _material_cache.size(),
		" textures=", _texture_cache.size(),
		" aliases=", _source_material_alias_diffuse.size(),
		" alias_resolved=", _source_material_resolved_alias_diffuse.size(),
		" alias_hits=", _source_material_alias_hits,
		" duplicate_source_hits=", _source_duplicate_material_hits,
		" duplicate_source_conflicts=", _source_duplicate_material_conflicts.size(),
		" exact_token_hits=", _source_material_exact_token_hits,
		" sibling_semantic_hits=", _source_material_sibling_semantic_hits,
		" effective_sibling_semantic_hits=", _source_effective_sibling_semantic_hits,
		" alias_conflicts=", _source_material_alias_conflicts.size(),
		" textured_materials=", _source_material_textured_count,
		" flat_fallbacks=", _source_material_flat_fallback_count,
		" effective_materials=", _source_effective_material_paths.size(),
		" effective_textured=", _source_effective_material_textured_count,
		" effective_flat_fallbacks=", _source_effective_material_flat_fallback_count,
		" effective_source_color=", _source_effective_source_color_count,
		" effective_default_surface=", _source_effective_default_surface_count,
		" effective_engine_default=", _source_effective_engine_default_count,
		" effective_unresolved_fallbacks=", _source_effective_unresolved_fallback_count,
		" texture_resource_hits=", _source_texture_resource_hits,
		" texture_image_hits=", _source_texture_image_hits,
		" texture_load_failures=", _source_texture_load_failures
	)
	for fallback_row: Dictionary in _source_effective_flat_fallback_rows:
		print("XZOGOT_EFFECTIVE_FLAT_FALLBACK ", JSON.stringify(fallback_row))

func _build_source_skeletal_actors() -> void:
	_source_skeletal_actor_count = 0
	_source_skeletal_actor_missing = 0
	var bindings := _read_json(_source_path(skeletal_bindings_file))
	if bindings.is_empty() or not bool(bindings.get("ready", false)):
		return

	var rows: Array = bindings.get("bindings", [])
	for index in range(rows.size()):
		var raw: Variant = rows[index]
		if not (raw is Dictionary):
			_source_skeletal_actor_missing += 1
			continue
		var row := raw as Dictionary
		var output := str(row.get("gltf", ""))
		if output.is_empty():
			_source_skeletal_actor_missing += 1
			continue
		var resource_path := _source_path(
			"source_library/skeletal_gltf".path_join(output)
		)
		if not ResourceLoader.exists(resource_path):
			_source_skeletal_actor_missing += 1
			push_error("XZIEL benchmark: exact skeletal GLTF missing " + resource_path)
			continue
		var packed := load(resource_path) as PackedScene
		if packed == null:
			_source_skeletal_actor_missing += 1
			push_error("XZIEL benchmark: exact skeletal GLTF failed to load " + resource_path)
			continue
		var visual := packed.instantiate() as Node3D
		if visual == null:
			_source_skeletal_actor_missing += 1
			continue

		var actor_root := Node3D.new()
		actor_root.name = "SourceSkeletalActor_%02d" % index
		actor_root.transform = _transform_from_row_major(row.get("matrixRowMajor", []))
		actor_root.set_meta("source_actor_name", str(row.get("actorName", "")))
		actor_root.set_meta("source_actor_object_path", str(row.get("actorObjectPath", "")))
		actor_root.set_meta("source_component_object_path", str(row.get("componentObjectPath", "")))
		actor_root.set_meta(
			"source_skeletal_mesh_package_path",
			str(row.get("sourceSkeletalMeshPackagePath", ""))
		)
		actor_root.set_meta("source_xzsk_file", str(row.get("sourceXzskFile", "")))
		actor_root.set_meta("source_skeleton_hash", str(row.get("skeletonHash", "")))
		actor_root.set_meta("source_animation_names", row.get("animations", []))
		actor_root.add_to_group(source_runtime_id + "_source_skeletal_actor")
		visual.name = "SourceSkeletalVisual"
		actor_root.add_child(visual)
		_runtime_root.add_child(actor_root)
		_source_skeletal_actor_count += 1

	var expected := int(bindings.get("bindingCount", rows.size()))
	if _source_skeletal_actor_count < expected:
		_source_skeletal_actor_missing += expected - _source_skeletal_actor_count
	print(
		"XZOGOT_SOURCE_EXACT_SKELETAL_RUNTIME map=", source_runtime_id, " ",
		"actors=", _source_skeletal_actor_count,
		" expected=", expected,
		" missing=", _source_skeletal_actor_missing
	)

func _source_path(relative: String) -> String:
	return source_root.path_join(relative)

func _canonical_source_object_path(raw: String) -> String:
	var value := raw.strip_edges().replace("\\", "/")
	var quote := value.find("'")
	if quote >= 0 and value.ends_with("'"):
		value = value.substr(quote + 1, value.length() - quote - 2)
	if value.begins_with("Content/"):
		value = "/Game/" + value.substr(8)
	elif value.begins_with("Game/"):
		value = "/" + value
	return value.to_lower()

func _prepare_particle_mesh_bindings() -> void:
	if not _particle_mesh_bindings.is_empty():
		return
	var report := _read_json(_source_path(particle_mesh_bindings_file))
	for raw: Variant in report.get("meshes", []):
		if not (raw is Dictionary):
			continue
		var row := raw as Dictionary
		var source_path := str(row.get("sourceObjectPath", ""))
		var runtime_file := str(row.get("runtimeFile", ""))
		if source_path.is_empty() or runtime_file.is_empty():
			continue
		_particle_mesh_bindings[_canonical_source_object_path(source_path)] = runtime_file

func resolve_particle_mesh_chunks(source_object_path: String) -> Array[ArrayMesh]:
	_prepare_particle_mesh_bindings()
	var key := _canonical_source_object_path(source_object_path)
	if _particle_mesh_cache.has(key):
		var cached: Array[ArrayMesh] = []
		for raw: Variant in _particle_mesh_cache[key]:
			if raw is ArrayMesh:
				cached.append(raw as ArrayMesh)
		return cached
	var runtime_file := str(_particle_mesh_bindings.get(key, ""))
	var result: Array[ArrayMesh] = []
	if runtime_file.is_empty():
		return result
	var native_name := runtime_file.get_basename() + ".glb"
	var native_path := _source_path(
		vfs_map_root.path_join("particle_meshes_glb").path_join(native_name)
	)
	if not ResourceLoader.exists(native_path):
		return result
	var packed := load(native_path) as PackedScene
	if packed == null:
		return result
	var instance := packed.instantiate()
	if instance == null:
		return result
	var mesh_nodes: Array[MeshInstance3D] = []
	_collect_mesh_instances(instance, mesh_nodes)
	for mesh_node: MeshInstance3D in mesh_nodes:
		if mesh_node.mesh is ArrayMesh:
			var duplicate := (mesh_node.mesh as ArrayMesh).duplicate() as ArrayMesh
			if duplicate != null:
				result.append(duplicate)
	instance.free()
	if not result.is_empty():
		_particle_mesh_cache[key] = result
	return result

func _read_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	return parsed as Dictionary if parsed is Dictionary else {}

func _prepare_material_authority() -> void:
	_material_records.clear()
	_texture_runtime_files.clear()
	_source_srgb_texture_paths.clear()
	_source_effective_material_paths.clear()
	_source_material_alias_diffuse.clear()
	_source_material_alias_conflicts.clear()
	_source_material_resolved_alias_diffuse.clear()
	_source_duplicate_material_parameters.clear()
	_source_duplicate_material_conflicts.clear()
	_source_material_alias_hits = 0
	_source_duplicate_material_hits = 0
	_source_material_exact_token_hits = 0
	_source_material_sibling_semantic_hits = 0
	_source_effective_sibling_semantic_hits = 0
	_source_material_textured_count = 0
	_source_material_flat_fallback_count = 0
	_source_effective_material_textured_count = 0
	_source_effective_material_flat_fallback_count = 0
	_source_effective_source_color_count = 0
	_source_effective_default_surface_count = 0
	_source_effective_engine_default_count = 0
	_source_effective_unresolved_fallback_count = 0
	_source_effective_flat_fallback_rows.clear()
	_source_texture_resource_hits = 0
	_source_texture_image_hits = 0
	_source_texture_load_failures = 0
	_mesh_material_paths.clear()
	_mesh_material_slots.clear()
	_instance_overrides.clear()

	if not build_materials:
		return

	var bindings := _read_json(_source_path(material_bindings_file))
	var texture_report := _read_json(_source_path(texture_report_file))
	var effective_material_report := _read_json(_source_path(effective_material_report_file))
	var complete_texture_report := _read_json(_source_path(complete_texture_report_file))

	for raw: Variant in bindings.get("materials", []):
		if raw is Dictionary:
			var record := raw as Dictionary
			var material_path := str(record.get("materialPath", ""))
			if material_path.is_empty():
				continue
			_material_records[material_path] = record
			# Particle graphs and static-scene bindings can preserve different
			# source spellings (Content/... versus /Game/...). They identify the
			# same cooked UE object. Keep the exact key for provenance and add a
			# canonical lookup key so source-authored Cascade materials resolve
			# without filename/name guessing.
			_material_records[_canonical_source_object_path(material_path)] = record

	for material_path_raw: Variant in effective_material_report.get("materialPaths", []):
		var effective_path := str(material_path_raw)
		if not effective_path.is_empty():
			_source_effective_material_paths[effective_path] = true
	set_meta("xziel_benchmark_effective_material_authority_count", _source_effective_material_paths.size())

	var texture_reports: Array[Dictionary] = [texture_report]
	if not complete_texture_report.is_empty():
		texture_reports.append(complete_texture_report)
	for report: Dictionary in texture_reports:
		for raw: Variant in report.get("textureAssets", []):
			if raw is Dictionary:
				var texture_row := raw as Dictionary
				var source_path := str(texture_row.get("sourcePath", ""))
				if source_path.is_empty():
					continue
				_texture_runtime_files[source_path] = str(
					texture_row.get("runtimeFile", "")
				)
				if bool(texture_row.get("srgb", false)) and not _source_srgb_texture_paths.has(source_path):
					_source_srgb_texture_paths.append(source_path)
	set_meta("xziel_benchmark_complete_texture_catalog_count", _texture_runtime_files.size())

	_build_source_material_aliases()

	for raw: Variant in bindings.get("meshes", []):
		if not (raw is Dictionary):
			continue
		var mesh_row := raw as Dictionary
		var mesh_index := int(mesh_row.get("sceneMeshIndex", -1))
		var submesh_count := int(mesh_row.get("submeshCount", 0))
		var paths: Array[String] = []
		paths.resize(submesh_count)
		paths.fill("")
		var slots: Array[int] = []
		slots.resize(submesh_count)
		slots.fill(-1)
		for section_raw: Variant in mesh_row.get("sections", []):
			if section_raw is Dictionary:
				var section := section_raw as Dictionary
				var submesh := int(section.get("submeshIndex", -1))
				if submesh >= 0 and submesh < paths.size():
					paths[submesh] = str(section.get("baseMaterialPath", ""))
					slots[submesh] = int(section.get("slotIndex", -1))
		_mesh_material_paths[mesh_index] = paths
		_mesh_material_slots[mesh_index] = slots

	for raw: Variant in bindings.get("instanceOverrides", []):
		if not (raw is Dictionary):
			continue
		var row := raw as Dictionary
		var by_slot: Dictionary = {}
		for slot_raw: Variant in row.get("slotOverrides", []):
			if slot_raw is Dictionary:
				var slot := slot_raw as Dictionary
				by_slot[int(slot.get("slotIndex", -1))] = str(slot.get("materialPath", ""))
		_instance_overrides[str(row.get("instanceId", ""))] = by_slot

func _collect_mesh_instances(node: Node, out: Array[MeshInstance3D]) -> void:
	if node is MeshInstance3D:
		out.append(node as MeshInstance3D)
	for child: Node in node.get_children():
		_collect_mesh_instances(child, out)

func _cached_mesh_chunks(cache_key: String) -> Array[ArrayMesh]:
	var result: Array[ArrayMesh] = []
	if not _mesh_cache.has(cache_key):
		return result
	var cached: Variant = _mesh_cache[cache_key]
	if cached is Array:
		for raw: Variant in cached:
			if raw is ArrayMesh:
				result.append(raw as ArrayMesh)
	elif cached is ArrayMesh:
		result.append(cached as ArrayMesh)
	return result

func _load_benchmark_mesh_chunks(runtime_file: String, scene_mesh_index: int) -> Array[ArrayMesh]:
	var cache_key := runtime_file.get_basename()
	if _mesh_cache.has(cache_key):
		return _cached_mesh_chunks(cache_key)

	var native_name := runtime_file.get_basename() + ".glb"
	var native_path := _source_path(vfs_map_root.path_join("meshes_glb").path_join(native_name))
	if ResourceLoader.exists(native_path):
		var packed := load(native_path) as PackedScene
		if packed != null:
			var instance := packed.instantiate()
			if instance != null:
				var mesh_nodes: Array[MeshInstance3D] = []
				_collect_mesh_instances(instance, mesh_nodes)
				var chunks: Array[ArrayMesh] = []
				var base_materials: Array = _mesh_material_paths.get(scene_mesh_index, [])
				var surface_offset := 0
				for mesh_node: MeshInstance3D in mesh_nodes:
					if not (mesh_node.mesh is ArrayMesh):
						continue
					var mesh := (mesh_node.mesh as ArrayMesh).duplicate() as ArrayMesh
					if mesh == null:
						continue
					# Material authority is instance-effective, not mesh-base. Do not
					# materialize all 661 source slots here: 463 are superseded by
					# per-instance overrides in the final XZMI binding table.
					chunks.append(mesh)
					surface_offset += mesh.get_surface_count()

				instance.free()
				if not chunks.is_empty():
					if not base_materials.is_empty() and surface_offset != base_materials.size():
						push_error(
							"XZIEL benchmark native GLB surface mismatch "
							+ runtime_file
							+ " imported="
							+ str(surface_offset)
							+ " source="
							+ str(base_materials.size())
						)
						return []
					_mesh_cache[cache_key] = chunks
					_native_glb_mesh_count += 1
					_native_glb_chunk_count += chunks.size()
					return chunks

	# Truthful compatibility fallback for source artifacts staged before the
	# native GLB conversion. Shipping/mobile benchmark paths must use GLB.
	var fallback := _load_xzmesh(runtime_file, scene_mesh_index)
	var fallback_chunks: Array[ArrayMesh] = []
	if fallback != null:
		fallback_chunks.append(fallback)
		_mesh_cache[cache_key] = fallback_chunks
		_xzms_fallback_mesh_count += 1
	return fallback_chunks

func _load_xzmesh(runtime_file: String, scene_mesh_index: int) -> ArrayMesh:
	if _mesh_cache.has(runtime_file):
		return _mesh_cache[runtime_file] as ArrayMesh

	var path := _source_path(vfs_map_root.path_join("meshes").path_join(runtime_file))
	if not FileAccess.file_exists(path):
		push_error("XZIEL benchmark mesh missing: " + path)
		return null
	var bytes := FileAccess.get_file_as_bytes(path)
	if bytes.size() < XZMS_HEADER_BYTES or bytes.slice(0, 4).get_string_from_ascii() != "XZMS":
		push_error("XZIEL benchmark invalid XZMS: " + runtime_file)
		return null

	var version := int(bytes.decode_u32(4))
	var vertex_count := int(bytes.decode_u32(8))
	var index_count := int(bytes.decode_u32(12))
	var submesh_count := int(bytes.decode_u32(16))
	var vertex_stride := int(bytes.decode_u32(24))
	var submesh_stride := int(bytes.decode_u32(28))
	if version < 3 or version > 4 or vertex_count <= 0 or index_count <= 0 or submesh_count <= 0:
		push_error("XZIEL benchmark unsupported XZMS header: " + runtime_file)
		return null
	if (version == 3 and vertex_stride != 72) or (version == 4 and vertex_stride != 104):
		push_error("XZIEL benchmark bad XZMS vertex stride: " + runtime_file)
		return null
	if submesh_stride != XZMS_SUBMESH_BYTES:
		push_error("XZIEL benchmark bad XZMS submesh stride: " + runtime_file)
		return null

	var vertex_offset := XZMS_HEADER_BYTES
	var index_offset := vertex_offset + vertex_count * vertex_stride
	var submesh_offset := index_offset + index_count * 4
	if submesh_offset + submesh_count * submesh_stride != bytes.size():
		push_error("XZIEL benchmark XZMS size mismatch: " + runtime_file)
		return null

	var positions := PackedVector3Array()
	var normals := PackedVector3Array()
	var uv0 := PackedVector2Array()
	var tangents := PackedFloat32Array()
	positions.resize(vertex_count)
	normals.resize(vertex_count)
	uv0.resize(vertex_count)
	tangents.resize(vertex_count * 4)
	for vertex_index in range(vertex_count):
		var at := vertex_offset + vertex_index * vertex_stride
		positions[vertex_index] = Vector3(
			bytes.decode_float(at),
			bytes.decode_float(at + 4),
			bytes.decode_float(at + 8)
		)
		normals[vertex_index] = Vector3(
			bytes.decode_float(at + 12),
			bytes.decode_float(at + 16),
			bytes.decode_float(at + 20)
		)
		if version >= 3:
			for tangent_component in range(4):
				tangents[vertex_index * 4 + tangent_component] = bytes.decode_float(
					at + 24 + tangent_component * 4
				)
			uv0[vertex_index] = Vector2(
				bytes.decode_float(at + 40),
				bytes.decode_float(at + 44)
			)
		else:
			uv0[vertex_index] = Vector2(
				bytes.decode_float(at + 24),
				bytes.decode_float(at + 28)
			)

	var mesh := ArrayMesh.new()
	var base_materials: Array = _mesh_material_paths.get(scene_mesh_index, [])
	for submesh_index in range(submesh_count):
		var sat := submesh_offset + submesh_index * submesh_stride
		var first_index := int(bytes.decode_u32(sat))
		var sub_index_count := int(bytes.decode_u32(sat + 4))
		var attr := int(bytes.decode_u32(sat + 12))
		if sub_index_count <= 0 or first_index < 0 or first_index + sub_index_count > index_count:
			continue

		var global_to_local: Dictionary = {}
		var local_positions := PackedVector3Array()
		var local_normals := PackedVector3Array()
		var local_uv := PackedVector2Array()
		var local_tangents := PackedFloat32Array()
		var local_indices := PackedInt32Array()

		for source_index_offset in range(sub_index_count):
			var global_index := int(bytes.decode_u32(index_offset + (first_index + source_index_offset) * 4))
			if global_index < 0 or global_index >= vertex_count:
				continue
			var local_index: int
			if global_to_local.has(global_index):
				local_index = int(global_to_local[global_index])
			else:
				local_index = local_positions.size()
				global_to_local[global_index] = local_index
				local_positions.append(positions[global_index])
				if (attr & XZMS_ATTR_NORMAL) != 0:
					local_normals.append(normals[global_index])
				if (attr & XZMS_ATTR_UV0) != 0:
					local_uv.append(uv0[global_index])
				if (attr & XZMS_ATTR_TANGENT) != 0:
					for tangent_component in range(4):
						local_tangents.append(tangents[global_index * 4 + tangent_component])
			local_indices.append(local_index)

		if local_positions.is_empty() or local_indices.size() < 3:
			continue
		var arrays: Array = []
		arrays.resize(Mesh.ARRAY_MAX)
		arrays[Mesh.ARRAY_VERTEX] = local_positions
		if not local_normals.is_empty():
			arrays[Mesh.ARRAY_NORMAL] = local_normals
		if not local_uv.is_empty():
			arrays[Mesh.ARRAY_TEX_UV] = local_uv
		if not local_tangents.is_empty():
			arrays[Mesh.ARRAY_TANGENT] = local_tangents
		arrays[Mesh.ARRAY_INDEX] = local_indices
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)

		# Instance-effective material binding is applied after this shared mesh
		# is mounted, matching XZMI rather than eagerly materializing base slots.

	_mesh_cache[runtime_file] = mesh
	return mesh

func _optional_source_path(value: Variant) -> String:
	if value == null:
		return ""
	var path := str(value)
	if path == "<null>" or path == "Null" or path == "null":
		return ""
	return path

func resolve_source_material(material_path: String) -> Material:
	# Public bridge for non-static source systems (Cascade, decals, future VFX).
	# Keep the actual material construction authoritative in one place.
	return _material_for_path(material_path)

func _material_for_path(material_path: String) -> Material:
	if material_path.is_empty():
		return null
	var canonical_path := _canonical_source_object_path(material_path)
	if _material_cache.has(material_path):
		return _material_cache[material_path] as Material
	if _material_cache.has(canonical_path):
		return _material_cache[canonical_path] as Material
	var record: Dictionary = _material_records.get(material_path, {})
	if record.is_empty():
		record = _material_records.get(canonical_path, {})
	if record.is_empty():
		return null

	var sibling_semantics_raw: Variant = record.get("sourceSiblingSemanticBindings", {})
	if sibling_semantics_raw is Dictionary:
		var sibling_semantics := sibling_semantics_raw as Dictionary
		if not sibling_semantics.is_empty():
			_source_material_sibling_semantic_hits += sibling_semantics.size()
			if _source_effective_material_paths.has(material_path):
				_source_effective_sibling_semantic_hits += sibling_semantics.size()

	var material := StandardMaterial3D.new()
	material.resource_name = material_path.get_file()

	var canonical: Dictionary = record.get("canonicalTextures", {})
	var diffuse_source := _optional_source_path(canonical.get("diffuse", null))
	var normal_source := _optional_source_path(canonical.get("normal", null))
	var emissive_source := _optional_source_path(canonical.get("emissive", null))
	var source_blend_mode := str(record.get("blendMode", "BLEND_Opaque"))
	var source_shading_model := str(record.get("shadingModel", ""))
	var source_graph_raw: Variant = record.get("sourceGraphBindings", {})
	var source_graph: Dictionary = (
		source_graph_raw as Dictionary
		if source_graph_raw is Dictionary
		else {}
	)
	var graph_diffuse_source := _optional_source_path(
		source_graph.get("diffuse", null)
	)
	var graph_emissive_source := _optional_source_path(
		source_graph.get("emissive", null)
	)
	var graph_emissive_as_unshaded_color := (
		source_shading_model == "MSM_Unlit"
		and graph_diffuse_source.is_empty()
		and not graph_emissive_source.is_empty()
	)
	if graph_emissive_as_unshaded_color:
		# UE Unlit surfaces display EmissiveColor directly. Godot's closest
		# StandardMaterial3D equivalent is an unshaded albedo input; assigning
		# the same texture to both albedo and emission would double its energy,
		# especially under additive blending.
		diffuse_source = graph_emissive_source
		emissive_source = ""

	# Preserve explicit cooked parameter semantics before any uniqueness-based
	# fallback. UE4 material instances commonly expose AlbedoTexture and
	# NormalTexture directly even when the canonical PM_* binding is absent.
	# This is source-authored metadata, not a filename/material-name guess.
	if diffuse_source.is_empty():
		diffuse_source = _exact_parameter_texture(record, "AlbedoTexture")
	# UE VFX masters commonly expose the cooked color texture through the
	# explicit source parameter DIFF. This is parameter authority, not a
	# filename/material-name guess.
	if diffuse_source.is_empty():
		diffuse_source = _exact_parameter_texture(record, "DIFF")
	if normal_source.is_empty():
		normal_source = _exact_parameter_texture(record, "NormalTexture")
	if emissive_source.is_empty() and not graph_emissive_as_unshaded_color:
		emissive_source = _exact_parameter_texture(record, "EmissiveTexture")
	if emissive_source.is_empty() and not graph_emissive_as_unshaded_color:
		emissive_source = _exact_parameter_texture(record, "EMISS")

	# Some cooked source materials expose their real texture binding under the
	# original parameter name instead of PM_Diffuse/PM_Normals. Do not guess by
	# material name: accept a fallback only when the manifest itself declares
	# exactly one unique sRGB texturePath (albedo) or one unique normal-like
	# linear texturePath. These paths are source-authored UE bindings.
	if diffuse_source.is_empty():
		diffuse_source = _unique_source_srgb_texture(record)
	if diffuse_source.is_empty():
		var duplicate_diffuse := _duplicate_source_material_parameter(
			material_path,
			"diffuse"
		)
		if not duplicate_diffuse.is_empty():
			diffuse_source = duplicate_diffuse
			_source_duplicate_material_hits += 1
	if diffuse_source.is_empty():
		diffuse_source = _source_named_composite_diffuse(material_path)
	if normal_source.is_empty():
		normal_source = _unique_source_normal_texture(record)
	if normal_source.is_empty():
		normal_source = _duplicate_source_material_parameter(
			material_path,
			"normal"
		)

	var diffuse := _texture_for_source(diffuse_source)
	# A cooked material can preserve a non-empty source binding whose Texture2D
	# payload is not part of this UGC PAK. Only after that exact binding fails,
	# fall back to the unique source alias recovered from the texture catalog.
	if diffuse == null:
		var resolved_alias := str(_source_material_resolved_alias_diffuse.get(material_path, ""))
		if not resolved_alias.is_empty() and resolved_alias != diffuse_source:
			var alias_texture := _texture_for_source(resolved_alias)
			if alias_texture != null:
				diffuse_source = resolved_alias
				diffuse = alias_texture
				_source_material_alias_hits += 1
	if diffuse == null:
		var exact_source := _source_exact_token_diffuse_for_composite(material_path)
		if not exact_source.is_empty() and exact_source != diffuse_source:
			var exact_texture := _texture_for_source(exact_source)
			if exact_texture != null:
				diffuse_source = exact_source
				diffuse = exact_texture
				_source_material_exact_token_hits += 1
	var normal := _texture_for_source(normal_source)
	var emissive := _texture_for_source(emissive_source)
	if diffuse != null:
		_source_material_textured_count += 1
		if _source_effective_material_paths.has(material_path):
			_source_effective_material_textured_count += 1
		material.albedo_texture = diffuse
		if _optional_source_path(canonical.get("diffuse", null)).is_empty():
			material.set_meta("source_noncanonical_diffuse_path", diffuse_source)
	else:
		_source_material_flat_fallback_count += 1
		var colors: Array = record.get("colors", [])
		var export_type := str(record.get("exportType", ""))
		var is_source_color := not colors.is_empty() and colors[0] is Dictionary
		var is_default_surface := export_type == "SyntheticDefaultSurface"
		var raw_property_keys: Array = record.get("rawPropertyKeys", [])
		# UE4.21 UMaterial constructor defaults are source engine semantics:
		# BaseColor = FColor(128,128,128), Metallic = 0, Specular = 0.5,
		# Roughness = 0.5. If a cooked base UMaterial has no BaseColor property
		# and no explicit color/texture binding, reproduce that exact constant
		# instead of letting Godot's white StandardMaterial default masquerade
		# as source material output.
		var is_engine_default_base_color := (
			export_type == "Material"
			and not is_source_color
			and not raw_property_keys.has("BaseColor")
		)
		if is_default_surface or is_engine_default_base_color:
			var ue_default_channel := 128.0 / 255.0
			material.albedo_color = Color(
				ue_default_channel,
				ue_default_channel,
				ue_default_channel,
				1.0
			)
			material.metallic = 0.0
			material.roughness = 0.5
			material.set("metallic_specular", 0.5)
			if is_default_surface:
				material.set_meta("source_ue421_default_surface_material", true)
			else:
				material.set_meta("source_ue421_default_base_color", true)
		if _source_effective_material_paths.has(material_path):
			_source_effective_material_flat_fallback_count += 1
			if is_source_color:
				_source_effective_source_color_count += 1
			elif is_default_surface:
				_source_effective_default_surface_count += 1
			elif is_engine_default_base_color:
				_source_effective_engine_default_count += 1
			else:
				_source_effective_unresolved_fallback_count += 1
			var diagnostic_textures: Array[Dictionary] = []
			for texture_raw: Variant in record.get("textures", []):
				if not (texture_raw is Dictionary):
					continue
				var texture_row := texture_raw as Dictionary
				var native_row: Dictionary = texture_row.get("native", {})
				diagnostic_textures.append({
					"parameter": str(texture_row.get("parameter", "")),
					"texturePath": str(texture_row.get("texturePath", "")),
					"srgb": bool(native_row.get("srgb", false)),
				})
			_source_effective_flat_fallback_rows.append({
				"materialPath": material_path,
				"exportType": str(record.get("exportType", "")),
				"textureCount": diagnostic_textures.size(),
				"textures": diagnostic_textures,
				"colorCount": (record.get("colors", []) as Array).size(),
				"rawPropertyKeys": record.get("rawPropertyKeys", []),
			})
		if not colors.is_empty() and colors[0] is Dictionary:
			var color_row := colors[0] as Dictionary
			material.albedo_color = Color(
				float(color_row.get("r", 1.0)),
				float(color_row.get("g", 1.0)),
				float(color_row.get("b", 1.0)),
				float(color_row.get("a", 1.0))
			)

	if normal != null:
		material.normal_enabled = true
		material.normal_texture = normal
	if emissive != null:
		material.emission_enabled = true
		material.emission_texture = emissive
		material.emission = Color.WHITE

	material.metallic = clampf(_source_scalar(record, "metallic", 0.0), 0.0, 1.0)
	# UE4.21 UMaterial constructor default Roughness is 0.5.
	material.roughness = clampf(_source_scalar(record, "roughness", 0.5), 0.0, 1.0)
	material.metallic_specular = maxf(0.0, _source_scalar(record, "specular", 0.5))
	material.cull_mode = (
		BaseMaterial3D.CULL_DISABLED
		if bool(record.get("twoSided", false))
		else BaseMaterial3D.CULL_BACK
	)

	var blend_mode := source_blend_mode
	if bool(record.get("isMasked", false)) or blend_mode == "BLEND_Masked":
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
		material.alpha_scissor_threshold = float(record.get("opacityMaskClipValue", 0.333))
	elif blend_mode == "BLEND_Translucent":
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		material.blend_mode = BaseMaterial3D.BLEND_MODE_MIX
	elif blend_mode == "BLEND_Additive":
		# UE additive Cascade materials must never fall through as opaque quads.
		# Godot still needs transparency enabled so texture/vertex alpha can
		# participate in the particle edge mask before additive accumulation.
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		material.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	elif blend_mode == "BLEND_Modulate":
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		material.blend_mode = BaseMaterial3D.BLEND_MODE_MUL
	elif blend_mode == "BLEND_AlphaComposite":
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		material.blend_mode = BaseMaterial3D.BLEND_MODE_PREMULT_ALPHA

	if source_shading_model == "MSM_Unlit":
		material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED

	material.set_meta("source_material_path", material_path)
	material.set_meta("source_blend_mode", blend_mode)
	material.set_meta("source_resolved_diffuse_path", diffuse_source)
	material.set_meta("source_resolved_normal_path", normal_source)
	material.set_meta("source_resolved_emissive_path", emissive_source)
	material.set_meta(
		"source_graph_emissive_as_unshaded_color",
		graph_emissive_as_unshaded_color
	)
	material.set_meta("source_specular_mask_path", _optional_source_path(canonical.get("specular_masks", null)))
	_material_cache[material_path] = material
	_material_cache[canonical_path] = material
	return material

func _source_name_token(value: String) -> String:
	var token := value.get_file().get_basename().to_lower()
	var out := ""
	var previous_separator := false
	for i in range(token.length()):
		var ch := token.substr(i, 1)
		var code := ch.unicode_at(0)
		var is_alpha_num := (
			(code >= 48 and code <= 57)
			or (code >= 97 and code <= 122)
		)
		if is_alpha_num:
			out += ch
			previous_separator = false
		elif not previous_separator:
			out += "_"
			previous_separator = true
	return out.trim_prefix("_").trim_suffix("_")

func _source_texture_likely_color(source_path: String) -> bool:
	var token := _source_name_token(source_path)
	var has_color_marker := (
		token.contains("_c_")
		or token.ends_with("_c")
		or token.contains("_col_")
		or token.contains("color")
		or token.contains("rgb")
	)
	var explicit_non_color := (
		token.contains("_normal_")
		or token.contains("_nml_")
		or token.ends_with("_n")
		or token.contains("_spc_")
		or token.contains("_spec_")
		or token.contains("_rough_")
		or token.contains("_mask_")
		or token.ends_with("_s")
		or token.contains("_s_")
	)
	if explicit_non_color and not has_color_marker:
		return false
	return true

func _is_hex_token(value: String) -> bool:
	if value.is_empty():
		return false
	for i in range(value.length()):
		var c := value.substr(i, 1).to_lower()
		if "0123456789abcdef".find(c) < 0:
			return false
	return true

func _trim_source_hash(token: String) -> String:
	var parts := token.split("_", false)
	if parts.size() > 1:
		var tail := str(parts[parts.size() - 1])
		if tail.length() == 8 and _is_hex_token(tail):
			parts.remove_at(parts.size() - 1)
			return "_".join(parts)
	return token

func _strip_source_suffix(token: String) -> String:
	var result := token
	var suffixes: Array[String] = [
		"_c_rgb_r",
		"_c_rgb",
		"_c_rgba",
		"_c_rga",
		"_c_rg",
		"_c_r",
		"_col",
		"_dec_col",
		"_c",
		"_d",
		"_mat",
	]
	for suffix: String in suffixes:
		if result.ends_with(suffix):
			result = result.trim_suffix(suffix)
			break
	return result

func _source_semantic_base(value: String) -> String:
	var token := _trim_source_hash(_source_name_token(value))
	token = _strip_source_suffix(token)
	var generated_prefixes: Array[String] = [
		"gzm_", "gjun_", "gpent_", "grus_", "gus_", "gcub_",
		"gberlin_", "gafr_", "ghavana_", "gpb_", "geb_", "gny_",
		"gt6_", "gconcrete_", "gdecal_", "gstone_", "gglobal_",
	]
	for prefix: String in generated_prefixes:
		if token.begins_with(prefix):
			token = token.trim_prefix("g")
			break
	token = token.replace("zm_nuked_", "zm_")
	token = token.replace("vinylsidings", "vinylsiding")
	var modifiers: Array[String] = [
		"_lambert_blend",
		"_lambert",
		"_blend",
		"_glossy",
	]
	for modifier: String in modifiers:
		if token.ends_with(modifier):
			token = token.trim_suffix(modifier)
			break
	return token.trim_prefix("_").trim_suffix("_")

func _source_semantic_keys(value: String) -> Array[String]:
	var base := _source_semantic_base(value)
	var keys: Array[String] = []
	if base.length() >= 4:
		keys.append(base)
	var contextual_prefixes: Array[String] = [
		"zm_",
		"jun_art_", "jun_ter_", "jun_dec_",
		"pent_art_",
		"rus_art_", "rus_metal_",
		"us_art_",
		"cub_art_", "cub_ter_",
		"berlin_",
		"mp_b_art_",
		"mtl_p_glo_",
		"ch_",
	]
	for prefix: String in contextual_prefixes:
		if base.begins_with(prefix):
			var stripped := base.trim_prefix(prefix)
			if stripped.length() >= 4 and not keys.has(stripped):
				keys.append(stripped)
	return keys

func _register_source_material_alias(key: String, diffuse_source: String) -> void:
	if key.is_empty() or diffuse_source.is_empty():
		return
	if _source_material_alias_conflicts.has(key):
		return
	if not _source_material_alias_diffuse.has(key):
		_source_material_alias_diffuse[key] = diffuse_source
		return
	if str(_source_material_alias_diffuse[key]) != diffuse_source:
		_source_material_alias_diffuse.erase(key)
		_source_material_alias_conflicts[key] = true

func _register_source_duplicate_material_parameters(
	material_path: String,
	record: Dictionary
) -> void:
	# Some cooked maps contain a base Material override and a sibling
	# MaterialInstanceConstant with the exact same source material basename.
	# Only accept the sibling as authority when it exposes an explicit
	# AlbedoTexture parameter. This is an exact source identity + parameter
	# relationship, not filename similarity or a visual guess.
	var diffuse_source := _exact_parameter_texture(record, "AlbedoTexture")
	if diffuse_source.is_empty():
		return
	var key := material_path.get_file().get_basename().to_lower()
	if key.is_empty() or _source_duplicate_material_conflicts.has(key):
		return
	var candidate := {
		"sourceMaterialPath": material_path,
		"diffuse": diffuse_source,
		"normal": _exact_parameter_texture(record, "NormalTexture"),
	}
	if not _source_duplicate_material_parameters.has(key):
		_source_duplicate_material_parameters[key] = candidate
		return
	var existing: Dictionary = _source_duplicate_material_parameters[key]
	if (
		str(existing.get("diffuse", "")) != diffuse_source
		or str(existing.get("normal", "")) != str(candidate.get("normal", ""))
	):
		_source_duplicate_material_parameters.erase(key)
		_source_duplicate_material_conflicts[key] = true


func _duplicate_source_material_parameter(
	material_path: String,
	parameter_name: String
) -> String:
	var key := material_path.get_file().get_basename().to_lower()
	if key.is_empty() or _source_duplicate_material_conflicts.has(key):
		return ""
	var candidate: Dictionary = _source_duplicate_material_parameters.get(key, {})
	if candidate.is_empty():
		return ""
	var source_material_path := str(candidate.get("sourceMaterialPath", ""))
	if source_material_path.is_empty() or source_material_path == material_path:
		return ""
	if parameter_name == "diffuse":
		return str(candidate.get("diffuse", ""))
	if parameter_name == "normal":
		return str(candidate.get("normal", ""))
	return ""


func _build_source_material_aliases() -> void:
	for material_path_var: Variant in _material_records.keys():
		var material_path := str(material_path_var)
		var record: Dictionary = _material_records[material_path]
		_register_source_duplicate_material_parameters(material_path, record)

	# Cooked /nt/ material packages no longer retain Texture2D imports, but the
	# source texture catalog itself still preserves the original semantic names.
	# Register ONLY exact semantic keys from source sRGB color textures. Any key
	# that maps to more than one source texture is discarded as a conflict.
	for source_path: String in _source_srgb_texture_paths:
		if not _source_texture_likely_color(source_path):
			continue
		for key: String in _source_semantic_keys(source_path):
			_register_source_material_alias(key, source_path)

	for material_path_var: Variant in _material_records.keys():
		var material_path := str(material_path_var)
		if not material_path.to_lower().contains("/text/"):
			continue
		var record: Dictionary = _material_records[material_path]
		var canonical: Dictionary = record.get("canonicalTextures", {})
		var diffuse_source := str(canonical.get("diffuse", ""))
		if diffuse_source.is_empty():
			diffuse_source = _unique_source_srgb_texture(record)
		if diffuse_source.is_empty() or not _source_texture_likely_color(diffuse_source):
			continue
		for key: String in _source_semantic_keys(material_path):
			_register_source_material_alias(key, diffuse_source)
		for key: String in _source_semantic_keys(diffuse_source):
			_register_source_material_alias(key, diffuse_source)

	# Resolve every generated /nt/ base layer once, after the unique source
	# alias table is complete. This makes the source-authoritative relationship
	# explicit instead of recomputing it while individual mesh surfaces load.
	for material_path_var: Variant in _material_records.keys():
		var material_path := str(material_path_var)
		if not material_path.to_lower().contains("/nt/"):
			continue
		var alias_source := _source_alias_diffuse_for_composite(material_path)
		if not alias_source.is_empty():
			_source_material_resolved_alias_diffuse[material_path] = alias_source

	print(
		"XZOGOT_NUKETOWN_MATERIAL_ALIASES aliases=",
		_source_material_alias_diffuse.size(),
		" resolved=", _source_material_resolved_alias_diffuse.size(),
		" conflicts=", _source_material_alias_conflicts.size()
	)

func _source_alias_diffuse_for_composite(material_path: String) -> String:
	if not material_path.to_lower().contains("/nt/"):
		return ""
	var material_name := material_path.get_file().get_basename()
	var layers := material_name.split("__", false)
	if layers.is_empty():
		return ""
	var base_layer := str(layers[0])
	for key: String in _source_semantic_keys(base_layer):
		if _source_material_alias_diffuse.has(key):
			var alias_source := str(_source_material_alias_diffuse[key])
			if not alias_source.is_empty():
				return alias_source
	return ""

func _source_named_composite_diffuse(material_path: String) -> String:
	# Generated Nuketown composites encode the base material first and optional
	# overlays after "__". Albedo authority must come only from the first/base
	# layer: later layers are decals, burn/rubble blends, trim or masks and must
	# never repaint the whole surface.
	if not material_path.to_lower().contains("/nt/"):
		return ""
	var material_name := material_path.get_file().get_basename()
	var layers := material_name.split("__", false)
	if layers.is_empty():
		return ""
	var base_layer := str(layers[0])

	# Prefer the pre-resolved unique source alias. Ambiguous aliases never enter
	# this map, so a hit remains deterministic and source-authored.
	var resolved_alias := str(_source_material_resolved_alias_diffuse.get(material_path, ""))
	if not resolved_alias.is_empty():
		_source_material_alias_hits += 1
		return resolved_alias

	return _source_exact_token_diffuse_for_composite(material_path)

func _source_exact_token_diffuse_for_composite(material_path: String) -> String:
	if not material_path.to_lower().contains("/nt/"):
		return ""
	var material_name := material_path.get_file().get_basename()
	var layers := material_name.split("__", false)
	if layers.is_empty():
		return ""
	# Generated composites encode the base material before "__". A unique exact
	# token containment in the source sRGB catalog is conservative enough to use;
	# zero or multiple matches remain flat instead of guessing.
	var layer := _source_name_token(str(layers[0]))
	if layer.length() < 5:
		return ""
	var matches: Array[String] = []
	for source_path: String in _source_srgb_texture_paths:
		if not _source_texture_likely_color(source_path):
			continue
		var source_name := _source_name_token(source_path)
		if source_name.contains(layer):
			matches.append(source_path)
	if matches.size() == 1:
		return matches[0]
	return ""

func _exact_parameter_texture(record: Dictionary, parameter_name: String) -> String:
	var matches: Dictionary = {}
	for raw: Variant in record.get("textures", []):
		if not (raw is Dictionary):
			continue
		var row := raw as Dictionary
		if str(row.get("parameter", "")).nocasecmp_to(parameter_name) != 0:
			continue
		var source := str(row.get("texturePath", ""))
		if not source.is_empty():
			matches[source] = true
	if matches.size() != 1:
		return ""
	return str(matches.keys()[0])

func _unique_source_srgb_texture(record: Dictionary) -> String:
	var unique: Dictionary = {}
	for raw: Variant in record.get("textures", []):
		if not (raw is Dictionary):
			continue
		var row := raw as Dictionary
		var native: Dictionary = row.get("native", {})
		if not bool(native.get("srgb", false)):
			continue
		var source := str(row.get("texturePath", ""))
		if not source.is_empty():
			unique[source] = true
	if unique.size() != 1:
		return ""
	return str(unique.keys()[0])

func _unique_source_normal_texture(record: Dictionary) -> String:
	var unique: Dictionary = {}
	for raw: Variant in record.get("textures", []):
		if not (raw is Dictionary):
			continue
		var row := raw as Dictionary
		var native: Dictionary = row.get("native", {})
		if bool(native.get("srgb", true)):
			continue
		var parameter := str(row.get("parameter", "")).to_lower()
		var source := str(row.get("texturePath", ""))
		var semantic := parameter + " " + source.to_lower()
		if not (
			semantic.contains("normal")
			or semantic.contains("nml")
			or semantic.contains("norm")
		):
			continue
		if not source.is_empty():
			unique[source] = true
	if unique.size() != 1:
		return ""
	return str(unique.keys()[0])

func _source_scalar(record: Dictionary, token: String, fallback: float) -> float:
	var needle := token.to_lower()
	for raw: Variant in record.get("scalars", []):
		if raw is Dictionary:
			var row := raw as Dictionary
			if str(row.get("name", "")).to_lower().contains(needle):
				return float(row.get("value", fallback))
	return fallback

func _texture_for_source(source_path: String) -> Texture2D:
	if source_path.is_empty():
		return null
	if _texture_cache.has(source_path):
		return _texture_cache[source_path] as Texture2D
	var runtime_file := str(_texture_runtime_files.get(source_path, ""))
	if runtime_file.is_empty():
		return null

	# Godot 4.6 does not expose an Image format for ASTC 6x6. The benchmark
	# capture pipeline decodes the source XZTX mip0 through astcenc into PNG
	# sidecars before import. Prefer that source-derived sidecar.
	var texture := _load_decoded_texture(runtime_file)
	if texture == null:
		texture = _load_xztexture(runtime_file)
	if texture != null:
		_texture_cache[source_path] = texture
	return texture

func _load_decoded_texture(runtime_file: String) -> Texture2D:
	var basename := runtime_file.get_basename()

	# PNG sidecars remain the compatibility path for ASTC/mobile source.
	var png_path := _source_path(
		vfs_map_root.path_join("textures_png").path_join(basename + ".png")
	)
	if ResourceLoader.exists(png_path):
		var png_resource := load(png_path)
		if png_resource is Texture2D:
			_source_texture_resource_hits += 1
			return png_resource as Texture2D
	if FileAccess.file_exists(png_path):
		var image := Image.new()
		var image_error := image.load(png_path)
		if image_error == OK and not image.is_empty():
			_source_texture_image_hits += 1
			return ImageTexture.create_from_image(image)

	# Nacht/UE4.21 cooks BC1/BC3/BC5/BGRA8/G8. The stage bridge writes DDS
	# without re-encoding the source mip payloads, so normals/color blocks stay
	# source-authoritative instead of being flattened into guessed PNGs.
	var dds_path := _source_path(
		vfs_map_root.path_join("textures_dds").path_join(basename + ".dds")
	)
	if ResourceLoader.exists(dds_path):
		var dds_resource := load(dds_path)
		if dds_resource is Texture2D:
			_source_texture_resource_hits += 1
			return dds_resource as Texture2D

	_source_texture_load_failures += 1
	return null

func _load_xztexture(runtime_file: String) -> Texture2D:
	# Keep XZTX validation for truthful diagnostics, but never reinterpret ASTC
	# 6x6 as 4x4/8x8. Godot 4.6 has no FORMAT_ASTC_6x6 enum.
	var path := _source_path(vfs_map_root.path_join("textures").path_join(runtime_file))
	if not FileAccess.file_exists(path):
		return null
	var bytes := FileAccess.get_file_as_bytes(path)
	if bytes.size() < XZTX_HEADER_BYTES or bytes.slice(0, 4).get_string_from_ascii() != "XZTX":
		return null
	var version := int(bytes.decode_u32(4))
	var depth := int(bytes.decode_u32(16))
	var mip_count := int(bytes.decode_u32(20))
	var format_name_bytes := int(bytes.decode_u32(28))
	var mip_record_bytes := int(bytes.decode_u32(32))
	var mip_table_offset := int(bytes.decode_u32(36))
	var payload_offset := int(bytes.decode_u32(40))
	var payload_bytes := int(bytes.decode_u32(44))
	if version != 1 or depth != 1 or mip_count <= 0:
		return null
	if mip_record_bytes != XZTX_MIP_RECORD_BYTES or mip_table_offset != XZTX_HEADER_BYTES:
		return null
	if payload_offset < XZTX_HEADER_BYTES or payload_offset + payload_bytes != bytes.size():
		return null
	var format_name := bytes.slice(48, 48 + format_name_bytes).get_string_from_ascii()
	if format_name == "PF_ASTC_6x6":
		push_warning(
			"XZIEL benchmark ASTC 6x6 requires decoded source sidecar: " + runtime_file
		)
		return null
	push_warning("XZIEL benchmark unsupported XZTX format: " + format_name)
	return null

func _apply_instance_materials(
	node: MeshInstance3D,
	instance_id: String,
	scene_mesh_index: int,
	surface_offset: int = 0
) -> void:
	if not build_materials or node.mesh == null:
		return
	var base_materials: Array = _mesh_material_paths.get(scene_mesh_index, [])
	var material_slots: Array = _mesh_material_slots.get(scene_mesh_index, [])
	var overrides: Dictionary = _instance_overrides.get(instance_id, {})
	var surface_count := node.mesh.get_surface_count()
	for local_surface in range(surface_count):
		var source_surface := surface_offset + local_surface
		var source_slot := (
			int(material_slots[source_surface])
			if source_surface >= 0 and source_surface < material_slots.size()
			else -1
		)
		var material_path := ""
		if source_slot >= 0 and overrides.has(source_slot):
			material_path = str(overrides[source_slot])
		elif source_surface >= 0 and source_surface < base_materials.size():
			material_path = str(base_materials[source_surface])
		if material_path.is_empty():
			continue
		if not _source_effective_material_paths.has(material_path):
			push_warning(
				"XZIEL benchmark effective material missing from XZMI authority: "
				+ material_path
			)
		var material := _material_for_path(material_path)
		if material != null:
			node.set_surface_override_material(local_surface, material)

func _transform_from_row_major(raw: Variant) -> Transform3D:
	if not (raw is Array):
		return Transform3D.IDENTITY
	var m := raw as Array
	if m.size() != 16:
		return Transform3D.IDENTITY
	return Transform3D(
		Basis(
			Vector3(float(m[0]), float(m[4]), float(m[8])),
			Vector3(float(m[1]), float(m[5]), float(m[9])),
			Vector3(float(m[2]), float(m[6]), float(m[10]))
		),
		Vector3(float(m[3]), float(m[7]), float(m[11]))
	)

func _build_source_lights() -> void:
	var report := _read_json(_source_path(light_report_file))
	if report.is_empty():
		return
	var created := 0
	var environment: Environment = null
	var world_environment: WorldEnvironment = null

	for raw: Variant in report.get("lights", []):
		if not (raw is Dictionary):
			continue
		var row := raw as Dictionary
		var type := str(row.get("componentType", ""))
		var source_position := _vec3(row.get("worldPositionMeters", []))
		var color := _color3(row.get("color", []))
		var intensity := float(row.get("intensity", 1.0))
		match type:
			"point":
				var light := OmniLight3D.new()
				light.name = str(row.get("id", "SourcePointLight"))
				light.position = source_position
				light.light_color = color
				light.omni_range = float(row.get("radiusMeters", 10.0))
				light.light_energy = 1.0
				# Source positional intensity is in candelas. Preserve the
				# physically equivalent lumens for projects using physical units.
				if str(row.get("units", "")) == "Candelas":
					light.light_intensity_lumens = intensity * 4.0 * PI
				elif str(row.get("units", "")) == "Lumens":
					light.light_intensity_lumens = intensity
				_apply_source_light_semantics(light, row)
				_runtime_root.add_child(light)
				created += 1
			"spot":
				var light := SpotLight3D.new()
				light.name = str(row.get("id", "SourceSpotLight"))
				light.position = source_position
				light.light_color = color
				light.spot_range = float(row.get("radiusMeters", 10.0))
				light.spot_angle = float(row.get("outerConeAngleDegrees", 45.0))
				light.basis = _directional_basis_xziel(row.get("worldRotationUE", {}))
				light.light_energy = 1.0
				var source_units := str(row.get("units", ""))
				if source_units == "Lumens":
					light.light_intensity_lumens = intensity
				elif source_units == "Candelas":
					var outer_radians := deg_to_rad(maxf(0.001, light.spot_angle))
					var solid_angle := 2.0 * PI * (1.0 - cos(outer_radians))
					light.light_intensity_lumens = intensity * solid_angle
				_apply_source_light_semantics(light, row)
				light.set_meta("source_inner_cone_degrees", row.get("innerConeAngleDegrees", null))
				light.set_meta("source_outer_cone_degrees", row.get("outerConeAngleDegrees", null))
				_runtime_root.add_child(light)
				created += 1
			"directional":
				var light := DirectionalLight3D.new()
				light.name = str(row.get("id", "SourceDirectionalLight"))
				light.position = source_position
				light.light_color = color
				light.light_energy = 1.0
				light.light_intensity_lux = intensity
				light.basis = _directional_basis_xziel(row.get("worldRotationUE", {}))
				_apply_source_light_semantics(light, row)
				_runtime_root.add_child(light)
				created += 1
			"sky":
				if world_environment == null:
					world_environment = WorldEnvironment.new()
					world_environment.name = "SourceSkyEnvironment"
					environment = Environment.new()
					# UE SkyLight is ambient/IBL authority, not the rendered sky.
					# Treating its white light color as the background caused the
					# giant white capture. Keep its ambient contribution only.
					environment.background_mode = Environment.BG_CLEAR_COLOR
					environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
					environment.ambient_light_color = color
					environment.ambient_light_energy = intensity
					world_environment.environment = environment
					_runtime_root.add_child(world_environment)
					world_environment.set_meta("source_sky_intensity", intensity)
					created += 1

	_apply_source_environment_truth(environment, world_environment)
	set_meta("xziel_benchmark_light_count", created)
	print("XZOGOT_XZIEL_BENCHMARK_LIGHTS ", created)

func _apply_source_environment_truth(
	environment: Environment,
	world_environment: WorldEnvironment
) -> void:
	var truth := _read_json(source_environment_truth_file)
	if truth.is_empty():
		push_warning("XZIEL benchmark source gameplay truth missing")
		return
	var env_truth: Dictionary = truth.get("environment", {})
	var fog: Dictionary = env_truth.get("fog", {})
	if fog.is_empty():
		return

	var target_environment := environment
	var target_world := world_environment
	if target_environment == null:
		target_environment = Environment.new()
		target_environment.background_mode = Environment.BG_CLEAR_COLOR
	if target_world == null:
		target_world = WorldEnvironment.new()
		target_world.name = "SourceGameplayEnvironment"
		target_world.environment = target_environment
		_runtime_root.add_child(target_world)

	var mode := str(fog.get("mode", ""))
	if mode == "exponential":
		target_environment.fog_mode = Environment.FOG_MODE_EXPONENTIAL
	target_environment.fog_enabled = true
	target_environment.fog_density = float(fog.get("density", 0.0))

	var sky_light: Dictionary = env_truth.get("skyLight", {})
	target_world.set_meta("source_sky_realtime_capture", bool(sky_light.get("realTimeCapture", false)))
	target_world.set_meta("source_fog_location_ue", fog.get("relativeLocationUE", []))
	set_meta("xziel_benchmark_fog_enabled", target_environment.fog_enabled)
	set_meta("xziel_benchmark_fog_density", target_environment.fog_density)
	set_meta("xziel_benchmark_fog_mode", mode)
	print(
		"XZOGOT_SOURCE_ENV_GREEN map=", source_runtime_id, " ",
		"fog_mode=", mode,
		" fog_density=", target_environment.fog_density,
		" skylight_realtime=", target_world.get_meta("source_sky_realtime_capture")
	)

func _apply_source_light_semantics(light: Light3D, row: Dictionary) -> void:
	light.shadow_enabled = bool(row.get("castShadows", false))
	light.visible = bool(row.get("visible", true))
	light.set_meta("source_intensity", float(row.get("intensity", 0.0)))
	light.set_meta("source_intensity_units", str(row.get("units", "")))
	light.set_meta("source_inverse_squared", row.get("inverseSquared", null))
	light.set_meta("source_falloff_exponent", row.get("falloffExponent", null))
	light.set_meta("source_temperature_kelvin", row.get("temperatureKelvin", null))
	light.set_meta("source_use_temperature", row.get("useTemperature", null))
	light.set_meta("source_radius_meters", row.get("radiusMeters", null))
	light.set_meta("source_radius_source_meters", row.get("sourceRadiusMeters", null))
	light.set_meta("source_soft_radius_meters", row.get("softSourceRadiusMeters", null))
	light.set_meta("source_length_meters", row.get("sourceLengthMeters", null))
	light.set_meta("source_rotation_ue", row.get("worldRotationUE", {}))
	light.set_meta("source_atmosphere_sun", row.get("atmosphereSun", null))

func _directional_basis_xziel(raw: Variant) -> Basis:
	if not (raw is Dictionary):
		return Basis.IDENTITY
	var rot := raw as Dictionary
	var pitch := deg_to_rad(float(rot.get("Pitch", 0.0)))
	var yaw := deg_to_rad(float(rot.get("Yaw", 0.0)))
	# UE +X forward, +Y right, +Z up -> XZIEL +X forward, -Y left, +Z up.
	var forward := Vector3(
		cos(pitch) * cos(yaw),
		-cos(pitch) * sin(yaw),
		sin(pitch)
	).normalized()
	var source_up := Vector3(0.0, 0.0, 1.0)
	var z_axis := -forward
	var x_axis := source_up.cross(z_axis).normalized()
	if x_axis.length_squared() < 0.000001:
		x_axis = Vector3(1.0, 0.0, 0.0)
	var y_axis := z_axis.cross(x_axis).normalized()
	return Basis(x_axis, y_axis, z_axis)

func _vec3(raw: Variant) -> Vector3:
	if not (raw is Array):
		return Vector3.ZERO
	var values := raw as Array
	if values.size() != 3:
		return Vector3.ZERO
	return Vector3(float(values[0]), float(values[1]), float(values[2]))

func _color3(raw: Variant) -> Color:
	if not (raw is Array):
		return Color.WHITE
	var values := raw as Array
	if values.size() < 3:
		return Color.WHITE
	return Color(float(values[0]), float(values[1]), float(values[2]), 1.0)
