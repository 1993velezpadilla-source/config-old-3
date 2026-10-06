extends RefCounted

const ParticleSource = preload("res://scripts/nacht_particle_source.gd")

const MYSTERY_VERTICAL_SYSTEM := "/Game/CustomMaps/UGC2755515831/CoD/Particles/mysteryBox/findMe/mysteryVerticalParticlesPurple.mysteryVerticalParticlesPurple"
const MYSTERY_VERTICAL_MATERIAL := "/Game/CustomMaps/UGC2755515831/CoD/Particles/mysteryBox/findMe/mysterBoxVerticalMat.mysterBoxVerticalMat"
const BIG_FIRE_FORWARD_SYSTEM := "/Game/CustomMaps/UGC2755515831/M5VFXVOL2/Particles/Reference/Fire/4_bigfire_fwd2_pt.4_bigfire_fwd2_pt"
const BIG_FIRE_FORWARD_MATERIAL := "/Game/CustomMaps/UGC2755515831/M5VFXVOL2/Materials/Fire_Inst/bigfire_fwd2_Inst.bigfire_fwd2_Inst"
const BONE_FIRE_2B_SYSTEM := "/Game/CustomMaps/UGC2755515831/M5VFXVOL2/Particles/Reference/Fireloop/2_bonefire2B_fwd2_pt.2_bonefire2B_fwd2_pt"
const BONE_FIRE_2B_MATERIAL := "/Game/CustomMaps/UGC2755515831/M5VFXVOL2/Materials/Fire_Inst/BoneFire2B_fwd2_Inst.BoneFire2B_fwd2_Inst"
const BONE_FIRE_3_SYSTEM := "/Game/CustomMaps/UGC2755515831/M5VFXVOL2/Particles/Reference/Fireloop/2_bonefire3_pt.2_bonefire3_pt"
const BONE_FIRE_3_MATERIAL := "/Game/CustomMaps/UGC2755515831/M5VFXVOL2/Materials/Fireloop_Inst/BoneFire3_Inst.BoneFire3_Inst"


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



