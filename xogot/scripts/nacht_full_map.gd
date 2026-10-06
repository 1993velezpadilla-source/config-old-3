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
const PARTICLE_GRAPHS_FILE := "nacht-particle-graphs.json"
const PARTICLE_RUNTIME_AUTHORITY_FILE := "nacht-particle-runtime-authority.json"
const ENVIRONMENT_SCENE_FILE := "nacht-environment-scene.json"
const ENVIRONMENT_RUNTIME_AUTHORITY_FILE := "nacht-environment-runtime-authority.json"
const AUDIO_SCENE_FILE := "nacht-audio-scene.json"
const AUDIO_CUES_FILE := "nacht-audio-cues.json"
const AUDIO_RUNTIME_REPORT_FILE := "audio-runtime-report.json"
const AUDIO_RUNTIME_AUTHORITY_FILE := "nacht-audio-runtime-authority.json"

const SUPPORTED_SOURCE_AUDIO_EVENT_CALLS := {
	"play": true,
	"stop": true,
	"playsound2d": true,
	"playsoundatlocation": true,
	"spawnsoundatlocation": true,
	"spawnsoundattached": true,
	"playsoundattached": true,
}
const SUPPORTED_SOURCE_SOUND_CUE_NODE_TYPES := {
	"SoundNode": true,
	"SoundNodeWavePlayer": true,
	"SoundNodeLooping": true,
	"SoundNodeRandom": true,
}

var _runtime_root: Node3D
var _benchmark_loader: Node3D
var _scene: Dictionary = {}
var _handoff: Dictionary = {}
var _glb_report: Dictionary = {}
var _lights_source: Dictionary = {}
var _environment_report: Dictionary = {}
var _particle_scene: Dictionary = {}
var _particle_graphs: Dictionary = {}
var _particle_runtime_authority: Dictionary = {}
var _environment_scene: Dictionary = {}
var _environment_runtime_authority: Dictionary = {}
var _audio_scene: Dictionary = {}
var _audio_cues: Dictionary = {}
var _audio_runtime_report: Dictionary = {}
var _audio_runtime_authority: Dictionary = {}
var _audio_wave_file_by_path: Dictionary = {}
var _audio_cue_by_path: Dictionary = {}
var _source_audio_players: Dictionary = {}
var _source_audio_component_key_by_id: Dictionary = {}
var _source_audio_events_by_key: Dictionary = {}
var _source_audio_random_remaining: Dictionary = {}
var _mesh_cache: Dictionary = {}

