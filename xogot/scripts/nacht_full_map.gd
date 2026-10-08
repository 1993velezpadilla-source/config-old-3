extends Node3D

const XzielBenchmarkLoaderScript = preload("res://scripts/xziel_benchmark_loader.gd")
const SourceNavigationRuntimeScript = preload("res://scripts/source_navigation_runtime.gd")
const NachtParticleSource = preload("res://scripts/nacht_particle_source.gd")
const NachtCascadeRuntime = preload("res://scripts/nacht_cascade_runtime.gd")
const NachtCascadeVisualRuntime = preload("res://scripts/nacht_cascade_visual_runtime.gd")

## Nacht der Untoten Chronicles full-map source runtime.
##
## This scene is intentionally independent from the church and Nuketown.
## CI mounts a validated full-map authority payload under source_root.
## Geometry placement and actor/light identities are source-authored; nothing
## is procedurally substituted when an authority row is missing.

@export_dir var source_root: String = "res://assets/benchmarks/nacht_chronicles"
@export var build_world_collision: bool = true
@export var place_player_from_source_anchor: bool = true
# Stock Godot exponential fog is only a diagnostic fallback. Its density and
# influence semantics are not UE4.21 ExponentialHeightFog 1:1, so shipping
# Nacht keeps it disabled until the dedicated source shader is validated.
@export var enable_approximate_environment_fallback: bool = false

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
const PARTICLE_ACTIVATION_AUTHORITY_FILE := "nacht-particle-activation-authority.json"
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
var _particle_activation_authority: Dictionary = {}
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
var _source_particle_event_generation: Dictionary = {}
var _mesh_cache: Dictionary = {}

var _created_instances := 0
var _missing_meshes := 0
var _actor_anchor_count := 0
var _collision_count := 0
var _light_count := 0
var _source_audio_player_count := 0
var _source_audio_stream_count := 0
var _source_environment_visual_node_count := 0
var _source_particle_semantic_runtime_count := 0
var _source_particle_semantic_placement_count := 0
var _source_particle_visual_anchor_count := 0
var _source_particle_visual_node_count := 0
var _source_particle_visual_material_count := 0
var _source_particle_visual_unresolved_material_count := 0
var _source_particle_visual_emitter_count := 0
var _source_particle_visual_mounted_emitter_count := 0
var _source_particle_visual_resolved_mesh_count := 0
var _source_particle_visual_unresolved_mesh_count := 0
var _source_particle_visual_exact_anchor_count := 0
var _source_particle_mystery_descriptor: Dictionary = {}
var _source_particle_fire_descriptor: Dictionary = {}
var _source_particle_bonefire_descriptor: Dictionary = {}
var _source_particle_bonefire3_descriptor: Dictionary = {}
var _source_particle_pap_wheel_descriptor: Dictionary = {}
var _source_particle_mystery_fog_descriptor: Dictionary = {}
var _source_particle_mystery_inside_descriptor: Dictionary = {}
var _source_particle_fire_smoke_descriptor: Dictionary = {}
var _source_particle_pap_wheel_out_descriptor: Dictionary = {}
var _source_particle_electric_beam_descriptor: Dictionary = {}
var _source_particle_acid_ball_descriptor: Dictionary = {}
var _source_particle_sparks_small_descriptor: Dictionary = {}
var _source_particle_quad_smoke_descriptor: Dictionary = {}
var _source_particle_monster_descriptor: Dictionary = {}
var _source_particle_fire00_descriptor: Dictionary = {}
var _source_particle_fire14_descriptor: Dictionary = {}
var _source_environment_fog_runtime_ready := false
var _source_environment_reflection_runtime_ready := false
var _source_spawn_candidates: Array[Node3D] = []
var _source_zombie_spawn_candidates: Array[Node3D] = []
var _source_navigation_runtime: Node3D
var _source_navigation_ready := false
var _source_gameplay_ready := false

func _ready() -> void:
	get_tree().set_meta("active_map_id", "nacht_chronicles_full")
	get_tree().set_meta("nacht_full_map_ready", false)
	get_tree().set_meta("nacht_gameplay_ready", false)
	set_meta("nacht_gameplay_ready", false)
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
	_particle_activation_authority = _read_json(
		_source_path(PARTICLE_ACTIVATION_AUTHORITY_FILE)
	)
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

	if not _audit_source_particle_values():
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
	_begin_source_navigation()

	if not _build_source_particle_semantic_runtime():
		return

	if not _environment_runtime_authority.is_empty():
		if not _build_source_environment_runtime():
			return

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
	set_meta(
		"source_particle_activation_authority_ready",
		bool(_particle_activation_authority.get("ready", false))
	)
	set_meta(
		"source_particle_activation_action_count",
		int(_particle_activation_authority.get("normalizedActionCount", 0))
	)
	set_meta(
		"source_particle_activation_entry_point_count",
		int(_particle_activation_authority.get("entryPointCount", 0))
	)
	set_meta(
		"source_particle_activation_latent_delay_count",
		int(_particle_activation_authority.get("latentDelayCount", 0))
	)
	set_meta(
		"source_particle_activation_visibility_action_count",
		int(_particle_activation_authority.get("componentVisibilityActionCount", 0))
	)
	set_meta(
		"source_particle_activation_event_binding_count",
		int(_particle_activation_authority.get("eventActionBindingCount", 0))
	)
	set_meta(
		"source_particle_activation_cfg_linked_action_count",
		int(_particle_activation_authority.get("cfgLinkedActionCount", 0))
	)
	set_meta(
		"source_particle_activation_replay_safe_event_count",
		int(_particle_activation_authority.get("replaySafeEventCount", 0))
	)
	set_meta(
		"source_interaction_contract_count",
		int(_particle_activation_authority.get("sourceInteractionContractCount", 0))
	)
	set_meta("source_environment_component_count", int(_environment_scene.get("environmentComponentCount", -1)))
	set_meta("runtime_environment_authority_count", (_environment_scene.get("components", []) as Array).size())
	set_meta("runtime_environment_component_count", int(_environment_runtime_authority.get("componentCount", 0)))
	set_meta("runtime_environment_visual_node_count", _source_environment_visual_node_count)
	set_meta("source_environment_fog_runtime_ready", _source_environment_fog_runtime_ready)
	set_meta("source_environment_reflection_runtime_ready", _source_environment_reflection_runtime_ready)
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
	# Parsed authority, mounted visuals and exact reproduction are separate
	# states. The first visual layer now mounts real Godot render nodes from
	# source graph/material values, but exact remains false until every Cascade
	# module has a 1:1 execution path.
	var particle_visual_mounted := (
		_source_particle_visual_anchor_count == _source_particle_semantic_placement_count
		and _source_particle_visual_node_count >= _source_particle_visual_anchor_count
		and _source_particle_visual_mounted_emitter_count == _source_particle_visual_emitter_count
		and _source_particle_visual_unresolved_material_count == 0
		and _source_particle_visual_unresolved_mesh_count == 0
	)
	var particle_visual_exact := (
		particle_visual_mounted
		and _source_particle_visual_exact_anchor_count == _source_particle_semantic_placement_count
		and _source_particle_visual_unresolved_material_count == 0
	)
	set_meta("particle_visual_runtime_mounted", particle_visual_mounted)
	set_meta("particle_visual_runtime_ready", particle_visual_exact)
	set_meta("source_particle_visual_anchor_count", _source_particle_visual_anchor_count)
	set_meta("source_particle_visual_node_count", _source_particle_visual_node_count)
	set_meta("source_particle_visual_material_count", _source_particle_visual_material_count)
	set_meta(
		"source_particle_visual_unresolved_material_count",
		_source_particle_visual_unresolved_material_count
	)
	set_meta("source_particle_visual_emitter_count", _source_particle_visual_emitter_count)
	set_meta(
		"source_particle_visual_mounted_emitter_count",
		_source_particle_visual_mounted_emitter_count
	)
	set_meta(
		"source_particle_visual_resolved_mesh_count",
		_source_particle_visual_resolved_mesh_count
	)
	set_meta(
		"source_particle_visual_unresolved_mesh_count",
		_source_particle_visual_unresolved_mesh_count
	)
	set_meta(
		"source_particle_visual_exact_anchor_count",
		_source_particle_visual_exact_anchor_count
	)
	set_meta("source_particle_semantic_runtime_ready", _source_particle_semantic_runtime_count == 16 and _source_particle_semantic_placement_count == 29)
	set_meta("source_particle_semantic_runtime_count", _source_particle_semantic_runtime_count)
	set_meta("source_particle_semantic_placement_count", _source_particle_semantic_placement_count)
	set_meta("source_audio_runtime_ready", _source_audio_semantics_ready())
	var environment_mounted := (
		_source_environment_fog_runtime_ready
		and _source_environment_reflection_runtime_ready
		and _source_environment_visual_node_count == 2
	)
	set_meta("source_environment_runtime_mounted", environment_mounted)
	# Mounted source inputs are not the same thing as 1:1 UE4.21 visual parity.
	# Godot mobile has no direct FogMaxOpacity/StartDistance equivalent and its
	# ReflectionProbe influence volume is box-shaped rather than spherical.
	set_meta("source_environment_runtime_ready", false)
	set_meta("source_environment_visual_exact", false)
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
		" particle_visual_anchors=", _source_particle_visual_anchor_count,
		" particle_visual_nodes=", _source_particle_visual_node_count,
		" particle_visual_materials=", _source_particle_visual_material_count,
		" particle_visual_unresolved_materials=", _source_particle_visual_unresolved_material_count,
		" particle_visual_emitters=", _source_particle_visual_emitter_count,
		" particle_visual_mounted_emitters=", _source_particle_visual_mounted_emitter_count,
		" particle_visual_resolved_meshes=", _source_particle_visual_resolved_mesh_count,
		" particle_visual_unresolved_meshes=", _source_particle_visual_unresolved_mesh_count,
		" environment_authority=", get_meta("runtime_environment_authority_count"),
		" audio_authority=", get_meta("runtime_audio_authority_count"),
		" cues_authority=", get_meta("runtime_sound_cue_authority_count")
	)

