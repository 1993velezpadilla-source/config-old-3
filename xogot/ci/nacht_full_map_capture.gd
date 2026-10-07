extends SceneTree

const EXPECTED_PACKAGES := 3871
const EXPECTED_MESHES := 493
const EXPECTED_INSTANCES := 10793
const EXPECTED_ACTORS := 11023
const EXPECTED_LIGHTS := 166
const EXPECTED_TEXTURES := 1581

func _init() -> void:
	call_deferred("_capture")

func _fail(code: int, message: String) -> void:
	push_error("NACHT_CAPTURE: " + message)
	quit(code)

func _percentile(values: Array[float], fraction: float) -> float:
	if values.is_empty():
		return 0.0
	values.sort()
	var index := clampi(
		int(round(float(values.size() - 1) * clampf(fraction, 0.0, 1.0))),
		0,
		values.size() - 1
	)
	return values[index]

func _luminance(color: Color) -> float:
	return (
		color.r * 0.2126
		+ color.g * 0.7152
		+ color.b * 0.0722
	)

func _validate_visual_detail(image: Image, label: String) -> bool:
	var samples: Array[float] = []
	var step_x := maxi(1, image.get_width() / 160)
	var step_y := maxi(1, image.get_height() / 90)
	for y in range(0, image.get_height(), step_y):
		for x in range(0, image.get_width(), step_x):
			samples.append(_luminance(image.get_pixel(x, y)))
	if samples.size() < 100:
		_fail(33, label + " visual sample set too small")
		return false
	var p05 := _percentile(samples.duplicate(), 0.05)
	var p50 := _percentile(samples.duplicate(), 0.50)
	var p95 := _percentile(samples.duplicate(), 0.95)
	var spread := p95 - p05
	print(
		"XZOGOT_NACHT_CAPTURE_VISUAL_STATS ",
		"label=", label,
		" p05=", p05,
		" p50=", p50,
		" p95=", p95,
		" spread=", spread,
		" samples=", samples.size()
	)
	# A generated PNG is not visual proof when it is essentially a flat clear
	# color or completely washed out by a non-exact environment fallback.
	if spread < 0.03:
		_fail(
			34,
			label + " frame is visually blank/washed out spread=" + str(spread)
		)
		return false
	return true

func _prepare_structural_visual_proof(scene: Node3D) -> void:
	var exact_environment := bool(
		scene.get_meta("source_environment_visual_exact", false)
	)
	var disabled_fog_nodes := 0
	if not exact_environment:
		for raw: Node in get_nodes_in_group("nacht_source_environment_runtime"):
			if raw is WorldEnvironment:
				var world := raw as WorldEnvironment
				if world.environment != null and world.environment.fog_enabled:
					world.environment.fog_enabled = false
					disabled_fog_nodes += 1
	print(
		"XZOGOT_NACHT_CAPTURE_VISUAL_PROOF_MODE ",
		"source_environment_visual_exact=", exact_environment,
		" approximate_fog_disabled=", disabled_fog_nodes
	)

func _save_view(
	path: String,
	label: String,
	require_visual_detail: bool = true,
	settle_frames: int = 2
) -> bool:
	for _i in range(maxi(1, settle_frames)):
		await process_frame
	var image := root.get_texture().get_image()
	if image == null or image.is_empty():
		_fail(30, label + " frame empty")
		return false
	if image.get_width() <= image.get_height():
		_fail(31, label + " frame not landscape")
		return false
	if require_visual_detail and not _validate_visual_detail(image, label):
		return false
	if image.save_png(path) != OK:
		_fail(32, label + " save failed")
		return false
	print(
		"XZOGOT_NACHT_", label.to_upper(), "_SCREENSHOT_GREEN ",
		path, " ", image.get_width(), "x", image.get_height()
	)
	return true

func _restart_particle_visuals_deterministic(
	particle_visuals: Array[Node],
	_warmup_frames: int = 30,
	force_inactive: bool = false
) -> void:
	const SNAPSHOT_SECONDS := 0.75
	for particle_index in range(particle_visuals.size()):
		var raw_particle: Node = particle_visuals[particle_index]
		if not (raw_particle is GPUParticles3D):
			continue
		var particles := raw_particle as GPUParticles3D
		var source_runtime_emitting := particles.emitting
		# Runtime-state A/B must never resurrect one-shot or source-disabled
		# emitters. Forced isolation is a separate forensic mode and is labeled
		# as such in the log so its frame cannot be mistaken for gameplay.
		if not source_runtime_emitting and not force_inactive:
			continue
		particles.use_fixed_seed = true
		particles.seed = 1337 + particle_index * 7919
		particles.speed_scale = 0.0
		particles.restart(false)
		particles.request_particles_process(SNAPSHOT_SECONDS)
	await process_frame
	await process_frame