var _created_instances := 0
var _missing_meshes := 0
var _actor_anchor_count := 0
var _collision_count := 0
var _light_count := 0
var _source_audio_player_count := 0
var _source_audio_stream_count := 0
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
	_particle_graphs = _read_json(_source_path(PARTICLE_GRAPHS_FILE))
	_particle_runtime_authority = _read_json(_source_path(PARTICLE_RUNTIME_AUTHORITY_FILE))
	_environment_scene = _read_json(_source_path(ENVIRONMENT_SCENE_FILE))
	_environment_runtime_authority = _read_json(_source_path(ENVIRONMENT_RUNTIME_AUTHORITY_FILE))
	_audio_scene = _read_json(_source_path(AUDIO_SCENE_FILE))
	_audio_cues = _read_json(_source_path(AUDIO_CUES_FILE))
	_audio_runtime_report = _read_json(_source_path(AUDIO_RUNTIME_REPORT_FILE))
	_audio_runtime_authority = _read_json(_source_path(AUDIO_RUNTIME_AUTHORITY_FILE))
	_index_audio_authority()
	_index_audio_runtime_events()

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

	if not _audio_runtime_report.is_empty():
		if not _build_source_audio_runtime():
			return

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
	set_meta("source_particle_system_count", int(_particle_graphs.get("particleSystemCount", -1)))
	set_meta("runtime_particle_graph_authority_count", (_particle_graphs.get("systems", []) as Array).size())
	set_meta("runtime_placed_particle_system_count", int(_particle_runtime_authority.get("uniquePlacedSystemCount", 0)))
	set_meta("runtime_placed_particle_node_type_count", (_particle_runtime_authority.get("placedNodeTypeCounts", {}) as Dictionary).size())
	set_meta("source_environment_component_count", int(_environment_scene.get("environmentComponentCount", -1)))
	set_meta("runtime_environment_authority_count", (_environment_scene.get("components", []) as Array).size())
	set_meta("runtime_environment_component_count", int(_environment_runtime_authority.get("componentCount", 0)))
	set_meta("source_audio_component_count", int(_audio_scene.get("audioComponentCount", -1)))
	set_meta("runtime_audio_authority_count", (_audio_scene.get("audioComponents", []) as Array).size())
	set_meta("source_sound_cue_count", int(_audio_cues.get("cueCount", -1)))
	set_meta("runtime_sound_cue_authority_count", (_audio_cues.get("cues", []) as Array).size())
	set_meta("runtime_audio_wave_catalog_count", _audio_wave_file_by_path.size())
	set_meta("runtime_sound_cue_index_count", _audio_cue_by_path.size())
	set_meta("source_audio_event_authority_count", int(_audio_runtime_authority.get("actorAudioEventCount", 0)))
	set_meta("source_audio_event_index_count", _source_audio_events_by_key.size())
	set_meta(
		"source_audio_used_cue_node_type_count",
		(_audio_runtime_authority.get("usedSoundCueNodeTypeCounts", {}) as Dictionary).size()
	)
	set_meta("source_audio_runtime_player_count", _source_audio_player_count)
	set_meta("source_audio_runtime_stream_count", _source_audio_stream_count)
	set_meta(
		"source_audio_stream_mount_ready",
		_source_audio_player_count == 3 and _source_audio_stream_count == 3
	)
	# These flags intentionally distinguish parsed source authority from visual /
	# audible runtime reproduction. They must only flip when those systems are
	# actually mounted, never merely because the JSON exists.
	set_meta("particle_visual_runtime_ready", false)
	set_meta("source_audio_runtime_ready", _source_audio_semantics_ready())
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
		" particle_graphs_authority=", get_meta("runtime_particle_graph_authority_count"),
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
	if int(_particle_scene.get("particleComponentCount", 0)) != 29:
		push_error("NACHT_FULL_MAP: source particle placement count mismatch")
		return false
	if int(_particle_scene.get("referencedTemplateCount", 0)) != 29:
		push_error("NACHT_FULL_MAP: source particle template coverage mismatch")
		return false
	if int(_particle_scene.get("nullTemplateCount", -1)) != 0:
		push_error("NACHT_FULL_MAP: source particle template authority contains nulls")
		return false
	if _particle_graphs.is_empty() or not bool(_particle_graphs.get("ready", false)):
		push_error("NACHT_FULL_MAP: source particle graph authority missing")
		return false
	if int(_particle_graphs.get("particleSystemCount", 0)) != 39:
		push_error("NACHT_FULL_MAP: source particle graph count mismatch")
		return false
	if not _particle_runtime_authority.is_empty():
		if not bool(_particle_runtime_authority.get("ready", false)):
			push_error("NACHT_FULL_MAP: placed particle runtime authority is not ready")
			return false
		if int(_particle_runtime_authority.get("placementCount", 0)) != 29:
			push_error("NACHT_FULL_MAP: placed particle runtime placement count mismatch")
			return false
		if int(_particle_runtime_authority.get("resolvedPlacementCount", 0)) != 29:
			push_error("NACHT_FULL_MAP: placed particle graph coverage mismatch")
			return false
	if _environment_scene.is_empty() or not bool(_environment_scene.get("ready", false)):
		push_error("NACHT_FULL_MAP: source environment authority missing")
		return false
	if not _environment_runtime_authority.is_empty():
		if not bool(_environment_runtime_authority.get("ready", false)):
			push_error("NACHT_FULL_MAP: environment runtime authority is not ready")
			return false
		if int(_environment_runtime_authority.get("componentCount", 0)) != 2:
			push_error("NACHT_FULL_MAP: environment runtime component count mismatch")
			return false
	if _audio_scene.is_empty() or not bool(_audio_scene.get("ready", false)):
		push_error("NACHT_FULL_MAP: source audio placement authority missing")
		return false
	if int(_audio_scene.get("audioComponentCount", 0)) != 3:
		push_error("NACHT_FULL_MAP: source audio placement count mismatch")
		return false
	if int(_audio_scene.get("referencedSoundCount", 0)) != 3:
		push_error("NACHT_FULL_MAP: source audio reference coverage mismatch")
		return false
	if int(_audio_scene.get("nullSoundCount", -1)) != 0:
		push_error("NACHT_FULL_MAP: source audio authority contains nulls")
		return false
	if _audio_cues.is_empty() or not bool(_audio_cues.get("ready", false)):
		push_error("NACHT_FULL_MAP: source SoundCue graph authority missing")
		return false
	if int(_audio_cues.get("cueCount", 0)) != 102:
		push_error("NACHT_FULL_MAP: source SoundCue graph count mismatch")
		return false
	if not _audio_runtime_report.is_empty():
		if not bool(_audio_runtime_report.get("ready", false)):
			push_error("NACHT_FULL_MAP: staged source OGG report is not ready")
			return false
		if int(_audio_runtime_report.get("audioCount", 0)) != 295:
			push_error("NACHT_FULL_MAP: staged source OGG count mismatch")
			return false
	if not _audio_runtime_authority.is_empty():
		if not bool(_audio_runtime_authority.get("ready", false)):
			push_error("NACHT_FULL_MAP: staged audio event authority is not ready")
			return false
		if int(_audio_runtime_authority.get("resolvedAudioComponentCount", 0)) != 3:
			push_error("NACHT_FULL_MAP: staged audio event component coverage mismatch")
			return false
		if not (_audio_runtime_authority.get("unresolvedComponents", []) as Array).is_empty():
			push_error("NACHT_FULL_MAP: staged audio event authority has unresolved components")
			return false
		if not (_audio_runtime_authority.get("unresolvedActorEvents", []) as Array).is_empty():
			push_error("NACHT_FULL_MAP: staged audio event authority has unresolved actor events")
			return false
		if not (_audio_runtime_authority.get("unresolvedAssets", []) as Array).is_empty():
			push_error("NACHT_FULL_MAP: staged audio event authority has unresolved assets")
			return false
	return true

