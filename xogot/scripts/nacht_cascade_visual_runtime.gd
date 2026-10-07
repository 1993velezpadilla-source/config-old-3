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


static func _ue_vector_to_xziel(value: Vector3) -> Vector3:
	# Same basis used by NachtSourceActorsAndLights:
	# UE +X -> Godot -Z, UE +Y -> Godot -X, UE +Z -> Godot +Y.
	return Vector3(-value.y, value.z, -value.x)


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
		result = maxf(result, maxf(absf(sample.x), maxf(absf(sample.y), absf(sample.z))))
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
	if loader == null or path.is_empty():
		push_warning("NACHT_CASCADE_MATERIAL_UNRESOLVED path=%s reason=loader_or_path" % path)
		return null
	if not loader.has_method("resolve_source_material"):
		push_warning("NACHT_CASCADE_MATERIAL_UNRESOLVED path=%s reason=resolver_missing" % path)
		return null
	var raw: Variant = loader.call("resolve_source_material", path)
	if not (raw is StandardMaterial3D):
		var raw_type := "null" if raw == null else str(typeof(raw))
		push_warning(
			"NACHT_CASCADE_MATERIAL_UNRESOLVED path=%s reason=material_lookup raw_type=%s"
			% [path, raw_type]
		)
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
		# UEParticleSceneExtract serializes the resolved source value as
		# `autoActivate`. Keep the legacy cooked-property spelling as a
		# compatibility fallback for older manifests, but never skip the
		# normalized authority field.
		if props.has("autoActivate"):
			return bool(ParticleSource.unwrap(props["autoActivate"]))
		if props.has("bAutoActivate"):
			return bool(ParticleSource.unwrap(props["bAutoActivate"]))
	return true


static func _emitter_key(lod_node: Dictionary) -> String:
	var path := str(lod_node.get("objectPath", ""))
	var marker := ".ParticleLODLevel_"
	var index := path.find(marker)
	if index < 0:
		return path
	return path.substr(0, index)


static func _lod_level(props: Dictionary) -> float:
	var raw: Variant = props.get("Level", 0.0)
	if raw is float or raw is int:
		return float(raw)
	return 0.0


static func _source_emitters(system: Dictionary) -> Array[Dictionary]:
	var chosen: Dictionary = {}
	for lod: Dictionary in ParticleSource.nodes_by_type(system, "ParticleLODLevel"):
		var props := ParticleSource.properties(lod)
		if not bool(props.get("bEnabled", true)):
			continue
		var key := _emitter_key(lod)
		var level := _lod_level(props)
		if chosen.has(key):
			var existing := chosen[key] as Dictionary
			if float(existing.get("level", INF)) <= level:
				continue
		var module_nodes: Array[Dictionary] = []
		var raw_modules: Variant = props.get("Modules", [])
		if raw_modules is Array:
			for raw_path: Variant in raw_modules:
				var module := _node_by_path(system, str(raw_path))
				if not module.is_empty():
					module_nodes.append(module)
		chosen[key] = {
			"key": key,
			"level": level,
			"peak": maxi(1, int(props.get("PeakActiveParticles", 1))),
			"required": _node_by_path(system, str(props.get("RequiredModule", ""))),
			"spawn": _node_by_path(system, str(props.get("SpawnModule", ""))),
			"typeData": _node_by_path(system, str(props.get("TypeDataModule", ""))),
			"modules": module_nodes,
			"lodPath": str(lod.get("objectPath", "")),
		}
	var keys: Array = chosen.keys()
	keys.sort()
	var result: Array[Dictionary] = []
	for raw_key: Variant in keys:
		result.append(chosen[raw_key] as Dictionary)
	return result


static func _first_emitter_module(emitter: Dictionary, export_type: String) -> Dictionary:
	var raw_modules: Variant = emitter.get("modules", [])
	if not (raw_modules is Array):
		return {}
	for raw: Variant in raw_modules:
		if not (raw is Dictionary):
			continue
		var module := raw as Dictionary
		if str(module.get("exportType", "")) != export_type:
			continue
		if not bool(ParticleSource.properties(module).get("bEnabled", true)):
			continue
		return module
	return {}


static func _distribution_table(value: Variant) -> Dictionary:
	var distribution := ParticleSource.distribution(value)
	var raw: Variant = distribution.get("Table", {})
	return raw as Dictionary if raw is Dictionary else {}


static func _float_table_series(value: Variant) -> Array[float]:
	var result: Array[float] = []
	var table := _distribution_table(value)
	var entry_count := int(table.get("EntryCount", 0))
	var entry_stride := int(table.get("EntryStride", 0))
	var raw_values: Variant = table.get("Values", [])
	if entry_count <= 0 or entry_stride <= 0 or not (raw_values is Array):
		return result
	var values := raw_values as Array
	if values.size() < entry_count * entry_stride:
		return result
	for entry_index in range(entry_count):
		var raw: Variant = values[entry_index * entry_stride]
		if raw is float or raw is int:
			result.append(float(raw))
	return result


static func _vector_table_series(value: Variant) -> Array[Vector3]:
	var result: Array[Vector3] = []
	var table := _distribution_table(value)
	var entry_count := int(table.get("EntryCount", 0))
	var entry_stride := int(table.get("EntryStride", 0))
	var raw_values: Variant = table.get("Values", [])
	if entry_count <= 0 or entry_stride < 3 or not (raw_values is Array):
		return result
	var values := raw_values as Array
	if values.size() < entry_count * entry_stride:
		return result
	for entry_index in range(entry_count):
		var at := entry_index * entry_stride
		result.append(Vector3(
			float(values[at]),
			float(values[at + 1]),
			float(values[at + 2])
		))
	return result


static func _sample_float_series(values: Array[float], t: float, default_value: float) -> float:
	if values.is_empty():
		return default_value
	if values.size() == 1:
		return values[0]
	var scaled := clampf(t, 0.0, 1.0) * float(values.size() - 1)
	var lo := int(floor(scaled))
	var hi := mini(values.size() - 1, lo + 1)
	return lerpf(values[lo], values[hi], scaled - float(lo))


static func _sample_vector_series(
	values: Array[Vector3],
	t: float,
	default_value: Vector3
) -> Vector3:
	if values.is_empty():
		return default_value
	if values.size() == 1:
		return values[0]
	var scaled := clampf(t, 0.0, 1.0) * float(values.size() - 1)
	var lo := int(floor(scaled))
	var hi := mini(values.size() - 1, lo + 1)
	return values[lo].lerp(values[hi], scaled - float(lo))


static func _curve_from_samples(samples: Array[float]) -> Curve:
	if samples.is_empty():
		return null
	var curve := Curve.new()
	var lo := INF
	var hi := -INF
	for value: float in samples:
		lo = minf(lo, value)
		hi = maxf(hi, value)
	curve.min_value = minf(0.0, lo)
	curve.max_value = maxf(1.0, hi)
	if samples.size() == 1:
		curve.add_point(Vector2(0.0, samples[0]))
		curve.add_point(Vector2(1.0, samples[0]))
		return curve
	for index in range(samples.size()):
		curve.add_point(Vector2(
			float(index) / float(samples.size() - 1),
			samples[index]
		))
	return curve


