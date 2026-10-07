extends SceneTree

const TARGET_CANDIDATES := [4, 5, 6]
const EXPECTED_ACTORS := 11023
const MONSTER_SYSTEM := "/Game/CustomMaps/UGC2755515831/InfinityBladeEffects/Effects/FX_Monsters/FX_Monster_Deaths/P_Monster_Death_XLarge.P_Monster_Death_XLarge"
const QUAD_SYSTEM := "/Game/CustomMaps/UGC2755515831/CoD/Particles/Quads/quadExplodeSmoke1.quadExplodeSmoke1"

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

func _capture_image(settle_frames: int = 1) -> Image:
	for _i in range(maxi(1, settle_frames)):
		await process_frame
	var image := root.get_texture().get_image()
	if image == null:
		return null
	return image.duplicate()

func _place_player(
	player: CharacterBody3D,
	camera: Camera3D,
	collision: CollisionShape3D,
	spawn: Node3D
) -> void:
	var basis := _capture_player_basis_from_source_anchor(spawn)
	player.global_basis = basis
	player.global_position = spawn.global_position - basis * collision.position
	camera.current = true

func _visual_row(node: GPUParticles3D) -> Dictionary:
	var parent := node.get_parent() as Node3D
	var process := node.process_material as ParticleProcessMaterial
	return {
		"name": node.name,
		"systemPath": (
			str(parent.get_meta("source_particle_system_path", ""))
			if parent != null else ""
		),
		"particleId": (
			str(parent.get_meta("source_particle_id", ""))
			if parent != null else ""
		),
		"materialPath": str(node.get_meta("source_particle_material_path", "")),
		"emitterPath": str(node.get_meta("source_particle_emitter_path", "")),
		"rendererMode": str(node.get_meta("source_particle_renderer_mode", "")),
		"oneShot": node.one_shot,
		"emitting": node.emitting,
		"amount": node.amount,
		"lifetime": node.lifetime,
		"sourceDelay": node.get_meta("source_emitter_delay_seconds", null),
		"sourceDuration": node.get_meta("source_emitter_duration_seconds", null),
		"startScaleBridge": (
			process.get_meta("source_start_scale_bridge", "")
			if process != null else ""
		),
		"startScaleMin": (
			process.get_meta("source_start_scale_min", null)
			if process != null else null
		),
		"startScaleMax": (
			process.get_meta("source_start_scale_max", null)
			if process != null else null
		),
	}

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

	var suspects: Array[GPUParticles3D] = []
	for raw_visual: Node in get_nodes_in_group("nacht_source_particle_visual"):
		if not (raw_visual is GPUParticles3D):
			continue
		var visual := raw_visual as GPUParticles3D
		var parent := visual.get_parent() as Node3D
		if parent == null:
			continue
		var system_path := str(parent.get_meta("source_particle_system_path", ""))
		if system_path == MONSTER_SYSTEM or system_path == QUAD_SYSTEM:
			suspects.append(visual)
	if suspects.size() != 5:
		_fail(8, "suspect visual coverage mismatch " + str(suspects.size()) + "/5")
		return

	# Capture the early frame where Stage 175 showed the cyan/black/fire cards,
	# then freeze only the five known offender emitters for deterministic A/B.
	for _i in range(30):
		await process_frame
	for visual: GPUParticles3D in suspects:
		visual.speed_scale = 0.0

	player.set_physics_process(false)
	player.velocity = Vector3.ZERO
	var head := scene.get_node_or_null("Player/Head") as Node3D
	if head != null:
		head.rotation.x = 0.0

	var early_images: Dictionary = {}
	var report_rows: Array = []
	for raw_index: Variant in TARGET_CANDIDATES:
		var candidate_index := int(raw_index)
		_place_player(player, camera, collision, spawn_candidates[candidate_index])
		var baseline := await _capture_image(3)
		if baseline == null or baseline.is_empty():
			_fail(9, "baseline capture failed candidate=" + str(candidate_index))
			return
		early_images[candidate_index] = baseline
		baseline.save_png(
			"/tmp/nacht-particle-isolation-candidate-%02d-baseline.png"
			% candidate_index
		)

		var scores: Array[Dictionary] = []
		for suspect_index in range(suspects.size()):
			var visual := suspects[suspect_index]
			var row := _visual_row(visual)
			visual.visible = false
			var hidden := await _capture_image(1)
			visual.visible = true
			await process_frame
			row["index"] = suspect_index
			row["mad"] = _sampled_mad(baseline, hidden, 4)
			scores.append(row)
		scores.sort_custom(
			func(a: Dictionary, b: Dictionary) -> bool:
				return float(a.get("mad", 0.0)) > float(b.get("mad", 0.0))
		)
		print(
			"XZOGOT_NACHT_PARTICLE_EMITTER_ISOLATION candidate=",
			candidate_index,
			" scores=",
			JSON.stringify(scores)
		)
		if not scores.is_empty():
			var top_index := int(scores[0].get("index", -1))
			if top_index >= 0 and top_index < suspects.size():
				suspects[top_index].visible = false
				var top_hidden := await _capture_image(1)
				suspects[top_index].visible = true
				await process_frame
				if top_hidden != null:
					top_hidden.save_png(
						"/tmp/nacht-particle-isolation-candidate-%02d-top-hidden.png"
						% candidate_index
					)
		report_rows.append({
			"candidate": candidate_index,
			"scores": scores,
		})

	# Resume source one-shots and let the longest 2.8 s Monster Death family
	# plus its 0.4 s delay fully expire. Seven seconds gives Godot enough room
	# even if a final particle is born at the end of its one-shot emission cycle.
	for visual: GPUParticles3D in suspects:
		visual.speed_scale = 1.0
	for _i in range(420):
		await process_frame

	var settled_rows: Array = []
	for raw_index: Variant in TARGET_CANDIDATES:
		var candidate_index := int(raw_index)
		_place_player(player, camera, collision, spawn_candidates[candidate_index])
		var settled := await _capture_image(3)
		if settled == null or settled.is_empty():
			_fail(10, "settled capture failed candidate=" + str(candidate_index))
			return
		settled.save_png(
			"/tmp/nacht-particle-isolation-candidate-%02d-settled.png"
			% candidate_index
		)
		var early := early_images[candidate_index] as Image
		var settled_mad := _sampled_mad(early, settled, 4)
		settled_rows.append({
			"candidate": candidate_index,
			"earlyToSettledMad": settled_mad,
		})
		print(
			"XZOGOT_NACHT_PARTICLE_SETTLED candidate=",
			candidate_index,
			" early_to_settled_mad=",
			settled_mad
		)

	var final_visuals: Array = []
	for visual: GPUParticles3D in suspects:
		final_visuals.append(_visual_row(visual))
	print(
		"XZOGOT_NACHT_PARTICLE_TIMING_STATE ",
		JSON.stringify(final_visuals)
	)

	var report := {
		"schemaVersion": 2,
		"format": "xogot_nacht_particle_emitter_isolation_v2",
		"candidateCount": TARGET_CANDIDATES.size(),
		"suspectVisualCount": suspects.size(),
		"rows": report_rows,
		"settledRows": settled_rows,
		"finalVisuals": final_visuals,
		"ready": true,
	}
	var out := FileAccess.open("/tmp/nacht-particle-isolation.json", FileAccess.WRITE)
	if out == null:
		_fail(11, "cannot write isolation report")
		return
	out.store_string(JSON.stringify(report, "\t") + "\n")
	out.close()
	print(
		"XZOGOT_NACHT_PARTICLE_ISOLATION_GREEN candidates=",
		TARGET_CANDIDATES.size(),
		" suspects=",
		suspects.size()
	)
	scene.queue_free()
	await process_frame
	quit(0)
