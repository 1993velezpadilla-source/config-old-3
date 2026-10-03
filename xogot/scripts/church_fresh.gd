extends Node3D

# XZOMBIE fresh Godot/Xogot church.
# Gameplay coordinates still come from nav_skeleton.json; this layer is visual architecture only.

var stone: StandardMaterial3D
var stone_dark: StandardMaterial3D
var wood: StandardMaterial3D
var wood_dark: StandardMaterial3D
var metal: StandardMaterial3D
var glass: StandardMaterial3D
var plaster: StandardMaterial3D
var altar_mat: StandardMaterial3D

func _ready() -> void:
	_make_materials()
	_build_shell()
	_build_nave()
	_build_upper_gallery()
	_build_altar()
	_build_windows()
	_build_pews()
	_build_exterior()
	print("XZOGOT: fresh native church V1 built; legacy Quake visuals disabled.")

func _material(color: Color, rough: float, metallic_value: float = 0.0) -> StandardMaterial3D:
	var m: StandardMaterial3D = StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = rough
	m.metallic = metallic_value
	return m

func _make_materials() -> void:
	stone = _material(Color(0.25, 0.22, 0.19), 0.88)
	stone_dark = _material(Color(0.095, 0.085, 0.08), 0.94)
	wood = _material(Color(0.20, 0.075, 0.028), 0.72)
	wood_dark = _material(Color(0.075, 0.027, 0.012), 0.82)
	metal = _material(Color(0.07, 0.075, 0.08), 0.42, 0.72)
	plaster = _material(Color(0.30, 0.285, 0.265), 0.96)
	altar_mat = _material(Color(0.36, 0.32, 0.27), 0.78)
	glass = _material(Color(0.035, 0.095, 0.16, 0.42), 0.18)
	glass.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	glass.metallic = 0.18

func _box(name_text: String, pos: Vector3, size: Vector3, mat: Material, yaw: float = 0.0) -> MeshInstance3D:
	var node: MeshInstance3D = MeshInstance3D.new()
	node.name = name_text
	var mesh: BoxMesh = BoxMesh.new()
	mesh.size = size
	node.mesh = mesh
	node.position = pos
	node.rotation.y = yaw
	node.material_override = mat
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	add_child(node)
	return node

func _cylinder(name_text: String, pos: Vector3, radius: float, height: float, mat: Material, sides: int = 16) -> MeshInstance3D:
	var node: MeshInstance3D = MeshInstance3D.new()
	node.name = name_text
	var mesh: CylinderMesh = CylinderMesh.new()
	mesh.top_radius = radius
	mesh.bottom_radius = radius
	mesh.height = height
	mesh.radial_segments = sides
	node.mesh = mesh
	node.position = pos
	node.material_override = mat
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	add_child(node)
	return node

func _build_shell() -> void:
	# Nave centered on the gameplay skeleton: x ~ -17.8, z ~ 27.3.
	var cx: float = -17.81
	var cz: float = 27.35
	_box("NaveFloor", Vector3(cx, -0.34, cz), Vector3(14.7, 0.28, 24.8), stone_dark)
	_box("LeftWall", Vector3(-25.0, 3.65, cz), Vector3(0.42, 8.0, 24.8), stone)
	_box("RightWall", Vector3(-10.62, 3.65, cz), Vector3(0.42, 8.0, 24.8), stone)
	_box("FrontWallL", Vector3(-22.0, 3.65, 39.55), Vector3(5.6, 8.0, 0.42), stone)
	_box("FrontWallR", Vector3(-13.62, 3.65, 39.55), Vector3(5.6, 8.0, 0.42), stone)
	_box("FrontHeader", Vector3(cx, 6.55, 39.55), Vector3(2.9, 2.2, 0.42), stone)
	_box("RearWall", Vector3(cx, 3.65, 15.15), Vector3(14.7, 8.0, 0.42), stone)
	# Timber roof planes give the nave a high, non-Quake silhouette.
	var left_roof: MeshInstance3D = _box("RoofLeft", Vector3(-21.4, 8.25, cz), Vector3(7.9, 0.30, 25.4), wood_dark)
	left_roof.rotation.z = deg_to_rad(-19.0)
	var right_roof: MeshInstance3D = _box("RoofRight", Vector3(-14.22, 8.25, cz), Vector3(7.9, 0.30, 25.4), wood_dark)
	right_roof.rotation.z = deg_to_rad(19.0)
	_box("RoofRidge", Vector3(cx, 9.48, cz), Vector3(0.34, 0.34, 25.6), metal)

func _build_nave() -> void:
	var z_values: Array[float] = [18.0, 22.0, 26.0, 30.0, 34.0]
	for z_pos: float in z_values:
		_cylinder("ColumnL_%d" % int(z_pos), Vector3(-22.75, 2.75, z_pos), 0.34, 5.5, stone, 12)
		_cylinder("ColumnR_%d" % int(z_pos), Vector3(-12.87, 2.75, z_pos), 0.34, 5.5, stone, 12)
		_box("Beam_%d" % int(z_pos), Vector3(-17.81, 6.75, z_pos), Vector3(10.4, 0.30, 0.32), wood_dark)
		var brace_l: MeshInstance3D = _box("BraceL_%d" % int(z_pos), Vector3(-20.35, 7.25, z_pos), Vector3(5.4, 0.22, 0.24), wood)
		brace_l.rotation.z = deg_to_rad(-25.0)
		var brace_r: MeshInstance3D = _box("BraceR_%d" % int(z_pos), Vector3(-15.27, 7.25, z_pos), Vector3(5.4, 0.22, 0.24), wood)
		brace_r.rotation.z = deg_to_rad(25.0)
	# Central aisle inset.
	_box("Aisle", Vector3(-17.81, -0.16, 27.4), Vector3(2.65, 0.08, 20.5), plaster)

