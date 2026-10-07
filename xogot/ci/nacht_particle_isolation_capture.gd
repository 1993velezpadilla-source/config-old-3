extends SceneTree

const TARGET_CANDIDATES := [4, 5, 6, 9]
const EXPECTED_ACTORS := 11023

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("NACHT_PARTICLE_ISOLATION: " + message)
	quit(code)

func _capture_player_basis_from_source_anchor(anchor: Node3D) -> Basis:
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

func _sampled_mad(a: Image, b: Image, step: int = 4) -> float:
	if a == null or b == null or a.is_empty() or b.is_empty():
		return INF
	if a.get_size() != b.get_size():
		return INF
	var total := 0.0
	var samples := 0
	for y in range(0, a.get_height(), maxi(1, step)):
		for x in range(0, a.get_width(), maxi(1, step)):
			var ca := a.get_pixel(x, y)
			var cb := b.get_pixel(x, y)
			total += (
				absf(ca.r - cb.r)
				+ absf(ca.g - cb.g)
				+ absf(ca.b - cb.b)
			) / 3.0
			samples += 1
	return total / float(maxi(1, samples))

func _set_system_visible(anchors: Array[Node3D], system_path: String, value: bool) -> void:
	for anchor: Node3D in anchors:
		if str(anchor.get_meta("source_particle_system_path", "")) == system_path:
			anchor.visible = value

func _capture_image(settle_frames: int = 1) -> Image:
	for _i in range(maxi(1, settle_frames)):
		await process_frame
	var image := root.get_texture().get_image()
	if image == null:
		return null
	return image.duplicate()

