extends SceneTree

const CascadeRuntime = preload("res://scripts/nacht_cascade_runtime.gd")
const ParticleSource = preload("res://scripts/nacht_particle_source.gd")

const SLICE_ROOT := "res://assets/benchmarks/nacht_particle_slice"
const GRAPHS_FILE := "particle-candidate-graphs.json"
const MATRIX_FILE := "particle-candidate-matrix.json"
const VISUAL_BRIDGED_TYPES := {
	"ParticleModuleRequired": true,
	"ParticleModuleSpawn": true,
	"ParticleModuleLifetime": true,
	"ParticleModuleSize": true,
	"ParticleModuleSizeMultiplyLife": true,
	"ParticleModuleSizeScaleBySpeed": true,
	"ParticleModuleVelocity": true,
	"ParticleModuleAcceleration": true,
	"ParticleModuleAccelerationConstant": true,
	"ParticleModuleRotation": true,
	"ParticleModuleRotation_Seeded": true,
	"ParticleModuleRotationRate": true,
	"ParticleModuleMeshMaterial": true,
	"ParticleModuleMeshRotation": true,
	"ParticleModuleMeshRotationRate": true,
	"ParticleModuleColor": true,
	"ParticleModuleColorOverLife": true,
	"ParticleModuleColorScaleOverLife": true,
	"ParticleModuleLocation": true,
	"ParticleModuleLocation_Seeded": true,
	"ParticleModuleLocationPrimitiveCylinder": true,
	"ParticleModuleLocationPrimitiveSphere": true,
	"ParticleModuleOrientationAxisLock": true,
	"ParticleModuleSubUV": true,
	"ParticleModuleSubUVMovie": true,
	"ParticleModulePivotOffset": true,
	"ParticleModuleTypeDataMesh": true,
	"ParticleModuleTypeDataGpu": true,
	"ParticleModuleTypeDataBeam2": true,
	"ParticleModuleBeamSource": true,
	"ParticleModuleBeamTarget": true,
}



func _init() -> void:
	call_deferred("_run")

func _read_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	return parsed as Dictionary if parsed is Dictionary else {}

func _canonical(raw: String) -> String:
	var value := raw.strip_edges().replace("\\", "/")
	if value.begins_with("Content/"):
		value = "/Game/" + value.substr(8)
	elif value.begins_with("Game/"):
		value = "/" + value
	return value.to_lower()

func _fail(message: String) -> void:
	push_error("NACHT_CASCADE_FAST_PROBE: " + message)
	quit(5)


func _find_system_canonical(graphs: Dictionary, system_path: String) -> Dictionary:
	var wanted := _canonical(system_path)
	for raw: Variant in graphs.get("systems", []):
		if not (raw is Dictionary):
			continue
		var row := raw as Dictionary
		if _canonical(str(row.get("objectPath", ""))) == wanted:
			return row
	return {}

func _lod_audit(graphs: Dictionary, system_path: String) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	var system := _find_system_canonical(graphs, system_path)
	for node: Dictionary in ParticleSource.nodes_by_type(system, "ParticleLODLevel"):
		var props := ParticleSource.properties(node)
		var modules: Array[String] = []
		var raw_modules: Variant = props.get("Modules", [])
		if raw_modules is Array:
			for raw: Variant in raw_modules:
				modules.append(str(raw))
		result.append({
			"node": str(node.get("objectPath", "")),
			"level": props.get("Level", null),
			"enabled": props.get("bEnabled", true),
			"peak": int(props.get("PeakActiveParticles", -1)),
			"required": str(props.get("RequiredModule", "")),
			"spawn": str(props.get("SpawnModule", "")),
			"typeData": str(props.get("TypeDataModule", "")),
			"modules": modules,
		})
	return result

func _node_by_path(system: Dictionary, object_path: String) -> Dictionary:
	var wanted := _canonical(object_path)
	for raw: Variant in system.get("nodes", []):
		if not (raw is Dictionary):
			continue
		var node := raw as Dictionary
		if _canonical(str(node.get("objectPath", ""))) == wanted:
			return node
	return {}


