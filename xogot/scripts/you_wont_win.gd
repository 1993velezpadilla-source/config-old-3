extends Node3D

const WORLD_SCALE: float = 0.78

var _stone_texture: Texture2D
var _wood_texture: Texture2D
var _floor_texture: Texture2D

func _wp(v: Vector3) -> Vector3:
	return v * WORLD_SCALE

func _ws(v: Vector3) -> Vector3:
	return v * WORLD_SCALE


func _hash_noise(x: int, y: int, seed: int) -> float:
	var v: float = sin(float(x * 127 + y * 311 + seed * 71)) * 43758.5453
	return v - floor(v)

func _make_grain_texture(kind: String) -> Texture2D:
	var tex_size: int = 64
	var image := Image.create(tex_size, tex_size, false, Image.FORMAT_RGBA8)
	var seed: int = 17 if kind == "stone" else (41 if kind == "wood" else 83)

	for y in range(tex_size):
		for x in range(tex_size):
			var noise: float = _hash_noise(x, y, seed)
			var value: float = 0.86

			if kind == "stone":
				var mortar_x: bool = x % 18 <= 1
				var row: int = y / 12
				var shifted_x: int = (x + (9 if row % 2 == 1 else 0)) % 18
				var mortar_y: bool = y % 12 <= 1
				var mortar: bool = mortar_y or shifted_x <= 1
				value = 0.72 if mortar else 0.83 + noise * 0.16
			elif kind == "wood":
				var grain: float = sin(float(x) * 0.44 + sin(float(y) * 0.18) * 1.8)
				value = 0.78 + grain * 0.075 + noise * 0.08
			else:
				var grout: bool = x % 16 <= 1 or y % 16 <= 1
				value = 0.70 if grout else 0.84 + noise * 0.11

			value = clampf(value, 0.58, 1.0)
			image.set_pixel(x, y, Color(value, value, value, 1.0))

	image.generate_mipmaps()
	return ImageTexture.create_from_image(image)

func _surface_texture_for(label: String) -> Texture2D:
	var lower: String = label.to_lower()
	var is_wood: bool = (
		lower.contains("pew")
		or lower.contains("altar")
		or lower.contains("balcony")
		or lower.contains("stair")
		or lower.contains("ceilingtie")
	)
	var is_floor: bool = (
		lower.contains("floor")
		or lower.contains("aisle")
		or lower.contains("ground")
		or lower.contains("walk")
		or lower.contains("step")
	)

	if is_wood:
		if _wood_texture == null:
			_wood_texture = _make_grain_texture("wood")
		return _wood_texture
	if is_floor:
		if _floor_texture == null:
			_floor_texture = _make_grain_texture("floor")
		return _floor_texture

	if _stone_texture == null:
		_stone_texture = _make_grain_texture("stone")
	return _stone_texture

func _make_surface_material(label: String, color: Color, base_roughness: float) -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	var variation: float = 0.955 + float(abs(label.hash()) % 11) * 0.006
	mat.albedo_color = Color(
		clampf(color.r * variation, 0.0, 1.0),
		clampf(color.g * variation, 0.0, 1.0),
		clampf(color.b * variation, 0.0, 1.0),
		color.a
	)
	mat.albedo_texture = _surface_texture_for(label)
	mat.roughness = clampf(base_roughness + float(abs(label.hash()) % 5) * 0.018, 0.55, 0.98)

	var lower: String = label.to_lower()
	if lower.contains("pew") or lower.contains("altar") or lower.contains("stair") or lower.contains("balcony"):
		mat.uv1_scale = Vector3(3.4, 3.4, 3.4)
	elif lower.contains("floor") or lower.contains("aisle") or lower.contains("ground"):
		mat.uv1_scale = Vector3(7.0, 7.0, 7.0)
	else:
		mat.uv1_scale = Vector3(5.0, 5.0, 5.0)
	return mat