static func big_fire_forward_descriptor(graphs: Dictionary) -> Dictionary:
	var system := _find_system(graphs, BIG_FIRE_FORWARD_SYSTEM)
	if system.is_empty():
		return {"ready": false, "error": "big fire source system missing"}
	if int(system.get("nodeCount", -1)) != 18:
		return {
			"ready": false,
			"error": "big fire node count mismatch %d" % int(system.get("nodeCount", -1)),
		}
	if int(system.get("referenceCount", -1)) != 6:
		return {
			"ready": false,
			"error": "big fire reference count mismatch %d" % int(system.get("referenceCount", -1)),
		}

	var required := _one_node(system, "ParticleModuleRequired")
	var lifetime := _one_node(system, "ParticleModuleLifetime")
	var size := _one_node(system, "ParticleModuleSize")
	var velocity := _one_node(system, "ParticleModuleVelocity")
	var size_life := _one_node(system, "ParticleModuleSizeMultiplyLife")
	var cylinder := _one_node(system, "ParticleModuleLocationPrimitiveCylinder")
	var orientation := _one_node(system, "ParticleModuleOrientationAxisLock")
	var subuv := _one_node(system, "ParticleModuleSubUV")
	var pivot := _one_node(system, "ParticleModulePivotOffset")
	var size_speed := _one_node(system, "ParticleModuleSizeScaleBySpeed")
	for pair: Array in [
		["ParticleModuleRequired", required],
		["ParticleModuleLifetime", lifetime],
		["ParticleModuleSize", size],
		["ParticleModuleVelocity", velocity],
		["ParticleModuleSizeMultiplyLife", size_life],
		["ParticleModuleLocationPrimitiveCylinder", cylinder],
		["ParticleModuleOrientationAxisLock", orientation],
		["ParticleModuleSubUV", subuv],
		["ParticleModulePivotOffset", pivot],
		["ParticleModuleSizeScaleBySpeed", size_speed],
	]:
		if (pair[1] as Dictionary).is_empty():
			return {"ready": false, "error": "missing or duplicate " + str(pair[0])}

	var spawn_nodes := ParticleSource.nodes_by_type(system, "ParticleModuleSpawn")
	var lod_nodes := ParticleSource.nodes_by_type(system, "ParticleLODLevel")
	if spawn_nodes.size() != 2:
		return {"ready": false, "error": "big fire spawn LOD count mismatch %d" % spawn_nodes.size()}
	if lod_nodes.size() != 2:
		return {"ready": false, "error": "big fire LOD count mismatch %d" % lod_nodes.size()}

	var required_props := ParticleSource.properties(required)
	var lifetime_props := ParticleSource.properties(lifetime)
	var size_props := ParticleSource.properties(size)
	var velocity_props := ParticleSource.properties(velocity)
	var cylinder_props := ParticleSource.properties(cylinder)
	var orientation_props := ParticleSource.properties(orientation)
	var subuv_props := ParticleSource.properties(subuv)
	var pivot_props := ParticleSource.properties(pivot)
	var size_speed_props := ParticleSource.properties(size_speed)

	var material_path := str(required_props.get("Material", ""))
	var screen_alignment := str(required_props.get("ScreenAlignment", ""))
	var interpolation := str(required_props.get("InterpolationMethod", ""))
	var subimages_h := int(required_props.get("SubImages_Horizontal", -1))
	var subimages_v := int(required_props.get("SubImages_Vertical", -1))
	var life := _distribution(lifetime_props.get("Lifetime"))
	var start_size := _distribution(size_props.get("StartSize"))
	var start_velocity := _distribution(velocity_props.get("StartVelocity"))
	var radius := _distribution(cylinder_props.get("StartRadius"))
	var subimage_index := _distribution(subuv_props.get("SubImageIndex"))
	var pivot_offset := ParticleSource.vector2(pivot_props.get("PivotOffset"), Vector2.INF)
	var speed_scale := ParticleSource.vector2(size_speed_props.get("SpeedScale"), Vector2.INF)
	var max_scale := ParticleSource.vector2(size_speed_props.get("MaxScale"), Vector2.INF)
	var lock_axis := str(orientation_props.get("LockAxisFlags", ""))

	var life_min := float(life.get("MinValue", -1.0))
	var life_max := float(life.get("MaxValue", -1.0))
	var size_min := _vector_from_distribution(start_size, "MinValueVec", Vector3.INF)
	var size_max := _vector_from_distribution(start_size, "MaxValueVec", Vector3.INF)
	var velocity_min := _vector_from_distribution(start_velocity, "MinValueVec", Vector3.INF)
	var velocity_max := _vector_from_distribution(start_velocity, "MaxValueVec", Vector3.INF)
	var radius_min := float(radius.get("MinValue", -1.0))
	var radius_max := float(radius.get("MaxValue", -1.0))
	var subuv_max := float(subimage_index.get("MaxValue", -1.0))

	var spawn_rates: Array[float] = []
	for node: Dictionary in spawn_nodes:
		var spawn_props := ParticleSource.properties(node)
		var rate := _distribution(spawn_props.get("Rate"))
		spawn_rates.append(float(rate.get("MinValue", -1.0)))
	spawn_rates.sort()

	var peak_active: Array[int] = []
	for node: Dictionary in lod_nodes:
		var lod_props := ParticleSource.properties(node)
		peak_active.append(int(lod_props.get("PeakActiveParticles", -1)))
	peak_active.sort()

	if _canonical(material_path) != _canonical(BIG_FIRE_FORWARD_MATERIAL):
		return {"ready": false, "error": "big fire material mismatch " + material_path}
	if screen_alignment != "PSA_Velocity":
		return {"ready": false, "error": "big fire screen alignment mismatch " + screen_alignment}
	if interpolation != "PSUVIM_Linear_Blend":
		return {"ready": false, "error": "big fire SubUV interpolation mismatch " + interpolation}
	if subimages_h != 8 or subimages_v != 6:
		return {"ready": false, "error": "big fire SubUV grid mismatch %dx%d" % [subimages_h, subimages_v]}
	if lock_axis != "EPAL_ROTATE_Z":
		return {"ready": false, "error": "big fire axis lock mismatch " + lock_axis}
	if not pivot_offset.is_equal_approx(Vector2(0.0, -0.5)):
		return {"ready": false, "error": "big fire pivot mismatch " + str(pivot_offset)}
	if not speed_scale.is_equal_approx(Vector2(1.0, 1.0)):
		return {"ready": false, "error": "big fire speed scale mismatch " + str(speed_scale)}
	if not max_scale.is_equal_approx(Vector2(10.0, 10.0)):
		return {"ready": false, "error": "big fire max scale mismatch " + str(max_scale)}
	if not is_equal_approx(life_min, 1.0) or not is_equal_approx(life_max, 1.75):
		return {"ready": false, "error": "big fire lifetime mismatch %s..%s" % [life_min, life_max]}
	if not size_min.is_equal_approx(Vector3(10.0, 10.0, 0.0)) or not size_max.is_equal_approx(Vector3(10.0, 10.0, 0.0)):
		return {"ready": false, "error": "big fire start size mismatch"}
	if not velocity_min.is_equal_approx(Vector3(-10.0, -10.0, 10.0)):
		return {"ready": false, "error": "big fire velocity min mismatch " + str(velocity_min)}
	if not velocity_max.is_equal_approx(Vector3(10.0, 10.0, 80.0)):
		return {"ready": false, "error": "big fire velocity max mismatch " + str(velocity_max)}
	if not is_equal_approx(radius_min, 50.0) or not is_equal_approx(radius_max, 50.0):
		return {"ready": false, "error": "big fire cylinder radius mismatch"}
	if not is_equal_approx(subuv_max, 47.0):
		return {"ready": false, "error": "big fire SubUV max mismatch " + str(subuv_max)}
	if spawn_rates.size() != 2 or not is_equal_approx(spawn_rates[0], 0.99999994) or not is_equal_approx(spawn_rates[1], 10.0):
		return {"ready": false, "error": "big fire LOD spawn rates mismatch " + str(spawn_rates)}
	if peak_active != [4, 20]:
		return {"ready": false, "error": "big fire peak active LOD mismatch " + str(peak_active)}

	return {
		"ready": true,
		"systemPath": BIG_FIRE_FORWARD_SYSTEM,
		"materialPath": material_path,
		"screenAlignment": screen_alignment,
		"interpolationMethod": interpolation,
		"subImagesHorizontal": subimages_h,
		"subImagesVertical": subimages_v,
		"pivotOffset": pivot_offset,
		"speedScale": speed_scale,
		"maxScale": max_scale,
		"lifetimeMin": life_min,
		"lifetimeMax": life_max,
		"startSizeMinUEcm": size_min,
		"startSizeMaxUEcm": size_max,
		"startVelocityMinUEcm": velocity_min,
		"startVelocityMaxUEcm": velocity_max,
		"cylinderRadiusUEcm": radius_min,
		"subUVMaxIndex": subuv_max,
		"spawnRatesByLOD": spawn_rates,
		"peakActiveByLOD": peak_active,
		"sourceNodeCount": int(system.get("nodeCount", 0)),
		"sourceReferenceCount": int(system.get("referenceCount", 0)),
	}


