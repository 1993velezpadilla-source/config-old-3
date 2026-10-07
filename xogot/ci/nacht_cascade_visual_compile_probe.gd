extends SceneTree

const VISUAL_RUNTIME_PATH := "res://scripts/nacht_cascade_visual_runtime.gd"
const BENCHMARK_LOADER_PATH := "res://scripts/xziel_benchmark_loader.gd"

func _assert_source_blend_mode(
	loader: Object,
	material_path: String,
	source_mode: String,
	expected_blend_mode: int
) -> bool:
	loader.set("_material_cache", {})
	loader.set("_material_records", {
		material_path: {
			"blendMode": source_mode,
			"canonicalTextures": {},
			"textures": [],
			"colors": [],
			"rawPropertyKeys": [],
		},
	})
	var material_raw: Variant = loader.call("resolve_source_material", material_path)
	if not (material_raw is StandardMaterial3D):
		push_error(
			"NACHT_CASCADE_BLEND_PROBE: failed material construction "
			+ source_mode
		)
		return false

	var material := material_raw as StandardMaterial3D
	if material.transparency != BaseMaterial3D.TRANSPARENCY_ALPHA:
		push_error(
			"NACHT_CASCADE_BLEND_PROBE: transparency mismatch "
			+ source_mode
		)
		return false
	if material.blend_mode != expected_blend_mode:
		push_error(
			"NACHT_CASCADE_BLEND_PROBE: blend mismatch %s got=%d expected=%d"
			% [source_mode, material.blend_mode, expected_blend_mode]
		)
		return false
	if str(material.get_meta("source_blend_mode", "")) != source_mode:
		push_error(
			"NACHT_CASCADE_BLEND_PROBE: source metadata mismatch "
			+ source_mode
		)
		return false
	return true

func _init() -> void:
	# Load at runtime instead of preloading at parser time so Godot reports the
	# exact source file/line when the Cascade runtime itself has a parse error.
	var runtime_resource: Resource = load(VISUAL_RUNTIME_PATH)
	if runtime_resource == null:
		push_error(
			"NACHT_CASCADE_VISUAL_COMPILE_PROBE: runtime load failed "
			+ VISUAL_RUNTIME_PATH
		)
		quit(2)
		return

	var loader_script := load(BENCHMARK_LOADER_PATH) as Script
	if loader_script == null:
		push_error(
			"NACHT_CASCADE_VISUAL_COMPILE_PROBE: loader load failed "
			+ BENCHMARK_LOADER_PATH
		)
		quit(3)
		return
	var loader: Object = loader_script.new()
	loader.set("load_on_ready", false)

	var blend_green := (
		_assert_source_blend_mode(
			loader,
			"/Probe/Translucent",
			"BLEND_Translucent",
			BaseMaterial3D.BLEND_MODE_MIX
		)
		and _assert_source_blend_mode(
			loader,
			"/Probe/Additive",
			"BLEND_Additive",
			BaseMaterial3D.BLEND_MODE_ADD
		)
		and _assert_source_blend_mode(
			loader,
			"/Probe/Modulate",
			"BLEND_Modulate",
			BaseMaterial3D.BLEND_MODE_MUL
		)
		and _assert_source_blend_mode(
			loader,
			"/Probe/AlphaComposite",
			"BLEND_AlphaComposite",
			BaseMaterial3D.BLEND_MODE_PREMULT_ALPHA
		)
	)
	if not blend_green:
		loader.free()
		quit(4)
		return
	print("XZOGOT_NACHT_SOURCE_BLEND_MODES_GREEN modes=4")

	var material := StandardMaterial3D.new()
	material.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	material.billboard_keep_scale = true
	material.vertex_color_use_as_albedo = true
	material.particles_anim_h_frames = 8
	material.particles_anim_v_frames = 8
	material.particles_anim_loop = true

	var process := ParticleProcessMaterial.new()
	process.initial_velocity_min = 0.1
	process.initial_velocity_max = 1.0
	process.direction = Vector3.UP
	process.spread = 45.0
	process.gravity = Vector3.ZERO
	process.anim_speed_min = 1.0
	process.anim_speed_max = 1.0
	process.anim_offset_min = 0.0
	process.anim_offset_max = 1.0

	var quad := QuadMesh.new()
	quad.size = Vector2(0.1, 0.1)
	quad.material = material

	var particles := GPUParticles3D.new()
	particles.amount = 4
	particles.lifetime = 1.0
	particles.randomness = 0.25
	particles.local_coords = true
	particles.process_material = process
	particles.draw_pass_1 = quad
	particles.visibility_aabb = AABB(Vector3(-1.0, -1.0, -1.0), Vector3(2.0, 2.0, 2.0))
	particles.fixed_fps = 30

	var beam_mesh := ImmediateMesh.new()
	beam_mesh.surface_begin(Mesh.PRIMITIVE_LINES, material)
	beam_mesh.surface_add_vertex(Vector3.ZERO)
	beam_mesh.surface_add_vertex(Vector3.UP)
	beam_mesh.surface_end()

	var beam := MeshInstance3D.new()
	beam.mesh = beam_mesh

	var anchor := Node3D.new()
	anchor.add_child(particles)
	anchor.add_child(beam)
	root.add_child(anchor)

	loader.free()
	print("XZOGOT_NACHT_CASCADE_VISUAL_API_GREEN")
	quit()