func _ready() -> void:
	set_meta("world_scale", WORLD_SCALE)
	_build_environment()
	_build_site()
	_build_church()
	_build_interior()
	_build_realism_pass()
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
	env.ambient_light_color = Color(0.11, 0.14, 0.20)
	env.ambient_light_energy = 0.30
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.fog_enabled = true
	env.fog_light_color = Color(0.055, 0.065, 0.085)
	env.fog_light_energy = 0.72
	env.fog_density = 0.018
	env.fog_aerial_perspective = 0.42
	world.environment = env
	add_child(world)
	var moon := DirectionalLight3D.new()
	moon.rotation_degrees = Vector3(-48, -32, 0)
	moon.light_color = Color(0.38, 0.48, 0.72)
	moon.light_energy = 0.72
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
	var wood := Color(0.115, 0.062, 0.031)
	# Center aisle + raised altar, kept deliberately tighter than the first blockout.
	_box("Aisle", Vector3(2.55, 0.035, 29.0), Vector3(0, 0.465, -3), Color(0.145, 0.132, 0.112))
	_box("AltarPlatform", Vector3(7.2, 0.34, 4.2), Vector3(0, 0.49, -20.5), Color(0.105, 0.095, 0.082))
	_box("Altar", Vector3(3.5, 1.0, 1.15), Vector3(0, 1.12, -21.0), Color(0.23, 0.205, 0.16))
	# Human-scale pews: thinner seat/back and shorter span, so they read as furniture instead of blocks.
	for z in range(-15, 8, 4):
		if z != 1 and z != 5:
			_pew(Vector3(-4.75, 0.55, float(z)), wood)
		_pew(Vector3(4.75, 0.55, float(z)), wood)
	# upper rear balcony / second-floor gameplay shell
	_box("Balcony", Vector3(20.5, 0.5, 6.0), Vector3(0, 5.0, 10.4), Color(0.11, 0.075, 0.045))

	# Balcony rail has a real opening aligned with the stair exit at x=-8.
	_box("BalconyRailMain", Vector3(15.8, 1.15, 0.25), Vector3(2.1, 5.8, 7.55), wood)
	_box("BalconyRailLeft", Vector3(1.3, 1.15, 0.25), Vector3(-10.35, 5.8, 7.55), wood)

	# Visual stairs stay crisp, while one continuous hidden ramp provides reliable
	# CharacterBody3D traversal to the balcony on touch/mobile.
	for i in range(14):
		_box(
			"Stair%d" % i,
			Vector3(3.2, 0.30, 0.58),
			Vector3(-8.0, 0.58 + float(i) * 0.35, 0.95 + float(i) * 0.45),
			wood,
			false
		)
	_box("StairTopLanding", Vector3(3.4, 0.30, 1.6), Vector3(-8.0, 5.08, 7.75), wood, false)
	_build_balcony_stair_ramp()

func _build_realism_pass() -> void:
	# Visual-only architecture pass. These details intentionally do not alter gameplay collision.
	var trim := Color(0.095, 0.090, 0.082)
	var beam := Color(0.075, 0.040, 0.020)
	var stone_dark := Color(0.115, 0.110, 0.105)

	# Interior pilasters break the long flat walls and restore human visual scale.
	var pillar_z: Array[float] = [-20.5, -13.0, -5.0, 3.0, 10.0]
	for i in range(pillar_z.size()):
		var z: float = pillar_z[i]
		_visual_cylinder(
			"PilasterL_%02d" % i,
			0.34,
			5.4,
			Vector3(-10.45, 2.75, z),
			stone_dark,
			12
		)
		_visual_cylinder(
			"PilasterR_%02d" % i,
			0.34,
			5.4,
			Vector3(10.45, 2.75, z),
			stone_dark,
			12
		)

	# Roof ribs / timber ties create repeated scale references overhead.
	var beam_z: Array[float] = [-18.0, -12.0, -6.0, 0.0, 6.0, 11.0]
	for i in range(beam_z.size()):
		_visual_box(
			"CeilingTie_%02d" % i,
			Vector3(18.4, 0.18, 0.28),
			Vector3(0.0, 6.25, beam_z[i]),
			beam
		)

	# Stone/wood base trim along the nave walls.
	_visual_box("BaseTrimL", Vector3(0.18, 0.42, 36.0), Vector3(-10.60, 0.35, -5.0), trim)
	_visual_box("BaseTrimR", Vector3(0.18, 0.42, 36.0), Vector3(10.60, 0.35, -5.0), trim)

	# Floor seams stop the nave from reading as one giant smooth toy slab.
	for zi in range(-18, 12, 2):
		_visual_box(
			"FloorSeamZ_%02d" % (zi + 20),
			Vector3(19.0, 0.018, 0.035),
			Vector3(0.0, 0.462, float(zi)),
			Color(0.070, 0.064, 0.055)
		)
	for xi in range(-8, 9, 2):
		_visual_box(
			"FloorSeamX_%02d" % (xi + 10),
			Vector3(0.035, 0.018, 31.0),
			Vector3(float(xi), 0.463, -3.0),
			Color(0.070, 0.064, 0.055)
		)

	print("XZOGOT_ANTI_TOY_PASS_READY")

func _visual_box(label: String, size: Vector3, pos: Vector3, color: Color) -> void:
	_box(label, size, pos, color, false)

func _visual_cylinder(label: String, radius: float, height: float, pos: Vector3, color: Color, sides: int = 12) -> void:
	var root := Node3D.new()
	root.name = label
	root.position = _wp(pos)
	var mi := MeshInstance3D.new()
	var mesh := CylinderMesh.new()
	mesh.top_radius = radius * WORLD_SCALE
	mesh.bottom_radius = radius * WORLD_SCALE
	mesh.height = height * WORLD_SCALE
	mesh.radial_segments = sides
	var mat: StandardMaterial3D = _make_surface_material(label, color, 0.91)
	mesh.material = mat
	mi.mesh = mesh
	root.add_child(mi)
	add_child(root)