static func _size_over_life_texture(emitter: Dictionary) -> CurveXYZTexture:
	var module := _first_emitter_module(emitter, "ParticleModuleSizeMultiplyLife")
	if module.is_empty():
		return null
	var samples := _vector_table_series(
		ParticleSource.properties(module).get("LifeMultiplier")
	)
	if samples.is_empty():
		return null
	var xs: Array[float] = []
	var ys: Array[float] = []
	var zs: Array[float] = []
	for sample: Vector3 in samples:
		xs.append(sample.x)
		ys.append(sample.y)
		zs.append(sample.z)
	var texture := CurveXYZTexture.new()
	texture.width = maxi(256, samples.size())
	texture.curve_x = _curve_from_samples(xs)
	texture.curve_y = _curve_from_samples(ys)
	texture.curve_z = _curve_from_samples(zs)
	return texture


static func _color_over_life_texture(emitter: Dictionary) -> GradientTexture1D:
	var color_module := _first_emitter_module(emitter, "ParticleModuleColorOverLife")
	var scale_module := _first_emitter_module(
		emitter,
		"ParticleModuleColorScaleOverLife"
	)
	if color_module.is_empty() and scale_module.is_empty():
		return null

	var rgb: Array[Vector3] = []
	var alpha: Array[float] = []
	if not color_module.is_empty():
		var color_props := ParticleSource.properties(color_module)
		rgb = _vector_table_series(color_props.get("ColorOverLife"))
		alpha = _float_table_series(color_props.get("AlphaOverLife"))

	var rgb_scale: Array[Vector3] = []
	var alpha_scale: Array[float] = []
	if not scale_module.is_empty():
		var scale_props := ParticleSource.properties(scale_module)
		rgb_scale = _vector_table_series(scale_props.get("ColorScaleOverLife"))
		alpha_scale = _float_table_series(scale_props.get("AlphaScaleOverLife"))

	if (
		rgb.is_empty()
		and alpha.is_empty()
		and rgb_scale.is_empty()
		and alpha_scale.is_empty()
	):
		return null

	var sample_count := maxi(
		2,
		maxi(
			maxi(rgb.size(), alpha.size()),
			maxi(rgb_scale.size(), alpha_scale.size())
		)
	)
	var offsets := PackedFloat32Array()
	var colors := PackedColorArray()
	offsets.resize(sample_count)
	colors.resize(sample_count)
	for index in range(sample_count):
		var t := float(index) / float(sample_count - 1)
		var c := _sample_vector_series(rgb, t, Vector3.ONE)
		var a := _sample_float_series(alpha, t, 1.0)
		var c_scale := _sample_vector_series(rgb_scale, t, Vector3.ONE)
		var a_scale := _sample_float_series(alpha_scale, t, 1.0)
		offsets[index] = t
		colors[index] = Color(
			c.x * c_scale.x,
			c.y * c_scale.y,
			c.z * c_scale.z,
			a * a_scale
		)
	var gradient := Gradient.new()
	gradient.offsets = offsets
	gradient.colors = colors
	gradient.interpolation_mode = Gradient.GRADIENT_INTERPOLATE_LINEAR
	var texture := GradientTexture1D.new()
	texture.width = maxi(256, sample_count)
	texture.use_hdr = true
	texture.gradient = gradient
	return texture


static func _apply_constant_start_color(
	process: ParticleProcessMaterial,
	emitter: Dictionary
) -> void:
	var module := _first_emitter_module(emitter, "ParticleModuleColor")
	if module.is_empty():
		return
	var props := ParticleSource.properties(module)
	var color_bounds := _distribution_vector_bounds(props.get("StartColor"))
	var alpha_distribution := ParticleSource.distribution(props.get("StartAlpha"))
	if not bool(color_bounds.get("ready", false)):
		return
	var lo := color_bounds.get("min", Vector3.ONE) as Vector3
	var hi := color_bounds.get("max", Vector3.ONE) as Vector3
	var alpha_min := float(alpha_distribution.get("MinValue", 1.0))
	var alpha_max := float(alpha_distribution.get("MaxValue", alpha_min))
	# Only map the exact constant case. UE can randomize RGB channels
	# independently; a one-dimensional Godot ramp would correlate them.
	if not lo.is_equal_approx(hi) or not is_equal_approx(alpha_min, alpha_max):
		return
	process.color = Color(lo.x, lo.y, lo.z, alpha_min)


static func _apply_emitter_life_curves(
	process: ParticleProcessMaterial,
	emitter: Dictionary
) -> void:
	_apply_constant_start_color(process, emitter)
	var size_curve := _size_over_life_texture(emitter)
	if size_curve != null:
		process.scale_curve = size_curve
	var color_curve := _color_over_life_texture(emitter)
	if color_curve != null:
		process.color_ramp = color_curve


static func _distribution_vector_bounds(value: Variant) -> Dictionary:
	var distribution := ParticleSource.distribution(value)
	var min_value := ParticleSource.vector3(
		distribution.get("MinValueVec"),
		Vector3.INF
	)
	var max_value := ParticleSource.vector3(
		distribution.get("MaxValueVec"),
		Vector3.INF
	)
	var samples := _vector_table_series(value)
	if min_value.is_equal_approx(Vector3.INF):
		if not samples.is_empty():
			min_value = samples[0]
			for sample: Vector3 in samples:
				min_value.x = minf(min_value.x, sample.x)
				min_value.y = minf(min_value.y, sample.y)
				min_value.z = minf(min_value.z, sample.z)
	if max_value.is_equal_approx(Vector3.INF):
		if not samples.is_empty():
			max_value = samples[0]
			for sample: Vector3 in samples:
				max_value.x = maxf(max_value.x, sample.x)
				max_value.y = maxf(max_value.y, sample.y)
				max_value.z = maxf(max_value.z, sample.z)
	return {
		"ready": (
			not min_value.is_equal_approx(Vector3.INF)
			and not max_value.is_equal_approx(Vector3.INF)
		),
		"min": min_value,
		"max": max_value,
	}


static func _distribution_float_max(value: Variant, default_value: float = 0.0) -> float:
	var samples := _float_table_series(value)
	if not samples.is_empty():
		var result := samples[0]
		for sample: float in samples:
			result = maxf(result, sample)
		return result
	var distribution := ParticleSource.distribution(value)
	if distribution.has("MaxValue"):
		return float(distribution.get("MaxValue", default_value))
	if distribution.has("MinValue"):
		return float(distribution.get("MinValue", default_value))
	return default_value


