extends Node3D

func _ready() -> void:
	_build_environment()
	_build_site()
	_build_church()
	_build_interior()
	_build_interactions()
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
	# Nave shell. Side walls are segmented around four real zombie-window apertures
	# per side; no invisible solid wall remains behind the barricades.
	_build_side_wall_with_window_openings(-11.0, "L", stone, dark_stone)
	_build_side_wall_with_window_openings(11.0, "R", stone, dark_stone)
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

func _build_side_wall_with_window_openings(x: float, side: String, stone: Color, trim: Color) -> void:
	var wall_min_z: float = -24.0
	var wall_max_z: float = 14.0
	var opening_half_width: float = 1.40
	var opening_top_y: float = 3.35
	var wall_top_y: float = 8.20
	var centers: Array[float] = [-17.0, -9.0, -1.0, 7.0]

	var cursor_z: float = wall_min_z
	for i in range(centers.size()):
		var center_z: float = centers[i]
		var opening_min_z: float = center_z - opening_half_width
		var opening_max_z: float = center_z + opening_half_width
		var segment_len: float = opening_min_z - cursor_z
		if segment_len > 0.01:
			_box(
				"SideWall_%s_%02d" % [side, i],
				Vector3(0.65, wall_top_y, segment_len),
				Vector3(x, wall_top_y * 0.5, cursor_z + segment_len * 0.5),
				stone
			)

		# Stone lintel above each walk-through zombie window.
		var lintel_height: float = wall_top_y - opening_top_y
		_box(
			"WindowLintel_%s_%02d" % [side, i],
			Vector3(0.65, lintel_height, opening_half_width * 2.0),
			Vector3(x, opening_top_y + lintel_height * 0.5, center_z),
			stone
		)

		# Thin jamb trim makes the aperture readable from inside and outside.
		_box(
			"WindowJambA_%s_%02d" % [side, i],
			Vector3(0.82, opening_top_y, 0.18),
			Vector3(x, opening_top_y * 0.5, opening_min_z),
			trim
		)
		_box(
			"WindowJambB_%s_%02d" % [side, i],
			Vector3(0.82, opening_top_y, 0.18),
			Vector3(x, opening_top_y * 0.5, opening_max_z),
			trim
		)
		cursor_z = opening_max_z

	var tail_len: float = wall_max_z - cursor_z
	if tail_len > 0.01:
		_box(
			"SideWall_%s_tail" % side,
			Vector3(0.65, wall_top_y, tail_len),
			Vector3(x, wall_top_y * 0.5, cursor_z + tail_len * 0.5),
			stone
		)

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

	# Balcony rail has a real opening aligned with the stair exit at x=-8.
	_box("BalconyRailMain", Vector3(15.8, 1.15, 0.25), Vector3(2.1, 5.8, 7.55), wood)
	_box("BalconyRailLeft", Vector3(1.3, 1.15, 0.25), Vector3(-10.35, 5.8, 7.55), wood)

	# Visual stairs stay crisp, while one continuous hidden ramp provides reliable
	# CharacterBody3D traversal to the balcony on touch/mobile.
	for i in range(12):
		_box(
			"Stair%d" % i,
			Vector3(3.2, 0.30, 0.68),
			Vector3(-8.0, 0.62 + float(i) * 0.37, 2.65 + float(i) * 0.52),
			wood,
			false
		)
	_box("StairTopLanding", Vector3(3.4, 0.30, 2.2), Vector3(-8.0, 5.05, 9.0), wood, false)
	_build_balcony_stair_ramp()

func _build_balcony_stair_ramp() -> void:
	var start := Vector3(-8.0, 0.46, 2.30)
	var finish := Vector3(-8.0, 5.02, 8.85)
	var run: float = finish.z - start.z
	var rise: float = finish.y - start.y
	var slope_length: float = sqrt(run * run + rise * rise)
	var angle_deg: float = rad_to_deg(atan(rise / run))

	var ramp := StaticBody3D.new()
	ramp.name = "BalconyStairRamp"
	ramp.position = (start + finish) * 0.5
	ramp.rotation_degrees.x = -angle_deg
	ramp.add_to_group("walkable_stair_ramp")

	var collision := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = Vector3(3.0, 0.16, slope_length)
	collision.shape = shape
	ramp.add_child(collision)
	add_child(ramp)

	print("XZOGOT_BALCONY_RAMP_READY ", angle_deg)

func _build_interactions() -> void:
	# Generic interaction kinds: 0 door, 1 wallbuy, 2 mystery, 3 perk, 4 power.
	_interactive_box("RearDoor", Vector3(3.4, 3.8, 0.35), Vector3(0, 1.9, -18.2), Color(0.12, 0.07, 0.035), 0, 750, 0, true, "OPEN REAR DOOR")
	_interactive_box("BalconyGate", Vector3(3.5, 2.2, 0.30), Vector3(-8.0, 6.0, 7.45), Color(0.13, 0.075, 0.04), 0, 1000, 0, true, "OPEN BALCONY")
	_interactive_box("WallBuy_01", Vector3(0.28, 1.8, 1.7), Vector3(-10.45, 1.7, -5.0), Color(0.16, 0.42, 0.62), 1, 500, 60, false, "BUY AMMO")
	_interactive_box("MysteryBoxSocket", Vector3(2.2, 1.4, 1.1), Vector3(7.4, 0.9, -15.0), Color(0.18, 0.12, 0.30), 2, 950, 0, false, "MYSTERY BOX")
	_interactive_box("PerkSocket", Vector3(1.2, 2.0, 1.2), Vector3(-7.4, 1.2, -15.2), Color(0.42, 0.11, 0.09), 3, 2500, 0, true, "PERK")
	_interactive_box("PowerSwitch", Vector3(0.7, 2.2, 0.7), Vector3(8.6, 1.4, 8.3), Color(0.52, 0.42, 0.12), 4, 0, 0, true, "TURN ON POWER")
	print("XZOGOT_INTERACTIONS_PREPARED 6")

