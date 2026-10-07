extends RefCounted

const ParticleSource = preload("res://scripts/nacht_particle_source.gd")

## First visual execution layer for source-authored UE4.21 Cascade graphs.
##
## This layer intentionally does NOT claim 1:1 Cascade parity yet. It mounts
## real Godot render nodes from source material/graph values while preserving
## an explicit exact=false result until emitter-to-LOD/module mapping, mesh
## particles, beam noise, curves and per-particle lights are reproduced fully.

static func _canonical(raw: String) -> String:
	var value := raw.strip_edges().replace("\\", "/")
	var quote := value.find("'")
	if quote >= 0 and value.ends_with("'"):
		value = value.substr(quote + 1, value.length() - quote - 2)
	if value.begins_with("Content/"):
		value = "/Game/" + value.substr(8)
	elif value.begins_with("Game/"):
		value = "/" + value
	return value.to_lower()


static func _find_system(graphs: Dictionary, object_path: String) -> Dictionary:
	var wanted := _canonical(object_path)
	for raw: Variant in graphs.get("systems", []):
		if not (raw is Dictionary):
			continue
		var system := raw as Dictionary
		if _canonical(str(system.get("objectPath", ""))) == wanted:
			return system
	return {}


static func _node_by_path(system: Dictionary, raw_path: String) -> Dictionary:
	var wanted := _canonical(raw_path)
	if wanted.is_empty():
		return {}
	for raw: Variant in system.get("nodes", []):
		if not (raw is Dictionary):
			continue
		var node := raw as Dictionary
		if _canonical(str(node.get("objectPath", ""))) == wanted:
			return node
	return {}


static func _float_samples(system: Dictionary, value: Variant) -> Array[float]:
	var result: Array[float] = []
	var distribution := ParticleSource.distribution(value)
	for sample: float in ParticleSource.table_float_values(distribution):
		result.append(sample)
	for key: String in ["MinValue", "MaxValue"]:
		if distribution.has(key):
			var raw: Variant = ParticleSource.unwrap(distribution[key])
			if raw is float or raw is int:
				result.append(float(raw))
	var dist_path := str(distribution.get("Distribution", ""))
	if not dist_path.is_empty():
		var node := _node_by_path(system, dist_path)
		if not node.is_empty():
			var props := ParticleSource.properties(node)
			for key: String in ["Constant", "Min", "Max"]:
				var raw: Variant = ParticleSource.unwrap(props.get(key))
				if raw is float or raw is int:
					result.append(float(raw))
	return result


static func _vector_samples(system: Dictionary, value: Variant) -> Array[Vector3]:
	var result: Array[Vector3] = []
	var distribution := ParticleSource.distribution(value)
	for key: String in ["MinValueVec", "MaxValueVec"]:
		if distribution.has(key):
			var decoded := ParticleSource.vector3(distribution[key], Vector3.INF)
			if not decoded.is_equal_approx(Vector3.INF):
				result.append(decoded)
	var table := ParticleSource.table_float_values(distribution)
	if table.size() >= 3 and table.size() % 3 == 0:
		for i in range(0, table.size(), 3):
			result.append(Vector3(table[i], table[i + 1], table[i + 2]))
	var dist_path := str(distribution.get("Distribution", ""))
	if not dist_path.is_empty():
		var node := _node_by_path(system, dist_path)
		if not node.is_empty():
			var props := ParticleSource.properties(node)
			for key: String in ["Constant", "Min", "Max"]:
				var decoded := ParticleSource.vector3(props.get(key), Vector3.INF)
				if not decoded.is_equal_approx(Vector3.INF):
					result.append(decoded)
	return result


static func _all_float_samples(system: Dictionary, export_type: String, property_name: String) -> Array[float]:
	var result: Array[float] = []
	for node: Dictionary in ParticleSource.nodes_by_type(system, export_type):
		var props := ParticleSource.properties(node)
		for sample: float in _float_samples(system, props.get(property_name)):
			result.append(sample)
	return result


static func _all_vector_samples(system: Dictionary, export_type: String, property_name: String) -> Array[Vector3]:
	var result: Array[Vector3] = []
	for node: Dictionary in ParticleSource.nodes_by_type(system, export_type):
		var props := ParticleSource.properties(node)
		for sample: Vector3 in _vector_samples(system, props.get(property_name)):
			result.append(sample)
	return result


