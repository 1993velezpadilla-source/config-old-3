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
const PAP_WHEEL_SYSTEM := "/Game/CustomMaps/UGC2755515831/Materials/KillerJim/PapEffects/PaPWheelParticles.PaPWheelParticles"
const PAP_WHEEL_MATERIAL_1 := "/Game/CustomMaps/UGC2755515831/Materials/KillerJim/PapEffects/PaPWheelMaterial1.PaPWheelMaterial1"
const PAP_WHEEL_MATERIAL_2 := "/Game/CustomMaps/UGC2755515831/Materials/KillerJim/PapEffects/PaPWheelMaterial2.PaPWheelMaterial2"
const MYSTERY_BOX_FOG_SYSTEM := "/Game/CustomMaps/UGC2755515831/Materials/KillerJim/Smoke/mysteryBoxFog.mysteryBoxFog"
const MYSTERY_BOX_FOG_MATERIAL := "/Game/CustomMaps/UGC2755515831/Materials/KillerJim/Smoke/unlit_smoke.unlit_smoke"
const MYSTERY_INSIDE_SYSTEM := "/Game/CustomMaps/UGC2755515831/CoD/Particles/mysteryBox/inside/mysteryParticles.mysteryParticles"
const MYSTERY_INSIDE_MATERIAL := "/Game/CustomMaps/UGC2755515831/CoD/Particles/mysteryBox/inside/mysteryParticle.mysteryParticle"
const BIG_FIRE_VG_SMK_SYSTEM := "/Game/CustomMaps/UGC2755515831/M5VFXVOL2/Particles/Reference/Fireloop/4_bigfire_vg_smk_pt.4_bigfire_vg_smk_pt"
const BIG_FIRE_VG_SMK_MATERIAL := "/Game/CustomMaps/UGC2755515831/M5VFXVOL2/Materials/Fireloop_Inst/bigfire_vg_smk_Inst.bigfire_vg_smk_Inst"
const PAP_WHEEL_OUT_SYSTEM := "/Game/CustomMaps/UGC2755515831/Materials/KillerJim/PapEffects/PaPWheelParticlesOut.PaPWheelParticlesOut"
const PAP_WHEEL_OUT_MATERIAL := "/Game/CustomMaps/UGC2755515831/Materials/KillerJim/PapEffects/PaPWheelMaterial1.PaPWheelMaterial1"


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


static func pap_wheel_descriptor(graphs: Dictionary) -> Dictionary:
	var system := _find_system(graphs, PAP_WHEEL_SYSTEM)
	if system.is_empty():
		return {"ready": false, "error": "PaP wheel source system missing"}
	if int(system.get("nodeCount", -1)) != 23:
		return {"ready": false, "error": "PaP wheel node count mismatch %d" % int(system.get("nodeCount", -1))}
	if int(system.get("referenceCount", -1)) != 8:
		return {"ready": false, "error": "PaP wheel reference count mismatch %d" % int(system.get("referenceCount", -1))}

	var required_nodes := ParticleSource.nodes_by_type(system, "ParticleModuleRequired")
	var lifetime_nodes := ParticleSource.nodes_by_type(system, "ParticleModuleLifetime")
	var size_nodes := ParticleSource.nodes_by_type(system, "ParticleModuleSize")
	var color_nodes := ParticleSource.nodes_by_type(system, "ParticleModuleColor")
	var size_life_nodes := ParticleSource.nodes_by_type(system, "ParticleModuleSizeMultiplyLife")
	var rotation_nodes := ParticleSource.nodes_by_type(system, "ParticleModuleRotation")
	var rotation_rate_nodes := ParticleSource.nodes_by_type(system, "ParticleModuleRotationRate")
	var velocity_life_nodes := ParticleSource.nodes_by_type(system, "ParticleModuleVelocityOverLifetime")
	var spawn_nodes := ParticleSource.nodes_by_type(system, "ParticleModuleSpawn")
	var lod_nodes := ParticleSource.nodes_by_type(system, "ParticleLODLevel")

	for pair: Array in [
		["ParticleModuleRequired", required_nodes],
		["ParticleModuleLifetime", lifetime_nodes],
		["ParticleModuleSize", size_nodes],
		["ParticleModuleColor", color_nodes],
		["ParticleModuleSizeMultiplyLife", size_life_nodes],
		["ParticleModuleRotation", rotation_nodes],
		["ParticleModuleRotationRate", rotation_rate_nodes],
		["ParticleModuleVelocityOverLifetime", velocity_life_nodes],
		["ParticleModuleSpawn", spawn_nodes],
		["ParticleLODLevel", lod_nodes],
	]:
		if (pair[1] as Array).size() != 2:
			return {"ready": false, "error": "PaP wheel emitter module count mismatch " + str(pair[0])}

	var materials: Array[String] = []
	var lifetimes: Array[float] = []
	var size_mins: Array[Vector3] = []
	var size_maxs: Array[Vector3] = []
	var rotation_rate_mins: Array[float] = []
	var rotation_rate_maxs: Array[float] = []
	var velocity_life_mins: Array[Vector3] = []
	var velocity_life_table_counts: Array[int] = []
	var velocity_life_time_scales: Array[float] = []
	var size_life_table_counts: Array[int] = []
	var color_mins: Array[Vector3] = []
	var color_maxs: Array[Vector3] = []
	var alpha_values: Array[float] = []
	var rotation_table_counts: Array[int] = []
	var spawn_rates: Array[float] = []
	var burst_counts: Array[int] = []
	var peak_active: Array[int] = []

	for node: Dictionary in required_nodes:
		var p := ParticleSource.properties(node)
		materials.append(str(p.get("Material", "")))
		if int(p.get("EmitterLoops", -1)) != 1:
			return {"ready": false, "error": "PaP wheel emitter loops mismatch"}
		if int(p.get("RandomImageTime", -1)) != 1:
			return {"ready": false, "error": "PaP wheel random image time mismatch"}
		if bool(p.get("bUseLegacyEmitterTime", true)):
			return {"ready": false, "error": "PaP wheel legacy emitter time unexpectedly enabled"}

	for node: Dictionary in lifetime_nodes:
		var p := ParticleSource.properties(node)
		var d := _distribution(p.get("Lifetime"))
		var lo := float(d.get("MinValue", -1.0))
		var hi := float(d.get("MaxValue", -1.0))
		if not is_equal_approx(lo, 8.0) or not is_equal_approx(hi, 8.0):
			return {"ready": false, "error": "PaP wheel lifetime mismatch %s..%s" % [lo, hi]}
		lifetimes.append(lo)

	for node: Dictionary in size_nodes:
		var p := ParticleSource.properties(node)
		var d := _distribution(p.get("StartSize"))
		size_mins.append(_vector_from_distribution(d, "MinValueVec", Vector3.INF))
		size_maxs.append(_vector_from_distribution(d, "MaxValueVec", Vector3.INF))

	for node: Dictionary in color_nodes:
		var p := ParticleSource.properties(node)
		var color := _distribution(p.get("StartColor"))
		var alpha := _distribution(p.get("StartAlpha"))
		color_mins.append(_vector_from_distribution(color, "MinValueVec", Vector3.INF))
		color_maxs.append(_vector_from_distribution(color, "MaxValueVec", Vector3.INF))
		alpha_values.append(float(alpha.get("MinValue", -1.0)))

	for node: Dictionary in size_life_nodes:
		var p := ParticleSource.properties(node)
		var d := _distribution(p.get("LifeMultiplier"))
		size_life_table_counts.append(ParticleSource.table_values(d).size())

	for node: Dictionary in rotation_nodes:
		var p := ParticleSource.properties(node)
		var d := _distribution(p.get("StartRotation"))
		if not is_equal_approx(float(d.get("MaxValue", -1.0)), 1.0):
			return {"ready": false, "error": "PaP wheel start rotation max mismatch"}
		rotation_table_counts.append(ParticleSource.table_values(d).size())

	for node: Dictionary in rotation_rate_nodes:
		var p := ParticleSource.properties(node)
		var d := _distribution(p.get("StartRotationRate"))
		rotation_rate_mins.append(float(d.get("MinValue", 999.0)))
		rotation_rate_maxs.append(float(d.get("MaxValue", -999.0)))

	for node: Dictionary in velocity_life_nodes:
		var p := ParticleSource.properties(node)
		var d := _distribution(p.get("VelOverLife"))
		velocity_life_mins.append(_vector_from_distribution(d, "MinValueVec", Vector3.INF))
		velocity_life_table_counts.append(ParticleSource.table_values(d).size())
		var table_raw: Variant = d.get("Table", {})
		var table := table_raw as Dictionary if table_raw is Dictionary else {}
		velocity_life_time_scales.append(float(table.get("TimeScale", -1.0)))

	for node: Dictionary in spawn_nodes:
		var p := ParticleSource.properties(node)
		var rate := _distribution(p.get("Rate"))
		var rate_scale := _distribution(p.get("RateScale"))
		var lo := float(rate.get("MinValue", -1.0))
		var hi := float(rate.get("MaxValue", -1.0))
		if not is_equal_approx(lo, 3.0) or not is_equal_approx(hi, 3.0):
			return {"ready": false, "error": "PaP wheel spawn rate mismatch %s..%s" % [lo, hi]}
		if not is_equal_approx(float(rate_scale.get("MinValue", -1.0)), 1.0):
			return {"ready": false, "error": "PaP wheel spawn rate scale mismatch"}
		spawn_rates.append(lo)
		var bursts_raw: Variant = p.get("BurstList", [])
		if not (bursts_raw is Array) or (bursts_raw as Array).size() != 1:
			return {"ready": false, "error": "PaP wheel burst list mismatch"}
		var burst_raw: Variant = (bursts_raw as Array)[0]
		if not (burst_raw is Dictionary):
			return {"ready": false, "error": "PaP wheel burst entry invalid"}
		var burst := burst_raw as Dictionary
		if int(burst.get("Count", -1)) != 2 or int(burst.get("CountLow", 0)) != -1 or not is_equal_approx(float(burst.get("Time", -1.0)), 0.0):
			return {"ready": false, "error": "PaP wheel burst values mismatch " + str(burst)}
		burst_counts.append(2)

	for node: Dictionary in lod_nodes:
		var p := ParticleSource.properties(node)
		peak_active.append(int(p.get("PeakActiveParticles", -1)))

	materials.sort()
	peak_active.sort()
	if materials != [PAP_WHEEL_MATERIAL_1, PAP_WHEEL_MATERIAL_2]:
		return {"ready": false, "error": "PaP wheel material set mismatch " + str(materials)}
	for v: Vector3 in size_mins:
		if not v.is_equal_approx(Vector3(60.0, 60.0, 60.0)):
			return {"ready": false, "error": "PaP wheel start size min mismatch " + str(v)}
	for v: Vector3 in size_maxs:
		if not v.is_equal_approx(Vector3(70.0, 70.0, 70.0)):
			return {"ready": false, "error": "PaP wheel start size max mismatch " + str(v)}
	for v: Vector3 in color_mins:
		if not v.is_equal_approx(Vector3(0.786901, 0.890625, 0.844701)):
			return {"ready": false, "error": "PaP wheel start color min mismatch " + str(v)}
	for v: Vector3 in color_maxs:
		if not v.is_equal_approx(Vector3.ONE):
			return {"ready": false, "error": "PaP wheel start color max mismatch " + str(v)}
	for a: float in alpha_values:
		if not is_equal_approx(a, 1.0):
			return {"ready": false, "error": "PaP wheel start alpha mismatch"}
	for count: int in size_life_table_counts:
		if count != 384:
			return {"ready": false, "error": "PaP wheel size-life table mismatch %d" % count}
	for count: int in rotation_table_counts:
		if count != 2:
			return {"ready": false, "error": "PaP wheel rotation table mismatch %d" % count}
	for lo: float in rotation_rate_mins:
		if not is_equal_approx(lo, -0.1):
			return {"ready": false, "error": "PaP wheel rotation-rate min mismatch %s" % lo}
	for hi: float in rotation_rate_maxs:
		if not is_equal_approx(hi, 0.2):
			return {"ready": false, "error": "PaP wheel rotation-rate max mismatch %s" % hi}
	for v: Vector3 in velocity_life_mins:
		if not v.is_equal_approx(Vector3(-2.0, -2.0, -2.0)):
			return {"ready": false, "error": "PaP wheel velocity-over-life min mismatch " + str(v)}
	for count: int in velocity_life_table_counts:
		if count != 6:
			return {"ready": false, "error": "PaP wheel velocity-over-life table mismatch %d" % count}
	for scale: float in velocity_life_time_scales:
		if not is_equal_approx(scale, 5.0):
			return {"ready": false, "error": "PaP wheel velocity-over-life time scale mismatch %s" % scale}
	if peak_active != [6, 6]:
		return {"ready": false, "error": "PaP wheel peak active mismatch " + str(peak_active)}

	return {
		"ready": true,
		"systemPath": PAP_WHEEL_SYSTEM,
		"materialPaths": materials,
		"emitterCount": 2,
		"lifetimeSeconds": 8.0,
		"startSizeMinUEcm": Vector3(60.0, 60.0, 60.0),
		"startSizeMaxUEcm": Vector3(70.0, 70.0, 70.0),
		"spawnRate": 3.0,
		"burstCount": 2,
		"startColorMin": Vector3(0.786901, 0.890625, 0.844701),
		"startColorMax": Vector3.ONE,
		"rotationRateMin": -0.1,
		"rotationRateMax": 0.2,
		"velocityOverLifeMin": Vector3(-2.0, -2.0, -2.0),
		"velocityOverLifeTimeScale": 5.0,
		"sizeLifeTableValueCount": 384,
		"peakActiveByEmitter": peak_active,
		"sourceNodeCount": int(system.get("nodeCount", 0)),
		"sourceReferenceCount": int(system.get("referenceCount", 0)),
	}