func _audit_source_particle_values() -> bool:
	# Parse every source-authored Cascade node through the runtime decoder.
	# This is deliberately a boot gate: having the authority JSON on disk is
	# not enough. Godot must be able to unwrap the UE4.21 reflected values.
	var systems_raw: Variant = _particle_graphs.get("systems", [])
	if not (systems_raw is Array):
		push_error("NACHT_FULL_MAP: particle systems array missing for source decode")
		return false
	var systems := systems_raw as Array

	var expected_systems := int(_particle_graphs.get("particleSystemCount", -1))
	var expected_nodes := int(_particle_graphs.get("totalNodes", -1))
	var expected_references := int(_particle_graphs.get("totalReferences", -1))
	if expected_systems != 39 or expected_nodes != 1327 or expected_references != 643:
		push_error(
			"NACHT_FULL_MAP: Cascade authority totals changed systems=%d nodes=%d refs=%d"
			% [expected_systems, expected_nodes, expected_references]
		)
		return false

	var expected_distribution_nodes := 0
	var node_type_counts_raw: Variant = _particle_graphs.get("nodeTypeCounts", {})
	if node_type_counts_raw is Dictionary:
		var node_type_counts := node_type_counts_raw as Dictionary
		for raw_type: Variant in node_type_counts.keys():
			if str(raw_type).begins_with("Distribution"):
				expected_distribution_nodes += int(node_type_counts[raw_type])

	var decoded_systems := 0
	var decoded_nodes := 0
	var decoded_properties := 0
	var decoded_complex_values := 0
	var decoded_distribution_nodes := 0
	var counted_system_references := 0
	var counted_node_references := 0

	for raw_system: Variant in systems:
		if not (raw_system is Dictionary):
			push_error("NACHT_FULL_MAP: non-dictionary Cascade system row")
			return false
		var system := raw_system as Dictionary
		decoded_systems += 1

		var system_references_raw: Variant = system.get("references", [])
		if system_references_raw is Array:
			counted_system_references += (system_references_raw as Array).size()

		var nodes_raw: Variant = system.get("nodes", [])
		if not (nodes_raw is Array):
			push_error(
				"NACHT_FULL_MAP: Cascade system nodes missing " + str(system.get("objectPath", ""))
			)
			return false

		for raw_node: Variant in nodes_raw as Array:
			if not (raw_node is Dictionary):
				push_error("NACHT_FULL_MAP: non-dictionary Cascade node row")
				return false
			var node := raw_node as Dictionary
			decoded_nodes += 1
			var node_references_raw: Variant = node.get("references", [])
			if node_references_raw is Array:
				counted_node_references += (node_references_raw as Array).size()
			if str(node.get("exportType", "")).begins_with("Distribution"):
				decoded_distribution_nodes += 1

			var decoded := NachtParticleSource.properties(node)
			decoded_properties += decoded.size()
			for raw_key: Variant in decoded.keys():
				var decoded_value: Variant = decoded[raw_key]
				if decoded_value is Dictionary or decoded_value is Array:
					decoded_complex_values += 1

	if decoded_systems != expected_systems:
		push_error(
			"NACHT_FULL_MAP: Cascade decoded system coverage mismatch %d/%d"
			% [decoded_systems, expected_systems]
		)
		return false
	if decoded_nodes != expected_nodes:
		push_error(
			"NACHT_FULL_MAP: Cascade decoded node coverage mismatch %d/%d"
			% [decoded_nodes, expected_nodes]
		)
		return false
	# Authority totalReferences is defined by UEParticleGraphExtract as the
	# aggregate of every node's direct references. System.references is a
	# deduplicated system-level catalog (547 for this source) and therefore
	# must not be compared to the 643 node-reference authority total.
	if counted_node_references != expected_references:
		push_error(
			"NACHT_FULL_MAP: Cascade node reference coverage mismatch %d/%d"
			% [counted_node_references, expected_references]
		)
		return false
	if counted_system_references <= 0 or counted_system_references > counted_node_references:
		push_error(
			"NACHT_FULL_MAP: Cascade system reference catalog invalid %d node_refs=%d"
			% [counted_system_references, counted_node_references]
		)
		return false
	if decoded_distribution_nodes != expected_distribution_nodes:
		push_error(
			"NACHT_FULL_MAP: Cascade distribution coverage mismatch %d/%d"
			% [decoded_distribution_nodes, expected_distribution_nodes]
		)
		return false
	if decoded_properties <= 0 or decoded_complex_values <= 0:
		push_error(
			"NACHT_FULL_MAP: Cascade source-value decoder produced no reflected values"
		)
		return false

	set_meta("source_particle_decoder_ready", true)
	set_meta("source_particle_decoded_system_count", decoded_systems)
	set_meta("source_particle_decoded_node_count", decoded_nodes)
	set_meta("source_particle_decoded_reference_count", counted_node_references)
	set_meta("source_particle_system_reference_catalog_count", counted_system_references)
	set_meta("source_particle_decoded_property_count", decoded_properties)
	set_meta("source_particle_decoded_complex_value_count", decoded_complex_values)
	set_meta("source_particle_decoded_distribution_node_count", decoded_distribution_nodes)

	print(
		"XZOGOT_NACHT_CASCADE_SOURCE_DECODER_GREEN ",
		"systems=", decoded_systems,
		" nodes=", decoded_nodes,
		" refs=", counted_node_references,
		" system_ref_catalog=", counted_system_references,
		" properties=", decoded_properties,
		" complex_values=", decoded_complex_values,
		" distribution_nodes=", decoded_distribution_nodes
	)
	return true


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
	if _particle_activation_authority.is_empty():
		push_error("NACHT_FULL_MAP: particle activation bytecode authority missing")
		return false
	if not bool(_particle_activation_authority.get("ready", false)):
		push_error("NACHT_FULL_MAP: particle activation bytecode authority is not ready")
		return false
	if int(_particle_activation_authority.get("schemaVersion", 0)) != 2:
		push_error("NACHT_FULL_MAP: particle activation authority schema mismatch")
		return false
	if int(_particle_activation_authority.get("normalizedActionCount", 0)) != 17:
		push_error("NACHT_FULL_MAP: particle activation action count mismatch")
		return false
	if int(_particle_activation_authority.get("sourceInteractionContractCount", 0)) != 1:
		push_error("NACHT_FULL_MAP: source interaction contract count mismatch")
		return false
	var source_contracts_raw: Variant = _particle_activation_authority.get(
		"sourceInteractionContracts",
		[]
	)
	if not (source_contracts_raw is Array) or (source_contracts_raw as Array).size() != 1:
		push_error("NACHT_FULL_MAP: source interaction contract authority incomplete")
		return false
	var source_gumball_contract := (source_contracts_raw as Array)[0] as Dictionary
	var source_gumball_box := source_gumball_contract.get("interactBox", {}) as Dictionary
	var source_gumball_selection := source_gumball_contract.get("selectionRule", {}) as Dictionary
	var source_gumball_pool_raw: Variant = source_gumball_contract.get("gobblegumPool", [])
	var source_gumball_paths_raw: Variant = source_gumball_selection.get("paths", [])
	if (
		str(source_gumball_contract.get("fileName", "")) != "MachineGumball.uasset"
		or int(source_gumball_contract.get("baseCost", -1)) != 950
		or int(source_gumball_contract.get("fireSaleCost", -1)) != 10
		or str(source_gumball_contract.get("powerSwitchRule", "")) != "PowerSwitchFlags_empty_or_Powered"
		or not bool(source_gumball_contract.get("requiresNotInUse", false))
		or str(source_gumball_box.get("componentName", "")) != "Pavlov_InteractBox"
		or str(source_gumball_selection.get("sourceFunction", "")) != "KismetMathLibrary.RandomIntegerInRange"
		or int(source_gumball_selection.get("minInclusive", -1)) != 0
		or int(source_gumball_selection.get("maxInclusive", -1)) != 5
		or str(source_gumball_selection.get("poolProperty", "")) != "Gobblegum"
		or int(source_gumball_selection.get("poolSize", -1)) != 6
		or not (source_gumball_pool_raw is Array)
		or (source_gumball_pool_raw as Array).size() != 6
		or not (source_gumball_paths_raw is Array)
		or (source_gumball_paths_raw as Array).size() != 2
	):
		push_error("NACHT_FULL_MAP: source Gumball interaction contract mismatch")
		return false
	var source_gumball_pool := source_gumball_pool_raw as Array
	if (
		str(source_gumball_pool[0]) != "ammo"
		or str(source_gumball_pool[1]) != "Firesale1"
		or str(source_gumball_pool[2]) != "Instagum"
		or str(source_gumball_pool[3]) != "nuke"
		or str(source_gumball_pool[4]) != "DoublePointsDrop"
		or str(source_gumball_pool[5]) != "Weapon"
	):
		push_error("NACHT_FULL_MAP: source Gumball pool mismatch")
		return false
	var source_gumball_paths := source_gumball_paths_raw as Array
	if not (source_gumball_paths[0] is Dictionary) or not (source_gumball_paths[1] is Dictionary):
		push_error("NACHT_FULL_MAP: source Gumball selection paths malformed")
		return false
	var source_gumball_path0 := source_gumball_paths[0] as Dictionary
	var source_gumball_path1 := source_gumball_paths[1] as Dictionary
	if (
		int(source_gumball_path0.get("randomOffset", -1)) != 884
		or int(source_gumball_path0.get("arrayGetOffset", -1)) != 1259
		or int(source_gumball_path1.get("randomOffset", -1)) != 2131
		or int(source_gumball_path1.get("arrayGetOffset", -1)) != 2506
	):
		push_error("NACHT_FULL_MAP: source Gumball selection offset mismatch")
		return false
	if int(_particle_activation_authority.get("entryPointCount", 0)) != 81:
		push_error("NACHT_FULL_MAP: particle Blueprint entry-point count mismatch")
		return false
	if int(_particle_activation_authority.get("latentDelayCount", 0)) != 37:
		push_error("NACHT_FULL_MAP: particle latent Delay count mismatch")
		return false
	if int(_particle_activation_authority.get("componentVisibilityActionCount", 0)) != 65:
		push_error("NACHT_FULL_MAP: particle visibility action count mismatch")
		return false
	if int(_particle_activation_authority.get("eventActionBindingCount", 0)) != 5:
		push_error("NACHT_FULL_MAP: particle event binding count mismatch")
		return false
	if int(_particle_activation_authority.get("cfgLinkedActionCount", 0)) != 17:
		push_error("NACHT_FULL_MAP: particle CFG linked action count mismatch")
		return false
	if int(_particle_activation_authority.get("replaySafeEventCount", 0)) != 4:
		push_error("NACHT_FULL_MAP: particle replay-safe event count mismatch")
		return false
	var replay_events_raw: Variant = _particle_activation_authority.get(
		"replaySafeEvents",
		[]
	)
	if not (replay_events_raw is Array) or (replay_events_raw as Array).size() != 4:
		push_error("NACHT_FULL_MAP: particle replay-safe event authority incomplete")
		return false
	var activation_actions_raw: Variant = _particle_activation_authority.get(
		"normalizedActions",
		[]
	)
	if not (activation_actions_raw is Array) or (activation_actions_raw as Array).size() != 17:
		push_error("NACHT_FULL_MAP: particle activation action authority incomplete")
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
	var resolved_looping := bool(resolved.get("looping", false))
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
		if not resolved_looping:
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


func _source_transform_from_row_major(raw: Variant) -> Transform3D:
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


func _environment_component_position(raw_hierarchy: Variant) -> Vector3:
	if not (raw_hierarchy is Array):
		return Vector3.ZERO
	var hierarchy := raw_hierarchy as Array
	if hierarchy.size() != 1:
		push_error(
			"NACHT_FULL_MAP: environment hierarchy is not source-flat count="
			+ str(hierarchy.size())
		)
		return Vector3.INF
	var row := hierarchy[0] as Dictionary
	var loc := row.get("locationUEcm", {}) as Dictionary
	return Vector3(
		float(loc.get("X", 0.0)),
		float(loc.get("Y", 0.0)),
		float(loc.get("Z", 0.0))
	) * 0.01


func _find_world_environment(node: Node) -> WorldEnvironment:
	if node is WorldEnvironment:
		return node as WorldEnvironment
	for child: Node in node.get_children():
		var found := _find_world_environment(child)
		if found != null:
			return found
	return null


func _build_source_environment_runtime() -> bool:
	_source_environment_visual_node_count = 0
	_source_environment_fog_runtime_ready = false
	_source_environment_reflection_runtime_ready = false

	if not bool(_environment_runtime_authority.get("ready", false)):
		push_error("NACHT_FULL_MAP: environment runtime authority is not ready")
		return false
	if int(_environment_runtime_authority.get("componentCount", 0)) != 2:
		push_error("NACHT_FULL_MAP: environment runtime authority expected 2 components")
		return false

	var fog := _environment_runtime_authority.get("fog", {}) as Dictionary
	var reflection := (
		_environment_runtime_authority.get("reflectionCapture", {}) as Dictionary
	)
	if fog.is_empty() or reflection.is_empty():
		push_error("NACHT_FULL_MAP: source fog or reflection capture missing")
		return false

	var fog_position := _environment_component_position(fog.get("hierarchy", []))
	var reflection_position := _environment_component_position(
		reflection.get("hierarchy", [])
	)
	if not fog_position.is_finite() or not reflection_position.is_finite():
		return false

	var world := _find_world_environment(_benchmark_loader)
	if world == null:
		world = WorldEnvironment.new()
		world.name = "NachtSourceWorldEnvironment"
		world.environment = Environment.new()
		_runtime_root.add_child(world)
	if world.environment == null:
		world.environment = Environment.new()

	var environment := world.environment
	var fog_typed := fog.get("typed", {}) as Dictionary
	var fog_density := float(fog_typed.get("FogDensity", -1.0))
	var fog_height_falloff := float(fog_typed.get("FogHeightFalloff", -1.0))
	var fog_max_opacity := float(fog_typed.get("FogMaxOpacity", -1.0))
	var fog_start_distance_cm := float(fog_typed.get("StartDistance", -1.0))
	var volumetric_distance_cm := float(
		fog_typed.get("VolumetricFogDistance", -1.0)
	)
	if (
		fog_density < 0.0
		or fog_height_falloff < 0.0
		or fog_max_opacity < 0.0
		or fog_start_distance_cm < 0.0
		or volumetric_distance_cm < 0.0
	):
		push_error("NACHT_FULL_MAP: source fog typed authority incomplete")
		return false

	environment.fog_enabled = enable_approximate_environment_fallback
	environment.fog_mode = Environment.FOG_MODE_EXPONENTIAL
	environment.fog_density = fog_density
	environment.fog_height = fog_position.z
	environment.fog_height_density = fog_height_falloff
	world.set_meta("source_environment_component_type", "exponential_height_fog")
	world.set_meta("source_environment_path", str(fog.get("sourcePath", "")))
	world.set_meta("source_fog_density", fog_density)
	world.set_meta(
		"approximate_fog_fallback_enabled",
		enable_approximate_environment_fallback
	)
	world.set_meta("source_fog_height_falloff", fog_height_falloff)
	world.set_meta("source_fog_max_opacity", fog_max_opacity)
	world.set_meta("source_fog_start_distance_m", fog_start_distance_cm * 0.01)
	world.set_meta(
		"source_volumetric_fog_distance_m",
		volumetric_distance_cm * 0.01
	)
	world.set_meta("source_fog_location_ue_cm", fog_position * 100.0)
	world.set_meta(
		"source_fog_semantic_note",
		"Godot exponential fog directly mounts density/height/falloff; UE "
		+ "FogMaxOpacity, StartDistance and VolumetricFogDistance are preserved "
		+ "as source authority because Godot 4 mobile/compatibility has no exact "
		+ "UE4.21 ExponentialHeightFog equivalent for those controls."
	)
	world.add_to_group("nacht_source_environment_runtime")
	_source_environment_visual_node_count += 1
	_source_environment_fog_runtime_ready = true

	var reflection_typed := reflection.get("typed", {}) as Dictionary
	var radius_cm := float(reflection_typed.get("InfluenceRadius", -1.0))
	if radius_cm <= 0.0:
		push_error("NACHT_FULL_MAP: source reflection influence radius invalid")
		return false
	var radius_m := radius_cm * 0.01
	var probe := ReflectionProbe.new()
	probe.name = "NachtSourceSphereReflectionCapture"
	probe.position = reflection_position
	probe.size = Vector3.ONE * radius_m * 2.0
	probe.set_meta("source_environment_component_type", "reflection_capture")
	probe.set_meta("source_environment_path", str(reflection.get("sourcePath", "")))
	probe.set_meta("source_shape", "sphere")
	probe.set_meta("source_influence_radius_m", radius_m)
	probe.set_meta("source_location_ue_cm", reflection_position * 100.0)
	probe.set_meta(
		"runtime_shape_note",
		"Godot ReflectionProbe influence is box-shaped; source UE4.21 authority "
		+ "is spherical. Position and diameter are mounted exactly and the shape "
		+ "difference remains explicitly flagged rather than hidden."
	)
	probe.add_to_group("nacht_source_environment_runtime")
	_runtime_root.add_child(probe)
	_source_environment_visual_node_count += 1
	_source_environment_reflection_runtime_ready = true

	print(
		"XZOGOT_NACHT_SOURCE_ENVIRONMENT_RUNTIME_GREEN ",
		"fog_density=", fog_density,
		" fog_height_m=", fog_position.z,
		" fog_height_falloff=", fog_height_falloff,
		" fog_max_opacity=", fog_max_opacity,
		" start_distance_m=", fog_start_distance_cm * 0.01,
		" volumetric_distance_m=", volumetric_distance_cm * 0.01,
		" reflection_radius_m=", radius_m,
		" nodes=", _source_environment_visual_node_count
	)
	return true


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
	if stream == null:
		return
	if stream is AudioStreamOggVorbis:
		(stream as AudioStreamOggVorbis).loop = enabled
	elif stream is AudioStreamWAV:
		(stream as AudioStreamWAV).loop_mode = (
			AudioStreamWAV.LOOP_FORWARD
			if enabled
			else AudioStreamWAV.LOOP_DISABLED
		)