static func _max_abs_component(samples: Array[Vector3]) -> float:
	var result := 0.0
	for sample: Vector3 in samples:
		result = maxf(result, absf(sample.x), absf(sample.y), absf(sample.z))
	return result


static func _min_max_length(samples: Array[Vector3]) -> Vector2:
	if samples.is_empty():
		return Vector2.ZERO
	var lo := INF
	var hi := 0.0
	for sample: Vector3 in samples:
		var length := sample.length()
		lo = minf(lo, length)
		hi = maxf(hi, length)
	return Vector2(0.0 if is_inf(lo) else lo, hi)


static func _mean_vector(samples: Array[Vector3]) -> Vector3:
	if samples.is_empty():
		return Vector3.ZERO
	var result := Vector3.ZERO
	for sample: Vector3 in samples:
		result += sample
	return result / float(samples.size())


static func _material_paths(system: Dictionary, descriptor: Dictionary) -> Array[String]:
	var result: Array[String] = []
	for node: Dictionary in ParticleSource.nodes_by_type(system, "ParticleModuleRequired"):
		var path := str(ParticleSource.properties(node).get("Material", ""))
		if not path.is_empty() and not result.has(path):
			result.append(path)
	for node: Dictionary in ParticleSource.nodes_by_type(system, "ParticleModuleMeshMaterial"):
		var materials_raw: Variant = ParticleSource.properties(node).get("MeshMaterials", [])
		if materials_raw is Array:
			for raw: Variant in materials_raw:
				var path := str(raw)
				if not path.is_empty() and not result.has(path):
					result.append(path)
	for key: String in ["materialPath", "meshMaterialPath", "spriteMaterialPath"]:
		var path := str(descriptor.get(key, ""))
		if not path.is_empty() and not result.has(path):
			result.append(path)
	for key: String in ["materialPaths", "requiredMaterialPaths", "meshMaterialPaths"]:
		var raw: Variant = descriptor.get(key, [])
		if raw is Array:
			for item: Variant in raw:
				var path := str(item)
				if not path.is_empty() and not result.has(path):
					result.append(path)
	return result


static func _source_material(loader: Node, path: String) -> StandardMaterial3D:
	if loader == null or path.is_empty() or not loader.has_method("_material_for_path"):
		return null
	var raw: Variant = loader.call("_material_for_path", path)
	if not (raw is StandardMaterial3D):
		return null
	var duplicated: Resource = (raw as StandardMaterial3D).duplicate(true)
	if not (duplicated is StandardMaterial3D):
		return null
	var material := duplicated as StandardMaterial3D
	material.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	material.billboard_keep_scale = true
	material.vertex_color_use_as_albedo = true
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	return material


static func _subuv_grid(system: Dictionary) -> Vector2i:
	var h := 1
	var v := 1
	for node: Dictionary in ParticleSource.nodes_by_type(system, "ParticleModuleRequired"):
		var props := ParticleSource.properties(node)
		h = maxi(h, int(props.get("SubImages_Horizontal", 1)))
		v = maxi(v, int(props.get("SubImages_Vertical", 1)))
	return Vector2i(h, v)


static func _subuv_frame_rate(system: Dictionary) -> float:
	var result := 0.0
	for node: Dictionary in ParticleSource.nodes_by_type(system, "ParticleModuleSubUVMovie"):
		var props := ParticleSource.properties(node)
		for sample: float in _float_samples(system, props.get("FrameRate")):
			result = maxf(result, sample)
	return result


static func _peak_active(system: Dictionary) -> int:
	var result := 0
	for node: Dictionary in ParticleSource.nodes_by_type(system, "ParticleLODLevel"):
		result = maxi(result, int(ParticleSource.properties(node).get("PeakActiveParticles", 0)))
	return result


static func _burst_count(system: Dictionary) -> int:
	var result := 0
	for node: Dictionary in ParticleSource.nodes_by_type(system, "ParticleModuleSpawn"):
		var raw: Variant = ParticleSource.properties(node).get("BurstList", [])
		if not (raw is Array):
			continue
		for burst_raw: Variant in raw:
			if burst_raw is Dictionary:
				result += maxi(0, int((burst_raw as Dictionary).get("Count", 0)))
	return result


