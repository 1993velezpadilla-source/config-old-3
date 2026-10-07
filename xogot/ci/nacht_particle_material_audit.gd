extends SceneTree

const TARGET_MONSTER := "/Game/CustomMaps/UGC2755515831/InfinityBladeEffects/Effects/FX_Monsters/FX_Monster_Deaths/P_Monster_Death_XLarge.P_Monster_Death_XLarge"
const PARTICLE_GRAPHS := "res://assets/benchmarks/nacht_chronicles/nacht-particle-graphs.json"
const PARTICLE_RUNTIME_AUTHORITY := "res://assets/benchmarks/nacht_chronicles/nacht-particle-runtime-authority.json"

func _init() -> void:
	call_deferred("_audit")


func _texture_alpha_summary(texture: Texture2D) -> Dictionary:
	if texture == null:
		return {"present": false}
	var image := texture.get_image()
	if image == null or image.is_empty():
		return {
			"present": true,
			"resource_path": texture.resource_path,
			"image": false
		}
	var compressed := image.is_compressed()
	if compressed:
		var err := image.decompress()
		if err != OK:
			return {
				"present": true,
				"resource_path": texture.resource_path,
				"image": true,
				"compressed": true,
				"decompress_error": int(err)
			}
	var min_alpha := 1.0
	var max_alpha := 0.0
	var below_half := 0
	var samples := 0
	var step_x := maxi(1, image.get_width() / 32)
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
		"present": true,
		"resource_path": texture.resource_path,
		"width": image.get_width(),
		"height": image.get_height(),
		"compressed": compressed,
		"min_alpha": min_alpha,
		"max_alpha": max_alpha,
		"below_half": below_half,
		"samples": samples
	}

func _monster_material_detail(
	system_path: String,
	node_name: String,
	material: Material
) -> void:
	if system_path != TARGET_MONSTER or not (material is StandardMaterial3D):
		return
	var standard := material as StandardMaterial3D
	print(
		"XZOGOT_NACHT_MONSTER_MATERIAL_DETAIL ",
		"node=", node_name,
		" source=", str(material.get_meta("source_material_path", "")),
		" blend=", str(material.get_meta("source_blend_mode", "")),
		" albedo_color=", standard.albedo_color,
		" albedo_texture=", JSON.stringify(_texture_alpha_summary(standard.albedo_texture)),
		" emission_enabled=", standard.emission_enabled,
		" emission=", standard.emission,
		" emission_texture=", JSON.stringify(_texture_alpha_summary(standard.emission_texture)),
		" vertex_color_as_albedo=", standard.vertex_color_use_as_albedo,
		" billboard=", int(standard.billboard_mode),
		" transparency=", int(standard.transparency),
		" blend_mode=", int(standard.blend_mode),
		" shading_mode=", int(standard.shading_mode)
	)

func _material_row(system_path: String, node_name: String, material: Material) -> void:
	if material == null:
		print("XZOGOT_NACHT_PARTICLE_MATERIAL_AUDIT system=", system_path,
			" node=", node_name, " material=null")
		return
	_monster_material_detail(system_path, node_name, material)
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


func _monster_runtime_row(system_path: String, particles: GPUParticles3D) -> void:
	if system_path != TARGET_MONSTER:
		return
	var process := particles.process_material as ParticleProcessMaterial
	var mesh := particles.draw_pass_1
	var mesh_aabb := AABB()
	var mesh_class := "null"
	if mesh != null:
		mesh_aabb = mesh.get_aabb()
		mesh_class = mesh.get_class()
	var scale_min := -1.0
	var scale_max := -1.0
	var initial_velocity_min := -1.0
	var initial_velocity_max := -1.0
	var source_start_min: Variant = null
	var source_start_max: Variant = null
	var source_scale_bridge := ""
	if process != null:
		scale_min = process.scale_min
		scale_max = process.scale_max
		initial_velocity_min = process.initial_velocity_min
		initial_velocity_max = process.initial_velocity_max
		source_start_min = process.get_meta("source_start_scale_min", null)
		source_start_max = process.get_meta("source_start_scale_max", null)
		source_scale_bridge = str(process.get_meta("source_start_scale_bridge", ""))
	print(
		"XZOGOT_NACHT_MONSTER_RUNTIME ",
		"node=", particles.name,
		" renderer=", str(particles.get_meta("source_particle_renderer_mode", "")),
		" emitter_path=", str(particles.get_meta("source_particle_emitter_path", "")),
		" mesh_path=", str(particles.get_meta("source_particle_mesh_path", "")),
		" material_path=", str(particles.get_meta("source_particle_material_path", "")),
		" mesh_class=", mesh_class,
		" mesh_aabb=", mesh_aabb,
		" amount=", particles.amount,
		" lifetime=", particles.lifetime,
		" emitting=", particles.emitting,
		" one_shot=", particles.one_shot,
		" explosiveness=", particles.explosiveness,
		" local_coords=", particles.local_coords,
		" scale_min=", scale_min,
		" scale_max=", scale_max,
		" source_start_min=", source_start_min,
		" source_start_max=", source_start_max,
		" scale_bridge=", source_scale_bridge,
		" velocity_min=", initial_velocity_min,
		" velocity_max=", initial_velocity_max
	)


