extends Node3D

func _ready() -> void:
	_build_environment()
	_build_site()
	_build_church()
	_build_interior()
	_build_windows()
	_build_lights()
	_build_camera()
	print("YOU_WONT_WIN: CHURCH_V2_READY")

func _build_environment() -> void:
	var world := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.006, 0.009, 0.016)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.16, 0.20, 0.30)
	env.ambient_light_energy = 0.42
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	world.environment = env
	add_child(world)
	var moon := DirectionalLight3D.new()
	moon.rotation_degrees = Vector3(-48, -32, 0)
	moon.light_color = Color(0.48, 0.60, 1.0)
	moon.light_energy = 1.25
	moon.shadow_enabled = true
	add_child(moon)

func _build_site() -> void:
	_box("Ground", Vector3(72, 0.5, 84), Vector3(0, -0.25, -4), Color(0.035, 0.04, 0.045))
	_box("ChurchFloor", Vector3(22, 0.45, 38), Vector3(0, 0.22, -5), Color(0.12, 0.105, 0.085))
	_box("FrontWalk", Vector3(6, 0.20, 14), Vector3(0, 0.10, 21), Color(0.13, 0.13, 0.135))
	for i in range(4):
		_box("Step%d" % i, Vector3(7.0 - i * 0.35, 0.22, 1.15), Vector3(0, 0.11 + i * 0.20, 14.8 - i * 0.8), Color(0.18, 0.18, 0.17))

func _build_church() -> void:
	var stone := Color(0.20, 0.19, 0.175)
	var dark_stone := Color(0.135, 0.13, 0.125)
	# nave shell, with openings instead of solid featureless walls
	_box("LeftWall", Vector3(0.65, 8.2, 38), Vector3(-11, 4.1, -5), stone)
	_box("RightWall", Vector3(0.65, 8.2, 38), Vector3(11, 4.1, -5), stone)
	_box("RearWall", Vector3(22, 8.2, 0.65), Vector3(0, 4.1, -24), stone)
	_box("FrontLeft", Vector3(7.8, 8.2, 0.65), Vector3(-7.1, 4.1, 14), stone)
	_box("FrontRight", Vector3(7.8, 8.2, 0.65), Vector3(7.1, 4.1, 14), stone)
	_box("FrontLintel", Vector3(6.4, 2.0, 0.8), Vector3(0, 7.2, 14), dark_stone)
	# buttresses give the exterior an actual church silhouette
	var buttress_z: Array[float] = [-19.0, -11.0, -3.0, 5.0, 12.0]
	for z: float in buttress_z:
		_box("ButtressL", Vector3(1.15, 6.2, 1.55), Vector3(-11.45, 3.1, z), dark_stone)
		_box("ButtressR", Vector3(1.15, 6.2, 1.55), Vector3(11.45, 3.1, z), dark_stone)
	# front tower
	_box("TowerBase", Vector3(7.0, 10.5, 6.0), Vector3(0, 5.25, 10.7), dark_stone)
	_box("TowerUpper", Vector3(5.4, 4.0, 5.0), Vector3(0, 12.5, 10.7), stone)
	# pitched nave roof
	_wedge_roof("RoofLeft", Vector3(-5.55, 9.9, -5), -20.0, Color(0.055, 0.06, 0.07))
	_wedge_roof("RoofRight", Vector3(5.55, 9.9, -5), 20.0, Color(0.055, 0.06, 0.07))
	# tower cap
	_wedge_roof("TowerRoofL", Vector3(-1.4, 15.0, 10.7), -28.0, Color(0.04, 0.045, 0.052), Vector3(3.3, 0.35, 6.2))
	_wedge_roof("TowerRoofR", Vector3(1.4, 15.0, 10.7), 28.0, Color(0.04, 0.045, 0.052), Vector3(3.3, 0.35, 6.2))