static func _uses_local_space(system: Dictionary) -> bool:
	for node: Dictionary in ParticleSource.nodes_by_type(system, "ParticleModuleRequired"):
		if bool(ParticleSource.properties(node).get("bUseLocalSpace", false)):
			return true
	return false


static func _auto_activate(placement: Dictionary) -> bool:
	var props_raw: Variant = placement.get("properties", {})
	if props_raw is Dictionary:
		var props := props_raw as Dictionary
		if props.has("bAutoActivate"):
			return bool(ParticleSource.unwrap(props["bAutoActivate"]))
	return true


static func _build_sprite_emitter(
	anchor: Node3D,
	system: Dictionary,
	material_path: String,
	loader: Node,
	auto_activate: bool,
	index: int
) -> Dictionary:
	var material := _source_material(loader, material_path)
	if material == null:
		return {
			"mounted": false,
			"materialResolved": false,
			"nodeCount": 0,
		}

	var lifetimes := _all_float_samples(system, "ParticleModuleLifetime", "Lifetime")
	var lifetime_min := 1.0
	var lifetime_max := 1.0
	if not lifetimes.is_empty():
		lifetime_min = maxf(0.001, lifetimes.min())
		lifetime_max = maxf(lifetime_min, lifetimes.max())

	var sizes := _all_vector_samples(system, "ParticleModuleSize", "StartSize")
	var size_ue := _max_abs_component(sizes)
	if size_ue <= 0.0:
		size_ue = 1.0

	var velocities := _all_vector_samples(system, "ParticleModuleVelocity", "StartVelocity")
	var velocity_lengths := _min_max_length(velocities)
	var velocity_mean := _mean_vector(velocities)

	var accelerations := _all_vector_samples(system, "ParticleModuleAcceleration", "Acceleration")
	var acceleration := _mean_vector(accelerations) * 0.01

	var spawn_rates := _all_float_samples(system, "ParticleModuleSpawn", "Rate")
	var spawn_rate := 0.0 if spawn_rates.is_empty() else maxf(0.0, spawn_rates.max())
	var burst_count := _burst_count(system)
	var amount := _peak_active(system)
	if amount <= 0:
		amount = maxi(1, int(ceil(spawn_rate * lifetime_max)) + burst_count)
	amount = clampi(amount, 1, 4096)

	var process := ParticleProcessMaterial.new()
	if velocity_lengths.y > 0.0:
		process.initial_velocity_min = velocity_lengths.x * 0.01
		process.initial_velocity_max = velocity_lengths.y * 0.01
		if velocity_mean.length_squared() > 0.000001:
			process.direction = velocity_mean.normalized()
			process.spread = 45.0
		else:
			process.spread = 180.0
	process.gravity = acceleration

	var grid := _subuv_grid(system)
	material.particles_anim_h_frames = grid.x
	material.particles_anim_v_frames = grid.y
	material.particles_anim_loop = true
	if grid.x * grid.y > 1:
		var source_fps := _subuv_frame_rate(system)
		var cycles := 1.0
		if source_fps > 0.0:
			cycles = source_fps * lifetime_max / float(grid.x * grid.y)
		process.anim_speed_min = cycles
		process.anim_speed_max = cycles
		process.anim_offset_min = 0.0
		process.anim_offset_max = 1.0

	var quad := QuadMesh.new()
	var size_m := maxf(0.001, size_ue * 0.01)
	quad.size = Vector2(size_m, size_m)
	quad.material = material

	var particles := GPUParticles3D.new()
	particles.name = "CascadeSpriteEmitter_%02d" % index
	particles.amount = amount
	particles.lifetime = lifetime_max
	particles.randomness = clampf(1.0 - (lifetime_min / lifetime_max), 0.0, 1.0)
	particles.local_coords = _uses_local_space(system)
	particles.process_material = process
	particles.draw_pass_1 = quad
	particles.visibility_aabb = AABB(
		Vector3(-8.0, -8.0, -8.0),
		Vector3(16.0, 16.0, 16.0)
	)
	particles.fixed_fps = 30
	particles.emitting = auto_activate
	particles.add_to_group("nacht_source_particle_visual")
	particles.set_meta("source_particle_material_path", material_path)
	particles.set_meta("source_particle_aggregate_renderer", true)
	anchor.add_child(particles)

	return {
		"mounted": true,
		"materialResolved": true,
		"nodeCount": 1,
		"amount": amount,
		"lifetimeMin": lifetime_min,
		"lifetimeMax": lifetime_max,
		"sizeUE": size_ue,
		"spawnRate": spawn_rate,
	}