static func bone_fire_2b_descriptor(graphs: Dictionary) -> Dictionary:
	var system := _find_system(graphs, BONE_FIRE_2B_SYSTEM)
	if system.is_empty():
		return {"ready": false, "error": "bone fire 2B source system missing"}
	if int(system.get("nodeCount", -1)) != 18:
		return {"ready": false, "error": "bone fire 2B node count mismatch %d" % int(system.get("nodeCount", -1))}
	if int(system.get("referenceCount", -1)) != 6:
		return {"ready": false, "error": "bone fire 2B reference count mismatch %d" % int(system.get("referenceCount", -1))}

	var required := _one_node(system, "ParticleModuleRequired")
	var lifetime := _one_node(system, "ParticleModuleLifetime")
	var size := _one_node(system, "ParticleModuleSize")
	var velocity := _one_node(system, "ParticleModuleVelocity")
	var cylinder := _one_node(system, "ParticleModuleLocationPrimitiveCylinder")
	var orientation := _one_node(system, "ParticleModuleOrientationAxisLock")
	var subuv := _one_node(system, "ParticleModuleSubUV")
	var pivot := _one_node(system, "ParticleModulePivotOffset")
	var size_speed := _one_node(system, "ParticleModuleSizeScaleBySpeed")
	for pair: Array in [
		["ParticleModuleRequired", required],
		["ParticleModuleLifetime", lifetime],
		["ParticleModuleSize", size],
		["ParticleModuleVelocity", velocity],
		["ParticleModuleLocationPrimitiveCylinder", cylinder],
		["ParticleModuleOrientationAxisLock", orientation],
		["ParticleModuleSubUV", subuv],
		["ParticleModulePivotOffset", pivot],
		["ParticleModuleSizeScaleBySpeed", size_speed],
	]:
		if (pair[1] as Dictionary).is_empty():
			return {"ready": false, "error": "missing or duplicate " + str(pair[0])}

	var spawn_nodes := ParticleSource.nodes_by_type(system, "ParticleModuleSpawn")
	var lod_nodes := ParticleSource.nodes_by_type(system, "ParticleLODLevel")
	if spawn_nodes.size() != 2:
		return {"ready": false, "error": "bone fire 2B spawn LOD count mismatch %d" % spawn_nodes.size()}
	if lod_nodes.size() != 2:
		return {"ready": false, "error": "bone fire 2B LOD count mismatch %d" % lod_nodes.size()}

	var required_props := ParticleSource.properties(required)
	var lifetime_props := ParticleSource.properties(lifetime)
	var size_props := ParticleSource.properties(size)
	var velocity_props := ParticleSource.properties(velocity)
	var cylinder_props := ParticleSource.properties(cylinder)
	var orientation_props := ParticleSource.properties(orientation)
	var subuv_props := ParticleSource.properties(subuv)
	var pivot_props := ParticleSource.properties(pivot)
	var size_speed_props := ParticleSource.properties(size_speed)

	var material_path := str(required_props.get("Material", ""))
	var screen_alignment := str(required_props.get("ScreenAlignment", ""))
	var interpolation := str(required_props.get("InterpolationMethod", ""))
	var subimages_h := int(required_props.get("SubImages_Horizontal", -1))
	var subimages_v := int(required_props.get("SubImages_Vertical", -1))
	var life := _distribution(lifetime_props.get("Lifetime"))
	var start_size := _distribution(size_props.get("StartSize"))
	var start_velocity := _distribution(velocity_props.get("StartVelocity"))
	var radius := _distribution(cylinder_props.get("StartRadius"))
	var subimage_index := _distribution(subuv_props.get("SubImageIndex"))
	var pivot_offset := ParticleSource.vector2(pivot_props.get("PivotOffset"), Vector2.INF)
	var speed_scale := ParticleSource.vector2(size_speed_props.get("SpeedScale"), Vector2.INF)
	var max_scale := ParticleSource.vector2(size_speed_props.get("MaxScale"), Vector2.INF)
	var lock_axis := str(orientation_props.get("LockAxisFlags", ""))

	var life_min := float(life.get("MinValue", -1.0))
	var life_max := float(life.get("MaxValue", -1.0))
	var size_min := _vector_from_distribution(start_size, "MinValueVec", Vector3.INF)
	var size_max := _vector_from_distribution(start_size, "MaxValueVec", Vector3.INF)
	var velocity_min := _vector_from_distribution(start_velocity, "MinValueVec", Vector3.INF)
	var velocity_max := _vector_from_distribution(start_velocity, "MaxValueVec", Vector3.INF)
	var radius_min := float(radius.get("MinValue", -1.0))
	var radius_max := float(radius.get("MaxValue", -1.0))
	var subuv_max := float(subimage_index.get("MaxValue", -1.0))

	var spawn_rates: Array[float] = []
	for node: Dictionary in spawn_nodes:
		var spawn_props := ParticleSource.properties(node)
		var rate := _distribution(spawn_props.get("Rate"))
		spawn_rates.append(float(rate.get("MinValue", -1.0)))
	spawn_rates.sort()

	var peak_active: Array[int] = []
	for node: Dictionary in lod_nodes:
		var lod_props := ParticleSource.properties(node)
		peak_active.append(int(lod_props.get("PeakActiveParticles", -1)))
	peak_active.sort()

	if _canonical(material_path) != _canonical(BONE_FIRE_2B_MATERIAL):
		return {"ready": false, "error": "bone fire 2B material mismatch " + material_path}
	if screen_alignment != "PSA_Velocity":
		return {"ready": false, "error": "bone fire 2B screen alignment mismatch " + screen_alignment}
	if interpolation != "PSUVIM_Linear_Blend":
		return {"ready": false, "error": "bone fire 2B SubUV interpolation mismatch " + interpolation}
	if subimages_h != 8 or subimages_v != 6:
		return {"ready": false, "error": "bone fire 2B SubUV grid mismatch %dx%d" % [subimages_h, subimages_v]}
	if lock_axis != "EPAL_ROTATE_Z":
		return {"ready": false, "error": "bone fire 2B axis lock mismatch " + lock_axis}
	if not pivot_offset.is_equal_approx(Vector2(0.0, -0.5)):
		return {"ready": false, "error": "bone fire 2B pivot mismatch " + str(pivot_offset)}
	if not speed_scale.is_equal_approx(Vector2(1.0, 1.0)):
		return {"ready": false, "error": "bone fire 2B speed scale mismatch " + str(speed_scale)}
	if not max_scale.is_equal_approx(Vector2(10.0, 10.0)):
		return {"ready": false, "error": "bone fire 2B max scale mismatch " + str(max_scale)}
	if not is_equal_approx(life_min, 1.0) or not is_equal_approx(life_max, 1.75):
		return {"ready": false, "error": "bone fire 2B lifetime mismatch %s..%s" % [life_min, life_max]}
	if not size_min.is_equal_approx(Vector3(14.0, 14.0, 0.0)):
		return {"ready": false, "error": "bone fire 2B start size min mismatch " + str(size_min)}
	if not size_max.is_equal_approx(Vector3(10.0, 10.0, 0.0)):
		return {"ready": false, "error": "bone fire 2B start size max mismatch " + str(size_max)}
	if not velocity_min.is_equal_approx(Vector3(-10.0, -10.0, 10.0)):
		return {"ready": false, "error": "bone fire 2B velocity min mismatch " + str(velocity_min)}
	if not velocity_max.is_equal_approx(Vector3(10.0, 10.0, 80.0)):
		return {"ready": false, "error": "bone fire 2B velocity max mismatch " + str(velocity_max)}
	if not is_equal_approx(radius_min, 50.0) or not is_equal_approx(radius_max, 50.0):
		return {"ready": false, "error": "bone fire 2B cylinder radius mismatch"}
	if not is_equal_approx(subuv_max, 47.0):
		return {"ready": false, "error": "bone fire 2B SubUV max mismatch " + str(subuv_max)}
	if spawn_rates.size() != 2 or not is_equal_approx(spawn_rates[0], 0.99999994) or not is_equal_approx(spawn_rates[1], 10.0):
		return {"ready": false, "error": "bone fire 2B LOD spawn rates mismatch " + str(spawn_rates)}
	if peak_active != [4, 20]:
		return {"ready": false, "error": "bone fire 2B peak active LOD mismatch " + str(peak_active)}

	return {
		"ready": true,
		"systemPath": BONE_FIRE_2B_SYSTEM,
		"materialPath": material_path,
		"screenAlignment": screen_alignment,
		"interpolationMethod": interpolation,
		"subImagesHorizontal": subimages_h,
		"subImagesVertical": subimages_v,
		"pivotOffset": pivot_offset,
		"speedScale": speed_scale,
		"maxScale": max_scale,
		"lifetimeMin": life_min,
		"lifetimeMax": life_max,
		"startSizeMinUEcm": size_min,
		"startSizeMaxUEcm": size_max,
		"startVelocityMinUEcm": velocity_min,
		"startVelocityMaxUEcm": velocity_max,
		"cylinderRadiusUEcm": radius_min,
		"subUVMaxIndex": subuv_max,
		"spawnRatesByLOD": spawn_rates,
		"peakActiveByLOD": peak_active,
		"sourceNodeCount": int(system.get("nodeCount", 0)),
		"sourceReferenceCount": int(system.get("referenceCount", 0)),
	}