static func _apply_emitter_spawn_shape(
	process: ParticleProcessMaterial,
	emitter: Dictionary
) -> void:
	var raw_modules: Variant = emitter.get("modules", [])
	if not (raw_modules is Array):
		return
	var enabled_locations: Array[Dictionary] = []
	for raw: Variant in raw_modules:
		if not (raw is Dictionary):
			continue
		var module := raw as Dictionary
		var export_type := str(module.get("exportType", ""))
		if export_type not in [
			"ParticleModuleLocation",
			"ParticleModuleLocation_Seeded",
			"ParticleModuleLocationPrimitiveCylinder",
			"ParticleModuleLocationPrimitiveSphere",
		]:
			continue
		if not bool(ParticleSource.properties(module).get("bEnabled", true)):
			continue
		enabled_locations.append(module)

	var primitive := {}
	var simple_locations: Array[Dictionary] = []
	for module: Dictionary in enabled_locations:
		var export_type := str(module.get("exportType", ""))
		if export_type in [
			"ParticleModuleLocationPrimitiveCylinder",
			"ParticleModuleLocationPrimitiveSphere",
		]:
			if primitive.is_empty():
				primitive = module
			else:
				# Multiple source primitives need custom shader semantics; do not
				# merge them into an invented Godot shape.
				return
		else:
			simple_locations.append(module)

	var simple_center := Vector3.ZERO
	var simple_extents := Vector3.ZERO
	var simple_uniform := false
	if simple_locations.size() == 1:
		var simple_props := ParticleSource.properties(simple_locations[0])
		var bounds := _distribution_vector_bounds(simple_props.get("StartLocation"))
		if bool(bounds.get("ready", false)):
			var lo := bounds.get("min", Vector3.ZERO) as Vector3
			var hi := bounds.get("max", Vector3.ZERO) as Vector3
			simple_center = (lo + hi) * 0.5 * 0.01
			simple_extents = (hi - lo).abs() * 0.5 * 0.01
			simple_uniform = not lo.is_equal_approx(hi)
	elif simple_locations.size() > 1:
		# Additive/random multiple location modules cannot be represented by one
		# built-in emission shape without changing source semantics.
		return

	if primitive.is_empty():
		if simple_locations.is_empty():
			return
		if simple_uniform:
			process.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
			process.emission_box_extents = simple_extents
			process.emission_shape_offset = simple_center
		else:
			process.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_POINT
			process.emission_shape_offset = simple_center
		return

	var primitive_props := ParticleSource.properties(primitive)
	var primitive_type := str(primitive.get("exportType", ""))
	var primitive_bounds := _distribution_vector_bounds(
		primitive_props.get("StartLocation")
	)
	var primitive_center := Vector3.ZERO
	if bool(primitive_bounds.get("ready", false)):
		var primitive_lo := primitive_bounds.get("min", Vector3.ZERO) as Vector3
		var primitive_hi := primitive_bounds.get("max", Vector3.ZERO) as Vector3
		if not primitive_lo.is_equal_approx(primitive_hi):
			# Primitive source center itself is random. Built-in Godot shapes
			# cannot preserve that extra distribution exactly.
			return
		primitive_center = primitive_lo * 0.01

	if simple_uniform:
		# UE applies the simple random location in addition to the primitive.
		# Keep this unsupported until the custom particle shader can compose
		# both distributions exactly.
		return
	var center := primitive_center + simple_center

	if primitive_type == "ParticleModuleLocationPrimitiveSphere":
		var radius := _distribution_float_max(
			primitive_props.get("StartRadius"),
			0.0
		) * 0.01
		if radius <= 0.0:
			return
		process.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
		process.emission_sphere_radius = radius
		process.emission_shape_offset = center
		return

	if primitive_type == "ParticleModuleLocationPrimitiveCylinder":
		var radius := _distribution_float_max(
			primitive_props.get("StartRadius"),
			0.0
		) * 0.01
		var height := _distribution_float_max(
			primitive_props.get("StartHeight"),
			0.0
		) * 0.01
		if radius <= 0.0:
			return
		if bool(primitive_props.get("SurfaceOnly", false)):
			# Godot's ring emitter is a volume/annulus primitive. Do not turn
			# UE Cascade's surface-only cylindrical shell into a filled volume.
			# Keep the source dependency explicit until the custom particle
			# shader can sample the cylinder surface exactly.
			process.set_meta(
				"cascade_unresolved_spawn_shape",
				"surface_only_cylinder"
			)
			process.set_meta("cascade_source_cylinder_radius_m", radius)
			process.set_meta("cascade_source_cylinder_height_m", height)
			return
		process.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_RING
		process.emission_ring_axis = Vector3(0.0, 0.0, 1.0)
		process.emission_ring_radius = radius
		process.emission_ring_inner_radius = 0.0
		process.emission_ring_height = height
		process.emission_ring_cone_angle = 90.0
		process.emission_shape_offset = center


static func _emitter_lifetime(system: Dictionary, emitter: Dictionary) -> Vector2:
	var module := _first_emitter_module(emitter, "ParticleModuleLifetime")
	if module.is_empty():
		return Vector2(1.0, 1.0)
	var samples := _float_samples(system, ParticleSource.properties(module).get("Lifetime"))
	if samples.is_empty():
		return Vector2(1.0, 1.0)
	var lo := INF
	var hi := 0.0
	for sample: float in samples:
		lo = minf(lo, sample)
		hi = maxf(hi, sample)
	lo = maxf(0.001, lo)
	return Vector2(lo, maxf(lo, hi))


static func _emitter_size_samples(system: Dictionary, emitter: Dictionary) -> Array[Vector3]:
	var module := _first_emitter_module(emitter, "ParticleModuleSize")
	if module.is_empty():
		return []
	return _vector_samples(system, ParticleSource.properties(module).get("StartSize"))


static func _emitter_size_bounds(
	system: Dictionary,
	emitter: Dictionary
) -> Dictionary:
	var samples := _emitter_size_samples(system, emitter)
	if samples.is_empty():
		return {"ready": false}
	var lo := samples[0]
	var hi := samples[0]
	for sample: Vector3 in samples:
		lo.x = minf(lo.x, sample.x)
		lo.y = minf(lo.y, sample.y)
		lo.z = minf(lo.z, sample.z)
		hi.x = maxf(hi.x, sample.x)
		hi.y = maxf(hi.y, sample.y)
		hi.z = maxf(hi.z, sample.z)
	return {"ready": true, "min": lo, "max": hi}


static func _speed_scale_curve(
	speed_scale: float,
	max_scale: float,
	max_speed_mps: float
) -> Curve:
	var curve := Curve.new()
	curve.min_value = 0.0
	curve.max_value = maxf(1.0, max_scale)
	if max_speed_mps <= 0.0 or speed_scale <= 0.0:
		curve.add_point(Vector2(0.0, 1.0))
		curve.add_point(Vector2(1.0, 1.0))
		return curve
	var clamp_speed_mps := max_scale / (speed_scale * 100.0)
	var clamp_t := clampf(clamp_speed_mps / max_speed_mps, 0.0, 1.0)
	curve.add_point(Vector2(0.0, 0.0))
	if clamp_t > 0.0 and clamp_t < 1.0:
		curve.add_point(Vector2(clamp_t, max_scale))
	curve.add_point(Vector2(
		1.0,
		minf(max_scale, max_speed_mps * speed_scale * 100.0)
	))
	return curve


