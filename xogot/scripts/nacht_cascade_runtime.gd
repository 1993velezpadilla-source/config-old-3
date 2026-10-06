extends RefCounted

const ParticleSource = preload("res://scripts/nacht_particle_source.gd")

const MYSTERY_VERTICAL_SYSTEM := "/Game/CustomMaps/UGC2755515831/CoD/Particles/mysteryBox/findMe/mysteryVerticalParticlesPurple.mysteryVerticalParticlesPurple"
const MYSTERY_VERTICAL_MATERIAL := "/Game/CustomMaps/UGC2755515831/CoD/Particles/mysteryBox/findMe/mysterBoxVerticalMat.mysterBoxVerticalMat"


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


static func _one_node(system: Dictionary, export_type: String) -> Dictionary:
	var matches: Array[Dictionary] = []
	for raw: Variant in system.get("nodes", []):
		if not (raw is Dictionary):
			continue
		var node := raw as Dictionary
		if str(node.get("exportType", "")) == export_type:
			matches.append(node)
	if matches.size() != 1:
		return {}
	return matches[0]


static func _distribution(value: Variant) -> Dictionary:
	return ParticleSource.distribution(value)


static func _vector_from_distribution(
	row: Dictionary,
	key: String,
	default_value: Vector3
) -> Vector3:
	return ParticleSource.vector3(row.get(key), default_value)