static func mystery_box_fog_descriptor(graphs: Dictionary) -> Dictionary:
	var system := _find_system(graphs, MYSTERY_BOX_FOG_SYSTEM)
	if system.is_empty():
		return {"ready": false, "error": "mystery box fog source system missing"}
	if int(system.get("nodeCount", -1)) != 14:
		return {"ready": false, "error": "mystery box fog node count mismatch %d" % int(system.get("nodeCount", -1))}
	if int(system.get("referenceCount", -1)) != 5:
		return {"ready": false, "error": "mystery box fog reference count mismatch %d" % int(system.get("referenceCount", -1))}

	var required := _one_node(system, "ParticleModuleRequired")
	var lifetime := _one_node(system, "ParticleModuleLifetime")
	var location := _one_node(system, "ParticleModuleLocation")
	var size := _one_node(system, "ParticleModuleSize")
	var size_life := _one_node(system, "ParticleModuleSizeMultiplyLife")
	var color := _one_node(system, "ParticleModuleColorOverLife")
	var spawn := _one_node(system, "ParticleModuleSpawn")
	var subuv_movie := _one_node(system, "ParticleModuleSubUVMovie")
	var subuv_curve := _one_node(system, "DistributionFloatConstantCurve")
	var velocity_life := _one_node(system, "ParticleModuleVelocityOverLifetime")
	var velocity := _one_node(system, "ParticleModuleVelocity")
	var lod := _one_node(system, "ParticleLODLevel")
	for pair: Array in [
		["ParticleModuleRequired", required],
		["ParticleModuleLifetime", lifetime],
		["ParticleModuleLocation", location],
		["ParticleModuleSize", size],
		["ParticleModuleSizeMultiplyLife", size_life],
		["ParticleModuleColorOverLife", color],
		["ParticleModuleSpawn", spawn],
		["ParticleModuleSubUVMovie", subuv_movie],
		["DistributionFloatConstantCurve", subuv_curve],
		["ParticleModuleVelocityOverLifetime", velocity_life],
		["ParticleModuleVelocity", velocity],
		["ParticleLODLevel", lod],
	]:
		if (pair[1] as Dictionary).is_empty():
			return {"ready": false, "error": "mystery box fog missing or duplicate " + str(pair[0])}

	var required_props := ParticleSource.properties(required)
	var lifetime_props := ParticleSource.properties(lifetime)
	var location_props := ParticleSource.properties(location)
	var size_props := ParticleSource.properties(size)
	var size_life_props := ParticleSource.properties(size_life)
	var color_props := ParticleSource.properties(color)
	var spawn_props := ParticleSource.properties(spawn)
	var subuv_props := ParticleSource.properties(subuv_movie)
	var velocity_life_props := ParticleSource.properties(velocity_life)
	var velocity_props := ParticleSource.properties(velocity)
	var lod_props := ParticleSource.properties(lod)

	var material_path := str(required_props.get("Material", ""))
	var interpolation := str(required_props.get("InterpolationMethod", ""))
	var subimages_h := int(required_props.get("SubImages_Horizontal", -1))
	var subimages_v := int(required_props.get("SubImages_Vertical", -1))
	var life := _distribution(lifetime_props.get("Lifetime"))
	var start_location := _distribution(location_props.get("StartLocation"))
	var start_size := _distribution(size_props.get("StartSize"))
	var life_multiplier := _distribution(size_life_props.get("LifeMultiplier"))
	var rgb := _distribution(color_props.get("ColorOverLife"))
	var alpha := _distribution(color_props.get("AlphaOverLife"))
	var rate := _distribution(spawn_props.get("Rate"))
	var rate_scale := _distribution(spawn_props.get("RateScale"))
	var frame_rate := _distribution(subuv_props.get("FrameRate"))
	var subimage_index := _distribution(subuv_props.get("SubImageIndex"))
	var vel_over_life := _distribution(velocity_life_props.get("VelOverLife"))
	var start_velocity := _distribution(velocity_props.get("StartVelocity"))

	var life_min := float(life.get("MinValue", -1.0))
	var life_max := float(life.get("MaxValue", -1.0))
	var location_min := _vector_from_distribution(start_location, "MinValueVec", Vector3.INF)
	var location_max := _vector_from_distribution(start_location, "MaxValueVec", Vector3.INF)
	var size_min := _vector_from_distribution(start_size, "MinValueVec", Vector3.INF)
	var size_max := _vector_from_distribution(start_size, "MaxValueVec", Vector3.INF)
	var life_multiplier_min := _vector_from_distribution(life_multiplier, "MinValueVec", Vector3.INF)
	var life_multiplier_max := _vector_from_distribution(life_multiplier, "MaxValueVec", Vector3.INF)
	var color_min := _vector_from_distribution(rgb, "MinValueVec", Vector3.INF)
	var color_max := _vector_from_distribution(rgb, "MaxValueVec", Vector3.INF)
	var alpha_max := float(alpha.get("MaxValue", -1.0))
	var spawn_rate := float(rate.get("MinValue", -1.0))
	var spawn_rate_max := float(rate.get("MaxValue", -1.0))
	var spawn_rate_scale := float(rate_scale.get("MinValue", -1.0))
	var subuv_fps := float(frame_rate.get("MinValue", -1.0))
	var subuv_fps_max := float(frame_rate.get("MaxValue", -1.0))
	var subuv_curve_path := str(subimage_index.get("Distribution", ""))
	var velocity_life_min := _vector_from_distribution(vel_over_life, "MinValueVec", Vector3.INF)
	var velocity_life_max := _vector_from_distribution(vel_over_life, "MaxValueVec", Vector3.INF)
	var velocity_min := _vector_from_distribution(start_velocity, "MinValueVec", Vector3.INF)
	var velocity_max := _vector_from_distribution(start_velocity, "MaxValueVec", Vector3.INF)
	var peak_active := int(lod_props.get("PeakActiveParticles", -1))

	var life_multiplier_values := ParticleSource.table_values(life_multiplier)
	var rgb_values := ParticleSource.table_values(rgb)
	var alpha_values := ParticleSource.table_values(alpha)
	var velocity_life_values := ParticleSource.table_values(vel_over_life)
	var velocity_values := ParticleSource.table_values(start_velocity)
	var velocity_life_table_raw: Variant = vel_over_life.get("Table", {})
	var velocity_life_table := velocity_life_table_raw as Dictionary if velocity_life_table_raw is Dictionary else {}
	var velocity_life_time_scale := float(velocity_life_table.get("TimeScale", -1.0))

	if _canonical(material_path) != _canonical(MYSTERY_BOX_FOG_MATERIAL):
		return {"ready": false, "error": "mystery box fog material mismatch " + material_path}
	if interpolation != "PSUVIM_Linear_Blend":
		return {"ready": false, "error": "mystery box fog interpolation mismatch " + interpolation}
	if subimages_h != 6 or subimages_v != 6:
		return {"ready": false, "error": "mystery box fog SubUV grid mismatch %dx%d" % [subimages_h, subimages_v]}
	if not is_equal_approx(life_min, 3.0) or not is_equal_approx(life_max, 5.0):
		return {"ready": false, "error": "mystery box fog lifetime mismatch %s..%s" % [life_min, life_max]}
	if not location_min.is_equal_approx(Vector3(-95.0, -10.0, -5.0)) or not location_max.is_equal_approx(Vector3(95.0, 10.0, 5.0)):
		return {"ready": false, "error": "mystery box fog location range mismatch"}
	if not size_min.is_equal_approx(Vector3(3.0, 3.0, 3.0)) or not size_max.is_equal_approx(Vector3(5.0, 5.0, 5.0)):
		return {"ready": false, "error": "mystery box fog start size mismatch"}
	if not life_multiplier_min.is_equal_approx(Vector3(10.0, 0.0, 0.0)) or not life_multiplier_max.is_equal_approx(Vector3(50.0, 1.0, 1.0)):
		return {"ready": false, "error": "mystery box fog size-life range mismatch"}
	if life_multiplier_values.size() != 96:
		return {"ready": false, "error": "mystery box fog size-life table mismatch %d" % life_multiplier_values.size()}
	if not color_min.is_equal_approx(Vector3(0.49479154, 0.489095, 0.4591)):
		return {"ready": false, "error": "mystery box fog color min mismatch " + str(color_min)}
	if not color_max.is_equal_approx(Vector3(1.0, 1.0, 0.97423244)):
		return {"ready": false, "error": "mystery box fog color max mismatch " + str(color_max)}
	if rgb_values.size() != 12 or alpha_values.size() != 128 or not is_equal_approx(alpha_max, 1.0380507):
		return {"ready": false, "error": "mystery box fog color/alpha curve mismatch"}
	if not is_equal_approx(spawn_rate, 4.0) or not is_equal_approx(spawn_rate_max, 4.0) or not is_equal_approx(spawn_rate_scale, 1.0):
		return {"ready": false, "error": "mystery box fog spawn rate mismatch"}
	if bool(spawn_props.get("bApplyGlobalSpawnRateScale", true)):
		return {"ready": false, "error": "mystery box fog global spawn rate scale unexpectedly enabled"}
	var bursts_raw: Variant = spawn_props.get("BurstList", [])
	if not (bursts_raw is Array) or (bursts_raw as Array).size() != 1:
		return {"ready": false, "error": "mystery box fog burst list mismatch"}
	var burst_raw: Variant = (bursts_raw as Array)[0]
	if not (burst_raw is Dictionary):
		return {"ready": false, "error": "mystery box fog burst entry invalid"}
	var burst := burst_raw as Dictionary
	if int(burst.get("Count", -1)) != 0 or int(burst.get("CountLow", 0)) != -1 or not is_equal_approx(float(burst.get("Time", -1.0)), 0.0):
		return {"ready": false, "error": "mystery box fog burst values mismatch " + str(burst)}
	if not is_equal_approx(subuv_fps, 16.0) or not is_equal_approx(subuv_fps_max, 16.0):
		return {"ready": false, "error": "mystery box fog SubUV frame rate mismatch"}
	if _canonical(subuv_curve_path) != _canonical(str(subuv_curve.get("objectPath", ""))):
		return {"ready": false, "error": "mystery box fog SubUV curve reference mismatch " + subuv_curve_path}
	if not velocity_life_min.is_equal_approx(Vector3(0.0, 0.0, -1.5)) or not velocity_life_max.is_equal_approx(Vector3(0.0, 0.2, 0.75)):
		return {"ready": false, "error": "mystery box fog velocity-over-life range mismatch"}
	if velocity_life_values.size() != 6 or not is_equal_approx(velocity_life_time_scale, 1.0):
		return {"ready": false, "error": "mystery box fog velocity-over-life table mismatch"}
	if not velocity_min.is_equal_approx(Vector3(0.0, 100.0, 0.0)) or not velocity_max.is_equal_approx(Vector3(0.0, 100.0, 40.0)):
		return {"ready": false, "error": "mystery box fog start velocity range mismatch"}
	if velocity_values.size() != 6:
		return {"ready": false, "error": "mystery box fog start velocity table mismatch %d" % velocity_values.size()}
	if peak_active != 22:
		return {"ready": false, "error": "mystery box fog peak active mismatch %d" % peak_active}

	return {
		"ready": true,
		"systemPath": MYSTERY_BOX_FOG_SYSTEM,
		"materialPath": material_path,
		"lifetimeMin": life_min,
		"lifetimeMax": life_max,
		"startLocationMinUEcm": location_min,
		"startLocationMaxUEcm": location_max,
		"startSizeMinUEcm": size_min,
		"startSizeMaxUEcm": size_max,
		"lifeMultiplierMin": life_multiplier_min,
		"lifeMultiplierMax": life_multiplier_max,
		"lifeMultiplierTableValueCount": life_multiplier_values.size(),
		"colorMin": color_min,
		"colorMax": color_max,
		"rgbTableValueCount": rgb_values.size(),
		"alphaTableValueCount": alpha_values.size(),
		"alphaMax": alpha_max,
		"spawnRate": spawn_rate,
		"subUVFrameRate": subuv_fps,
		"velocityOverLifeMin": velocity_life_min,
		"velocityOverLifeMax": velocity_life_max,
		"velocityOverLifeTimeScale": velocity_life_time_scale,
		"startVelocityMinUEcm": velocity_min,
		"startVelocityMaxUEcm": velocity_max,
		"peakActiveParticles": peak_active,
		"sourceNodeCount": int(system.get("nodeCount", 0)),
		"sourceReferenceCount": int(system.get("referenceCount", 0)),
	}