func set_source_particle_component_active(
	actor_name: String,
	component_name: String,
	active: bool,
	reset: bool = false
) -> Dictionary:
	var matched_anchors := 0
	var visual_nodes := 0
	var particle_emitters := 0
	var beam_nodes := 0

	for raw_anchor: Node in get_tree().get_nodes_in_group(
		"nacht_source_particle_semantic"
	):
		if not (raw_anchor is Node3D):
			continue
		var anchor := raw_anchor as Node3D
		if str(anchor.get_meta("source_actor_name", "")) != actor_name:
			continue
		if str(anchor.get_meta("source_component_name", "")) != component_name:
			continue
		var report := NachtCascadeVisualRuntime.set_anchor_active(
			anchor,
			active,
			reset
		)
		if not bool(report.get("matched", false)):
			continue
		matched_anchors += 1
		visual_nodes += int(report.get("visualNodeCount", 0))
		particle_emitters += int(report.get("particleEmitterCount", 0))
		beam_nodes += int(report.get("beamNodeCount", 0))

	var ready := matched_anchors > 0
	var result := {
		"ready": ready,
		"actorName": actor_name,
		"componentName": component_name,
		"active": active,
		"reset": reset,
		"matchedAnchorCount": matched_anchors,
		"visualNodeCount": visual_nodes,
		"particleEmitterCount": particle_emitters,
		"beamNodeCount": beam_nodes,
	}
	if ready:
		print(
			"XZOGOT_NACHT_PARTICLE_COMPONENT_ACTIVE ",
			"actor=", actor_name,
			" component=", component_name,
			" active=", active,
			" reset=", reset,
			" anchors=", matched_anchors,
			" particles=", particle_emitters,
			" beams=", beam_nodes
		)
	return result


func set_source_actor_particles_active(
	actor_name: String,
	active: bool,
	reset: bool = false
) -> Dictionary:
	var matched_anchors := 0
	var visual_nodes := 0
	var particle_emitters := 0
	var beam_nodes := 0

	for raw_anchor: Node in get_tree().get_nodes_in_group(
		"nacht_source_particle_semantic"
	):
		if not (raw_anchor is Node3D):
			continue
		var anchor := raw_anchor as Node3D
		if str(anchor.get_meta("source_actor_name", "")) != actor_name:
			continue
		var report := NachtCascadeVisualRuntime.set_anchor_active(
			anchor,
			active,
			reset
		)
		if not bool(report.get("matched", false)):
			continue
		matched_anchors += 1
		visual_nodes += int(report.get("visualNodeCount", 0))
		particle_emitters += int(report.get("particleEmitterCount", 0))
		beam_nodes += int(report.get("beamNodeCount", 0))

	var ready := matched_anchors > 0
	var result := {
		"ready": ready,
		"actorName": actor_name,
		"active": active,
		"reset": reset,
		"matchedAnchorCount": matched_anchors,
		"visualNodeCount": visual_nodes,
		"particleEmitterCount": particle_emitters,
		"beamNodeCount": beam_nodes,
	}
	if ready:
		print(
			"XZOGOT_NACHT_PARTICLE_ACTOR_ACTIVE ",
			"actor=", actor_name,
			" active=", active,
			" reset=", reset,
			" anchors=", matched_anchors,
			" particles=", particle_emitters,
			" beams=", beam_nodes
		)
	return result


func _source_particle_blueprint_file_for_actor(actor_name: String) -> String:
	for raw_anchor: Node in get_tree().get_nodes_in_group(
		"nacht_source_particle_semantic"
	):
		if not (raw_anchor is Node3D):
			continue
		var anchor := raw_anchor as Node3D
		if str(anchor.get_meta("source_actor_name", "")) != actor_name:
			continue
		var owner_type := str(anchor.get_meta("source_owner_export_type", ""))
		if owner_type.ends_with("_C") and owner_type.length() > 2:
			owner_type = owner_type.substr(0, owner_type.length() - 2)
		if not owner_type.is_empty():
			return owner_type + ".uasset"
	return ""


func apply_source_particle_activation_action(
	actor_name: String,
	action: Dictionary
) -> Dictionary:
	var target_mode := str(action.get("targetMode", ""))
	var active := bool(action.get("active", false))
	var reset := bool(action.get("reset", false))
	var report: Dictionary = {}
	if target_mode == "named_component":
		report = set_source_particle_component_active(
			actor_name,
			str(action.get("componentName", "")),
			active,
			reset
		)
	elif target_mode == "all_particle_components":
		report = set_source_actor_particles_active(
			actor_name,
			active,
			reset
		)
	else:
		return {
			"ready": false,
			"error": "unsupported targetMode " + target_mode,
			"actorName": actor_name,
		}
	report["sourceAction"] = action.duplicate(true)
	return report


func _source_interaction_contract_for_blueprint(
	blueprint_file: String
) -> Dictionary:
	var raw_contracts: Variant = _particle_activation_authority.get(
		"sourceInteractionContracts",
		[]
	)
	if not (raw_contracts is Array):
		return {}
	for raw_contract: Variant in raw_contracts as Array:
		if not (raw_contract is Dictionary):
			continue
		var contract := raw_contract as Dictionary
		if str(contract.get("fileName", "")) == blueprint_file:
			return contract
	return {}


func describe_source_gumball_interaction(actor_name: String) -> Dictionary:
	var blueprint_file := _source_particle_blueprint_file_for_actor(actor_name)
	if blueprint_file != "MachineGumball.uasset":
		return {
			"ready": false,
			"error": "actor is not source MachineGumball",
			"actorName": actor_name,
		}
	var contract := _source_interaction_contract_for_blueprint(blueprint_file)
	if contract.is_empty():
		return {
			"ready": false,
			"error": "source interaction contract missing",
			"actorName": actor_name,
		}
	return {
		"ready": true,
		"actorName": actor_name,
		"blueprintFile": blueprint_file,
		"contract": contract.duplicate(true),
	}


func select_source_gumball_by_index(
	actor_name: String,
	selection_index: int
) -> Dictionary:
	var desc := describe_source_gumball_interaction(actor_name)
	if not bool(desc.get("ready", false)):
		return desc
	var contract := desc.get("contract", {}) as Dictionary
	var selection := contract.get("selectionRule", {}) as Dictionary
	var pool_raw: Variant = contract.get("gobblegumPool", [])
	if (
		str(selection.get("sourceFunction", "")) != "KismetMathLibrary.RandomIntegerInRange"
		or int(selection.get("minInclusive", -1)) != 0
		or int(selection.get("maxInclusive", -1)) != 5
		or str(selection.get("poolProperty", "")) != "Gobblegum"
		or int(selection.get("poolSize", -1)) != 6
		or not (pool_raw is Array)
		or (pool_raw as Array).size() != 6
	):
		return {
			"ready": false,
			"error": "source Gumball selection authority mismatch",
			"actorName": actor_name,
		}
	var min_index := int(selection.get("minInclusive", 0))
	var max_index := int(selection.get("maxInclusive", 5))
	if selection_index < min_index or selection_index > max_index:
		return {
			"ready": false,
			"error": "source Gumball selection index out of range",
			"actorName": actor_name,
			"selectedIndex": selection_index,
			"minInclusive": min_index,
			"maxInclusive": max_index,
		}
	var pool := pool_raw as Array
	return {
		"ready": true,
		"actorName": actor_name,
		"blueprintFile": str(desc.get("blueprintFile", "")),
		"selectedIndex": selection_index,
		"selectedId": str(pool[selection_index]),
		"sourceFunction": str(selection.get("sourceFunction", "")),
		"minInclusive": min_index,
		"maxInclusive": max_index,
		"poolProperty": str(selection.get("poolProperty", "")),
		"poolSize": int(selection.get("poolSize", 0)),
		"paths": (
			(selection.get("paths", []) as Array).duplicate(true)
			if selection.get("paths", []) is Array
			else []
		),
	}


func roll_source_gumball_selection(actor_name: String) -> Dictionary:
	var desc := describe_source_gumball_interaction(actor_name)
	if not bool(desc.get("ready", false)):
		return desc
	var contract := desc.get("contract", {}) as Dictionary
	var selection := contract.get("selectionRule", {}) as Dictionary
	var min_index := int(selection.get("minInclusive", -1))
	var max_index := int(selection.get("maxInclusive", -1))
	if (
		str(selection.get("sourceFunction", "")) != "KismetMathLibrary.RandomIntegerInRange"
		or min_index != 0
		or max_index != 5
	):
		return {
			"ready": false,
			"error": "source Gumball RNG authority mismatch",
			"actorName": actor_name,
		}
	var selection_index: int = randi_range(min_index, max_index)
	var result := select_source_gumball_by_index(actor_name, selection_index)
	result["rolled"] = true
	return result


func evaluate_source_gumball_interaction(
	actor_name: String,
	player_cash: int,
	fire_sale_active: bool,
	power_switch_flags_empty: bool,
	powered: bool,
	in_use: bool,
	player_tags: Array
) -> Dictionary:
	var desc := describe_source_gumball_interaction(actor_name)
	if not bool(desc.get("ready", false)):
		return desc
	var contract := desc.get("contract", {}) as Dictionary
	var selected_cost := (
		int(contract.get("fireSaleCost", 10))
		if fire_sale_active
		else int(contract.get("baseCost", 950))
	)
	var deny_tags_raw: Variant = contract.get("denyPlayerTags", [])
	var deny_tags: Array[String] = []
	if deny_tags_raw is Array:
		for raw_tag: Variant in deny_tags_raw as Array:
			deny_tags.append(str(raw_tag))
	var blocked_tag := ""
	for raw_tag: Variant in player_tags:
		var tag := str(raw_tag)
		if tag in deny_tags:
			blocked_tag = tag
			break
	var power_ok := power_switch_flags_empty or powered
	var not_in_use := not in_use
	var cash_ok := player_cash >= selected_cost
	var allowed := power_ok and not_in_use and cash_ok and blocked_tag.is_empty()
	var reason := "ok"
	if not power_ok:
		reason = "power"
	elif not not_in_use:
		reason = "in_use"
	elif not blocked_tag.is_empty():
		reason = "player_tag:" + blocked_tag
	elif not cash_ok:
		reason = "cash"
	return {
		"ready": true,
		"allowed": allowed,
		"reason": reason,
		"actorName": actor_name,
		"selectedCost": selected_cost,
		"cashBefore": player_cash,
		"cashAfter": player_cash - selected_cost if allowed else player_cash,
		"fireSaleActive": fire_sale_active,
		"powerOk": power_ok,
		"notInUse": not_in_use,
		"cashOk": cash_ok,
		"blockedTag": blocked_tag,
		"serverEntryOffset": int(contract.get("serverEntryOffset", -1)),
		"serverInteractFunction": str(contract.get("serverInteractFunction", "")),
		"successSequence": (
			(contract.get("successSequence", []) as Array).duplicate(true)
			if contract.get("successSequence", []) is Array
			else []
		),
		"gobblegumPool": (
			(contract.get("gobblegumPool", []) as Array).duplicate(true)
			if contract.get("gobblegumPool", []) is Array
			else []
		),
		"selectionRule": (
			(contract.get("selectionRule", {}) as Dictionary).duplicate(true)
			if contract.get("selectionRule", {}) is Dictionary
			else {}
		),
		"interactBox": (
			(contract.get("interactBox", {}) as Dictionary).duplicate(true)
			if contract.get("interactBox", {}) is Dictionary
			else {}
		),
	}


func _source_particle_activation_action_for_offset(
	blueprint_file: String,
	start_offset: int
) -> Dictionary:
	var raw_actions: Variant = _particle_activation_authority.get(
		"normalizedActions",
		[]
	)
	if not (raw_actions is Array):
		return {}
	for raw_action: Variant in raw_actions as Array:
		if not (raw_action is Dictionary):
			continue
		var action := raw_action as Dictionary
		if str(action.get("fileName", "")) != blueprint_file:
			continue
		if int(action.get("startOffset", -1)) == start_offset:
			return action
	return {}


func _source_particle_replay_event(
	blueprint_file: String,
	event_name: String
) -> Dictionary:
	var raw_events: Variant = _particle_activation_authority.get(
		"replaySafeEvents",
		[]
	)
	if not (raw_events is Array):
		return {}
	for raw_event: Variant in raw_events as Array:
		if not (raw_event is Dictionary):
			continue
		var event := raw_event as Dictionary
		if str(event.get("fileName", "")) != blueprint_file:
			continue
		if str(event.get("eventFunction", "")) == event_name:
			return event
	return {}


func describe_source_blueprint_particle_event(
	actor_name: String,
	event_name: String
) -> Dictionary:
	var blueprint_file := _source_particle_blueprint_file_for_actor(actor_name)
	if blueprint_file.is_empty():
		return {
			"ready": false,
			"error": "source Blueprint owner missing",
			"actorName": actor_name,
			"eventFunction": event_name,
		}
	var event := _source_particle_replay_event(
		blueprint_file,
		event_name
	)
	if event.is_empty():
		return {
			"ready": false,
			"error": "event is not replay-safe",
			"actorName": actor_name,
			"blueprintFile": blueprint_file,
			"eventFunction": event_name,
		}
	var timeline_raw: Variant = event.get("timeline", [])
	if not (timeline_raw is Array) or (timeline_raw as Array).is_empty():
		return {
			"ready": false,
			"error": "replay-safe timeline missing",
			"actorName": actor_name,
			"blueprintFile": blueprint_file,
			"eventFunction": event_name,
		}
	return {
		"ready": true,
		"actorName": actor_name,
		"blueprintFile": blueprint_file,
		"eventFunction": event_name,
		"entryOffset": int(event.get("entryOffset", -1)),
		"timeline": (timeline_raw as Array).duplicate(true),
		"proof": str(event.get("proof", "")),
	}