static func _apply_size_scale_by_speed(
	process: ParticleProcessMaterial,
	emitter: Dictionary
) -> void:
	var modules := _enabled_emitter_modules(
		emitter,
		["ParticleModuleSizeScaleBySpeed"]
	)
	if modules.size() != 1:
		return
	var props := ParticleSource.properties(modules[0])
	var speed_scale := ParticleSource.vector2(
		props.get("SpeedScale"),
		Vector2.INF
	)
	var max_scale := ParticleSource.vector2(
		props.get("MaxScale"),
		Vector2.INF
	)
	if (
		speed_scale.is_equal_approx(Vector2.INF)
		or max_scale.is_equal_approx(Vector2.INF)
	):
		return
	var max_speed_mps := 0.0
	for value: float in [
		(max_scale.x / (speed_scale.x * 100.0)) if speed_scale.x > 0.0 else 0.0,
		(max_scale.y / (speed_scale.y * 100.0)) if speed_scale.y > 0.0 else 0.0,
	]:
		max_speed_mps = maxf(max_speed_mps, value)
	if max_speed_mps <= 0.0:
		return
	var texture := CurveXYZTexture.new()
	texture.width = 256
	texture.curve_x = _speed_scale_curve(speed_scale.x, max_scale.x, max_speed_mps)
	texture.curve_y = _speed_scale_curve(speed_scale.y, max_scale.y, max_speed_mps)
	var z_curve := Curve.new()
	z_curve.add_point(Vector2(0.0, 1.0))
	z_curve.add_point(Vector2(1.0, 1.0))
	texture.curve_z = z_curve
	process.scale_over_velocity_min = 0.0
	process.scale_over_velocity_max = max_speed_mps
	process.scale_over_velocity_curve = texture


static func _object_has_property(object: Object, property_name: String) -> bool:
	for property_raw: Variant in object.get_property_list():
		if not (property_raw is Dictionary):
			continue
		if str((property_raw as Dictionary).get("name", "")) == property_name:
			return true
	return false


static func _scale_vector_to_46_scalar(value: Vector3, sprite: bool) -> float:
	if sprite:
		return maxf(0.0001, (absf(value.x) + absf(value.y)) * 0.5)
	return maxf(
		0.0001,
		(absf(value.x) + absf(value.y) + absf(value.z)) / 3.0
	)


static func _apply_emitter_start_scale(
	process: ParticleProcessMaterial,
	system: Dictionary,
	emitter: Dictionary,
	sprite: bool
) -> bool:
	var bounds := _emitter_size_bounds(system, emitter)
	if not bool(bounds.get("ready", false)):
		return false
	var lo := bounds.get("min", Vector3.ONE) as Vector3
	var hi := bounds.get("max", Vector3.ONE) as Vector3
	if sprite:
		# A 1 cm source quad lets Cascade StartSize map directly to particle
		# scale. Godot 4.7+ exposes vector start-scale. Xogot currently targets
		# Godot 4.6.1, whose ParticleProcessMaterial only has scalar scale_min /
		# scale_max, so use the exact scalar path for symmetric Cascade sprites
		# and retain the source vectors as metadata for the custom shader bridge.
		lo.z = 1.0 if is_zero_approx(lo.z) else lo.z
		hi.z = 1.0 if is_zero_approx(hi.z) else hi.z

	process.set_meta("source_start_scale_min", lo)
	process.set_meta("source_start_scale_max", hi)

	if _object_has_property(process, "use_scale_3d"):
		process.set("use_scale_3d", true)
		process.set("scale_3d_min", lo)
		process.set("scale_3d_max", hi)
		process.set_meta("source_start_scale_bridge", "native_vector")
		return true

	var scalar_lo := _scale_vector_to_46_scalar(lo, sprite)
	var scalar_hi := _scale_vector_to_46_scalar(hi, sprite)
	process.scale_min = minf(scalar_lo, scalar_hi)
	process.scale_max = maxf(scalar_lo, scalar_hi)
	process.set_meta("source_start_scale_bridge", "godot46_scalar")
	process.set_meta(
		"source_start_scale_vector_exact",
		is_equal_approx(lo.x, lo.y)
		and is_equal_approx(hi.x, hi.y)
		if sprite
		else (
			is_equal_approx(lo.x, lo.y)
			and is_equal_approx(lo.y, lo.z)
			and is_equal_approx(hi.x, hi.y)
			and is_equal_approx(hi.y, hi.z)
		)
	)
	return true


static func _emitter_velocity_samples(system: Dictionary, emitter: Dictionary) -> Array[Vector3]:
	var module := _first_emitter_module(emitter, "ParticleModuleVelocity")
	if module.is_empty():
		return []
	return _vector_samples(system, ParticleSource.properties(module).get("StartVelocity"))


static func _emitter_acceleration_samples(system: Dictionary, emitter: Dictionary) -> Array[Vector3]:
	var result: Array[Vector3] = []
	var module := _first_emitter_module(emitter, "ParticleModuleAcceleration")
	if not module.is_empty():
		var props := ParticleSource.properties(module)
		for sample: Vector3 in _vector_samples(system, props.get("Acceleration")):
			if bool(props.get("bAlwaysInWorldSpace", false)):
				result.append(_ue_vector_to_xziel(sample))
			else:
				result.append(sample)
	var constant := _first_emitter_module(emitter, "ParticleModuleAccelerationConstant")
	if not constant.is_empty():
		var constant_props := ParticleSource.properties(constant)
		var sample := ParticleSource.vector3(
			constant_props.get("Acceleration"),
			Vector3.INF
		)
		if not sample.is_equal_approx(Vector3.INF):
			if bool(constant_props.get("bAlwaysInWorldSpace", false)):
				sample = _ue_vector_to_xziel(sample)
			result.append(sample)

	var type_raw: Variant = emitter.get("typeData", {})
	if (
		type_raw is Dictionary
		and str((type_raw as Dictionary).get("exportType", ""))
			== "ParticleModuleTypeDataGpu"
	):
		var type_props := ParticleSource.properties(type_raw as Dictionary)
		var info_raw: Variant = type_props.get("EmitterInfo", {})
		if info_raw is Dictionary:
			var gpu_accel := ParticleSource.vector3(
				(info_raw as Dictionary).get("ConstantAcceleration"),
				Vector3.INF
			)
			if not gpu_accel.is_equal_approx(Vector3.INF):
				# GPU emitter acceleration is authored in UE simulation axes.
				# World-space GPU emitters need the Nacht UE->Godot basis;
				# local-space emitters inherit it from the parent transform.
				if not _emitter_local_space(emitter):
					gpu_accel = _ue_vector_to_xziel(gpu_accel)
				result.append(gpu_accel)
	return result


static func _emitter_spawn_rate(system: Dictionary, emitter: Dictionary) -> float:
	var spawn_raw: Variant = emitter.get("spawn", {})
	if not (spawn_raw is Dictionary):
		return 0.0
	var samples := _float_samples(
		system,
		ParticleSource.properties(spawn_raw as Dictionary).get("Rate")
	)
	var result := 0.0
	for sample: float in samples:
		result = maxf(result, sample)
	return maxf(0.0, result)


static func _emitter_burst_count(emitter: Dictionary) -> int:
	var spawn_raw: Variant = emitter.get("spawn", {})
	if not (spawn_raw is Dictionary):
		return 0
	var raw: Variant = ParticleSource.properties(spawn_raw as Dictionary).get("BurstList", [])
	if not (raw is Array):
		return 0
	var result := 0
	for burst_raw: Variant in raw:
		if burst_raw is Dictionary:
			result += maxi(0, int((burst_raw as Dictionary).get("Count", 0)))
	return result


static func _enabled_emitter_modules(
	emitter: Dictionary,
	export_types: Array[String]
) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	var raw_modules: Variant = emitter.get("modules", [])
	if not (raw_modules is Array):
		return result
	for raw: Variant in raw_modules:
		if not (raw is Dictionary):
			continue
		var module := raw as Dictionary
		if str(module.get("exportType", "")) not in export_types:
			continue
		if not bool(ParticleSource.properties(module).get("bEnabled", true)):
			continue
		result.append(module)
	return result