func _run() -> void:
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

	var hud := scene.get_node_or_null("HUD")
	if hud is CanvasLayer:
		(hud as CanvasLayer).visible = false

	# Structural capture parity with nacht_full_map_capture.gd.
	if not bool(scene.get_meta("source_environment_visual_exact", false)):
		for raw_env: Node in get_nodes_in_group("nacht_source_environment_runtime"):
			if raw_env is WorldEnvironment:
				var world := raw_env as WorldEnvironment
				if world.environment != null:
					world.environment.fog_enabled = false

	var player := scene.get_node_or_null("Player") as CharacterBody3D
	var camera := scene.get_node_or_null("Player/Head/Camera3D") as Camera3D
	var collision := scene.get_node_or_null("Player/CollisionShape3D") as CollisionShape3D
	if player == null or camera == null or collision == null:
		_fail(5, "source player/camera/collision missing")
		return
	camera.fov = 72.0
	camera.near = 0.03
	camera.far = 800.0
	camera.current = true

	var actor_nodes := get_nodes_in_group("nacht_source_actor")
	if actor_nodes.size() != EXPECTED_ACTORS:
		_fail(6, "source actor coverage mismatch " + str(actor_nodes.size()))
		return
	var spawn_candidates: Array[Node3D] = []
	for raw_actor: Node in actor_nodes:
		if raw_actor is Node3D:
			var anchor := raw_actor as Node3D
			if str(anchor.get_meta("source_object_path", "")).contains("Pavlov_Spawn"):
				spawn_candidates.append(anchor)
	if spawn_candidates.size() != 10:
		_fail(7, "spawn candidate coverage mismatch " + str(spawn_candidates.size()))
		return

	var semantic_nodes := get_nodes_in_group("nacht_source_particle_semantic")
	var particle_anchors: Array[Node3D] = []
	var systems: Array[String] = []
	for raw_anchor: Node in semantic_nodes:
		if not (raw_anchor is Node3D):
			continue
		var particle_anchor := raw_anchor as Node3D
		particle_anchors.append(particle_anchor)
		var system_path := str(
			particle_anchor.get_meta("source_particle_system_path", "")
		)
		if not system_path.is_empty() and not systems.has(system_path):
			systems.append(system_path)
	systems.sort()
	if particle_anchors.size() != 29 or systems.size() != 16:
		_fail(
			8,
			"particle isolation coverage mismatch anchors=%d systems=%d"
			% [particle_anchors.size(), systems.size()]
		)
		return

	# Let Cascade advance into a representative frame, then freeze every GPU
	# emitter so hide-one-system A/B comparisons cannot be polluted by animation.
	for _i in range(30):
		await process_frame
	var visual_nodes := get_nodes_in_group("nacht_source_particle_visual")
	var frozen := 0
	for raw_visual: Node in visual_nodes:
		if raw_visual is GPUParticles3D:
			(raw_visual as GPUParticles3D).speed_scale = 0.0
			frozen += 1
	print(
		"XZOGOT_NACHT_PARTICLE_ISOLATION_FREEZE_GREEN visuals=",
		visual_nodes.size(),
		" gpu_frozen=",
		frozen
	)

	player.set_physics_process(false)
	player.velocity = Vector3.ZERO
	var head := scene.get_node_or_null("Player/Head") as Node3D
	if head != null:
		head.rotation.x = 0.0

	var report_rows: Array = []
	for raw_index: Variant in TARGET_CANDIDATES:
		var candidate_index := int(raw_index)
		var spawn := spawn_candidates[candidate_index]
		var basis := _capture_player_basis_from_source_anchor(spawn)
		player.global_basis = basis
		player.global_position = spawn.global_position - basis * collision.position
		camera.current = true
		var baseline := await _capture_image(3)
		if baseline == null or baseline.is_empty():
			_fail(9, "baseline capture failed candidate=" + str(candidate_index))
			return
		baseline.save_png(
			"/tmp/nacht-particle-isolation-candidate-%02d-baseline.png"
			% candidate_index
		)

		var scores: Array[Dictionary] = []
		for system_path: String in systems:
			_set_system_visible(particle_anchors, system_path, false)
			var hidden := await _capture_image(1)
			_set_system_visible(particle_anchors, system_path, true)
			await process_frame
			var mad := _sampled_mad(baseline, hidden, 4)
			scores.append({
				"systemPath": system_path,
				"mad": mad,
			})
		scores.sort_custom(
			func(a: Dictionary, b: Dictionary) -> bool:
				return float(a.get("mad", 0.0)) > float(b.get("mad", 0.0))
		)
		var top_count := mini(6, scores.size())
		var top: Array = []
		for score_index in range(top_count):
			top.append(scores[score_index])
		print(
			"XZOGOT_NACHT_PARTICLE_ISOLATION candidate=",
			candidate_index,
			" top=",
			JSON.stringify(top)
		)

		if not scores.is_empty():
			var top_system := str(scores[0].get("systemPath", ""))
			_set_system_visible(particle_anchors, top_system, false)
			var top_hidden := await _capture_image(1)
			_set_system_visible(particle_anchors, top_system, true)
			await process_frame
			if top_hidden != null:
				top_hidden.save_png(
					"/tmp/nacht-particle-isolation-candidate-%02d-top-hidden.png"
					% candidate_index
				)

		report_rows.append({
			"candidate": candidate_index,
			"playerPosition": [
				player.global_position.x,
				player.global_position.y,
				player.global_position.z,
			],
			"scores": scores,
		})

	var report := {
		"schemaVersion": 1,
		"format": "xogot_nacht_particle_isolation_v1",
		"candidateCount": TARGET_CANDIDATES.size(),
		"systemCount": systems.size(),
		"particleAnchorCount": particle_anchors.size(),
		"visualNodeCount": visual_nodes.size(),
		"rows": report_rows,
		"ready": true,
	}
	var out := FileAccess.open("/tmp/nacht-particle-isolation.json", FileAccess.WRITE)
	if out == null:
		_fail(10, "cannot write isolation report")
		return
	out.store_string(JSON.stringify(report, "\t") + "\n")
	out.close()
	print(
		"XZOGOT_NACHT_PARTICLE_ISOLATION_GREEN candidates=",
		TARGET_CANDIDATES.size(),
		" systems=",
		systems.size(),
		" anchors=",
		particle_anchors.size()
	)
	scene.queue_free()
	await process_frame
	quit(0)
