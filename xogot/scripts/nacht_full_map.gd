extends Node3D

const XzielBenchmarkLoaderScript = preload("res://scripts/xziel_benchmark_loader.gd")

## Nacht der Untoten Chronicles full-map source runtime.
##
## This scene is intentionally independent from the church and Nuketown.
## CI mounts a validated full-map authority payload under source_root.
## Geometry placement and actor/light identities are source-authored; nothing
## is procedurally substituted when an authority row is missing.

@export_dir var source_root: String = "res://assets/benchmarks/nacht_chronicles"
@export var build_world_collision: bool = true
@export var place_player_from_source_anchor: bool = true

const EXPECTED_SOURCE_PACKAGES := 3871
const HANDOFF_FILE := "nacht-full-map-handoff.json"
const SCENE_FILE := "nacht-static-scene.json"
const GLB_REPORT_FILE := "native-glb-report.json"
const GLB_DIR := "static_glb"
const LIGHTS_FILE := "nacht-lights.json"
const ENVIRONMENT_REPORT_FILE := "nacht-environment-report.json"
const PARTICLES_FILE := "nacht-particles.json"
const ENVIRONMENT_SCENE_FILE := "nacht-environment-scene.json"
const AUDIO_SCENE_FILE := "nacht-audio-scene.json"
const AUDIO_CUES_FILE := "nacht-audio-cues.json"

var _runtime_root: Node3D
var _benchmark_loader: Node3D
var _scene: Dictionary = {}
var _handoff: Dictionary = {}
var _glb_report: Dictionary = {}
var _lights_source: Dictionary = {}
var _environment_report: Dictionary = {}
var _particle_scene: Dictionary = {}
var _environment_scene: Dictionary = {}
var _audio_scene: Dictionary = {}
var _audio_cues: Dictionary = {}
var _mesh_cache: Dictionary = {}

var _created_instances := 0
var _missing_meshes := 0
var _actor_anchor_count := 0
var _collision_count := 0
var _light_count := 0
var _source_spawn_candidates: Array[Node3D] = []

func _ready() -> void:
	get_tree().set_meta("active_map_id", "nacht_chronicles_full")
	get_tree().set_meta("nacht_full_map_ready", false)
	call_deferred("_boot")

func _source_path(name: String) -> String:
	return source_root.path_join(name)

func _read_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	return parsed as Dictionary if parsed is Dictionary else {}