static func mystery_vertical_descriptor(graphs: Dictionary) -> Dictionary:
	var system := _find_system(graphs, MYSTERY_VERTICAL_SYSTEM)
	if system.is_empty():
		return {"ready": false, "error": "source system missing"}
	if int(system.get("nodeCount", -1)) != 11:
		return {
			"ready": false,
			"error": "unexpected source node count %d" % int(system.get("nodeCount", -1)),
		}

	var required := _one_node(system, "ParticleModuleRequired")
	var spawn := _one_node(system, "ParticleModuleSpawn")
	var lifetime := _one_node(system, "ParticleModuleLifetime")
	var size := _one_node(system, "ParticleModuleSize")
	var velocity := _one_node(system, "ParticleModuleVelocity")
	var color := _one_node(system, "ParticleModuleColorOverLife")
	var orientation := _one_node(system, "ParticleModuleOrientationAxisLock")
	var lod := _one_node(system, "ParticleLODLevel")
	for pair: Array in [
		["ParticleModuleRequired", required],
		["ParticleModuleSpawn", spawn],
		["ParticleModuleLifetime", lifetime],
		["ParticleModuleSize", size],
		["ParticleModuleVelocity", velocity],
		["ParticleModuleColorOverLife", color],
		["ParticleModuleOrientationAxisLock", orientation],
		["ParticleLODLevel", lod],
	]:
		if (pair[1] as Dictionary).is_empty():
			return {"ready": false, "error": "missing or duplicate " + str(pair[0])}

	var required_props := ParticleSource.properties(required)
	var spawn_props := ParticleSource.properties(spawn)
	var lifetime_props := ParticleSource.properties(lifetime)
	var size_props := ParticleSource.properties(size)
	var velocity_props := ParticleSource.properties(velocity)
	var color_props := ParticleSource.properties(color)
	var orientation_props := ParticleSource.properties(orientation)
	var lod_props := ParticleSource.properties(lod)

	var rate := _distribution(spawn_props.get("Rate"))
	var rate_scale := _distribution(spawn_props.get("RateScale"))
	var life := _distribution(lifetime_props.get("Lifetime"))
	var start_size := _distribution(size_props.get("StartSize"))
	var start_velocity := _distribution(velocity_props.get("StartVelocity"))
	var rgb := _distribution(color_props.get("ColorOverLife"))
	var alpha := _distribution(color_props.get("AlphaOverLife"))

	var material_path := str(required_props.get("Material", ""))
	var screen_alignment := str(required_props.get("ScreenAlignment", ""))
	var lock_axis := str(orientation_props.get("LockAxisFlags", ""))
	var velocity_enabled := bool(velocity_props.get("bEnabled", true))
	var peak_active := int(lod_props.get("PeakActiveParticles", -1))
	var rate_min := float(rate.get("MinValue", -1.0))
	var rate_max := float(rate.get("MaxValue", -1.0))
	var rate_scale_min := float(rate_scale.get("MinValue", -1.0))
	var rate_scale_max := float(rate_scale.get("MaxValue", -1.0))
	var life_min := float(life.get("MinValue", -1.0))
	var life_max := float(life.get("MaxValue", -1.0))
	var size_min := _vector_from_distribution(start_size, "MinValueVec", Vector3.INF)
	var size_max := _vector_from_distribution(start_size, "MaxValueVec", Vector3.INF)
	var rgb_values := ParticleSource.table_values(rgb)
	var alpha_values := ParticleSource.table_values(alpha)

	if _canonical(material_path) != _canonical(MYSTERY_VERTICAL_MATERIAL):
		return {"ready": false, "error": "material authority mismatch " + material_path}
	if screen_alignment != "PSA_Rectangle":
		return {"ready": false, "error": "screen alignment mismatch " + screen_alignment}
	if lock_axis != "EPAL_ROTATE_Z":
		return {"ready": false, "error": "axis lock mismatch " + lock_axis}
	if velocity_enabled:
		return {"ready": false, "error": "source velocity module unexpectedly enabled"}
	if peak_active != 82:
		return {"ready": false, "error": "peak active mismatch %d" % peak_active}
	if not is_equal_approx(rate_min, 10.0) or not is_equal_approx(rate_max, 10.0):
		return {"ready": false, "error": "spawn rate mismatch %s..%s" % [rate_min, rate_max]}
	if not is_equal_approx(rate_scale_min, 1.0) or not is_equal_approx(rate_scale_max, 1.0):
		return {"ready": false, "error": "spawn rate scale mismatch"}
	if not is_equal_approx(life_min, 5.0) or not is_equal_approx(life_max, 8.0):
		return {"ready": false, "error": "lifetime mismatch %s..%s" % [life_min, life_max]}
	if not size_min.is_equal_approx(Vector3(2500.0, 8000.0, 25.0)):
		return {"ready": false, "error": "start size min mismatch " + str(size_min)}
	if not size_max.is_equal_approx(Vector3(3000.0, 8500.0, 25.0)):
		return {"ready": false, "error": "start size max mismatch " + str(size_max)}
	if rgb_values.size() != 192:
		return {"ready": false, "error": "RGB table value count mismatch %d" % rgb_values.size()}
	if alpha_values.size() != 16:
		return {"ready": false, "error": "alpha table value count mismatch %d" % alpha_values.size()}

	return {
		"ready": true,
		"systemPath": MYSTERY_VERTICAL_SYSTEM,
		"materialPath": material_path,
		"screenAlignment": screen_alignment,
		"lockAxis": lock_axis,
		"peakActiveParticles": peak_active,
		"spawnRateMin": rate_min,
		"spawnRateMax": rate_max,
		"spawnRateScaleMin": rate_scale_min,
		"spawnRateScaleMax": rate_scale_max,
		"lifetimeMin": life_min,
		"lifetimeMax": life_max,
		"startSizeMinUEcm": size_min,
		"startSizeMaxUEcm": size_max,
		"velocityModuleEnabled": velocity_enabled,
		"rgbTable": rgb,
		"alphaTable": alpha,
		"startVelocityTable": start_velocity,
		"sourceNodeCount": int(system.get("nodeCount", 0)),
		"sourceReferenceCount": int(system.get("referenceCount", 0)),
	}


static func placements_for_system(authority: Dictionary, object_path: String) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	var wanted := _canonical(object_path)
	for raw: Variant in authority.get("placements", []):
		if not (raw is Dictionary):
			continue
		var row := raw as Dictionary
		if _canonical(str(row.get("templateObjectPath", ""))) == wanted:
			result.append(row)
	return result
