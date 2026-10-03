extends Node3D

const NAV_PATH := "res://data/nav_skeleton.json"
const CHURCH_PATH := "res://assets/church/sanctum_current.glb"

var _show_fallback_visuals := true
var _stone_mat: StandardMaterial3D
var _wood_mat: StandardMaterial3D
var _exterior_mat: StandardMaterial3D
var _ramp_mat: StandardMaterial3D

func _ready() -> void:
	_show_fallback_visuals = not ResourceLoader.exists(CHURCH_PATH)
	_make_materials()
	_build()

func _make_materials() -> void:
	_stone_mat = _mat(Color(0.16, 0.13, 0.12), 0.92)
	_wood_mat = _mat(Color(0.12, 0.045, 0.018), 0.78)
	_exterior_mat = _mat(Color(0.10, 0.12, 0.14), 0.96)
	_ramp_mat = _mat(Color(0.20, 0.16, 0.13), 0.86)

func _mat(color: Color, roughness: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = roughness
	return m

func _read_nav() -> Dictionary:
	var f := FileAccess.open(NAV_PATH, FileAccess.READ)
	if f == null:
		push_error("XZOGOT: nav skeleton missing")
		return {}
	var parsed = JSON.parse_string(f.get_as_text())
	return parsed if parsed is Dictionary else {}

func _b2g(a: Array) -> Vector3:
	return Vector3(float(a[0]), float(a[2]), -float(a[1]))

func _converted_aabb(mn: Array, mx: Array) -> AABB:
	var points: Array[Vector3] = []
	for x in [float(mn[0]), float(mx[0])]:
		for y in [float(mn[1]), float(mx[1])]:
			for z in [float(mn[2]), float(mx[2])]:
				points.append(_b2g([x, y, z]))
	var lo := Vector3(INF, INF, INF)
	var hi := Vector3(-INF, -INF, -INF)
	for p in points:
		lo.x = min(lo.x, p.x)
		lo.y = min(lo.y, p.y)
		lo.z = min(lo.z, p.z)
		hi.x = max(hi.x, p.x)
		hi.y = max(hi.y, p.y)
		hi.z = max(hi.z, p.z)
	return AABB(lo, hi - lo)

func _add_box(id: String, center: Vector3, size: Vector3, material: Material, visible_mesh: bool = true, yaw: float = 0.0) -> Node3D:
	var root := Node3D.new()
	root.name = id
	root.position = center
	root.rotation.y = yaw
	add_child(root)

	var body := StaticBody3D.new()
	body.name = "Collision"
	root.add_child(body)
	var shape_node := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = Vector3(max(size.x, 0.02), max(size.y, 0.02), max(size.z, 0.02))
	shape_node.shape = shape
	body.add_child(shape_node)

	if visible_mesh and _show_fallback_visuals:
		var mesh_node := MeshInstance3D.new()
		mesh_node.name = "FallbackVisual"
		var box := BoxMesh.new()
		box.size = shape.size
		mesh_node.mesh = box
		mesh_node.material_override = material
		mesh_node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		root.add_child(mesh_node)
	return root

func _build() -> void:
	var nav := _read_nav()
	if nav.is_empty():
		return

	for floor in nav.get("floors", []):
		var box := _converted_aabb(floor["min"], floor["max"])
		var id := str(floor.get("id", "floor"))
		var mat: Material = _stone_mat
		if id.begins_with("exterior_"):
			mat = _exterior_mat
		elif id == "upper_full_deck":
			mat = _wood_mat
		_add_box("Floor_" + id, box.get_center(), box.size, mat, true)

	for ramp in nav.get("ramps", []):
		_build_ramp(ramp)

func _build_ramp(ramp: Dictionary) -> void:
	var low := _b2g(ramp["low"])
	var high := _b2g(ramp["high"])
	if high.y < low.y:
		var swap := low
		low = high
		high = swap

	var horizontal := Vector3(high.x - low.x, 0.0, high.z - low.z)
	var total_len: float = maxf(horizontal.length(), 0.01)
	var direction := horizontal.normalized()
	var requested: int = maxi(int(ramp.get("steps", 12)), 12)
	var vertical: float = high.y - low.y
	var steps: int = maxi(requested, int(ceil(absf(vertical) / 0.30)))
	var seg_len: float = total_len / float(steps)
	var width: float = float(ramp.get("width_m", 1.5))
	var yaw: float = atan2(direction.x, direction.z)
	var base_y: float = low.y - 0.12

	for i in range(steps):
		var t0: float = float(i) / float(steps)
		var t1: float = float(i + 1) / float(steps)
		var p0 := low.lerp(high, t0)
		var p1 := low.lerp(high, t1)
		var top_y: float = p1.y
		var height: float = maxf(0.08, top_y - base_y)
		var mid := Vector3((p0.x + p1.x) * 0.5, base_y + height * 0.5, (p0.z + p1.z) * 0.5)
		_add_box(
			"Ramp_%s_%02d" % [str(ramp.get("id", "ramp")), i],
			mid,
			Vector3(width, height, seg_len + 0.06),
			_ramp_mat,
			true,
			yaw
		)