func _interactive_box(label: String, size: Vector3, pos: Vector3, color: Color, kind: int, price: int, reward: int, one_shot: bool, prompt: String) -> void:
	var script_resource: Script = load("res://scripts/interactable.gd") as Script
	var body := StaticBody3D.new()
	body.name = label
	body.position = pos
	body.set_script(script_resource)
	body.set("interaction_kind", kind)
	body.set("price", price)
	body.set("reward_amount", reward)
	body.set("one_shot", one_shot)
	body.set("prompt_text", prompt)
	body.add_to_group("zombie_interactable")

	var mi := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = size
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.roughness = 0.74
	mat.metallic = 0.06
	mesh.material = mat
	mi.mesh = mesh
	body.add_child(mi)

	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	cs.shape = shape
	body.add_child(cs)
	add_child(body)

func _build_windows() -> void:
	var glow := Color(0.24, 0.34, 0.48)
	var zs: Array[float] = [-17.0, -9.0, -1.0, 7.0]
	var window_id: int = 0
	for i in range(zs.size()):
		var z: float = zs[i]
		# A faint non-colliding back glow marks the aperture; the opening itself is real.
		_box("WindowGlowL_%d" % i, Vector3(0.03, 2.25, 2.35), Vector3(-11.34, 1.55, z), Color(glow.r, glow.g, glow.b, 0.22), false)
		_box("WindowGlowR_%d" % i, Vector3(0.03, 2.25, 2.35), Vector3(11.34, 1.55, z), Color(glow.r, glow.g, glow.b, 0.22), false)
		_add_window_threshold_ramp("L", -1.0, i, z)
		_add_window_socket(window_id, "left", z)
		window_id += 1
		_add_window_threshold_ramp("R", 1.0, i, z)
		_add_window_socket(window_id, "right", z)
		window_id += 1
	print("XZOGOT_WINDOWS_PREPARED ", window_id)

func _add_window_threshold_ramp(side: String, sx: float, index: int, z: float) -> void:
	# Exterior ground is y=0 while the church floor top is ~0.445 m.
	# A shallow physical ramp lets CharacterBody3D zombies and players cross without teleport/stair hacks.
	var run: float = 2.40
	var rise: float = 0.45
	var angle_rad: float = atan(rise / run)
	var angle_deg: float = rad_to_deg(angle_rad)
	var body := StaticBody3D.new()
	body.name = "WindowRamp_%s_%02d" % [side, index]
	body.position = Vector3(10.90 * sx, 0.225, z)
	body.rotation_degrees.z = -sx * angle_deg

	var mesh_instance := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = Vector3(run, 0.16, 2.30)
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.16, 0.15, 0.13)
	mat.roughness = 0.92
	mesh.material = mat
	mesh_instance.mesh = mesh
	body.add_child(mesh_instance)

	var collision := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = Vector3(run, 0.16, 2.30)
	collision.shape = shape
	body.add_child(collision)
	body.add_to_group("zombie_window_ramp")
	add_child(body)

func _add_window_socket(window_id: int, side: String, z: float) -> void:
	var left: bool = side == "left"
	var sx: float = -1.0 if left else 1.0
	var barricade_x: float = 10.52 * sx
	var outside_spawn := Vector3(13.0 * sx, 0.55, z)
	var outside_approach := Vector3(11.45 * sx, 0.55, z)
	var inside_point := Vector3(9.72 * sx, 0.55, z)

	var marker := Marker3D.new()
	marker.name = "ZombieWindow_%02d" % window_id
	marker.position = Vector3(12.0 * sx, 0.55, z)
	marker.add_to_group("zombie_window")
	marker.set_meta("window_id", window_id)
	marker.set_meta("side", side)
	marker.set_meta("status", "ACTIVE_BARRICADE")
	marker.set_meta("outside_spawn", outside_spawn)
	marker.set_meta("outside_approach", outside_approach)
	marker.set_meta("inside_point", inside_point)
	add_child(marker)

	var script_resource: Script = load("res://scripts/barricade.gd") as Script
	var barricade := StaticBody3D.new()
	barricade.name = "Barricade_%02d" % window_id
	barricade.position = Vector3(barricade_x, 1.55, z)
	barricade.set_script(script_resource)
	barricade.set_meta("window_id", window_id)
	barricade.set_meta("side", side)
	barricade.set_meta("outside_spawn", outside_spawn)
	barricade.set_meta("outside_approach", outside_approach)
	barricade.set_meta("inside_point", inside_point)
	add_child(barricade)

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