func _build_balcony_stair_ramp() -> void:
	var start: Vector3 = _wp(Vector3(-8.0, 0.38, 0.60))
	var finish: Vector3 = _wp(Vector3(-8.0, 5.60, 7.55))
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
	shape.size = Vector3(3.0 * WORLD_SCALE, 0.16 * WORLD_SCALE, slope_length)
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
	body.position = _wp(pos)
	body.set_script(script_resource)
	body.set("interaction_kind", kind)
	body.set("price", price)
	body.set("reward_amount", reward)
	body.set("one_shot", one_shot)
	body.set("prompt_text", prompt)
	body.add_to_group("zombie_interactable")

	var mi := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = _ws(size)
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.roughness = 0.74
	mat.metallic = 0.06
	mesh.material = mat
	mi.mesh = mesh
	body.add_child(mi)

	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = _ws(size)
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
	var run: float = 1.80
	var rise: float = 0.62
	var angle_rad: float = atan(rise / run)
	var angle_deg: float = rad_to_deg(angle_rad)
	var body := StaticBody3D.new()
	body.name = "WindowRamp_%s_%02d" % [side, index]
	body.position = _wp(Vector3(11.50 * sx, 0.21, z))
	body.rotation_degrees.z = -sx * angle_deg

	var mesh_instance := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = _ws(Vector3(run, 0.18, 2.30))
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.16, 0.15, 0.13)
	mat.roughness = 0.92
	mesh.material = mat
	mesh_instance.mesh = mesh
	body.add_child(mesh_instance)

	var collision := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = _ws(Vector3(run, 0.18, 2.30))
	collision.shape = shape
	body.add_child(collision)
	body.add_to_group("zombie_window_ramp")
	add_child(body)

func _add_window_socket(window_id: int, side: String, z: float) -> void:
	var left: bool = side == "left"
	var sx: float = -1.0 if left else 1.0
	var barricade_x: float = 10.52 * sx
	var outside_spawn: Vector3 = _wp(Vector3(13.0 * sx, 0.08, z))
	var outside_approach: Vector3 = _wp(Vector3(11.95 * sx, 0.08, z))
	var inside_point: Vector3 = _wp(Vector3(10.20 * sx, 0.48, z))

	var marker := Marker3D.new()
	marker.name = "ZombieWindow_%02d" % window_id
	marker.position = _wp(Vector3(12.0 * sx, 0.55, z))
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
	barricade.position = _wp(Vector3(barricade_x, 1.55, z))
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
		lamp.position = _wp(Vector3(0, 4.2, z))
		lamp.light_color = Color(1.0, 0.56, 0.27)
		lamp.light_energy = 1.45
		lamp.omni_range = 7.0 * WORLD_SCALE
		lamp.shadow_enabled = true
		add_child(lamp)

func _build_camera() -> void:
	if get_viewport().get_camera_3d() != null:
		return
	var camera := Camera3D.new()
	camera.name = "PreviewCamera"
	camera.position = _wp(Vector3(0, 7.8, 31))
	camera.rotation_degrees = Vector3(-8, 0, 0)
	camera.fov = 68
	camera.current = true
	add_child(camera)

func _pew(pos: Vector3, color: Color) -> void:
	_box("PewSeat", Vector3(4.65, 0.22, 0.82), pos, color)
	_box("PewBack", Vector3(4.65, 0.92, 0.16), pos + Vector3(0, 0.44, 0.33), color)
	_box("PewLegL", Vector3(0.18, 0.55, 0.62), pos + Vector3(-1.95, -0.25, 0), color)
	_box("PewLegR", Vector3(0.18, 0.55, 0.62), pos + Vector3(1.95, -0.25, 0), color)

func _wedge_roof(label: String, pos: Vector3, roll: float, color: Color, size: Vector3 = Vector3(11.8, 0.45, 39.0)) -> void:
	var body := StaticBody3D.new()
	body.name = label
	body.position = _wp(pos)
	body.rotation_degrees.z = roll
	var mi := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = _ws(size)
	var mat: StandardMaterial3D = _make_surface_material(label, color, 0.91)
	mesh.material = mat
	mi.mesh = mesh
	body.add_child(mi)
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = _ws(size)
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
	root.position = _wp(pos)
	var mi := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = _ws(size)
	var mat: StandardMaterial3D = _make_surface_material(label, color, 0.84)
	mesh.material = mat
	mi.mesh = mesh
	root.add_child(mi)
	if collision:
		var cs := CollisionShape3D.new()
		var shape := BoxShape3D.new()
		shape.size = _ws(size)
		cs.shape = shape
		root.add_child(cs)
	add_child(root)
