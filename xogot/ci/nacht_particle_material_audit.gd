extends SceneTree

func _init() -> void:
	call_deferred("_audit")

func _material_row(system_path: String, node_name: String, material: Material) -> void:
	if material == null:
		print("XZOGOT_NACHT_PARTICLE_MATERIAL_AUDIT system=", system_path,
			" node=", node_name, " material=null")
		return
	var source_path := str(material.get_meta("source_material_path", ""))
	var source_blend := str(material.get_meta("source_blend_mode", ""))
	var transparency := -1
	var blend_mode := -1
	var hframes := 1
	var vframes := 1
	if material is StandardMaterial3D:
		var standard := material as StandardMaterial3D
		transparency = int(standard.transparency)
		blend_mode = int(standard.blend_mode)
		hframes = standard.particles_anim_h_frames
		vframes = standard.particles_anim_v_frames
	print(
		"XZOGOT_NACHT_PARTICLE_MATERIAL_AUDIT ",
		"system=", system_path,
		" node=", node_name,
		" material_path=", source_path,
		" source_blend=", source_blend,
		" godot_transparency=", transparency,
		" godot_blend=", blend_mode,
		" hframes=", hframes,
		" vframes=", vframes,
		" class=", material.get_class()
	)

func _audit() -> void:
	var packed := load("res://nacht_full_map.tscn") as PackedScene
	if packed == null:
		push_error("XZOGOT_NACHT_PARTICLE_MATERIAL_AUDIT_FAILURE scene_missing")
		quit(5)
		return
	var scene := packed.instantiate() as Node3D
	root.add_child(scene)
	var ready := false
	for _i in range(3000):
		await create_timer(0.05).timeout
		if bool(scene.get_meta("nacht_full_map_ready", false)):
			ready = true
			break
	if not ready:
		push_error("XZOGOT_NACHT_PARTICLE_MATERIAL_AUDIT_FAILURE map_not_ready")
		quit(5)
		return

	var visuals := get_nodes_in_group("nacht_source_particle_visual")
	var rows := 0
	for raw: Node in visuals:
		var parent := raw.get_parent()
		var system_path := ""
		if parent != null:
			system_path = str(parent.get_meta("source_particle_system_path", ""))
		if raw is GPUParticles3D:
			var particles := raw as GPUParticles3D
			for pass_index in range(1, particles.draw_passes + 1):
				var mesh := particles.get("draw_pass_%d" % pass_index) as Mesh
				if mesh == null:
					continue
				for surface_index in range(mesh.get_surface_count()):
					_material_row(
						system_path,
						raw.name + "/pass%d/surface%d" % [pass_index, surface_index],
						mesh.surface_get_material(surface_index)
					)
					rows += 1
		elif raw is MeshInstance3D:
			var mesh_instance := raw as MeshInstance3D
			if mesh_instance.mesh == null:
				continue
			for surface_index in range(mesh_instance.mesh.get_surface_count()):
				_material_row(
					system_path,
					raw.name + "/surface%d" % surface_index,
					mesh_instance.mesh.surface_get_material(surface_index)
				)
				rows += 1

	print(
		"XZOGOT_NACHT_PARTICLE_MATERIAL_AUDIT_GREEN ",
		"visual_nodes=", visuals.size(),
		" material_rows=", rows
	)
	quit(0)