static func _float_sample_range(
	system: Dictionary,
	value: Variant
) -> Vector2:
	var samples := _float_samples(system, value)
	if samples.is_empty():
		return Vector2.ZERO
	var lo := INF
	var hi := -INF
	for sample: float in samples:
		lo = minf(lo, sample)
		hi = maxf(hi, sample)
	return Vector2(lo, hi)


static func _vector_component_bounds(samples: Array[Vector3]) -> Dictionary:
	if samples.is_empty():
		return {"ready": false}
	var lo := samples[0]
	var hi := samples[0]
	for sample: Vector3 in samples:
		lo.x = minf(lo.x, sample.x)
		lo.y = minf(lo.y, sample.y)
		lo.z = minf(lo.z, sample.z)
		hi.x = maxf(hi.x, sample.x)
		hi.y = maxf(hi.y, sample.y)
		hi.z = maxf(hi.z, sample.z)
	return {"ready": true, "min": lo, "max": hi}


static func _apply_mesh_rotation(
	process: ParticleProcessMaterial,
	system: Dictionary,
	emitter: Dictionary
) -> void:
	var rotation := _first_emitter_module(emitter, "ParticleModuleMeshRotation")
	if not rotation.is_empty():
		var rotation_samples := _vector_samples(
			system,
			ParticleSource.properties(rotation).get("StartRotation")
		)
		var bounds := _vector_component_bounds(rotation_samples)
		if bool(bounds.get("ready", false)):
			var lo := bounds.get("min", Vector3.ZERO) as Vector3
			var hi := bounds.get("max", Vector3.ZERO) as Vector3
			process.set_meta("source_mesh_rotation_min_turns", lo)
			process.set_meta("source_mesh_rotation_max_turns", hi)
			if _object_has_property(process, "use_rotation_3d"):
				process.set("use_rotation_3d", true)
				process.set("rotation_3d_min", lo * 360.0)
				process.set("rotation_3d_max", hi * 360.0)
				process.set_meta("source_mesh_rotation_bridge", "native_vector")
			else:
				# Godot 4.6 has no per-particle 3D orientation range. Preserve
				# UE yaw (source Z-up -> Godot Y-up) through the scalar angle
				# channel and keep all source axes in metadata for the custom
				# process-shader parity pass.
				process.particle_flag_rotate_y = true
				process.angle_min = lo.z * 360.0
				process.angle_max = hi.z * 360.0
				process.set_meta("source_mesh_rotation_bridge", "godot46_yaw")

	var rate := _first_emitter_module(emitter, "ParticleModuleMeshRotationRate")
	if not rate.is_empty():
		var rate_samples := _vector_samples(
			system,
			ParticleSource.properties(rate).get("StartRotationRate")
		)
		var rate_bounds := _vector_component_bounds(rate_samples)
		if bool(rate_bounds.get("ready", false)):
			var rate_lo := rate_bounds.get("min", Vector3.ZERO) as Vector3
			var rate_hi := rate_bounds.get("max", Vector3.ZERO) as Vector3
			process.set_meta("source_mesh_rotation_rate_min_turns", rate_lo)
			process.set_meta("source_mesh_rotation_rate_max_turns", rate_hi)
			if _object_has_property(process, "use_rotation_velocity_3d"):
				process.set("use_rotation_velocity_3d", true)
				process.set("rotation_velocity_3d_min", rate_lo * 360.0)
				process.set("rotation_velocity_3d_max", rate_hi * 360.0)
				process.set_meta("source_mesh_rotation_rate_bridge", "native_vector")
			else:
				process.particle_flag_rotate_y = true
				process.angular_velocity_min = rate_lo.z * 360.0
				process.angular_velocity_max = rate_hi.z * 360.0
				process.set_meta("source_mesh_rotation_rate_bridge", "godot46_yaw")


static func _apply_emitter_rotation(
	process: ParticleProcessMaterial,
	system: Dictionary,
	emitter: Dictionary
) -> void:
	var rotation_modules := _enabled_emitter_modules(
		emitter,
		["ParticleModuleRotation", "ParticleModuleRotation_Seeded"]
	)
	# Multiple enabled rotation modules are additive in Cascade. Leave those for
	# the custom particle shader instead of collapsing them into one range.
	if rotation_modules.size() == 1:
		var rotation_props := ParticleSource.properties(rotation_modules[0])
		var rotation_range := _float_sample_range(
			system,
			rotation_props.get("StartRotation")
		)
		# Cascade particle rotations are authored in turns; Godot expects
		# degrees for billboard angle.
		process.angle_min = rotation_range.x * 360.0
		process.angle_max = rotation_range.y * 360.0

	var rate_modules := _enabled_emitter_modules(
		emitter,
		["ParticleModuleRotationRate"]
	)
	if rate_modules.size() == 1:
		var rate_props := ParticleSource.properties(rate_modules[0])
		var rate_range := _float_sample_range(
			system,
			rate_props.get("StartRotationRate")
		)
		process.angular_velocity_min = rate_range.x * 360.0
		process.angular_velocity_max = rate_range.y * 360.0


static func _configure_process_from_emitter(
	process: ParticleProcessMaterial,
	system: Dictionary,
	emitter: Dictionary
) -> void:
	_apply_emitter_spawn_shape(process, emitter)
	_apply_emitter_rotation(process, system, emitter)
	var velocities := _emitter_velocity_samples(system, emitter)
	var velocity_lengths := _min_max_length(velocities)
	var velocity_mean := _mean_vector(velocities)
	if velocity_lengths.y > 0.0:
		process.initial_velocity_min = velocity_lengths.x * 0.01
		process.initial_velocity_max = velocity_lengths.y * 0.01
		if velocity_mean.length_squared() > 0.000001:
			process.direction = velocity_mean.normalized()
			process.spread = 45.0
		else:
			process.spread = 180.0
	var accelerations := _emitter_acceleration_samples(system, emitter)
	process.gravity = _mean_vector(accelerations) * 0.01


static func _emitter_material_path(emitter: Dictionary) -> String:
	var required_raw: Variant = emitter.get("required", {})
	if not (required_raw is Dictionary):
		return ""
	return str(ParticleSource.properties(required_raw as Dictionary).get("Material", ""))


static func _emitter_subuv_grid(emitter: Dictionary) -> Vector2i:
	var required_raw: Variant = emitter.get("required", {})
	if not (required_raw is Dictionary):
		return Vector2i.ONE
	var props := ParticleSource.properties(required_raw as Dictionary)
	return Vector2i(
		maxi(1, int(props.get("SubImages_Horizontal", 1))),
		maxi(1, int(props.get("SubImages_Vertical", 1)))
	)


static func _emitter_subuv_frame_rate(system: Dictionary, emitter: Dictionary) -> float:
	var movie := _first_emitter_module(emitter, "ParticleModuleSubUVMovie")
	if movie.is_empty():
		return 0.0
	var result := 0.0
	for sample: float in _float_samples(system, ParticleSource.properties(movie).get("FrameRate")):
		result = maxf(result, sample)
	return result


