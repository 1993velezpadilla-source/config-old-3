extends SceneTree

const NachtCascadeVisualRuntime = preload("res://scripts/nacht_cascade_visual_runtime.gd")

func _init() -> void:
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

	if NachtCascadeVisualRuntime == null:
		push_error("NACHT_CASCADE_VISUAL_COMPILE_PROBE: visual runtime preload failed")
		quit(2)
		return
	print("XZOGOT_NACHT_CASCADE_VISUAL_API_GREEN")
	quit()