func _canonical_ue_object_path(raw_path: String) -> String:
	var path := raw_path.strip_edges()
	var quote_index := path.find("'")
	if quote_index >= 0 and path.ends_with("'"):
		path = path.substr(quote_index + 1, path.length() - quote_index - 2)
	if path.begins_with("Content/"):
		path = "/Game/" + path.substr("Content/".length())
	elif path.begins_with("Game/"):
		path = "/" + path
	return path

func _index_audio_authority() -> void:
	_audio_wave_file_by_path.clear()
	_audio_cue_by_path.clear()

	for raw: Variant in _audio_runtime_report.get("audio", []):
		if not (raw is Dictionary):
			continue
		var row := raw as Dictionary
		var object_path := _canonical_ue_object_path(str(row.get("objectPath", "")))
		var runtime_file := str(row.get("runtimeFile", ""))
		if object_path.is_empty() or runtime_file.is_empty():
			continue
		_audio_wave_file_by_path[object_path] = runtime_file

	for raw: Variant in _audio_cues.get("cues", []):
		if not (raw is Dictionary):
			continue
		var cue := raw as Dictionary
		var object_path := _canonical_ue_object_path(str(cue.get("objectPath", "")))
		if object_path.is_empty():
			continue
		_audio_cue_by_path[object_path] = cue