static func _emitter_subuv_offset_curve(
	system: Dictionary,
	emitter: Dictionary,
	frame_count: int
) -> CurveTexture:
	if frame_count <= 1:
		return null
	var required_raw: Variant = emitter.get("required", {})
	if not (required_raw is Dictionary):
		return null
	var interpolation := str(
		ParticleSource.properties(required_raw as Dictionary).get(
			"InterpolationMethod",
			""
		)
	)
	if not interpolation.begins_with("PSUVIM_Linear"):
		return null
	var subuv := _first_emitter_module(emitter, "ParticleModuleSubUV")
	if subuv.is_empty():
		return null
	var values := _float_table_series(
		ParticleSource.properties(subuv).get("SubImageIndex")
	)
	if values.size() < 2:
		return null
	var normalized: Array[float] = []
	var denominator := float(frame_count - 1)
	for value: float in values:
		normalized.append(clampf(value / denominator, 0.0, 1.0))
	var curve := _curve_from_samples(normalized)
	if curve == null:
		return null
	var texture := CurveTexture.new()
	texture.width = maxi(256, normalized.size())
	texture.curve = curve
	return texture


static func _emitter_local_space(emitter: Dictionary) -> bool:
	var required_raw: Variant = emitter.get("required", {})
	if not (required_raw is Dictionary):
		return false
	return bool(ParticleSource.properties(required_raw as Dictionary).get("bUseLocalSpace", false))


static func _emitter_delay_seconds(emitter: Dictionary) -> float:
	var required_raw: Variant = emitter.get("required", {})
	if not (required_raw is Dictionary):
		return 0.0
	return maxf(
		0.0,
		float(
			ParticleSource.properties(required_raw as Dictionary).get(
				"EmitterDelay",
				0.0
			)
		)
	)


static func _emitter_duration_seconds(emitter: Dictionary) -> float:
	var required_raw: Variant = emitter.get("required", {})
	if not (required_raw is Dictionary):
		return 0.0
	return maxf(
		0.0,
		float(
			ParticleSource.properties(required_raw as Dictionary).get(
				"EmitterDuration",
				0.0
			)
		)
	)


static func _apply_emitter_activation(
	anchor: Node3D,
	particles: GPUParticles3D,
	emitter: Dictionary,
	auto_activate: bool,
	index: int
) -> void:
	var delay := _emitter_delay_seconds(emitter)
	particles.set_meta("source_emitter_delay_seconds", delay)
	particles.set_meta(
		"source_emitter_duration_seconds",
		_emitter_duration_seconds(emitter)
	)
	if not auto_activate:
		particles.emitting = false
		return
	if delay <= 0.0:
		particles.emitting = true
		return
	particles.emitting = false
	var timer := Timer.new()
	timer.name = "CascadeEmitterDelay_%02d" % index
	timer.wait_time = delay
	timer.one_shot = true
	timer.autostart = true
	anchor.add_child(timer)
	timer.timeout.connect(
		func() -> void:
			if is_instance_valid(particles):
				particles.restart()
				particles.emitting = true
			if is_instance_valid(timer):
				timer.queue_free()
	)


static func _apply_sprite_axis_lock(
	material: StandardMaterial3D,
	emitter: Dictionary
) -> void:
	var modules := _enabled_emitter_modules(
		emitter,
		["ParticleModuleOrientationAxisLock"]
	)
	if modules.size() != 1:
		return
	var flag := str(ParticleSource.properties(modules[0]).get("LockAxisFlags", ""))
	if flag == "EPAL_Z":
		# QuadMesh defaults to FACE_Z in emitter-local space. The parent Nacht
		# source basis maps that UE +Z facing to Godot world +Y exactly.
		material.billboard_mode = BaseMaterial3D.BILLBOARD_DISABLED
	elif flag == "EPAL_ROTATE_Z":
		# UE Z-up is Godot Y-up after the Nacht source-root basis conversion.
		material.billboard_mode = BaseMaterial3D.BILLBOARD_FIXED_Y


static func _apply_sprite_pivot(
	quad: QuadMesh,
	emitter: Dictionary
) -> void:
	var modules := _enabled_emitter_modules(
		emitter,
		["ParticleModulePivotOffset"]
	)
	if modules.size() != 1:
		return
	var pivot := ParticleSource.vector2(
		ParticleSource.properties(modules[0]).get("PivotOffset"),
		Vector2.INF
	)
	if pivot.is_equal_approx(Vector2.INF):
		return
	# UE Cascade applies PivotOffset in UV-sized sprite space. The documented
	# default (0.5, 0.5) is the centered pivot, while QuadMesh center_offset=0
	# is centered. The mesh is one UE centimeter before particle StartSize
	# scaling, so this offset stays source-literal after scale_3d.
	quad.center_offset = Vector3(
		(pivot.x - 0.5) * 0.01,
		(pivot.y - 0.5) * 0.01,
		0.0
	)


static func _apply_sprite_screen_alignment(
	material: StandardMaterial3D,
	process: ParticleProcessMaterial,
	emitter: Dictionary
) -> void:
	var required_raw: Variant = emitter.get("required", {})
	if not (required_raw is Dictionary):
		return
	var alignment := str(
		ParticleSource.properties(required_raw as Dictionary).get(
			"ScreenAlignment",
			""
		)
	)
	if alignment == "PSA_Velocity":
		# Particle billboard + Align Y matches UE velocity-facing sprite intent.
		material.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
		process.particle_flag_align_y = true