static func _build_beam(
	anchor: Node3D,
	system: Dictionary,
	descriptor: Dictionary,
	material_path: String,
	loader: Node
) -> Dictionary:
	var material := _source_material(loader, material_path)
	if material == null:
		return {"mounted": false, "materialResolved": false, "nodeCount": 0}
	material.billboard_mode = BaseMaterial3D.BILLBOARD_DISABLED
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED

	var target_raw: Variant = descriptor.get("targetUEcm", Vector3.ZERO)
	var target := target_raw as Vector3 if target_raw is Vector3 else Vector3.ZERO
	target *= 0.01
	if target.length_squared() < 0.000001:
		return {"mounted": false, "materialResolved": true, "nodeCount": 0}

	var immediate := ImmediateMesh.new()
	immediate.surface_begin(Mesh.PRIMITIVE_LINES, material)
	immediate.surface_add_vertex(Vector3.ZERO)
	immediate.surface_add_vertex(target)
	immediate.surface_end()

	var beam := MeshInstance3D.new()
	beam.name = "CascadeBeam"
	beam.mesh = immediate
	beam.add_to_group("nacht_source_particle_visual")
	beam.set_meta("source_particle_material_path", material_path)
	beam.set_meta("source_beam_target_ue_cm", descriptor.get("targetUEcm"))
	beam.set_meta("source_beam_noise_frequency", descriptor.get("noiseFrequency", 0))
	anchor.add_child(beam)

	return {
		"mounted": true,
		"materialResolved": true,
		"nodeCount": 1,
	}


static func mount_anchor(
	anchor: Node3D,
	descriptor: Dictionary,
	graphs: Dictionary,
	loader: Node,
	placement: Dictionary
) -> Dictionary:
	var system_path := str(descriptor.get("systemPath", ""))
	var system := _find_system(graphs, system_path)
	if system.is_empty():
		return {
			"mounted": false,
			"exact": false,
			"visualNodeCount": 0,
			"resolvedMaterialCount": 0,
			"unresolvedMaterialCount": 0,
			"error": "source system missing",
		}

	var paths := _material_paths(system, descriptor)
	var resolved_materials := 0
	var unresolved_materials := 0
	var visual_nodes := 0
	var auto_activate := _auto_activate(placement)

	if descriptor.has("targetUEcm") and descriptor.has("noiseFrequency"):
		if not paths.is_empty():
			var beam_report := _build_beam(
				anchor,
				system,
				descriptor,
				paths[0],
				loader
			)
			visual_nodes += int(beam_report.get("nodeCount", 0))
			if bool(beam_report.get("materialResolved", false)):
				resolved_materials += 1
			else:
				unresolved_materials += 1
	else:
		for index in range(paths.size()):
			var report := _build_sprite_emitter(
				anchor,
				system,
				paths[index],
				loader,
				auto_activate,
				index
			)
			visual_nodes += int(report.get("nodeCount", 0))
			if bool(report.get("materialResolved", false)):
				resolved_materials += 1
			else:
				unresolved_materials += 1

	anchor.set_meta("source_particle_visual_node_count", visual_nodes)
	anchor.set_meta("source_particle_visual_material_count", resolved_materials)
	anchor.set_meta("source_particle_visual_unresolved_material_count", unresolved_materials)
	anchor.set_meta("source_particle_visual_exact", false)

	return {
		"mounted": visual_nodes > 0,
		# Aggregate source values are real, but this first renderer does not yet
		# preserve per-emitter LOD/module associations. Never call it exact.
		"exact": false,
		"visualNodeCount": visual_nodes,
		"resolvedMaterialCount": resolved_materials,
		"unresolvedMaterialCount": unresolved_materials,
		"materialPathCount": paths.size(),
		"systemPath": system_path,
	}