static func bone_fire_3_descriptor(graphs: Dictionary) -> Dictionary:
	var system := _find_system(graphs, BONE_FIRE_3_SYSTEM)
	if system.is_empty():
		return {"ready": false, "error": "bone fire 3 source system missing"}
	if int(system.get("nodeCount", -1)) != 17:
		return {"ready": false, "error": "bone fire 3 node count mismatch %d" % int(system.get("nodeCount", -1))}
	if int(system.get("referenceCount", -1)) != 7:
		return {"ready": false, "error": "bone fire 3 reference count mismatch %d" % int(system.get("referenceCount", -1))}

	var required := _one_node(system, "ParticleModuleRequired")
	var lifetime := _one_node(system, "ParticleModuleLifetime")
	var size := _one_node(system, "ParticleModuleSize")
	var color := _one_node(system, "ParticleModuleColorOverLife")
	var size_life := _one_node(system, "ParticleModuleSizeMultiplyLife")
	var cylinder := _one_node(system, "ParticleModuleLocationPrimitiveCylinder")
	var orientation := _one_node(system, "ParticleModuleOrientationAxisLock")
	var pivot := _one_node(system, "ParticleModulePivotOffset")
	var subuv_movie := _one_node(system, "ParticleModuleSubUVMovie")
	var subuv_curve := _one_node(system, "DistributionFloatConstantCurve")
	for pair: Array in [
		["ParticleModuleRequired", required],
		["ParticleModuleLifetime", lifetime],
		["ParticleModuleSize", size],
		["ParticleModuleColorOverLife", color],
		["ParticleModuleSizeMultiplyLife", size_life],
		["ParticleModuleLocationPrimitiveCylinder", cylinder],
		["ParticleModuleOrientationAxisLock", orientation],
		["ParticleModulePivotOffset", pivot],
		["ParticleModuleSubUVMovie", subuv_movie],
		["DistributionFloatConstantCurve", subuv_curve],
	]:
		if (pair[1] as Dictionary).is_empty():
			return {"ready": false, "error": "missing or duplicate " + str(pair[0])}

	var spawn_nodes := ParticleSource.nodes_by_type(system, "ParticleModuleSpawn")
	var lod_nodes := ParticleSource.nodes_by_type(system, "ParticleLODLevel")
	if spawn_nodes.size() != 2:
		return {"ready": false, "error": "bone fire 3 spawn LOD count mismatch %d" % spawn_nodes.size()}
	if lod_nodes.size() != 2:
		return {"ready": false, "error": "bone fire 3 LOD count mismatch %d" % lod_nodes.size()}

	var required_props := ParticleSource.properties(required)
	var lifetime_props := ParticleSource.properties(lifetime)
	var size_props := ParticleSource.properties(size)
	var color_props := ParticleSource.properties(color)
	var size_life_props := ParticleSource.properties(size_life)
	var cylinder_props := ParticleSource.properties(cylinder)
	var orientation_props := ParticleSource.properties(orientation)
	var pivot_props := ParticleSource.properties(pivot)
	var subuv_props := ParticleSource.properties(subuv_movie)

	var material_path := str(required_props.get("Material", ""))
	var screen_alignment := str(required_props.get("ScreenAlignment", ""))
	var interpolation := str(required_props.get("InterpolationMethod", ""))
	var subimages_h := int(required_props.get("SubImages_Horizontal", -1))
	var subimages_v := int(required_props.get("SubImages_Vertical", -1))
	var life := _distribution(lifetime_props.get("Lifetime"))
	var start_size := _distribution(size_props.get("StartSize"))
	var rgb := _distribution(color_props.get("ColorOverLife"))
	var alpha := _distribution(color_props.get("AlphaOverLife"))
	var life_multiplier := _distribution(size_life_props.get("LifeMultiplier"))
	var radius := _distribution(cylinder_props.get("StartRadius"))
	var pivot_offset := ParticleSource.vector2(pivot_props.get("PivotOffset"), Vector2.INF)
	var frame_rate := _distribution(subuv_props.get("FrameRate"))
	var subimage_index := _distribution(subuv_props.get("SubImageIndex"))
	var lock_axis := str(orientation_props.get("LockAxisFlags", ""))

	var life_min := float(life.get("MinValue", -1.0))
	var life_max := float(life.get("MaxValue", -1.0))
	var size_min := _vector_from_distribution(start_size, "MinValueVec", Vector3.INF)
	var size_max := _vector_from_distribution(start_size, "MaxValueVec", Vector3.INF)
	var life_multiplier_min := _vector_from_distribution(life_multiplier, "MinValueVec", Vector3.INF)
	var life_multiplier_max := _vector_from_distribution(life_multiplier, "MaxValueVec", Vector3.INF)
	var radius_min := float(radius.get("MinValue", -1.0))
	var radius_max := float(radius.get("MaxValue", -1.0))
	var frame_rate_min := float(frame_rate.get("MinValue", -1.0))
	var frame_rate_max := float(frame_rate.get("MaxValue", -1.0))
	var rgb_values := ParticleSource.table_values(rgb)
	var alpha_values := ParticleSource.table_values(alpha)
	var life_multiplier_values := ParticleSource.table_values(life_multiplier)
	var subuv_curve_path := str(subimage_index.get("Distribution", ""))

	var spawn_rates: Array[float] = []
	for node: Dictionary in spawn_nodes:
		var spawn_props := ParticleSource.properties(node)
		var rate := _distribution(spawn_props.get("Rate"))
		spawn_rates.append(float(rate.get("MinValue", -1.0)))
	spawn_rates.sort()

	var peak_active: Array[int] = []
	for node: Dictionary in lod_nodes:
		var lod_props := ParticleSource.properties(node)
		peak_active.append(int(lod_props.get("PeakActiveParticles", -1)))
	peak_active.sort()

	if _canonical(material_path) != _canonical(BONE_FIRE_3_MATERIAL):
		return {"ready": false, "error": "bone fire 3 material mismatch " + material_path}
	if screen_alignment != "PSA_Rectangle":
		return {"ready": false, "error": "bone fire 3 screen alignment mismatch " + screen_alignment}
	if interpolation != "PSUVIM_Linear_Blend":
		return {"ready": false, "error": "bone fire 3 SubUV interpolation mismatch " + interpolation}
	if subimages_h != 8 or subimages_v != 8:
		return {"ready": false, "error": "bone fire 3 SubUV grid mismatch %dx%d" % [subimages_h, subimages_v]}
	if lock_axis != "EPAL_ROTATE_Z":
		return {"ready": false, "error": "bone fire 3 axis lock mismatch " + lock_axis}
	if not pivot_offset.is_equal_approx(Vector2(0.0, -0.5)):
		return {"ready": false, "error": "bone fire 3 pivot mismatch " + str(pivot_offset)}
	if not is_equal_approx(life_min, 1.5) or not is_equal_approx(life_max, 2.0):
		return {"ready": false, "error": "bone fire 3 lifetime mismatch %s..%s" % [life_min, life_max]}
	if not size_min.is_equal_approx(Vector3(14.0, 15.0, 0.0)):
		return {"ready": false, "error": "bone fire 3 start size min mismatch " + str(size_min)}
	if not size_max.is_equal_approx(Vector3(10.0, 10.0, 0.0)):
		return {"ready": false, "error": "bone fire 3 start size max mismatch " + str(size_max)}
	if not life_multiplier_min.is_equal_approx(Vector3(10.0, 10.0, 1.0)):
		return {"ready": false, "error": "bone fire 3 life multiplier min mismatch " + str(life_multiplier_min)}
	if not life_multiplier_max.is_equal_approx(Vector3(12.0, 12.0, 10.0)):
		return {"ready": false, "error": "bone fire 3 life multiplier max mismatch " + str(life_multiplier_max)}
	if life_multiplier_values.size() != 6:
		return {"ready": false, "error": "bone fire 3 life multiplier table mismatch %d" % life_multiplier_values.size()}
	if rgb_values.size() != 384:
		return {"ready": false, "error": "bone fire 3 RGB table mismatch %d" % rgb_values.size()}
	if alpha_values.size() != 32:
		return {"ready": false, "error": "bone fire 3 alpha table mismatch %d" % alpha_values.size()}
	if not is_equal_approx(radius_min, 50.0) or not is_equal_approx(radius_max, 50.0):
		return {"ready": false, "error": "bone fire 3 cylinder radius mismatch"}
	if not is_equal_approx(frame_rate_min, 30.0) or not is_equal_approx(frame_rate_max, 30.0):
		return {"ready": false, "error": "bone fire 3 SubUV movie rate mismatch %s..%s" % [frame_rate_min, frame_rate_max]}
	if _canonical(subuv_curve_path) != _canonical(str(subuv_curve.get("objectPath", ""))):
		return {"ready": false, "error": "bone fire 3 SubUV curve reference mismatch " + subuv_curve_path}
	if spawn_rates.size() != 2 or not is_equal_approx(spawn_rates[0], 0.99999994) or not is_equal_approx(spawn_rates[1], 10.0):
		return {"ready": false, "error": "bone fire 3 LOD spawn rates mismatch " + str(spawn_rates)}
	if peak_active != [5, 23]:
		return {"ready": false, "error": "bone fire 3 peak active LOD mismatch " + str(peak_active)}

	return {
		"ready": true,
		"systemPath": BONE_FIRE_3_SYSTEM,
		"materialPath": material_path,
		"screenAlignment": screen_alignment,
		"interpolationMethod": interpolation,
		"subImagesHorizontal": subimages_h,
		"subImagesVertical": subimages_v,
		"pivotOffset": pivot_offset,
		"lifetimeMin": life_min,
		"lifetimeMax": life_max,
		"startSizeMinUEcm": size_min,
		"startSizeMaxUEcm": size_max,
		"lifeMultiplierMin": life_multiplier_min,
		"lifeMultiplierMax": life_multiplier_max,
		"rgbTableValueCount": rgb_values.size(),
		"alphaTableValueCount": alpha_values.size(),
		"cylinderRadiusUEcm": radius_min,
		"subUVFrameRate": frame_rate_min,
		"subUVCurvePath": subuv_curve_path,
		"spawnRatesByLOD": spawn_rates,
		"peakActiveByLOD": peak_active,
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