static func mystery_inside_descriptor(graphs: Dictionary) -> Dictionary:
	var system := _find_system(graphs, MYSTERY_INSIDE_SYSTEM)
	if system.is_empty():
		return {"ready": false, "error": "mystery inside source system missing"}
	if int(system.get("nodeCount", -1)) != 17:
		return {"ready": false, "error": "mystery inside node count mismatch %d" % int(system.get("nodeCount", -1))}
	if int(system.get("referenceCount", -1)) != 9:
		return {"ready": false, "error": "mystery inside reference count mismatch %d" % int(system.get("referenceCount", -1))}

	var required := _one_node(system, "ParticleModuleRequired")
	var lifetime := _one_node(system, "ParticleModuleLifetime")
	var location := _one_node(system, "ParticleModuleLocation")
	var orbit := _one_node(system, "ParticleModuleOrbit")
	var size := _one_node(system, "ParticleModuleSize")
	var spawn := _one_node(system, "ParticleModuleSpawn")
	var type_gpu := _one_node(system, "ParticleModuleTypeDataGpu")
	var velocity := _one_node(system, "ParticleModuleVelocity")
	var color := _one_node(system, "ParticleModuleColorOverLife")
	var lod_nodes := ParticleSource.nodes_by_type(system, "ParticleLODLevel")
	for pair: Array in [
		["ParticleModuleRequired", required],
		["ParticleModuleLifetime", lifetime],
		["ParticleModuleLocation", location],
		["ParticleModuleOrbit", orbit],
		["ParticleModuleSize", size],
		["ParticleModuleSpawn", spawn],
		["ParticleModuleTypeDataGpu", type_gpu],
		["ParticleModuleVelocity", velocity],
		["ParticleModuleColorOverLife", color],
	]:
		if (pair[1] as Dictionary).is_empty():
			return {"ready": false, "error": "mystery inside missing or duplicate " + str(pair[0])}
	if lod_nodes.size() != 2:
		return {"ready": false, "error": "mystery inside LOD count mismatch %d" % lod_nodes.size()}

	var required_props := ParticleSource.properties(required)
	var lifetime_props := ParticleSource.properties(lifetime)
	var location_props := ParticleSource.properties(location)
	var orbit_props := ParticleSource.properties(orbit)
	var size_props := ParticleSource.properties(size)
	var spawn_props := ParticleSource.properties(spawn)
	var gpu_props := ParticleSource.properties(type_gpu)
	var velocity_props := ParticleSource.properties(velocity)
	var color_props := ParticleSource.properties(color)

	var material_path := str(required_props.get("Material", ""))
	var screen_alignment := str(required_props.get("ScreenAlignment", ""))
	var random_image_time := int(required_props.get("RandomImageTime", -1))
	var legacy_emitter_time := bool(required_props.get("bUseLegacyEmitterTime", true))
	var life := _distribution(lifetime_props.get("Lifetime"))
	var start_location := _distribution(location_props.get("StartLocation"))
	var start_size := _distribution(size_props.get("StartSize"))
	var rate := _distribution(spawn_props.get("Rate"))
	var rate_scale := _distribution(spawn_props.get("RateScale"))
	var start_velocity := _distribution(velocity_props.get("StartVelocity"))
	var rgb := _distribution(color_props.get("ColorOverLife"))
	var alpha := _distribution(color_props.get("AlphaOverLife"))

	var life_min := float(life.get("MinValue", -1.0))
	var life_max := float(life.get("MaxValue", -1.0))
	var location_min := _vector_from_distribution(start_location, "MinValueVec", Vector3.INF)
	var location_max := _vector_from_distribution(start_location, "MaxValueVec", Vector3.INF)
	var size_min := _vector_from_distribution(start_size, "MinValueVec", Vector3.INF)
	var size_max := _vector_from_distribution(start_size, "MaxValueVec", Vector3.INF)
	var spawn_rate := float(rate.get("MinValue", -1.0))
	var spawn_rate_max := float(rate.get("MaxValue", -1.0))
	var spawn_scale := float(rate_scale.get("MinValue", -1.0))
	var spawn_scale_max := float(rate_scale.get("MaxValue", -1.0))
	var velocity_min := _vector_from_distribution(start_velocity, "MinValueVec", Vector3.INF)
	var velocity_max := _vector_from_distribution(start_velocity, "MaxValueVec", Vector3.INF)
	var rgb_min := _vector_from_distribution(rgb, "MinValueVec", Vector3.INF)
	var rgb_max := _vector_from_distribution(rgb, "MaxValueVec", Vector3.INF)
	var rgb_values := ParticleSource.table_values(rgb)
	var alpha_values := ParticleSource.table_values(alpha)

	var orbit_enabled := bool(orbit_props.get("bEnabled", true))
	var offset_distribution := str((_distribution(orbit_props.get("OffsetAmount"))).get("Distribution", ""))
	var rotation_distribution := str((_distribution(orbit_props.get("RotationAmount"))).get("Distribution", ""))
	var rotation_rate_distribution := str((_distribution(orbit_props.get("RotationRateAmount"))).get("Distribution", ""))
	var orbit_offset_min := Vector3.INF
	var orbit_offset_max := Vector3.INF
	var orbit_rotation_max := Vector3.INF
	var orbit_rotation_rate_max := Vector3.INF
	for raw: Variant in system.get("nodes", []):
		if not (raw is Dictionary):
			continue
		var node := raw as Dictionary
		var node_path := str(node.get("objectPath", ""))
		var node_props := ParticleSource.properties(node)
		if _canonical(node_path) == _canonical(offset_distribution):
			orbit_offset_min = ParticleSource.vector3(node_props.get("Min"), Vector3.INF)
			orbit_offset_max = ParticleSource.vector3(node_props.get("Max"), Vector3.INF)
		elif _canonical(node_path) == _canonical(rotation_distribution):
			orbit_rotation_max = ParticleSource.vector3(node_props.get("Max"), Vector3.INF)
		elif _canonical(node_path) == _canonical(rotation_rate_distribution):
			orbit_rotation_rate_max = ParticleSource.vector3(node_props.get("Max"), Vector3.INF)

	var emitter_info_raw: Variant = gpu_props.get("EmitterInfo", {})
	var emitter_info := emitter_info_raw as Dictionary if emitter_info_raw is Dictionary else {}
	var resource_data_raw: Variant = gpu_props.get("ResourceData", {})
	var resource_data := resource_data_raw as Dictionary if resource_data_raw is Dictionary else {}
	var gpu_inv_max_size := ParticleSource.vector2(emitter_info.get("InvMaxSize"), Vector2.INF)
	var gpu_inv_rotation_rate_scale := float(emitter_info.get("InvRotationRateScale", -1.0))
	var gpu_max_lifetime := float(emitter_info.get("MaxLifetime", -1.0))
	var gpu_max_particles := int(emitter_info.get("MaxParticleCount", -1))
	var gpu_screen_alignment := str(emitter_info.get("ScreenAlignment", ""))
	var gpu_rotation_rate_scale := float(resource_data.get("RotationRateScale", -1.0))
	var quantized_raw: Variant = resource_data.get("QuantizedColorSamples", [])
	var quantized_count := (quantized_raw as Array).size() if quantized_raw is Array else -1

	var peaks: Array[int] = []
	for node: Dictionary in lod_nodes:
		var lod_props := ParticleSource.properties(node)
		peaks.append(int(lod_props.get("PeakActiveParticles", -1)))
	peaks.sort()

	if _canonical(material_path) != _canonical(MYSTERY_INSIDE_MATERIAL):
		return {"ready": false, "error": "mystery inside material mismatch " + material_path}
	if screen_alignment != "PSA_Rectangle" or gpu_screen_alignment != "PSA_Rectangle":
		return {"ready": false, "error": "mystery inside screen alignment mismatch"}
	if random_image_time != 1 or legacy_emitter_time:
		return {"ready": false, "error": "mystery inside emitter timing flags mismatch"}
	if not is_equal_approx(life_min, 1.5) or not is_equal_approx(life_max, 3.0):
		return {"ready": false, "error": "mystery inside lifetime mismatch %s..%s" % [life_min, life_max]}
	if not location_min.is_equal_approx(Vector3(-20.0, -95.0, -10.0)) or not location_max.is_equal_approx(Vector3(20.0, 95.0, 10.0)):
		return {"ready": false, "error": "mystery inside location range mismatch"}
	if not size_min.is_equal_approx(Vector3(5.0, 5.0, 5.0)) or not size_max.is_equal_approx(Vector3(10.0, 10.0, 10.0)):
		return {"ready": false, "error": "mystery inside start size mismatch"}
	if not is_equal_approx(spawn_rate, 175.0) or not is_equal_approx(spawn_rate_max, 175.0):
		return {"ready": false, "error": "mystery inside spawn rate mismatch"}
	if not is_equal_approx(spawn_scale, 1.0) or not is_equal_approx(spawn_scale_max, 1.0):
		return {"ready": false, "error": "mystery inside spawn scale mismatch"}
	if not velocity_min.is_equal_approx(Vector3(0.0, 0.0, 45.0)) or not velocity_max.is_equal_approx(Vector3(0.0, 0.0, 50.0)):
		return {"ready": false, "error": "mystery inside velocity range mismatch"}
	if not rgb_min.is_equal_approx(Vector3.ONE) or not rgb_max.is_equal_approx(Vector3.ONE):
		return {"ready": false, "error": "mystery inside color range mismatch"}
	if rgb_values.size() != 3 or alpha_values.size() != 2:
		return {"ready": false, "error": "mystery inside color table mismatch rgb=%d alpha=%d" % [rgb_values.size(), alpha_values.size()]}
	if orbit_enabled:
		return {"ready": false, "error": "mystery inside orbit unexpectedly enabled"}
	if not orbit_offset_min.is_equal_approx(Vector3(0.0, 10.0, 0.0)) or not orbit_offset_max.is_equal_approx(Vector3(0.0, 25.0, 0.0)):
		return {"ready": false, "error": "mystery inside orbit offset authority mismatch"}
	if not orbit_rotation_max.is_equal_approx(Vector3.ONE) or not orbit_rotation_rate_max.is_equal_approx(Vector3.ONE):
		return {"ready": false, "error": "mystery inside orbit rotation authority mismatch"}
	if not gpu_inv_max_size.is_equal_approx(Vector2(0.1, 0.1)):
		return {"ready": false, "error": "mystery inside GPU inv max size mismatch"}
	if not is_equal_approx(gpu_inv_rotation_rate_scale, 0.33333334):
		return {"ready": false, "error": "mystery inside GPU rotation scale mismatch"}
	if not is_equal_approx(gpu_max_lifetime, 3.0) or gpu_max_particles != 531:
		return {"ready": false, "error": "mystery inside GPU lifetime/particle count mismatch"}
	if not is_equal_approx(gpu_rotation_rate_scale, 3.0) or quantized_count != 16:
		return {"ready": false, "error": "mystery inside GPU resource data mismatch"}
	if peaks != [531, 531]:
		return {"ready": false, "error": "mystery inside LOD peaks mismatch " + str(peaks)}

	return {
		"ready": true,
		"systemPath": MYSTERY_INSIDE_SYSTEM,
		"materialPath": material_path,
		"screenAlignment": screen_alignment,
		"lifetimeMin": life_min,
		"lifetimeMax": life_max,
		"startLocationMinUEcm": location_min,
		"startLocationMaxUEcm": location_max,
		"startSizeMinUEcm": size_min,
		"startSizeMaxUEcm": size_max,
		"spawnRate": spawn_rate,
		"startVelocityMinUEcm": velocity_min,
		"startVelocityMaxUEcm": velocity_max,
		"rgbTableValueCount": rgb_values.size(),
		"alphaTableValueCount": alpha_values.size(),
		"orbitEnabled": orbit_enabled,
		"orbitOffsetMin": orbit_offset_min,
		"orbitOffsetMax": orbit_offset_max,
		"gpuInvMaxSize": gpu_inv_max_size,
		"gpuInvRotationRateScale": gpu_inv_rotation_rate_scale,
		"gpuMaxLifetime": gpu_max_lifetime,
		"gpuMaxParticleCount": gpu_max_particles,
		"gpuRotationRateScale": gpu_rotation_rate_scale,
		"gpuQuantizedColorSampleCount": quantized_count,
		"peakActiveByLOD": peaks,
		"sourceNodeCount": int(system.get("nodeCount", 0)),
		"sourceReferenceCount": int(system.get("referenceCount", 0)),
	}


