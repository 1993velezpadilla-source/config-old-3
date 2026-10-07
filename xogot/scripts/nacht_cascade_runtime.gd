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
const ELECTRIC_BEAM_SYSTEM := "/Game/CustomMaps/UGC2755515831/Materials/ElectricTrap/ElectricBeam.ElectricBeam"
const ELECTRIC_BEAM_MATERIAL := "/Game/CustomMaps/UGC2755515831/Materials/KillerJim/DogSpawnEffects/lightning.lightning"
const ACID_BALL_SYSTEM := "/Game/CustomMaps/UGC2755515831/Magnum/Particles/Acid/AcidBall.AcidBall"
const ACID_BALL_SMOKE_MATERIAL := "/Game/CustomMaps/UGC2755515831/Magnum/Materials/Universal/SmokeyAcid.SmokeyAcid"
const ACID_BALL_MATERIAL := "/Game/CustomMaps/UGC2755515831/Magnum/Materials/Universal/AcidBall.AcidBall"
const ACID_BALL_MESH := "/Game/CustomMaps/UGC2755515831/Magnum/Meshes/Sphere.Sphere"
const SPARKS_SMALL_SYSTEM := "/Game/CustomMaps/UGC2755515831/CoD/Particles/sparks/sparksParticlesSmall.sparksParticlesSmall"
const SPARKS_SMALL_MATERIAL := "/Game/CustomMaps/UGC2755515831/CoD/Particles/Dust/Dust.Dust"
const QUAD_EXPLODE_SMOKE_SYSTEM := "/Game/CustomMaps/UGC2755515831/CoD/Particles/Quads/quadExplodeSmoke1.quadExplodeSmoke1"
const QUAD_EXPLODE_SMOKE_MATERIAL := "/Game/CustomMaps/UGC2755515831/CoD/Particles/Fire/Materials/Smoke_Inst/unlit_smoke.unlit_smoke"
const MONSTER_DEATH_XL_SYSTEM := "/Game/CustomMaps/UGC2755515831/InfinityBladeEffects/Effects/FX_Monsters/FX_Monster_Deaths/P_Monster_Death_XLarge.P_Monster_Death_XLarge"
const MONSTER_DEATH_MESH_1 := "/Game/CustomMaps/UGC2755515831/InfinityBladeEffects/Effects/FX_Meshes/Skills/SM_DeathPlane_01.SM_DeathPlane_01"
const MONSTER_DEATH_MESH_2 := "/Game/CustomMaps/UGC2755515831/InfinityBladeEffects/Effects/FX_Meshes/Skills/SM_FireBlastMesh_Twist_01.SM_FireBlastMesh_Twist_01"
const MONSTER_DEATH_MESH_MAT_1 := "/Game/CustomMaps/UGC2755515831/InfinityBladeEffects/Effects/FX_Materials/Misc/M_DeathPlane_01.M_DeathPlane_01"
const MONSTER_DEATH_MESH_MAT_2 := "/Game/CustomMaps/UGC2755515831/InfinityBladeEffects/Effects/FX_Materials/Fire/M_Fire_Sheet_01_INST.M_Fire_Sheet_01_INST"
const MONSTER_DEATH_ICE_MAT := "/Game/CustomMaps/UGC2755515831/InfinityBladeEffects/Effects/FX_Materials/ICE/M_IceBlastBase.M_IceBlastBase"
const MONSTER_DEATH_SMOKE_MAT := "/Game/CustomMaps/UGC2755515831/InfinityBladeEffects/Effects/FX_Materials/Smoke/M_Smoke_01_8X8_INST.M_Smoke_01_8X8_INST"
const MONSTER_DEATH_EMISSIVE_MAT := "/Engine/EngineMaterials/EmissiveTexturedMaterial.EmissiveTexturedMaterial"
const FIRE_00_SYSTEM := "/Game/CustomMaps/UGC2755515831/M5VFXVOL2/Particles/Fire/Fire_00.Fire_00"
const FIRE_00_MAT_BONE_FWD4 := "/Game/CustomMaps/UGC2755515831/M5VFXVOL2/Materials/Fire_Inst/BoneFire_fwd4_Inst.BoneFire_fwd4_Inst"
const FIRE_00_MAT_BONE3 := "/Game/CustomMaps/UGC2755515831/M5VFXVOL2/Materials/Fireloop_Inst/BoneFire3_Inst.BoneFire3_Inst"
const FIRE_00_MAT_DISTORT := "/Game/CustomMaps/UGC2755515831/M5VFXVOL2/Materials/Distortion/Distortion_Mat_Inst2.Distortion_Mat_Inst2"
const FIRE_00_MAT_FLAME := "/Game/CustomMaps/UGC2755515831/M5VFXVOL2/Materials/Etc/Flame_Inst.Flame_Inst"
const FIRE_00_MAT_SMOKE := "/Game/CustomMaps/UGC2755515831/M5VFXVOL2/Materials/Smoke_Inst/0_6_smoke_Inst.0_6_smoke_Inst"


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


static func _node_by_path(system: Dictionary, object_path: String) -> Dictionary:
	var wanted := _canonical(object_path)
	if wanted.is_empty():
		return {}
	for raw: Variant in system.get("nodes", []):
		if not (raw is Dictionary):
			continue
		var node := raw as Dictionary
		if _canonical(str(node.get("objectPath", ""))) == wanted:
			return node
	return {}


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


static func electric_beam_descriptor(graphs: Dictionary) -> Dictionary:
	var system := _find_system(graphs, ELECTRIC_BEAM_SYSTEM)
	if system.is_empty():
		return {"ready": false, "error": "electric beam source system missing"}
	if int(system.get("nodeCount", -1)) != 19:
		return {"ready": false, "error": "electric beam node count mismatch %d" % int(system.get("nodeCount", -1))}
	if int(system.get("referenceCount", -1)) != 12:
		return {"ready": false, "error": "electric beam reference count mismatch %d" % int(system.get("referenceCount", -1))}

	var required := _one_node(system, "ParticleModuleRequired")
	var lifetime := _one_node(system, "ParticleModuleLifetime")
	var size := _one_node(system, "ParticleModuleSize")
	var start_color := _one_node(system, "ParticleModuleColor")
	var spawn := _one_node(system, "ParticleModuleSpawn")
	var beam_noise := _one_node(system, "ParticleModuleBeamNoise")
	var beam_source := _one_node(system, "ParticleModuleBeamSource")
	var beam_target := _one_node(system, "ParticleModuleBeamTarget")
	var beam_type := _one_node(system, "ParticleModuleTypeDataBeam2")
	var lod := _one_node(system, "ParticleLODLevel")
	for pair: Array in [
		["ParticleModuleRequired", required],
		["ParticleModuleLifetime", lifetime],
		["ParticleModuleSize", size],
		["ParticleModuleColor", start_color],
		["ParticleModuleSpawn", spawn],
		["ParticleModuleBeamNoise", beam_noise],
		["ParticleModuleBeamSource", beam_source],
		["ParticleModuleBeamTarget", beam_target],
		["ParticleModuleTypeDataBeam2", beam_type],
		["ParticleLODLevel", lod],
	]:
		if (pair[1] as Dictionary).is_empty():
			return {"ready": false, "error": "electric beam missing or duplicate " + str(pair[0])}

	var required_props := ParticleSource.properties(required)
	var lifetime_props := ParticleSource.properties(lifetime)
	var size_props := ParticleSource.properties(size)
	var start_color_props := ParticleSource.properties(start_color)
	var spawn_props := ParticleSource.properties(spawn)
	var noise_props := ParticleSource.properties(beam_noise)
	var source_props := ParticleSource.properties(beam_source)
	var target_props := ParticleSource.properties(beam_target)
	var beam_props := ParticleSource.properties(beam_type)
	var lod_props := ParticleSource.properties(lod)

	var material_path := str(required_props.get("Material", ""))
	var random_image_time := int(required_props.get("RandomImageTime", -1))
	var legacy_emitter_time := bool(required_props.get("bUseLegacyEmitterTime", true))
	var life := _distribution(lifetime_props.get("Lifetime"))
	var start_size := _distribution(size_props.get("StartSize"))
	var start_rgb := _distribution(start_color_props.get("StartColor"))
	var start_alpha := _distribution(start_color_props.get("StartAlpha"))
	var rate := _distribution(spawn_props.get("Rate"))
	var rate_scale := _distribution(spawn_props.get("RateScale"))

	var noise_range := _distribution(noise_props.get("NoiseRange"))
	var noise_range_scale := _distribution(noise_props.get("NoiseRangeScale"))
	var noise_scale := _distribution(noise_props.get("NoiseScale"))
	var noise_speed := _distribution(noise_props.get("NoiseSpeed"))
	var noise_tangent_strength := _distribution(noise_props.get("NoiseTangentStrength"))

	var source_dist := _distribution(source_props.get("Source"))
	var source_strength := _distribution(source_props.get("SourceStrength"))
	var source_tangent_dist := _distribution(source_props.get("SourceTangent"))
	var target_dist := _distribution(target_props.get("Target"))
	var target_strength := _distribution(target_props.get("TargetStrength"))
	var target_tangent_dist := _distribution(target_props.get("TargetTangent"))

	var distance_dist := _distribution(beam_props.get("Distance"))
	var taper_factor_dist := _distribution(beam_props.get("TaperFactor"))
	var taper_scale_dist := _distribution(beam_props.get("TaperScale"))

	var noise_scale_path := str(noise_scale.get("Distribution", ""))
	var source_tangent_path := str(source_tangent_dist.get("Distribution", ""))
	var target_tangent_path := str(target_tangent_dist.get("Distribution", ""))
	var distance_path := str(distance_dist.get("Distribution", ""))
	var taper_factor_path := str(taper_factor_dist.get("Distribution", ""))
	var taper_scale_path := str(taper_scale_dist.get("Distribution", ""))

	var noise_scale_node := _node_by_path(system, noise_scale_path)
	var source_tangent_node := _node_by_path(system, source_tangent_path)
	var target_tangent_node := _node_by_path(system, target_tangent_path)
	var distance_node := _node_by_path(system, distance_path)
	var taper_factor_node := _node_by_path(system, taper_factor_path)
	var taper_scale_node := _node_by_path(system, taper_scale_path)
	for pair: Array in [
		["NoiseScale", noise_scale_node],
		["SourceTangent", source_tangent_node],
		["TargetTangent", target_tangent_node],
		["Distance", distance_node],
		["TaperFactor", taper_factor_node],
		["TaperScale", taper_scale_node],
	]:
		if (pair[1] as Dictionary).is_empty():
			return {"ready": false, "error": "electric beam distribution node missing " + str(pair[0])}

	var source_tangent_props := ParticleSource.properties(source_tangent_node)
	var target_tangent_props := ParticleSource.properties(target_tangent_node)
	var distance_props := ParticleSource.properties(distance_node)
	var taper_factor_props := ParticleSource.properties(taper_factor_node)
	var taper_scale_props := ParticleSource.properties(taper_scale_node)

	var life_min := float(life.get("MinValue", -1.0))
	var life_max := float(life.get("MaxValue", -1.0))
	var size_min := _vector_from_distribution(start_size, "MinValueVec", Vector3.INF)
	var size_max := _vector_from_distribution(start_size, "MaxValueVec", Vector3.INF)
	var color_min := _vector_from_distribution(start_rgb, "MinValueVec", Vector3.INF)
	var color_max := _vector_from_distribution(start_rgb, "MaxValueVec", Vector3.INF)
	var alpha_min := float(start_alpha.get("MinValue", -1.0))
	var alpha_max := float(start_alpha.get("MaxValue", -1.0))
	var spawn_rate := float(rate.get("MinValue", -1.0))
	var spawn_rate_max := float(rate.get("MaxValue", -1.0))
	var spawn_scale := float(rate_scale.get("MinValue", -1.0))
	var spawn_scale_max := float(rate_scale.get("MaxValue", -1.0))

	var noise_frequency := int(noise_props.get("Frequency", -1))
	var noise_lock_time := float(noise_props.get("NoiseLockTime", -1.0))
	var noise_range_max := _vector_from_distribution(noise_range, "MaxValueVec", Vector3.INF)
	var noise_range_scale_min := float(noise_range_scale.get("MinValue", -1.0))
	var noise_range_scale_max := float(noise_range_scale.get("MaxValue", -1.0))
	var noise_speed_min := _vector_from_distribution(noise_speed, "MinValueVec", Vector3.INF)
	var noise_speed_max := _vector_from_distribution(noise_speed, "MaxValueVec", Vector3.INF)
	var noise_tangent_min := float(noise_tangent_strength.get("MinValue", -1.0))
	var noise_tangent_max := float(noise_tangent_strength.get("MaxValue", -1.0))
	var low_freq_enabled := bool(noise_props.get("bLowFreq_Enabled", false))

	var source_values := ParticleSource.table_values(source_dist)
	var source_strength_min := float(source_strength.get("MinValue", -1.0))
	var source_strength_max := float(source_strength.get("MaxValue", -1.0))
	var source_tangent := ParticleSource.vector3(source_tangent_props.get("Constant"), Vector3.INF)
	var target_min := _vector_from_distribution(target_dist, "MinValueVec", Vector3.INF)
	var target_max := _vector_from_distribution(target_dist, "MaxValueVec", Vector3.INF)
	var target_strength_min := float(target_strength.get("MinValue", -1.0))
	var target_strength_max := float(target_strength.get("MaxValue", -1.0))
	var target_tangent := ParticleSource.vector3(target_tangent_props.get("Constant"), Vector3.INF)

	var distance := float(distance_props.get("Constant", -1.0))
	var taper_factor := float(taper_factor_props.get("Constant", -1.0))
	var taper_scale := float(taper_scale_props.get("Constant", -1.0))
	var interpolation_points := int(beam_props.get("InterpolationPoints", -1))
	var max_beam_count := int(beam_props.get("MaxBeamCount", -1))
	var beam_speed := float(beam_props.get("Speed", -1.0))
	var peak_active := int(lod_props.get("PeakActiveParticles", -1))

	if _canonical(material_path) != _canonical(ELECTRIC_BEAM_MATERIAL):
		return {"ready": false, "error": "electric beam material mismatch " + material_path}
	if random_image_time != 1 or legacy_emitter_time:
		return {"ready": false, "error": "electric beam emitter timing flags mismatch"}
	if not is_equal_approx(life_min, 1.0) or not is_equal_approx(life_max, 1.0):
		return {"ready": false, "error": "electric beam lifetime mismatch"}
	if not size_min.is_equal_approx(Vector3(25.0, 25.0, 25.0)) or not size_max.is_equal_approx(Vector3(25.0, 25.0, 25.0)):
		return {"ready": false, "error": "electric beam size mismatch"}
	if not color_min.is_equal_approx(Vector3(0.676412, 0.821064, 1.0)) or not color_max.is_equal_approx(Vector3(0.676412, 0.821064, 1.0)):
		return {"ready": false, "error": "electric beam start color mismatch"}
	if not is_equal_approx(alpha_min, 1.0) or not is_equal_approx(alpha_max, 1.0):
		return {"ready": false, "error": "electric beam alpha mismatch"}
	if not is_equal_approx(spawn_rate, 20.0) or not is_equal_approx(spawn_rate_max, 20.0):
		return {"ready": false, "error": "electric beam spawn rate mismatch"}
	if not is_equal_approx(spawn_scale, 1.0) or not is_equal_approx(spawn_scale_max, 1.0):
		return {"ready": false, "error": "electric beam spawn scale mismatch"}

	if noise_frequency != 5 or not is_equal_approx(noise_lock_time, 0.025) or not low_freq_enabled:
		return {"ready": false, "error": "electric beam noise frequency/lock flags mismatch"}
	if not noise_range_max.is_equal_approx(Vector3(30.0, 30.0, 20.0)):
		return {"ready": false, "error": "electric beam noise range mismatch " + str(noise_range_max)}
	if not is_equal_approx(noise_range_scale_min, 1.0) or not is_equal_approx(noise_range_scale_max, 1.0):
		return {"ready": false, "error": "electric beam noise range scale mismatch"}
	if not noise_speed_min.is_equal_approx(Vector3(50.0, 50.0, 50.0)) or not noise_speed_max.is_equal_approx(Vector3(50.0, 50.0, 50.0)):
		return {"ready": false, "error": "electric beam noise speed mismatch"}
	if not is_equal_approx(noise_tangent_min, 250.0) or not is_equal_approx(noise_tangent_max, 250.0):
		return {"ready": false, "error": "electric beam noise tangent strength mismatch"}
	# The cooked NoiseScale constant-curve export is present but contains no
	# authored keys. Preserve that exact source limitation; do not synthesize
	# curve values in Godot.
	if not ParticleSource.properties(noise_scale_node).is_empty():
		return {"ready": false, "error": "electric beam NoiseScale curve unexpectedly changed"}

	if source_values.size() != 3:
		return {"ready": false, "error": "electric beam source table value count mismatch %d" % source_values.size()}
	if not is_equal_approx(source_strength_min, 25.0) or not is_equal_approx(source_strength_max, 25.0):
		return {"ready": false, "error": "electric beam source strength mismatch"}
	if not source_tangent.is_equal_approx(Vector3(1.0, 0.0, 0.0)):
		return {"ready": false, "error": "electric beam source tangent mismatch " + str(source_tangent)}
	if not target_min.is_equal_approx(Vector3(0.0, 0.0, 280.0)) or not target_max.is_equal_approx(Vector3(0.0, 0.0, 280.0)):
		return {"ready": false, "error": "electric beam target mismatch"}
	if not is_equal_approx(target_strength_min, 25.0) or not is_equal_approx(target_strength_max, 25.0):
		return {"ready": false, "error": "electric beam target strength mismatch"}
	if not target_tangent.is_equal_approx(Vector3(1.0, 0.0, 0.0)):
		return {"ready": false, "error": "electric beam target tangent mismatch " + str(target_tangent)}

	if not is_equal_approx(distance, 25.0) or not is_equal_approx(taper_factor, 1.0) or not is_equal_approx(taper_scale, 1.0):
		return {"ready": false, "error": "electric beam Beam2 distribution constants mismatch"}
	if interpolation_points != 20 or max_beam_count != 1 or not is_equal_approx(beam_speed, 0.0):
		return {"ready": false, "error": "electric beam Beam2 settings mismatch"}
	if peak_active != 3:
		return {"ready": false, "error": "electric beam peak active mismatch %d" % peak_active}

	return {
		"ready": true,
		"systemPath": ELECTRIC_BEAM_SYSTEM,
		"materialPath": material_path,
		"lifetimeSeconds": life_min,
		"startSizeUEcm": size_min,
		"spawnRate": spawn_rate,
		"noiseFrequency": noise_frequency,
		"noiseLockTime": noise_lock_time,
		"noiseRangeMaxUEcm": noise_range_max,
		"noiseSpeedUEcm": noise_speed_min,
		"noiseTangentStrength": noise_tangent_min,
		"noiseScaleCurvePath": noise_scale_path,
		"sourceStrength": source_strength_min,
		"sourceTangent": source_tangent,
		"targetUEcm": target_min,
		"targetStrength": target_strength_min,
		"targetTangent": target_tangent,
		"beamDistance": distance,
		"interpolationPoints": interpolation_points,
		"maxBeamCount": max_beam_count,
		"beamSpeed": beam_speed,
		"taperFactor": taper_factor,
		"taperScale": taper_scale,
		"peakActiveParticles": peak_active,
		"sourceNodeCount": int(system.get("nodeCount", 0)),
		"sourceReferenceCount": int(system.get("referenceCount", 0)),
	}


