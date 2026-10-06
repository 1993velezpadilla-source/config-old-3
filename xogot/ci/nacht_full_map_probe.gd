extends SceneTree

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("NACHT_FULL_MAP_PROBE: " + message)
	quit(code)

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
	if complete_textures != 1581:
		_fail(14, "complete texture catalog mismatch " + str(complete_textures))
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
		" textured_materials=", textured_materials,
		" particles_authority=", particle_authority,
		" particle_graphs_authority=", particle_graph_authority,
		" environment_authority=", environment_authority,
		" audio_authority=", audio_authority,
		" cues_authority=", cue_authority,
		" particles_rendered=", bool(scene.get_meta("particle_visual_runtime_ready", false)),
		" source_audio_runtime=", bool(scene.get_meta("source_audio_runtime_ready", false)),
		" source_environment_runtime=", bool(scene.get_meta("source_environment_runtime_ready", false)),
		" player=", player.global_position
	)
	scene.queue_free()
	await process_frame
	quit(0)