func _index_audio_runtime_events() -> void:
	_source_audio_events_by_key.clear()
	for raw: Variant in _audio_runtime_authority.get("actorEventBindings", []):
		if not (raw is Dictionary):
			continue
		var event := raw as Dictionary
		var actor_name := str(event.get("actorName", ""))
		var function_name := str(event.get("function", ""))
		var start_offset := int(event.get("startOffset", -1))
		if actor_name.is_empty() or function_name.is_empty() or start_offset < 0:
			continue
		var key := actor_name + "|" + function_name + "|" + str(start_offset)
		_source_audio_events_by_key[key] = event


func _cue_node_property(node: Dictionary, property_name: String, default_value: Variant = null) -> Variant:
	for raw: Variant in node.get("properties", []):
		if not (raw is Dictionary):
			continue
		var row := raw as Dictionary
		if str(row.get("name", "")).to_lower() == property_name.to_lower():
			return row.get("value", default_value)
	return default_value


func _cue_node_map(cue: Dictionary) -> Dictionary:
	var result: Dictionary = {}
	for raw: Variant in cue.get("nodes", []):
		if not (raw is Dictionary):
			continue
		var node := raw as Dictionary
		var object_path := str(node.get("objectPath", ""))
		if object_path.is_empty():
			continue
		result[_authority_object_key(object_path)] = node
	return result


func _random_node_child_index(
	cue_path: String,
	node: Dictionary,
	consume_state: bool = true
) -> int:
	var children := node.get("children", []) as Array
	if children.is_empty():
		return -1

	var weights_raw: Variant = _cue_node_property(node, "Weights", [])
	var weights: Array = weights_raw as Array if weights_raw is Array else []
	var without_replacement := bool(
		_cue_node_property(node, "bRandomizeWithoutReplacement", false)
	)

	var node_path := str(node.get("objectPath", ""))
	var state_key := _authority_object_key(cue_path) + "|" + _authority_object_key(node_path)
	var candidates: Array[int] = []

	if without_replacement and consume_state:
		var remaining_raw: Variant = _source_audio_random_remaining.get(state_key, [])
		if remaining_raw is Array:
			for raw_index: Variant in remaining_raw:
				candidates.append(int(raw_index))
		if candidates.is_empty():
			for index in range(children.size()):
				candidates.append(index)
	else:
		for index in range(children.size()):
			candidates.append(index)

	# Building an autoplay=false component must not burn a source random draw.
	# Use the first reachable child only as a non-consuming preview stream; the
	# first real Play call performs the actual weighted source selection.
	if not consume_state:
		return candidates[0]

	var total_weight := 0.0
	var candidate_weights: Array[float] = []
	for index: int in candidates:
		var weight := 1.0
		if index >= 0 and index < weights.size():
			weight = maxf(0.0, float(weights[index]))
		candidate_weights.append(weight)
		total_weight += weight

	var selected_candidate := 0
	if total_weight > 0.0:
		var target := randf() * total_weight
		var running := 0.0
		for i in range(candidates.size()):
			running += candidate_weights[i]
			if target <= running:
				selected_candidate = i
				break
	else:
		selected_candidate = randi_range(0, candidates.size() - 1)

	var selected_index := candidates[selected_candidate]
	if without_replacement and consume_state:
		candidates.remove_at(selected_candidate)
		_source_audio_random_remaining[state_key] = candidates
	return selected_index