func _apply_source_blueprint_particle_event_step(
	actor_name: String,
	blueprint_file: String,
	event_name: String,
	step: Dictionary
) -> Dictionary:
	var raw_offsets: Variant = step.get("actionStartOffsets", [])
	if not (raw_offsets is Array) or (raw_offsets as Array).is_empty():
		return {
			"ready": false,
			"error": "event step has no action offsets",
			"actorName": actor_name,
			"eventFunction": event_name,
		}

	var matched_anchors := 0
	var reports: Array[Dictionary] = []
	var all_ready := true
	for raw_offset: Variant in raw_offsets as Array:
		var action := _source_particle_activation_action_for_offset(
			blueprint_file,
			int(raw_offset)
		)
		if action.is_empty():
			all_ready = false
			reports.append({
				"ready": false,
				"error": "source action offset missing",
				"startOffset": int(raw_offset),
			})
			continue
		var report := apply_source_particle_activation_action(
			actor_name,
			action
		)
		reports.append(report)
		if not bool(report.get("ready", false)):
			all_ready = false
		matched_anchors += int(
			report.get("matchedAnchorCount", 0)
		)

	var result := {
		"ready": all_ready,
		"actorName": actor_name,
		"blueprintFile": blueprint_file,
		"eventFunction": event_name,
		"atSeconds": float(step.get("atSeconds", 0.0)),
		"actionCount": (raw_offsets as Array).size(),
		"matchedAnchorCount": matched_anchors,
		"reports": reports,
	}
	if all_ready:
		print(
			"XZOGOT_NACHT_PARTICLE_EVENT_STEP_GREEN ",
			"actor=", actor_name,
			" event=", event_name,
			" at=", result["atSeconds"],
			" actions=", result["actionCount"],
			" anchors=", matched_anchors
		)
	return result


func _source_particle_event_key(
	actor_name: String,
	event_name: String
) -> String:
	return actor_name + "::" + event_name


func _run_source_blueprint_particle_event_timeline(
	actor_name: String,
	blueprint_file: String,
	event_name: String,
	generation: int,
	steps: Array
) -> void:
	var key := _source_particle_event_key(
		actor_name,
		event_name
	)
	var elapsed := 0.0
	for raw_step: Variant in steps:
		if not (raw_step is Dictionary):
			continue
		var step := raw_step as Dictionary
		var at_seconds: float = maxf(
			0.0,
			float(step.get("atSeconds", 0.0))
		)
		var delay: float = maxf(0.0, at_seconds - elapsed)
		if delay > 0.0:
			await get_tree().create_timer(delay).timeout
		if int(_source_particle_event_generation.get(key, 0)) != generation:
			return
		var report := _apply_source_blueprint_particle_event_step(
			actor_name,
			blueprint_file,
			event_name,
			step
		)
		if not bool(report.get("ready", false)):
			push_error(
				"NACHT_FULL_MAP: source particle event step failed "
				+ str(report)
			)
			return
		elapsed = at_seconds
	print(
		"XZOGOT_NACHT_PARTICLE_EVENT_TIMELINE_GREEN ",
		"actor=", actor_name,
		" event=", event_name,
		" generation=", generation,
		" steps=", steps.size()
	)


func cancel_source_blueprint_particle_event(
	actor_name: String,
	event_name: String
) -> void:
	var key := _source_particle_event_key(
		actor_name,
		event_name
	)
	_source_particle_event_generation[key] = int(
		_source_particle_event_generation.get(key, 0)
	) + 1


func trigger_source_blueprint_particle_event(
	actor_name: String,
	event_name: String
) -> Dictionary:
	var description := describe_source_blueprint_particle_event(
		actor_name,
		event_name
	)
	if not bool(description.get("ready", false)):
		return description

	var blueprint_file := str(
		description.get("blueprintFile", "")
	)
	var timeline_raw: Variant = description.get(
		"timeline",
		[]
	)
	var timeline := timeline_raw as Array
	timeline.sort_custom(
		func(a: Variant, b: Variant) -> bool:
			if not (a is Dictionary) or not (b is Dictionary):
				return false
			return float(
				(a as Dictionary).get("atSeconds", 0.0)
			) < float(
				(b as Dictionary).get("atSeconds", 0.0)
			)
	)

	var key := _source_particle_event_key(
		actor_name,
		event_name
	)
	var generation := int(
		_source_particle_event_generation.get(key, 0)
	) + 1
	_source_particle_event_generation[key] = generation

	var immediate_reports: Array[Dictionary] = []
	var delayed_steps: Array = []
	var matched_anchors := 0
	var all_ready := true
	for raw_step: Variant in timeline:
		if not (raw_step is Dictionary):
			continue
		var step := raw_step as Dictionary
		if float(step.get("atSeconds", 0.0)) <= 0.0:
			var report := _apply_source_blueprint_particle_event_step(
				actor_name,
				blueprint_file,
				event_name,
				step
			)
			immediate_reports.append(report)
			if not bool(report.get("ready", false)):
				all_ready = false
			matched_anchors += int(
				report.get("matchedAnchorCount", 0)
			)
		else:
			delayed_steps.append(step.duplicate(true))

	if not delayed_steps.is_empty():
		call_deferred(
			"_run_source_blueprint_particle_event_timeline",
			actor_name,
			blueprint_file,
			event_name,
			generation,
			delayed_steps
		)

	var result := {
		"ready": all_ready,
		"actorName": actor_name,
		"blueprintFile": blueprint_file,
		"eventFunction": event_name,
		"generation": generation,
		"timelineStepCount": timeline.size(),
		"immediateStepCount": immediate_reports.size(),
		"scheduledStepCount": delayed_steps.size(),
		"matchedAnchorCount": matched_anchors,
		"immediateReports": immediate_reports,
	}
	if all_ready:
		print(
			"XZOGOT_NACHT_PARTICLE_EVENT_TRIGGER_GREEN ",
			"actor=", actor_name,
			" event=", event_name,
			" immediate=", immediate_reports.size(),
			" scheduled=", delayed_steps.size(),
			" anchors=", matched_anchors
		)
	return result


func apply_source_particle_activation_window(
	actor_name: String,
	function_name: String,
	start_offset: int,
	end_offset: int
) -> Dictionary:
	var blueprint_file := _source_particle_blueprint_file_for_actor(actor_name)
	if blueprint_file.is_empty():
		return {
			"ready": false,
			"error": "source Blueprint owner missing",
			"actorName": actor_name,
		}
	var raw_actions: Variant = _particle_activation_authority.get(
		"normalizedActions",
		[]
	)
	if not (raw_actions is Array):
		return {
			"ready": false,
			"error": "particle activation actions missing",
			"actorName": actor_name,
		}

	var actions: Array[Dictionary] = []
	for raw_action: Variant in raw_actions as Array:
		if not (raw_action is Dictionary):
			continue
		var action := raw_action as Dictionary
		if str(action.get("fileName", "")) != blueprint_file:
			continue
		if str(action.get("function", "")) != function_name:
			continue
		var action_start := int(action.get("startOffset", -1))
		var action_end := int(action.get("endOffset", -1))
		if action_start < start_offset or action_end > end_offset:
			continue
		actions.append(action)

	actions.sort_custom(
		func(a: Dictionary, b: Dictionary) -> bool:
			return int(a.get("startOffset", 0)) < int(b.get("startOffset", 0))
	)

	var matched_anchors := 0
	var all_ready := not actions.is_empty()
	var reports: Array[Dictionary] = []
	for action: Dictionary in actions:
		var report := apply_source_particle_activation_action(actor_name, action)
		reports.append(report)
		if not bool(report.get("ready", false)):
			all_ready = false
		matched_anchors += int(report.get("matchedAnchorCount", 0))

	var result := {
		"ready": all_ready,
		"actorName": actor_name,
		"blueprintFile": blueprint_file,
		"function": function_name,
		"startOffset": start_offset,
		"endOffset": end_offset,
		"actionCount": actions.size(),
		"matchedAnchorCount": matched_anchors,
		"reports": reports,
	}
	if all_ready:
		print(
			"XZOGOT_NACHT_PARTICLE_BYTECODE_WINDOW_GREEN ",
			"actor=", actor_name,
			" blueprint=", blueprint_file,
			" function=", function_name,
			" offsets=", start_offset, "..", end_offset,
			" actions=", actions.size(),
			" anchors=", matched_anchors
		)
	return result



func _mount_source_particle_semantic_anchors(
	descriptor: Dictionary,
	expected_count: int,
	label: String
) -> bool:
	var placements := NachtCascadeRuntime.placements_for_system(
		_particle_runtime_authority,
		str(descriptor.get("systemPath", ""))
	)
	if placements.size() != expected_count:
		push_error(
			"NACHT_FULL_MAP: " + label + " source placement coverage mismatch "
			+ str(placements.size()) + "/" + str(expected_count)
		)
		return false

	for raw: Dictionary in placements:
		var hierarchy_raw: Variant = raw.get("hierarchy", [])
		if not (hierarchy_raw is Array):
			push_error("NACHT_FULL_MAP: particle hierarchy missing")
			return false
		var hierarchy := hierarchy_raw as Array
		if hierarchy.is_empty():
			push_error("NACHT_FULL_MAP: particle hierarchy empty")
			return false
		var root_raw: Variant = hierarchy[hierarchy.size() - 1]
		if not (root_raw is Dictionary):
			push_error("NACHT_FULL_MAP: particle root hierarchy row invalid")
			return false
		var root := root_raw as Dictionary
		var matrix_raw: Variant = raw.get("matrixRowMajor", [])
		if not (matrix_raw is Array) or (matrix_raw as Array).size() != 16:
			push_error("NACHT_FULL_MAP: particle source world matrix missing")
			return false

		var anchor := Node3D.new()
		anchor.name = "NachtCascadeSemantic_" + str(raw.get("id", "unknown"))
		anchor.transform = _source_transform_from_row_major(matrix_raw)
		anchor.add_to_group("nacht_source_particle_semantic")
		anchor.set_meta("source_particle_id", str(raw.get("id", "")))
		anchor.set_meta("source_actor_name", str(raw.get("actorName", "")))
		anchor.set_meta("source_component_name", str(raw.get("componentName", "")))
		anchor.set_meta("source_component_path", str(raw.get("sourcePath", "")))
		anchor.set_meta(
			"source_owner_export_type",
			str(raw.get("ownerExportType", ""))
		)
		anchor.set_meta(
			"source_owner_class_path",
			str(raw.get("ownerClassPath", ""))
		)
		anchor.set_meta(
			"source_particle_system_path",
			str(descriptor.get("systemPath", ""))
		)
		anchor.set_meta(
			"source_particle_material_path",
			str(descriptor.get("materialPath", ""))
		)
		anchor.set_meta("source_root_rotation_ue", root.get("rotationUE", {}))
		anchor.set_meta("source_root_scale", root.get("scale", {}))
		anchor.set_meta("source_particle_world_matrix_row_major", matrix_raw)
		anchor.set_meta("source_particle_hierarchy_depth", hierarchy.size())
		_runtime_root.add_child(anchor)

		var visual_report := NachtCascadeVisualRuntime.mount_anchor(
			anchor,
			descriptor,
			_particle_graphs,
			_benchmark_loader,
			raw
		)
		if bool(visual_report.get("mounted", false)):
			_source_particle_visual_anchor_count += 1
		if bool(visual_report.get("exact", false)):
			_source_particle_visual_exact_anchor_count += 1
		_source_particle_visual_node_count += int(
			visual_report.get("visualNodeCount", 0)
		)
		_source_particle_visual_material_count += int(
			visual_report.get("resolvedMaterialCount", 0)
		)
		_source_particle_visual_unresolved_material_count += int(
			visual_report.get("unresolvedMaterialCount", 0)
		)
		_source_particle_visual_emitter_count += int(
			visual_report.get("emitterCount", 0)
		)
		_source_particle_visual_mounted_emitter_count += int(
			visual_report.get("mountedEmitterCount", 0)
		)
		_source_particle_visual_resolved_mesh_count += int(
			visual_report.get("resolvedMeshCount", 0)
		)
		_source_particle_visual_unresolved_mesh_count += int(
			visual_report.get("unresolvedMeshCount", 0)
		)
		anchor.set_meta(
			"source_particle_visual_report",
			visual_report.duplicate(true)
		)
		_source_particle_semantic_placement_count += 1
	return true