static func acid_ball_descriptor(graphs: Dictionary) -> Dictionary:
	var system := _find_system(graphs, ACID_BALL_SYSTEM)
	if system.is_empty():
		return {"ready": false, "error": "AcidBall source system missing"}
	if int(system.get("nodeCount", -1)) != 20:
		return {"ready": false, "error": "AcidBall node count mismatch %d" % int(system.get("nodeCount", -1))}
	if int(system.get("referenceCount", -1)) != 11:
		return {"ready": false, "error": "AcidBall reference count mismatch %d" % int(system.get("referenceCount", -1))}

	var base := str(system.get("objectPath", ""))
	var required_mesh := _node_by_path(system, base + ":ParticleModuleRequired_0")
	var required_sprite := _node_by_path(system, base + ":ParticleModuleRequired_1")
	var spawn_mesh := _node_by_path(system, base + ":ParticleModuleSpawn_0")
	var spawn_sprite := _node_by_path(system, base + ":ParticleModuleSpawn_1")
	var size_mesh := _node_by_path(system, base + ":ParticleModuleSize_0")
	var size_sprite := _node_by_path(system, base + ":ParticleModuleSize_1")
	var lifetime_sprite := _one_node(system, "ParticleModuleLifetime")
	var size_life_sprite := _one_node(system, "ParticleModuleSizeMultiplyLife")
	var dynamic_sprite := _one_node(system, "ParticleModuleParameterDynamic")
	var rotation_sprite := _one_node(system, "ParticleModuleRotation")
	var color_sprite := _one_node(system, "ParticleModuleColor")
	var color_scale_sprite := _one_node(system, "ParticleModuleColorScaleOverLife")
	var color_mesh := _one_node(system, "ParticleModuleColorOverLife")
	var mesh_type := _one_node(system, "ParticleModuleTypeDataMesh")
	var lod_nodes := ParticleSource.nodes_by_type(system, "ParticleLODLevel")

	for pair: Array in [
		["required mesh", required_mesh],
		["required sprite", required_sprite],
		["spawn mesh", spawn_mesh],
		["spawn sprite", spawn_sprite],
		["size mesh", size_mesh],
		["size sprite", size_sprite],
		["lifetime sprite", lifetime_sprite],
		["size-life sprite", size_life_sprite],
		["dynamic sprite", dynamic_sprite],
		["rotation sprite", rotation_sprite],
		["color sprite", color_sprite],
		["color-scale sprite", color_scale_sprite],
		["color mesh", color_mesh],
		["mesh type", mesh_type],
	]:
		if (pair[1] as Dictionary).is_empty():
			return {"ready": false, "error": "AcidBall missing " + str(pair[0])}
	if lod_nodes.size() != 2:
		return {"ready": false, "error": "AcidBall LOD emitter count mismatch %d" % lod_nodes.size()}

	var mesh_required_props := ParticleSource.properties(required_mesh)
	var sprite_required_props := ParticleSource.properties(required_sprite)
	var mesh_spawn_props := ParticleSource.properties(spawn_mesh)
	var sprite_spawn_props := ParticleSource.properties(spawn_sprite)
	var mesh_size_props := ParticleSource.properties(size_mesh)
	var sprite_size_props := ParticleSource.properties(size_sprite)
	var lifetime_props := ParticleSource.properties(lifetime_sprite)
	var size_life_props := ParticleSource.properties(size_life_sprite)
	var dynamic_props := ParticleSource.properties(dynamic_sprite)
	var rotation_props := ParticleSource.properties(rotation_sprite)
	var color_props := ParticleSource.properties(color_sprite)
	var color_scale_props := ParticleSource.properties(color_scale_sprite)
	var mesh_color_props := ParticleSource.properties(color_mesh)
	var mesh_type_props := ParticleSource.properties(mesh_type)

	if _canonical(str(mesh_required_props.get("Material", ""))) != _canonical(ACID_BALL_SMOKE_MATERIAL):
		return {"ready": false, "error": "AcidBall mesh material mismatch"}
	if _canonical(str(sprite_required_props.get("Material", ""))) != _canonical(ACID_BALL_MATERIAL):
		return {"ready": false, "error": "AcidBall sprite material mismatch"}
	if not bool(mesh_required_props.get("bUseLocalSpace", false)):
		return {"ready": false, "error": "AcidBall mesh local-space flag mismatch"}
	if not bool(sprite_required_props.get("bUseLocalSpace", false)):
		return {"ready": false, "error": "AcidBall sprite local-space flag mismatch"}
	if bool(mesh_required_props.get("bUseLegacyEmitterTime", true)) or bool(sprite_required_props.get("bUseLegacyEmitterTime", true)):
		return {"ready": false, "error": "AcidBall legacy emitter time unexpectedly enabled"}
	if int(mesh_required_props.get("RandomImageTime", -1)) != 1 or int(sprite_required_props.get("RandomImageTime", -1)) != 1:
		return {"ready": false, "error": "AcidBall random image timing mismatch"}
	if int(mesh_required_props.get("EmitterLoops", -1)) != 1 or not bool(mesh_required_props.get("bKillOnDeactivate", false)):
		return {"ready": false, "error": "AcidBall mesh emitter lifecycle mismatch"}
	if not is_equal_approx(float(sprite_required_props.get("EmitterDelay", -1.0)), 0.5):
		return {"ready": false, "error": "AcidBall sprite emitter delay mismatch"}
	if not is_equal_approx(float(sprite_required_props.get("EmitterDuration", -1.0)), 0.5):
		return {"ready": false, "error": "AcidBall sprite emitter duration mismatch"}
	if not bool(sprite_required_props.get("bDelayFirstLoopOnly", false)):
		return {"ready": false, "error": "AcidBall sprite first-loop delay flag mismatch"}

	var mesh_spawn_rate := _distribution(mesh_spawn_props.get("Rate"))
	var mesh_rate_scale := _distribution(mesh_spawn_props.get("RateScale"))
	var sprite_spawn_rate := _distribution(sprite_spawn_props.get("Rate"))
	var sprite_rate_scale := _distribution(sprite_spawn_props.get("RateScale"))
	if ParticleSource.table_float_values(mesh_spawn_rate) != [0.0]:
		return {"ready": false, "error": "AcidBall mesh continuous spawn must be zero"}
	if not is_equal_approx(float(mesh_rate_scale.get("MinValue", -1.0)), 1.0):
		return {"ready": false, "error": "AcidBall mesh rate scale mismatch"}
	var mesh_bursts_raw: Variant = mesh_spawn_props.get("BurstList", [])
	if not (mesh_bursts_raw is Array) or (mesh_bursts_raw as Array).size() != 1:
		return {"ready": false, "error": "AcidBall mesh burst list mismatch"}
	var mesh_burst := (mesh_bursts_raw as Array)[0] as Dictionary
	if int(mesh_burst.get("Count", -1)) != 1 or int(mesh_burst.get("CountLow", 0)) != -1 or not is_equal_approx(float(mesh_burst.get("Time", -1.0)), 0.0):
		return {"ready": false, "error": "AcidBall mesh burst values mismatch " + str(mesh_burst)}
	if not is_equal_approx(float(sprite_spawn_rate.get("MinValue", -1.0)), 10.0) or not is_equal_approx(float(sprite_spawn_rate.get("MaxValue", -1.0)), 10.0):
		return {"ready": false, "error": "AcidBall sprite spawn rate mismatch"}
	if not is_equal_approx(float(sprite_rate_scale.get("MinValue", -1.0)), 1.0):
		return {"ready": false, "error": "AcidBall sprite rate scale mismatch"}
	if bool(sprite_spawn_props.get("bApplyGlobalSpawnRateScale", true)):
		return {"ready": false, "error": "AcidBall sprite global spawn scaling unexpectedly enabled"}

	var mesh_size := _distribution(mesh_size_props.get("StartSize"))
	var mesh_size_min := _vector_from_distribution(mesh_size, "MinValueVec", Vector3.INF)
	var mesh_size_max := _vector_from_distribution(mesh_size, "MaxValueVec", Vector3.INF)
	if not mesh_size_min.is_equal_approx(Vector3(0.5, 0.6, 0.5)) or not mesh_size_max.is_equal_approx(Vector3(0.5, 0.6, 0.5)):
		return {"ready": false, "error": "AcidBall mesh size mismatch"}

	var sprite_size := _distribution(sprite_size_props.get("StartSize"))
	var sprite_size_min := _vector_from_distribution(sprite_size, "MinValueVec", Vector3.INF)
	var sprite_size_max := _vector_from_distribution(sprite_size, "MaxValueVec", Vector3.INF)
	if not sprite_size_min.is_equal_approx(Vector3(5.0, 8.333333, 8.333333)) or not sprite_size_max.is_equal_approx(Vector3(6.666667, 8.333333, 8.333333)):
		return {"ready": false, "error": "AcidBall sprite size mismatch"}

	var lifetime := _distribution(lifetime_props.get("Lifetime"))
	var lifetime_min := float(lifetime.get("MinValue", -1.0))
	var lifetime_max := float(lifetime.get("MaxValue", -1.0))
	if not is_equal_approx(lifetime_min, 1.0) or not is_equal_approx(lifetime_max, 2.0):
		return {"ready": false, "error": "AcidBall sprite lifetime mismatch"}

	var life_multiplier := _distribution(size_life_props.get("LifeMultiplier"))
	var life_multiplier_min := _vector_from_distribution(life_multiplier, "MinValueVec", Vector3.INF)
	var life_multiplier_max := _vector_from_distribution(life_multiplier, "MaxValueVec", Vector3.INF)
	if not life_multiplier_min.is_equal_approx(Vector3(2.0, 1.0, 1.0)) or not life_multiplier_max.is_equal_approx(Vector3(4.0, 5.0, 1.0)):
		return {"ready": false, "error": "AcidBall size-life range mismatch"}
	if ParticleSource.table_float_values(life_multiplier) != [2.0, 1.0, 1.0, 4.0, 5.0, 1.0]:
		return {"ready": false, "error": "AcidBall size-life samples mismatch"}

	var rotation := _distribution(rotation_props.get("StartRotation"))
	if not is_equal_approx(float(rotation.get("MaxValue", -1.0)), 1.0):
		return {"ready": false, "error": "AcidBall sprite rotation max mismatch"}
	if ParticleSource.table_float_values(rotation) != [0.0, 1.0]:
		return {"ready": false, "error": "AcidBall sprite rotation samples mismatch"}

	var start_color := _distribution(color_props.get("StartColor"))
	var start_alpha := _distribution(color_props.get("StartAlpha"))
	var start_color_max := _vector_from_distribution(start_color, "MaxValueVec", Vector3.INF)
	if not start_color_max.is_equal_approx(Vector3(2.0, 0.787645, 0.0)):
		return {"ready": false, "error": "AcidBall sprite start color max mismatch " + str(start_color_max)}
	if not is_equal_approx(float(start_alpha.get("MinValue", -1.0)), 1.0) or not is_equal_approx(float(start_alpha.get("MaxValue", -1.0)), 1.0):
		return {"ready": false, "error": "AcidBall sprite start alpha mismatch"}

	var color_scale := _distribution(color_scale_props.get("ColorScaleOverLife"))
	var alpha_scale := _distribution(color_scale_props.get("AlphaScaleOverLife"))
	if _vector_from_distribution(color_scale, "MinValueVec", Vector3.INF) != Vector3.ONE or _vector_from_distribution(color_scale, "MaxValueVec", Vector3.INF) != Vector3.ONE:
		return {"ready": false, "error": "AcidBall color-scale RGB mismatch"}
	var alpha_scale_values := ParticleSource.table_float_values(alpha_scale)
	if alpha_scale_values.size() != 32:
		return {"ready": false, "error": "AcidBall alpha-scale sample count mismatch %d" % alpha_scale_values.size()}
	if not is_equal_approx(alpha_scale_values[0], 0.0) or not is_equal_approx(alpha_scale_values[15], 0.9677419) or not is_equal_approx(alpha_scale_values[16], 0.96774197) or not is_equal_approx(alpha_scale_values[31], 0.0):
		return {"ready": false, "error": "AcidBall alpha-scale curve samples mismatch"}

	var mesh_rgb := _distribution(mesh_color_props.get("ColorOverLife"))
	var mesh_alpha := _distribution(mesh_color_props.get("AlphaOverLife"))
	if not _vector_from_distribution(mesh_rgb, "MinValueVec", Vector3.INF).is_equal_approx(Vector3(2.0, 0.0, 1.653337)):
		return {"ready": false, "error": "AcidBall mesh color mismatch"}
	var mesh_alpha_values := ParticleSource.table_float_values(mesh_alpha)
	if mesh_alpha_values.size() != 32:
		return {"ready": false, "error": "AcidBall mesh alpha curve count mismatch %d" % mesh_alpha_values.size()}
	if not is_equal_approx(mesh_alpha_values[0], 1.0) or not is_equal_approx(mesh_alpha_values[1], 0.67741936) or not is_equal_approx(mesh_alpha_values[2], 0.35483873) or not is_equal_approx(mesh_alpha_values[3], 0.039116114):
		return {"ready": false, "error": "AcidBall mesh alpha curve head mismatch"}

	if _canonical(str(mesh_type_props.get("Mesh", ""))) != _canonical(ACID_BALL_MESH):
		return {"ready": false, "error": "AcidBall mesh authority mismatch"}
	if not bool(mesh_type_props.get("bOverrideMaterial", false)):
		return {"ready": false, "error": "AcidBall mesh override-material flag mismatch"}

	var dynamic_raw: Variant = dynamic_props.get("DynamicParams", [])
	if not (dynamic_raw is Array) or (dynamic_raw as Array).size() != 4:
		return {"ready": false, "error": "AcidBall dynamic parameter count mismatch"}
	if int(dynamic_props.get("UpdateFlags", -1)) != 13:
		return {"ready": false, "error": "AcidBall dynamic parameter update flags mismatch"}

	var dynamic_ranges: Array[Vector2] = []
	var dynamic_spawn_only: Array[bool] = []
	var dynamic_samples: Array[Array] = []
	var expected_mins := [0.0, 0.3, 0.0, 0.0]
	var expected_maxs := [0.5, 0.6, 0.0, 0.0]
	var expected_samples: Array[Array] = [
		[0.0, 0.5],
		[0.3, 0.6],
		[0.0],
		[0.0],
	]
	for index in range(4):
		var row_raw: Variant = (dynamic_raw as Array)[index]
		if not (row_raw is Dictionary):
			return {"ready": false, "error": "AcidBall dynamic parameter row invalid"}
		var row := row_raw as Dictionary
		if str(row.get("ParamName", "")) != "None" or str(row.get("ValueMethod", "")) != "EDPV_UserSet":
			return {"ready": false, "error": "AcidBall dynamic parameter identity mismatch index=%d" % index}
		if bool(row.get("bScaleVelocityByParamValue", true)) or bool(row.get("bUseEmitterTime", true)):
			return {"ready": false, "error": "AcidBall dynamic parameter flags mismatch index=%d" % index}
		var expected_spawn_only := index == 1
		if bool(row.get("bSpawnTimeOnly", false)) != expected_spawn_only:
			return {"ready": false, "error": "AcidBall dynamic spawn-time flag mismatch index=%d" % index}
		var param_value := _distribution(row.get("ParamValue"))
		var param_min := float(param_value.get("MinValue", -999.0))
		var param_max := float(param_value.get("MaxValue", -999.0))
		if not is_equal_approx(param_min, float(expected_mins[index])) or not is_equal_approx(param_max, float(expected_maxs[index])):
			return {"ready": false, "error": "AcidBall dynamic range mismatch index=%d %s..%s" % [index, param_min, param_max]}
		var samples := ParticleSource.table_float_values(param_value)
		var expected := expected_samples[index]
		if samples.size() != expected.size():
			return {"ready": false, "error": "AcidBall dynamic sample count mismatch index=%d" % index}
		for sample_index in range(samples.size()):
			if not is_equal_approx(float(samples[sample_index]), float(expected[sample_index])):
				return {"ready": false, "error": "AcidBall dynamic sample mismatch index=%d sample=%d" % [index, sample_index]}
		if index == 0:
			var table0 := param_value.get("Table", {}) as Dictionary
			if not is_equal_approx(float(table0.get("TimeBias", -1.0)), 0.3) or not is_equal_approx(float(table0.get("TimeScale", -1.0)), 1.4285715):
				return {"ready": false, "error": "AcidBall dynamic curve timing mismatch index=0"}
		dynamic_ranges.append(Vector2(param_min, param_max))
		dynamic_spawn_only.append(expected_spawn_only)
		dynamic_samples.append(samples)

	var peaks: Array[int] = []
	for lod: Dictionary in lod_nodes:
		var lod_props := ParticleSource.properties(lod)
		peaks.append(int(lod_props.get("PeakActiveParticles", -1)))
	peaks.sort()
	if peaks != [3, 20]:
		return {"ready": false, "error": "AcidBall emitter peak counts mismatch " + str(peaks)}

	return {
		"ready": true,
		"systemPath": ACID_BALL_SYSTEM,
		"meshMaterialPath": ACID_BALL_SMOKE_MATERIAL,
		"spriteMaterialPath": ACID_BALL_MATERIAL,
		"meshPath": ACID_BALL_MESH,
		"meshBurstCount": 1,
		"spriteSpawnRate": 10.0,
		"spriteLifetimeMin": lifetime_min,
		"spriteLifetimeMax": lifetime_max,
		"meshSizeUEcm": mesh_size_min,
		"spriteSizeMinUEcm": sprite_size_min,
		"spriteSizeMaxUEcm": sprite_size_max,
		"dynamicParamCount": 4,
		"dynamicRanges": dynamic_ranges,
		"dynamicSpawnTimeOnly": dynamic_spawn_only,
		"dynamicSamples": dynamic_samples,
		"peakActiveByEmitter": peaks,
		"sourceNodeCount": int(system.get("nodeCount", 0)),
		"sourceReferenceCount": int(system.get("referenceCount", 0)),
	}