func _resolve_cue_wave_selection(
	cue: Dictionary,
	node_path: String = "",
	inherited_loop: bool = false,
	depth: int = 0,
	consume_random_state: bool = true
) -> Dictionary:
	if depth > 64:
		return {}

	var nodes := _cue_node_map(cue)
	var current_path := node_path
	if current_path.is_empty():
		current_path = str(cue.get("firstNode", ""))
	if current_path.is_empty():
		return {}

	var node := nodes.get(_authority_object_key(current_path), {}) as Dictionary
	if node.is_empty():
		return {}

	var node_type := str(node.get("exportType", ""))
	if node_type == "SoundNodeWavePlayer":
		var wave_path := str(node.get("wavePath", ""))
		if wave_path.is_empty():
			return {}
		var looping := inherited_loop
		for property_name in ["bLooping", "Looping", "bLoop"]:
			var value: Variant = _cue_node_property(node, property_name, null)
			if value is bool and bool(value):
				looping = true
			elif str(value).to_lower() in ["true", "1"]:
				looping = true
		return {
			"wavePath": wave_path,
			"looping": looping,
			"nodePath": str(node.get("objectPath", "")),
		}

	var children := node.get("children", []) as Array
	if children.is_empty():
		return {}

	if node_type == "SoundNodeRandom":
		var child_index := _random_node_child_index(
			str(cue.get("objectPath", "")),
			node,
			consume_random_state
		)
		if child_index < 0 or child_index >= children.size():
			return {}
		return _resolve_cue_wave_selection(
			cue,
			str(children[child_index]),
			inherited_loop,
			depth + 1,
			consume_random_state
		)

	var next_loop := inherited_loop or node_type == "SoundNodeLooping"
	return _resolve_cue_wave_selection(
		cue,
		str(children[0]),
		next_loop,
		depth + 1,
		consume_random_state
	)


func _source_audio_stream_for_asset(asset_path: String) -> Dictionary:
	var canonical := _canonical_ue_object_path(asset_path)
	var cue := _source_cue_for_path(canonical)
	var wave_path := canonical

	var selection: Dictionary = {}
	if not cue.is_empty():
		selection = _resolve_cue_wave_selection(cue)
		if selection.is_empty():
			return {}
		wave_path = str(selection.get("wavePath", ""))

	var runtime_path := _runtime_audio_file_for_wave(wave_path)
	if runtime_path.is_empty() or not ResourceLoader.exists(runtime_path):
		return {}
	var stream := load(runtime_path) as AudioStream
	if stream == null:
		return {}

	if not cue.is_empty():
		_set_audio_stream_loop(
			stream,
			bool(selection.get("looping", _cue_has_loop(cue)))
		)

	return {
		"stream": stream,
		"cue": cue,
		"wavePath": wave_path,
		"runtimePath": runtime_path,
		"looping": bool(selection.get("looping", false)),
	}


func _source_audio_component_player_by_id(component_id: String) -> AudioStreamPlayer3D:
	var component_key := str(_source_audio_component_key_by_id.get(component_id, ""))
	if component_key.is_empty():
		return null
	return _source_audio_players.get(component_key) as AudioStreamPlayer3D


func _source_audio_actor_position(actor_name: String) -> Vector3:
	for raw: Variant in _audio_scene.get("audioComponents", []):
		if not (raw is Dictionary):
			continue
		var row := raw as Dictionary
		if str(row.get("actorName", "")) == actor_name:
			return _audio_component_position(row.get("hierarchy", []))
	return Vector3.ZERO


func _source_audio_semantics_ready() -> bool:
	if _audio_runtime_authority.is_empty():
		return false
	if not bool(_audio_runtime_authority.get("ready", false)):
		return false
	if _source_audio_player_count != 3 or _source_audio_stream_count != 3:
		return false

	var node_counts := (
		_audio_runtime_authority.get("usedSoundCueNodeTypeCounts", {})
		as Dictionary
	)
	for raw_type: Variant in node_counts.keys():
		var node_type := str(raw_type)
		if not SUPPORTED_SOURCE_SOUND_CUE_NODE_TYPES.has(node_type):
			return false

	for raw: Variant in _audio_runtime_authority.get("actorEventBindings", []):
		if not (raw is Dictionary):
			continue
		var event := raw as Dictionary
		var call := str(event.get("call", "")).to_lower()
		if not SUPPORTED_SOURCE_AUDIO_EVENT_CALLS.has(call):
			return false
		# A Play/Stop on a generated temporary AudioComponent cannot yet be
		# addressed independently. SpawnSound* itself is supported, but until
		# that temporary return object is indexed, full bytecode semantics are
		# intentionally not GREEN.
		if call in ["play", "stop"] and str(event.get("resolvedComponentId", "")).is_empty():
			return false
	return true