func _build_source_particle_semantic_runtime() -> bool:
	_source_particle_semantic_runtime_count = 0
	_source_particle_semantic_placement_count = 0
	_source_particle_visual_anchor_count = 0
	_source_particle_visual_node_count = 0
	_source_particle_visual_material_count = 0
	_source_particle_visual_unresolved_material_count = 0
	_source_particle_visual_emitter_count = 0
	_source_particle_visual_mounted_emitter_count = 0
	_source_particle_visual_resolved_mesh_count = 0
	_source_particle_visual_unresolved_mesh_count = 0
	_source_particle_visual_exact_anchor_count = 0

	_source_particle_mystery_descriptor = NachtCascadeRuntime.mystery_vertical_descriptor(_particle_graphs)
	if not bool(_source_particle_mystery_descriptor.get("ready", false)):
		push_error(
			"NACHT_FULL_MAP: mystery vertical Cascade semantics unresolved "
			+ str(_source_particle_mystery_descriptor.get("error", "unknown"))
		)
		return false
	if not _mount_source_particle_semantic_anchors(
		_source_particle_mystery_descriptor,
		3,
		"mystery vertical"
	):
		return false
	_source_particle_semantic_runtime_count += 1

	_source_particle_fire_descriptor = NachtCascadeRuntime.big_fire_forward_descriptor(_particle_graphs)
	if not bool(_source_particle_fire_descriptor.get("ready", false)):
		push_error(
			"NACHT_FULL_MAP: big fire Cascade semantics unresolved "
			+ str(_source_particle_fire_descriptor.get("error", "unknown"))
		)
		return false
	if not _mount_source_particle_semantic_anchors(
		_source_particle_fire_descriptor,
		2,
		"big fire forward"
	):
		return false
	_source_particle_semantic_runtime_count += 1

	_source_particle_bonefire_descriptor = NachtCascadeRuntime.bone_fire_2b_descriptor(_particle_graphs)
	if not bool(_source_particle_bonefire_descriptor.get("ready", false)):
		push_error(
			"NACHT_FULL_MAP: bone fire 2B Cascade semantics unresolved "
			+ str(_source_particle_bonefire_descriptor.get("error", "unknown"))
		)
		return false
	if not _mount_source_particle_semantic_anchors(
		_source_particle_bonefire_descriptor,
		1,
		"bone fire 2B"
	):
		return false
	_source_particle_semantic_runtime_count += 1

	_source_particle_bonefire3_descriptor = NachtCascadeRuntime.bone_fire_3_descriptor(_particle_graphs)
	if not bool(_source_particle_bonefire3_descriptor.get("ready", false)):
		push_error(
			"NACHT_FULL_MAP: bone fire 3 Cascade semantics unresolved "
			+ str(_source_particle_bonefire3_descriptor.get("error", "unknown"))
		)
		return false
	if not _mount_source_particle_semantic_anchors(
		_source_particle_bonefire3_descriptor,
		1,
		"bone fire 3"
	):
		return false
	_source_particle_semantic_runtime_count += 1

	_source_particle_pap_wheel_descriptor = NachtCascadeRuntime.pap_wheel_descriptor(_particle_graphs)
	if not bool(_source_particle_pap_wheel_descriptor.get("ready", false)):
		push_error(
			"NACHT_FULL_MAP: PaP wheel Cascade semantics unresolved "
			+ str(_source_particle_pap_wheel_descriptor.get("error", "unknown"))
		)
		return false
	if not _mount_source_particle_semantic_anchors(
		_source_particle_pap_wheel_descriptor,
		3,
		"PaP wheel"
	):
		return false
	_source_particle_semantic_runtime_count += 1

	_source_particle_mystery_fog_descriptor = NachtCascadeRuntime.mystery_box_fog_descriptor(_particle_graphs)
	if not bool(_source_particle_mystery_fog_descriptor.get("ready", false)):
		push_error(
			"NACHT_FULL_MAP: mystery box fog Cascade semantics unresolved "
			+ str(_source_particle_mystery_fog_descriptor.get("error", "unknown"))
		)
		return false
	if not _mount_source_particle_semantic_anchors(
		_source_particle_mystery_fog_descriptor,
		3,
		"mystery box fog"
	):
		return false
	_source_particle_semantic_runtime_count += 1

	_source_particle_mystery_inside_descriptor = NachtCascadeRuntime.mystery_inside_descriptor(_particle_graphs)
	if not bool(_source_particle_mystery_inside_descriptor.get("ready", false)):
		push_error(
			"NACHT_FULL_MAP: mystery inside Cascade semantics unresolved "
			+ str(_source_particle_mystery_inside_descriptor.get("error", "unknown"))
		)
		return false
	if not _mount_source_particle_semantic_anchors(
		_source_particle_mystery_inside_descriptor,
		3,
		"mystery inside"
	):
		return false
	_source_particle_semantic_runtime_count += 1

	_source_particle_fire_smoke_descriptor = NachtCascadeRuntime.big_fire_vg_smk_descriptor(_particle_graphs)
	if not bool(_source_particle_fire_smoke_descriptor.get("ready", false)):
		push_error(
			"NACHT_FULL_MAP: big fire vg smoke Cascade semantics unresolved "
			+ str(_source_particle_fire_smoke_descriptor.get("error", "unknown"))
		)
		return false
	if not _mount_source_particle_semantic_anchors(
		_source_particle_fire_smoke_descriptor,
		1,
		"big fire vg smoke"
	):
		return false
	_source_particle_semantic_runtime_count += 1

	_source_particle_pap_wheel_out_descriptor = NachtCascadeRuntime.pap_wheel_out_descriptor(_particle_graphs)
	if not bool(_source_particle_pap_wheel_out_descriptor.get("ready", false)):
		push_error(
			"NACHT_FULL_MAP: PaP wheel out Cascade semantics unresolved "
			+ str(_source_particle_pap_wheel_out_descriptor.get("error", "unknown"))
		)
		return false
	if not _mount_source_particle_semantic_anchors(
		_source_particle_pap_wheel_out_descriptor,
		1,
		"PaP wheel out"
	):
		return false
	_source_particle_semantic_runtime_count += 1

	_source_particle_electric_beam_descriptor = NachtCascadeRuntime.electric_beam_descriptor(_particle_graphs)
	if not bool(_source_particle_electric_beam_descriptor.get("ready", false)):
		push_error(
			"NACHT_FULL_MAP: electric beam Cascade semantics unresolved "
			+ str(_source_particle_electric_beam_descriptor.get("error", "unknown"))
		)
		return false
	if not _mount_source_particle_semantic_anchors(
		_source_particle_electric_beam_descriptor,
		1,
		"electric beam"
	):
		return false
	_source_particle_semantic_runtime_count += 1

	_source_particle_acid_ball_descriptor = NachtCascadeRuntime.acid_ball_descriptor(_particle_graphs)
	if not bool(_source_particle_acid_ball_descriptor.get("ready", false)):
		push_error(
			"NACHT_FULL_MAP: AcidBall Cascade semantics unresolved "
			+ str(_source_particle_acid_ball_descriptor.get("error", "unknown"))
		)
		return false
	if not _mount_source_particle_semantic_anchors(
		_source_particle_acid_ball_descriptor,
		2,
		"AcidBall"
	):
		return false
	_source_particle_semantic_runtime_count += 1

	_source_particle_sparks_small_descriptor = NachtCascadeRuntime.sparks_small_descriptor(_particle_graphs)
	if not bool(_source_particle_sparks_small_descriptor.get("ready", false)):
		push_error(
			"NACHT_FULL_MAP: sparks small Cascade semantics unresolved "
			+ str(_source_particle_sparks_small_descriptor.get("error", "unknown"))
		)
		return false
	if not _mount_source_particle_semantic_anchors(
		_source_particle_sparks_small_descriptor,
		2,
		"sparks small"
	):
		return false
	_source_particle_semantic_runtime_count += 1

	_source_particle_quad_smoke_descriptor = NachtCascadeRuntime.quad_explode_smoke_descriptor(_particle_graphs)
	if not bool(_source_particle_quad_smoke_descriptor.get("ready", false)):
		push_error(
			"NACHT_FULL_MAP: quad explode smoke Cascade semantics unresolved "
			+ str(_source_particle_quad_smoke_descriptor.get("error", "unknown"))
		)
		return false
	if not _mount_source_particle_semantic_anchors(
		_source_particle_quad_smoke_descriptor,
		1,
		"quad explode smoke"
	):
		return false
	_source_particle_semantic_runtime_count += 1

	_source_particle_monster_descriptor = NachtCascadeRuntime.monster_death_xl_descriptor(_particle_graphs)
	if not bool(_source_particle_monster_descriptor.get("ready", false)):
		push_error("NACHT_FULL_MAP: monster XL Cascade semantics unresolved " + str(_source_particle_monster_descriptor.get("error", "unknown")))
		return false
	if not _mount_source_particle_semantic_anchors(
		_source_particle_monster_descriptor,
		1,
		"monster XL"
	):
		return false
	_source_particle_semantic_runtime_count += 1

	_source_particle_fire00_descriptor = NachtCascadeRuntime.fire_00_descriptor(_particle_graphs)
	if not bool(_source_particle_fire00_descriptor.get("ready", false)):
		push_error("NACHT_FULL_MAP: Fire_00 Cascade semantics unresolved " + str(_source_particle_fire00_descriptor.get("error", "unknown")))
		return false
	if not _mount_source_particle_semantic_anchors(
		_source_particle_fire00_descriptor,
		2,
		"Fire_00"
	):
		return false
	_source_particle_semantic_runtime_count += 1

	_source_particle_fire14_descriptor = NachtCascadeRuntime.fire_14_descriptor(_particle_graphs)
	if not bool(_source_particle_fire14_descriptor.get("ready", false)):
		push_error("NACHT_FULL_MAP: Fire_14 Cascade semantics unresolved " + str(_source_particle_fire14_descriptor.get("error", "unknown")))
		return false
	if not _mount_source_particle_semantic_anchors(
		_source_particle_fire14_descriptor,
		2,
		"Fire_14"
	):
		return false
	_source_particle_semantic_runtime_count += 1

	set_meta(
		"source_particle_mystery_spawn_rate",
		float(_source_particle_mystery_descriptor.get("spawnRateMin", -1.0))
	)
	set_meta(
		"source_particle_mystery_lifetime_min",
		float(_source_particle_mystery_descriptor.get("lifetimeMin", -1.0))
	)
	set_meta(
		"source_particle_mystery_lifetime_max",
		float(_source_particle_mystery_descriptor.get("lifetimeMax", -1.0))
	)
	set_meta(
		"source_particle_mystery_peak_active",
		int(_source_particle_mystery_descriptor.get("peakActiveParticles", -1))
	)
	set_meta(
		"source_particle_mystery_start_size_min_ue_cm",
		_source_particle_mystery_descriptor.get("startSizeMinUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_mystery_start_size_max_ue_cm",
		_source_particle_mystery_descriptor.get("startSizeMaxUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_fire_pivot_offset",
		_source_particle_fire_descriptor.get("pivotOffset", Vector2.INF)
	)
	set_meta(
		"source_particle_fire_speed_scale",
		_source_particle_fire_descriptor.get("speedScale", Vector2.INF)
	)
	set_meta(
		"source_particle_fire_max_scale",
		_source_particle_fire_descriptor.get("maxScale", Vector2.INF)
	)
	set_meta(
		"source_particle_fire_lifetime_min",
		float(_source_particle_fire_descriptor.get("lifetimeMin", -1.0))
	)
	set_meta(
		"source_particle_fire_lifetime_max",
		float(_source_particle_fire_descriptor.get("lifetimeMax", -1.0))
	)
	set_meta(
		"source_particle_fire_cylinder_radius_ue_cm",
		float(_source_particle_fire_descriptor.get("cylinderRadiusUEcm", -1.0))
	)
	set_meta(
		"source_particle_fire_subuv_max_index",
		float(_source_particle_fire_descriptor.get("subUVMaxIndex", -1.0))
	)
	set_meta(
		"source_particle_bonefire_start_size_min_ue_cm",
		_source_particle_bonefire_descriptor.get("startSizeMinUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_bonefire_start_size_max_ue_cm",
		_source_particle_bonefire_descriptor.get("startSizeMaxUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_bonefire_lifetime_min",
		float(_source_particle_bonefire_descriptor.get("lifetimeMin", -1.0))
	)
	set_meta(
		"source_particle_bonefire_lifetime_max",
		float(_source_particle_bonefire_descriptor.get("lifetimeMax", -1.0))
	)
	set_meta(
		"source_particle_bonefire_cylinder_radius_ue_cm",
		float(_source_particle_bonefire_descriptor.get("cylinderRadiusUEcm", -1.0))
	)
	set_meta(
		"source_particle_bonefire_subuv_max_index",
		float(_source_particle_bonefire_descriptor.get("subUVMaxIndex", -1.0))
	)
	set_meta(
		"source_particle_bonefire3_start_size_min_ue_cm",
		_source_particle_bonefire3_descriptor.get("startSizeMinUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_bonefire3_start_size_max_ue_cm",
		_source_particle_bonefire3_descriptor.get("startSizeMaxUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_bonefire3_life_multiplier_min",
		_source_particle_bonefire3_descriptor.get("lifeMultiplierMin", Vector3.INF)
	)
	set_meta(
		"source_particle_bonefire3_life_multiplier_max",
		_source_particle_bonefire3_descriptor.get("lifeMultiplierMax", Vector3.INF)
	)
	set_meta(
		"source_particle_bonefire3_lifetime_min",
		float(_source_particle_bonefire3_descriptor.get("lifetimeMin", -1.0))
	)
	set_meta(
		"source_particle_bonefire3_lifetime_max",
		float(_source_particle_bonefire3_descriptor.get("lifetimeMax", -1.0))
	)
	set_meta(
		"source_particle_bonefire3_cylinder_radius_ue_cm",
		float(_source_particle_bonefire3_descriptor.get("cylinderRadiusUEcm", -1.0))
	)
	set_meta(
		"source_particle_bonefire3_subuv_frame_rate",
		float(_source_particle_bonefire3_descriptor.get("subUVFrameRate", -1.0))
	)
	set_meta(
		"source_particle_bonefire3_rgb_table_value_count",
		int(_source_particle_bonefire3_descriptor.get("rgbTableValueCount", -1))
	)
	set_meta(
		"source_particle_bonefire3_alpha_table_value_count",
		int(_source_particle_bonefire3_descriptor.get("alphaTableValueCount", -1))
	)
	set_meta(
		"source_particle_pap_wheel_emitter_count",
		int(_source_particle_pap_wheel_descriptor.get("emitterCount", -1))
	)
	set_meta(
		"source_particle_pap_wheel_lifetime_seconds",
		float(_source_particle_pap_wheel_descriptor.get("lifetimeSeconds", -1.0))
	)
	set_meta(
		"source_particle_pap_wheel_start_size_min_ue_cm",
		_source_particle_pap_wheel_descriptor.get("startSizeMinUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_pap_wheel_start_size_max_ue_cm",
		_source_particle_pap_wheel_descriptor.get("startSizeMaxUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_pap_wheel_spawn_rate",
		float(_source_particle_pap_wheel_descriptor.get("spawnRate", -1.0))
	)
	set_meta(
		"source_particle_pap_wheel_burst_count",
		int(_source_particle_pap_wheel_descriptor.get("burstCount", -1))
	)
	set_meta(
		"source_particle_pap_wheel_rotation_rate_min",
		float(_source_particle_pap_wheel_descriptor.get("rotationRateMin", 999.0))
	)
	set_meta(
		"source_particle_pap_wheel_rotation_rate_max",
		float(_source_particle_pap_wheel_descriptor.get("rotationRateMax", -999.0))
	)
	set_meta(
		"source_particle_pap_wheel_velocity_life_min",
		_source_particle_pap_wheel_descriptor.get("velocityOverLifeMin", Vector3.INF)
	)
	set_meta(
		"source_particle_pap_wheel_velocity_life_time_scale",
		float(_source_particle_pap_wheel_descriptor.get("velocityOverLifeTimeScale", -1.0))
	)
	set_meta(
		"source_particle_pap_wheel_size_life_table_value_count",
		int(_source_particle_pap_wheel_descriptor.get("sizeLifeTableValueCount", -1))
	)
	set_meta(
		"source_particle_mystery_fog_lifetime_min",
		float(_source_particle_mystery_fog_descriptor.get("lifetimeMin", -1.0))
	)
	set_meta(
		"source_particle_mystery_fog_lifetime_max",
		float(_source_particle_mystery_fog_descriptor.get("lifetimeMax", -1.0))
	)
	set_meta(
		"source_particle_mystery_fog_location_min_ue_cm",
		_source_particle_mystery_fog_descriptor.get("startLocationMinUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_mystery_fog_location_max_ue_cm",
		_source_particle_mystery_fog_descriptor.get("startLocationMaxUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_mystery_fog_start_size_min_ue_cm",
		_source_particle_mystery_fog_descriptor.get("startSizeMinUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_mystery_fog_start_size_max_ue_cm",
		_source_particle_mystery_fog_descriptor.get("startSizeMaxUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_mystery_fog_spawn_rate",
		float(_source_particle_mystery_fog_descriptor.get("spawnRate", -1.0))
	)
	set_meta(
		"source_particle_mystery_fog_subuv_frame_rate",
		float(_source_particle_mystery_fog_descriptor.get("subUVFrameRate", -1.0))
	)
	set_meta(
		"source_particle_mystery_fog_alpha_table_value_count",
		int(_source_particle_mystery_fog_descriptor.get("alphaTableValueCount", -1))
	)
	set_meta(
		"source_particle_mystery_fog_peak_active",
		int(_source_particle_mystery_fog_descriptor.get("peakActiveParticles", -1))
	)
	set_meta(
		"source_particle_mystery_fog_life_multiplier_min",
		_source_particle_mystery_fog_descriptor.get("lifeMultiplierMin", Vector3.INF)
	)
	set_meta(
		"source_particle_mystery_fog_life_multiplier_max",
		_source_particle_mystery_fog_descriptor.get("lifeMultiplierMax", Vector3.INF)
	)
	set_meta(
		"source_particle_mystery_fog_life_multiplier_table_value_count",
		int(_source_particle_mystery_fog_descriptor.get("lifeMultiplierTableValueCount", -1))
	)
	set_meta(
		"source_particle_mystery_fog_color_min",
		_source_particle_mystery_fog_descriptor.get("colorMin", Vector3.INF)
	)
	set_meta(
		"source_particle_mystery_fog_color_max",
		_source_particle_mystery_fog_descriptor.get("colorMax", Vector3.INF)
	)
	set_meta(
		"source_particle_mystery_fog_rgb_table_value_count",
		int(_source_particle_mystery_fog_descriptor.get("rgbTableValueCount", -1))
	)
	set_meta(
		"source_particle_mystery_fog_alpha_max",
		float(_source_particle_mystery_fog_descriptor.get("alphaMax", -1.0))
	)
	set_meta(
		"source_particle_mystery_fog_velocity_life_min",
		_source_particle_mystery_fog_descriptor.get("velocityOverLifeMin", Vector3.INF)
	)
	set_meta(
		"source_particle_mystery_fog_velocity_life_max",
		_source_particle_mystery_fog_descriptor.get("velocityOverLifeMax", Vector3.INF)
	)
	set_meta(
		"source_particle_mystery_fog_velocity_life_time_scale",
		float(_source_particle_mystery_fog_descriptor.get("velocityOverLifeTimeScale", -1.0))
	)
	set_meta(
		"source_particle_mystery_fog_start_velocity_min_ue_cm",
		_source_particle_mystery_fog_descriptor.get("startVelocityMinUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_mystery_fog_start_velocity_max_ue_cm",
		_source_particle_mystery_fog_descriptor.get("startVelocityMaxUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_mystery_inside_lifetime_min",
		float(_source_particle_mystery_inside_descriptor.get("lifetimeMin", -1.0))
	)
	set_meta(
		"source_particle_mystery_inside_lifetime_max",
		float(_source_particle_mystery_inside_descriptor.get("lifetimeMax", -1.0))
	)
	set_meta(
		"source_particle_mystery_inside_location_min_ue_cm",
		_source_particle_mystery_inside_descriptor.get("startLocationMinUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_mystery_inside_location_max_ue_cm",
		_source_particle_mystery_inside_descriptor.get("startLocationMaxUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_mystery_inside_start_size_min_ue_cm",
		_source_particle_mystery_inside_descriptor.get("startSizeMinUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_mystery_inside_start_size_max_ue_cm",
		_source_particle_mystery_inside_descriptor.get("startSizeMaxUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_mystery_inside_spawn_rate",
		float(_source_particle_mystery_inside_descriptor.get("spawnRate", -1.0))
	)
	set_meta(
		"source_particle_mystery_inside_start_velocity_min_ue_cm",
		_source_particle_mystery_inside_descriptor.get("startVelocityMinUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_mystery_inside_start_velocity_max_ue_cm",
		_source_particle_mystery_inside_descriptor.get("startVelocityMaxUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_mystery_inside_rgb_table_value_count",
		int(_source_particle_mystery_inside_descriptor.get("rgbTableValueCount", -1))
	)
	set_meta(
		"source_particle_mystery_inside_alpha_table_value_count",
		int(_source_particle_mystery_inside_descriptor.get("alphaTableValueCount", -1))
	)
	set_meta(
		"source_particle_mystery_inside_orbit_enabled",
		bool(_source_particle_mystery_inside_descriptor.get("orbitEnabled", true))
	)
	set_meta(
		"source_particle_mystery_inside_orbit_offset_min",
		_source_particle_mystery_inside_descriptor.get("orbitOffsetMin", Vector3.INF)
	)
	set_meta(
		"source_particle_mystery_inside_orbit_offset_max",
		_source_particle_mystery_inside_descriptor.get("orbitOffsetMax", Vector3.INF)
	)
	set_meta(
		"source_particle_mystery_inside_gpu_inv_max_size",
		_source_particle_mystery_inside_descriptor.get("gpuInvMaxSize", Vector2.INF)
	)
	set_meta(
		"source_particle_mystery_inside_gpu_inv_rotation_rate_scale",
		float(_source_particle_mystery_inside_descriptor.get("gpuInvRotationRateScale", -1.0))
	)
	set_meta(
		"source_particle_mystery_inside_gpu_max_lifetime",
		float(_source_particle_mystery_inside_descriptor.get("gpuMaxLifetime", -1.0))
	)
	set_meta(
		"source_particle_mystery_inside_gpu_max_particle_count",
		int(_source_particle_mystery_inside_descriptor.get("gpuMaxParticleCount", -1))
	)
	set_meta(
		"source_particle_mystery_inside_gpu_rotation_rate_scale",
		float(_source_particle_mystery_inside_descriptor.get("gpuRotationRateScale", -1.0))
	)
	set_meta(
		"source_particle_mystery_inside_gpu_quantized_color_sample_count",
		int(_source_particle_mystery_inside_descriptor.get("gpuQuantizedColorSampleCount", -1))
	)
	set_meta(
		"source_particle_fire_smoke_lifetime_min",
		float(_source_particle_fire_smoke_descriptor.get("lifetimeMin", -1.0))
	)
	set_meta(
		"source_particle_fire_smoke_lifetime_max",
		float(_source_particle_fire_smoke_descriptor.get("lifetimeMax", -1.0))
	)
	set_meta(
		"source_particle_fire_smoke_cylinder_radius_ue_cm",
		float(_source_particle_fire_smoke_descriptor.get("cylinderRadiusUEcm", -1.0))
	)
	set_meta(
		"source_particle_fire_smoke_pivot_offset",
		_source_particle_fire_smoke_descriptor.get("pivotOffset", Vector2.INF)
	)
	set_meta(
		"source_particle_fire_smoke_life_multiplier_min",
		_source_particle_fire_smoke_descriptor.get("lifeMultiplierMin", Vector3.INF)
	)
	set_meta(
		"source_particle_fire_smoke_life_multiplier_max",
		_source_particle_fire_smoke_descriptor.get("lifeMultiplierMax", Vector3.INF)
	)
	set_meta(
		"source_particle_fire_smoke_speed_scale",
		_source_particle_fire_smoke_descriptor.get("speedScale", Vector2.INF)
	)
	set_meta(
		"source_particle_fire_smoke_max_scale",
		_source_particle_fire_smoke_descriptor.get("maxScale", Vector2.INF)
	)
	set_meta(
		"source_particle_fire_smoke_start_size_min_ue_cm",
		_source_particle_fire_smoke_descriptor.get("startSizeMinUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_fire_smoke_start_size_max_ue_cm",
		_source_particle_fire_smoke_descriptor.get("startSizeMaxUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_fire_smoke_subuv_frame_rate",
		float(_source_particle_fire_smoke_descriptor.get("subUVFrameRate", -1.0))
	)
	set_meta(
		"source_particle_fire_smoke_start_velocity_min_ue_cm",
		_source_particle_fire_smoke_descriptor.get("startVelocityMinUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_fire_smoke_start_velocity_max_ue_cm",
		_source_particle_fire_smoke_descriptor.get("startVelocityMaxUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_fire_smoke_rgb_table_value_count",
		int(_source_particle_fire_smoke_descriptor.get("rgbTableValueCount", -1))
	)
	set_meta(
		"source_particle_fire_smoke_alpha_table_value_count",
		int(_source_particle_fire_smoke_descriptor.get("alphaTableValueCount", -1))
	)
	set_meta(
		"source_particle_fire_smoke_spawn_rates_by_lod",
		_source_particle_fire_smoke_descriptor.get("spawnRatesByLOD", [])
	)
	set_meta(
		"source_particle_fire_smoke_peak_active_by_lod",
		_source_particle_fire_smoke_descriptor.get("peakActiveByLOD", [])
	)
	set_meta(
		"source_particle_pap_wheel_out_lifetime_min",
		float(_source_particle_pap_wheel_out_descriptor.get("lifetimeMin", -1.0))
	)
	set_meta(
		"source_particle_pap_wheel_out_lifetime_max",
		float(_source_particle_pap_wheel_out_descriptor.get("lifetimeMax", -1.0))
	)
	set_meta(
		"source_particle_pap_wheel_out_location_min_ue_cm",
		_source_particle_pap_wheel_out_descriptor.get("startLocationMinUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_pap_wheel_out_location_max_ue_cm",
		_source_particle_pap_wheel_out_descriptor.get("startLocationMaxUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_pap_wheel_out_start_size_min_ue_cm",
		_source_particle_pap_wheel_out_descriptor.get("startSizeMinUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_pap_wheel_out_start_size_max_ue_cm",
		_source_particle_pap_wheel_out_descriptor.get("startSizeMaxUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_pap_wheel_out_size_life_table_value_count",
		int(_source_particle_pap_wheel_out_descriptor.get("sizeLifeTableValueCount", -1))
	)
	set_meta(
		"source_particle_pap_wheel_out_size_life_time_scale",
		float(_source_particle_pap_wheel_out_descriptor.get("sizeLifeTimeScale", -1.0))
	)
	set_meta(
		"source_particle_pap_wheel_out_start_velocity_min_ue_cm",
		_source_particle_pap_wheel_out_descriptor.get("startVelocityMinUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_pap_wheel_out_start_velocity_max_ue_cm",
		_source_particle_pap_wheel_out_descriptor.get("startVelocityMaxUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_pap_wheel_out_velocity_life_max",
		_source_particle_pap_wheel_out_descriptor.get("velocityOverLifeMax", Vector3.INF)
	)
	set_meta(
		"source_particle_pap_wheel_out_velocity_life_table_value_count",
		int(_source_particle_pap_wheel_out_descriptor.get("velocityOverLifeTableValueCount", -1))
	)
	set_meta(
		"source_particle_pap_wheel_out_velocity_life_time_scale",
		float(_source_particle_pap_wheel_out_descriptor.get("velocityOverLifeTimeScale", -1.0))
	)
	set_meta(
		"source_particle_pap_wheel_out_acceleration_min_ue_cm",
		_source_particle_pap_wheel_out_descriptor.get("accelerationMinUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_pap_wheel_out_acceleration_max_ue_cm",
		_source_particle_pap_wheel_out_descriptor.get("accelerationMaxUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_pap_wheel_out_acceleration_world_space",
		bool(_source_particle_pap_wheel_out_descriptor.get("accelerationWorldSpace", false))
	)
	set_meta(
		"source_particle_pap_wheel_out_rotation_rate_min",
		float(_source_particle_pap_wheel_out_descriptor.get("rotationRateMin", 999.0))
	)
	set_meta(
		"source_particle_pap_wheel_out_rotation_rate_max",
		float(_source_particle_pap_wheel_out_descriptor.get("rotationRateMax", -999.0))
	)
	set_meta(
		"source_particle_pap_wheel_out_spawn_rate",
		float(_source_particle_pap_wheel_out_descriptor.get("spawnRate", -1.0))
	)
	set_meta(
		"source_particle_pap_wheel_out_spawn_rate_scale",
		float(_source_particle_pap_wheel_out_descriptor.get("spawnRateScale", -1.0))
	)
	set_meta(
		"source_particle_pap_wheel_out_peak_active",
		int(_source_particle_pap_wheel_out_descriptor.get("peakActiveParticles", -1))
	)
	set_meta(
		"source_particle_electric_beam_lifetime_seconds",
		float(_source_particle_electric_beam_descriptor.get("lifetimeSeconds", -1.0))
	)
	set_meta(
		"source_particle_electric_beam_start_size_ue_cm",
		_source_particle_electric_beam_descriptor.get("startSizeUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_electric_beam_spawn_rate",
		float(_source_particle_electric_beam_descriptor.get("spawnRate", -1.0))
	)
	set_meta(
		"source_particle_electric_beam_noise_frequency",
		int(_source_particle_electric_beam_descriptor.get("noiseFrequency", -1))
	)
	set_meta(
		"source_particle_electric_beam_noise_lock_time",
		float(_source_particle_electric_beam_descriptor.get("noiseLockTime", -1.0))
	)
	set_meta(
		"source_particle_electric_beam_noise_range_max_ue_cm",
		_source_particle_electric_beam_descriptor.get("noiseRangeMaxUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_electric_beam_noise_speed_ue_cm",
		_source_particle_electric_beam_descriptor.get("noiseSpeedUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_electric_beam_noise_tangent_strength",
		float(_source_particle_electric_beam_descriptor.get("noiseTangentStrength", -1.0))
	)
	set_meta(
		"source_particle_electric_beam_source_strength",
		float(_source_particle_electric_beam_descriptor.get("sourceStrength", -1.0))
	)
	set_meta(
		"source_particle_electric_beam_source_tangent",
		_source_particle_electric_beam_descriptor.get("sourceTangent", Vector3.INF)
	)
	set_meta(
		"source_particle_electric_beam_target_ue_cm",
		_source_particle_electric_beam_descriptor.get("targetUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_electric_beam_target_strength",
		float(_source_particle_electric_beam_descriptor.get("targetStrength", -1.0))
	)
	set_meta(
		"source_particle_electric_beam_target_tangent",
		_source_particle_electric_beam_descriptor.get("targetTangent", Vector3.INF)
	)
	set_meta(
		"source_particle_electric_beam_distance",
		float(_source_particle_electric_beam_descriptor.get("beamDistance", -1.0))
	)
	set_meta(
		"source_particle_electric_beam_interpolation_points",
		int(_source_particle_electric_beam_descriptor.get("interpolationPoints", -1))
	)
	set_meta(
		"source_particle_electric_beam_max_beam_count",
		int(_source_particle_electric_beam_descriptor.get("maxBeamCount", -1))
	)
	set_meta(
		"source_particle_electric_beam_peak_active",
		int(_source_particle_electric_beam_descriptor.get("peakActiveParticles", -1))
	)
	set_meta(
		"source_particle_acid_ball_mesh_burst_count",
		int(_source_particle_acid_ball_descriptor.get("meshBurstCount", -1))
	)
	set_meta(
		"source_particle_acid_ball_sprite_spawn_rate",
		float(_source_particle_acid_ball_descriptor.get("spriteSpawnRate", -1.0))
	)
	set_meta(
		"source_particle_acid_ball_sprite_lifetime_min",
		float(_source_particle_acid_ball_descriptor.get("spriteLifetimeMin", -1.0))
	)
	set_meta(
		"source_particle_acid_ball_sprite_lifetime_max",
		float(_source_particle_acid_ball_descriptor.get("spriteLifetimeMax", -1.0))
	)
	set_meta(
		"source_particle_acid_ball_mesh_size_ue_cm",
		_source_particle_acid_ball_descriptor.get("meshSizeUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_acid_ball_sprite_size_min_ue_cm",
		_source_particle_acid_ball_descriptor.get("spriteSizeMinUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_acid_ball_sprite_size_max_ue_cm",
		_source_particle_acid_ball_descriptor.get("spriteSizeMaxUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_acid_ball_dynamic_param_count",
		int(_source_particle_acid_ball_descriptor.get("dynamicParamCount", -1))
	)
	set_meta(
		"source_particle_acid_ball_dynamic_ranges",
		_source_particle_acid_ball_descriptor.get("dynamicRanges", [])
	)
	set_meta(
		"source_particle_acid_ball_dynamic_spawn_time_only",
		_source_particle_acid_ball_descriptor.get("dynamicSpawnTimeOnly", [])
	)
	set_meta(
		"source_particle_acid_ball_dynamic_samples",
		_source_particle_acid_ball_descriptor.get("dynamicSamples", [])
	)
	set_meta(
		"source_particle_acid_ball_peak_active_by_emitter",
		_source_particle_acid_ball_descriptor.get("peakActiveByEmitter", [])
	)
	set_meta(
		"source_particle_sparks_lifetime_min",
		float(_source_particle_sparks_small_descriptor.get("lifetimeMin", -1.0))
	)
	set_meta(
		"source_particle_sparks_lifetime_max",
		float(_source_particle_sparks_small_descriptor.get("lifetimeMax", -1.0))
	)
	set_meta(
		"source_particle_sparks_seeded_location_min_ue_cm",
		_source_particle_sparks_small_descriptor.get("seededLocationMinUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_sparks_seeded_location_max_ue_cm",
		_source_particle_sparks_small_descriptor.get("seededLocationMaxUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_sparks_acceleration_ue_cm",
		_source_particle_sparks_small_descriptor.get("accelerationUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_sparks_acceleration_world_space",
		bool(_source_particle_sparks_small_descriptor.get("accelerationWorldSpace", false))
	)
	set_meta(
		"source_particle_sparks_collision_enabled",
		bool(_source_particle_sparks_small_descriptor.get("collisionEnabled", true))
	)
	set_meta(
		"source_particle_sparks_collision_resilience",
		float(_source_particle_sparks_small_descriptor.get("collisionResilience", -1.0))
	)
	set_meta(
		"source_particle_sparks_collision_resilience_scale",
		float(_source_particle_sparks_small_descriptor.get("collisionResilienceScale", -1.0))
	)
	set_meta(
		"source_particle_sparks_speed_scale",
		_source_particle_sparks_small_descriptor.get("speedScale", Vector2.INF)
	)
	set_meta(
		"source_particle_sparks_max_scale",
		_source_particle_sparks_small_descriptor.get("maxScale", Vector2.INF)
	)
	set_meta(
		"source_particle_sparks_start_size_min_ue_cm",
		_source_particle_sparks_small_descriptor.get("startSizeMinUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_sparks_start_size_max_ue_cm",
		_source_particle_sparks_small_descriptor.get("startSizeMaxUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_sparks_spawn_rate",
		float(_source_particle_sparks_small_descriptor.get("spawnRate", -1.0))
	)
	set_meta(
		"source_particle_sparks_burst_count",
		int(_source_particle_sparks_small_descriptor.get("burstCount", -1))
	)
	set_meta(
		"source_particle_sparks_burst_count_low",
		int(_source_particle_sparks_small_descriptor.get("burstCountLow", -1))
	)
	set_meta(
		"source_particle_sparks_burst_time",
		float(_source_particle_sparks_small_descriptor.get("burstTime", -1.0))
	)
	set_meta(
		"source_particle_sparks_burst_scale",
		float(_source_particle_sparks_small_descriptor.get("burstScale", -1.0))
	)
	set_meta(
		"source_particle_sparks_start_velocity_min_ue_cm",
		_source_particle_sparks_small_descriptor.get("startVelocityMinUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_sparks_start_velocity_max_ue_cm",
		_source_particle_sparks_small_descriptor.get("startVelocityMaxUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_sparks_gpu_inv_max_size",
		_source_particle_sparks_small_descriptor.get("gpuInvMaxSize", Vector2.INF)
	)
	set_meta(
		"source_particle_sparks_gpu_max_lifetime",
		float(_source_particle_sparks_small_descriptor.get("gpuMaxLifetime", -1.0))
	)
	set_meta(
		"source_particle_sparks_gpu_max_particle_count",
		int(_source_particle_sparks_small_descriptor.get("gpuMaxParticleCount", -1))
	)
	set_meta(
		"source_particle_sparks_gpu_collision_radius_scale",
		float(_source_particle_sparks_small_descriptor.get("gpuCollisionRadiusScale", -1.0))
	)
	set_meta(
		"source_particle_sparks_gpu_collision_random_distribution",
		float(_source_particle_sparks_small_descriptor.get("gpuCollisionRandomDistribution", -1.0))
	)
	set_meta(
		"source_particle_sparks_peak_active_by_lod",
		_source_particle_sparks_small_descriptor.get("peakActiveByLOD", [])
	)
	set_meta(
		"source_particle_quad_smoke_lifetime_min",
		float(_source_particle_quad_smoke_descriptor.get("lifetimeMin", -1.0))
	)
	set_meta(
		"source_particle_quad_smoke_lifetime_max",
		float(_source_particle_quad_smoke_descriptor.get("lifetimeMax", -1.0))
	)
	set_meta(
		"source_particle_quad_smoke_start_size_min_ue_cm",
		_source_particle_quad_smoke_descriptor.get("startSizeMinUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_quad_smoke_start_size_max_ue_cm",
		_source_particle_quad_smoke_descriptor.get("startSizeMaxUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_quad_smoke_start_location_min_ue_cm",
		_source_particle_quad_smoke_descriptor.get("startLocationMinUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_quad_smoke_start_location_max_ue_cm",
		_source_particle_quad_smoke_descriptor.get("startLocationMaxUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_quad_smoke_start_velocity_min_ue_cm",
		_source_particle_quad_smoke_descriptor.get("startVelocityMinUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_quad_smoke_start_velocity_max_ue_cm",
		_source_particle_quad_smoke_descriptor.get("startVelocityMaxUEcm", Vector3.INF)
	)
	set_meta(
		"source_particle_quad_smoke_spawn_rate",
		float(_source_particle_quad_smoke_descriptor.get("spawnRate", -1.0))
	)
	set_meta(
		"source_particle_quad_smoke_spawn_rate_scale",
		float(_source_particle_quad_smoke_descriptor.get("spawnRateScale", -1.0))
	)
	set_meta(
		"source_particle_quad_smoke_burst_count",
		int(_source_particle_quad_smoke_descriptor.get("burstCount", -1))
	)
	set_meta(
		"source_particle_quad_smoke_subuv_frame_rate",
		float(_source_particle_quad_smoke_descriptor.get("subUVFrameRate", -1.0))
	)
	set_meta(
		"source_particle_quad_smoke_size_life_table_value_count",
		int(_source_particle_quad_smoke_descriptor.get("sizeLifeTableValueCount", -1))
	)
	set_meta(
		"source_particle_quad_smoke_rgb_table_value_count",
		int(_source_particle_quad_smoke_descriptor.get("rgbTableValueCount", -1))
	)
	set_meta(
		"source_particle_quad_smoke_alpha_table_value_count",
		int(_source_particle_quad_smoke_descriptor.get("alphaTableValueCount", -1))
	)
	set_meta(
		"source_particle_quad_smoke_disabled_module_types",
		_source_particle_quad_smoke_descriptor.get("disabledModuleTypes", [])
	)
	set_meta(
		"source_particle_quad_smoke_peak_active",
		int(_source_particle_quad_smoke_descriptor.get("peakActiveParticles", -1))
	)
	set_meta("source_particle_monster_emitter_count", int(_source_particle_monster_descriptor.get("emitterCount", -1)))
	set_meta("source_particle_monster_lod_count", int(_source_particle_monster_descriptor.get("lodCount", -1)))
	set_meta("source_particle_monster_burst_only_emitters", int(_source_particle_monster_descriptor.get("burstOnlyEmitterCount", -1)))
	set_meta("source_particle_monster_continuous_emitters", int(_source_particle_monster_descriptor.get("continuousRate15EmitterCount", -1)))
	set_meta("source_particle_monster_lifetime_ranges", _source_particle_monster_descriptor.get("lifetimeRanges", []))
	set_meta("source_particle_monster_size_life_modules", int(_source_particle_monster_descriptor.get("resolvedSizeLifeModuleCount", -1)))
	set_meta("source_particle_monster_color_modules", int(_source_particle_monster_descriptor.get("resolvedColorModuleCount", -1)))
	set_meta("source_particle_monster_velocity_min_ue_cm", _source_particle_monster_descriptor.get("velocityMinUEcm", Vector3.INF))
	set_meta("source_particle_monster_velocity_max_ue_cm", _source_particle_monster_descriptor.get("velocityMaxUEcm", Vector3.INF))
	set_meta("source_particle_monster_subuv_sample_count", int(_source_particle_monster_descriptor.get("subUVSampleCount", -1)))
	set_meta("source_particle_monster_lod_peaks", _source_particle_monster_descriptor.get("lodPeaks", []))
	set_meta("source_particle_fire00_emitter_count", int(_source_particle_fire00_descriptor.get("emitterCount", -1)))
	set_meta("source_particle_fire00_lod_count", int(_source_particle_fire00_descriptor.get("lodCount", -1)))
	set_meta("source_particle_fire00_material_paths", _source_particle_fire00_descriptor.get("materialPaths", []))
	set_meta("source_particle_fire00_lifetime_ranges", _source_particle_fire00_descriptor.get("lifetimeRanges", []))
	set_meta("source_particle_fire00_spawn_rates", _source_particle_fire00_descriptor.get("spawnRates", []))
	set_meta("source_particle_fire00_dynamic_module_count", int(_source_particle_fire00_descriptor.get("dynamicModuleCount", -1)))
	set_meta("source_particle_fire00_dynamic_parameter_count", int(_source_particle_fire00_descriptor.get("dynamicParameterCount", -1)))
	set_meta("source_particle_fire00_light_count", int(_source_particle_fire00_descriptor.get("particleLightCount", -1)))
	set_meta("source_particle_fire00_disabled_skel_surface_count", int(_source_particle_fire00_descriptor.get("disabledSkelSurfaceCount", -1)))
	set_meta("source_particle_fire00_lod_peaks", _source_particle_fire00_descriptor.get("lodPeaks", []))
	set_meta("source_particle_fire14_emitter_count", int(_source_particle_fire14_descriptor.get("emitterCount", -1)))
	set_meta("source_particle_fire14_lod_count", int(_source_particle_fire14_descriptor.get("lodCount", -1)))
	set_meta("source_particle_fire14_material_paths", _source_particle_fire14_descriptor.get("materialPaths", []))
	set_meta("source_particle_fire14_lifetime_ranges", _source_particle_fire14_descriptor.get("lifetimeRanges", []))
	set_meta("source_particle_fire14_spawn_rates", _source_particle_fire14_descriptor.get("spawnRates", []))
	set_meta("source_particle_fire14_dynamic_module_count", int(_source_particle_fire14_descriptor.get("dynamicModuleCount", -1)))
	set_meta("source_particle_fire14_dynamic_parameter_count", int(_source_particle_fire14_descriptor.get("dynamicParameterCount", -1)))
	set_meta("source_particle_fire14_light_count", int(_source_particle_fire14_descriptor.get("particleLightCount", -1)))
	set_meta("source_particle_fire14_disabled_skel_surface_count", int(_source_particle_fire14_descriptor.get("disabledSkelSurfaceCount", -1)))
	set_meta("source_particle_fire14_lod_peaks", _source_particle_fire14_descriptor.get("lodPeaks", []))

	print(
		"XZOGOT_NACHT_CASCADE_SEMANTIC_RUNTIME_GREEN systems=",
		_source_particle_semantic_runtime_count,
		" placements=",
		_source_particle_semantic_placement_count,
		" mystery_rate=",
		_source_particle_mystery_descriptor.get("spawnRateMin"),
		" mystery_lifetime=",
		_source_particle_mystery_descriptor.get("lifetimeMin"),
		"..",
		_source_particle_mystery_descriptor.get("lifetimeMax"),
		" mystery_peak=",
		_source_particle_mystery_descriptor.get("peakActiveParticles"),
		" fire_pivot=",
		_source_particle_fire_descriptor.get("pivotOffset"),
		" fire_speed_scale=",
		_source_particle_fire_descriptor.get("speedScale"),
		" fire_max_scale=",
		_source_particle_fire_descriptor.get("maxScale"),
		" bonefire_size=",
		_source_particle_bonefire_descriptor.get("startSizeMinUEcm"),
		"..",
		_source_particle_bonefire_descriptor.get("startSizeMaxUEcm"),
		" bonefire3_size=",
		_source_particle_bonefire3_descriptor.get("startSizeMinUEcm"),
		"..",
		_source_particle_bonefire3_descriptor.get("startSizeMaxUEcm"),
		" bonefire3_subuv_fps=",
		_source_particle_bonefire3_descriptor.get("subUVFrameRate"),
		" pap_wheel_rate=",
		_source_particle_pap_wheel_descriptor.get("spawnRate"),
		" pap_wheel_burst=",
		_source_particle_pap_wheel_descriptor.get("burstCount"),
		" mystery_fog_rate=",
		_source_particle_mystery_fog_descriptor.get("spawnRate"),
		" mystery_fog_subuv_fps=",
		_source_particle_mystery_fog_descriptor.get("subUVFrameRate"),
		" mystery_inside_rate=",
		_source_particle_mystery_inside_descriptor.get("spawnRate"),
		" mystery_inside_gpu_max=",
		_source_particle_mystery_inside_descriptor.get("gpuMaxParticleCount"),
		" fire_smoke_subuv_fps=",
		_source_particle_fire_smoke_descriptor.get("subUVFrameRate"),
		" fire_smoke_rates=",
		_source_particle_fire_smoke_descriptor.get("spawnRatesByLOD"),
		" pap_wheel_out_rate=",
		_source_particle_pap_wheel_out_descriptor.get("spawnRate"),
		" pap_wheel_out_peak=",
		_source_particle_pap_wheel_out_descriptor.get("peakActiveParticles"),
		" electric_beam_rate=",
		_source_particle_electric_beam_descriptor.get("spawnRate"),
		" electric_beam_target=",
		_source_particle_electric_beam_descriptor.get("targetUEcm"),
		" acid_ball_dynamic=",
		_source_particle_acid_ball_descriptor.get("dynamicRanges"),
		" acid_ball_peaks=",
		_source_particle_acid_ball_descriptor.get("peakActiveByEmitter"),
		" sparks_rate=",
		_source_particle_sparks_small_descriptor.get("spawnRate"),
		" sparks_gpu_max=",
		_source_particle_sparks_small_descriptor.get("gpuMaxParticleCount"),
		" quad_smoke_rate=",
		_source_particle_quad_smoke_descriptor.get("spawnRate"),
		" quad_smoke_disabled=",
		_source_particle_quad_smoke_descriptor.get("disabledModuleTypes"),
		" fire00_emitters=",
		_source_particle_fire00_descriptor.get("emitterCount"),
		" fire00_peaks=",
		_source_particle_fire00_descriptor.get("lodPeaks"),
		" fire14_emitters=",
		_source_particle_fire14_descriptor.get("emitterCount"),
		" fire14_peaks=",
		_source_particle_fire14_descriptor.get("lodPeaks")
	)
	return true


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
	_benchmark_loader.set("world_collision_group", &"nacht_world_collision")
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
		"source_effective_material_count",
		int(_benchmark_loader.get_meta("xziel_benchmark_effective_material_count", 0))
	)
	set_meta(
		"source_effective_material_textured_count",
		int(_benchmark_loader.get_meta("xziel_benchmark_effective_material_textured_count", 0))
	)
	set_meta(
		"source_effective_material_flat_fallback_count",
		int(_benchmark_loader.get_meta("xziel_benchmark_effective_material_flat_fallback_count", 0))
	)
	set_meta(
		"source_effective_source_color_count",
		int(_benchmark_loader.get_meta("xziel_benchmark_effective_source_color_count", 0))
	)
	set_meta(
		"source_effective_default_surface_count",
		int(_benchmark_loader.get_meta("xziel_benchmark_effective_default_surface_count", 0))
	)
	set_meta(
		"source_effective_engine_default_count",
		int(_benchmark_loader.get_meta("xziel_benchmark_effective_engine_default_count", 0))
	)
	set_meta(
		"source_effective_sibling_semantic_hits",
		int(_benchmark_loader.get_meta("xziel_benchmark_effective_sibling_semantic_hits", 0))
	)
	set_meta(
		"source_effective_unresolved_fallback_count",
		int(_benchmark_loader.get_meta("xziel_benchmark_effective_unresolved_fallback_count", 0))
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

		if str(row.get("className", "")) == "ZombieSpawner_C":
			anchor.add_to_group("zombie_spawn_anchor")
			anchor.add_to_group("nacht_zombie_spawn_anchor")
			anchor.set_meta(
				"spawn_id",
				str(row.get("objectPath", anchor.name))
			)
			anchor.set_meta("entry_kind", "source_direct")
			anchor.set_meta("zone", "nacht_source")
			anchor.set_meta("min_round", 1)
			anchor.set_meta("source_authority", "NACHT_UMAP_ZombieSpawner_C")
			_source_zombie_spawn_candidates.append(anchor)


func _begin_source_navigation() -> void:
	set_meta("nacht_source_zombie_spawn_count", _source_zombie_spawn_candidates.size())
	if _source_zombie_spawn_candidates.size() != 22:
		push_error(
			"NACHT_FULL_MAP: source ZombieSpawner_C coverage mismatch "
			+ str(_source_zombie_spawn_candidates.size()) + "/22"
		)
		return
	_source_navigation_runtime = SourceNavigationRuntimeScript.new() as Node3D
	if _source_navigation_runtime == null:
		push_error("NACHT_FULL_MAP: source navigation runtime missing")
		return
	_source_navigation_runtime.name = "NachtSourceNavigation"
	_source_navigation_runtime.set("source_collision_group", &"nacht_world_collision")
	_source_navigation_runtime.set("source_runtime_id", "nacht")
	_source_navigation_runtime.navigation_ready.connect(_on_source_navigation_ready)
	_source_navigation_runtime.navigation_failed.connect(_on_source_navigation_failed)
	add_child(_source_navigation_runtime)
	_source_navigation_runtime.call_deferred("begin_bake")
	print(
		"XZOGOT_NACHT_SOURCE_SPAWNS_GREEN count=",
		_source_zombie_spawn_candidates.size()
	)

func _on_source_navigation_ready(polygons: int, vertices: int) -> void:
	_source_navigation_ready = true
	set_meta("nacht_navigation_ready", true)
	set_meta("nacht_navigation_polygon_count", polygons)
	set_meta("nacht_navigation_vertex_count", vertices)
	_activate_source_gameplay()

func _on_source_navigation_failed(reason: String) -> void:
	_source_navigation_ready = false
	set_meta("nacht_navigation_ready", false)
	set_meta("nacht_navigation_failure", reason)
	push_error("NACHT_FULL_MAP: navigation failed " + reason)

func _activate_source_gameplay() -> void:
	if _source_gameplay_ready:
		return
	if not _source_navigation_ready or _source_zombie_spawn_candidates.size() != 22:
		return
	var round_manager := get_node_or_null("RoundManager")
	if round_manager == null:
		push_error("NACHT_FULL_MAP: RoundManager missing for source gameplay")
		return
	round_manager.set("auto_start", true)
	if round_manager.has_method("reset_network_match"):
		round_manager.call("reset_network_match")
	_source_gameplay_ready = true
	set_meta("nacht_gameplay_ready", true)
	set_meta("nacht_source_zombie_spawn_count", 22)
	set_meta("nacht_spawn_authority", "NACHT_UMAP_ZombieSpawner_C")
	get_tree().set_meta("nacht_gameplay_ready", true)
	print(
		"XZOGOT_NACHT_GAMEPLAY_GREEN spawns=22 nav_polygons=",
		int(get_meta("nacht_navigation_polygon_count", 0)),
		" rounds=enabled"
	)

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

func _godot_player_basis_from_source_anchor(anchor: Node3D) -> Basis:
	# UE characters are X-forward / Z-up. The source anchor already carries the
	# XZIEL axis conversion in global space, so its +X column is the desired
	# Godot forward vector and its +Z column is the desired Godot up vector.
	# Rebuild a native Godot X-right / Y-up / -Z-forward basis instead of
	# assigning the UE component basis directly to CharacterBody3D.
	var forward := anchor.global_basis.x.normalized()
	var up := anchor.global_basis.z.normalized()
	var z_axis := -forward
	var x_axis := up.cross(z_axis).normalized()
	if x_axis.length_squared() < 0.000001:
		x_axis = Vector3.RIGHT
	var y_axis := z_axis.cross(x_axis).normalized()
	return Basis(x_axis, y_axis, z_axis).orthonormalized()


func _place_player() -> void:
	var player := get_node_or_null("Player") as CharacterBody3D
	if player == null or _source_spawn_candidates.is_empty():
		return

	# Preserve source actor order. Do not lexically reshuffle Pavlov_Spawn10
	# ahead of Pavlov_Spawn2 and pretend that string ordering is gameplay
	# authority.
	var chosen := _source_spawn_candidates[0]
	player.global_basis = _godot_player_basis_from_source_anchor(chosen)

	# Pavlov_Spawn is rooted on its CollisionCapsule. The extracted anchor is
	# therefore the source capsule CENTER, while our CharacterBody3D origin is
	# at the feet and its CollisionShape3D center is +0.88 m. Align capsule
	# center to capsule center after converting UE X-forward/Z-up orientation
	# into native Godot Y-up character orientation.
	var collision := player.get_node_or_null("CollisionShape3D") as CollisionShape3D
	if collision != null:
		player.global_position = (
			chosen.global_position
			- player.global_basis * collision.position
		)
	else:
		player.global_position = chosen.global_position

	player.set_meta(
		"nacht_source_spawn_object",
		chosen.get_meta("source_object_path", "")
	)
	player.set_meta(
		"nacht_source_spawn_anchor_position",
		chosen.global_position
	)
	player.set_meta(
		"nacht_source_spawn_candidate_count",
		_source_spawn_candidates.size()
	)
	var placement_capsule_error := -1.0
	if collision != null:
		placement_capsule_error = collision.global_position.distance_to(
			chosen.global_position
		)
	player.set_meta(
		"nacht_source_spawn_capsule_error_at_placement_m",
		placement_capsule_error
	)
	player.set_meta(
		"nacht_source_spawn_up_dot_at_placement",
		player.global_basis.y.dot(Vector3.UP)
	)
	print(
		"XZOGOT_NACHT_PLAYER_SOURCE_SPAWN ",
		"anchor=", chosen.global_position,
		" player_feet=", player.global_position,
		" placement_capsule_error_m=", placement_capsule_error,
		" up_dot=", player.global_basis.y.dot(Vector3.UP),
		" candidates=", _source_spawn_candidates.size(),
		" source=", chosen.get_meta("source_object_path", "")
	)

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