func _build_upper_gallery() -> void:
	_box("GalleryDeck", Vector3(-17.81, 3.36, 27.6), Vector3(10.7, 0.28, 9.2), wood_dark)
	_box("GalleryFrontRail", Vector3(-17.81, 4.22, 32.1), Vector3(10.7, 0.18, 0.18), wood)
	for x_pos: float in [-22.7, -21.4, -20.1, -18.8, -17.5, -16.2, -14.9, -13.6, -12.9]:
		_box("GalleryBaluster", Vector3(x_pos, 3.82, 32.1), Vector3(0.10, 0.82, 0.10), wood)

func _build_altar() -> void:
	_box("ChancelStep1", Vector3(-17.81, 0.02, 16.9), Vector3(8.4, 0.34, 3.0), stone)
	_box("ChancelStep2", Vector3(-17.81, 0.24, 16.25), Vector3(6.8, 0.30, 1.8), stone)
	_box("AltarBase", Vector3(-17.81, 0.72, 15.82), Vector3(3.7, 0.75, 1.25), altar_mat)
	_box("AltarTop", Vector3(-17.81, 1.16, 15.82), Vector3(4.15, 0.16, 1.48), stone)
	_box("Reredos", Vector3(-17.81, 3.15, 15.42), Vector3(5.8, 3.8, 0.36), stone_dark)
	_box("CrossV", Vector3(-17.81, 3.55, 15.18), Vector3(0.22, 2.1, 0.16), metal)
	_box("CrossH", Vector3(-17.81, 3.82, 15.18), Vector3(1.15, 0.22, 0.16), metal)
	for x_pos: float in [-19.35, -18.55, -17.07, -16.27]:
		_cylinder("AltarCandle_%d" % int((x_pos + 20.0) * 100.0), Vector3(x_pos, 1.52, 15.62), 0.045, 0.55, plaster, 10)

func _build_windows() -> void:
	var z_values: Array[float] = [19.0, 24.0, 29.0, 34.0]
	var index: int = 0
	for z_pos: float in z_values:
		for x_pos: float in [-24.76, -10.86]:
			var pane: MeshInstance3D = _box("Window_%02d" % index, Vector3(x_pos, 3.35, z_pos), Vector3(0.08, 2.7, 1.55), glass)
			pane.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			_box("WindowSill_%02d" % index, Vector3(x_pos, 1.93, z_pos), Vector3(0.55, 0.18, 1.85), stone_dark)
			_box("WindowBarV_%02d" % index, Vector3(x_pos, 3.35, z_pos), Vector3(0.12, 2.75, 0.10), metal)
			_box("WindowBarH_%02d" % index, Vector3(x_pos, 3.35, z_pos), Vector3(0.12, 0.10, 1.58), metal)
			index += 1

func _build_pews() -> void:
	var z_values: Array[float] = [20.0, 22.0, 24.0, 26.0, 28.0, 30.0, 32.0, 34.0]
	var row: int = 0
	for z_pos: float in z_values:
		_pew("PewL_%02d" % row, Vector3(-20.45, 0.34, z_pos), 3.25)
		_pew("PewR_%02d" % row, Vector3(-15.17, 0.34, z_pos), 3.25)
		row += 1

func _pew(name_text: String, pos: Vector3, width: float) -> void:
	_box(name_text + "_Seat", pos, Vector3(width, 0.18, 0.55), wood)
	_box(name_text + "_Back", pos + Vector3(0.0, 0.52, 0.24), Vector3(width, 0.86, 0.16), wood_dark)
	_box(name_text + "_LegL", pos + Vector3(-width * 0.42, -0.27, 0.0), Vector3(0.14, 0.55, 0.45), wood_dark)
	_box(name_text + "_LegR", pos + Vector3(width * 0.42, -0.27, 0.0), Vector3(0.14, 0.55, 0.45), wood_dark)

func _build_exterior() -> void:
	_box("ExteriorGround", Vector3(-17.81, -0.58, 27.3), Vector3(43.0, 0.24, 55.0), stone_dark)
	# Buttresses break up the flat exterior walls.
	for z_pos: float in [17.5, 22.5, 27.5, 32.5, 37.5]:
		_box("ButtressL_%d" % int(z_pos), Vector3(-25.45, 2.0, z_pos), Vector3(0.9, 4.2, 0.85), stone_dark)
		_box("ButtressR_%d" % int(z_pos), Vector3(-10.17, 2.0, z_pos), Vector3(0.9, 4.2, 0.85), stone_dark)
	# Front entrance depth + steps.
	_box("PorchTop", Vector3(-17.81, 6.45, 40.45), Vector3(5.1, 0.45, 2.1), stone_dark)
	_box("PorchPostL", Vector3(-20.05, 3.0, 40.45), Vector3(0.55, 6.0, 0.55), stone)
	_box("PorchPostR", Vector3(-15.57, 3.0, 40.45), Vector3(0.55, 6.0, 0.55), stone)
	_box("DoorL", Vector3(-18.65, 2.05, 39.82), Vector3(1.55, 4.1, 0.18), wood_dark)
	_box("DoorR", Vector3(-16.97, 2.05, 39.82), Vector3(1.55, 4.1, 0.18), wood_dark)
	for step_i: int in range(4):
		var step_width: float = 6.4 - float(step_i) * 0.45
		_box("FrontStep_%02d" % step_i, Vector3(-17.81, -0.36 + float(step_i) * 0.16, 42.0 - float(step_i) * 0.32), Vector3(step_width, 0.20, 1.15), stone)
