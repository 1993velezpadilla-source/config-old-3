extends SceneTree

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("NACHT_FULL_MAP_PROBE: " + message)
	quit(code)

func _read_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	return parsed as Dictionary if parsed is Dictionary else {}

func _run() -> void:
	var packed := load("res://nacht_full_map.tscn") as PackedScene
	if packed == null:
		_fail(2, "nacht_full_map.tscn missing")
		return

	var scene := packed.instantiate()
	root.add_child(scene)

	var ready := false
	for _i in range(2400):
		await create_timer(0.05).timeout
		if bool(scene.get_meta("nacht_full_map_ready", false)):
			ready = true
			break
	if not ready:
		_fail(3, "full map did not become ready")
		return

	var packages := int(scene.get_meta("source_package_count", -1))
	var meshes := int(scene.get_meta("source_mesh_count", -1))
	var source_instances := int(scene.get_meta("source_instance_count", -1))
	var runtime_instances := int(scene.get_meta("runtime_instance_count", -1))
	var missing_meshes := int(scene.get_meta("missing_mesh_count", -1))
	var source_actors := int(scene.get_meta("source_actor_anchor_count", -1))
	var runtime_actors := int(scene.get_meta("runtime_actor_anchor_count", -1))
	var collisions := int(scene.get_meta("world_collision_count", -1))
	var source_lights := int(scene.get_meta("source_light_count", -1))
	var runtime_lights := int(scene.get_meta("runtime_light_count", -1))
	var complete_textures := int(scene.get_meta("source_complete_texture_catalog_count", -1))
	var texture_failures := int(scene.get_meta("source_texture_load_failures", -1))
	var textured_materials := int(scene.get_meta("source_material_textured_count", -1))
	var source_particles := int(scene.get_meta("source_particle_component_count", -1))
	var particle_authority := int(scene.get_meta("runtime_particle_authority_count", -1))
	var source_particle_systems := int(scene.get_meta("source_particle_system_count", -1))
	var particle_graph_authority := int(scene.get_meta("runtime_particle_graph_authority_count", -1))
	var source_environment := int(scene.get_meta("source_environment_component_count", -1))
	var environment_authority := int(scene.get_meta("runtime_environment_authority_count", -1))
	var source_audio_components := int(scene.get_meta("source_audio_component_count", -1))
	var audio_authority := int(scene.get_meta("runtime_audio_authority_count", -1))
	var source_cues := int(scene.get_meta("source_sound_cue_count", -1))
	var cue_authority := int(scene.get_meta("runtime_sound_cue_authority_count", -1))
	var source_audio_runtime := bool(scene.get_meta("source_audio_runtime_ready", false))
	var source_audio_stream_mount := bool(scene.get_meta("source_audio_stream_mount_ready", false))
	var source_audio_players := int(scene.get_meta("source_audio_runtime_player_count", -1))
	var source_audio_streams := int(scene.get_meta("source_audio_runtime_stream_count", -1))
	var source_audio_event_authority := int(scene.get_meta("source_audio_event_authority_count", 0))
	var source_audio_event_index := int(scene.get_meta("source_audio_event_index_count", 0))
	var placed_particle_systems := int(scene.get_meta("runtime_placed_particle_system_count", 0))
	var placed_particle_node_types := int(scene.get_meta("runtime_placed_particle_node_type_count", 0))
	var runtime_environment_components := int(scene.get_meta("runtime_environment_component_count", 0))
	var runtime_environment_visual_nodes := int(scene.get_meta("runtime_environment_visual_node_count", 0))
	var source_environment_runtime := bool(scene.get_meta("source_environment_runtime_ready", false))
	var source_environment_fog_runtime := bool(scene.get_meta("source_environment_fog_runtime_ready", false))
	var source_environment_reflection_runtime := bool(scene.get_meta("source_environment_reflection_runtime_ready", false))
	var staged_runtime := FileAccess.file_exists(
		"res://assets/benchmarks/nacht_chronicles/nacht-audio-runtime-authority.json"
	)
	var staged_manifest := _read_json(
		"res://assets/benchmarks/nacht_chronicles/source_manifest.json"
	)
	var expected_texture_count := 1581
	if staged_runtime:
		expected_texture_count = int(staged_manifest.get("sourceTextures", -1))

	if packages != 3871:
		_fail(4, "package authority mismatch " + str(packages))
		return
	if meshes <= 0:
		_fail(5, "no source meshes")
		return
	if source_instances <= 0 or runtime_instances != source_instances:
		_fail(6, "instance coverage mismatch %d/%d" % [runtime_instances, source_instances])
		return
	if missing_meshes != 0:
		_fail(7, "missing mesh bridge count " + str(missing_meshes))
		return
	if source_actors != 11023 or runtime_actors != source_actors:
		_fail(8, "actor coverage mismatch %d/%d expected=11023" % [runtime_actors, source_actors])
		return
	if get_nodes_in_group("nacht_source_actor").size() != source_actors:
		_fail(9, "actor runtime group mismatch")
		return
	if collisions <= 0:
		_fail(10, "no world collision generated")
		return
	if source_lights <= 0 or runtime_lights != source_lights:
		_fail(11, "light coverage mismatch %d/%d" % [runtime_lights, source_lights])
		return
	if expected_texture_count <= 0:
		_fail(14, "staged source texture authority missing")
		return
	if complete_textures != expected_texture_count:
		_fail(
			14,
			"complete texture catalog mismatch %d/%d"
			% [complete_textures, expected_texture_count]
		)
		return
	if texture_failures != 0:
		_fail(15, "source texture load failures " + str(texture_failures))
		return
	if textured_materials <= 0:
		_fail(16, "no source materials resolved with textures")
		return
	if source_particles <= 0 or particle_authority != source_particles:
		_fail(17, "particle authority coverage mismatch %d/%d" % [particle_authority, source_particles])
		return
	if source_particle_systems != 39 or particle_graph_authority != source_particle_systems:
		_fail(18, "particle graph authority coverage mismatch %d/%d expected=39" % [particle_graph_authority, source_particle_systems])
		return
	if source_environment < 0 or environment_authority != source_environment:
		_fail(21, "environment authority coverage mismatch %d/%d" % [environment_authority, source_environment])
		return
	if source_audio_components <= 0 or audio_authority != source_audio_components:
		_fail(19, "audio placement authority coverage mismatch %d/%d" % [audio_authority, source_audio_components])
		return
	if source_cues != 102 or cue_authority != source_cues:
		_fail(20, "SoundCue authority coverage mismatch %d/%d expected=102" % [cue_authority, source_cues])
		return
	if staged_runtime:
		if not source_audio_stream_mount or source_audio_players != 3 or source_audio_streams != 3:
			_fail(
				22,
				"source audio stream mount mismatch ready=%s players=%d streams=%d"
				% [str(source_audio_stream_mount), source_audio_players, source_audio_streams]
			)
			return
		if source_audio_event_authority <= 0 or source_audio_event_index <= 0:
			_fail(
				23,
				"staged audio event authority missing authority=%d index=%d"
				% [source_audio_event_authority, source_audio_event_index]
			)
			return
		if placed_particle_systems <= 0 or placed_particle_node_types <= 0:
			_fail(
				24,
				"staged particle runtime authority missing systems=%d nodeTypes=%d"
				% [placed_particle_systems, placed_particle_node_types]
			)
			return
		if runtime_environment_components != 2:
			_fail(
				25,
				"staged environment runtime authority mismatch %d/2"
				% runtime_environment_components
			)
			return
		if not source_audio_runtime:
			_fail(26, "staged source audio semantics are not runtime-ready")
			return
		if (
			not source_environment_runtime
			or not source_environment_fog_runtime
			or not source_environment_reflection_runtime
			or runtime_environment_visual_nodes != 2
		):
			_fail(
				27,
				"source environment runtime incomplete ready=%s fog=%s reflection=%s nodes=%d"
				% [
					str(source_environment_runtime),
					str(source_environment_fog_runtime),
					str(source_environment_reflection_runtime),
					runtime_environment_visual_nodes,
				]
			)
			return
		if get_nodes_in_group("nacht_source_environment_runtime").size() != 2:
			_fail(28, "source environment runtime node coverage mismatch")
			return

	var player := scene.get_node_or_null("Player") as CharacterBody3D
	var weapon := scene.get_node_or_null("Player/Weapon")
	var round_manager := scene.get_node_or_null("RoundManager")
	if player == null or weapon == null or round_manager == null:
		_fail(12, "player weapon or round manager missing")
		return
	if bool(round_manager.get("auto_start")):
		_fail(13, "round manager must remain gated until Nacht source spawns/nav are wired")
		return

	print(
		"XZOGOT_NACHT_FULL_MAP_PROBE_GREEN ",
		"packages=", packages,
		" meshes=", meshes,
		" instances=", runtime_instances,
		" actors=", runtime_actors,
		" collisions=", collisions,
		" lights=", runtime_lights,
		" textures=", complete_textures,
		" expected_textures=", expected_texture_count,
		" textured_materials=", textured_materials,
		" particles_authority=", particle_authority,
		" particle_graphs_authority=", particle_graph_authority,
		" environment_authority=", environment_authority,
		" audio_authority=", audio_authority,
		" cues_authority=", cue_authority,
		" particles_rendered=", bool(scene.get_meta("particle_visual_runtime_ready", false)),
		" source_audio_stream_mount=", source_audio_stream_mount,
		" source_audio_runtime=", source_audio_runtime,
		" source_audio_players=", source_audio_players,
		" source_audio_streams=", source_audio_streams,
		" source_audio_events=", source_audio_event_index,
		" placed_particle_systems=", placed_particle_systems,
		" placed_particle_node_types=", placed_particle_node_types,
		" runtime_environment_components=", runtime_environment_components,
		" runtime_environment_visual_nodes=", runtime_environment_visual_nodes,
		" source_environment_runtime=", source_environment_runtime,
		" source_environment_fog_runtime=", source_environment_fog_runtime,
		" source_environment_reflection_runtime=", source_environment_reflection_runtime,
		" player=", player.global_position
	)
	scene.queue_free()
	await process_frame
	quit(0)