static func sparks_small_descriptor(graphs: Dictionary) -> Dictionary:
	var system := _find_system(graphs, SPARKS_SMALL_SYSTEM)
	if system.is_empty():
		return {"ready": false, "error": "sparks small source system missing"}
	if int(system.get("nodeCount", -1)) != 17:
		return {"ready": false, "error": "sparks small node count mismatch %d" % int(system.get("nodeCount", -1))}
	if int(system.get("referenceCount", -1)) != 7:
		return {"ready": false, "error": "sparks small reference count mismatch %d" % int(system.get("referenceCount", -1))}

	var required := _one_node(system, "ParticleModuleRequired")
	var lifetime := _one_node(system, "ParticleModuleLifetime")
	var location_seeded := _one_node(system, "ParticleModuleLocation_Seeded")
	var acceleration := _one_node(system, "ParticleModuleAccelerationConstant")
	var collision_gpu := _one_node(system, "ParticleModuleCollisionGPU")
	var size_speed := _one_node(system, "ParticleModuleSizeScaleBySpeed")
	var size := _one_node(system, "ParticleModuleSize")
	var spawn := _one_node(system, "ParticleModuleSpawn")
	var type_gpu := _one_node(system, "ParticleModuleTypeDataGpu")
	var velocity := _one_node(system, "ParticleModuleVelocity")
	var color := _one_node(system, "ParticleModuleColorOverLife")
	var lod_nodes := ParticleSource.nodes_by_type(system, "ParticleLODLevel")
	for pair: Array in [
		["required", required],
		["lifetime", lifetime],
		["seeded location", location_seeded],
		["acceleration constant", acceleration],
		["GPU collision", collision_gpu],
		["size by speed", size_speed],
		["size", size],
		["spawn", spawn],
		["GPU type", type_gpu],
		["velocity", velocity],
		["color over life", color],
	]:
		if (pair[1] as Dictionary).is_empty():
			return {"ready": false, "error": "sparks small missing " + str(pair[0])}
	if lod_nodes.size() != 2:
		return {"ready": false, "error": "sparks small LOD count mismatch %d" % lod_nodes.size()}

	var required_props := ParticleSource.properties(required)
	var lifetime_props := ParticleSource.properties(lifetime)
	var location_props := ParticleSource.properties(location_seeded)
	var acceleration_props := ParticleSource.properties(acceleration)
	var collision_props := ParticleSource.properties(collision_gpu)
	var size_speed_props := ParticleSource.properties(size_speed)
	var size_props := ParticleSource.properties(size)
	var spawn_props := ParticleSource.properties(spawn)
	var gpu_props := ParticleSource.properties(type_gpu)
	var velocity_props := ParticleSource.properties(velocity)
	var color_props := ParticleSource.properties(color)

	var material_path := str(required_props.get("Material", ""))
	var screen_alignment := str(required_props.get("ScreenAlignment", ""))
	var random_image_time := int(required_props.get("RandomImageTime", -1))
	var legacy_emitter_time := bool(required_props.get("bUseLegacyEmitterTime", true))
	if _canonical(material_path) != _canonical(SPARKS_SMALL_MATERIAL):
		return {"ready": false, "error": "sparks small material mismatch " + material_path}
	if screen_alignment != "PSA_Velocity":
		return {"ready": false, "error": "sparks small screen alignment mismatch " + screen_alignment}
	if random_image_time != 1 or legacy_emitter_time:
		return {"ready": false, "error": "sparks small emitter timing flags mismatch"}

	var life := _distribution(lifetime_props.get("Lifetime"))
	var life_values := ParticleSource.table_float_values(life)
	var life_min := float(life.get("MinValue", -1.0))
	var life_max := float(life.get("MaxValue", -1.0))
	if not is_equal_approx(life_min, 0.2) or not is_equal_approx(life_max, 0.5):
		return {"ready": false, "error": "sparks small lifetime mismatch %s..%s" % [life_min, life_max]}
	if life_values != [0.2, 0.5]:
		return {"ready": false, "error": "sparks small lifetime samples mismatch " + str(life_values)}

	var start_location := _distribution(location_props.get("StartLocation"))
	var location_min := _vector_from_distribution(start_location, "MinValueVec", Vector3.ZERO)
	var location_max := _vector_from_distribution(start_location, "MaxValueVec", Vector3.INF)
	if not location_min.is_equal_approx(Vector3.ZERO) or not location_max.is_equal_approx(Vector3(1.0, 4.0, 6.0)):
		return {"ready": false, "error": "sparks small seeded location mismatch %s..%s" % [location_min, location_max]}

	var accel := ParticleSource.vector3(acceleration_props.get("Acceleration"), Vector3.INF)
	var accel_world := bool(acceleration_props.get("bAlwaysInWorldSpace", false))
	if not accel.is_equal_approx(Vector3(0.0, 0.0, -900.0)) or not accel_world:
		return {"ready": false, "error": "sparks small acceleration mismatch accel=%s world=%s" % [accel, accel_world]}

	var collision_enabled := bool(collision_props.get("bEnabled", true))
	var resilience := _distribution(collision_props.get("Resilience"))
	var resilience_scale := _distribution(collision_props.get("ResilienceScaleOverLife"))
	var resilience_node := _node_by_path(system, str(resilience.get("Distribution", "")))
	var resilience_scale_node := _node_by_path(system, str(resilience_scale.get("Distribution", "")))
	if resilience_node.is_empty() or resilience_scale_node.is_empty():
		return {"ready": false, "error": "sparks small collision distribution node missing"}
	var resilience_value := ParticleSource.float_value(
		ParticleSource.properties(resilience_node).get("Constant"),
		-1.0
	)
	var resilience_scale_value := ParticleSource.float_value(
		ParticleSource.properties(resilience_scale_node).get("Constant"),
		-1.0
	)
	if collision_enabled or not is_equal_approx(resilience_value, 0.75) or not is_equal_approx(resilience_scale_value, 1.0):
		return {"ready": false, "error": "sparks small GPU collision mismatch enabled=%s resilience=%s scale=%s" % [collision_enabled, resilience_value, resilience_scale_value]}

	var speed_scale := ParticleSource.vector2(size_speed_props.get("SpeedScale"), Vector2.INF)
	var max_scale := ParticleSource.vector2(size_speed_props.get("MaxScale"), Vector2.INF)
	if not speed_scale.is_equal_approx(Vector2(0.0, 7.0)) or not max_scale.is_equal_approx(Vector2(1.0, 10.0)):
		return {"ready": false, "error": "sparks small size-speed mismatch"}

	var start_size := _distribution(size_props.get("StartSize"))
	var size_min := _vector_from_distribution(start_size, "MinValueVec", Vector3.INF)
	var size_max := _vector_from_distribution(start_size, "MaxValueVec", Vector3.INF)
	if not size_min.is_equal_approx(Vector3(0.1, 0.1, 0.1)) or not size_max.is_equal_approx(Vector3(2.0, 2.0, 2.0)):
		return {"ready": false, "error": "sparks small size mismatch %s..%s" % [size_min, size_max]}

	var rate := _distribution(spawn_props.get("Rate"))
	var rate_scale := _distribution(spawn_props.get("RateScale"))
	var burst_scale := _distribution(spawn_props.get("BurstScale"))
	var spawn_rate := float(rate.get("MinValue", -1.0))
	var spawn_rate_max := float(rate.get("MaxValue", -1.0))
	var spawn_scale := float(rate_scale.get("MinValue", -1.0))
	var burst_scale_value := float(burst_scale.get("MinValue", -1.0))
	if not is_equal_approx(spawn_rate, 10.0) or not is_equal_approx(spawn_rate_max, 10.0):
		return {"ready": false, "error": "sparks small spawn rate mismatch"}
	if not is_equal_approx(spawn_scale, 1.0) or not is_equal_approx(burst_scale_value, 0.5):
		return {"ready": false, "error": "sparks small spawn scales mismatch"}
	if bool(spawn_props.get("bApplyGlobalSpawnRateScale", true)):
		return {"ready": false, "error": "sparks small global spawn scaling unexpectedly enabled"}
	var bursts_raw: Variant = spawn_props.get("BurstList", [])
	if not (bursts_raw is Array) or (bursts_raw as Array).size() != 1:
		return {"ready": false, "error": "sparks small burst list mismatch"}
	var burst_raw: Variant = (bursts_raw as Array)[0]
	if not (burst_raw is Dictionary):
		return {"ready": false, "error": "sparks small burst entry invalid"}
	var burst := burst_raw as Dictionary
	var burst_count := int(burst.get("Count", -1))
	var burst_low := int(burst.get("CountLow", -999))
	var burst_time := float(burst.get("Time", -1.0))
	if burst_count != 20 or burst_low != 4 or not is_equal_approx(burst_time, 0.2):
		return {"ready": false, "error": "sparks small burst mismatch " + str(burst)}

	var start_velocity := _distribution(velocity_props.get("StartVelocity"))
	var velocity_min := _vector_from_distribution(start_velocity, "MinValueVec", Vector3.INF)
	var velocity_max := _vector_from_distribution(start_velocity, "MaxValueVec", Vector3.INF)
	var radial := _distribution(velocity_props.get("StartVelocityRadial"))
	if not velocity_min.is_equal_approx(Vector3(100.0, -100.0, -10.0)):
		return {"ready": false, "error": "sparks small velocity min mismatch " + str(velocity_min)}
	if not velocity_max.is_equal_approx(Vector3(100.0, 100.0, 125.0)):
		return {"ready": false, "error": "sparks small velocity max mismatch " + str(velocity_max)}
	if ParticleSource.table_float_values(radial) != [0.0]:
		return {"ready": false, "error": "sparks small radial velocity mismatch"}

	var rgb := _distribution(color_props.get("ColorOverLife"))
	var alpha := _distribution(color_props.get("AlphaOverLife"))
	if not _vector_from_distribution(rgb, "MinValueVec", Vector3.INF).is_equal_approx(Vector3.ONE):
		return {"ready": false, "error": "sparks small RGB min mismatch"}
	if not _vector_from_distribution(rgb, "MaxValueVec", Vector3.INF).is_equal_approx(Vector3.ONE):
		return {"ready": false, "error": "sparks small RGB max mismatch"}
	if ParticleSource.table_float_values(rgb) != [1.0, 1.0, 1.0]:
		return {"ready": false, "error": "sparks small RGB samples mismatch"}
	if ParticleSource.table_float_values(alpha) != [1.0, 0.0]:
		return {"ready": false, "error": "sparks small alpha samples mismatch"}

	var emitter_info_raw: Variant = gpu_props.get("EmitterInfo", {})
	var emitter_info := emitter_info_raw as Dictionary if emitter_info_raw is Dictionary else {}
	var resource_raw: Variant = gpu_props.get("ResourceData", {})
	var resource := resource_raw as Dictionary if resource_raw is Dictionary else {}
	var gpu_accel := ParticleSource.vector3(emitter_info.get("ConstantAcceleration"), Vector3.INF)
	var gpu_inv_max_size := ParticleSource.vector2(emitter_info.get("InvMaxSize"), Vector2.INF)
	var gpu_inv_rotation_scale := float(emitter_info.get("InvRotationRateScale", -1.0))
	var gpu_max_lifetime := float(emitter_info.get("MaxLifetime", -1.0))
	var gpu_max_particles := int(emitter_info.get("MaxParticleCount", -1))
	var gpu_alignment := str(emitter_info.get("ScreenAlignment", ""))
	var collision_radius_scale := float(resource.get("CollisionRadiusScale", -1.0))
	var collision_random := float(resource.get("CollisionRandomDistribution", -1.0))
	var rotation_rate_scale := float(resource.get("RotationRateScale", -1.0))
	var quantized_raw: Variant = resource.get("QuantizedColorSamples", [])
	var quantized_count := (quantized_raw as Array).size() if quantized_raw is Array else -1
	if not gpu_accel.is_equal_approx(Vector3(0.0, 0.0, -900.0)):
		return {"ready": false, "error": "sparks small GPU acceleration mismatch " + str(gpu_accel)}
	if not gpu_inv_max_size.is_equal_approx(Vector2(0.5, 0.5)):
		return {"ready": false, "error": "sparks small GPU inv max size mismatch " + str(gpu_inv_max_size)}
	if not is_equal_approx(gpu_inv_rotation_scale, 2.0) or not is_equal_approx(gpu_max_lifetime, 0.5):
		return {"ready": false, "error": "sparks small GPU lifetime/rotation scale mismatch"}
	if gpu_max_particles != 27 or gpu_alignment != "PSA_Velocity":
		return {"ready": false, "error": "sparks small GPU count/alignment mismatch"}
	if not is_equal_approx(collision_radius_scale, 0.5) or not is_equal_approx(collision_random, 1.0):
		return {"ready": false, "error": "sparks small GPU collision resource mismatch"}
	if not is_equal_approx(rotation_rate_scale, 0.5) or quantized_count != 2:
		return {"ready": false, "error": "sparks small GPU resource color/rotation mismatch"}

	var peaks: Array[int] = []
	for lod: Dictionary in lod_nodes:
		peaks.append(int(ParticleSource.properties(lod).get("PeakActiveParticles", -1)))
	peaks.sort()
	if peaks != [27, 27]:
		return {"ready": false, "error": "sparks small LOD peaks mismatch " + str(peaks)}

	return {
		"ready": true,
		"systemPath": SPARKS_SMALL_SYSTEM,
		"materialPath": material_path,
		"lifetimeMin": life_min,
		"lifetimeMax": life_max,
		"seededLocationMinUEcm": location_min,
		"seededLocationMaxUEcm": location_max,
		"accelerationUEcm": accel,
		"accelerationWorldSpace": accel_world,
		"collisionEnabled": collision_enabled,
		"collisionResilience": resilience_value,
		"collisionResilienceScale": resilience_scale_value,
		"speedScale": speed_scale,
		"maxScale": max_scale,
		"startSizeMinUEcm": size_min,
		"startSizeMaxUEcm": size_max,
		"spawnRate": spawn_rate,
		"burstCount": burst_count,
		"burstCountLow": burst_low,
		"burstTime": burst_time,
		"burstScale": burst_scale_value,
		"startVelocityMinUEcm": velocity_min,
		"startVelocityMaxUEcm": velocity_max,
		"gpuInvMaxSize": gpu_inv_max_size,
		"gpuMaxLifetime": gpu_max_lifetime,
		"gpuMaxParticleCount": gpu_max_particles,
		"gpuCollisionRadiusScale": collision_radius_scale,
		"gpuCollisionRandomDistribution": collision_random,
		"peakActiveByLOD": peaks,
		"sourceNodeCount": int(system.get("nodeCount", 0)),
		"sourceReferenceCount": int(system.get("referenceCount", 0)),
	}