static func big_fire_vg_smk_descriptor(graphs: Dictionary) -> Dictionary:
	var system := _find_system(graphs, BIG_FIRE_VG_SMK_SYSTEM)
	if system.is_empty():
		return {"ready": false, "error": "big fire vg smoke source system missing"}
	if int(system.get("nodeCount", -1)) != 19:
		return {"ready": false, "error": "big fire vg smoke node count mismatch %d" % int(system.get("nodeCount", -1))}
	if int(system.get("referenceCount", -1)) != 7:
		return {"ready": false, "error": "big fire vg smoke reference count mismatch %d" % int(system.get("referenceCount", -1))}

	var required := _one_node(system, "ParticleModuleRequired")
	var lifetime := _one_node(system, "ParticleModuleLifetime")
	var cylinder := _one_node(system, "ParticleModuleLocationPrimitiveCylinder")
	var orientation := _one_node(system, "ParticleModuleOrientationAxisLock")
	var pivot := _one_node(system, "ParticleModulePivotOffset")
	var size_life := _one_node(system, "ParticleModuleSizeMultiplyLife")
	var size_speed := _one_node(system, "ParticleModuleSizeScaleBySpeed")
	var size := _one_node(system, "ParticleModuleSize")
	var subuv_movie := _one_node(system, "ParticleModuleSubUVMovie")
	var subuv_curve := _one_node(system, "DistributionFloatConstantCurve")
	var velocity := _one_node(system, "ParticleModuleVelocity")
	var color := _one_node(system, "ParticleModuleColorOverLife")
	var spawn_nodes := ParticleSource.nodes_by_type(system, "ParticleModuleSpawn")
	var lod_nodes := ParticleSource.nodes_by_type(system, "ParticleLODLevel")

	for pair: Array in [
		["ParticleModuleRequired", required],
		["ParticleModuleLifetime", lifetime],
		["ParticleModuleLocationPrimitiveCylinder", cylinder],
		["ParticleModuleOrientationAxisLock", orientation],
		["ParticleModulePivotOffset", pivot],
		["ParticleModuleSizeMultiplyLife", size_life],
		["ParticleModuleSizeScaleBySpeed", size_speed],
		["ParticleModuleSize", size],
		["ParticleModuleSubUVMovie", subuv_movie],
		["DistributionFloatConstantCurve", subuv_curve],
		["ParticleModuleVelocity", velocity],
		["ParticleModuleColorOverLife", color],
	]:
		if (pair[1] as Dictionary).is_empty():
			return {"ready": false, "error": "big fire vg smoke missing or duplicate " + str(pair[0])}
	if spawn_nodes.size() != 2:
		return {"ready": false, "error": "big fire vg smoke spawn LOD count mismatch %d" % spawn_nodes.size()}
	if lod_nodes.size() != 2:
		return {"ready": false, "error": "big fire vg smoke LOD count mismatch %d" % lod_nodes.size()}

	var required_props := ParticleSource.properties(required)
	var lifetime_props := ParticleSource.properties(lifetime)
	var cylinder_props := ParticleSource.properties(cylinder)
	var orientation_props := ParticleSource.properties(orientation)
	var pivot_props := ParticleSource.properties(pivot)
	var size_life_props := ParticleSource.properties(size_life)
	var size_speed_props := ParticleSource.properties(size_speed)
	var size_props := ParticleSource.properties(size)
	var subuv_props := ParticleSource.properties(subuv_movie)
	var velocity_props := ParticleSource.properties(velocity)
	var color_props := ParticleSource.properties(color)

	var material_path := str(required_props.get("Material", ""))
	var screen_alignment := str(required_props.get("ScreenAlignment", ""))
	var interpolation := str(required_props.get("InterpolationMethod", ""))
	var subimages_h := int(required_props.get("SubImages_Horizontal", -1))
	var subimages_v := int(required_props.get("SubImages_Vertical", -1))
	var random_image_time := int(required_props.get("RandomImageTime", -1))
	var legacy_emitter_time := bool(required_props.get("bUseLegacyEmitterTime", true))

	var life := _distribution(lifetime_props.get("Lifetime"))
	var radius := _distribution(cylinder_props.get("StartRadius"))
	var height := _distribution(cylinder_props.get("StartHeight"))
	var life_multiplier := _distribution(size_life_props.get("LifeMultiplier"))
	var start_size := _distribution(size_props.get("StartSize"))
	var frame_rate := _distribution(subuv_props.get("FrameRate"))
	var subimage_index := _distribution(subuv_props.get("SubImageIndex"))
	var start_velocity := _distribution(velocity_props.get("StartVelocity"))
	var rgb := _distribution(color_props.get("ColorOverLife"))
	var alpha := _distribution(color_props.get("AlphaOverLife"))

	var life_min := float(life.get("MinValue", -1.0))
	var life_max := float(life.get("MaxValue", -1.0))
	var radius_min := float(radius.get("MinValue", -1.0))
	var radius_max := float(radius.get("MaxValue", -1.0))
	var height_min := float(height.get("MinValue", 0.0))
	var height_max := float(height.get("MaxValue", 0.0))
	var pivot_offset := ParticleSource.vector2(pivot_props.get("PivotOffset"), Vector2.INF)
	var life_multiplier_min := _vector_from_distribution(life_multiplier, "MinValueVec", Vector3.INF)
	var life_multiplier_max := _vector_from_distribution(life_multiplier, "MaxValueVec", Vector3.INF)
	var speed_scale := ParticleSource.vector2(size_speed_props.get("SpeedScale"), Vector2.INF)
	var max_scale := ParticleSource.vector2(size_speed_props.get("MaxScale"), Vector2.INF)
	var size_min := _vector_from_distribution(start_size, "MinValueVec", Vector3.INF)
	var size_max := _vector_from_distribution(start_size, "MaxValueVec", Vector3.INF)
	var subuv_fps_min := float(frame_rate.get("MinValue", -1.0))
	var subuv_fps_max := float(frame_rate.get("MaxValue", -1.0))
	var subuv_curve_path := str(subimage_index.get("Distribution", ""))
	var velocity_min := _vector_from_distribution(start_velocity, "MinValueVec", Vector3.INF)
	var velocity_max := _vector_from_distribution(start_velocity, "MaxValueVec", Vector3.INF)
	var rgb_min := _vector_from_distribution(rgb, "MinValueVec", Vector3.INF)
	var rgb_max := _vector_from_distribution(rgb, "MaxValueVec", Vector3.INF)
	var rgb_values := ParticleSource.table_values(rgb)
	var alpha_values := ParticleSource.table_values(alpha)
	var lock_axis := str(orientation_props.get("LockAxisFlags", ""))

	var spawn_rates: Array[float] = []
	for node: Dictionary in spawn_nodes:
		var p := ParticleSource.properties(node)
		var rate := _distribution(p.get("Rate"))
		var rate_scale := _distribution(p.get("RateScale"))
		var lo := float(rate.get("MinValue", -1.0))
		var hi := float(rate.get("MaxValue", -1.0))
		if not is_equal_approx(lo, hi):
			return {"ready": false, "error": "big fire vg smoke non-constant LOD rate"}
		if not is_equal_approx(float(rate_scale.get("MinValue", -1.0)), 1.0):
			return {"ready": false, "error": "big fire vg smoke rate scale mismatch"}
		spawn_rates.append(lo)
	spawn_rates.sort()

	var peaks: Array[int] = []
	for node: Dictionary in lod_nodes:
		var p := ParticleSource.properties(node)
		peaks.append(int(p.get("PeakActiveParticles", -1)))
	peaks.sort()

	if _canonical(material_path) != _canonical(BIG_FIRE_VG_SMK_MATERIAL):
		return {"ready": false, "error": "big fire vg smoke material mismatch " + material_path}
	if screen_alignment != "PSA_Rectangle":
		return {"ready": false, "error": "big fire vg smoke screen alignment mismatch " + screen_alignment}
	if interpolation != "PSUVIM_Linear_Blend":
		return {"ready": false, "error": "big fire vg smoke interpolation mismatch " + interpolation}
	if subimages_h != 8 or subimages_v != 8:
		return {"ready": false, "error": "big fire vg smoke SubUV grid mismatch %dx%d" % [subimages_h, subimages_v]}
	if random_image_time != 1 or legacy_emitter_time:
		return {"ready": false, "error": "big fire vg smoke emitter timing flags mismatch"}
	if lock_axis != "EPAL_ROTATE_Z":
		return {"ready": false, "error": "big fire vg smoke axis lock mismatch " + lock_axis}
	if not is_equal_approx(life_min, 3.0) or not is_equal_approx(life_max, 5.0):
		return {"ready": false, "error": "big fire vg smoke lifetime mismatch %s..%s" % [life_min, life_max]}
	if not is_equal_approx(radius_min, 100.0) or not is_equal_approx(radius_max, 100.0):
		return {"ready": false, "error": "big fire vg smoke cylinder radius mismatch"}
	if not is_equal_approx(height_min, 0.0) or not is_equal_approx(height_max, 0.0):
		return {"ready": false, "error": "big fire vg smoke cylinder height mismatch"}
	if not pivot_offset.is_equal_approx(Vector2(0.0, -0.5)):
		return {"ready": false, "error": "big fire vg smoke pivot mismatch " + str(pivot_offset)}
	if not life_multiplier_min.is_equal_approx(Vector3(6.0, 6.0, 0.0)):
		return {"ready": false, "error": "big fire vg smoke life multiplier min mismatch " + str(life_multiplier_min)}
	if not life_multiplier_max.is_equal_approx(Vector3(7.0, 8.0, 0.0)):
		return {"ready": false, "error": "big fire vg smoke life multiplier max mismatch " + str(life_multiplier_max)}
	if ParticleSource.table_values(life_multiplier).size() != 6:
		return {"ready": false, "error": "big fire vg smoke life multiplier table mismatch"}
	if not speed_scale.is_equal_approx(Vector2(1.0, 2.0)) or not max_scale.is_equal_approx(Vector2(10.0, 50.0)):
		return {"ready": false, "error": "big fire vg smoke speed scale mismatch"}
	if not size_min.is_equal_approx(Vector3(20.0, 10.0, 0.0)):
		return {"ready": false, "error": "big fire vg smoke start size min mismatch " + str(size_min)}
	if not size_max.is_equal_approx(Vector3(15.0, 6.0, 0.0)):
		return {"ready": false, "error": "big fire vg smoke start size max mismatch " + str(size_max)}
	if not is_equal_approx(subuv_fps_min, 45.0) or not is_equal_approx(subuv_fps_max, 45.0):
		return {"ready": false, "error": "big fire vg smoke SubUV frame rate mismatch"}
	if _canonical(subuv_curve_path) != _canonical(str(subuv_curve.get("objectPath", ""))):
		return {"ready": false, "error": "big fire vg smoke SubUV curve reference mismatch " + subuv_curve_path}
	if not velocity_min.is_equal_approx(Vector3(-10.0, -10.0, 1.0)):
		return {"ready": false, "error": "big fire vg smoke velocity min mismatch " + str(velocity_min)}
	if not velocity_max.is_equal_approx(Vector3(10.0, 10.0, 5.0)):
		return {"ready": false, "error": "big fire vg smoke velocity max mismatch " + str(velocity_max)}
	if not rgb_min.is_equal_approx(Vector3(10.0, 5.0, 2.0)) or not rgb_max.is_equal_approx(Vector3(10.0, 5.0, 2.0)):
		return {"ready": false, "error": "big fire vg smoke color mismatch"}
	if rgb_values.size() != 3 or alpha_values.size() != 16:
		return {"ready": false, "error": "big fire vg smoke color table mismatch rgb=%d alpha=%d" % [rgb_values.size(), alpha_values.size()]}
	if spawn_rates.size() != 2 or not is_equal_approx(spawn_rates[0], 0.29999998) or not is_equal_approx(spawn_rates[1], 3.0):
		return {"ready": false, "error": "big fire vg smoke LOD spawn rate mismatch " + str(spawn_rates)}
	if peaks != [7, 17]:
		return {"ready": false, "error": "big fire vg smoke LOD peaks mismatch " + str(peaks)}

	return {
		"ready": true,
		"systemPath": BIG_FIRE_VG_SMK_SYSTEM,
		"materialPath": material_path,
		"lifetimeMin": life_min,
		"lifetimeMax": life_max,
		"cylinderRadiusUEcm": radius_min,
		"pivotOffset": pivot_offset,
		"lifeMultiplierMin": life_multiplier_min,
		"lifeMultiplierMax": life_multiplier_max,
		"speedScale": speed_scale,
		"maxScale": max_scale,
		"startSizeMinUEcm": size_min,
		"startSizeMaxUEcm": size_max,
		"subUVFrameRate": subuv_fps_min,
		"subUVCurvePath": subuv_curve_path,
		"startVelocityMinUEcm": velocity_min,
		"startVelocityMaxUEcm": velocity_max,
		"rgbTableValueCount": rgb_values.size(),
		"alphaTableValueCount": alpha_values.size(),
		"spawnRatesByLOD": spawn_rates,
		"peakActiveByLOD": peaks,
		"sourceNodeCount": int(system.get("nodeCount", 0)),
		"sourceReferenceCount": int(system.get("referenceCount", 0)),
	}