func _boot() -> void:
	_handoff = _read_json(_source_path(HANDOFF_FILE))
	_scene = _read_json(_source_path(SCENE_FILE))
	_glb_report = _read_json(_source_path(GLB_REPORT_FILE))
	_lights_source = _read_json(_source_path(LIGHTS_FILE))
	_environment_report = _read_json(_source_path(ENVIRONMENT_REPORT_FILE))
	_particle_scene = _read_json(_source_path(PARTICLES_FILE))
	_environment_scene = _read_json(_source_path(ENVIRONMENT_SCENE_FILE))
	_audio_scene = _read_json(_source_path(AUDIO_SCENE_FILE))
	_audio_cues = _read_json(_source_path(AUDIO_CUES_FILE))

	if not _validate_authority():
		return

	if not _build_shared_source_world():
		return

	# Actor anchors and light transforms use the same XZIEL coordinate basis as
	# the shared static-world loader but remain separate so gameplay adapters can
	# bind directly to source actor identities without touching render nodes.
	_runtime_root = Node3D.new()
	_runtime_root.name = "NachtSourceActorsAndLights"
	_runtime_root.basis = Basis(
		Vector3(0.0, 0.0, -1.0),
		Vector3(-1.0, 0.0, 0.0),
		Vector3(0.0, 1.0, 0.0)
	)
	add_child(_runtime_root)

	_build_actor_anchors()

	if place_player_from_source_anchor:
		_place_player()

	var summary: Dictionary = _scene.get("summary", {})
	set_meta("source_package_count", int(_handoff.get("sourcePackageCount", -1)))
	set_meta("source_mesh_count", int(summary.get("referencedNativeMeshCount", -1)))
	set_meta("source_instance_count", int(summary.get("sceneInstanceCount", -1)))
	set_meta("runtime_instance_count", _created_instances)
	set_meta("missing_mesh_count", _missing_meshes)
	set_meta("source_actor_anchor_count", int(summary.get("actorAnchorCount", -1)))
	set_meta("runtime_actor_anchor_count", _actor_anchor_count)
	set_meta("world_collision_count", _collision_count)
	set_meta("source_light_count", int(_environment_report.get("lightCount", -1)))
	set_meta("runtime_light_count", _light_count)
	set_meta("source_particle_component_count", int(_particle_scene.get("particleComponentCount", -1)))
	set_meta("runtime_particle_authority_count", (_particle_scene.get("particleComponents", []) as Array).size())
	set_meta("source_environment_component_count", int(_environment_scene.get("environmentComponentCount", -1)))
	set_meta("runtime_environment_authority_count", (_environment_scene.get("components", []) as Array).size())
	set_meta("source_audio_component_count", int(_audio_scene.get("audioComponentCount", -1)))
	set_meta("runtime_audio_authority_count", (_audio_scene.get("audioComponents", []) as Array).size())
	set_meta("source_sound_cue_count", int(_audio_cues.get("cueCount", -1)))
	set_meta("runtime_sound_cue_authority_count", (_audio_cues.get("cues", []) as Array).size())
	# These flags intentionally distinguish parsed source authority from visual /
	# audible runtime reproduction. They must only flip when those systems are
	# actually mounted, never merely because the JSON exists.
	set_meta("particle_visual_runtime_ready", false)
	set_meta("source_audio_runtime_ready", false)
	set_meta("source_environment_runtime_ready", false)
	set_meta("source_class_count", int((_handoff.get("fullMapAuthority", {}) as Dictionary).get("classCensus", {}).get("uniqueClasses", -1)))
	set_meta("nacht_full_map_ready", true)
	get_tree().set_meta("nacht_full_map_ready", true)

	print(
		"XZOGOT_NACHT_FULL_MAP_GREEN ",
		"packages=", get_meta("source_package_count"),
		" meshes=", get_meta("source_mesh_count"),
		" instances=", _created_instances,
		" actors=", _actor_anchor_count,
		" collisions=", _collision_count,
		" lights=", _light_count,
		" particles_authority=", get_meta("runtime_particle_authority_count"),
		" environment_authority=", get_meta("runtime_environment_authority_count"),
		" audio_authority=", get_meta("runtime_audio_authority_count"),
		" cues_authority=", get_meta("runtime_sound_cue_authority_count")
	)

func _validate_authority() -> bool:
	if _handoff.is_empty():
		push_error("NACHT_FULL_MAP: handoff missing")
		return false
	if int(_handoff.get("sourcePackageCount", -1)) != EXPECTED_SOURCE_PACKAGES:
		push_error("NACHT_FULL_MAP: source package authority mismatch")
		return false
	if str(_handoff.get("sourceMap", "")) != "Nacht_de_Untoten.umap":
		push_error("NACHT_FULL_MAP: wrong source map")
		return false
	if str(_scene.get("format", "")) != "xziel_visual_scene_v1":
		push_error("NACHT_FULL_MAP: source scene format invalid")
		return false
	var summary: Dictionary = _scene.get("summary", {})
	if not bool(summary.get("ready", false)):
		push_error("NACHT_FULL_MAP: source scene is not GREEN")
		return false
	if int(summary.get("mapPackageCount", 0)) != 1:
		push_error("NACHT_FULL_MAP: expected one source UMAP")
		return false
	if _glb_report.is_empty() or int(_glb_report.get("mesh_count", 0)) <= 0:
		push_error("NACHT_FULL_MAP: native GLB bridge missing")
		return false
	if _environment_report.is_empty() or int(_environment_report.get("lightCount", 0)) != 166:
		push_error("NACHT_FULL_MAP: source light report missing or incomplete")
		return false
	if _particle_scene.is_empty() or not bool(_particle_scene.get("ready", false)):
		push_error("NACHT_FULL_MAP: source particle placement authority missing")
		return false
	if int(_particle_scene.get("particleComponentCount", 0)) <= 0:
		push_error("NACHT_FULL_MAP: source particle placement authority empty")
		return false
	if _environment_scene.is_empty() or not bool(_environment_scene.get("ready", false)):
		push_error("NACHT_FULL_MAP: source environment authority missing")
		return false
	if _audio_scene.is_empty() or not bool(_audio_scene.get("ready", false)):
		push_error("NACHT_FULL_MAP: source audio placement authority missing")
		return false
	if int(_audio_scene.get("audioComponentCount", 0)) <= 0:
		push_error("NACHT_FULL_MAP: source audio placement authority empty")
		return false
	if _audio_cues.is_empty() or not bool(_audio_cues.get("ready", false)):
		push_error("NACHT_FULL_MAP: source SoundCue graph authority missing")
		return false
	if int(_audio_cues.get("cueCount", 0)) != 102:
		push_error("NACHT_FULL_MAP: source SoundCue graph count mismatch")
		return false
	return true