func _texture_alpha_probe(texture: Texture2D) -> Dictionary:
	if texture == null:
		return {"ready": false}
	var image := texture.get_image()
	if image == null or image.is_empty():
		return {
			"ready": false,
			"width": texture.get_width(),
			"height": texture.get_height(),
		}
	if image.is_compressed():
		var decompress_error := image.decompress()
		if decompress_error != OK:
			return {
				"ready": false,
				"width": image.get_width(),
				"height": image.get_height(),
				"compressed": true,
				"decompressError": int(decompress_error),
			}
	var min_alpha := 1.0
	var max_alpha := 0.0
	var below_half := 0
	var samples := 0
	var step_x := maxi(1, image.get_width() / 64)
	var step_y := maxi(1, image.get_height() / 32)
	for y in range(0, image.get_height(), step_y):
		for x in range(0, image.get_width(), step_x):
			var alpha := image.get_pixel(x, y).a
			min_alpha = minf(min_alpha, alpha)
			max_alpha = maxf(max_alpha, alpha)
			if alpha < 0.5:
				below_half += 1
			samples += 1
	return {
		"ready": true,
		"width": image.get_width(),
		"height": image.get_height(),
		"minAlpha": min_alpha,
		"maxAlpha": max_alpha,
		"belowHalf": below_half,
		"samples": samples,
	}


func _print_material_probe(label: String, material: Material) -> void:
	if material == null:
		print("XZOGOT_NACHT_MATERIAL_PROBE label=", label, " material=null")
		return
	if not (material is StandardMaterial3D):
		print(
			"XZOGOT_NACHT_MATERIAL_PROBE label=", label,
			" class=", material.get_class()
		)
		return
	var standard := material as StandardMaterial3D
	var alpha_probe := _texture_alpha_probe(standard.albedo_texture)
	print(
		"XZOGOT_NACHT_MATERIAL_PROBE ",
		"label=", label,
		" source_blend=", str(standard.get_meta("source_blend_mode", "")),
		" transparency=", int(standard.transparency),
		" blend_mode=", int(standard.blend_mode),
		" shading=", int(standard.shading_mode),
		" billboard=", int(standard.billboard_mode),
		" vertex_color=", standard.vertex_color_use_as_albedo,
		" hframes=", standard.particles_anim_h_frames,
		" vframes=", standard.particles_anim_v_frames,
		" has_albedo=", standard.albedo_texture != null,
		" alpha_probe=", alpha_probe
	)


func _probe_bonefire_material(scene: Node3D, particle_visuals: Array[Node]) -> void:
	const BONEFIRE_SYSTEM := "/Game/CustomMaps/UGC2755515831/M5VFXVOL2/Particles/Reference/Fireloop/2_bonefire2B_fwd2_pt.2_bonefire2B_fwd2_pt"
	const BONEFIRE_MATERIAL := "/Game/CustomMaps/UGC2755515831/M5VFXVOL2/Materials/Fire_Inst/BoneFire2B_fwd2_Inst.BoneFire2B_fwd2_Inst"
	var loader := scene.get_node_or_null("NachtStaticWorld")
	if loader != null and loader.has_method("resolve_source_material"):
		var resolved_raw: Variant = loader.call(
			"resolve_source_material",
			BONEFIRE_MATERIAL
		)
		if resolved_raw is Material:
			_print_material_probe("bonefire_loader", resolved_raw as Material)
		else:
			print(
				"XZOGOT_NACHT_MATERIAL_PROBE label=bonefire_loader raw=",
				typeof(resolved_raw)
			)

	for raw_particle: Node in particle_visuals:
		if not (raw_particle is GPUParticles3D):
			continue
		var parent := raw_particle.get_parent()
		if parent == null:
			continue
		if str(parent.get_meta("source_particle_system_path", "")) != BONEFIRE_SYSTEM:
			continue
		var particles := raw_particle as GPUParticles3D
		var draw_mesh := particles.draw_pass_1
		var draw_material: Material = null
		if draw_mesh != null and draw_mesh.get_surface_count() > 0:
			draw_material = draw_mesh.surface_get_material(0)
		_print_material_probe("bonefire_draw_pass", draw_material)
		print(
			"XZOGOT_NACHT_BONEFIRE_PARTICLE_PROBE ",
			"amount=", particles.amount,
			" lifetime=", particles.lifetime,
			" randomness=", particles.randomness,
			" fixed_fps=", particles.fixed_fps,
			" local_coords=", particles.local_coords,
			" visible_aabb=", particles.visibility_aabb
		)