func _probe_monster_placement() -> void:
	if not FileAccess.file_exists(PARTICLE_RUNTIME_AUTHORITY):
		print("XZOGOT_NACHT_MONSTER_PLACEMENT missing=", PARTICLE_RUNTIME_AUTHORITY)
		return
	var file := FileAccess.open(PARTICLE_RUNTIME_AUTHORITY, FileAccess.READ)
	if file == null:
		print("XZOGOT_NACHT_MONSTER_PLACEMENT open_failed")
		return
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if not (parsed is Dictionary):
		print("XZOGOT_NACHT_MONSTER_PLACEMENT parse_failed")
		return
	var placements_raw: Variant = (parsed as Dictionary).get("placements", [])
	if not (placements_raw is Array):
		return
	var hits := 0
	for raw_placement: Variant in placements_raw:
		if not (raw_placement is Dictionary):
			continue
		var placement := raw_placement as Dictionary
		if str(placement.get("templateObjectPath", "")) != TARGET_MONSTER:
			continue
		hits += 1
		var props_raw: Variant = placement.get("properties", {})
		var props := props_raw as Dictionary if props_raw is Dictionary else {}
		print(
			"XZOGOT_NACHT_MONSTER_PLACEMENT ",
			"id=", str(placement.get("id", "")),
			" actor=", str(placement.get("actorName", "")),
			" owner_type=", str(placement.get("ownerExportType", "")),
			" owner_class=", str(placement.get("ownerClassPath", "")),
			" component=", str(placement.get("componentName", "")),
			" source_path=", str(placement.get("sourcePath", "")),
			" auto_present=", props.has("autoActivate"),
			" auto_value=", str(props.get("autoActivate", "<missing>")),
			" legacy_bAutoActivate_present=", props.has("bAutoActivate"),
			" properties=", JSON.stringify(props)
		)
	print("XZOGOT_NACHT_MONSTER_PLACEMENT_GREEN hits=", hits)

func _probe_monster_source_graph() -> void:
	if not FileAccess.file_exists(PARTICLE_RUNTIME_AUTHORITY):
		print("XZOGOT_NACHT_MONSTER_SOURCE missing=", PARTICLE_RUNTIME_AUTHORITY)
		return
	var file := FileAccess.open(PARTICLE_RUNTIME_AUTHORITY, FileAccess.READ)
	if file == null:
		print("XZOGOT_NACHT_MONSTER_SOURCE open_failed")
		return
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if not (parsed is Dictionary):
		print("XZOGOT_NACHT_MONSTER_SOURCE parse_failed")
		return
	var systems_raw: Variant = (parsed as Dictionary).get("placedSystems", [])
	if not (systems_raw is Array):
		return
	var interesting := {
		"ParticleLODLevel": true,
		"ParticleModuleRequired": true,
		"ParticleModuleSize": true,
		"ParticleModuleSizeMultiplyLife": true,
		"ParticleModuleSizeScaleBySpeed": true,
		"ParticleModuleLifetime": true,
		"ParticleModuleSpawn": true,
		"ParticleModuleVelocity": true,
		"ParticleModuleTypeDataMesh": true,
		"ParticleModuleMeshMaterial": true,
		"ParticleModuleColor": true,
		"ParticleModuleColorOverLife": true,
	}
	for raw_system: Variant in systems_raw:
		if not (raw_system is Dictionary):
			continue
		var system := raw_system as Dictionary
		if str(system.get("objectPath", "")) != TARGET_MONSTER:
			continue
		var nodes_raw: Variant = system.get("nodes", [])
		var node_count := (nodes_raw as Array).size() if nodes_raw is Array else 0
		print("XZOGOT_NACHT_MONSTER_SOURCE_GREEN nodes=", node_count)
		if nodes_raw is Array:
			for raw_node: Variant in nodes_raw:
				if not (raw_node is Dictionary):
					continue
				var node := raw_node as Dictionary
				var export_type := str(node.get("exportType", ""))
				if not interesting.has(export_type):
					continue
				print(
					"XZOGOT_NACHT_MONSTER_SOURCE_NODE ",
					JSON.stringify({
						"exportType": export_type,
						"objectPath": node.get("objectPath", ""),
						"properties": node.get("properties", {})
					})
				)
		return

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

	_probe_monster_placement()
	_probe_monster_source_graph()
	_probe_monster_placement()

	var visuals := get_nodes_in_group("nacht_source_particle_visual")
	var rows := 0
	for raw: Node in visuals:
		var parent := raw.get_parent()
		var system_path := ""
		if parent != null:
			system_path = str(parent.get_meta("source_particle_system_path", ""))
		if raw is GPUParticles3D:
			var particles := raw as GPUParticles3D
			_monster_runtime_row(system_path, particles)
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