static func quad_explode_smoke_descriptor(graphs: Dictionary) -> Dictionary:
	var system := _find_system(graphs, QUAD_EXPLODE_SMOKE_SYSTEM)
	if system.is_empty():
		return {"ready": false, "error": "quad explode smoke source system missing"}
	if int(system.get("nodeCount", -1)) != 23:
		return {"ready": false, "error": "quad explode smoke node count mismatch %d" % int(system.get("nodeCount", -1))}
	if int(system.get("referenceCount", -1)) != 7:
		return {"ready": false, "error": "quad explode smoke reference count mismatch %d" % int(system.get("referenceCount", -1))}

	var required := _one_node(system, "ParticleModuleRequired")
	var lifetime := _one_node(system, "ParticleModuleLifetime")
	var size := _one_node(system, "ParticleModuleSize")
	var color_life := _one_node(system, "ParticleModuleColorOverLife")
	var subuv_movie := _one_node(system, "ParticleModuleSubUVMovie")
	var size_life := _one_node(system, "ParticleModuleSizeMultiplyLife")
	var cylinder := _one_node(system, "ParticleModuleLocationPrimitiveCylinder")
	var acceleration := _one_node(system, "ParticleModuleAcceleration")
	var rotation := _one_node(system, "ParticleModuleRotation")
	var rotation_rate := _one_node(system, "ParticleModuleRotationRate")
	var velocity := _one_node(system, "ParticleModuleVelocity")
	var velocity_life := _one_node(system, "ParticleModuleVelocityOverLifetime")
	var skel_surface := _one_node(system, "ParticleModuleLocationSkelVertSurface")
	var start_color := _one_node(system, "ParticleModuleColor")
	var rotation_seeded := _one_node(system, "ParticleModuleRotation_Seeded")
	var location := _one_node(system, "ParticleModuleLocation")
	var spawn := _one_node(system, "ParticleModuleSpawn")
	var lod := _one_node(system, "ParticleLODLevel")
	for pair: Array in [
		["required", required], ["lifetime", lifetime], ["size", size],
		["color over life", color_life], ["SubUV movie", subuv_movie],
		["size over life", size_life], ["cylinder location", cylinder],
		["acceleration", acceleration], ["rotation", rotation],
		["rotation rate", rotation_rate], ["velocity", velocity],
		["velocity over life", velocity_life], ["skeletal surface", skel_surface],
		["start color", start_color], ["seeded rotation", rotation_seeded],
		["location", location], ["spawn", spawn], ["LOD", lod],
	]:
		if (pair[1] as Dictionary).is_empty():
			return {"ready": false, "error": "quad explode smoke missing " + str(pair[0])}

	var required_props := ParticleSource.properties(required)
	if _canonical(str(required_props.get("Material", ""))) != _canonical(QUAD_EXPLODE_SMOKE_MATERIAL):
		return {"ready": false, "error": "quad explode smoke material mismatch"}
	if not is_equal_approx(float(required_props.get("EmitterDelay", -1.0)), 0.1):
		return {"ready": false, "error": "quad explode smoke emitter delay mismatch"}
	if int(required_props.get("EmitterLoops", -1)) != 1 or int(required_props.get("RandomImageTime", -1)) != 1:
		return {"ready": false, "error": "quad explode smoke emitter loop/image timing mismatch"}
	if int(required_props.get("SubImages_Horizontal", -1)) != 6 or int(required_props.get("SubImages_Vertical", -1)) != 6:
		return {"ready": false, "error": "quad explode smoke SubUV grid mismatch"}
	if str(required_props.get("InterpolationMethod", "")) != "PSUVIM_Linear_Blend":
		return {"ready": false, "error": "quad explode smoke interpolation mismatch"}
	if str(required_props.get("SortMode", "")) != "PSORTMODE_Age_OldestFirst":
		return {"ready": false, "error": "quad explode smoke sort mode mismatch"}
	if not bool(required_props.get("bRemoveHMDRoll", false)):
		return {"ready": false, "error": "quad explode smoke HMD roll flag mismatch"}

	var life := _distribution(ParticleSource.properties(lifetime).get("Lifetime"))
	if not is_equal_approx(float(life.get("MinValue", -1.0)), 1.0) or not is_equal_approx(float(life.get("MaxValue", -1.0)), 2.0):
		return {"ready": false, "error": "quad explode smoke lifetime mismatch"}
	if ParticleSource.table_float_values(life) != [1.0, 2.0]:
		return {"ready": false, "error": "quad explode smoke lifetime samples mismatch"}

	var size_dist := _distribution(ParticleSource.properties(size).get("StartSize"))
	var size_min := _vector_from_distribution(size_dist, "MinValueVec", Vector3.INF)
	var size_max := _vector_from_distribution(size_dist, "MaxValueVec", Vector3.INF)
	if not size_min.is_equal_approx(Vector3(200.0, 200.0, 200.0)) or not size_max.is_equal_approx(Vector3(250.0, 250.0, 250.0)):
		return {"ready": false, "error": "quad explode smoke size mismatch"}

	var location_dist := _distribution(ParticleSource.properties(location).get("StartLocation"))
	var location_min := _vector_from_distribution(location_dist, "MinValueVec", Vector3.INF)
	var location_max := _vector_from_distribution(location_dist, "MaxValueVec", Vector3.INF)
	if not location_min.is_equal_approx(Vector3(-120.0, -120.0, 5.0)) or not location_max.is_equal_approx(Vector3(120.0, 120.0, 25.0)):
		return {"ready": false, "error": "quad explode smoke location mismatch"}

	var velocity_dist := _distribution(ParticleSource.properties(velocity).get("StartVelocity"))
	var velocity_min := _vector_from_distribution(velocity_dist, "MinValueVec", Vector3.INF)
	var velocity_max := _vector_from_distribution(velocity_dist, "MaxValueVec", Vector3.INF)
	if not velocity_min.is_equal_approx(Vector3(-20.0, -20.0, 7.0)) or not velocity_max.is_equal_approx(Vector3(20.0, 20.0, 25.0)):
		return {"ready": false, "error": "quad explode smoke velocity mismatch"}

	var spawn_props := ParticleSource.properties(spawn)
	var rate := _distribution(spawn_props.get("Rate"))
	var rate_scale := _distribution(spawn_props.get("RateScale"))
	var burst_scale := _distribution(spawn_props.get("BurstScale"))
	if not is_equal_approx(float(rate.get("MinValue", -1.0)), 5.0) or not is_equal_approx(float(rate.get("MaxValue", -1.0)), 5.0):
		return {"ready": false, "error": "quad explode smoke rate mismatch"}
	if not is_equal_approx(float(rate_scale.get("MinValue", -1.0)), 5.0):
		return {"ready": false, "error": "quad explode smoke rate scale mismatch"}
	if not is_equal_approx(float(burst_scale.get("MinValue", -1.0)), 1.0):
		return {"ready": false, "error": "quad explode smoke burst scale mismatch"}
	var bursts_raw: Variant = spawn_props.get("BurstList", [])
	if not (bursts_raw is Array) or (bursts_raw as Array).size() != 1:
		return {"ready": false, "error": "quad explode smoke burst list mismatch"}
	var burst := (bursts_raw as Array)[0] as Dictionary
	if int(burst.get("Count", -1)) != 5 or int(burst.get("CountLow", 0)) != -1 or not is_equal_approx(float(burst.get("Time", -1.0)), 0.0):
		return {"ready": false, "error": "quad explode smoke burst values mismatch"}

	var subuv_props := ParticleSource.properties(subuv_movie)
	var frame_rate := _distribution(subuv_props.get("FrameRate"))
	if not is_equal_approx(float(frame_rate.get("MinValue", -1.0)), 15.0) or not is_equal_approx(float(frame_rate.get("MaxValue", -1.0)), 15.0):
		return {"ready": false, "error": "quad explode smoke SubUV FPS mismatch"}
	var subuv_index := _distribution(subuv_props.get("SubImageIndex"))
	var subuv_curve_node := _node_by_path(system, str(subuv_index.get("Distribution", "")))
	if subuv_curve_node.is_empty():
		return {"ready": false, "error": "quad explode smoke SubUV curve missing"}
	var curve_raw: Variant = ParticleSource.properties(subuv_curve_node).get("ConstantCurve", {})
	var curve := curve_raw as Dictionary if curve_raw is Dictionary else {}
	var points_raw: Variant = curve.get("Points", [])
	if not (points_raw is Array) or (points_raw as Array).size() != 2:
		return {"ready": false, "error": "quad explode smoke SubUV curve point count mismatch"}
	for raw_point: Variant in points_raw as Array:
		if not (raw_point is Dictionary) or not is_equal_approx(float((raw_point as Dictionary).get("OutVal", -1.0)), 0.0):
			return {"ready": false, "error": "quad explode smoke SubUV curve value mismatch"}

	var size_life_dist := _distribution(ParticleSource.properties(size_life).get("LifeMultiplier"))
	var size_life_values := ParticleSource.table_float_values(size_life_dist)
	if size_life_values.size() != 384:
		return {"ready": false, "error": "quad explode smoke size-life table count mismatch %d" % size_life_values.size()}
	if not is_equal_approx(size_life_values[0], 0.4) or not is_equal_approx(size_life_values[1], 0.4) or not is_equal_approx(size_life_values[2], 0.4):
		return {"ready": false, "error": "quad explode smoke size-life head mismatch"}
	if not is_equal_approx(size_life_values[381], 0.9) or not is_equal_approx(size_life_values[382], 0.9) or not is_equal_approx(size_life_values[383], 0.9):
		return {"ready": false, "error": "quad explode smoke size-life tail mismatch"}

	var color_props := ParticleSource.properties(color_life)
	var rgb := _distribution(color_props.get("ColorOverLife"))
	var alpha := _distribution(color_props.get("AlphaOverLife"))
	var rgb_values := ParticleSource.table_float_values(rgb)
	var alpha_values := ParticleSource.table_float_values(alpha)
	if rgb_values.size() != 48 or alpha_values.size() != 128:
		return {"ready": false, "error": "quad explode smoke color table counts mismatch rgb=%d alpha=%d" % [rgb_values.size(), alpha_values.size()]}
	if not is_equal_approx(alpha_values[0], 0.0) or not is_equal_approx(alpha_values[127], 0.0):
		return {"ready": false, "error": "quad explode smoke alpha endpoints mismatch"}

	var rotation_dist := _distribution(ParticleSource.properties(rotation).get("StartRotation"))
	if ParticleSource.table_float_values(rotation_dist) != [0.0, 0.1]:
		return {"ready": false, "error": "quad explode smoke rotation mismatch"}
	var seeded_rotation_dist := _distribution(ParticleSource.properties(rotation_seeded).get("StartRotation"))
	if ParticleSource.table_float_values(seeded_rotation_dist) != [0.0, 1.0]:
		return {"ready": false, "error": "quad explode smoke seeded rotation mismatch"}

	var disabled_types: Array[String] = []
	for node: Dictionary in [acceleration, cylinder, skel_surface, start_color, rotation_rate, velocity_life]:
		var p := ParticleSource.properties(node)
		if bool(p.get("bEnabled", true)):
			return {"ready": false, "error": "quad explode smoke source-disabled module became enabled " + str(node.get("exportType", ""))}
		disabled_types.append(str(node.get("exportType", "")))
	disabled_types.sort()

	var cylinder_props := ParticleSource.properties(cylinder)
	var radius := _distribution(cylinder_props.get("StartRadius"))
	var height := _distribution(cylinder_props.get("StartHeight"))
	if not is_equal_approx(float(radius.get("MinValue", -1.0)), 350.0) or not is_equal_approx(float(height.get("MinValue", -1.0)), 50.0):
		return {"ready": false, "error": "quad explode smoke disabled cylinder authority mismatch"}

	var skel_props := ParticleSource.properties(skel_surface)
	var valid_materials_raw: Variant = skel_props.get("ValidMaterialIndices", [])
	var valid_materials := valid_materials_raw as Array if valid_materials_raw is Array else []
	if not bool(skel_props.get("bEnforceNormalCheck", false)) or not is_equal_approx(float(skel_props.get("NormalCheckTolerance", -1.0)), 1.0):
		return {"ready": false, "error": "quad explode smoke disabled skeletal check mismatch"}
	if valid_materials.size() != 1 or int(valid_materials[0]) != 0:
		return {"ready": false, "error": "quad explode smoke skeletal material indices mismatch"}

	var rotation_rate_dist := _distribution(ParticleSource.properties(rotation_rate).get("StartRotationRate"))
	if ParticleSource.table_float_values(rotation_rate_dist) != [-0.03, 0.03]:
		return {"ready": false, "error": "quad explode smoke disabled rotation-rate authority mismatch"}
	var velocity_life_dist := _distribution(ParticleSource.properties(velocity_life).get("VelOverLife"))
	var velocity_life_values := ParticleSource.table_float_values(velocity_life_dist)
	if velocity_life_values != [1.0, 1.0, 1.2, 1.0, 1.0, 1.0]:
		return {"ready": false, "error": "quad explode smoke disabled velocity-life authority mismatch"}

	if int(ParticleSource.properties(lod).get("PeakActiveParticles", -1)) != 31:
		return {"ready": false, "error": "quad explode smoke peak active mismatch"}

	return {
		"ready": true,
		"systemPath": QUAD_EXPLODE_SMOKE_SYSTEM,
		"materialPath": QUAD_EXPLODE_SMOKE_MATERIAL,
		"lifetimeMin": 1.0,
		"lifetimeMax": 2.0,
		"startSizeMinUEcm": size_min,
		"startSizeMaxUEcm": size_max,
		"startLocationMinUEcm": location_min,
		"startLocationMaxUEcm": location_max,
		"startVelocityMinUEcm": velocity_min,
		"startVelocityMaxUEcm": velocity_max,
		"spawnRate": 5.0,
		"spawnRateScale": 5.0,
		"burstCount": 5,
		"subUVFrameRate": 15.0,
		"sizeLifeTableValueCount": size_life_values.size(),
		"rgbTableValueCount": rgb_values.size(),
		"alphaTableValueCount": alpha_values.size(),
		"disabledModuleTypes": disabled_types,
		"peakActiveParticles": 31,
		"sourceNodeCount": int(system.get("nodeCount", 0)),
		"sourceReferenceCount": int(system.get("referenceCount", 0)),
	}