func _audio_event_number(
	event: Dictionary,
	parameter_index: int,
	default_value: float
) -> float:
	var parameters := event.get("parameters", []) as Array
	if parameter_index < 0 or parameter_index >= parameters.size():
		return default_value
	var raw: Variant = parameters[parameter_index]
	if not (raw is Dictionary):
		return default_value
	var row := raw as Dictionary
	var value: Variant = row.get("value", null)
	if value is int or value is float:
		return float(value)
	return default_value


func play_source_audio_event(
	actor_name: String,
	function_name: String,
	start_offset: int,
	source_position: Variant = null
) -> bool:
	var key := actor_name + "|" + function_name + "|" + str(start_offset)
	var event := _source_audio_events_by_key.get(key, {}) as Dictionary
	if event.is_empty():
		return false

	var call := str(event.get("call", "")).to_lower()
	var resolved_component_id := str(event.get("resolvedComponentId", ""))
	if call in ["play", "stop"]:
		var component_player := _source_audio_component_player_by_id(resolved_component_id)
		if component_player == null:
			return false
		if call == "play":
			if not _refresh_source_audio_component_stream(component_player):
				return false
			component_player.play(_audio_event_number(event, 0, 0.0))
		else:
			component_player.stop()
		return true

	var asset_path := str(event.get("resolvedAsset", ""))
	if asset_path.is_empty():
		return false
	var resolved := _source_audio_stream_for_asset(asset_path)
	if resolved.is_empty():
		return false

	var stream := resolved.get("stream") as AudioStream
	if stream == null:
		return false
	var cue := resolved.get("cue", {}) as Dictionary
	var cue_volume := maxf(0.0001, float(cue.get("volumeMultiplier", 1.0)))
	var cue_pitch := maxf(0.01, float(cue.get("pitchMultiplier", 1.0)))

	if call == "playsound2d":
		var event_volume := maxf(0.0001, _audio_event_number(event, 2, 1.0))
		var event_pitch := maxf(0.01, _audio_event_number(event, 3, 1.0))
		var start_time := maxf(0.0, _audio_event_number(event, 4, 0.0))
		var player_2d := AudioStreamPlayer.new()
		player_2d.stream = stream
		player_2d.volume_db = linear_to_db(cue_volume * event_volume)
		player_2d.pitch_scale = cue_pitch * event_pitch
		player_2d.finished.connect(player_2d.queue_free)
		add_child(player_2d)
		player_2d.play(start_time)
		return true

	if call in [
		"playsoundatlocation",
		"spawnsoundatlocation",
		"spawnsoundattached",
		"playsoundattached"
	]:
		var event_volume := maxf(0.0001, _audio_event_number(event, 4, 1.0))
		var event_pitch := maxf(0.01, _audio_event_number(event, 5, 1.0))
		var start_time := maxf(0.0, _audio_event_number(event, 6, 0.0))
		var player_3d := AudioStreamPlayer3D.new()
		player_3d.stream = stream
		player_3d.volume_db = linear_to_db(cue_volume * event_volume)
		player_3d.pitch_scale = cue_pitch * event_pitch
		if source_position is Vector3:
			player_3d.position = source_position
		else:
			player_3d.position = _source_audio_actor_position(actor_name)
		if not _cue_has_loop(cue):
			player_3d.finished.connect(player_3d.queue_free)
		_runtime_root.add_child(player_3d)
		player_3d.play(start_time)
		return true

	return false


func _runtime_audio_file_for_wave(wave_path: String) -> String:
	var canonical := _canonical_ue_object_path(wave_path)
	var runtime_file := str(_audio_wave_file_by_path.get(canonical, ""))
	if runtime_file.is_empty():
		return ""
	return _source_path("audio").path_join(runtime_file)

func _source_cue_for_path(cue_path: String) -> Dictionary:
	var canonical := _canonical_ue_object_path(cue_path)
	return _audio_cue_by_path.get(canonical, {}) as Dictionary

