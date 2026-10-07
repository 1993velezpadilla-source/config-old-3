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
	var particle_bonefire_size_min := scene.get_meta(
		"source_particle_bonefire_start_size_min_ue_cm",
		Vector3.INF
	) as Vector3
	var particle_bonefire_size_max := scene.get_meta(
		"source_particle_bonefire_start_size_max_ue_cm",
		Vector3.INF
	) as Vector3
	var particle_bonefire_lifetime_min := float(
		scene.get_meta("source_particle_bonefire_lifetime_min", -1.0)
	)
	var particle_bonefire_lifetime_max := float(
		scene.get_meta("source_particle_bonefire_lifetime_max", -1.0)
	)
	var particle_bonefire_radius := float(
		scene.get_meta("source_particle_bonefire_cylinder_radius_ue_cm", -1.0)
	)
	var particle_bonefire_subuv_max := float(
		scene.get_meta("source_particle_bonefire_subuv_max_index", -1.0)
	)
	var particle_bonefire3_size_min := scene.get_meta(
		"source_particle_bonefire3_start_size_min_ue_cm", Vector3.INF
	) as Vector3
	var particle_bonefire3_size_max := scene.get_meta(
		"source_particle_bonefire3_start_size_max_ue_cm", Vector3.INF
	) as Vector3
	var particle_bonefire3_life_multiplier_min := scene.get_meta(
		"source_particle_bonefire3_life_multiplier_min", Vector3.INF
	) as Vector3
	var particle_bonefire3_life_multiplier_max := scene.get_meta(
		"source_particle_bonefire3_life_multiplier_max", Vector3.INF
	) as Vector3
	var particle_bonefire3_lifetime_min := float(
		scene.get_meta("source_particle_bonefire3_lifetime_min", -1.0)
	)
	var particle_bonefire3_lifetime_max := float(
		scene.get_meta("source_particle_bonefire3_lifetime_max", -1.0)
	)
	var particle_bonefire3_radius := float(
		scene.get_meta("source_particle_bonefire3_cylinder_radius_ue_cm", -1.0)
	)
	var particle_bonefire3_subuv_fps := float(
		scene.get_meta("source_particle_bonefire3_subuv_frame_rate", -1.0)
	)
	var particle_bonefire3_rgb_values := int(
		scene.get_meta("source_particle_bonefire3_rgb_table_value_count", -1)
	)
	var particle_bonefire3_alpha_values := int(
		scene.get_meta("source_particle_bonefire3_alpha_table_value_count", -1)
	)
	var particle_pap_wheel_emitters := int(
		scene.get_meta("source_particle_pap_wheel_emitter_count", -1)
	)
	var particle_pap_wheel_lifetime := float(
		scene.get_meta("source_particle_pap_wheel_lifetime_seconds", -1.0)
	)
	var particle_pap_wheel_size_min := scene.get_meta(
		"source_particle_pap_wheel_start_size_min_ue_cm", Vector3.INF
	) as Vector3
	var particle_pap_wheel_size_max := scene.get_meta(
		"source_particle_pap_wheel_start_size_max_ue_cm", Vector3.INF
	) as Vector3
	var particle_pap_wheel_spawn_rate := float(
		scene.get_meta("source_particle_pap_wheel_spawn_rate", -1.0)
	)
	var particle_pap_wheel_burst_count := int(
		scene.get_meta("source_particle_pap_wheel_burst_count", -1)
	)
	var particle_pap_wheel_rotation_rate_min := float(
		scene.get_meta("source_particle_pap_wheel_rotation_rate_min", 999.0)
	)
	var particle_pap_wheel_rotation_rate_max := float(
		scene.get_meta("source_particle_pap_wheel_rotation_rate_max", -999.0)
	)
	var particle_pap_wheel_velocity_life_min := scene.get_meta(
		"source_particle_pap_wheel_velocity_life_min", Vector3.INF
	) as Vector3
	var particle_pap_wheel_velocity_life_time_scale := float(
		scene.get_meta("source_particle_pap_wheel_velocity_life_time_scale", -1.0)
	)
	var particle_pap_wheel_size_life_table_values := int(
		scene.get_meta("source_particle_pap_wheel_size_life_table_value_count", -1)
	)
	var particle_mystery_fog_lifetime_min := float(
		scene.get_meta("source_particle_mystery_fog_lifetime_min", -1.0)
	)
	var particle_mystery_fog_lifetime_max := float(
		scene.get_meta("source_particle_mystery_fog_lifetime_max", -1.0)
	)
	var particle_mystery_fog_location_min := scene.get_meta(
		"source_particle_mystery_fog_location_min_ue_cm", Vector3.INF
	) as Vector3
	var particle_mystery_fog_location_max := scene.get_meta(
		"source_particle_mystery_fog_location_max_ue_cm", Vector3.INF
	) as Vector3
	var particle_mystery_fog_size_min := scene.get_meta(
		"source_particle_mystery_fog_start_size_min_ue_cm", Vector3.INF
	) as Vector3
	var particle_mystery_fog_size_max := scene.get_meta(
		"source_particle_mystery_fog_start_size_max_ue_cm", Vector3.INF
	) as Vector3
	var particle_mystery_fog_spawn_rate := float(
		scene.get_meta("source_particle_mystery_fog_spawn_rate", -1.0)
	)
	var particle_mystery_fog_subuv_fps := float(
		scene.get_meta("source_particle_mystery_fog_subuv_frame_rate", -1.0)
	)
	var particle_mystery_fog_alpha_values := int(
		scene.get_meta("source_particle_mystery_fog_alpha_table_value_count", -1)
	)
	var particle_mystery_fog_peak := int(
		scene.get_meta("source_particle_mystery_fog_peak_active", -1)
	)
	var particle_mystery_fog_life_multiplier_min := scene.get_meta(
		"source_particle_mystery_fog_life_multiplier_min", Vector3.INF
	) as Vector3
	var particle_mystery_fog_life_multiplier_max := scene.get_meta(
		"source_particle_mystery_fog_life_multiplier_max", Vector3.INF
	) as Vector3
	var particle_mystery_fog_life_multiplier_values := int(
		scene.get_meta("source_particle_mystery_fog_life_multiplier_table_value_count", -1)
	)
	var particle_mystery_fog_color_min := scene.get_meta(
		"source_particle_mystery_fog_color_min", Vector3.INF
	) as Vector3
	var particle_mystery_fog_color_max := scene.get_meta(
		"source_particle_mystery_fog_color_max", Vector3.INF
	) as Vector3
	var particle_mystery_fog_rgb_values := int(
		scene.get_meta("source_particle_mystery_fog_rgb_table_value_count", -1)
	)
	var particle_mystery_fog_alpha_max := float(
		scene.get_meta("source_particle_mystery_fog_alpha_max", -1.0)
	)
	var particle_mystery_fog_velocity_life_min := scene.get_meta(
		"source_particle_mystery_fog_velocity_life_min", Vector3.INF
	) as Vector3
	var particle_mystery_fog_velocity_life_max := scene.get_meta(
		"source_particle_mystery_fog_velocity_life_max", Vector3.INF
	) as Vector3
	var particle_mystery_fog_velocity_life_time_scale := float(
		scene.get_meta("source_particle_mystery_fog_velocity_life_time_scale", -1.0)
	)
	var particle_mystery_fog_start_velocity_min := scene.get_meta(
		"source_particle_mystery_fog_start_velocity_min_ue_cm", Vector3.INF
	) as Vector3
	var particle_mystery_fog_start_velocity_max := scene.get_meta(
		"source_particle_mystery_fog_start_velocity_max_ue_cm", Vector3.INF
	) as Vector3
	var particle_mystery_inside_lifetime_min := float(
		scene.get_meta("source_particle_mystery_inside_lifetime_min", -1.0)
	)
	var particle_mystery_inside_lifetime_max := float(
		scene.get_meta("source_particle_mystery_inside_lifetime_max", -1.0)
	)
	var particle_mystery_inside_location_min := scene.get_meta(
		"source_particle_mystery_inside_location_min_ue_cm", Vector3.INF
	) as Vector3
	var particle_mystery_inside_location_max := scene.get_meta(
		"source_particle_mystery_inside_location_max_ue_cm", Vector3.INF
	) as Vector3
	var particle_mystery_inside_size_min := scene.get_meta(
		"source_particle_mystery_inside_start_size_min_ue_cm", Vector3.INF
	) as Vector3
	var particle_mystery_inside_size_max := scene.get_meta(
		"source_particle_mystery_inside_start_size_max_ue_cm", Vector3.INF
	) as Vector3
	var particle_mystery_inside_spawn_rate := float(
		scene.get_meta("source_particle_mystery_inside_spawn_rate", -1.0)
	)
	var particle_mystery_inside_velocity_min := scene.get_meta(
		"source_particle_mystery_inside_start_velocity_min_ue_cm", Vector3.INF
	) as Vector3
	var particle_mystery_inside_velocity_max := scene.get_meta(
		"source_particle_mystery_inside_start_velocity_max_ue_cm", Vector3.INF
	) as Vector3
	var particle_mystery_inside_rgb_values := int(
		scene.get_meta("source_particle_mystery_inside_rgb_table_value_count", -1)
	)
	var particle_mystery_inside_alpha_values := int(
		scene.get_meta("source_particle_mystery_inside_alpha_table_value_count", -1)
	)
	var particle_mystery_inside_orbit_enabled := bool(
		scene.get_meta("source_particle_mystery_inside_orbit_enabled", true)
	)
	var particle_mystery_inside_orbit_offset_min := scene.get_meta(
		"source_particle_mystery_inside_orbit_offset_min", Vector3.INF
	) as Vector3
	var particle_mystery_inside_orbit_offset_max := scene.get_meta(
		"source_particle_mystery_inside_orbit_offset_max", Vector3.INF
	) as Vector3
	var particle_mystery_inside_gpu_inv_max_size := scene.get_meta(
		"source_particle_mystery_inside_gpu_inv_max_size", Vector2.INF
	) as Vector2
	var particle_mystery_inside_gpu_inv_rotation_scale := float(
		scene.get_meta("source_particle_mystery_inside_gpu_inv_rotation_rate_scale", -1.0)
	)
	var particle_mystery_inside_gpu_max_lifetime := float(
		scene.get_meta("source_particle_mystery_inside_gpu_max_lifetime", -1.0)
	)
	var particle_mystery_inside_gpu_max_particles := int(
		scene.get_meta("source_particle_mystery_inside_gpu_max_particle_count", -1)
	)
	var particle_mystery_inside_gpu_rotation_scale := float(
		scene.get_meta("source_particle_mystery_inside_gpu_rotation_rate_scale", -1.0)
	)
	var particle_mystery_inside_gpu_color_samples := int(
		scene.get_meta("source_particle_mystery_inside_gpu_quantized_color_sample_count", -1)
	)
	var particle_fire_smoke_lifetime_min := float(
		scene.get_meta("source_particle_fire_smoke_lifetime_min", -1.0)
	)
	var particle_fire_smoke_lifetime_max := float(
		scene.get_meta("source_particle_fire_smoke_lifetime_max", -1.0)
	)
	var particle_fire_smoke_radius := float(
		scene.get_meta("source_particle_fire_smoke_cylinder_radius_ue_cm", -1.0)
	)
	var particle_fire_smoke_pivot := scene.get_meta(
		"source_particle_fire_smoke_pivot_offset", Vector2.INF
	) as Vector2
	var particle_fire_smoke_life_multiplier_min := scene.get_meta(
		"source_particle_fire_smoke_life_multiplier_min", Vector3.INF
	) as Vector3
	var particle_fire_smoke_life_multiplier_max := scene.get_meta(
		"source_particle_fire_smoke_life_multiplier_max", Vector3.INF
	) as Vector3
	var particle_fire_smoke_speed_scale := scene.get_meta(
		"source_particle_fire_smoke_speed_scale", Vector2.INF
	) as Vector2
	var particle_fire_smoke_max_scale := scene.get_meta(
		"source_particle_fire_smoke_max_scale", Vector2.INF
	) as Vector2
	var particle_fire_smoke_size_min := scene.get_meta(
		"source_particle_fire_smoke_start_size_min_ue_cm", Vector3.INF
	) as Vector3
	var particle_fire_smoke_size_max := scene.get_meta(
		"source_particle_fire_smoke_start_size_max_ue_cm", Vector3.INF
	) as Vector3
	var particle_fire_smoke_subuv_fps := float(
		scene.get_meta("source_particle_fire_smoke_subuv_frame_rate", -1.0)
	)
	var particle_fire_smoke_velocity_min := scene.get_meta(
		"source_particle_fire_smoke_start_velocity_min_ue_cm", Vector3.INF
	) as Vector3
	var particle_fire_smoke_velocity_max := scene.get_meta(
		"source_particle_fire_smoke_start_velocity_max_ue_cm", Vector3.INF
	) as Vector3
	var particle_fire_smoke_rgb_values := int(
		scene.get_meta("source_particle_fire_smoke_rgb_table_value_count", -1)
	)
	var particle_fire_smoke_alpha_values := int(
		scene.get_meta("source_particle_fire_smoke_alpha_table_value_count", -1)
	)
	var particle_fire_smoke_spawn_rates: Array = scene.get_meta(
		"source_particle_fire_smoke_spawn_rates_by_lod", []
	) as Array
	var particle_fire_smoke_peaks: Array = scene.get_meta(
		"source_particle_fire_smoke_peak_active_by_lod", []
	) as Array
	var particle_pap_wheel_out_lifetime_min := float(
		scene.get_meta("source_particle_pap_wheel_out_lifetime_min", -1.0)
	)
	var particle_pap_wheel_out_lifetime_max := float(
		scene.get_meta("source_particle_pap_wheel_out_lifetime_max", -1.0)
	)
	var particle_pap_wheel_out_location_min := scene.get_meta(
		"source_particle_pap_wheel_out_location_min_ue_cm", Vector3.INF
	) as Vector3
	var particle_pap_wheel_out_location_max := scene.get_meta(
		"source_particle_pap_wheel_out_location_max_ue_cm", Vector3.INF
	) as Vector3
	var particle_pap_wheel_out_size_min := scene.get_meta(
		"source_particle_pap_wheel_out_start_size_min_ue_cm", Vector3.INF
	) as Vector3
	var particle_pap_wheel_out_size_max := scene.get_meta(
		"source_particle_pap_wheel_out_start_size_max_ue_cm", Vector3.INF
	) as Vector3
	var particle_pap_wheel_out_size_life_values := int(
		scene.get_meta("source_particle_pap_wheel_out_size_life_table_value_count", -1)
	)
	var particle_pap_wheel_out_size_life_time_scale := float(
		scene.get_meta("source_particle_pap_wheel_out_size_life_time_scale", -1.0)
	)
	var particle_pap_wheel_out_velocity_min := scene.get_meta(
		"source_particle_pap_wheel_out_start_velocity_min_ue_cm", Vector3.INF
	) as Vector3
	var particle_pap_wheel_out_velocity_max := scene.get_meta(
		"source_particle_pap_wheel_out_start_velocity_max_ue_cm", Vector3.INF
	) as Vector3
	var particle_pap_wheel_out_velocity_life_max := scene.get_meta(
		"source_particle_pap_wheel_out_velocity_life_max", Vector3.INF
	) as Vector3
	var particle_pap_wheel_out_velocity_life_values := int(
		scene.get_meta("source_particle_pap_wheel_out_velocity_life_table_value_count", -1)
	)
	var particle_pap_wheel_out_velocity_life_time_scale := float(
		scene.get_meta("source_particle_pap_wheel_out_velocity_life_time_scale", -1.0)
	)
	var particle_pap_wheel_out_accel_min := scene.get_meta(
		"source_particle_pap_wheel_out_acceleration_min_ue_cm", Vector3.INF
	) as Vector3
	var particle_pap_wheel_out_accel_max := scene.get_meta(
		"source_particle_pap_wheel_out_acceleration_max_ue_cm", Vector3.INF
	) as Vector3
	var particle_pap_wheel_out_accel_world := bool(
		scene.get_meta("source_particle_pap_wheel_out_acceleration_world_space", false)
	)
	var particle_pap_wheel_out_rotation_rate_min := float(
		scene.get_meta("source_particle_pap_wheel_out_rotation_rate_min", 999.0)
	)
	var particle_pap_wheel_out_rotation_rate_max := float(
		scene.get_meta("source_particle_pap_wheel_out_rotation_rate_max", -999.0)
	)
	var particle_pap_wheel_out_spawn_rate := float(
		scene.get_meta("source_particle_pap_wheel_out_spawn_rate", -1.0)
	)
	var particle_pap_wheel_out_spawn_rate_scale := float(
		scene.get_meta("source_particle_pap_wheel_out_spawn_rate_scale", -1.0)
	)
	var particle_pap_wheel_out_peak := int(
		scene.get_meta("source_particle_pap_wheel_out_peak_active", -1)
	)
	var particle_electric_beam_lifetime := float(
		scene.get_meta("source_particle_electric_beam_lifetime_seconds", -1.0)
	)
	var particle_electric_beam_size := scene.get_meta(
		"source_particle_electric_beam_start_size_ue_cm", Vector3.INF
	) as Vector3
	var particle_electric_beam_spawn_rate := float(
		scene.get_meta("source_particle_electric_beam_spawn_rate", -1.0)
	)
	var particle_electric_beam_noise_frequency := int(
		scene.get_meta("source_particle_electric_beam_noise_frequency", -1)
	)
	var particle_electric_beam_noise_lock_time := float(
		scene.get_meta("source_particle_electric_beam_noise_lock_time", -1.0)
	)
	var particle_electric_beam_noise_range := scene.get_meta(
		"source_particle_electric_beam_noise_range_max_ue_cm", Vector3.INF
	) as Vector3
	var particle_electric_beam_noise_speed := scene.get_meta(
		"source_particle_electric_beam_noise_speed_ue_cm", Vector3.INF
	) as Vector3
	var particle_electric_beam_noise_tangent := float(
		scene.get_meta("source_particle_electric_beam_noise_tangent_strength", -1.0)
	)
	var particle_electric_beam_source_strength := float(
		scene.get_meta("source_particle_electric_beam_source_strength", -1.0)
	)
	var particle_electric_beam_source_tangent := scene.get_meta(
		"source_particle_electric_beam_source_tangent", Vector3.INF
	) as Vector3
	var particle_electric_beam_target := scene.get_meta(
		"source_particle_electric_beam_target_ue_cm", Vector3.INF
	) as Vector3
	var particle_electric_beam_target_strength := float(
		scene.get_meta("source_particle_electric_beam_target_strength", -1.0)
	)
	var particle_electric_beam_target_tangent := scene.get_meta(
		"source_particle_electric_beam_target_tangent", Vector3.INF
	) as Vector3
	var particle_electric_beam_distance := float(
		scene.get_meta("source_particle_electric_beam_distance", -1.0)
	)
	var particle_electric_beam_interpolation_points := int(
		scene.get_meta("source_particle_electric_beam_interpolation_points", -1)
	)
	var particle_electric_beam_max_count := int(
		scene.get_meta("source_particle_electric_beam_max_beam_count", -1)
	)
	var particle_electric_beam_peak := int(
		scene.get_meta("source_particle_electric_beam_peak_active", -1)
	)
	var particle_acid_ball_mesh_burst := int(
		scene.get_meta("source_particle_acid_ball_mesh_burst_count", -1)
	)
	var particle_acid_ball_spawn_rate := float(
		scene.get_meta("source_particle_acid_ball_sprite_spawn_rate", -1.0)
	)
	var particle_acid_ball_lifetime_min := float(
		scene.get_meta("source_particle_acid_ball_sprite_lifetime_min", -1.0)
	)
	var particle_acid_ball_lifetime_max := float(
		scene.get_meta("source_particle_acid_ball_sprite_lifetime_max", -1.0)
	)
	var particle_acid_ball_mesh_size := scene.get_meta(
		"source_particle_acid_ball_mesh_size_ue_cm", Vector3.INF
	) as Vector3
	var particle_acid_ball_sprite_size_min := scene.get_meta(
		"source_particle_acid_ball_sprite_size_min_ue_cm", Vector3.INF
	) as Vector3
	var particle_acid_ball_sprite_size_max := scene.get_meta(
		"source_particle_acid_ball_sprite_size_max_ue_cm", Vector3.INF
	) as Vector3
	var particle_acid_ball_dynamic_count := int(
		scene.get_meta("source_particle_acid_ball_dynamic_param_count", -1)
	)
	var particle_acid_ball_dynamic_ranges: Array = scene.get_meta(
		"source_particle_acid_ball_dynamic_ranges", []
	) as Array
	var particle_acid_ball_dynamic_spawn_only: Array = scene.get_meta(
		"source_particle_acid_ball_dynamic_spawn_time_only", []
	) as Array
	var particle_acid_ball_dynamic_samples: Array = scene.get_meta(
		"source_particle_acid_ball_dynamic_samples", []
	) as Array
	var particle_acid_ball_peaks: Array = scene.get_meta(
		"source_particle_acid_ball_peak_active_by_emitter", []
	) as Array
	var particle_sparks_lifetime_min := float(
		scene.get_meta("source_particle_sparks_lifetime_min", -1.0)
	)
	var particle_sparks_lifetime_max := float(
		scene.get_meta("source_particle_sparks_lifetime_max", -1.0)
	)
	var particle_sparks_location_min := scene.get_meta(
		"source_particle_sparks_seeded_location_min_ue_cm", Vector3.INF
	) as Vector3
	var particle_sparks_location_max := scene.get_meta(
		"source_particle_sparks_seeded_location_max_ue_cm", Vector3.INF
	) as Vector3
	var particle_sparks_accel := scene.get_meta(
		"source_particle_sparks_acceleration_ue_cm", Vector3.INF
	) as Vector3
	var particle_sparks_accel_world := bool(
		scene.get_meta("source_particle_sparks_acceleration_world_space", false)
	)
	var particle_sparks_collision_enabled := bool(
		scene.get_meta("source_particle_sparks_collision_enabled", true)
	)
	var particle_sparks_resilience := float(
		scene.get_meta("source_particle_sparks_collision_resilience", -1.0)
	)
	var particle_sparks_resilience_scale := float(
		scene.get_meta("source_particle_sparks_collision_resilience_scale", -1.0)
	)
	var particle_sparks_speed_scale := scene.get_meta(
		"source_particle_sparks_speed_scale", Vector2.INF
	) as Vector2
	var particle_sparks_max_scale := scene.get_meta(
		"source_particle_sparks_max_scale", Vector2.INF
	) as Vector2
	var particle_sparks_size_min := scene.get_meta(
		"source_particle_sparks_start_size_min_ue_cm", Vector3.INF
	) as Vector3
	var particle_sparks_size_max := scene.get_meta(
		"source_particle_sparks_start_size_max_ue_cm", Vector3.INF
	) as Vector3
	var particle_sparks_spawn_rate := float(
		scene.get_meta("source_particle_sparks_spawn_rate", -1.0)
	)
	var particle_sparks_burst_count := int(
		scene.get_meta("source_particle_sparks_burst_count", -1)
	)
	var particle_sparks_burst_low := int(
		scene.get_meta("source_particle_sparks_burst_count_low", -1)
	)
	var particle_sparks_burst_time := float(
		scene.get_meta("source_particle_sparks_burst_time", -1.0)
	)
	var particle_sparks_burst_scale := float(
		scene.get_meta("source_particle_sparks_burst_scale", -1.0)
	)
	var particle_sparks_velocity_min := scene.get_meta(
		"source_particle_sparks_start_velocity_min_ue_cm", Vector3.INF
	) as Vector3
	var particle_sparks_velocity_max := scene.get_meta(
		"source_particle_sparks_start_velocity_max_ue_cm", Vector3.INF
	) as Vector3
	var particle_sparks_gpu_inv_max_size := scene.get_meta(
		"source_particle_sparks_gpu_inv_max_size", Vector2.INF
	) as Vector2
	var particle_sparks_gpu_max_lifetime := float(
		scene.get_meta("source_particle_sparks_gpu_max_lifetime", -1.0)
	)
	var particle_sparks_gpu_max_particles := int(
		scene.get_meta("source_particle_sparks_gpu_max_particle_count", -1)
	)
	var particle_sparks_gpu_collision_radius := float(
		scene.get_meta("source_particle_sparks_gpu_collision_radius_scale", -1.0)
	)
	var particle_sparks_gpu_collision_random := float(
		scene.get_meta("source_particle_sparks_gpu_collision_random_distribution", -1.0)
	)
	var particle_sparks_peaks: Array = scene.get_meta(
		"source_particle_sparks_peak_active_by_lod", []
	) as Array
	var particle_quad_smoke_lifetime_min := float(
		scene.get_meta("source_particle_quad_smoke_lifetime_min", -1.0)
	)
	var particle_quad_smoke_lifetime_max := float(
		scene.get_meta("source_particle_quad_smoke_lifetime_max", -1.0)
	)
	var particle_quad_smoke_size_min := scene.get_meta(
		"source_particle_quad_smoke_start_size_min_ue_cm", Vector3.INF
	) as Vector3
	var particle_quad_smoke_size_max := scene.get_meta(
		"source_particle_quad_smoke_start_size_max_ue_cm", Vector3.INF
	) as Vector3
	var particle_quad_smoke_location_min := scene.get_meta(
		"source_particle_quad_smoke_start_location_min_ue_cm", Vector3.INF
	) as Vector3
	var particle_quad_smoke_location_max := scene.get_meta(
		"source_particle_quad_smoke_start_location_max_ue_cm", Vector3.INF
	) as Vector3
	var particle_quad_smoke_velocity_min := scene.get_meta(
		"source_particle_quad_smoke_start_velocity_min_ue_cm", Vector3.INF
	) as Vector3
	var particle_quad_smoke_velocity_max := scene.get_meta(
		"source_particle_quad_smoke_start_velocity_max_ue_cm", Vector3.INF
	) as Vector3
	var particle_quad_smoke_rate := float(
		scene.get_meta("source_particle_quad_smoke_spawn_rate", -1.0)
	)
	var particle_quad_smoke_rate_scale := float(
		scene.get_meta("source_particle_quad_smoke_spawn_rate_scale", -1.0)
	)
	var particle_quad_smoke_burst := int(
		scene.get_meta("source_particle_quad_smoke_burst_count", -1)
	)
	var particle_quad_smoke_subuv_fps := float(
		scene.get_meta("source_particle_quad_smoke_subuv_frame_rate", -1.0)
	)
	var particle_quad_smoke_size_life_values := int(
		scene.get_meta("source_particle_quad_smoke_size_life_table_value_count", -1)
	)
	var particle_quad_smoke_rgb_values := int(
		scene.get_meta("source_particle_quad_smoke_rgb_table_value_count", -1)
	)
	var particle_quad_smoke_alpha_values := int(
		scene.get_meta("source_particle_quad_smoke_alpha_table_value_count", -1)
	)
	var particle_quad_smoke_disabled: Array = scene.get_meta(
		"source_particle_quad_smoke_disabled_module_types", []
	) as Array
	var particle_quad_smoke_peak := int(
		scene.get_meta("source_particle_quad_smoke_peak_active", -1)
	)
	var particle_monster_emitters := int(scene.get_meta("source_particle_monster_emitter_count", -1))
	var particle_monster_lods := int(scene.get_meta("source_particle_monster_lod_count", -1))
	var particle_monster_burst_emitters := int(scene.get_meta("source_particle_monster_burst_only_emitters", -1))
	var particle_monster_continuous_emitters := int(scene.get_meta("source_particle_monster_continuous_emitters", -1))
	var particle_monster_lifetimes: Array = scene.get_meta("source_particle_monster_lifetime_ranges", []) as Array
	var particle_monster_size_life_modules := int(scene.get_meta("source_particle_monster_size_life_modules", -1))
	var particle_monster_color_modules := int(scene.get_meta("source_particle_monster_color_modules", -1))
	var particle_monster_velocity_min := scene.get_meta("source_particle_monster_velocity_min_ue_cm", Vector3.INF) as Vector3
	var particle_monster_velocity_max := scene.get_meta("source_particle_monster_velocity_max_ue_cm", Vector3.INF) as Vector3
	var particle_monster_subuv_samples := int(scene.get_meta("source_particle_monster_subuv_sample_count", -1))
	var particle_monster_peaks: Array = scene.get_meta("source_particle_monster_lod_peaks", []) as Array
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
		if particle_semantic_systems != 14 or particle_semantic_placements != 25:
			_fail(
				34,
				"Cascade semantic runtime coverage mismatch systems=%d placements=%d"
				% [particle_semantic_systems, particle_semantic_placements]
			)
			return
		if get_nodes_in_group("nacht_source_particle_semantic").size() != 25:
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

		if (
			not particle_bonefire_size_min.is_equal_approx(Vector3(14.0, 14.0, 0.0))
			or not particle_bonefire_size_max.is_equal_approx(Vector3(10.0, 10.0, 0.0))
			or not is_equal_approx(particle_bonefire_lifetime_min, 1.0)
			or not is_equal_approx(particle_bonefire_lifetime_max, 1.75)
			or not is_equal_approx(particle_bonefire_radius, 50.0)
			or not is_equal_approx(particle_bonefire_subuv_max, 47.0)
		):
			_fail(
				34,
				"Cascade bone fire 2B values mismatch size=%s..%s lifetime=%s..%s radius=%s subuv=%s"
				% [
					particle_bonefire_size_min,
					particle_bonefire_size_max,
					particle_bonefire_lifetime_min,
					particle_bonefire_lifetime_max,
					particle_bonefire_radius,
					particle_bonefire_subuv_max,
				]
			)
			return
		if (
			not particle_bonefire3_size_min.is_equal_approx(Vector3(14.0, 15.0, 0.0))
			or not particle_bonefire3_size_max.is_equal_approx(Vector3(10.0, 10.0, 0.0))
			or not particle_bonefire3_life_multiplier_min.is_equal_approx(Vector3(10.0, 10.0, 1.0))
			or not particle_bonefire3_life_multiplier_max.is_equal_approx(Vector3(12.0, 12.0, 10.0))
			or not is_equal_approx(particle_bonefire3_lifetime_min, 1.5)
			or not is_equal_approx(particle_bonefire3_lifetime_max, 2.0)
			or not is_equal_approx(particle_bonefire3_radius, 50.0)
			or not is_equal_approx(particle_bonefire3_subuv_fps, 30.0)
			or particle_bonefire3_rgb_values != 384
			or particle_bonefire3_alpha_values != 32
		):
			_fail(
				34,
				"Cascade bone fire 3 values mismatch size=%s..%s life_mul=%s..%s lifetime=%s..%s radius=%s subuv_fps=%s rgb=%d alpha=%d"
				% [
					particle_bonefire3_size_min,
					particle_bonefire3_size_max,
					particle_bonefire3_life_multiplier_min,
					particle_bonefire3_life_multiplier_max,
					particle_bonefire3_lifetime_min,
					particle_bonefire3_lifetime_max,
					particle_bonefire3_radius,
					particle_bonefire3_subuv_fps,
					particle_bonefire3_rgb_values,
					particle_bonefire3_alpha_values,
				]
			)
			return
		if (
			particle_pap_wheel_emitters != 2
			or not is_equal_approx(particle_pap_wheel_lifetime, 8.0)
			or not particle_pap_wheel_size_min.is_equal_approx(Vector3(60.0, 60.0, 60.0))
			or not particle_pap_wheel_size_max.is_equal_approx(Vector3(70.0, 70.0, 70.0))
			or not is_equal_approx(particle_pap_wheel_spawn_rate, 3.0)
			or particle_pap_wheel_burst_count != 2
			or not is_equal_approx(particle_pap_wheel_rotation_rate_min, -0.1)
			or not is_equal_approx(particle_pap_wheel_rotation_rate_max, 0.2)
			or not particle_pap_wheel_velocity_life_min.is_equal_approx(Vector3(-2.0, -2.0, -2.0))
			or not is_equal_approx(particle_pap_wheel_velocity_life_time_scale, 5.0)
			or particle_pap_wheel_size_life_table_values != 384
		):
			_fail(
				34,
				"PaP wheel Cascade values mismatch emitters=%d lifetime=%s size=%s..%s rate=%s burst=%d rotation_rate=%s..%s vel_life=%s vel_scale=%s size_life_values=%d"
				% [
					particle_pap_wheel_emitters,
					particle_pap_wheel_lifetime,
					particle_pap_wheel_size_min,
					particle_pap_wheel_size_max,
					particle_pap_wheel_spawn_rate,
					particle_pap_wheel_burst_count,
					particle_pap_wheel_rotation_rate_min,
					particle_pap_wheel_rotation_rate_max,
					particle_pap_wheel_velocity_life_min,
					particle_pap_wheel_velocity_life_time_scale,
					particle_pap_wheel_size_life_table_values,
				]
			)
			return
		if (
			not is_equal_approx(particle_mystery_fog_lifetime_min, 3.0)
			or not is_equal_approx(particle_mystery_fog_lifetime_max, 5.0)
			or not particle_mystery_fog_location_min.is_equal_approx(Vector3(-95.0, -10.0, -5.0))
			or not particle_mystery_fog_location_max.is_equal_approx(Vector3(95.0, 10.0, 5.0))
			or not particle_mystery_fog_size_min.is_equal_approx(Vector3(3.0, 3.0, 3.0))
			or not particle_mystery_fog_size_max.is_equal_approx(Vector3(5.0, 5.0, 5.0))
			or not particle_mystery_fog_life_multiplier_min.is_equal_approx(Vector3(10.0, 0.0, 0.0))
			or not particle_mystery_fog_life_multiplier_max.is_equal_approx(Vector3(50.0, 1.0, 1.0))
			or particle_mystery_fog_life_multiplier_values != 96
			or not particle_mystery_fog_color_min.is_equal_approx(Vector3(0.49479154, 0.489095, 0.4591))
			or not particle_mystery_fog_color_max.is_equal_approx(Vector3(1.0, 1.0, 0.97423244))
			or particle_mystery_fog_rgb_values != 12
			or particle_mystery_fog_alpha_values != 128
			or not is_equal_approx(particle_mystery_fog_alpha_max, 1.0380507)
			or not is_equal_approx(particle_mystery_fog_spawn_rate, 4.0)
			or not is_equal_approx(particle_mystery_fog_subuv_fps, 16.0)
			or not particle_mystery_fog_velocity_life_min.is_equal_approx(Vector3(0.0, 0.0, -1.5))
			or not particle_mystery_fog_velocity_life_max.is_equal_approx(Vector3(0.0, 0.2, 0.75))
			or not is_equal_approx(particle_mystery_fog_velocity_life_time_scale, 1.0)
			or not particle_mystery_fog_start_velocity_min.is_equal_approx(Vector3(0.0, 100.0, 0.0))
			or not particle_mystery_fog_start_velocity_max.is_equal_approx(Vector3(0.0, 100.0, 40.0))
			or particle_mystery_fog_peak != 22
		):
			_fail(
				34,
				"mystery box fog Cascade values mismatch lifetime=%s..%s location=%s..%s size=%s..%s life_mul=%s..%s life_values=%d color=%s..%s rgb=%d alpha=%d alpha_max=%s rate=%s subuv_fps=%s vel_life=%s..%s vel_scale=%s start_vel=%s..%s peak=%d"
				% [
					particle_mystery_fog_lifetime_min,
					particle_mystery_fog_lifetime_max,
					particle_mystery_fog_location_min,
					particle_mystery_fog_location_max,
					particle_mystery_fog_size_min,
					particle_mystery_fog_size_max,
					particle_mystery_fog_life_multiplier_min,
					particle_mystery_fog_life_multiplier_max,
					particle_mystery_fog_life_multiplier_values,
					particle_mystery_fog_color_min,
					particle_mystery_fog_color_max,
					particle_mystery_fog_rgb_values,
					particle_mystery_fog_alpha_values,
					particle_mystery_fog_alpha_max,
					particle_mystery_fog_spawn_rate,
					particle_mystery_fog_subuv_fps,
					particle_mystery_fog_velocity_life_min,
					particle_mystery_fog_velocity_life_max,
					particle_mystery_fog_velocity_life_time_scale,
					particle_mystery_fog_start_velocity_min,
					particle_mystery_fog_start_velocity_max,
					particle_mystery_fog_peak,
				]
			)
			return
		if (
			not is_equal_approx(particle_mystery_inside_lifetime_min, 1.5)
			or not is_equal_approx(particle_mystery_inside_lifetime_max, 3.0)
			or not particle_mystery_inside_location_min.is_equal_approx(Vector3(-20.0, -95.0, -10.0))
			or not particle_mystery_inside_location_max.is_equal_approx(Vector3(20.0, 95.0, 10.0))
			or not particle_mystery_inside_size_min.is_equal_approx(Vector3(5.0, 5.0, 5.0))
			or not particle_mystery_inside_size_max.is_equal_approx(Vector3(10.0, 10.0, 10.0))
			or not is_equal_approx(particle_mystery_inside_spawn_rate, 175.0)
			or not particle_mystery_inside_velocity_min.is_equal_approx(Vector3(0.0, 0.0, 45.0))
			or not particle_mystery_inside_velocity_max.is_equal_approx(Vector3(0.0, 0.0, 50.0))
			or particle_mystery_inside_rgb_values != 3
			or particle_mystery_inside_alpha_values != 2
			or particle_mystery_inside_orbit_enabled
			or not particle_mystery_inside_orbit_offset_min.is_equal_approx(Vector3(0.0, 10.0, 0.0))
			or not particle_mystery_inside_orbit_offset_max.is_equal_approx(Vector3(0.0, 25.0, 0.0))
			or not particle_mystery_inside_gpu_inv_max_size.is_equal_approx(Vector2(0.1, 0.1))
			or not is_equal_approx(particle_mystery_inside_gpu_inv_rotation_scale, 0.33333334)
			or not is_equal_approx(particle_mystery_inside_gpu_max_lifetime, 3.0)
			or particle_mystery_inside_gpu_max_particles != 531
			or not is_equal_approx(particle_mystery_inside_gpu_rotation_scale, 3.0)
			or particle_mystery_inside_gpu_color_samples != 16
		):
			_fail(
				34,
				"mystery inside Cascade values mismatch lifetime=%s..%s location=%s..%s size=%s..%s rate=%s velocity=%s..%s rgb=%d alpha=%d orbit=%s offset=%s..%s gpu_inv=%s gpu_inv_rot=%s gpu_life=%s gpu_max=%d gpu_rot=%s gpu_colors=%d"
				% [
					particle_mystery_inside_lifetime_min,
					particle_mystery_inside_lifetime_max,
					particle_mystery_inside_location_min,
					particle_mystery_inside_location_max,
					particle_mystery_inside_size_min,
					particle_mystery_inside_size_max,
					particle_mystery_inside_spawn_rate,
					particle_mystery_inside_velocity_min,
					particle_mystery_inside_velocity_max,
					particle_mystery_inside_rgb_values,
					particle_mystery_inside_alpha_values,
					str(particle_mystery_inside_orbit_enabled),
					particle_mystery_inside_orbit_offset_min,
					particle_mystery_inside_orbit_offset_max,
					particle_mystery_inside_gpu_inv_max_size,
					particle_mystery_inside_gpu_inv_rotation_scale,
					particle_mystery_inside_gpu_max_lifetime,
					particle_mystery_inside_gpu_max_particles,
					particle_mystery_inside_gpu_rotation_scale,
					particle_mystery_inside_gpu_color_samples,
				]
			)
			return
		if (
			not is_equal_approx(particle_fire_smoke_lifetime_min, 3.0)
			or not is_equal_approx(particle_fire_smoke_lifetime_max, 5.0)
			or not is_equal_approx(particle_fire_smoke_radius, 100.0)
			or not particle_fire_smoke_pivot.is_equal_approx(Vector2(0.0, -0.5))
			or not particle_fire_smoke_life_multiplier_min.is_equal_approx(Vector3(6.0, 6.0, 0.0))
			or not particle_fire_smoke_life_multiplier_max.is_equal_approx(Vector3(7.0, 8.0, 0.0))
			or not particle_fire_smoke_speed_scale.is_equal_approx(Vector2(1.0, 2.0))
			or not particle_fire_smoke_max_scale.is_equal_approx(Vector2(10.0, 50.0))
			or not particle_fire_smoke_size_min.is_equal_approx(Vector3(20.0, 10.0, 0.0))
			or not particle_fire_smoke_size_max.is_equal_approx(Vector3(15.0, 6.0, 0.0))
			or not is_equal_approx(particle_fire_smoke_subuv_fps, 45.0)
			or not particle_fire_smoke_velocity_min.is_equal_approx(Vector3(-10.0, -10.0, 1.0))
			or not particle_fire_smoke_velocity_max.is_equal_approx(Vector3(10.0, 10.0, 5.0))
			or particle_fire_smoke_rgb_values != 3
			or particle_fire_smoke_alpha_values != 16
			or particle_fire_smoke_spawn_rates.size() != 2
			or not is_equal_approx(float(particle_fire_smoke_spawn_rates[0]), 0.29999998)
			or not is_equal_approx(float(particle_fire_smoke_spawn_rates[1]), 3.0)
			or particle_fire_smoke_peaks.size() != 2
			or int(particle_fire_smoke_peaks[0]) != 7
			or int(particle_fire_smoke_peaks[1]) != 17
		):
			_fail(
				34,
				"big fire vg smoke Cascade values mismatch lifetime=%s..%s radius=%s pivot=%s life_mul=%s..%s speed=%s max=%s size=%s..%s subuv_fps=%s velocity=%s..%s rgb=%d alpha=%d rates=%s peaks=%s"
				% [
					particle_fire_smoke_lifetime_min,
					particle_fire_smoke_lifetime_max,
					particle_fire_smoke_radius,
					particle_fire_smoke_pivot,
					particle_fire_smoke_life_multiplier_min,
					particle_fire_smoke_life_multiplier_max,
					particle_fire_smoke_speed_scale,
					particle_fire_smoke_max_scale,
					particle_fire_smoke_size_min,
					particle_fire_smoke_size_max,
					particle_fire_smoke_subuv_fps,
					particle_fire_smoke_velocity_min,
					particle_fire_smoke_velocity_max,
					particle_fire_smoke_rgb_values,
					particle_fire_smoke_alpha_values,
					particle_fire_smoke_spawn_rates,
					particle_fire_smoke_peaks,
				]
			)
			return
		if (
			not is_equal_approx(particle_pap_wheel_out_lifetime_min, 0.5)
			or not is_equal_approx(particle_pap_wheel_out_lifetime_max, 1.5)
			or not particle_pap_wheel_out_location_min.is_equal_approx(Vector3(-50.0, -50.0, -10.0))
			or not particle_pap_wheel_out_location_max.is_equal_approx(Vector3(50.0, 50.0, 10.0))
			or not particle_pap_wheel_out_size_min.is_equal_approx(Vector3(3.0, 3.0, 3.0))
			or not particle_pap_wheel_out_size_max.is_equal_approx(Vector3(5.0, 5.0, 5.0))
			or particle_pap_wheel_out_size_life_values != 384
			or not is_equal_approx(particle_pap_wheel_out_size_life_time_scale, 127.34587)
			or not particle_pap_wheel_out_velocity_min.is_equal_approx(Vector3(60.0, -5.0, -5.0))
			or not particle_pap_wheel_out_velocity_max.is_equal_approx(Vector3(80.0, 5.0, 5.0))
			or not particle_pap_wheel_out_velocity_life_max.is_equal_approx(Vector3(1.0, 10.0, 10.0))
			or particle_pap_wheel_out_velocity_life_values != 6
			or not is_equal_approx(particle_pap_wheel_out_velocity_life_time_scale, 2.0)
			or not particle_pap_wheel_out_accel_min.is_equal_approx(Vector3(0.0, 0.0, -10.0))
			or not particle_pap_wheel_out_accel_max.is_equal_approx(Vector3(0.0, 0.0, -15.0))
			or not particle_pap_wheel_out_accel_world
			or not is_equal_approx(particle_pap_wheel_out_rotation_rate_min, -0.1)
			or not is_equal_approx(particle_pap_wheel_out_rotation_rate_max, 0.2)
			or not is_equal_approx(particle_pap_wheel_out_spawn_rate, 15.0)
			or not is_equal_approx(particle_pap_wheel_out_spawn_rate_scale, 15.0)
			or particle_pap_wheel_out_peak != 339
		):
			_fail(
				34,
				"PaP wheel out Cascade values mismatch lifetime=%s..%s location=%s..%s size=%s..%s life_values=%d life_scale=%s velocity=%s..%s vel_life_max=%s vel_values=%d vel_scale=%s accel=%s..%s accel_world=%s rotation_rate=%s..%s rate=%s rate_scale=%s peak=%d"
				% [
					particle_pap_wheel_out_lifetime_min,
					particle_pap_wheel_out_lifetime_max,
					particle_pap_wheel_out_location_min,
					particle_pap_wheel_out_location_max,
					particle_pap_wheel_out_size_min,
					particle_pap_wheel_out_size_max,
					particle_pap_wheel_out_size_life_values,
					particle_pap_wheel_out_size_life_time_scale,
					particle_pap_wheel_out_velocity_min,
					particle_pap_wheel_out_velocity_max,
					particle_pap_wheel_out_velocity_life_max,
					particle_pap_wheel_out_velocity_life_values,
					particle_pap_wheel_out_velocity_life_time_scale,
					particle_pap_wheel_out_accel_min,
					particle_pap_wheel_out_accel_max,
					str(particle_pap_wheel_out_accel_world),
					particle_pap_wheel_out_rotation_rate_min,
					particle_pap_wheel_out_rotation_rate_max,
					particle_pap_wheel_out_spawn_rate,
					particle_pap_wheel_out_spawn_rate_scale,
					particle_pap_wheel_out_peak,
				]
			)
			return
		if (
			not is_equal_approx(particle_electric_beam_lifetime, 1.0)
			or not particle_electric_beam_size.is_equal_approx(Vector3(25.0, 25.0, 25.0))
			or not is_equal_approx(particle_electric_beam_spawn_rate, 20.0)
			or particle_electric_beam_noise_frequency != 5
			or not is_equal_approx(particle_electric_beam_noise_lock_time, 0.025)
			or not particle_electric_beam_noise_range.is_equal_approx(Vector3(30.0, 30.0, 20.0))
			or not particle_electric_beam_noise_speed.is_equal_approx(Vector3(50.0, 50.0, 50.0))
			or not is_equal_approx(particle_electric_beam_noise_tangent, 250.0)
			or not is_equal_approx(particle_electric_beam_source_strength, 25.0)
			or not particle_electric_beam_source_tangent.is_equal_approx(Vector3(1.0, 0.0, 0.0))
			or not particle_electric_beam_target.is_equal_approx(Vector3(0.0, 0.0, 280.0))
			or not is_equal_approx(particle_electric_beam_target_strength, 25.0)
			or not particle_electric_beam_target_tangent.is_equal_approx(Vector3(1.0, 0.0, 0.0))
			or not is_equal_approx(particle_electric_beam_distance, 25.0)
			or particle_electric_beam_interpolation_points != 20
			or particle_electric_beam_max_count != 1
			or particle_electric_beam_peak != 3
		):
			_fail(
				34,
				"electric beam Cascade values mismatch life=%s size=%s rate=%s noise_freq=%d noise_lock=%s noise_range=%s noise_speed=%s noise_tangent=%s source_strength=%s source_tangent=%s target=%s target_strength=%s target_tangent=%s distance=%s points=%d max=%d peak=%d"
				% [
					particle_electric_beam_lifetime,
					particle_electric_beam_size,
					particle_electric_beam_spawn_rate,
					particle_electric_beam_noise_frequency,
					particle_electric_beam_noise_lock_time,
					particle_electric_beam_noise_range,
					particle_electric_beam_noise_speed,
					particle_electric_beam_noise_tangent,
					particle_electric_beam_source_strength,
					particle_electric_beam_source_tangent,
					particle_electric_beam_target,
					particle_electric_beam_target_strength,
					particle_electric_beam_target_tangent,
					particle_electric_beam_distance,
					particle_electric_beam_interpolation_points,
					particle_electric_beam_max_count,
					particle_electric_beam_peak,
				]
			)
			return
		var acid_ranges_ok := (
			particle_acid_ball_dynamic_ranges.size() == 4
			and particle_acid_ball_dynamic_ranges[0] is Vector2
			and (particle_acid_ball_dynamic_ranges[0] as Vector2).is_equal_approx(Vector2(0.0, 0.5))
			and particle_acid_ball_dynamic_ranges[1] is Vector2
			and (particle_acid_ball_dynamic_ranges[1] as Vector2).is_equal_approx(Vector2(0.3, 0.6))
			and particle_acid_ball_dynamic_ranges[2] is Vector2
			and (particle_acid_ball_dynamic_ranges[2] as Vector2).is_equal_approx(Vector2.ZERO)
			and particle_acid_ball_dynamic_ranges[3] is Vector2
			and (particle_acid_ball_dynamic_ranges[3] as Vector2).is_equal_approx(Vector2.ZERO)
		)
		var acid_spawn_only_ok := (
			particle_acid_ball_dynamic_spawn_only.size() == 4
			and not bool(particle_acid_ball_dynamic_spawn_only[0])
			and bool(particle_acid_ball_dynamic_spawn_only[1])
			and not bool(particle_acid_ball_dynamic_spawn_only[2])
			and not bool(particle_acid_ball_dynamic_spawn_only[3])
		)
		var acid_samples_ok := false
		if particle_acid_ball_dynamic_samples.size() == 4:
			var acid_samples_0: Array = particle_acid_ball_dynamic_samples[0] as Array
			var acid_samples_1: Array = particle_acid_ball_dynamic_samples[1] as Array
			var acid_samples_2: Array = particle_acid_ball_dynamic_samples[2] as Array
			var acid_samples_3: Array = particle_acid_ball_dynamic_samples[3] as Array
			acid_samples_ok = (
				acid_samples_0.size() == 2
				and is_equal_approx(float(acid_samples_0[0]), 0.0)
				and is_equal_approx(float(acid_samples_0[1]), 0.5)
				and acid_samples_1.size() == 2
				and is_equal_approx(float(acid_samples_1[0]), 0.3)
				and is_equal_approx(float(acid_samples_1[1]), 0.6)
				and acid_samples_2.size() == 1
				and is_equal_approx(float(acid_samples_2[0]), 0.0)
				and acid_samples_3.size() == 1
				and is_equal_approx(float(acid_samples_3[0]), 0.0)
			)
		var acid_peaks_ok := (
			particle_acid_ball_peaks.size() == 2
			and int(particle_acid_ball_peaks[0]) == 3
			and int(particle_acid_ball_peaks[1]) == 20
		)
		if (
			particle_acid_ball_mesh_burst != 1
			or not is_equal_approx(particle_acid_ball_spawn_rate, 10.0)
			or not is_equal_approx(particle_acid_ball_lifetime_min, 1.0)
			or not is_equal_approx(particle_acid_ball_lifetime_max, 2.0)
			or not particle_acid_ball_mesh_size.is_equal_approx(Vector3(0.5, 0.6, 0.5))
			or not particle_acid_ball_sprite_size_min.is_equal_approx(Vector3(5.0, 8.333333, 8.333333))
			or not particle_acid_ball_sprite_size_max.is_equal_approx(Vector3(6.666667, 8.333333, 8.333333))
			or particle_acid_ball_dynamic_count != 4
			or not acid_ranges_ok
			or not acid_spawn_only_ok
			or not acid_samples_ok
			or not acid_peaks_ok
		):
			_fail(
				34,
				"AcidBall Cascade mismatch burst=%d rate=%s life=%s..%s mesh_size=%s sprite_size=%s..%s dynamic_count=%d ranges=%s spawn_only=%s samples=%s peaks=%s"
				% [
					particle_acid_ball_mesh_burst,
					particle_acid_ball_spawn_rate,
					particle_acid_ball_lifetime_min,
					particle_acid_ball_lifetime_max,
					particle_acid_ball_mesh_size,
					particle_acid_ball_sprite_size_min,
					particle_acid_ball_sprite_size_max,
					particle_acid_ball_dynamic_count,
					particle_acid_ball_dynamic_ranges,
					particle_acid_ball_dynamic_spawn_only,
					particle_acid_ball_dynamic_samples,
					particle_acid_ball_peaks,
				]
			)
			return
		var sparks_peaks_ok := (
			particle_sparks_peaks.size() == 2
			and int(particle_sparks_peaks[0]) == 27
			and int(particle_sparks_peaks[1]) == 27
		)
		if (
			not is_equal_approx(particle_sparks_lifetime_min, 0.2)
			or not is_equal_approx(particle_sparks_lifetime_max, 0.5)
			or not particle_sparks_location_min.is_equal_approx(Vector3.ZERO)
			or not particle_sparks_location_max.is_equal_approx(Vector3(1.0, 4.0, 6.0))
			or not particle_sparks_accel.is_equal_approx(Vector3(0.0, 0.0, -900.0))
			or not particle_sparks_accel_world
			or particle_sparks_collision_enabled
			or not is_equal_approx(particle_sparks_resilience, 0.75)
			or not is_equal_approx(particle_sparks_resilience_scale, 1.0)
			or not particle_sparks_speed_scale.is_equal_approx(Vector2(0.0, 7.0))
			or not particle_sparks_max_scale.is_equal_approx(Vector2(1.0, 10.0))
			or not particle_sparks_size_min.is_equal_approx(Vector3(0.1, 0.1, 0.1))
			or not particle_sparks_size_max.is_equal_approx(Vector3(2.0, 2.0, 2.0))
			or not is_equal_approx(particle_sparks_spawn_rate, 10.0)
			or particle_sparks_burst_count != 20
			or particle_sparks_burst_low != 4
			or not is_equal_approx(particle_sparks_burst_time, 0.2)
			or not is_equal_approx(particle_sparks_burst_scale, 0.5)
			or not particle_sparks_velocity_min.is_equal_approx(Vector3(100.0, -100.0, -10.0))
			or not particle_sparks_velocity_max.is_equal_approx(Vector3(100.0, 100.0, 125.0))
			or not particle_sparks_gpu_inv_max_size.is_equal_approx(Vector2(0.5, 0.5))
			or not is_equal_approx(particle_sparks_gpu_max_lifetime, 0.5)
			or particle_sparks_gpu_max_particles != 27
			or not is_equal_approx(particle_sparks_gpu_collision_radius, 0.5)
			or not is_equal_approx(particle_sparks_gpu_collision_random, 1.0)
			or not sparks_peaks_ok
		):
			_fail(
				34,
				"sparks Cascade mismatch life=%s..%s location=%s..%s accel=%s world=%s collision=%s resilience=%s/%s speed=%s max=%s size=%s..%s rate=%s burst=%d/%d@%s scale=%s velocity=%s..%s gpu_inv=%s gpu_life=%s gpu_max=%d gpu_collision=%s/%s peaks=%s"
				% [
					particle_sparks_lifetime_min,
					particle_sparks_lifetime_max,
					particle_sparks_location_min,
					particle_sparks_location_max,
					particle_sparks_accel,
					str(particle_sparks_accel_world),
					str(particle_sparks_collision_enabled),
					particle_sparks_resilience,
					particle_sparks_resilience_scale,
					particle_sparks_speed_scale,
					particle_sparks_max_scale,
					particle_sparks_size_min,
					particle_sparks_size_max,
					particle_sparks_spawn_rate,
					particle_sparks_burst_low,
					particle_sparks_burst_count,
					particle_sparks_burst_time,
					particle_sparks_burst_scale,
					particle_sparks_velocity_min,
					particle_sparks_velocity_max,
					particle_sparks_gpu_inv_max_size,
					particle_sparks_gpu_max_lifetime,
					particle_sparks_gpu_max_particles,
					particle_sparks_gpu_collision_radius,
					particle_sparks_gpu_collision_random,
					particle_sparks_peaks,
				]
			)
			return
		var quad_disabled_expected := [
			"ParticleModuleAcceleration",
			"ParticleModuleColor",
			"ParticleModuleLocationPrimitiveCylinder",
			"ParticleModuleLocationSkelVertSurface",
			"ParticleModuleRotationRate",
			"ParticleModuleVelocityOverLifetime",
		]
		if (
			not is_equal_approx(particle_quad_smoke_lifetime_min, 1.0)
			or not is_equal_approx(particle_quad_smoke_lifetime_max, 2.0)
			or not particle_quad_smoke_size_min.is_equal_approx(Vector3(200.0, 200.0, 200.0))
			or not particle_quad_smoke_size_max.is_equal_approx(Vector3(250.0, 250.0, 250.0))
			or not particle_quad_smoke_location_min.is_equal_approx(Vector3(-120.0, -120.0, 5.0))
			or not particle_quad_smoke_location_max.is_equal_approx(Vector3(120.0, 120.0, 25.0))
			or not particle_quad_smoke_velocity_min.is_equal_approx(Vector3(-20.0, -20.0, 7.0))
			or not particle_quad_smoke_velocity_max.is_equal_approx(Vector3(20.0, 20.0, 25.0))
			or not is_equal_approx(particle_quad_smoke_rate, 5.0)
			or not is_equal_approx(particle_quad_smoke_rate_scale, 5.0)
			or particle_quad_smoke_burst != 5
			or not is_equal_approx(particle_quad_smoke_subuv_fps, 15.0)
			or particle_quad_smoke_size_life_values != 384
			or particle_quad_smoke_rgb_values != 48
			or particle_quad_smoke_alpha_values != 128
			or particle_quad_smoke_disabled != quad_disabled_expected
			or particle_quad_smoke_peak != 31
		):
			_fail(
				34,
				"quad smoke Cascade mismatch life=%s..%s size=%s..%s location=%s..%s velocity=%s..%s rate=%s scale=%s burst=%d subuv=%s size_life=%d rgb=%d alpha=%d disabled=%s peak=%d"
				% [
					particle_quad_smoke_lifetime_min,
					particle_quad_smoke_lifetime_max,
					particle_quad_smoke_size_min,
					particle_quad_smoke_size_max,
					particle_quad_smoke_location_min,
					particle_quad_smoke_location_max,
					particle_quad_smoke_velocity_min,
					particle_quad_smoke_velocity_max,
					particle_quad_smoke_rate,
					particle_quad_smoke_rate_scale,
					particle_quad_smoke_burst,
					particle_quad_smoke_subuv_fps,
					particle_quad_smoke_size_life_values,
					particle_quad_smoke_rgb_values,
					particle_quad_smoke_alpha_values,
					particle_quad_smoke_disabled,
					particle_quad_smoke_peak,
				]
			)
			return
		var monster_peaks_ok := (
			particle_monster_peaks.size() == 12
			and int(particle_monster_peaks[0]) == 2
			and int(particle_monster_peaks[5]) == 2
			and int(particle_monster_peaks[6]) == 3
			and int(particle_monster_peaks[8]) == 3
			and int(particle_monster_peaks[9]) == 16
			and int(particle_monster_peaks[11]) == 16
		)
		if (
			particle_monster_emitters != 4
			or particle_monster_lods != 12
			or particle_monster_burst_emitters != 3
			or particle_monster_continuous_emitters != 1
			or particle_monster_lifetimes.size() != 6
			or particle_monster_size_life_modules != 6
			or particle_monster_color_modules != 10
			or not particle_monster_velocity_min.is_equal_approx(Vector3(-15.0, -15.0, 25.0))
			or not particle_monster_velocity_max.is_equal_approx(Vector3(15.0, 15.0, 35.0))
			or particle_monster_subuv_samples != 32
			or not monster_peaks_ok
		):
			_fail(
				34,
				"monster XL Cascade summary mismatch emitters=%d lods=%d burst=%d continuous=%d lifetimes=%s size_life=%d color=%d velocity=%s..%s subuv=%d peaks=%s"
				% [
					particle_monster_emitters, particle_monster_lods,
					particle_monster_burst_emitters, particle_monster_continuous_emitters,
					particle_monster_lifetimes, particle_monster_size_life_modules,
					particle_monster_color_modules, particle_monster_velocity_min,
					particle_monster_velocity_max, particle_monster_subuv_samples,
					particle_monster_peaks,
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
		" bonefire_size=", particle_bonefire_size_min,
		"..", particle_bonefire_size_max,
		" bonefire3_size=", particle_bonefire3_size_min,
		"..", particle_bonefire3_size_max,
		" bonefire3_subuv_fps=", particle_bonefire3_subuv_fps,
		" pap_wheel_rate=", particle_pap_wheel_spawn_rate,
		" pap_wheel_burst=", particle_pap_wheel_burst_count,
		" mystery_fog_rate=", particle_mystery_fog_spawn_rate,
		" mystery_fog_subuv_fps=", particle_mystery_fog_subuv_fps,
		" mystery_inside_rate=", particle_mystery_inside_spawn_rate,
		" mystery_inside_gpu_max=", particle_mystery_inside_gpu_max_particles,
		" fire_smoke_subuv_fps=", particle_fire_smoke_subuv_fps,
		" fire_smoke_rates=", particle_fire_smoke_spawn_rates,
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
