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
	var particle_visibility: Array[bool] = []
	for raw_particle: Node in particle_visuals:
		if raw_particle is Node3D:
			particle_visibility.append((raw_particle as Node3D).visible)
			(raw_particle as Node3D).visible = false
		else:
			particle_visibility.append(false)
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

	player.global_transform = saved_player_transform
	player.velocity = saved_player_velocity
	player.set_physics_process(true)

	# Build the diagnostic overview from the densest horizontal cluster of
	# source player spawns instead of all 11k actor anchors. The actor catalog
	# contains background foliage and non-playable outliers that previously
	# pulled the overview camera outside Nacht.
	var best_cluster: Array[Node3D] = []
	for candidate: Node3D in spawn_candidates:
		var cluster: Array[Node3D] = []
		for other: Node3D in spawn_candidates:
			var delta := other.global_position - candidate.global_position
			if Vector2(delta.x, delta.z).length() <= 5.0:
				cluster.append(other)
		if cluster.size() > best_cluster.size():
			best_cluster = cluster
	if best_cluster.size() < 3:
		_fail(14, "playable spawn cluster unresolved")
		return

	var center := Vector3.ZERO
	for candidate: Node3D in best_cluster:
		center += candidate.global_position
	center /= float(best_cluster.size())

	var representative := best_cluster[0]
	var representative_distance := INF
	for candidate: Node3D in best_cluster:
		var delta := candidate.global_position - center
		var distance := Vector2(delta.x, delta.z).length()
		if distance < representative_distance:
			representative_distance = distance
			representative = candidate

	var overview_basis := _capture_player_basis_from_source_anchor(representative)
	player.global_basis = overview_basis
	player.global_position = (
		representative.global_position
		- overview_basis * collision.position
	)
	player.velocity = Vector3.ZERO
	var saved_fov := spawn_camera.fov
	spawn_camera.fov = 86.0
	spawn_camera.current = true

	print(
		"XZOGOT_NACHT_CAPTURE_OVERVIEW_SPAWN_CLUSTER ",
		"members=", best_cluster.size(),
		" center=", center,
		" representative=",
		representative.get_meta("source_object_path", "")
	)

	if not (await _save_view("/tmp/xogot-nacht-overview.png", "overview")):
		return

	spawn_camera.fov = saved_fov
	player.global_transform = saved_player_transform
	player.velocity = saved_player_velocity
	player.set_physics_process(true)

	scene.queue_free()
	await process_frame
	quit(0)
