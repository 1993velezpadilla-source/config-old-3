extends SceneTree

const CascadeRuntime = preload("res://scripts/nacht_cascade_runtime.gd")

const SLICE_ROOT := "res://assets/benchmarks/nacht_particle_slice"
const GRAPHS_FILE := "particle-candidate-graphs.json"
const MATRIX_FILE := "particle-candidate-matrix.json"

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

	if descriptors.size() != 10:
		_fail("semantic system coverage mismatch " + str(descriptors.size()) + "/10")
		return
	if total_placements != 19:
		_fail("semantic placement coverage mismatch " + str(total_placements) + "/19")
		return

	print(
		"XZOGOT_NACHT_CASCADE_FAST_SEMANTIC_GREEN systems=",
		descriptors.size(),
		" placements=",
		total_placements,
		" matrix_systems=",
		int(matrix.get("systemCount", -1))
	)
	quit(0)