static func monster_death_xl_descriptor(graphs: Dictionary) -> Dictionary:
	var system := _find_system(graphs, MONSTER_DEATH_XL_SYSTEM)
	if system.is_empty():
		return {"ready": false, "error": "monster death XL source system missing"}
	if int(system.get("nodeCount", -1)) != 97:
		return {"ready": false, "error": "monster death XL node count mismatch %d" % int(system.get("nodeCount", -1))}
	if int(system.get("referenceCount", -1)) != 46:
		return {"ready": false, "error": "monster death XL reference count mismatch %d" % int(system.get("referenceCount", -1))}

	var expected_counts := {
		"ParticleModuleRequired": 4,
		"ParticleModuleSpawn": 4,
		"ParticleLODLevel": 12,
		"ParticleModuleTypeDataMesh": 2,
		"ParticleModuleMeshMaterial": 2,
		"ParticleModuleMeshRotation": 2,
		"ParticleModuleMeshRotationRate": 4,
		"ParticleModuleLifetime": 6,
		"ParticleModuleSize": 4,
		"ParticleModuleSizeMultiplyLife": 6,
		"ParticleModuleColorOverLife": 10,
		"ParticleModuleRotation": 2,
		"ParticleModuleAcceleration": 1,
		"ParticleModuleCameraOffset": 1,
		"ParticleModuleLocation": 1,
		"ParticleModuleLocationPrimitiveCylinder": 1,
		"ParticleModuleOrientationAxisLock": 1,
		"ParticleModuleSubUV": 1,
		"ParticleModuleVelocity": 1,
	}
	for raw_type: Variant in expected_counts.keys():
		var type_name := str(raw_type)
		var actual := ParticleSource.nodes_by_type(system, type_name).size()
		var expected := int(expected_counts[raw_type])
		if actual != expected:
			return {"ready": false, "error": "monster death XL module count mismatch %s=%d/%d" % [type_name, actual, expected]}

	var base := str(system.get("objectPath", ""))
	var required_suffixes := ["ParticleModuleRequired_1", "ParticleModuleRequired_22", "ParticleModuleRequired_25", "ParticleModuleRequired_8"]
	var spawn_suffixes := ["ParticleModuleSpawn_1", "ParticleModuleSpawn_22", "ParticleModuleSpawn_25", "ParticleModuleSpawn_8"]
	var required_nodes: Array[Dictionary] = []
	var spawn_nodes: Array[Dictionary] = []
	for suffix: String in required_suffixes:
		var node := _node_by_path(system, base + ":" + suffix)
		if node.is_empty():
			return {"ready": false, "error": "monster death XL required node missing " + suffix}
		required_nodes.append(node)
	for suffix: String in spawn_suffixes:
		var node := _node_by_path(system, base + ":" + suffix)
		if node.is_empty():
			return {"ready": false, "error": "monster death XL spawn node missing " + suffix}
		spawn_nodes.append(node)

	var delays: Array[float] = []
	var material_paths: Array[String] = []
	for node: Dictionary in required_nodes:
		var p := ParticleSource.properties(node)
		delays.append(float(p.get("EmitterDelay", 0.0)))
		var material := str(p.get("Material", ""))
		if not material.is_empty():
			material_paths.append(material)
		if int(p.get("EmitterLoops", -1)) != 1:
			return {"ready": false, "error": "monster death XL emitter loops mismatch"}
		if int(p.get("RandomImageTime", -1)) != 1:
			return {"ready": false, "error": "monster death XL random image time mismatch"}
		if bool(p.get("bUseLegacyEmitterTime", true)):
			return {"ready": false, "error": "monster death XL legacy emitter time unexpectedly enabled"}
	delays.sort()
	material_paths.sort()
	var expected_materials: Array[String] = [
		MONSTER_DEATH_EMISSIVE_MAT,
		MONSTER_DEATH_ICE_MAT,
		MONSTER_DEATH_SMOKE_MAT,
	]
	expected_materials.sort()
	if delays != [0.0, 0.1, 0.3, 0.4]:
		return {"ready": false, "error": "monster death XL emitter delays mismatch " + str(delays)}
	if material_paths != expected_materials:
		return {"ready": false, "error": "monster death XL required material set mismatch " + str(material_paths)}
	var smoke_required := ParticleSource.properties(_node_by_path(system, base + ":ParticleModuleRequired_25"))
	if int(smoke_required.get("SubImages_Horizontal", -1)) != 8 or int(smoke_required.get("SubImages_Vertical", -1)) != 8:
		return {"ready": false, "error": "monster death XL smoke SubUV grid mismatch"}
	if str(smoke_required.get("InterpolationMethod", "")) != "PSUVIM_Linear_Blend":
		return {"ready": false, "error": "monster death XL smoke interpolation mismatch"}

	var burst_only_emitters := 0
	var continuous_rate_15_emitters := 0
	for node: Dictionary in spawn_nodes:
		var p := ParticleSource.properties(node)
		var rate := _distribution(p.get("Rate"))
		var rate_values := ParticleSource.table_float_values(rate)
		var bursts_raw: Variant = p.get("BurstList", [])
		if not (bursts_raw is Array) or (bursts_raw as Array).size() != 1:
			return {"ready": false, "error": "monster death XL spawn burst list mismatch"}
		var burst := (bursts_raw as Array)[0] as Dictionary
		if rate_values == [0.0]:
			if int(burst.get("Count", -1)) != 1 or int(burst.get("CountLow", 0)) != -1 or not is_equal_approx(float(burst.get("Time", -1.0)), 0.0):
				return {"ready": false, "error": "monster death XL burst-only emitter mismatch"}
			burst_only_emitters += 1
		elif rate_values == [15.0]:
			if int(burst.get("Count", -1)) != 0:
				return {"ready": false, "error": "monster death XL continuous emitter burst mismatch"}
			continuous_rate_15_emitters += 1
		else:
			return {"ready": false, "error": "monster death XL unexpected spawn rate " + str(rate_values)}
	if burst_only_emitters != 3 or continuous_rate_15_emitters != 1:
		return {"ready": false, "error": "monster death XL spawn contract counts mismatch"}
	var spawn8 := ParticleSource.properties(_node_by_path(system, base + ":ParticleModuleSpawn_8"))
	var spawn8_scale := _distribution(spawn8.get("BurstScale"))
	var spawn8_scale_node := _node_by_path(system, str(spawn8_scale.get("Distribution", "")))
	if spawn8_scale_node.is_empty() or not is_equal_approx(float(ParticleSource.properties(spawn8_scale_node).get("Constant", -1.0)), 1.0):
		return {"ready": false, "error": "monster death XL emitter 8 burst scale mismatch"}

	var mesh_paths: Array[String] = []
	for node: Dictionary in ParticleSource.nodes_by_type(system, "ParticleModuleTypeDataMesh"):
		mesh_paths.append(str(ParticleSource.properties(node).get("Mesh", "")))
	mesh_paths.sort()
	var expected_meshes: Array[String] = [MONSTER_DEATH_MESH_1, MONSTER_DEATH_MESH_2]
	expected_meshes.sort()
	if mesh_paths != expected_meshes:
		return {"ready": false, "error": "monster death XL mesh set mismatch " + str(mesh_paths)}

	var mesh_materials: Array[String] = []
	for node: Dictionary in ParticleSource.nodes_by_type(system, "ParticleModuleMeshMaterial"):
		var raw_materials: Variant = ParticleSource.properties(node).get("MeshMaterials", [])
		if not (raw_materials is Array) or (raw_materials as Array).size() != 1:
			return {"ready": false, "error": "monster death XL mesh material override count mismatch"}
		mesh_materials.append(str((raw_materials as Array)[0]))
	mesh_materials.sort()
	var expected_mesh_materials: Array[String] = [MONSTER_DEATH_MESH_MAT_1, MONSTER_DEATH_MESH_MAT_2]
	expected_mesh_materials.sort()
	if mesh_materials != expected_mesh_materials:
		return {"ready": false, "error": "monster death XL mesh material set mismatch " + str(mesh_materials)}

	var lifetime_ranges: Array[Vector2] = []
	for node: Dictionary in ParticleSource.nodes_by_type(system, "ParticleModuleLifetime"):
		var d := _distribution(ParticleSource.properties(node).get("Lifetime"))
		var lo := float(d.get("MinValue", INF))
		var hi := float(d.get("MaxValue", -INF))
		if (is_inf(lo) or is_inf(hi)) and not str(d.get("Distribution", "")).is_empty():
			var dist_node := _node_by_path(system, str(d.get("Distribution", "")))
			if dist_node.is_empty():
				return {"ready": false, "error": "monster death XL lifetime distribution missing"}
			var dp := ParticleSource.properties(dist_node)
			lo = float(dp.get("Min", INF))
			hi = float(dp.get("Max", -INF))
		if is_inf(lo) or is_inf(hi):
			return {"ready": false, "error": "monster death XL lifetime range unresolved"}
		lifetime_ranges.append(Vector2(lo, hi))
	lifetime_ranges.sort()
	var expected_lifetimes: Array[Vector2] = [
		Vector2(1.4, 1.8),
		Vector2(1.7, 2.0),
		Vector2(2.0, 2.4),
		Vector2(2.0, 2.4),
		Vector2(2.4, 2.8),
		Vector2(2.7, 2.8),
	]
	if lifetime_ranges != expected_lifetimes:
		return {"ready": false, "error": "monster death XL lifetime families mismatch " + str(lifetime_ranges)}

	var size1 := _distribution(ParticleSource.properties(_node_by_path(system, base + ":ParticleModuleSize_1")).get("StartSize"))
	if ParticleSource.table_float_values(size1) != [13.0, 13.0, 1.0]:
		return {"ready": false, "error": "monster death XL mesh size 1 mismatch"}
	var size9 := _distribution(ParticleSource.properties(_node_by_path(system, base + ":ParticleModuleSize_9")).get("StartSize"))
	var size9_node := _node_by_path(system, str(size9.get("Distribution", "")))
	if size9_node.is_empty():
		return {"ready": false, "error": "monster death XL size9 distribution missing"}
	var size9_props := ParticleSource.properties(size9_node)
	if not ParticleSource.vector3(size9_props.get("Min"), Vector3.INF).is_equal_approx(Vector3(2.0, 2.0, 2.0)):
		return {"ready": false, "error": "monster death XL size9 min mismatch"}
	if not ParticleSource.vector3(size9_props.get("Max"), Vector3.INF).is_equal_approx(Vector3(2.0, 2.0, 2.0)):
		return {"ready": false, "error": "monster death XL size9 max mismatch"}
	var size18 := _distribution(ParticleSource.properties(_node_by_path(system, base + ":ParticleModuleSize_18")).get("StartSize"))
	var size21 := _distribution(ParticleSource.properties(_node_by_path(system, base + ":ParticleModuleSize_21")).get("StartSize"))
	var size18_values := ParticleSource.table_float_values(size18)
	var size21_values := ParticleSource.table_float_values(size21)
	if size18_values != [-500.0, -500.0, 0.0, 500.0, 500.0, 0.0]:
		return {"ready": false, "error": "monster death XL size18 samples mismatch " + str(size18_values)}
	if size21_values != [-75.0, -75.0, 0.0, 75.0, 75.0, 0.0]:
		return {"ready": false, "error": "monster death XL size21 samples mismatch " + str(size21_values)}

	var resolved_size_life := 0
	for node: Dictionary in ParticleSource.nodes_by_type(system, "ParticleModuleSizeMultiplyLife"):
		var d := _distribution(ParticleSource.properties(node).get("LifeMultiplier"))
		if not ParticleSource.table_float_values(d).is_empty():
			resolved_size_life += 1
		elif not str(d.get("Distribution", "")).is_empty() and not _node_by_path(system, str(d.get("Distribution", ""))).is_empty():
			resolved_size_life += 1
	if resolved_size_life != 6:
		return {"ready": false, "error": "monster death XL size-life source coverage mismatch %d/6" % resolved_size_life}

	var resolved_color_modules := 0
	for node: Dictionary in ParticleSource.nodes_by_type(system, "ParticleModuleColorOverLife"):
		var p := ParticleSource.properties(node)
		var rgb := _distribution(p.get("ColorOverLife"))
		var alpha := _distribution(p.get("AlphaOverLife"))
		var rgb_ok := not ParticleSource.table_float_values(rgb).is_empty()
		var alpha_ok := not ParticleSource.table_float_values(alpha).is_empty()
		if not rgb_ok and not str(rgb.get("Distribution", "")).is_empty():
			rgb_ok = not _node_by_path(system, str(rgb.get("Distribution", ""))).is_empty()
		if not alpha_ok and not str(alpha.get("Distribution", "")).is_empty():
			alpha_ok = not _node_by_path(system, str(alpha.get("Distribution", ""))).is_empty()
		if rgb_ok and alpha_ok:
			resolved_color_modules += 1
	if resolved_color_modules != 10:
		return {"ready": false, "error": "monster death XL color source coverage mismatch %d/10" % resolved_color_modules}

	var accel := _distribution(ParticleSource.properties(_one_node(system, "ParticleModuleAcceleration")).get("Acceleration"))
	if ParticleSource.table_float_values(accel) != [0.0, 0.0, 15.0, 0.0, 0.0, 30.0]:
		return {"ready": false, "error": "monster death XL acceleration samples mismatch"}
	if not bool(ParticleSource.properties(_one_node(system, "ParticleModuleAcceleration")).get("bAlwaysInWorldSpace", false)):
		return {"ready": false, "error": "monster death XL acceleration world-space mismatch"}
	var camera_offset := _distribution(ParticleSource.properties(_one_node(system, "ParticleModuleCameraOffset")).get("CameraOffset"))
	if ParticleSource.table_float_values(camera_offset) != [80.0]:
		return {"ready": false, "error": "monster death XL camera offset mismatch"}
	var cylinder_props := ParticleSource.properties(_one_node(system, "ParticleModuleLocationPrimitiveCylinder"))
	if not is_equal_approx(float(_distribution(cylinder_props.get("StartRadius")).get("MinValue", -1.0)), 190.0):
		return {"ready": false, "error": "monster death XL cylinder radius mismatch"}
	if not is_equal_approx(float(_distribution(cylinder_props.get("StartHeight")).get("MinValue", -1.0)), 5.0):
		return {"ready": false, "error": "monster death XL cylinder height mismatch"}
	var location_values := ParticleSource.table_float_values(_distribution(ParticleSource.properties(_one_node(system, "ParticleModuleLocation")).get("StartLocation")))
	if location_values != [0.0, 0.0, 15.0]:
		return {"ready": false, "error": "monster death XL location mismatch"}
	if str(ParticleSource.properties(_one_node(system, "ParticleModuleOrientationAxisLock")).get("LockAxisFlags", "")) != "EPAL_Z":
		return {"ready": false, "error": "monster death XL axis lock mismatch"}

	var velocity_dist := _distribution(ParticleSource.properties(_one_node(system, "ParticleModuleVelocity")).get("StartVelocity"))
	var velocity_values := ParticleSource.table_float_values(velocity_dist)
	if velocity_values != [-15.0, -15.0, 25.0, 15.0, 15.0, 35.0]:
		return {"ready": false, "error": "monster death XL velocity samples mismatch " + str(velocity_values)}
	var velocity_min := Vector3(velocity_values[0], velocity_values[1], velocity_values[2])
	var velocity_max := Vector3(velocity_values[3], velocity_values[4], velocity_values[5])

	var subuv := _distribution(ParticleSource.properties(_one_node(system, "ParticleModuleSubUV")).get("SubImageIndex"))
	var subuv_values := ParticleSource.table_float_values(subuv)
	if subuv_values.size() != 32 or not is_equal_approx(subuv_values[0], 0.0) or not is_equal_approx(subuv_values[31], 63.0):
		return {"ready": false, "error": "monster death XL SubUV samples mismatch"}

	var lod_nodes := ParticleSource.nodes_by_type(system, "ParticleLODLevel")
	var peaks: Array[int] = []
	var required_counts: Dictionary = {}
	var spawn_counts: Dictionary = {}
	var type_counts: Dictionary = {}
	for node: Dictionary in lod_nodes:
		var p := ParticleSource.properties(node)
		peaks.append(int(p.get("PeakActiveParticles", -1)))
		var required_key := _canonical(str(p.get("RequiredModule", "")))
		var spawn_key := _canonical(str(p.get("SpawnModule", "")))
		var type_key := _canonical(str(p.get("TypeDataModule", "")))
		required_counts[required_key] = int(required_counts.get(required_key, 0)) + 1
		spawn_counts[spawn_key] = int(spawn_counts.get(spawn_key, 0)) + 1
		type_counts[type_key] = int(type_counts.get(type_key, 0)) + 1
	peaks.sort()
	if peaks != [2, 2, 2, 2, 2, 2, 3, 3, 3, 16, 16, 16]:
		return {"ready": false, "error": "monster death XL LOD peaks mismatch " + str(peaks)}
	for suffix: String in required_suffixes:
		if int(required_counts.get(_canonical(base + ":" + suffix), 0)) != 3:
			return {"ready": false, "error": "monster death XL LOD required mapping mismatch " + suffix}
	for suffix: String in spawn_suffixes:
		if int(spawn_counts.get(_canonical(base + ":" + suffix), 0)) != 3:
			return {"ready": false, "error": "monster death XL LOD spawn mapping mismatch " + suffix}
	if int(type_counts.get(_canonical(base + ":ParticleModuleTypeDataMesh_1"), 0)) != 3:
		return {"ready": false, "error": "monster death XL LOD mesh1 mapping mismatch"}
	if int(type_counts.get(_canonical(base + ":ParticleModuleTypeDataMesh_3"), 0)) != 3:
		return {"ready": false, "error": "monster death XL LOD mesh3 mapping mismatch"}
	if int(type_counts.get("", 0)) != 6:
		return {"ready": false, "error": "monster death XL sprite LOD mapping mismatch"}

	return {
		"ready": true,
		"systemPath": MONSTER_DEATH_XL_SYSTEM,
		"emitterCount": 4,
		"lodCount": 12,
		"meshPaths": mesh_paths,
		"meshMaterialPaths": mesh_materials,
		"requiredMaterialPaths": material_paths,
		"emitterDelays": delays,
		"burstOnlyEmitterCount": burst_only_emitters,
		"continuousRate15EmitterCount": continuous_rate_15_emitters,
		"lifetimeRanges": lifetime_ranges,
		"resolvedSizeLifeModuleCount": resolved_size_life,
		"resolvedColorModuleCount": resolved_color_modules,
		"velocityMinUEcm": velocity_min,
		"velocityMaxUEcm": velocity_max,
		"subUVSampleCount": subuv_values.size(),
		"lodPeaks": peaks,
		"sourceNodeCount": int(system.get("nodeCount", 0)),
		"sourceReferenceCount": int(system.get("referenceCount", 0)),
	}