func _active_lod0_module_coverage(
	graphs: Dictionary,
	system_paths: Array[String]
) -> Dictionary:
	var bridged: Dictionary = {}
	var pending: Dictionary = {}
	var emitters := 0
	for system_path: String in system_paths:
		var system := _find_system_canonical(graphs, system_path)
		if system.is_empty():
			continue
		var best_by_emitter: Dictionary = {}
		for lod: Dictionary in ParticleSource.nodes_by_type(system, "ParticleLODLevel"):
			var props := ParticleSource.properties(lod)
			if not bool(props.get("bEnabled", true)):
				continue
			var lod_path := str(lod.get("objectPath", ""))
			var marker := lod_path.find(".ParticleLODLevel_")
			var emitter_key := lod_path.substr(0, marker) if marker >= 0 else lod_path
			var level := float(props.get("Level", 0.0))
			if not best_by_emitter.has(emitter_key) or level < float((best_by_emitter[emitter_key] as Dictionary).get("level", INF)):
				best_by_emitter[emitter_key] = {"level": level, "lod": lod}
		for emitter_key: String in best_by_emitter:
			emitters += 1
			var lod := (best_by_emitter[emitter_key] as Dictionary).get("lod", {}) as Dictionary
			var props := ParticleSource.properties(lod)
			var paths: Array[String] = []
			for direct_name: String in ["RequiredModule", "SpawnModule", "TypeDataModule"]:
				var direct_path := str(props.get(direct_name, ""))
				if not direct_path.is_empty():
					paths.append(direct_path)
			var raw_modules: Variant = props.get("Modules", [])
			if raw_modules is Array:
				for raw_path: Variant in raw_modules:
					paths.append(str(raw_path))
			for module_path: String in paths:
				var module := _node_by_path(system, module_path)
				if module.is_empty():
					continue
				var module_props := ParticleSource.properties(module)
				if not bool(module_props.get("bEnabled", true)):
					continue
				var export_type := str(module.get("exportType", ""))
				if export_type.is_empty():
					continue
				var bucket := bridged if VISUAL_BRIDGED_TYPES.has(export_type) else pending
				bucket[export_type] = int(bucket.get(export_type, 0)) + 1
	return {
		"emitters": emitters,
		"bridged": bridged,
		"pending": pending,
		"pendingTypeCount": pending.size(),
	}


func _run() -> void:
	var graphs := _read_json(SLICE_ROOT.path_join(GRAPHS_FILE))
	var matrix := _read_json(SLICE_ROOT.path_join(MATRIX_FILE))
	if graphs.is_empty() or matrix.is_empty():
		_fail("candidate slice missing")
		return

	var descriptors: Array[Dictionary] = [
		CascadeRuntime.mystery_vertical_descriptor(graphs),
		CascadeRuntime.big_fire_forward_descriptor(graphs),
		CascadeRuntime.bone_fire_2b_descriptor(graphs),
		CascadeRuntime.bone_fire_3_descriptor(graphs),
		CascadeRuntime.pap_wheel_descriptor(graphs),
		CascadeRuntime.mystery_box_fog_descriptor(graphs),
		CascadeRuntime.mystery_inside_descriptor(graphs),
		CascadeRuntime.big_fire_vg_smk_descriptor(graphs),
		CascadeRuntime.pap_wheel_out_descriptor(graphs),
		CascadeRuntime.electric_beam_descriptor(graphs),
		CascadeRuntime.acid_ball_descriptor(graphs),
		CascadeRuntime.sparks_small_descriptor(graphs),
		CascadeRuntime.quad_explode_smoke_descriptor(graphs),
		CascadeRuntime.monster_death_xl_descriptor(graphs),
		CascadeRuntime.fire_00_descriptor(graphs),
		CascadeRuntime.fire_14_descriptor(graphs),
	]

	var placement_by_path: Dictionary = {}
	for raw: Variant in matrix.get("systems", []):
		if not (raw is Dictionary):
			continue
		var row := raw as Dictionary
		placement_by_path[_canonical(str(row.get("systemPath", "")))] = int(
			row.get("placementCount", 0)
		)

	var total_placements := 0
	for descriptor: Dictionary in descriptors:
		if not bool(descriptor.get("ready", false)):
			_fail("descriptor RED: " + str(descriptor.get("error", "unknown")))
			return
		var key := _canonical(str(descriptor.get("systemPath", "")))
		if not placement_by_path.has(key):
			_fail("descriptor placement authority missing: " + key)
			return
		total_placements += int(placement_by_path[key])

	if descriptors.size() != 16:
		_fail("semantic system coverage mismatch " + str(descriptors.size()) + "/16")
		return
	if total_placements != 29:
		_fail("semantic placement coverage mismatch " + str(total_placements) + "/29")
		return

	var placed_paths: Array[String] = []
	for descriptor: Dictionary in descriptors:
		placed_paths.append(str(descriptor.get("systemPath", "")))
	var coverage := _active_lod0_module_coverage(graphs, placed_paths)
	print(
		"XZOGOT_NACHT_CASCADE_ACTIVE_LOD0_COVERAGE ",
		JSON.stringify(coverage)
	)

	print("XZOGOT_NACHT_CASCADE_LOD_AUDIT_FIRE00 ", JSON.stringify(
		_lod_audit(graphs, CascadeRuntime.FIRE_00_SYSTEM)
	))
	print("XZOGOT_NACHT_CASCADE_LOD_AUDIT_ACIDBALL ", JSON.stringify(
		_lod_audit(graphs, CascadeRuntime.ACID_BALL_SYSTEM)
	))
	print("XZOGOT_NACHT_CASCADE_LOD_AUDIT_MONSTER ", JSON.stringify(
		_lod_audit(graphs, CascadeRuntime.MONSTER_DEATH_XL_SYSTEM)
	))

	print(
		"XZOGOT_NACHT_CASCADE_FAST_SEMANTIC_GREEN systems=",
		descriptors.size(),
		" placements=",
		total_placements,
		" matrix_systems=",
		int(matrix.get("systemCount", -1))
	)
	quit(0)