func _build_shared_source_world() -> bool:
	_benchmark_loader = XzielBenchmarkLoaderScript.new() as Node3D
	if _benchmark_loader == null:
		push_error("NACHT_FULL_MAP: generic source loader missing")
		return false

	_benchmark_loader.name = "NachtStaticWorld"
	_benchmark_loader.set("source_root", source_root)
	_benchmark_loader.set("load_on_ready", false)
	_benchmark_loader.set("build_materials", true)
	_benchmark_loader.set("build_lights", true)
	_benchmark_loader.set("build_skeletal_actors", false)
	_benchmark_loader.set("cast_geometry_shadows", true)
	_benchmark_loader.set("build_world_collision", build_world_collision)
	_benchmark_loader.set("max_instances", 0)
	_benchmark_loader.set("vfs_map_root", "vfs/xziel/maps/xziel_nacht_chronicles")
	_benchmark_loader.set("source_runtime_id", "nacht_chronicles")
	_benchmark_loader.set("visual_scene_file", SCENE_FILE)
	_benchmark_loader.set("material_bindings_file", "material-binding-manifest.json")
	_benchmark_loader.set("texture_report_file", "xzml-report.json")
	_benchmark_loader.set("effective_material_report_file", "xzmi-report.json")
	_benchmark_loader.set("complete_texture_report_file", "complete-xztx-report.json")
	_benchmark_loader.set("light_report_file", ENVIRONMENT_REPORT_FILE)
	# Never inherit another map's environment/fog authority.
	_benchmark_loader.set("source_environment_truth_file", "")
	add_child(_benchmark_loader)

	_benchmark_loader.call("_load_benchmark_world")
	var ready := bool(_benchmark_loader.get_meta("xziel_benchmark_ready", false))
	_created_instances = int(_benchmark_loader.get_meta("xziel_benchmark_instance_count", 0))
	_missing_meshes = int(_benchmark_loader.get_meta("xziel_benchmark_missing_meshes", 0))
	_collision_count = int(_benchmark_loader.get_meta("xziel_benchmark_world_collision_count", 0))
	_light_count = int(_benchmark_loader.get_meta("xziel_benchmark_light_count", 0))
	set_meta(
		"source_material_textured_count",
		int(_benchmark_loader.get_meta("xziel_benchmark_material_textured_count", 0))
	)
	set_meta(
		"source_material_flat_fallback_count",
		int(_benchmark_loader.get_meta("xziel_benchmark_material_flat_fallback_count", 0))
	)
	set_meta(
		"source_texture_load_failures",
		int(_benchmark_loader.get_meta("xziel_benchmark_texture_load_failures", 0))
	)
	set_meta(
		"source_complete_texture_catalog_count",
		int(_benchmark_loader.get_meta("xziel_benchmark_complete_texture_catalog_count", 0))
	)
	set_meta(
		"source_texture_resource_hits",
		int(_benchmark_loader.get_meta("xziel_benchmark_texture_resource_hits", 0))
	)
	set_meta(
		"source_texture_image_hits",
		int(_benchmark_loader.get_meta("xziel_benchmark_texture_image_hits", 0))
	)
	if not ready:
		push_error(
			"NACHT_FULL_MAP: generic source world incomplete instances="
			+ str(_created_instances)
			+ " missing=" + str(_missing_meshes)
		)
		return false
	var expected_lights := int(_environment_report.get("lightCount", -1))
	if expected_lights <= 0 or _light_count != expected_lights:
		push_error(
			"NACHT_FULL_MAP: generic source light coverage mismatch "
			+ str(_light_count) + "/" + str(expected_lights)
		)
		return false
	return true