func _authority_object_key(raw: String) -> String:
	var value := raw.strip_edges().replace("\\", "/")
	var quote := value.find("'")
	if quote >= 0 and value.ends_with("'"):
		value = value.substr(quote + 1, value.length() - quote - 2)
	if value.begins_with("Content/"):
		value = "/Game/" + value.substr(8)
	elif value.begins_with("Game/"):
		value = "/" + value
	return value.to_lower()


func _audio_component_position(raw_hierarchy: Variant) -> Vector3:
	if not (raw_hierarchy is Array):
		return Vector3.ZERO
	var hierarchy := raw_hierarchy as Array
	if hierarchy.is_empty():
		return Vector3.ZERO
	# The last hierarchy row is the root component. All three source audio
	# components have zero local offset, so the root relative location is the
	# exact actor-space placement serialized in the UMAP.
	var root_row := hierarchy[hierarchy.size() - 1] as Dictionary
	var loc := root_row.get("locationUEcm", {}) as Dictionary
	return Vector3(
		float(loc.get("X", 0.0)),
		float(loc.get("Y", 0.0)),
		float(loc.get("Z", 0.0))
	) * 0.01


func _cue_has_loop(cue: Dictionary) -> bool:
	for raw: Variant in cue.get("nodes", []):
		if not (raw is Dictionary):
			continue
		var node := raw as Dictionary
		if str(node.get("exportType", "")).to_lower().contains("loop"):
			return true
		for raw_property: Variant in node.get("properties", []):
			if not (raw_property is Dictionary):
				continue
			var property := raw_property as Dictionary
			var property_name := str(property.get("name", "")).to_lower()
			if property_name in ["blooping", "looping", "bloop"]:
				var value: Variant = property.get("value", false)
				if value is bool and bool(value):
					return true
				if str(value).to_lower() in ["true", "1"]:
					return true
	return false


func _set_audio_stream_loop(stream: AudioStream, enabled: bool) -> void:
	if not enabled or stream == null:
		return
	if stream is AudioStreamOggVorbis:
		(stream as AudioStreamOggVorbis).loop = true
	elif stream is AudioStreamWAV:
		(stream as AudioStreamWAV).loop_mode = AudioStreamWAV.LOOP_FORWARD


