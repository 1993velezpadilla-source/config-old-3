extends SceneTree

const TARGET_MONSTER := "/Game/CustomMaps/UGC2755515831/InfinityBladeEffects/Effects/FX_Monsters/FX_Monster_Deaths/P_Monster_Death_XLarge.P_Monster_Death_XLarge"
const TARGET_BONEFIRE := "/Game/CustomMaps/UGC2755515831/M5VFXVOL2/Particles/Reference/Fireloop/2_bonefire2B_fwd2_pt.2_bonefire2B_fwd2_pt"

func _init() -> void:
	call_deferred("_run")

func _fail(message: String) -> void:
	push_error("XZOGOT_NACHT_BLEND_PARITY_FAILURE " + message)
	quit(5)

func _percentile(values: Array[float], fraction: float) -> float:
	values.sort()
	if values.is_empty():
		return 0.0
	var index := clampi(
		int(round(float(values.size() - 1) * clampf(fraction, 0.0, 1.0))),
		0,
		values.size() - 1
	)
	return values[index]

func _luma(color: Color) -> float:
	return color.r * 0.2126 + color.g * 0.7152 + color.b * 0.0722

func _capture(path: String, label: String, min_spread: float = -1.0) -> bool:
	for _i in range(3):
		await process_frame
	var image := root.get_texture().get_image()
	if image == null or image.is_empty():
		_fail(label + " empty")
		return false
	var samples: Array[float] = []
	var step_x := maxi(1, image.get_width() / 160)
	var step_y := maxi(1, image.get_height() / 90)
	for y in range(0, image.get_height(), step_y):
		for x in range(0, image.get_width(), step_x):
			samples.append(_luma(image.get_pixel(x, y)))
	var p05 := _percentile(samples.duplicate(), 0.05)
	var p95 := _percentile(samples.duplicate(), 0.95)
	var spread := p95 - p05
	print(
		"XZOGOT_NACHT_BLEND_PARITY_FRAME ",
		"label=", label,
		" p05=", p05,
		" p95=", p95,
		" spread=", spread
	)
	if min_spread >= 0.0 and spread < min_spread:
		_fail(label + " visually occluded spread=" + str(spread))
		return false
	if image.save_png(path) != OK:
		_fail(label + " save")
		return false
	return true

func _candidate_basis(anchor: Node3D) -> Basis:
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

func _set_only_system(
	particle_visuals: Array[Node],
	original_visibility: Array[bool],
	system_path: String
) -> void:
	for index in range(particle_visuals.size()):
		var raw := particle_visuals[index]
		if not (raw is Node3D):
			continue
		var parent := raw.get_parent()
		var matches := (
			parent != null
			and str(parent.get_meta("source_particle_system_path", "")) == system_path
		)
		(raw as Node3D).visible = original_visibility[index] and matches


func _monster_visual_nodes(particle_visuals: Array[Node]) -> Array[Node3D]:
	var result: Array[Node3D] = []
	for raw in particle_visuals:
		if not (raw is Node3D):
			continue
		var parent := raw.get_parent()
		if (
			parent != null
			and str(parent.get_meta("source_particle_system_path", "")) == TARGET_MONSTER
		):
			result.append(raw as Node3D)
	return result

func _set_only_visual_node(
	particle_visuals: Array[Node],
	original_visibility: Array[bool],
	target: Node3D
) -> void:
	for index in range(particle_visuals.size()):
		var raw := particle_visuals[index]
		if raw is Node3D:
			(raw as Node3D).visible = original_visibility[index] and raw == target

func _safe_capture_token(value: String) -> String:
	return value.to_lower().replace("/", "_").replace(" ", "_")

func _restore_visibility(
	particle_visuals: Array[Node],
	original_visibility: Array[bool]
) -> void:
	for index in range(particle_visuals.size()):
		if particle_visuals[index] is Node3D:
			(particle_visuals[index] as Node3D).visible = original_visibility[index]

func _freeze_particles(particle_visuals: Array[Node]) -> void:
	for index in range(particle_visuals.size()):
		var raw := particle_visuals[index]
		if not (raw is GPUParticles3D):
			continue
		var particles := raw as GPUParticles3D
		particles.use_fixed_seed = true
		particles.seed = 4242 + index * 7919
		particles.speed_scale = 0.0
		particles.restart(false)
		particles.request_particles_process(0.75)
	await process_frame
	await process_frame

func _probe_target_materials(particle_visuals: Array[Node]) -> bool:
	var target_nodes := 0
	var opaque_nodes := 0
	for raw in particle_visuals:
		if not (raw is GPUParticles3D):
			continue
		var parent := raw.get_parent()
		if parent == null:
			continue
		var system_path := str(parent.get_meta("source_particle_system_path", ""))
		if system_path != TARGET_MONSTER and system_path != TARGET_BONEFIRE:
			continue
		target_nodes += 1
		var particles := raw as GPUParticles3D
		var mesh := particles.draw_pass_1
		var material: Material = null
		if mesh != null and mesh.get_surface_count() > 0:
			material = mesh.surface_get_material(0)
		var blend := ""
		var transparency := -1
		if material is StandardMaterial3D:
			var standard := material as StandardMaterial3D
			blend = str(standard.get_meta("source_blend_mode", ""))
			transparency = int(standard.transparency)
			if blend == "BLEND_Opaque" or transparency == int(BaseMaterial3D.TRANSPARENCY_DISABLED):
				opaque_nodes += 1
		print(
			"XZOGOT_NACHT_BLEND_PARITY_MATERIAL ",
			"system=", system_path,
			" material=", str(raw.get_meta("source_particle_material_path", "")),
			" blend=", blend,
			" transparency=", transparency
		)
	if target_nodes <= 0:
		_fail("target particle nodes missing")
		return false
	if opaque_nodes != 0:
		_fail("target particle material remained opaque count=" + str(opaque_nodes))
		return false
	print(
		"XZOGOT_NACHT_BLEND_PARITY_MATERIAL_GREEN nodes=",
		target_nodes,
		" opaque=0"
	)
	return true