static func _build_source_sprite_emitter(
	anchor: Node3D,
	system: Dictionary,
	emitter: Dictionary,
	loader: Node,
	auto_activate: bool,
	index: int
) -> Dictionary:
	var material_path := _emitter_material_path(emitter)
	var material := _source_material(loader, material_path)
	if material == null:
		return {
			"mounted": false,
			"materialResolved": false,
			"meshResolved": true,
			"nodeCount": 0,
			"error": "sprite material unresolved",
		}
	_apply_sprite_axis_lock(material, emitter)

	var lifetime := _emitter_lifetime(system, emitter)
	var process := ParticleProcessMaterial.new()
	_configure_process_from_emitter(process, system, emitter)
	_apply_sprite_screen_alignment(material, process, emitter)
	_apply_emitter_start_scale(
		process,
		system,
		emitter,
		true
	)
	_apply_size_scale_by_speed(process, emitter)
	_apply_emitter_life_curves(process, emitter)

	var grid := _emitter_subuv_grid(emitter)
	material.particles_anim_h_frames = grid.x
	material.particles_anim_v_frames = grid.y
	material.particles_anim_loop = true
	if grid.x * grid.y > 1:
		var frame_count := grid.x * grid.y
		var offset_curve := _emitter_subuv_offset_curve(
			system,
			emitter,
			frame_count
		)
		if offset_curve != null:
			process.anim_speed_min = 0.0
			process.anim_speed_max = 0.0
			process.anim_offset_min = 1.0
			process.anim_offset_max = 1.0
			process.anim_offset_curve = offset_curve
			material.particles_anim_loop = false
		else:
			var source_fps := _emitter_subuv_frame_rate(system, emitter)
			var cycles := 1.0
			if source_fps > 0.0:
				cycles = source_fps * lifetime.y / float(frame_count)
			process.anim_speed_min = cycles
			process.anim_speed_max = cycles
			process.anim_offset_min = 0.0
			process.anim_offset_max = 1.0

	var quad := QuadMesh.new()
	# StartSize now lives in ParticleProcessMaterial scale_3d. Keep the mesh at
	# one UE centimeter so the source size vectors remain literal.
	quad.size = Vector2(0.01, 0.01)
	_apply_sprite_pivot(quad, emitter)
	quad.material = material

	var particles := GPUParticles3D.new()
	particles.name = "CascadeSpriteEmitter_%02d" % index
	particles.amount = clampi(int(emitter.get("peak", 1)), 1, 4096)
	particles.lifetime = lifetime.y
	particles.randomness = clampf(1.0 - (lifetime.x / lifetime.y), 0.0, 1.0)
	particles.local_coords = _emitter_local_space(emitter)
	particles.process_material = process
	particles.draw_pass_1 = quad
	particles.visibility_aabb = AABB(Vector3(-8.0, -8.0, -8.0), Vector3(16.0, 16.0, 16.0))
	particles.fixed_fps = 30
	_apply_emitter_activation(anchor, particles, emitter, auto_activate, index)
	var burst_count := _emitter_burst_count(emitter)
	var spawn_rate := _emitter_spawn_rate(system, emitter)
	var required_raw: Variant = emitter.get("required", {})
	if required_raw is Dictionary:
		var required_props := ParticleSource.properties(required_raw as Dictionary)
		if int(required_props.get("EmitterLoops", 0)) == 1:
			particles.one_shot = true
	if spawn_rate <= 0.0 and burst_count > 0:
		particles.one_shot = true
		particles.explosiveness = 1.0
	particles.add_to_group("nacht_source_particle_visual")
	particles.set_meta("source_particle_material_path", material_path)
	particles.set_meta("source_particle_emitter_path", str(emitter.get("key", "")))
	particles.set_meta("source_particle_lod_path", str(emitter.get("lodPath", "")))
	particles.set_meta("source_particle_lod_level", float(emitter.get("level", 0.0)))
	particles.set_meta("source_particle_renderer_mode", "sprite_lod0")
	anchor.add_child(particles)

	return {
		"mounted": true,
		"materialResolved": true,
		"meshResolved": true,
		"nodeCount": 1,
		"emitterPath": str(emitter.get("key", "")),
		"lodLevel": float(emitter.get("level", 0.0)),
		"peak": particles.amount,
		"spawnRate": spawn_rate,
		"burstCount": burst_count,
	}


static func _mesh_material_path(emitter: Dictionary) -> String:
	var module := _first_emitter_module(emitter, "ParticleModuleMeshMaterial")
	if module.is_empty():
		return _emitter_material_path(emitter)
	var raw: Variant = ParticleSource.properties(module).get("MeshMaterials", [])
	if raw is Array and not (raw as Array).is_empty():
		return str((raw as Array)[0])
	return _emitter_material_path(emitter)


static func _build_source_mesh_emitter(
	anchor: Node3D,
	system: Dictionary,
	emitter: Dictionary,
	loader: Node,
	auto_activate: bool,
	index: int
) -> Dictionary:
	var type_raw: Variant = emitter.get("typeData", {})
	if not (type_raw is Dictionary) or (type_raw as Dictionary).is_empty():
		return {
			"mounted": false,
			"materialResolved": false,
			"meshResolved": false,
			"nodeCount": 0,
			"error": "mesh type data missing",
		}
	var mesh_path := str(ParticleSource.properties(type_raw as Dictionary).get("Mesh", ""))
	if mesh_path.is_empty() or loader == null or not loader.has_method("resolve_particle_mesh_chunks"):
		return {
			"mounted": false,
			"materialResolved": false,
			"meshResolved": false,
			"nodeCount": 0,
			"error": "mesh resolver unavailable",
		}
	var chunks_raw: Variant = loader.call("resolve_particle_mesh_chunks", mesh_path)
	var chunks: Array[ArrayMesh] = []
	if chunks_raw is Array:
		for raw: Variant in chunks_raw:
			if raw is ArrayMesh:
				chunks.append(raw as ArrayMesh)
	if chunks.is_empty() or chunks.size() > 4:
		return {
			"mounted": false,
			"materialResolved": false,
			"meshResolved": false,
			"nodeCount": 0,
			"meshPath": mesh_path,
			"error": "mesh chunk count unsupported " + str(chunks.size()),
		}

	var material_path := _mesh_material_path(emitter)
	var material := _source_material(loader, material_path)
	if material == null:
		return {
			"mounted": false,
			"materialResolved": false,
			"meshResolved": true,
			"nodeCount": 0,
			"meshPath": mesh_path,
			"error": "mesh material unresolved",
		}
	material.billboard_mode = BaseMaterial3D.BILLBOARD_DISABLED

	for mesh: ArrayMesh in chunks:
		for surface_index in range(mesh.get_surface_count()):
			mesh.surface_set_material(surface_index, material)

	var lifetime := _emitter_lifetime(system, emitter)
	var process := ParticleProcessMaterial.new()
	_configure_process_from_emitter(process, system, emitter)
	_apply_mesh_rotation(process, system, emitter)
	_apply_emitter_start_scale(process, system, emitter, false)
	_apply_emitter_life_curves(process, emitter)

	var particles := GPUParticles3D.new()
	particles.name = "CascadeMeshEmitter_%02d" % index
	particles.amount = clampi(int(emitter.get("peak", 1)), 1, 4096)
	particles.lifetime = lifetime.y
	particles.randomness = clampf(1.0 - (lifetime.x / lifetime.y), 0.0, 1.0)
	particles.local_coords = _emitter_local_space(emitter)
	particles.process_material = process
	particles.draw_passes = chunks.size()
	for chunk_index in range(chunks.size()):
		particles.set("draw_pass_%d" % (chunk_index + 1), chunks[chunk_index])
	particles.visibility_aabb = AABB(Vector3(-8.0, -8.0, -8.0), Vector3(16.0, 16.0, 16.0))
	particles.fixed_fps = 30
	_apply_emitter_activation(anchor, particles, emitter, auto_activate, index)
	var burst_count := _emitter_burst_count(emitter)
	var spawn_rate := _emitter_spawn_rate(system, emitter)
	var required_raw: Variant = emitter.get("required", {})
	if required_raw is Dictionary:
		var required_props := ParticleSource.properties(required_raw as Dictionary)
		if int(required_props.get("EmitterLoops", 0)) == 1:
			particles.one_shot = true
	if spawn_rate <= 0.0 and burst_count > 0:
		particles.one_shot = true
		particles.explosiveness = 1.0
	particles.add_to_group("nacht_source_particle_visual")
	particles.set_meta("source_particle_material_path", material_path)
	particles.set_meta("source_particle_mesh_path", mesh_path)
	particles.set_meta("source_particle_emitter_path", str(emitter.get("key", "")))
	particles.set_meta("source_particle_lod_path", str(emitter.get("lodPath", "")))
	particles.set_meta("source_particle_lod_level", float(emitter.get("level", 0.0)))
	particles.set_meta("source_particle_renderer_mode", "mesh_lod0")
	anchor.add_child(particles)

	return {
		"mounted": true,
		"materialResolved": true,
		"meshResolved": true,
		"nodeCount": 1,
		"meshPath": mesh_path,
		"meshChunkCount": chunks.size(),
		"emitterPath": str(emitter.get("key", "")),
		"lodLevel": float(emitter.get("level", 0.0)),
		"peak": particles.amount,
		"spawnRate": spawn_rate,
		"burstCount": burst_count,
	}


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
		lifetime_min = INF
		lifetime_max = 0.0
		for sample: float in lifetimes:
			lifetime_min = minf(lifetime_min, sample)
			lifetime_max = maxf(lifetime_max, sample)
		lifetime_min = maxf(0.001, lifetime_min)
		lifetime_max = maxf(lifetime_min, lifetime_max)

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
	var spawn_rate := 0.0
	for sample: float in spawn_rates:
		spawn_rate = maxf(spawn_rate, sample)
	spawn_rate = maxf(0.0, spawn_rate)
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