func _build_static_world() -> bool:
	var glb_by_source: Dictionary = {}
	for raw: Variant in _glb_report.get("meshes", []):
		if raw is Dictionary:
			var row := raw as Dictionary
			glb_by_source[str(row.get("source", ""))] = str(row.get("output", ""))

	var meshes: Array = _scene.get("meshes", [])
	var instances: Array = _scene.get("instances", [])
	var resources: Array[Resource] = []
	resources.resize(meshes.size())

	for mesh_index in range(meshes.size()):
		var mesh_row: Dictionary = meshes[mesh_index]
		var runtime_file := str(mesh_row.get("runtimeFile", ""))
		var glb_name := str(glb_by_source.get(runtime_file, ""))
		if glb_name.is_empty():
			push_error("NACHT_FULL_MAP: no GLB bridge for " + runtime_file)
			return false
		var resource_path := _source_path(GLB_DIR).path_join(glb_name)
		if not ResourceLoader.exists(resource_path):
			push_error("NACHT_FULL_MAP: GLB missing " + resource_path)
			return false
		var packed := load(resource_path)
		if not (packed is PackedScene):
			push_error("NACHT_FULL_MAP: GLB did not import as PackedScene " + resource_path)
			return false
		resources[mesh_index] = packed

	for instance_index in range(instances.size()):
		var row: Dictionary = instances[instance_index]
		var mesh_index := int(row.get("meshIndex", -1))
		if mesh_index < 0 or mesh_index >= resources.size():
			push_error("NACHT_FULL_MAP: invalid mesh index " + str(mesh_index))
			return false
		var packed := resources[mesh_index] as PackedScene
		if packed == null:
			_missing_meshes += 1
			continue

		var root := Node3D.new()
		root.name = str(row.get("instanceId", "NachtInstance_%06d" % instance_index))
		root.transform = _transform_from_row_major(row.get("matrixRowMajor", []))
		root.set_meta("source_component_path", str(row.get("sourceComponentPath", "")))
		root.set_meta("source_scene_mesh_index", mesh_index)
		root.set_meta("source_instance_index", row.get("sourceInstanceIndex", null))
		_runtime_root.add_child(root)

		var visual := packed.instantiate()
		root.add_child(visual)
		_created_instances += 1

		if build_world_collision:
			_collision_count += _build_collision_recursive(visual)

	if _missing_meshes != 0 or _created_instances != instances.size():
		push_error(
			"NACHT_FULL_MAP: static world incomplete "
			+ str(_created_instances) + "/" + str(instances.size())
			+ " missing=" + str(_missing_meshes)
		)
		return false
	return true

func _build_collision_recursive(node: Node) -> int:
	var count := 0
	if node is MeshInstance3D:
		var mesh_instance := node as MeshInstance3D
		if mesh_instance.mesh != null:
			mesh_instance.create_trimesh_collision()
			if mesh_instance.get_child_count() > 0:
				count += 1
	for child: Node in node.get_children():
		if child is StaticBody3D:
			continue
		count += _build_collision_recursive(child)
	return count

func _build_actor_anchors() -> void:
	for raw: Variant in _scene.get("actorAnchors", []):
		if not (raw is Dictionary):
			continue
		var row := raw as Dictionary
		var anchor := Node3D.new()
		anchor.name = "SourceActor_%06d" % _actor_anchor_count
		anchor.transform = _transform_from_row_major(row.get("matrixRowMajor", []))
		anchor.set_meta("source_object_path", str(row.get("objectPath", "")))
		anchor.set_meta("source_class_name", str(row.get("className", "")))
		anchor.set_meta("source_root_component_path", str(row.get("rootComponentPath", "")))
		anchor.set_meta("source_anchor_source", str(row.get("anchorSource", "")))
		anchor.add_to_group("nacht_source_actor")
		_runtime_root.add_child(anchor)
		_actor_anchor_count += 1

		var identity := (
			str(row.get("className", "")) + " "
			+ str(row.get("objectPath", "")) + " "
			+ str(row.get("rootComponentPath", ""))
		).to_lower()
		# Only source actor identities known to represent player starts are
		# eligible. Never fall back to a generic "spawn" substring because the
		# Nacht package also contains zombie/dog/FX spawn actors.
		if (
			identity.contains("playerstart")
			or identity.contains("pavlov_spawn")
		):
			_source_spawn_candidates.append(anchor)