func _capture_player_basis_from_source_anchor(anchor: Node3D) -> Basis:
	# Match nacht_full_map.gd source-spawn conversion: UE +X is gameplay
	# forward, while the Godot character must remain native +Y-up.
	var source_forward := anchor.global_basis.x
	source_forward.y = 0.0
	if source_forward.length_squared() < 0.000001:
		source_forward = Vector3.FORWARD
	else:
		source_forward = source_forward.normalized()
	var godot_z := -source_forward
	var godot_x := Vector3.UP.cross(godot_z).normalized()
	if godot_x.length_squared() < 0.000001:
		godot_x = Vector3.RIGHT
	return Basis(godot_x, Vector3.UP, godot_z).orthonormalized()


func _capture() -> void:
	var packed := load("res://nacht_full_map.tscn") as PackedScene
	if packed == null:
		_fail(2, "nacht_full_map.tscn missing")
		return

	var scene := packed.instantiate() as Node3D
	if scene == null:
		_fail(3, "Nacht scene instantiate failed")
		return
	root.add_child(scene)

	var ready := false
	for _i in range(3000):
		await create_timer(0.05).timeout
		if bool(scene.get_meta("nacht_full_map_ready", false)):
			ready = true
			break
	if not ready:
		_fail(4, "full map did not become ready")
		return

	var packages := int(scene.get_meta("source_package_count", -1))
	var meshes := int(scene.get_meta("source_mesh_count", -1))
	var instances := int(scene.get_meta("runtime_instance_count", -1))
	var actors := int(scene.get_meta("runtime_actor_anchor_count", -1))
	var lights := int(scene.get_meta("runtime_light_count", -1))
	var textures := int(scene.get_meta("source_complete_texture_catalog_count", -1))
	var missing_meshes := int(scene.get_meta("missing_mesh_count", -1))
	var texture_failures := int(scene.get_meta("source_texture_load_failures", -1))

	if packages != EXPECTED_PACKAGES:
		_fail(5, "package count mismatch " + str(packages))
		return
	if meshes != EXPECTED_MESHES:
		_fail(6, "mesh count mismatch " + str(meshes))
		return
	if instances != EXPECTED_INSTANCES:
		_fail(7, "instance count mismatch " + str(instances))
		return
	if actors != EXPECTED_ACTORS:
		_fail(8, "actor count mismatch " + str(actors))
		return
	if lights != EXPECTED_LIGHTS:
		_fail(9, "light count mismatch " + str(lights))
		return
	if textures != EXPECTED_TEXTURES:
		_fail(10, "texture count mismatch " + str(textures))
		return
	if missing_meshes != 0 or texture_failures != 0:
		_fail(
			11,
			"runtime source losses missing_meshes=%d texture_failures=%d"
			% [missing_meshes, texture_failures]
		)
		return

	print(
		"XZOGOT_NACHT_CAPTURE_WORLD_GREEN ",
		"packages=", packages,
		" meshes=", meshes,
		" instances=", instances,
		" actors=", actors,
		" lights=", lights,
		" textures=", textures
	)

	var hud := scene.get_node_or_null("HUD")
	if hud is CanvasLayer:
		(hud as CanvasLayer).visible = false

	# Runtime environment mounting is validated separately. Until the dedicated
	# UE4.21 fog/reflection bridge is visually exact, structural screenshots must
	# not be hidden behind Godot's intentionally approximate fog fallback.
	_prepare_structural_visual_proof(scene)

	var player := scene.get_node_or_null("Player") as CharacterBody3D
	var spawn_camera := scene.get_node_or_null("Player/Head/Camera3D") as Camera3D
	if player == null or spawn_camera == null:
		_fail(12, "source player/camera missing")
		return
	spawn_camera.fov = 72.0
	spawn_camera.near = 0.03
	spawn_camera.far = 800.0
	spawn_camera.current = true

	if not (await _save_view(
		"/tmp/xogot-nacht-spawn.png",
		"spawn",
		true,
		12
	)):
		return

	# Diagnostic A/B: preserve the exact same camera/player transform and hide
	# only Cascade visual nodes. This distinguishes static-world/default-material
	# occlusion from an auto-activated particle effect without changing runtime.
	var particle_visuals := get_nodes_in_group("nacht_source_particle_visual")
	_probe_bonefire_material(scene, particle_visuals)
	var particle_visibility: Array[bool] = []
	var particle_sim_state: Array[Dictionary] = []
	for raw_particle: Node in particle_visuals:
		if raw_particle is Node3D:
			particle_visibility.append((raw_particle as Node3D).visible)
			(raw_particle as Node3D).visible = false
		else:
			particle_visibility.append(false)
		if raw_particle is GPUParticles3D:
			var state_particles := raw_particle as GPUParticles3D
			particle_sim_state.append({
				"emitting": state_particles.emitting,
				"speed_scale": state_particles.speed_scale,
				"use_fixed_seed": state_particles.use_fixed_seed,
				"seed": state_particles.seed,
			})
		else:
			particle_sim_state.append({})
	if not (await _save_view(
		"/tmp/xogot-nacht-spawn-no-particles.png",
		"spawn_no_particles",
		false,
		2
	)):
		return
	for particle_index in range(particle_visuals.size()):
		var raw_particle: Node = particle_visuals[particle_index]
		if raw_particle is Node3D:
			(raw_particle as Node3D).visible = particle_visibility[particle_index]
	print(
		"XZOGOT_NACHT_PARTICLE_OCCLUSION_AB_GREEN nodes=",
		particle_visuals.size()
	)

	var anchors := get_nodes_in_group("nacht_source_actor")
	if anchors.size() != EXPECTED_ACTORS:
		_fail(13, "source actor group mismatch " + str(anchors.size()))
		return

	# Source does not identify one of the ten Pavlov_Spawn actors as the solo
	# gameplay start. Capture all ten from the exact capsule-center transform so
	# visual clearance can be judged from evidence instead of picking by name.
	var spawn_candidates: Array[Node3D] = []
	for raw: Node in anchors:
		if not (raw is Node3D):
			continue
		var anchor := raw as Node3D
		var source_object_path := str(
			anchor.get_meta("source_object_path", "")
		)
		if source_object_path.contains("Pavlov_Spawn"):
			spawn_candidates.append(anchor)
	if spawn_candidates.size() != 10:
		_fail(
			35,
			"source Pavlov spawn candidate coverage mismatch %d/10"
			% spawn_candidates.size()
		)
		return

	var collision := player.get_node_or_null("CollisionShape3D") as CollisionShape3D
	if collision == null:
		_fail(36, "player collision capsule missing for spawn sweep")
		return
	var saved_player_transform := player.global_transform
	var saved_player_velocity := player.velocity
	player.set_physics_process(false)
	player.velocity = Vector3.ZERO
	var head := scene.get_node_or_null("Player/Head") as Node3D
	if head != null:
		head.rotation.x = 0.0

	for spawn_index in range(spawn_candidates.size()):
		var anchor := spawn_candidates[spawn_index]
		var candidate_basis := _capture_player_basis_from_source_anchor(anchor)
		player.global_basis = candidate_basis
		player.global_position = (
			anchor.global_position
			- candidate_basis * collision.position
		)
		spawn_camera.current = true
		var source_object_path := str(
			anchor.get_meta("source_object_path", "")
		)
		var candidate_path := (
			"/tmp/xogot-nacht-spawn-candidate-%02d.png"
			% spawn_index
		)
		print(
			"XZOGOT_NACHT_SPAWN_CANDIDATE_CAPTURE ",
			"index=", spawn_index,
			" source=", source_object_path,
			" anchor=", anchor.global_position,
			" player=", player.global_position
		)
		# Candidate frames intentionally do not fail on low visual spread: an
		# obstructed/inside-geometry image is evidence that the candidate is bad.
		if not (await _save_view(
			candidate_path,
			"spawn_candidate_%02d" % spawn_index,
			false
		)):
			return
		if spawn_index == 2:
			for particle_index in range(particle_visuals.size()):
				var raw_particle: Node = particle_visuals[particle_index]
				if raw_particle is Node3D:
					(raw_particle as Node3D).visible = false
			if not (await _save_view(
				"/tmp/xogot-nacht-spawn-candidate-02-no-particles.png",
				"spawn_candidate_02_no_particles",
				false
			)):
				return
			for particle_index in range(particle_visuals.size()):
				var raw_particle: Node = particle_visuals[particle_index]
				if raw_particle is Node3D:
					(raw_particle as Node3D).visible = particle_visibility[particle_index]
			await _restart_particle_visuals_deterministic(particle_visuals, 30)
			if not (await _save_view(
				"/tmp/xogot-nacht-spawn-candidate-02-particles-deterministic.png",
				"spawn_candidate_02_particles_deterministic",
				false,
				1
			)):
				return
			print(
				"XZOGOT_NACHT_CANDIDATE02_PARTICLE_AB_GREEN nodes=",
				particle_visuals.size(),
				" deterministic_seed=true snapshot_seconds=0.75 frozen=true"
			)

			var systems: Array[String] = []
			for raw_particle: Node in particle_visuals:
				if not (raw_particle is Node3D):
					continue
				var parent := raw_particle.get_parent()
				if parent == null:
					continue
				var system_path := str(
					parent.get_meta("source_particle_system_path", "")
				)
				if not system_path.is_empty() and not systems.has(system_path):
					systems.append(system_path)
			systems.sort()
			for system_index in range(systems.size()):
				var system_path := systems[system_index]
				# Restore the exact authored visibility before every sample.
				for particle_index in range(particle_visuals.size()):
					var raw_particle: Node = particle_visuals[particle_index]
					if raw_particle is Node3D:
						(raw_particle as Node3D).visible = particle_visibility[particle_index]
				for raw_particle: Node in particle_visuals:
					if not (raw_particle is Node3D):
						continue
					var parent := raw_particle.get_parent()
					if parent == null:
						continue
					if str(parent.get_meta("source_particle_system_path", "")) == system_path:
						(raw_particle as Node3D).visible = false
				await _restart_particle_visuals_deterministic(particle_visuals, 30, true)
				var isolate_path := (
					"/tmp/xogot-nacht-spawn-candidate-02-hide-system-%02d.png"
					% system_index
				)
				if not (await _save_view(
					isolate_path,
					"spawn_candidate_02_hide_system_%02d" % system_index,
					false,
					1
				)):
					return
				print(
					"XZOGOT_NACHT_CANDIDATE02_SYSTEM_ISOLATION ",
					"index=", system_index,
					" system=", system_path,
					" deterministic_seed=true snapshot_seconds=0.75 frozen=true forced_restart=true"
				)

				# Complement the hide-A/B with a solo render. This makes each
				# source system independently inspectable even when multiple
				# translucent quads overlap the same camera.
				for raw_particle: Node in particle_visuals:
					if not (raw_particle is Node3D):
						continue
					var parent := raw_particle.get_parent()
					var show_system := (
						parent != null
						and str(parent.get_meta("source_particle_system_path", ""))
							== system_path
					)
					(raw_particle as Node3D).visible = show_system
				await _restart_particle_visuals_deterministic(particle_visuals, 30, true)
				var solo_path := (
					"/tmp/xogot-nacht-spawn-candidate-02-solo-system-%02d.png"
					% system_index
				)
				if not (await _save_view(
					solo_path,
					"spawn_candidate_02_solo_system_%02d" % system_index,
					false,
					1
				)):
					return
				print(
					"XZOGOT_NACHT_CANDIDATE02_SYSTEM_SOLO ",
					"index=", system_index,
					" system=", system_path,
					" deterministic_seed=true snapshot_seconds=0.75 frozen=true forced_restart=true"
				)
			for particle_index in range(particle_visuals.size()):
				var raw_particle: Node = particle_visuals[particle_index]
				if raw_particle is Node3D:
					(raw_particle as Node3D).visible = particle_visibility[particle_index]
				if raw_particle is GPUParticles3D:
					var restore_particles := raw_particle as GPUParticles3D
					var restore_state := particle_sim_state[particle_index]
					if not restore_state.is_empty():
						restore_particles.speed_scale = float(restore_state.get("speed_scale", 1.0))
						restore_particles.use_fixed_seed = bool(restore_state.get("use_fixed_seed", false))
						restore_particles.seed = int(restore_state.get("seed", 0))
						restore_particles.emitting = bool(restore_state.get("emitting", false))
			print("XZOGOT_NACHT_PARTICLE_DIAGNOSTIC_STATE_RESTORED")

	player.global_transform = saved_player_transform
	player.velocity = saved_player_velocity
	player.set_physics_process(true)

	var xs: Array[float] = []
	var ys: Array[float] = []
	var zs: Array[float] = []
	for raw: Node in anchors:
		if raw is Node3D:
			var p := (raw as Node3D).global_position
			xs.append(p.x)
			ys.append(p.y)
			zs.append(p.z)
	if xs.size() < 100:
		_fail(14, "not enough source actor positions for overview")
		return

	# Use 5th-95th percentile bounds so source-authored background/outlier
	# anchors do not pull the overview camera miles away from the playable core.
	var low := Vector3(
		_percentile(xs.duplicate(), 0.05),
		_percentile(ys.duplicate(), 0.05),
		_percentile(zs.duplicate(), 0.05)
	)
	var high := Vector3(
		_percentile(xs.duplicate(), 0.95),
		_percentile(ys.duplicate(), 0.95),
		_percentile(zs.duplicate(), 0.95)
	)
	var center := (low + high) * 0.5
	var span := high - low
	var horizontal_radius := maxf(maxf(span.x, span.z) * 0.5, 12.0)
	var vertical_span := maxf(span.y, 8.0)

	var overview_camera := Camera3D.new()
	overview_camera.name = "NachtSourceOverviewCamera"
	overview_camera.fov = 58.0
	overview_camera.near = 0.05
	overview_camera.far = maxf(1200.0, horizontal_radius * 12.0)
	scene.add_child(overview_camera)
	overview_camera.global_position = center + Vector3(
		horizontal_radius * 0.9,
		maxf(horizontal_radius * 1.15, vertical_span * 1.8),
		horizontal_radius * 0.9
	)
	overview_camera.look_at(center, Vector3.UP)
	overview_camera.current = true

	print(
		"XZOGOT_NACHT_CAPTURE_OVERVIEW_BOUNDS ",
		"low=", low,
		" high=", high,
		" center=", center,
		" camera=", overview_camera.global_position
	)

	if not (await _save_view("/tmp/xogot-nacht-overview.png", "overview")):
		return

	# Runtime-state overview isolation: group by actual ParticleSystem, not by
	# individual visual/emitter node. A system can own several GPUParticles3D
	# nodes, so hiding one node at a time can misattribute the defect.
	var overview_system_paths: Array[String] = []
	var overview_system_indices := {}
	for particle_index in range(particle_visuals.size()):
		var raw_particle: Node = particle_visuals[particle_index]
		if not (raw_particle is Node3D):
			continue
		if not particle_visibility[particle_index]:
			continue
		var visual := raw_particle as Node3D
		var parent := visual.get_parent()
		var system_path := (
			str(parent.get_meta("source_particle_system_path", ""))
			if parent != null
			else ""
		)
		if system_path.is_empty():
			continue
		if not overview_system_indices.has(system_path):
			overview_system_paths.append(system_path)
			overview_system_indices[system_path] = []
		(overview_system_indices[system_path] as Array).append(particle_index)

	for system_index in range(overview_system_paths.size()):
		var system_path := overview_system_paths[system_index]
		var member_indices: Array = overview_system_indices[system_path]
		for raw_index: Variant in member_indices:
			var particle_index := int(raw_index)
			var raw_particle: Node = particle_visuals[particle_index]
			if raw_particle is Node3D:
				(raw_particle as Node3D).visible = false
		var overview_hide_path := (
			"/tmp/xogot-nacht-overview-hide-system-%02d.png" % system_index
		)
		if not (await _save_view(
			overview_hide_path,
			"overview_hide_system_%02d" % system_index,
			false,
			2
		)):
			return
		print(
			"XZOGOT_NACHT_OVERVIEW_SYSTEM_ISOLATION ",
			"index=", system_index,
			" system=", system_path,
			" visual_nodes=", member_indices.size(),
			" forced_restart=false runtime_state=true"
		)
		for raw_index: Variant in member_indices:
			var particle_index := int(raw_index)
			var raw_particle: Node = particle_visuals[particle_index]
			if raw_particle is Node3D:
				(raw_particle as Node3D).visible = particle_visibility[particle_index]

	for particle_index in range(particle_visuals.size()):
		var raw_particle: Node = particle_visuals[particle_index]
		if raw_particle is Node3D:
			(raw_particle as Node3D).visible = false
	if not (await _save_view(
		"/tmp/xogot-nacht-overview-no-particles.png",
		"overview_no_particles",
		false,
		2
	)):
		return
	for particle_index in range(particle_visuals.size()):
		var raw_particle: Node = particle_visuals[particle_index]
		if raw_particle is Node3D:
			(raw_particle as Node3D).visible = particle_visibility[particle_index]
	print("XZOGOT_NACHT_OVERVIEW_PARTICLE_AB_GREEN")

	scene.queue_free()
	await process_frame
	quit(0)