static func fire_00_descriptor(graphs: Dictionary) -> Dictionary:
	var system := _find_system(graphs, FIRE_00_SYSTEM)
	if system.is_empty():
		return {"ready": false, "error": "Fire_00 source system missing"}
	if int(system.get("nodeCount", -1)) != 124:
		return {"ready": false, "error": "Fire_00 node count mismatch %d" % int(system.get("nodeCount", -1))}
	if int(system.get("referenceCount", -1)) != 45:
		return {"ready": false, "error": "Fire_00 reference count mismatch %d" % int(system.get("referenceCount", -1))}

	var expected_counts := {
		"DistributionFloatConstant": 18,
		"DistributionFloatConstantCurve": 4,
		"ParticleLODLevel": 12,
		"ParticleModuleAcceleration": 3,
		"ParticleModuleColorOverLife": 6,
		"ParticleModuleLifetime": 6,
		"ParticleModuleLight": 1,
		"ParticleModuleLocation": 2,
		"ParticleModuleLocationEmitter": 3,
		"ParticleModuleLocationPrimitiveCylinder": 5,
		"ParticleModuleLocationPrimitiveSphere": 1,
		"ParticleModuleLocationSkelVertSurface": 1,
		"ParticleModuleOrbit": 2,
		"ParticleModuleOrientationAxisLock": 2,
		"ParticleModuleParameterDynamic": 2,
		"ParticleModulePivotOffset": 3,
		"ParticleModuleRequired": 6,
		"ParticleModuleRotation": 3,
		"ParticleModuleRotationRate": 3,
		"ParticleModuleSize": 6,
		"ParticleModuleSizeMultiplyLife": 6,
		"ParticleModuleSizeScaleBySpeed": 2,
		"ParticleModuleSpawn": 12,
		"ParticleModuleSubUV": 3,
		"ParticleModuleSubUVMovie": 2,
		"ParticleModuleVelocity": 6,
		"ParticleModuleVelocityOverLifetime": 3,
		"ParticleSystem": 1,
	}
	for raw_type: Variant in expected_counts.keys():
		var type_name := str(raw_type)
		var actual := ParticleSource.nodes_by_type(system, type_name).size()
		var expected := int(expected_counts[raw_type])
		if actual != expected:
			return {"ready": false, "error": "Fire_00 module count mismatch %s=%d/%d" % [type_name, actual, expected]}

	var base := str(system.get("objectPath", ""))
	var required_specs := {
		"ParticleModuleRequired_0": [FIRE_00_MAT_BONE_FWD4, 8, 3, "PSUVIM_Linear_Blend", "PSA_Velocity"],
		"ParticleModuleRequired_4": [FIRE_00_MAT_BONE3, 8, 8, "PSUVIM_Linear_Blend", "PSA_Velocity"],
		"ParticleModuleRequired_5": [FIRE_00_MAT_DISTORT, -1, -1, "", ""],
		"ParticleModuleRequired_7": [FIRE_00_MAT_FLAME, 2, 2, "PSUVIM_Random", ""],
		"ParticleModuleRequired_8": [FIRE_00_MAT_FLAME, 2, 2, "PSUVIM_Random", "PSA_Velocity"],
		"ParticleModuleRequired_10": [FIRE_00_MAT_SMOKE, 6, 6, "PSUVIM_Linear_Blend", ""],
	}
	var required_paths: Array[String] = []
	var material_paths: Array[String] = []
	for raw_suffix: Variant in required_specs.keys():
		var suffix := str(raw_suffix)
		var node := _node_by_path(system, base + ":" + suffix)
		if node.is_empty():
			return {"ready": false, "error": "Fire_00 required node missing " + suffix}
		var p := ParticleSource.properties(node)
		var spec: Array = required_specs[raw_suffix] as Array
		if _canonical(str(p.get("Material", ""))) != _canonical(str(spec[0])):
			return {"ready": false, "error": "Fire_00 material mismatch " + suffix}
		if int(spec[1]) >= 0:
			if int(p.get("SubImages_Horizontal", -1)) != int(spec[1]) or int(p.get("SubImages_Vertical", -1)) != int(spec[2]):
				return {"ready": false, "error": "Fire_00 SubUV grid mismatch " + suffix}
		if not str(spec[3]).is_empty() and str(p.get("InterpolationMethod", "")) != str(spec[3]):
			return {"ready": false, "error": "Fire_00 interpolation mismatch " + suffix}
		if not str(spec[4]).is_empty() and str(p.get("ScreenAlignment", "")) != str(spec[4]):
			return {"ready": false, "error": "Fire_00 alignment mismatch " + suffix}
		if p.has("bUseLegacyEmitterTime") and bool(p.get("bUseLegacyEmitterTime", true)):
			return {"ready": false, "error": "Fire_00 legacy emitter time enabled " + suffix}
		if suffix == "ParticleModuleRequired_10":
			if not is_equal_approx(float(p.get("EmitterDelay", -1.0)), 0.1) or str(p.get("SortMode", "")) != "PSORTMODE_Age_OldestFirst":
				return {"ready": false, "error": "Fire_00 smoke required contract mismatch"}
		if suffix == "ParticleModuleRequired_5" and int(p.get("MaxDrawCount", -1)) != 100:
			return {"ready": false, "error": "Fire_00 distortion MaxDrawCount mismatch"}
		required_paths.append(base + ":" + suffix)
		material_paths.append(str(p.get("Material", "")))
	material_paths.sort()

	var expected_lifetimes := {
		"ParticleModuleLifetime_0": Vector2(0.5, 1.0),
		"ParticleModuleLifetime_4": Vector2(1.5, 2.0),
		"ParticleModuleLifetime_5": Vector2(0.5, 1.0),
		"ParticleModuleLifetime_6": Vector2(0.5, 1.0),
		"ParticleModuleLifetime_7": Vector2(0.75, 1.5),
		"ParticleModuleLifetime_11": Vector2(3.0, 5.0),
	}
	var lifetime_ranges: Array[Vector2] = []
	for raw_suffix: Variant in expected_lifetimes.keys():
		var suffix := str(raw_suffix)
		var node := _node_by_path(system, base + ":" + suffix)
		if node.is_empty():
			return {"ready": false, "error": "Fire_00 lifetime node missing " + suffix}
		var d := _distribution(ParticleSource.properties(node).get("Lifetime"))
		var values := ParticleSource.table_float_values(d)
		var expected: Vector2 = expected_lifetimes[raw_suffix]
		if values.size() != 2 or not is_equal_approx(values[0], expected.x) or not is_equal_approx(values[1], expected.y):
			return {"ready": false, "error": "Fire_00 lifetime mismatch " + suffix + " " + str(values)}
		lifetime_ranges.append(expected)
	lifetime_ranges.sort()

	var expected_size_values := {
		"ParticleModuleSize_0": [7.0, 6.0, 0.0, 4.0, 4.0, 0.0],
		"ParticleModuleSize_2": [5.0, 5.0, 0.0],
		"ParticleModuleSize_4": [10.0, 8.0, 0.0, 7.0, 4.0, 0.0],
		"ParticleModuleSize_6": [9.0, 1.0, 1.0, 6.0, 1.0, 1.0],
		"ParticleModuleSize_7": [4.0, 0.0, 0.0, 2.0, 0.0, 0.0],
		"ParticleModuleSize_9": [5.0, 6.0, 0.0, 2.0, 2.0, 0.0],
	}
	for raw_suffix: Variant in expected_size_values.keys():
		var suffix := str(raw_suffix)
		var node := _node_by_path(system, base + ":" + suffix)
		if node.is_empty():
			return {"ready": false, "error": "Fire_00 size node missing " + suffix}
		var d := _distribution(ParticleSource.properties(node).get("StartSize"))
		var values := ParticleSource.table_float_values(d)
		var expected: Array = expected_size_values[raw_suffix] as Array
		if values.size() != expected.size():
			return {"ready": false, "error": "Fire_00 size sample count mismatch " + suffix}
		for i in range(values.size()):
			if not is_equal_approx(float(values[i]), float(expected[i])):
				return {"ready": false, "error": "Fire_00 size mismatch " + suffix + " sample=" + str(i)}

	var expected_velocity_values := {
		"ParticleModuleVelocity_0": [-3.0, -3.0, 2.5, 3.0, 3.0, 5.0],
		"ParticleModuleVelocity_2": [-5.0, -5.0, 10.0, 5.0, 5.0, 50.0],
		"ParticleModuleVelocity_6": [-75.0, -25.0, 100.0, 75.0, 25.0, 50.0],
		"ParticleModuleVelocity_10": [-20.0, -20.0, 20.0, 20.0, 20.0, 60.0],
		"ParticleModuleVelocity_16": [-10.0, -10.0, 10.0, 10.0, 10.0, 30.0],
		"ParticleModuleVelocity_33": [-10.0, -10.0, 50.0, 10.0, 10.0, 100.0],
	}
	for raw_suffix: Variant in expected_velocity_values.keys():
		var suffix := str(raw_suffix)
		var node := _node_by_path(system, base + ":" + suffix)
		if node.is_empty():
			return {"ready": false, "error": "Fire_00 velocity node missing " + suffix}
		var d := _distribution(ParticleSource.properties(node).get("StartVelocity"))
		var values := ParticleSource.table_float_values(d)
		var expected: Array = expected_velocity_values[raw_suffix] as Array
		if values.size() != expected.size():
			return {"ready": false, "error": "Fire_00 velocity sample count mismatch " + suffix}
		for i in range(values.size()):
			if not is_equal_approx(float(values[i]), float(expected[i])):
				return {"ready": false, "error": "Fire_00 velocity mismatch " + suffix + " sample=" + str(i)}

	var expected_spawn_rates := {
		"ParticleModuleSpawn_0": 10.0,
		"ParticleModuleSpawn_1": 0.99999994,
		"ParticleModuleSpawn_2": 1.9999999,
		"ParticleModuleSpawn_3": 1.4999999,
		"ParticleModuleSpawn_4": 10.0,
		"ParticleModuleSpawn_5": 10.0,
		"ParticleModuleSpawn_6": 50.0,
		"ParticleModuleSpawn_7": 20.0,
		"ParticleModuleSpawn_8": 0.99999994,
		"ParticleModuleSpawn_9": 0.99999994,
		"ParticleModuleSpawn_10": 15.0,
		"ParticleModuleSpawn_11": 4.9999995,
	}
	var spawn_rates: Array[float] = []
	for raw_suffix: Variant in expected_spawn_rates.keys():
		var suffix := str(raw_suffix)
		var node := _node_by_path(system, base + ":" + suffix)
		if node.is_empty():
			return {"ready": false, "error": "Fire_00 spawn node missing " + suffix}
		var p := ParticleSource.properties(node)
		var rate := _distribution(p.get("Rate"))
		var rate_values := ParticleSource.table_float_values(rate)
		var expected := float(expected_spawn_rates[raw_suffix])
		if rate_values.size() != 1 or not is_equal_approx(rate_values[0], expected):
			return {"ready": false, "error": "Fire_00 spawn rate mismatch " + suffix + " " + str(rate_values)}
		var scale := _distribution(p.get("RateScale"))
		if not is_equal_approx(float(scale.get("MinValue", -1.0)), 1.0):
			return {"ready": false, "error": "Fire_00 spawn scale mismatch " + suffix}
		spawn_rates.append(expected)
	spawn_rates.sort()

	var dynamic_specs := {
		"ParticleModuleParameterDynamic_1": [
			["Temperature", 10.0, 1000.0, 128],
			["Temp_Intensity", 1.0, 50.0, 128],
			["ori_blend", -0.0057327608, 1.0, 16],
			["None", 0.0, 0.0, 1],
		],
		"ParticleModuleParameterDynamic_2": [
			["Normal_Scale", 0.2, 0.2, 1],
			["Normal_Flatness", 0.6, 1.0, 8],
			["IOR", 0.05, 0.05, 1],
			["None", 0.05, 0.05, 1],
		],
	}
	for raw_suffix: Variant in dynamic_specs.keys():
		var suffix := str(raw_suffix)
		var node := _node_by_path(system, base + ":" + suffix)
		if node.is_empty():
			return {"ready": false, "error": "Fire_00 dynamic node missing " + suffix}
		var p := ParticleSource.properties(node)
		if int(p.get("UpdateFlags", -1)) != 15:
			return {"ready": false, "error": "Fire_00 dynamic UpdateFlags mismatch " + suffix}
		var rows_raw: Variant = p.get("DynamicParams", [])
		if not (rows_raw is Array) or (rows_raw as Array).size() != 4:
			return {"ready": false, "error": "Fire_00 dynamic row count mismatch " + suffix}
		var specs: Array = dynamic_specs[raw_suffix] as Array
		for i in range(4):
			var row_raw: Variant = (rows_raw as Array)[i]
			if not (row_raw is Dictionary):
				return {"ready": false, "error": "Fire_00 dynamic row invalid " + suffix}
			var row := row_raw as Dictionary
			var spec: Array = specs[i] as Array
			if str(row.get("ParamName", "")) != str(spec[0]) or str(row.get("ValueMethod", "")) != "EDPV_UserSet":
				return {"ready": false, "error": "Fire_00 dynamic identity mismatch " + suffix + " index=" + str(i)}
			var d := _distribution(row.get("ParamValue"))
			if not is_equal_approx(float(d.get("MinValue", -999.0)), float(spec[1])) or not is_equal_approx(float(d.get("MaxValue", -999.0)), float(spec[2])):
				return {"ready": false, "error": "Fire_00 dynamic range mismatch " + suffix + " index=" + str(i)}
			if ParticleSource.table_float_values(d).size() != int(spec[3]):
				return {"ready": false, "error": "Fire_00 dynamic sample count mismatch " + suffix + " index=" + str(i)}

	var pivot_expected := {
		"ParticleModulePivotOffset_2": Vector2(0.0, -0.5),
		"ParticleModulePivotOffset_3": Vector2(0.0, -0.5),
		"ParticleModulePivotOffset_8": Vector2(0.0, -0.3),
	}
	for raw_suffix: Variant in pivot_expected.keys():
		var suffix := str(raw_suffix)
		var p := ParticleSource.properties(_node_by_path(system, base + ":" + suffix))
		if not ParticleSource.vector2(p.get("PivotOffset"), Vector2.INF).is_equal_approx(pivot_expected[raw_suffix]):
			return {"ready": false, "error": "Fire_00 pivot mismatch " + suffix}

	var skel_nodes := ParticleSource.nodes_by_type(system, "ParticleModuleLocationSkelVertSurface")
	if skel_nodes.size() != 1 or bool(ParticleSource.properties(skel_nodes[0]).get("bEnabled", true)):
		return {"ready": false, "error": "Fire_00 source-disabled skeletal location mismatch"}

	var light := _one_node(system, "ParticleModuleLight")
	var light_props := ParticleSource.properties(light)
	var brightness := _distribution(light_props.get("BrightnessOverLife"))
	var color_scale := _distribution(light_props.get("ColorScaleOverLife"))
	var exponent := _distribution(light_props.get("LightExponent"))
	var radius_scale := _distribution(light_props.get("RadiusScale"))
	if ParticleSource.table_float_values(brightness) != [0.5]:
		return {"ready": false, "error": "Fire_00 light brightness mismatch"}
	if ParticleSource.table_float_values(color_scale) != [0.9, 1.0, 0.5]:
		return {"ready": false, "error": "Fire_00 light color mismatch"}
	if ParticleSource.table_float_values(exponent) != [3.0] or ParticleSource.table_float_values(radius_scale) != [2.0]:
		return {"ready": false, "error": "Fire_00 light exponent/radius mismatch"}
	if not bool(light_props.get("bAffectsTranslucency", false)) or not bool(light_props.get("bHighQualityLights", false)) or bool(light_props.get("bUseInverseSquaredFalloff", true)):
		return {"ready": false, "error": "Fire_00 light flags mismatch"}

	var lod_nodes := ParticleSource.nodes_by_type(system, "ParticleLODLevel")
	var peaks: Array[int] = []
	var required_counts: Dictionary = {}
	for node: Dictionary in lod_nodes:
		var p := ParticleSource.properties(node)
		peaks.append(int(p.get("PeakActiveParticles", -1)))
		var required_key := _canonical(str(p.get("RequiredModule", "")))
		required_counts[required_key] = int(required_counts.get(required_key, 0)) + 1
	peaks.sort()
	if peaks != [3, 3, 5, 5, 7, 12, 12, 12, 25, 32, 52, 77]:
		return {"ready": false, "error": "Fire_00 LOD peaks mismatch " + str(peaks)}
	for required_path: String in required_paths:
		if int(required_counts.get(_canonical(required_path), 0)) != 2:
			return {"ready": false, "error": "Fire_00 LOD required mapping mismatch " + required_path}

	return {
		"ready": true,
		"systemPath": FIRE_00_SYSTEM,
		"emitterCount": 6,
		"lodCount": 12,
		"materialPaths": material_paths,
		"lifetimeRanges": lifetime_ranges,
		"spawnRates": spawn_rates,
		"dynamicModuleCount": 2,
		"dynamicParameterCount": 8,
		"particleLightCount": 1,
		"disabledSkelSurfaceCount": 1,
		"lodPeaks": peaks,
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
