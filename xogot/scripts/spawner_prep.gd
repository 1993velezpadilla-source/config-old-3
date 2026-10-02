extends Node3D

const NAV_PATH := "res://data/nav_skeleton.json"
const GENERATED_PATH := "res://data/window_spawners.json"
const CHURCH_PATH := "res://assets/church/sanctum_current.glb"

func _ready() -> void:
	var windows := _load_or_derive()
	for w in windows:
		_add_socket(w)
	print("XZOGOT: %d window spawner sockets prepared; zombies disabled." % windows.size())

func _b2g(a: Array) -> Vector3:
	return Vector3(float(a[0]), float(a[2]), -float(a[1]))

func _load_or_derive() -> Array:
	if FileAccess.file_exists(GENERATED_PATH):
		var f := FileAccess.open(GENERATED_PATH, FileAccess.READ)
		var d = JSON.parse_string(f.get_as_text())
		if d is Dictionary and d.has("windows"):
			return d["windows"]

	var f := FileAccess.open(NAV_PATH, FileAccess.READ)
	if f == null:
		return []
	var nav = JSON.parse_string(f.get_as_text())
	if not nav is Dictionary:
		return []

	var nave := []
	for floor in nav.get("floors", []):
		if str(floor.get("id", "")).begins_with("nave_"):
			nave.append(floor)
	if nave.is_empty():
		return []
	var xmin := INF
	var xmax := -INF
	var ymin := INF
	var ymax := -INF
	var ztop := -INF
	for floor in nave:
		xmin = min(xmin, float(floor["min"][0]))
		xmax = max(xmax, float(floor["max"][0]))
		ymin = min(ymin, float(floor["min"][1]))
		ymax = max(ymax, float(floor["max"][1]))
		ztop = max(ztop, float(floor["max"][2]))

	var result := []
	for side_data in [["west", xmin, -1.0], ["east", xmax, 1.0]]:
		var side := str(side_data[0])
		var x := float(side_data[1])
		var nx := float(side_data[2])
		for i in range(4):
			var t := [0.18, 0.38, 0.62, 0.82][i]
			var y := lerp(ymin, ymax, t)
			var z := ztop + 1.28
			result.append({
				"id": "window_%s_%d" % [side, i + 1],
				"side": side,
				"barricade_center": [x, y, z],
				"normal": [nx, 0.0, 0.0],
				"outside_spawn": [x + nx * 2.6, y, z - 0.55],
				"outside_approach": [x + nx * 1.25, y, z - 0.55],
				"inside_player_side": [x - nx * 0.85, y, z - 0.55],
				"state": "prepared_no_zombies"
			})
	return result

func _add_socket(w: Dictionary) -> void:
	var marker := Marker3D.new()
	marker.name = str(w.get("id", "window"))
	marker.position = _b2g(w["barricade_center"])
	marker.set_meta("state", "prepared_no_zombies")
	marker.set_meta("outside_spawn", _b2g(w["outside_spawn"]))
	marker.set_meta("outside_approach", _b2g(w["outside_approach"]))
	marker.set_meta("inside_player_side", _b2g(w["inside_player_side"]))
	add_child(marker)

	# The detailed GLB already contains the boarded/stained visual. If it is
	# missing, provide a visible fallback so the socket is still obvious in Xogot.
	if ResourceLoader.exists(CHURCH_PATH):
		return
	var panel := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = Vector3(0.08, 1.7, 1.85)
	panel.mesh = box
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.08, 0.12, 0.28)
	mat.emission_enabled = true
	mat.emission = Color(0.04, 0.12, 0.52)
	mat.emission_energy_multiplier = 1.6
	panel.material_override = mat
	marker.add_child(panel)