func _build_source_lights() -> void:
	var raw_by_id: Dictionary = {}
	for raw: Variant in _lights_source.get("lights", []):
		if raw is Dictionary:
			var row := raw as Dictionary
			raw_by_id[str(row.get("id", ""))] = row

	for raw: Variant in _environment_report.get("lights", []):
		if not (raw is Dictionary):
			continue
		var row := raw as Dictionary
		var source_id := str(row.get("id", ""))
		var exact: Dictionary = raw_by_id.get(source_id, {}) as Dictionary
		var props: Dictionary = exact.get("properties", {}) as Dictionary
		var type := str(row.get("componentType", ""))
		var source_position := _vec3(row.get("worldPositionMeters", []))
		var color := _color3(row.get("color", []))
		var intensity := float(row.get("intensity", 0.0))
		var created: Node = null

		match type:
			"point":
				var light := OmniLight3D.new()
				light.name = source_id
				light.position = source_position
				light.light_color = color
				light.omni_range = float(row.get("radiusMeters", 0.0))
				light.light_energy = 1.0
				if str(row.get("units", "")) == "Candelas":
					light.light_intensity_lumens = intensity * 4.0 * PI
				created = light
			"spot":
				var light := SpotLight3D.new()
				light.name = source_id
				light.position = source_position
				light.light_color = color
				light.spot_range = float(row.get("radiusMeters", 0.0))
				light.spot_angle = float(props.get("outerConeAngleDegrees", 45.0))
				light.basis = _directional_basis_xziel(row.get("worldRotationUE", {}))
				light.light_energy = 1.0
				created = light
			"directional":
				var light := DirectionalLight3D.new()
				light.name = source_id
				light.position = source_position
				light.light_color = color
				light.light_energy = 1.0
				light.light_intensity_lux = intensity
				light.basis = _directional_basis_xziel(row.get("worldRotationUE", {}))
				created = light
			"sky":
				var world := WorldEnvironment.new()
				world.name = source_id
				var environment := Environment.new()
				environment.background_mode = Environment.BG_CLEAR_COLOR
				environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
				environment.ambient_light_color = color
				environment.ambient_light_energy = intensity
				world.environment = environment
				created = world
			_:
				push_error("NACHT_FULL_MAP: unsupported source light type " + type)
				continue

		if created != null:
			created.set_meta("source_light_id", source_id)
			created.set_meta("source_light_type", type)
			created.set_meta("source_light_path", str(exact.get("sourcePath", "")))
			created.set_meta("source_light_properties", props.duplicate(true))
			_runtime_root.add_child(created)
			_light_count += 1

	if _light_count != int(_environment_report.get("lightCount", -1)):
		push_error(
			"NACHT_FULL_MAP: source light coverage mismatch "
			+ str(_light_count) + "/"
			+ str(_environment_report.get("lightCount", -1))
		)

func _place_player() -> void:
	var player := get_node_or_null("Player") as CharacterBody3D
	if player == null or _source_spawn_candidates.is_empty():
		return
	_source_spawn_candidates.sort_custom(
		func(a: Node3D, b: Node3D) -> bool:
			return str(a.get_meta("source_object_path", "")) < str(b.get_meta("source_object_path", ""))
	)
	var chosen := _source_spawn_candidates[0]
	player.global_transform = chosen.global_transform
	player.global_position += Vector3.UP * 0.9
	player.set_meta("nacht_source_spawn_object", chosen.get_meta("source_object_path", ""))
	print("XZOGOT_NACHT_PLAYER_SOURCE_SPAWN ", player.global_position)

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

func _directional_basis_xziel(raw: Variant) -> Basis:
	if not (raw is Dictionary):
		return Basis.IDENTITY
	var rot := raw as Dictionary
	var pitch := deg_to_rad(float(rot.get("Pitch", 0.0)))
	var yaw := deg_to_rad(float(rot.get("Yaw", 0.0)))
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