func _run() -> void:
	var packed := load("res://nacht_full_map.tscn") as PackedScene
	if packed == null:
		_fail("nacht scene missing")
		return
	var scene := packed.instantiate() as Node3D
	if scene == null:
		_fail("nacht instantiate")
		return
	root.add_child(scene)

	var ready := false
	for _i in range(3000):
		await create_timer(0.05).timeout
		if bool(scene.get_meta("nacht_full_map_ready", false)):
			ready = true
			break
	if not ready:
		_fail("nacht ready timeout")
		return

	var hud := scene.get_node_or_null("HUD")
	if hud is CanvasLayer:
		(hud as CanvasLayer).visible = false
	if not bool(scene.get_meta("source_environment_visual_exact", false)):
		for raw in get_nodes_in_group("nacht_source_environment_runtime"):
			if raw is WorldEnvironment:
				var world := raw as WorldEnvironment
				if world.environment != null:
					world.environment.fog_enabled = false

	var player := scene.get_node_or_null("Player") as CharacterBody3D
	var camera := scene.get_node_or_null("Player/Head/Camera3D") as Camera3D
	var collision := scene.get_node_or_null("Player/CollisionShape3D") as CollisionShape3D
	if player == null or camera == null or collision == null:
		_fail("player camera collision missing")
		return
	camera.current = true
	camera.fov = 72.0
	camera.near = 0.03
	camera.far = 800.0
	player.set_physics_process(false)
	player.velocity = Vector3.ZERO

	var candidates: Array[Node3D] = []
	for raw in get_nodes_in_group("nacht_source_actor"):
		if raw is Node3D and str(raw.get_meta("source_object_path", "")).contains("Pavlov_Spawn"):
			candidates.append(raw as Node3D)
	if candidates.size() != 10:
		_fail("spawn candidates=" + str(candidates.size()))
		return
	var anchor := candidates[2]
	var basis := _candidate_basis(anchor)
	player.global_basis = basis
	player.global_position = anchor.global_position - basis * collision.position

	var particle_visuals := get_nodes_in_group("nacht_source_particle_visual")
	var original_visibility: Array[bool] = []
	for raw in particle_visuals:
		original_visibility.append(
			(raw as Node3D).visible if raw is Node3D else false
		)

	if not _probe_target_materials(particle_visuals):
		return

	# Baseline structural frame.
	for raw in particle_visuals:
		if raw is Node3D:
			(raw as Node3D).visible = false
	if not (await _capture(
		"/tmp/xogot-nacht-blend-parity-no-particles.png",
		"no_particles",
		0.10
	)):
		return

	_restore_visibility(particle_visuals, original_visibility)
	await _freeze_particles(particle_visuals)
	if not (await _capture(
		"/tmp/xogot-nacht-blend-parity-all.png",
		"all_particles",
		0.10
	)):
		return

	_set_only_system(particle_visuals, original_visibility, TARGET_MONSTER)
	await _freeze_particles(particle_visuals)
	if not (await _capture(
		"/tmp/xogot-nacht-blend-parity-monster-death-xl.png",
		"monster_death_xl",
		0.10
	)):
		return

	var monster_nodes := _monster_visual_nodes(particle_visuals)
	if monster_nodes.size() != 4:
		_fail("monster visual node count=" + str(monster_nodes.size()))
		return
	for monster_index in range(monster_nodes.size()):
		var monster_node := monster_nodes[monster_index]
		_set_only_visual_node(particle_visuals, original_visibility, monster_node)
		await _freeze_particles(particle_visuals)
		var node_token := _safe_capture_token(monster_node.name)
		print(
			"XZOGOT_NACHT_MONSTER_EMITTER_ISOLATION ",
			"index=", monster_index,
			" node=", monster_node.name,
			" renderer=", str(monster_node.get_meta("source_particle_renderer_mode", "")),
			" emitter_path=", str(monster_node.get_meta("source_particle_emitter_path", "")),
			" mesh_path=", str(monster_node.get_meta("source_particle_mesh_path", "")),
			" material_path=", str(monster_node.get_meta("source_particle_material_path", ""))
		)
		if not (await _capture(
			"/tmp/xogot-nacht-blend-parity-monster-emitter-%02d-%s.png" % [
				monster_index,
				node_token
			],
			"monster_emitter_%02d" % monster_index,
			0.10
		)):
			return

	_set_only_system(particle_visuals, original_visibility, TARGET_BONEFIRE)
	await _freeze_particles(particle_visuals)
	if not (await _capture(
		"/tmp/xogot-nacht-blend-parity-bonefire.png",
		"bonefire",
		0.10
	)):
		return

	print("XZOGOT_NACHT_BLEND_PARITY_GREEN")
	quit(0)