func _build_source_audio_runtime() -> bool:
	_source_audio_players.clear()
	_source_audio_component_key_by_id.clear()
	_source_audio_player_count = 0
	_source_audio_stream_count = 0

	var runtime_wave_by_key: Dictionary = {}
	for raw: Variant in _audio_runtime_report.get("audio", []):
		if not (raw is Dictionary):
			continue
		var row := raw as Dictionary
		var object_path := str(row.get("objectPath", ""))
		var runtime_file := str(row.get("runtimeFile", ""))
		if object_path.is_empty() or runtime_file.is_empty():
			continue
		runtime_wave_by_key[_authority_object_key(object_path)] = _source_path("audio").path_join(runtime_file)

	var cue_by_key: Dictionary = {}
	for raw: Variant in _audio_cues.get("cues", []):
		if raw is Dictionary:
			var cue := raw as Dictionary
			var cue_path := str(cue.get("objectPath", ""))
			if not cue_path.is_empty():
				cue_by_key[_authority_object_key(cue_path)] = cue

	for raw: Variant in _audio_scene.get("audioComponents", []):
		if not (raw is Dictionary):
			continue
		var row := raw as Dictionary
		var sound := row.get("sound", {}) as Dictionary
		var cue_path := str(sound.get("objectPath", ""))
		var cue_key := _authority_object_key(cue_path)
		if cue_key.is_empty() or not cue_by_key.has(cue_key):
			push_error("NACHT_FULL_MAP: source audio cue graph missing " + cue_path)
			return false

		var cue := cue_by_key[cue_key] as Dictionary
		var selection := _resolve_cue_wave_selection(cue, "", false, 0, false)
		if selection.is_empty():
			push_error(
				"NACHT_FULL_MAP: source UMAP cue graph could not resolve a wave "
				+ cue_path
			)
			return false

		var wave_path := str(selection.get("wavePath", ""))
		var wave_key := _authority_object_key(wave_path)
		if not runtime_wave_by_key.has(wave_key):
			push_error("NACHT_FULL_MAP: staged source wave missing " + wave_path)
			return false
		var runtime_path := str(runtime_wave_by_key[wave_key])
		if not ResourceLoader.exists(runtime_path):
			push_error("NACHT_FULL_MAP: Godot source audio resource missing " + runtime_path)
			return false
		var stream := load(runtime_path) as AudioStream
		if stream == null:
			push_error("NACHT_FULL_MAP: Godot failed to load source audio " + runtime_path)
			return false

		_set_audio_stream_loop(
			stream,
			bool(selection.get("looping", _cue_has_loop(cue)))
		)

		var player := AudioStreamPlayer3D.new()
		var actor_name := str(row.get("actorName", ""))
		var component_name := str(row.get("componentName", ""))
		player.name = actor_name + "_" + component_name + "_SourceAudio"
		player.position = _audio_component_position(row.get("hierarchy", []))
		player.stream = stream
		var props := row.get("properties", {}) as Dictionary
		var component_volume := maxf(0.0001, float(props.get("volumeMultiplier", 1.0)))
		var cue_volume := maxf(0.0001, float(cue.get("volumeMultiplier", 1.0)))
		player.volume_db = linear_to_db(component_volume * cue_volume)
		player.pitch_scale = maxf(
			0.01,
			float(props.get("pitchMultiplier", 1.0))
			* float(cue.get("pitchMultiplier", 1.0))
		)
		player.autoplay = false
		player.add_to_group("nacht_source_audio_runtime")
		player.set_meta("source_actor_name", actor_name)
		player.set_meta("source_component_name", component_name)
		player.set_meta("source_cue_path", cue_path)
		player.set_meta("source_wave_path", wave_path)
		player.set_meta("source_runtime_path", runtime_path)
		player.set_meta("source_provenance", str(sound.get("provenance", "")))
		_runtime_root.add_child(player)

		var key := actor_name + "." + component_name
		_source_audio_players[key] = player
		_source_audio_component_key_by_id[str(row.get("id", ""))] = key
		_source_audio_player_count += 1
		_source_audio_stream_count += 1

	if _source_audio_player_count != 3 or _source_audio_stream_count != 3:
		push_error(
			"NACHT_FULL_MAP: source audio runtime coverage mismatch "
			+ str(_source_audio_player_count) + "/3 players "
			+ str(_source_audio_stream_count) + "/3 streams"
		)
		return false

	print(
		"XZOGOT_NACHT_SOURCE_AUDIO_RUNTIME_GREEN players=",
		_source_audio_player_count,
		" streams=",
		_source_audio_stream_count
	)
	return true


func _refresh_source_audio_component_stream(player: AudioStreamPlayer3D) -> bool:
	var cue_path := str(player.get_meta("source_cue_path", ""))
	if cue_path.is_empty():
		return false
	var resolved := _source_audio_stream_for_asset(cue_path)
	if resolved.is_empty():
		return false
	var stream := resolved.get("stream") as AudioStream
	if stream == null:
		return false
	player.stream = stream
	player.set_meta("source_wave_path", str(resolved.get("wavePath", "")))
	player.set_meta("source_runtime_path", str(resolved.get("runtimePath", "")))
	return true


func play_source_audio_component(actor_name: String, component_name: String) -> bool:
	var key := actor_name + "." + component_name
	var player := _source_audio_players.get(key) as AudioStreamPlayer3D
	if player == null:
		return false
	if not _refresh_source_audio_component_stream(player):
		return false
	player.play()
	return true


func stop_source_audio_component(actor_name: String, component_name: String) -> bool:
	var key := actor_name + "." + component_name
	var player := _source_audio_players.get(key) as AudioStreamPlayer3D
	if player == null:
		return false
	player.stop()
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