static func _beam_hermite_point(
	start: Vector3,
	end: Vector3,
	start_tangent: Vector3,
	end_tangent: Vector3,
	t: float
) -> Vector3:
	var t2 := t * t
	var t3 := t2 * t
	var h00 := 2.0 * t3 - 3.0 * t2 + 1.0
	var h10 := t3 - 2.0 * t2 + t
	var h01 := -2.0 * t3 + 3.0 * t2
	var h11 := t3 - t2
	return (
		start * h00
		+ start_tangent * h10
		+ end * h01
		+ end_tangent * h11
	)


static func _beam_source_path_points(descriptor: Dictionary) -> PackedVector3Array:
	var result := PackedVector3Array()
	var target_raw: Variant = descriptor.get("targetUEcm", Vector3.ZERO)
	if not (target_raw is Vector3):
		return result
	var target := (target_raw as Vector3) * 0.01
	if target.length_squared() < 0.000001:
		return result

	var source_tangent_raw: Variant = descriptor.get("sourceTangent", Vector3.ZERO)
	var target_tangent_raw: Variant = descriptor.get("targetTangent", Vector3.ZERO)
	var source_tangent := (
		source_tangent_raw as Vector3
		if source_tangent_raw is Vector3
		else Vector3.ZERO
	)
	var target_tangent := (
		target_tangent_raw as Vector3
		if target_tangent_raw is Vector3
		else Vector3.ZERO
	)
	var source_strength := float(descriptor.get("sourceStrength", 0.0)) * 0.01
	var target_strength := float(descriptor.get("targetStrength", 0.0)) * 0.01
	if source_tangent.length_squared() > 0.000001:
		source_tangent = source_tangent.normalized() * source_strength
	if target_tangent.length_squared() > 0.000001:
		target_tangent = target_tangent.normalized() * target_strength

	var points := maxi(1, int(descriptor.get("interpolationPoints", 1)))
	result.resize(points + 1)
	for index in range(points + 1):
		var t := float(index) / float(points)
		result[index] = _beam_hermite_point(
			Vector3.ZERO,
			target,
			source_tangent,
			target_tangent,
			t
		)
	return result


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

	var points := _beam_source_path_points(descriptor)
	if points.size() < 2:
		return {"mounted": false, "materialResolved": true, "nodeCount": 0}

	var immediate := ImmediateMesh.new()
	immediate.surface_begin(Mesh.PRIMITIVE_LINES, material)
	for index in range(points.size() - 1):
		immediate.surface_add_vertex(points[index])
		immediate.surface_add_vertex(points[index + 1])
	immediate.surface_end()

	var beam := MeshInstance3D.new()
	beam.name = "CascadeBeam"
	beam.mesh = immediate
	beam.add_to_group("nacht_source_particle_visual")
	beam.set_meta("source_particle_material_path", material_path)
	beam.set_meta("source_beam_target_ue_cm", descriptor.get("targetUEcm"))
	beam.set_meta("source_beam_noise_frequency", descriptor.get("noiseFrequency", 0))
	beam.set_meta(
		"source_beam_interpolation_points",
		descriptor.get("interpolationPoints", 0)
	)
	beam.set_meta("source_beam_source_tangent", descriptor.get("sourceTangent"))
	beam.set_meta("source_beam_target_tangent", descriptor.get("targetTangent"))
	beam.set_meta("source_beam_source_strength", descriptor.get("sourceStrength", 0.0))
	beam.set_meta("source_beam_target_strength", descriptor.get("targetStrength", 0.0))
	beam.set_meta("source_beam_taper_factor", descriptor.get("taperFactor", 1.0))
	beam.set_meta("source_beam_taper_scale", descriptor.get("taperScale", 1.0))
	beam.set_meta("source_beam_noise_runtime_exact", false)
	beam.set_meta("source_beam_width_runtime_exact", false)
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
	var resolved_meshes := 0
	var unresolved_meshes := 0
	var visual_nodes := 0
	var mounted_emitters := 0
	var emitter_rows := _source_emitters(system)
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
			if bool(beam_report.get("mounted", false)):
				mounted_emitters += 1
	else:
		for index in range(emitter_rows.size()):
			var emitter := emitter_rows[index]
			var type_raw: Variant = emitter.get("typeData", {})
			var is_mesh := (
				type_raw is Dictionary
				and str((type_raw as Dictionary).get("exportType", "")) == "ParticleModuleTypeDataMesh"
			)
			var report := (
				_build_source_mesh_emitter(
					anchor,
					system,
					emitter,
					loader,
					auto_activate,
					index
				)
				if is_mesh
				else _build_source_sprite_emitter(
					anchor,
					system,
					emitter,
					loader,
					auto_activate,
					index
				)
			)
			visual_nodes += int(report.get("nodeCount", 0))
			if bool(report.get("materialResolved", false)):
				resolved_materials += 1
			else:
				unresolved_materials += 1
			if is_mesh:
				if bool(report.get("meshResolved", false)):
					resolved_meshes += 1
				else:
					unresolved_meshes += 1
			if bool(report.get("mounted", false)):
				mounted_emitters += 1

	anchor.set_meta("source_particle_visual_node_count", visual_nodes)
	anchor.set_meta("source_particle_visual_material_count", resolved_materials)
	anchor.set_meta("source_particle_visual_unresolved_material_count", unresolved_materials)
	anchor.set_meta("source_particle_visual_resolved_mesh_count", resolved_meshes)
	anchor.set_meta("source_particle_visual_unresolved_mesh_count", unresolved_meshes)
	anchor.set_meta("source_particle_visual_emitter_count", emitter_rows.size())
	anchor.set_meta("source_particle_visual_mounted_emitter_count", mounted_emitters)
	anchor.set_meta("source_particle_visual_exact", false)

	return {
		"mounted": visual_nodes > 0,
		# Aggregate source values are real, but this first renderer does not yet
		# preserve per-emitter LOD/module associations. Never call it exact.
		"exact": false,
		"visualNodeCount": visual_nodes,
		"resolvedMaterialCount": resolved_materials,
		"unresolvedMaterialCount": unresolved_materials,
		"resolvedMeshCount": resolved_meshes,
		"unresolvedMeshCount": unresolved_meshes,
		"emitterCount": emitter_rows.size(),
		"mountedEmitterCount": mounted_emitters,
		"materialPathCount": paths.size(),
		"systemPath": system_path,
	}