func _build_interior() -> void:
	var wood := Color(0.16, 0.095, 0.055)
	# center aisle + raised altar
	_box("Aisle", Vector3(3.2, 0.05, 30), Vector3(0, 0.48, -3), Color(0.20, 0.18, 0.145))
	_box("AltarPlatform", Vector3(12, 0.55, 5.5), Vector3(0, 0.55, -20.5), Color(0.15, 0.13, 0.105))
	_box("Altar", Vector3(4.8, 1.25, 1.5), Vector3(0, 1.45, -21.2), Color(0.30, 0.27, 0.21))
	# pew rows leave a central combat lane
	for z in range(-15, 8, 4):
		_pew(Vector3(-5.6, 0.75, float(z)), wood)
		_pew(Vector3(5.6, 0.75, float(z)), wood)
	# upper rear balcony / second-floor gameplay shell
	_box("Balcony", Vector3(20.5, 0.5, 6.0), Vector3(0, 5.0, 10.4), Color(0.11, 0.075, 0.045))
	_box("BalconyRail", Vector3(20.0, 1.15, 0.25), Vector3(0, 5.8, 7.55), wood)
	_box("StairLanding", Vector3(4.0, 0.45, 4.0), Vector3(-8.0, 2.65, 8.0), wood)
	for i in range(8):
		_box("Stair%d" % i, Vector3(3.2, 0.30, 1.0), Vector3(-8.0, 0.55 + i * 0.55, 3.0 + i * 0.62), wood)

func _build_windows() -> void:
	var glow := Color(0.24, 0.34, 0.48)
	var zs: Array[float] = [-17.0, -9.0, -1.0, 7.0]
	for i in range(zs.size()):
		var z: float = zs[i]
		_box("WindowL_%d" % i, Vector3(0.10, 3.1, 2.0), Vector3(-10.64, 4.2, z), glow, false)
		_box("WindowR_%d" % i, Vector3(0.10, 3.1, 2.0), Vector3(10.64, 4.2, z), glow, false)
		# barricade boards mark future zombie entry/spawn gameplay points
		for b in range(3):
			_box("BarricadeL_%d_%d" % [i,b], Vector3(0.18, 0.28, 2.5), Vector3(-10.52, 3.4 + b * 0.75, z), Color(0.22, 0.12, 0.055), false)
			_box("BarricadeR_%d_%d" % [i,b], Vector3(0.18, 0.28, 2.5), Vector3(10.52, 3.4 + b * 0.75, z), Color(0.22, 0.12, 0.055), false)

func _build_lights() -> void:
	var light_z: Array[float] = [-17.0, -7.0, 3.0, 10.0]
	for z: float in light_z:
		var lamp := OmniLight3D.new()
		lamp.position = Vector3(0, 4.2, z)
		lamp.light_color = Color(1.0, 0.56, 0.27)
		lamp.light_energy = 2.0
		lamp.omni_range = 8.5
		lamp.shadow_enabled = true
		add_child(lamp)

func _build_camera() -> void:
	if get_viewport().get_camera_3d() != null:
		return
	var camera := Camera3D.new()
	camera.name = "PreviewCamera"
	camera.position = Vector3(0, 7.8, 31)
	camera.rotation_degrees = Vector3(-8, 0, 0)
	camera.fov = 68
	camera.current = true
	add_child(camera)

func _pew(pos: Vector3, color: Color) -> void:
	_box("PewSeat", Vector3(6.2, 0.35, 1.05), pos, color)
	_box("PewBack", Vector3(6.2, 1.35, 0.22), pos + Vector3(0, 0.72, 0.42), color)
	_box("PewLegL", Vector3(0.28, 0.8, 0.8), pos + Vector3(-2.6, -0.35, 0), color)
	_box("PewLegR", Vector3(0.28, 0.8, 0.8), pos + Vector3(2.6, -0.35, 0), color)

func _wedge_roof(label: String, pos: Vector3, roll: float, color: Color, size: Vector3 = Vector3(11.8, 0.45, 39.0)) -> void:
	var body := StaticBody3D.new()
	body.name = label
	body.position = pos
	body.rotation_degrees.z = roll
	var mi := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = size
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.roughness = 0.92
	mesh.material = mat
	mi.mesh = mesh
	body.add_child(mi)
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	cs.shape = shape
	body.add_child(cs)
	add_child(body)

func _box(label: String, size: Vector3, pos: Vector3, color: Color, collision: bool = true) -> void:
	var root: Node3D
	if collision:
		var body := StaticBody3D.new()
		root = body
	else:
		root = Node3D.new()
	root.name = label
	root.position = pos
	var mi := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = size
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.roughness = 0.86
	mesh.material = mat
	mi.mesh = mesh
	root.add_child(mi)
	if collision:
		var cs := CollisionShape3D.new()
		var shape := BoxShape3D.new()
		shape.size = size
		cs.shape = shape
		root.add_child(cs)
	add_child(root)