static func pap_wheel_out_descriptor(graphs: Dictionary) -> Dictionary:
	var system := _find_system(graphs, PAP_WHEEL_OUT_SYSTEM)
	if system.is_empty():
		return {"ready": false, "error": "PaP wheel out source system missing"}
	if int(system.get("nodeCount", -1)) != 16:
		return {"ready": false, "error": "PaP wheel out node count mismatch %d" % int(system.get("nodeCount", -1))}
	if int(system.get("referenceCount", -1)) != 4:
		return {"ready": false, "error": "PaP wheel out reference count mismatch %d" % int(system.get("referenceCount", -1))}

	var required := _one_node(system, "ParticleModuleRequired")
	var lifetime := _one_node(system, "ParticleModuleLifetime")
	var location := _one_node(system, "ParticleModuleLocation")
	var size := _one_node(system, "ParticleModuleSize")
	var size_life := _one_node(system, "ParticleModuleSizeMultiplyLife")
	var velocity := _one_node(system, "ParticleModuleVelocity")
	var velocity_life := _one_node(system, "ParticleModuleVelocityOverLifetime")
	var acceleration := _one_node(system, "ParticleModuleAcceleration")
	var rotation := _one_node(system, "ParticleModuleRotation")
	var rotation_rate := _one_node(system, "ParticleModuleRotationRate")
	var start_color := _one_node(system, "ParticleModuleColor")
	var color_life := _one_node(system, "ParticleModuleColorOverLife")
	var spawn := _one_node(system, "ParticleModuleSpawn")
	var lod := _one_node(system, "ParticleLODLevel")
	for pair: Array in [
		["ParticleModuleRequired", required],
		["ParticleModuleLifetime", lifetime],
		["ParticleModuleLocation", location],
		["ParticleModuleSize", size],
		["ParticleModuleSizeMultiplyLife", size_life],
		["ParticleModuleVelocity", velocity],
		["ParticleModuleVelocityOverLifetime", velocity_life],
		["ParticleModuleAcceleration", acceleration],
		["ParticleModuleRotation", rotation],
		["ParticleModuleRotationRate", rotation_rate],
		["ParticleModuleColor", start_color],
		["ParticleModuleColorOverLife", color_life],
		["ParticleModuleSpawn", spawn],
		["ParticleLODLevel", lod],
	]:
		if (pair[1] as Dictionary).is_empty():
			return {"ready": false, "error": "PaP wheel out missing or duplicate " + str(pair[0])}

	var required_props := ParticleSource.properties(required)
	var lifetime_props := ParticleSource.properties(lifetime)
	var location_props := ParticleSource.properties(location)
	var size_props := ParticleSource.properties(size)
	var size_life_props := ParticleSource.properties(size_life)
	var velocity_props := ParticleSource.properties(velocity)
	var velocity_life_props := ParticleSource.properties(velocity_life)
	var acceleration_props := ParticleSource.properties(acceleration)
	var rotation_props := ParticleSource.properties(rotation)
	var rotation_rate_props := ParticleSource.properties(rotation_rate)
	var start_color_props := ParticleSource.properties(start_color)
	var color_life_props := ParticleSource.properties(color_life)
	var spawn_props := ParticleSource.properties(spawn)
	var lod_props := ParticleSource.properties(lod)

	var material_path := str(required_props.get("Material", ""))
	var emitter_duration := float(required_props.get("EmitterDuration", -1.0))
	var emitter_loops := int(required_props.get("EmitterLoops", -1))
	var random_image_time := int(required_props.get("RandomImageTime", -1))
	var legacy_emitter_time := bool(required_props.get("bUseLegacyEmitterTime", true))

	var life := _distribution(lifetime_props.get("Lifetime"))
	var start_location := _distribution(location_props.get("StartLocation"))
	var start_size := _distribution(size_props.get("StartSize"))
	var life_multiplier := _distribution(size_life_props.get("LifeMultiplier"))
	var start_velocity := _distribution(velocity_props.get("StartVelocity"))
	var velocity_over_life := _distribution(velocity_life_props.get("VelOverLife"))
	var accel := _distribution(acceleration_props.get("Acceleration"))
	var start_rotation := _distribution(rotation_props.get("StartRotation"))
	var start_rotation_rate := _distribution(rotation_rate_props.get("StartRotationRate"))
	var color_start := _distribution(start_color_props.get("StartColor"))
	var alpha_start := _distribution(start_color_props.get("StartAlpha"))
	var color_over_life := _distribution(color_life_props.get("ColorOverLife"))
	var alpha_over_life := _distribution(color_life_props.get("AlphaOverLife"))
	var rate := _distribution(spawn_props.get("Rate"))
	var rate_scale := _distribution(spawn_props.get("RateScale"))

	var life_min := float(life.get("MinValue", -1.0))
	var life_max := float(life.get("MaxValue", -1.0))
	var location_min := _vector_from_distribution(start_location, "MinValueVec", Vector3.INF)
	var location_max := _vector_from_distribution(start_location, "MaxValueVec", Vector3.INF)
	var size_min := _vector_from_distribution(start_size, "MinValueVec", Vector3.INF)
	var size_max := _vector_from_distribution(start_size, "MaxValueVec", Vector3.INF)
	var velocity_min := _vector_from_distribution(start_velocity, "MinValueVec", Vector3.INF)
	var velocity_max := _vector_from_distribution(start_velocity, "MaxValueVec", Vector3.INF)
	var velocity_life_max := _vector_from_distribution(velocity_over_life, "MaxValueVec", Vector3.INF)
	var accel_min := _vector_from_distribution(accel, "MinValueVec", Vector3.INF)
	var accel_max := _vector_from_distribution(accel, "MaxValueVec", Vector3.INF)
	var start_color_min := _vector_from_distribution(color_start, "MinValueVec", Vector3.INF)
	var start_color_max := _vector_from_distribution(color_start, "MaxValueVec", Vector3.INF)

	var life_multiplier_values := ParticleSource.table_values(life_multiplier)
	var velocity_life_values := ParticleSource.table_values(velocity_over_life)
	var color_life_values := ParticleSource.table_values(color_over_life)
	var alpha_life_values := ParticleSource.table_values(alpha_over_life)
	var rotation_values := ParticleSource.table_values(start_rotation)

	var velocity_life_table_raw: Variant = velocity_over_life.get("Table", {})
	var velocity_life_table := velocity_life_table_raw as Dictionary if velocity_life_table_raw is Dictionary else {}
	var velocity_life_time_scale := float(velocity_life_table.get("TimeScale", -1.0))
	var life_table_raw: Variant = life_multiplier.get("Table", {})
	var life_table := life_table_raw as Dictionary if life_table_raw is Dictionary else {}
	var life_time_scale := float(life_table.get("TimeScale", -1.0))

	var spawn_rate := float(rate.get("MinValue", -1.0))
	var spawn_rate_max := float(rate.get("MaxValue", -1.0))
	var spawn_scale := float(rate_scale.get("MinValue", -1.0))
	var spawn_scale_max := float(rate_scale.get("MaxValue", -1.0))
	var rotation_rate_min := float(start_rotation_rate.get("MinValue", 999.0))
	var rotation_rate_max := float(start_rotation_rate.get("MaxValue", -999.0))
	var rotation_max := float(start_rotation.get("MaxValue", -1.0))
	var start_alpha_min := float(alpha_start.get("MinValue", -1.0))
	var start_alpha_max := float(alpha_start.get("MaxValue", -1.0))
	var peak_active := int(lod_props.get("PeakActiveParticles", -1))
	var acceleration_world_space := bool(acceleration_props.get("bAlwaysInWorldSpace", false))

	if _canonical(material_path) != _canonical(PAP_WHEEL_OUT_MATERIAL):
		return {"ready": false, "error": "PaP wheel out material mismatch " + material_path}
	if not is_equal_approx(emitter_duration, 5.0) or emitter_loops != 1:
		return {"ready": false, "error": "PaP wheel out emitter duration/loops mismatch"}
	if random_image_time != 1 or legacy_emitter_time:
		return {"ready": false, "error": "PaP wheel out emitter timing flags mismatch"}
	if not is_equal_approx(life_min, 0.5) or not is_equal_approx(life_max, 1.5):
		return {"ready": false, "error": "PaP wheel out lifetime mismatch %s..%s" % [life_min, life_max]}
	if not location_min.is_equal_approx(Vector3(-50.0, -50.0, -10.0)) or not location_max.is_equal_approx(Vector3(50.0, 50.0, 10.0)):
		return {"ready": false, "error": "PaP wheel out location range mismatch"}
	if not size_min.is_equal_approx(Vector3(3.0, 3.0, 3.0)) or not size_max.is_equal_approx(Vector3(5.0, 5.0, 5.0)):
		return {"ready": false, "error": "PaP wheel out size range mismatch"}
	if life_multiplier_values.size() != 384 or not is_equal_approx(life_time_scale, 127.34587):
		return {"ready": false, "error": "PaP wheel out size-life table mismatch values=%d time=%s" % [life_multiplier_values.size(), life_time_scale]}
	if not velocity_min.is_equal_approx(Vector3(60.0, -5.0, -5.0)) or not velocity_max.is_equal_approx(Vector3(80.0, 5.0, 5.0)):
		return {"ready": false, "error": "PaP wheel out start velocity mismatch"}
	if not velocity_life_max.is_equal_approx(Vector3(1.0, 10.0, 10.0)):
		return {"ready": false, "error": "PaP wheel out velocity-over-life max mismatch " + str(velocity_life_max)}
	if velocity_life_values.size() != 6 or not is_equal_approx(velocity_life_time_scale, 2.0):
		return {"ready": false, "error": "PaP wheel out velocity-over-life table mismatch"}
	if not accel_min.is_equal_approx(Vector3(0.0, 0.0, -10.0)) or not accel_max.is_equal_approx(Vector3(0.0, 0.0, -15.0)):
		return {"ready": false, "error": "PaP wheel out acceleration mismatch"}
	if not acceleration_world_space:
		return {"ready": false, "error": "PaP wheel out acceleration world-space flag mismatch"}
	if not is_equal_approx(rotation_rate_min, -0.1) or not is_equal_approx(rotation_rate_max, 0.2):
		return {"ready": false, "error": "PaP wheel out rotation rate mismatch"}
	if not is_equal_approx(rotation_max, 1.0) or rotation_values.size() != 2:
		return {"ready": false, "error": "PaP wheel out start rotation mismatch"}
	if not start_color_min.is_equal_approx(Vector3(0.786901, 0.890625, 0.844701)) or not start_color_max.is_equal_approx(Vector3.ONE):
		return {"ready": false, "error": "PaP wheel out start color mismatch"}
	if not is_equal_approx(start_alpha_min, 1.0) or not is_equal_approx(start_alpha_max, 1.0):
		return {"ready": false, "error": "PaP wheel out start alpha mismatch"}
	if color_life_values.size() != 6 or alpha_life_values.size() != 2:
		return {"ready": false, "error": "PaP wheel out color-over-life table mismatch"}
	if not is_equal_approx(spawn_rate, 15.0) or not is_equal_approx(spawn_rate_max, 15.0):
		return {"ready": false, "error": "PaP wheel out spawn rate mismatch"}
	if not is_equal_approx(spawn_scale, 15.0) or not is_equal_approx(spawn_scale_max, 15.0):
		return {"ready": false, "error": "PaP wheel out spawn rate scale mismatch"}
	if peak_active != 339:
		return {"ready": false, "error": "PaP wheel out peak active mismatch %d" % peak_active}

	return {
		"ready": true,
		"systemPath": PAP_WHEEL_OUT_SYSTEM,
		"materialPath": material_path,
		"emitterDuration": emitter_duration,
		"emitterLoops": emitter_loops,
		"lifetimeMin": life_min,
		"lifetimeMax": life_max,
		"startLocationMinUEcm": location_min,
		"startLocationMaxUEcm": location_max,
		"startSizeMinUEcm": size_min,
		"startSizeMaxUEcm": size_max,
		"sizeLifeTableValueCount": life_multiplier_values.size(),
		"sizeLifeTimeScale": life_time_scale,
		"startVelocityMinUEcm": velocity_min,
		"startVelocityMaxUEcm": velocity_max,
		"velocityOverLifeMax": velocity_life_max,
		"velocityOverLifeTableValueCount": velocity_life_values.size(),
		"velocityOverLifeTimeScale": velocity_life_time_scale,
		"accelerationMinUEcm": accel_min,
		"accelerationMaxUEcm": accel_max,
		"accelerationWorldSpace": acceleration_world_space,
		"rotationRateMin": rotation_rate_min,
		"rotationRateMax": rotation_rate_max,
		"spawnRate": spawn_rate,
		"spawnRateScale": spawn_scale,
		"peakActiveParticles": peak_active,
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
