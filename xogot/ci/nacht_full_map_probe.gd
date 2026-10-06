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
	var effective_materials := int(scene.get_meta("source_effective_material_count", -1))
	var effective_textured_materials := int(
		scene.get_meta("source_effective_material_textured_count", -1)
	)
	var effective_flat_fallbacks := int(
		scene.get_meta("source_effective_material_flat_fallback_count", -1)
	)
	var effective_source_color := int(
		scene.get_meta("source_effective_source_color_count", -1)
	)
	var effective_default_surface := int(
		scene.get_meta("source_effective_default_surface_count", -1)
	)
	var effective_unresolved_fallbacks := int(
		scene.get_meta("source_effective_unresolved_fallback_count", -1)
	)
	var effective_engine_defaults := int(
		scene.get_meta("source_effective_engine_default_count", -1)
	)
	var effective_sibling_semantic_hits := int(
		scene.get_meta("source_effective_sibling_semantic_hits", -1)
	)
	var particle_decoder_ready := bool(
		scene.get_meta("source_particle_decoder_ready", false)
	)
	var particle_decoded_systems := int(
		scene.get_meta("source_particle_decoded_system_count", -1)
	)
	var particle_decoded_nodes := int(
		scene.get_meta("source_particle_decoded_node_count", -1)
	)
	var particle_decoded_references := int(
		scene.get_meta("source_particle_decoded_reference_count", -1)
	)
	var particle_semantic_ready := bool(
		scene.get_meta("source_particle_semantic_runtime_ready", false)
	)
	var particle_semantic_systems := int(
		scene.get_meta("source_particle_semantic_runtime_count", -1)
	)
	var particle_semantic_placements := int(
		scene.get_meta("source_particle_semantic_placement_count", -1)
	)
	var particle_mystery_rate := float(
		scene.get_meta("source_particle_mystery_spawn_rate", -1.0)
	)
	var particle_mystery_lifetime_min := float(
		scene.get_meta("source_particle_mystery_lifetime_min", -1.0)
	)
	var particle_mystery_lifetime_max := float(
		scene.get_meta("source_particle_mystery_lifetime_max", -1.0)
	)
	var particle_mystery_peak := int(
		scene.get_meta("source_particle_mystery_peak_active", -1)
	)
	var particle_fire_pivot := scene.get_meta(
		"source_particle_fire_pivot_offset",
		Vector2.INF
	) as Vector2
	var particle_fire_speed_scale := scene.get_meta(
		"source_particle_fire_speed_scale",
		Vector2.INF
	) as Vector2
	var particle_fire_max_scale := scene.get_meta(
		"source_particle_fire_max_scale",
		Vector2.INF
	) as Vector2
	var particle_fire_lifetime_min := float(
		scene.get_meta("source_particle_fire_lifetime_min", -1.0)
	)
	var particle_fire_lifetime_max := float(
		scene.get_meta("source_particle_fire_lifetime_max", -1.0)
	)
	var particle_fire_radius := float(
		scene.get_meta("source_particle_fire_cylinder_radius_ue_cm", -1.0)
	)
	var particle_fire_subuv_max := float(
		scene.get_meta("source_particle_fire_subuv_max_index", -1.0)
	)
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
	var source_environment_mounted := bool(scene.get_meta("source_environment_runtime_mounted", false))
	var source_environment_exact := bool(scene.get_meta("source_environment_visual_exact", false))
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
		if not particle_decoder_ready:
			_fail(32, "Cascade source-value decoder did not become runtime-ready")
			return
		if (
			particle_decoded_systems != 39
			or particle_decoded_nodes != 1327
			or particle_decoded_references != 643
		):
			_fail(
				32,
				"Cascade decoder coverage mismatch systems=%d nodes=%d refs=%d"
				% [
					particle_decoded_systems,
					particle_decoded_nodes,
					particle_decoded_references,
				]
			)
			return
		if not particle_semantic_ready:
			_fail(34, "source-complete Cascade semantic runtime is not ready")
			return
		if particle_semantic_systems != 2 or particle_semantic_placements != 5:
			_fail(
				34,
				"Cascade semantic runtime coverage mismatch systems=%d placements=%d"
				% [particle_semantic_systems, particle_semantic_placements]
			)
			return
		if get_nodes_in_group("nacht_source_particle_semantic").size() != 5:
			_fail(34, "Cascade semantic placement group mismatch")
			return
		if (
			not is_equal_approx(particle_mystery_rate, 10.0)
			or not is_equal_approx(particle_mystery_lifetime_min, 5.0)
			or not is_equal_approx(particle_mystery_lifetime_max, 8.0)
			or particle_mystery_peak != 82
		):
			_fail(
				34,
				"Cascade mystery beam values mismatch rate=%s lifetime=%s..%s peak=%d"
				% [
					particle_mystery_rate,
					particle_mystery_lifetime_min,
					particle_mystery_lifetime_max,
					particle_mystery_peak,
				]
			)
			return
		if (
			not particle_fire_pivot.is_equal_approx(Vector2(0.0, -0.5))
			or not particle_fire_speed_scale.is_equal_approx(Vector2(1.0, 1.0))
			or not particle_fire_max_scale.is_equal_approx(Vector2(10.0, 10.0))
			or not is_equal_approx(particle_fire_lifetime_min, 1.0)
			or not is_equal_approx(particle_fire_lifetime_max, 1.75)
			or not is_equal_approx(particle_fire_radius, 50.0)
			or not is_equal_approx(particle_fire_subuv_max, 47.0)
		):
			_fail(
				34,
				"Cascade big fire values mismatch pivot=%s speed=%s max=%s lifetime=%s..%s radius=%s subuv=%s"
				% [
					particle_fire_pivot,
					particle_fire_speed_scale,
					particle_fire_max_scale,
					particle_fire_lifetime_min,
					particle_fire_lifetime_max,
					particle_fire_radius,
					particle_fire_subuv_max,
				]
			)
			return
		if effective_unresolved_fallbacks != 0:
			_fail(
				33,
				"effective material unresolved fallbacks remain %d"
				% effective_unresolved_fallbacks
			)
			return
		if effective_sibling_semantic_hits <= 0:
			_fail(33, "source sibling material semantic recovery produced no effective bindings")
			return
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
			not source_environment_mounted
			or not source_environment_fog_runtime
			or not source_environment_reflection_runtime
			or runtime_environment_visual_nodes != 2
		):
			_fail(
				27,
				"source environment mount incomplete mounted=%s fog=%s reflection=%s nodes=%d"
				% [
					str(source_environment_mounted),
					str(source_environment_fog_runtime),
					str(source_environment_reflection_runtime),
					runtime_environment_visual_nodes,
				]
			)
			return
		# Do not let a stock Godot fallback masquerade as exact UE4.21 parity.
		if source_environment_runtime or source_environment_exact:
			_fail(
				28,
				"environment exact-parity flag flipped before semantic gaps were closed"
			)
			return
		var environment_nodes := get_nodes_in_group("nacht_source_environment_runtime")
		if environment_nodes.size() != 2:
			_fail(29, "source environment runtime node coverage mismatch")
			return
		var fog_node: WorldEnvironment = null
		var reflection_node: ReflectionProbe = null
		for runtime_node: Node in environment_nodes:
			var component_type := str(
				runtime_node.get_meta("source_environment_component_type", "")
			)
			if component_type == "exponential_height_fog" and runtime_node is WorldEnvironment:
				fog_node = runtime_node as WorldEnvironment
			elif component_type == "reflection_capture" and runtime_node is ReflectionProbe:
				reflection_node = runtime_node as ReflectionProbe
		if fog_node == null or reflection_node == null or fog_node.environment == null:
			_fail(30, "source environment runtime node types incomplete")
			return
		var fog_environment := fog_node.environment
		if fog_environment.fog_enabled:
			_fail(31, "non-exact stock Godot fog fallback must default disabled")
			return
		if bool(fog_node.get_meta("approximate_fog_fallback_enabled", true)):
			_fail(31, "approximate Nacht fog fallback metadata unexpectedly enabled")
			return
		if (
			absf(fog_environment.fog_density - 0.1) > 0.00001
			or absf(float(fog_node.get_meta("source_fog_height_falloff", -1.0)) - 2.0) > 0.00001
			or absf(float(fog_node.get_meta("source_fog_max_opacity", -1.0)) - 0.2) > 0.00001
			or absf(float(fog_node.get_meta("source_fog_start_distance_m", -1.0)) - 3.0) > 0.00001
			or absf(float(fog_node.get_meta("source_volumetric_fog_distance_m", -1.0)) - 10.0) > 0.00001
		):
			_fail(31, "source fog runtime inputs do not match authority")
			return
		var reflection_radius_m := float(
			reflection_node.get_meta("source_influence_radius_m", -1.0)
		)
		if absf(reflection_radius_m - 51.83467) > 0.0001:
			_fail(32, "source reflection radius runtime mismatch " + str(reflection_radius_m))
			return
		var expected_probe_size := Vector3.ONE * reflection_radius_m * 2.0
		if reflection_node.size.distance_to(expected_probe_size) > 0.0001:
			_fail(33, "source reflection probe diameter mismatch")
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

	var spawn_candidate_count := int(
		player.get_meta("nacht_source_spawn_candidate_count", -1)
	)
	if spawn_candidate_count != 10:
		_fail(
			26,
			"source spawn candidate count mismatch %d/10"
			% spawn_candidate_count
		)
		return

	var collision := player.get_node_or_null("CollisionShape3D") as CollisionShape3D
	var raw_spawn_anchor: Variant = player.get_meta(
		"nacht_source_spawn_anchor_position",
		null
	)
	var placement_capsule_error := float(
		player.get_meta(
			"nacht_source_spawn_capsule_error_at_placement_m",
			-1.0
		)
	)
	var placement_up_dot := float(
		player.get_meta(
			"nacht_source_spawn_up_dot_at_placement",
			-1.0
		)
	)
	if (
		collision == null
		or not (raw_spawn_anchor is Vector3)
		or placement_capsule_error < 0.0
	):
		_fail(27, "source spawn capsule alignment metadata missing")
		return
	var spawn_anchor := raw_spawn_anchor as Vector3
	if placement_capsule_error > 0.001:
		_fail(
			28,
			"source spawn capsule placement mismatch error_m=%f"
			% placement_capsule_error
		)
		return
	if placement_up_dot < 0.999:
		_fail(
			28,
			"source spawn character is not Godot Y-up dot=%f"
			% placement_up_dot
		)
		return

	# After placement, player physics is intentionally live. Gravity and
	# move_and_slide() may settle the capsule onto source collision before this
	# probe reaches it, so the current offset is diagnostic rather than a
	# placement-authority failure.
	var settled_capsule_delta := collision.global_position.distance_to(
		spawn_anchor
	)

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
		" effective_materials=", effective_materials,
		" effective_textured_materials=", effective_textured_materials,
		" effective_flat_fallbacks=", effective_flat_fallbacks,
		" effective_source_color=", effective_source_color,
		" effective_default_surface=", effective_default_surface,
		" effective_engine_defaults=", effective_engine_defaults,
		" effective_sibling_semantic_hits=", effective_sibling_semantic_hits,
		" effective_unresolved_fallbacks=", effective_unresolved_fallbacks,
		" cascade_decoder=", particle_decoder_ready,
		" cascade_systems=", particle_decoded_systems,
		" cascade_nodes=", particle_decoded_nodes,
		" cascade_refs=", particle_decoded_references,
		" cascade_semantic_ready=", particle_semantic_ready,
		" cascade_semantic_systems=", particle_semantic_systems,
		" cascade_semantic_placements=", particle_semantic_placements,
		" fire_pivot=", particle_fire_pivot,
		" fire_speed_scale=", particle_fire_speed_scale,
		" fire_max_scale=", particle_fire_max_scale,
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
		" source_environment_mounted=", source_environment_mounted,
		" source_environment_exact=", source_environment_exact,
		" source_environment_fog_runtime=", source_environment_fog_runtime,
		" source_environment_reflection_runtime=", source_environment_reflection_runtime,
		" spawn_candidates=", spawn_candidate_count,
		" spawn_capsule_error_at_placement_m=", placement_capsule_error,
		" spawn_up_dot_at_placement=", placement_up_dot,
		" spawn_settled_capsule_delta_m=", settled_capsule_delta,
		" player=", player.global_position
	)
	scene.queue_free()
	await process_frame
	quit(0)
