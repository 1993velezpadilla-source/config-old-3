extends Node3D

const WORLD_SCALE: float = 0.78
const ALTAR_ASSET_PATH := "res://assets/environment/church/altar.glb"
const BENCH_ASSET_PATH := "res://assets/environment/church/bench.glb"

# High-density user gift pack. These are optional so CI stays green until the
# binary GLBs are copied into res://assets/gifts/ with the canonical names.
const GIFT_ALTAR_ASSET_PATH := "res://assets/gifts/intricate_wooden_altar.glb"
const GIFT_CHANDELIER_ASSET_PATH := "res://assets/gifts/candelabros_colgantes_techo.glb"
const GIFT_STAINED_GLASS_ASSET_PATH := "res://assets/gifts/gothic_stained_glass_window.glb"
const GIFT_MULTI_STAINED_GLASS_ASSET_PATH := "res://assets/gifts/multiple_gothic_stained_glass_window.glb"
const GIFT_STATUES_ASSET_PATH := "res://assets/gifts/religious_statue_collection.glb"
const GIFT_CANDLE_HOLDER_ASSET_PATH := "res://assets/gifts/ornate_candle_holder.glb"
const GIFT_FURNITURE_ASSET_PATH := "res://assets/gifts/gothic_church_furniture.glb"
const GIFT_RUINS_ASSET_PATH := "res://assets/gifts/medieval_church_ruins.glb"

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
				var row: int = floori(float(y) / 12.0)
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
	_build_expansion_v1()
	_build_interior()
	_build_realism_pass()
	_build_architectural_shell_v2()
	_build_church_visual_v3()
	_build_gift_pack()
	_build_interactions()
	_build_windows()
	_build_selective_spawn_anchors()
	_build_zombie_path_network()
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
	env.ambient_light_energy = 0.38
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.fog_enabled = true
	env.fog_light_color = Color(0.055, 0.065, 0.085)
	env.fog_light_energy = 0.80
	env.fog_density = 0.014
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
	# Expansion V1 needs a real training loop around the full church, not a decorative strip.
	_box("Ground", Vector3(112, 0.5, 118), Vector3(0, -0.25, -4), Color(0.035, 0.04, 0.045))
	_box("ChurchFloor", Vector3(22, 0.45, 38), Vector3(0, 0.22, -5), Color(0.12, 0.105, 0.085))
	_box("FrontWalk", Vector3(6, 0.20, 14), Vector3(0, 0.10, 21), Color(0.13, 0.13, 0.135))
	for i in range(4):
		_box("Step%d" % i, Vector3(7.0 - i * 0.35, 0.22, 1.15), Vector3(0, 0.11 + i * 0.20, 14.8 - i * 0.8), Color(0.18, 0.18, 0.17))

func _build_expansion_v1() -> void:
	var yard_stone := Color(0.105, 0.105, 0.102)
	var yard_edge := Color(0.155, 0.148, 0.135)
	var wall_stone := Color(0.125, 0.118, 0.108)
	var wall_dark := Color(0.078, 0.074, 0.070)
	var timber := Color(0.070, 0.038, 0.020)

	# --- PLAYABLE EXTERIOR LOOP -------------------------------------------------
	# These slabs are collision floors and intentionally overlap the world ground by
	# a few centimeters so the player never catches an edge while sprinting.
	_box("FrontCourtyardFloor", Vector3(36.0, 0.16, 21.0), Vector3(0.0, 0.08, 25.0), yard_stone)
	_box("WestOuterLoopFloor", Vector3(10.0, 0.16, 72.0), Vector3(-17.0, 0.08, -3.0), yard_stone)
	_box("EastOuterLoopFloor", Vector3(10.0, 0.16, 72.0), Vector3(17.0, 0.08, -3.0), yard_stone)
	_box("RearRuinsYardFloor", Vector3(42.0, 0.16, 20.0), Vector3(0.0, 0.08, -34.0), yard_stone)
	_box("WestTrainingPad", Vector3(16.0, 0.18, 18.0), Vector3(-25.0, 0.09, -19.0), yard_stone)
	_box("EastTrainingPad", Vector3(16.0, 0.18, 18.0), Vector3(25.0, 0.09, -19.0), yard_stone)
	_box("BellTowerAccessYardFloor", Vector3(18.0, 0.18, 20.0), Vector3(-25.0, 0.09, 10.0), yard_stone)

	# Low perimeter architecture shapes the route without turning the exterior into
	# a corridor. Openings stay deliberately wide enough for touch movement + trains.
	_box("FrontCourtyardWallL", Vector3(0.65, 2.3, 22.0), Vector3(-18.2, 1.15, 27.0), wall_stone)
	_box("FrontCourtyardWallR", Vector3(0.65, 2.3, 22.0), Vector3(18.2, 1.15, 27.0), wall_stone)
	_box("RearBoundary", Vector3(42.0, 2.4, 0.65), Vector3(0.0, 1.20, -44.0), wall_dark)
	_box("WestRearBoundary", Vector3(0.65, 2.4, 20.0), Vector3(-31.0, 1.20, -32.0), wall_dark)
	_box("EastRearBoundary", Vector3(0.65, 2.4, 20.0), Vector3(31.0, 1.20, -32.0), wall_dark)

	# Graveyard rhythm: collision-light stone markers, spaced so training paths remain clean.
	for i in range(10):
		var gx: float = 20.0 + float(i % 2) * 4.2
		var gz: float = -28.0 + float(i / 2) * 4.8
		_box(
			"GraveMarker_%02d" % i,
			Vector3(0.55, 1.35 + float(i % 3) * 0.18, 0.28),
			Vector3(gx, 0.70, gz),
			yard_edge
		)

	# West ruins read as cover/landmarks while preserving a broad outer training lane.
	for i in range(6):
		var rx: float = -27.5 + float(i % 3) * 3.2
		var rz: float = -34.0 + float(i / 3) * 5.0
		_box(
			"RearRuin_%02d" % i,
			Vector3(2.2, 1.4 + float(i % 2) * 1.2, 0.55),
			Vector3(rx, 0.70 + float(i % 2) * 0.60, rz),
			wall_stone
		)

	_build_side_rooms_v1(wall_stone, wall_dark, timber)
	_build_church_second_floor_v1(wall_stone, wall_dark, timber)
	_build_bell_tower_v1(wall_stone, wall_dark, timber)
	_build_expansion_zone_markers()
	print("XZOGOT_EXPANSION_V1_LOOP_READY")

func _build_side_rooms_v1(stone: Color, dark_stone: Color, timber: Color) -> void:
	# East sacristy / side chapel shell.
	_box("SacristyFloor", Vector3(8.0, 0.20, 11.0), Vector3(15.0, 0.10, -15.0), Color(0.11, 0.10, 0.085))
	_box("SacristyOuterWall", Vector3(0.55, 4.8, 11.0), Vector3(18.8, 2.4, -15.0), stone)
	_box("SacristyRearWall", Vector3(8.0, 4.8, 0.55), Vector3(15.0, 2.4, -20.3), stone)
	_box("SacristyFrontWallA", Vector3(2.3, 4.8, 0.55), Vector3(12.1, 2.4, -9.7), dark_stone)
	_box("SacristyFrontWallB", Vector3(2.3, 4.8, 0.55), Vector3(17.9, 2.4, -9.7), dark_stone)
	_visual_box("SacristyBeam", Vector3(7.2, 0.28, 0.30), Vector3(15.0, 4.35, -15.0), timber)

	# West utility hallway / future power route.
	_box("WestHallFloor", Vector3(7.0, 0.20, 16.0), Vector3(-14.5, 0.10, 3.0), Color(0.095, 0.09, 0.08))
	_box("WestHallOuterWall", Vector3(0.55, 4.4, 16.0), Vector3(-17.8, 2.2, 3.0), stone)
	_box("WestHallCapA", Vector3(7.0, 4.4, 0.55), Vector3(-14.5, 2.2, -4.7), dark_stone)
	_box("WestHallCapB", Vector3(7.0, 4.4, 0.55), Vector3(-14.5, 2.2, 10.7), dark_stone)

	# Crypt access room plus a physical descending ramp to the first basement landing.
	_box("CryptAccessFloor", Vector3(8.0, 0.20, 8.0), Vector3(15.0, 0.10, -3.0), Color(0.09, 0.085, 0.075))
	_box("CryptOuterWall", Vector3(0.55, 4.2, 8.0), Vector3(18.8, 2.1, -3.0), stone)
	_box("CryptCapNorth", Vector3(8.0, 4.2, 0.55), Vector3(15.0, 2.1, -6.8), dark_stone)
	_box("CryptCapSouth", Vector3(8.0, 4.2, 0.55), Vector3(15.0, 2.1, 0.8), dark_stone)
	_build_expansion_ramp(
		"CryptRamp",
		Vector3(16.0, 0.35, -1.0),
		Vector3(16.0, -2.80, -7.0),
		2.4
	)
	_box("CryptBasementFloor", Vector3(12.0, 0.28, 14.0), Vector3(16.0, -2.95, -12.5), Color(0.060, 0.058, 0.055))
	_box("CryptBasementRearWall", Vector3(12.0, 3.3, 0.55), Vector3(16.0, -1.30, -19.3), dark_stone)
	print("XZOGOT_SIDE_ROOMS_V1_READY")

func _build_church_second_floor_v1(stone: Color, dark_stone: Color, timber: Color) -> void:
	# The original rear balcony becomes the entry landing for a real second-floor loop.
	# Side galleries stay narrow enough to preserve the cathedral void over the nave.
	var gallery_y: float = 5.02
	var rail_y: float = 5.78

	_box(
		"SecondFloorWestGallery",
		Vector3(3.35, 0.28, 27.0),
		Vector3(-8.35, gallery_y, -6.0),
		Color(0.095, 0.080, 0.060)
	)
	_box(
		"SecondFloorEastGallery",
		Vector3(3.35, 0.28, 27.0),
		Vector3(8.35, gallery_y, -6.0),
		Color(0.095, 0.080, 0.060)
	)

	# Front/choir bridge connects both galleries, making the upper floor a loop
	# instead of two dead-end catwalks.
	_box(
		"SecondFloorChoirBridge",
		Vector3(16.70, 0.30, 3.10),
		Vector3(0.0, gallery_y, -18.15),
		Color(0.090, 0.075, 0.055)
	)

	# Rear connectors overlap the existing balcony so the current staircase and
	# BalconyGate remain the only progression entrance from the first floor.
	_box(
		"SecondFloorWestRearConnector",
		Vector3(3.35, 0.28, 4.8),
		Vector3(-8.35, gallery_y, 8.70),
		Color(0.095, 0.080, 0.060)
	)
	_box(
		"SecondFloorEastRearConnector",
		Vector3(3.35, 0.28, 4.8),
		Vector3(8.35, gallery_y, 8.70),
		Color(0.095, 0.080, 0.060)
	)

	# Inner rails are real collision. The outer church wall itself protects the outside edge.
	_box(
		"SecondFloorWestInnerRail",
		Vector3(0.20, 1.35, 27.0),
		Vector3(-6.63, rail_y, -6.0),
		timber
	)
	_box(
		"SecondFloorEastInnerRail",
		Vector3(0.20, 1.35, 27.0),
		Vector3(6.63, rail_y, -6.0),
		timber
	)
	_box(
		"SecondFloorChoirRailFront",
		Vector3(13.10, 1.35, 0.20),
		Vector3(0.0, rail_y, -16.58),
		timber
	)
	_box(
		"SecondFloorChoirRailRear",
		Vector3(13.10, 1.35, 0.20),
		Vector3(0.0, rail_y, -19.72),
		timber
	)

	# Decorative rhythm + cover anchors, kept away from the 2.8m clear walking lanes.
	for z in [-15.0, -9.0, -3.0, 3.0]:
		_visual_box(
			"SecondFloorWestPost_%s" % str(z).replace("-", "N").replace(".", "_"),
			Vector3(0.24, 2.05, 0.24),
			Vector3(-6.78, 6.02, z),
			dark_stone
		)
		_visual_box(
			"SecondFloorEastPost_%s" % str(z).replace("-", "N").replace(".", "_"),
			Vector3(0.24, 2.05, 0.24),
			Vector3(6.78, 6.02, z),
			dark_stone
		)

	# Dedicated upper-floor zone markers are useful for future AI spawning,
	# music/occlusion, ads, perks, and Easter-egg logic.
	var upper_zones: Dictionary = {
		"SecondFloorWest": Vector3(-8.35, 5.35, -6.0),
		"SecondFloorEast": Vector3(8.35, 5.35, -6.0),
		"SecondFloorChoir": Vector3(0.0, 5.35, -18.15),
	}
	for zone_name: String in upper_zones.keys():
		var marker := Marker3D.new()
		marker.name = "Zone_" + zone_name
		marker.position = _wp(upper_zones[zone_name])
		marker.add_to_group("second_floor_zone")
		marker.add_to_group("gameplay_zone")
		marker.set_meta("zone_name", zone_name)
		marker.set_meta("floor", 2)
		add_child(marker)

	print("XZOGOT_CHURCH_SECOND_FLOOR_READY 3 zones")
	print("XZOGOT_CHURCH_SECOND_FLOOR_LOOP_READY")

func _build_bell_tower_v1(stone: Color, dark_stone: Color, timber: Color) -> void:
	var cx: float = -25.0
	var cz: float = 9.0

	# Lower chamber and four structural piers keep the tower readable while leaving
	# broad openings for combat and exterior visibility.
	_box("BellTowerLowerFloor", Vector3(9.0, 0.25, 9.0), Vector3(cx, 0.125, cz), Color(0.11, 0.10, 0.085))
	for sx in [-1.0, 1.0]:
		for sz in [-1.0, 1.0]:
			_box(
				"BellTowerPier_%s_%s" % [str(sx), str(sz)],
				Vector3(1.0, 12.8, 1.0),
				Vector3(cx + 3.8 * sx, 6.4, cz + 3.8 * sz),
				stone
			)

	# Switchback traversal: two physical ramps and real landings.
	_build_expansion_ramp(
		"BellTowerRampLower",
		Vector3(cx - 2.1, 0.35, cz - 3.0),
		Vector3(cx - 2.1, 4.25, cz + 2.8),
		2.2
	)
	_box("BellTowerMidLanding", Vector3(8.0, 0.26, 2.2), Vector3(cx, 4.12, cz + 3.0), Color(0.095, 0.075, 0.050))
	_build_expansion_ramp(
		"BellTowerRampUpper",
		Vector3(cx + 2.1, 4.35, cz + 2.6),
		Vector3(cx + 2.1, 8.25, cz - 3.0),
		2.2
	)
	_box("BellTowerTopLanding", Vector3(8.0, 0.26, 2.5), Vector3(cx, 8.12, cz - 3.0), Color(0.095, 0.075, 0.050))
	_box("BellTowerBellDeckL", Vector3(2.4, 0.26, 5.5), Vector3(cx - 2.8, 8.12, cz + 0.7), Color(0.095, 0.075, 0.050))
	_box("BellTowerBellDeckR", Vector3(2.4, 0.26, 5.5), Vector3(cx + 2.8, 8.12, cz + 0.7), Color(0.095, 0.075, 0.050))

	# Timber cross frame + procedural bell placeholder. This is gameplay geometry now;
	# the final authored bell GLB can replace the visual without touching traversal.
	_visual_box("BellFrameTop", Vector3(7.4, 0.45, 0.45), Vector3(cx, 11.2, cz), timber)
	_visual_box("BellFrameL", Vector3(0.45, 5.8, 0.45), Vector3(cx - 2.8, 9.0, cz), timber)
	_visual_box("BellFrameR", Vector3(0.45, 5.8, 0.45), Vector3(cx + 2.8, 9.0, cz), timber)
	_visual_cylinder("ChurchBellCrown", 1.05, 0.55, Vector3(cx, 10.0, cz), Color(0.16, 0.095, 0.045), 24)
	_visual_cylinder("ChurchBellBody", 1.45, 1.35, Vector3(cx, 9.25, cz), Color(0.19, 0.105, 0.050), 24)
	_visual_cylinder("ChurchBellLip", 1.70, 0.22, Vector3(cx, 8.52, cz), Color(0.12, 0.065, 0.030), 24)

	# Thin level rails prevent accidental falls while keeping sightlines open.
	for y in [4.55, 8.55]:
		_visual_box("BellRailW_%s" % str(y), Vector3(7.5, 0.75, 0.18), Vector3(cx, y, cz + 3.75), timber)
		_visual_box("BellRailE_%s" % str(y), Vector3(7.5, 0.75, 0.18), Vector3(cx, y, cz - 3.75), timber)

	print("XZOGOT_BELL_TOWER_V1_PLAYABLE")

func _build_expansion_ramp(label: String, start_local: Vector3, end_local: Vector3, width: float) -> void:
	var start: Vector3 = _wp(start_local)
	var finish: Vector3 = _wp(end_local)
	var delta: Vector3 = finish - start
	var horizontal: float = Vector2(delta.x, delta.z).length()
	if horizontal <= 0.001:
		return
	var slope_length: float = sqrt(horizontal * horizontal + delta.y * delta.y)
	var yaw: float = rad_to_deg(atan2(delta.x, delta.z))
	var pitch: float = -rad_to_deg(atan2(delta.y, horizontal))

	var ramp := StaticBody3D.new()
	ramp.name = label
	ramp.position = (start + finish) * 0.5
	ramp.rotation_degrees = Vector3(pitch, yaw, 0.0)
	ramp.add_to_group("expansion_walkable_ramp")

	var mesh_instance := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = Vector3(width * WORLD_SCALE, 0.18 * WORLD_SCALE, slope_length)
	mesh.material = _make_surface_material(label, Color(0.11, 0.095, 0.075), 0.88)
	mesh_instance.mesh = mesh
	ramp.add_child(mesh_instance)

	var collision := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = Vector3(width * WORLD_SCALE, 0.18 * WORLD_SCALE, slope_length)
	collision.shape = shape
	ramp.add_child(collision)
	add_child(ramp)

func _build_expansion_zone_markers() -> void:
	var zones: Dictionary = {
		"FrontCourtyard": Vector3(0.0, 0.5, 25.0),
		"WestOuterLoop": Vector3(-17.0, 0.5, -3.0),
		"EastOuterLoop": Vector3(17.0, 0.5, -3.0),
		"RearRuinsYard": Vector3(0.0, 0.5, -34.0),
		"GraveyardPath": Vector3(23.0, 0.5, -18.0),
		"BellTowerAccessYard": Vector3(-25.0, 0.5, 10.0),
		"Sacristy": Vector3(15.0, 0.5, -15.0),
		"CryptAccess": Vector3(15.0, 0.5, -3.0),
	}
	for zone_name: String in zones.keys():
		var marker := Marker3D.new()
		marker.name = "Zone_" + zone_name
		marker.position = _wp(zones[zone_name])
		marker.add_to_group("gameplay_zone")
		marker.set_meta("zone_name", zone_name)
		add_child(marker)
	print("XZOGOT_EXPANSION_ZONES_READY ", zones.size())

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
	# Front tower with a real central passage instead of one solid block.
	# Two piers + upper lintel preserve tower mass while keeping the 3 m portal walkable.
	_box("TowerBasePierL", Vector3(2.0, 4.4, 6.0), Vector3(-2.5, 2.2, 10.7), dark_stone)
	_box("TowerBasePierR", Vector3(2.0, 4.4, 6.0), Vector3(2.5, 2.2, 10.7), dark_stone)
	_box("TowerBaseLintel", Vector3(7.0, 6.1, 6.0), Vector3(0, 7.45, 10.7), dark_stone)
	_box("TowerUpper", Vector3(5.4, 4.0, 5.0), Vector3(0, 12.5, 10.7), stone)
	print("XZOGOT_TOWER_PORTAL_OPEN 3.0")
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
	# Center aisle + raised altar. Furniture visuals now come from the authored GLBs.
	_box("Aisle", Vector3(2.55, 0.035, 29.0), Vector3(0, 0.465, -3), Color(0.145, 0.132, 0.112))
	_box("AltarPlatform", Vector3(7.2, 0.34, 4.2), Vector3(0, 0.49, -20.5), Color(0.105, 0.095, 0.082))
	_build_authored_altar()
	_build_authored_benches()
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

func _build_authored_altar() -> void:
	var altar_base_y: float = 0.66
	var altar_target := Vector3(3.60, 1.45, 1.35)
	var altar := _spawn_fitted_furniture(
		ALTAR_ASSET_PATH,
		"AuthoredAltar",
		Vector3(0.0, altar_base_y, -20.85),
		altar_target,
		90.0,
		true
	)
	if altar != null:
		altar.add_to_group("authored_church_furniture")
		_collision_box(
			"AltarCollision",
			Vector3(3.35, 1.12, 1.15),
			Vector3(0.0, altar_base_y + 0.56, -20.85)
		)
		print("XZOGOT_AUTHORED_ALTAR_READY")

func _build_authored_benches() -> void:
	var bench_base_y: float = 0.445
	var bench_target := Vector3(4.65, 1.35, 1.00)
	var bench_rows: Array[float] = [-15.0, -11.0, -7.0, -3.0, 1.0]
	var count: int = 0
	for z: float in bench_rows:
		var right := _spawn_fitted_furniture(
			BENCH_ASSET_PATH,
			"AuthoredBench_R_%02d" % count,
			Vector3(4.75, bench_base_y, z),
			bench_target,
			180.0,
			false
		)
		if right != null:
			right.add_to_group("authored_church_furniture")
			_collision_box(
				"BenchCollision_R_%02d" % count,
				Vector3(4.30, 0.78, 0.82),
				Vector3(4.75, bench_base_y + 0.39, z)
			)
			count += 1

		# Preserve the stair lane on the rear-left side.
		if z <= -3.0:
			var left := _spawn_fitted_furniture(
				BENCH_ASSET_PATH,
				"AuthoredBench_L_%02d" % count,
				Vector3(-4.75, bench_base_y, z),
				bench_target,
				180.0,
				false
			)
			if left != null:
				left.add_to_group("authored_church_furniture")
				_collision_box(
					"BenchCollision_L_%02d" % count,
					Vector3(4.30, 0.78, 0.82),
					Vector3(-4.75, bench_base_y + 0.39, z)
				)
				count += 1

	print("XZOGOT_AUTHORED_BENCHES_FACE_ALTAR 180")
	print("XZOGOT_AUTHORED_BENCHES_READY ", count)

func _spawn_fitted_furniture(
	path: String,
	label: String,
	base_pos: Vector3,
	target_size: Vector3,
	rotation_y_deg: float,
	swap_xz: bool
) -> Node3D:
	if not ResourceLoader.exists(path):
		push_error("FURNITURE_ASSET_MISSING: " + path)
		return null

	var packed: PackedScene = load(path) as PackedScene
	if packed == null:
		push_error("FURNITURE_ASSET_NOT_PACKED: " + path)
		return null

	var imported: Node3D = packed.instantiate() as Node3D
	if imported == null:
		push_error("FURNITURE_ASSET_INSTANTIATE_FAILED: " + path)
		return null

	var points: Array[Vector3] = []
	_collect_furniture_bounds(imported, Transform3D.IDENTITY, points)
	if points.is_empty():
		imported.queue_free()
		push_error("FURNITURE_ASSET_BOUNDS_EMPTY: " + path)
		return null

	var min_v: Vector3 = points[0]
	var max_v: Vector3 = points[0]
	for point: Vector3 in points:
		min_v.x = minf(min_v.x, point.x)
		min_v.y = minf(min_v.y, point.y)
		min_v.z = minf(min_v.z, point.z)
		max_v.x = maxf(max_v.x, point.x)
		max_v.y = maxf(max_v.y, point.y)
		max_v.z = maxf(max_v.z, point.z)

	var raw_size: Vector3 = max_v - min_v
	if raw_size.x <= 0.0001 or raw_size.y <= 0.0001 or raw_size.z <= 0.0001:
		imported.queue_free()
		push_error("FURNITURE_ASSET_BAD_BOUNDS: " + path)
		return null

	var desired_local: Vector3 = target_size
	if swap_xz:
		desired_local = Vector3(target_size.z, target_size.y, target_size.x)
	var desired_world: Vector3 = desired_local * WORLD_SCALE

	var wrapper := Node3D.new()
	wrapper.name = label
	wrapper.position = _wp(base_pos)
	wrapper.rotation_degrees.y = rotation_y_deg
	wrapper.scale = Vector3(
		desired_world.x / raw_size.x,
		desired_world.y / raw_size.y,
		desired_world.z / raw_size.z
	)

	imported.name = "Source"
	imported.position = Vector3(
		-(min_v.x + max_v.x) * 0.5,
		-min_v.y,
		-(min_v.z + max_v.z) * 0.5
	)
	wrapper.add_child(imported)
	wrapper.set_meta("source_asset", path)
	wrapper.set_meta("target_size_m", target_size * WORLD_SCALE)
	add_child(wrapper)
	return wrapper

func _gift_bundle_paths() -> Array[String]:
	return [
		GIFT_ALTAR_ASSET_PATH,
		GIFT_CHANDELIER_ASSET_PATH,
		GIFT_STAINED_GLASS_ASSET_PATH,
		GIFT_MULTI_STAINED_GLASS_ASSET_PATH,
		GIFT_STATUES_ASSET_PATH,
		GIFT_CANDLE_HOLDER_ASSET_PATH,
		GIFT_FURNITURE_ASSET_PATH,
		GIFT_RUINS_ASSET_PATH,
	]

func _build_gift_pack() -> void:
	# IMPORTANT: each source GLB is a bundle containing multiple visual models.
	# Their current Tripo export is fused as 1 scene / 1 node / 1 mesh / 1 primitive,
	# so spawning the source GLB would incorrectly glue every internal model together.
	# Only split/component assets are allowed into gameplay.
	var source_present: int = 0
	for path: String in _gift_bundle_paths():
		if ResourceLoader.exists(path):
			source_present += 1
			print("XZOGOT_GIFT_BUNDLE_REQUIRES_SPLIT ", path)
		else:
			print("XZOGOT_GIFT_BUNDLE_PENDING ", path)

	print("XZOGOT_GIFT_BUNDLE_GATE ", source_present, "/8 source bundles present")
	print("XZOGOT_GIFT_WHOLE_BUNDLE_SPAWN_DISABLED")

func _collect_furniture_bounds(
	node: Node3D,
	parent_transform: Transform3D,
	points: Array[Vector3]
) -> void:
	var current_transform: Transform3D = parent_transform * node.transform
	if node is MeshInstance3D:
		var mesh_instance := node as MeshInstance3D
		if mesh_instance.mesh != null:
			var bounds: AABB = mesh_instance.mesh.get_aabb()
			for xi in range(2):
				for yi in range(2):
					for zi in range(2):
						var corner := bounds.position + Vector3(
							bounds.size.x * float(xi),
							bounds.size.y * float(yi),
							bounds.size.z * float(zi)
						)
						points.append(current_transform * corner)

	for child: Node in node.get_children():
		if child is Node3D:
			_collect_furniture_bounds(child as Node3D, current_transform, points)

func _collision_box(label: String, size: Vector3, pos: Vector3) -> void:
	var body := StaticBody3D.new()
	body.name = label
	body.position = _wp(pos)
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = _ws(size)
	cs.shape = shape
	body.add_child(cs)
	add_child(body)

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

func _visual_box_rotated(label: String, size: Vector3, pos: Vector3, rotation_deg: Vector3, color: Color) -> void:
	var root := Node3D.new()
	root.name = label
	root.position = _wp(pos)
	root.rotation_degrees = rotation_deg
	var mi := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = _ws(size)
	mesh.material = _make_surface_material(label, color, 0.83)
	mi.mesh = mesh
	root.add_child(mi)
	add_child(root)

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

func _build_architectural_shell_v2() -> void:
	var stone_mid := Color(0.145, 0.138, 0.126)
	var stone_dark := Color(0.086, 0.082, 0.076)
	var stone_edge := Color(0.185, 0.176, 0.158)
	var timber := Color(0.062, 0.032, 0.016)

	# Continuous nave cornices stop the walls from reading as giant flat slabs.
	_visual_box("NaveCorniceL", Vector3(0.34, 0.26, 36.0), Vector3(-10.48, 5.55, -5.0), stone_edge)
	_visual_box("NaveCorniceR", Vector3(0.34, 0.26, 36.0), Vector3(10.48, 5.55, -5.0), stone_edge)
	_visual_box("NaveStringCourseL", Vector3(0.26, 0.18, 36.0), Vector3(-10.43, 2.25, -5.0), stone_mid)
	_visual_box("NaveStringCourseR", Vector3(0.26, 0.18, 36.0), Vector3(10.43, 2.25, -5.0), stone_mid)

	# Pilaster bases/capitals add believable load-bearing rhythm.
	var pier_z: Array[float] = [-20.5, -13.0, -5.0, 3.0, 10.0]
	for i in range(pier_z.size()):
		var z: float = pier_z[i]
		for side in [-1.0, 1.0]:
			var x: float = 10.28 * side
			var side_tag: String = "L" if side < 0.0 else "R"
			_visual_box(
				"PilasterBase_%s_%02d" % [side_tag, i],
				Vector3(0.92, 0.34, 0.96),
				Vector3(x, 0.38, z),
				stone_dark
			)
			_visual_box(
				"PilasterCapital_%s_%02d" % [side_tag, i],
				Vector3(0.90, 0.28, 0.92),
				Vector3(x, 5.36, z),
				stone_edge
			)
			_visual_box(
				"PilasterNeck_%s_%02d" % [side_tag, i],
				Vector3(0.62, 0.30, 0.66),
				Vector3(x, 5.10, z),
				stone_mid
			)

	# Repeated rib-vault members create real architectural scale overhead.
	var rib_z: Array[float] = [-18.0, -12.0, -6.0, 0.0, 6.0, 11.0]
	for i in range(rib_z.size()):
		var z: float = rib_z[i]
		_visual_box_rotated(
			"VaultRibL_%02d" % i,
			Vector3(7.25, 0.20, 0.24),
			Vector3(-4.15, 6.35, z),
			Vector3(0.0, 0.0, 18.0),
			stone_mid
		)
		_visual_box_rotated(
			"VaultRibR_%02d" % i,
			Vector3(7.25, 0.20, 0.24),
			Vector3(4.15, 6.35, z),
			Vector3(0.0, 0.0, -18.0),
			stone_mid
		)
		_visual_box(
			"VaultBoss_%02d" % i,
			Vector3(0.52, 0.28, 0.52),
			Vector3(0.0, 7.52, z),
			stone_edge
		)

	# Deep front portal with nested pointed arches, instead of a rectangular entrance cutout.
	_build_pointed_portal_layer("Outer", 2.55, 5.50, 0.34, 13.62, stone_dark)
	_build_pointed_portal_layer("Mid", 2.15, 5.10, 0.26, 13.48, stone_mid)
	_build_pointed_portal_layer("Inner", 1.75, 4.70, 0.20, 13.36, stone_edge)

	# Interior door reveal gives thickness to the front wall.
	_visual_box("PortalRevealL", Vector3(0.36, 4.15, 1.10), Vector3(-1.93, 2.10, 13.42), stone_dark)
	_visual_box("PortalRevealR", Vector3(0.36, 4.15, 1.10), Vector3(1.93, 2.10, 13.42), stone_dark)

	# Window sills/reveals give each zombie opening visible wall depth.
	var window_z: Array[float] = [-17.0, -9.0, -1.0, 7.0]
	for i in range(window_z.size()):
		var z: float = window_z[i]
		for side in [-1.0, 1.0]:
			var x: float = 10.62 * side
			var side_tag: String = "L" if side < 0.0 else "R"
			_visual_box(
				"WindowSill_%s_%02d" % [side_tag, i],
				Vector3(0.95, 0.18, 2.62),
				Vector3(x, 0.70, z),
				stone_edge
			)
			_visual_box(
				"WindowRevealA_%s_%02d" % [side_tag, i],
				Vector3(0.92, 2.70, 0.16),
				Vector3(x, 2.05, z - 1.30),
				stone_dark
			)
			_visual_box(
				"WindowRevealB_%s_%02d" % [side_tag, i],
				Vector3(0.92, 2.70, 0.16),
				Vector3(x, 2.05, z + 1.30),
				stone_dark
			)

	# External stepped buttress faces read as real masonry masses instead of one rectangle.
	var buttress_z: Array[float] = [-19.0, -11.0, -3.0, 5.0, 12.0]
	for i in range(buttress_z.size()):
		var z: float = buttress_z[i]
		for side in [-1.0, 1.0]:
			var x: float = 11.70 * side
			var side_tag: String = "L" if side < 0.0 else "R"
			_visual_box(
				"ButtressFoot_%s_%02d" % [side_tag, i],
				Vector3(1.55, 1.10, 2.10),
				Vector3(x, 0.70, z),
				stone_dark
			)
			_visual_box(
				"ButtressShoulder_%s_%02d" % [side_tag, i],
				Vector3(1.15, 0.80, 1.65),
				Vector3(x, 4.60, z),
				stone_mid
			)

	# Timber wall plates visually connect the roof to the masonry.
	_visual_box("RoofPlateL", Vector3(0.34, 0.28, 36.0), Vector3(-9.95, 6.18, -5.0), timber)
	_visual_box("RoofPlateR", Vector3(0.34, 0.28, 36.0), Vector3(9.95, 6.18, -5.0), timber)

	print("XZOGOT_ARCH_SHELL_V2_READY")

func _build_church_visual_v3() -> void:
	# Visual-only focal and readability pass. Keep gameplay collision untouched.
	# The goal is a readable horror church on mobile without flattening the contrast.
	var sanctuary_stone := Color(0.115, 0.105, 0.092)
	var sanctuary_edge := Color(0.205, 0.175, 0.135)
	var dark_wood := Color(0.078, 0.038, 0.018)
	var candle_wax := Color(0.68, 0.53, 0.33)
	var flame := Color(1.0, 0.42, 0.10)

	# Give the authored altar a proper architectural destination instead of a black rear wall.
	_visual_box(
		"SanctuaryDaisTrim",
		Vector3(8.35, 0.12, 4.72),
		Vector3(0.0, 0.705, -20.50),
		sanctuary_edge
	)
	_visual_box(
		"ReredosBack",
		Vector3(6.60, 4.90, 0.30),
		Vector3(0.0, 2.90, -23.42),
		sanctuary_stone
	)
	_visual_cylinder(
		"ReredosColumnL",
		0.23,
		4.20,
		Vector3(-2.75, 2.70, -23.16),
		sanctuary_edge,
		12
	)
	_visual_cylinder(
		"ReredosColumnR",
		0.23,
		4.20,
		Vector3(2.75, 2.70, -23.16),
		sanctuary_edge,
		12
	)
	_visual_box(
		"ReredosCap",
		Vector3(6.30, 0.30, 0.42),
		Vector3(0.0, 5.12, -23.14),
		sanctuary_edge
	)

	# Large cross behind the altar gives the player a strong long-axis landmark.
	_visual_box(
		"SanctuaryCrossVertical",
		Vector3(0.24, 2.25, 0.18),
		Vector3(0.0, 3.82, -22.98),
		dark_wood
	)
	_visual_box(
		"SanctuaryCrossHorizontal",
		Vector3(1.42, 0.24, 0.18),
		Vector3(0.0, 4.18, -22.97),
		dark_wood
	)

	# A small candle row adds believable scale and warm specular accents around the real altar.
	for i in range(7):
		var x: float = -2.25 + float(i) * 0.75
		_visual_cylinder(
			"AltarCandle_%02d" % i,
			0.035,
			0.26,
			Vector3(x, 1.28, -20.20),
			candle_wax,
			8
		)
		_visual_box(
			"AltarFlame_%02d" % i,
			Vector3(0.065, 0.11, 0.065),
			Vector3(x, 1.465, -20.20),
			flame
		)

	# Two cheap, non-shadow sanctuary accents reveal the altar silhouette without a flat flood light.
	for side in [-1.0, 1.0]:
		var sanctuary_light := OmniLight3D.new()
		sanctuary_light.name = "SanctuaryAccent_%s" % ("L" if side < 0.0 else "R")
		sanctuary_light.position = _wp(Vector3(2.85 * side, 2.65, -19.85))
		sanctuary_light.light_color = Color(1.0, 0.34, 0.11)
		sanctuary_light.light_energy = 0.58
		sanctuary_light.omni_range = 4.1 * WORLD_SCALE
		sanctuary_light.shadow_enabled = false
		add_child(sanctuary_light)

	# Moonlight leaking through the eight prepared zombie windows makes the wall depth readable.
	# These are intentionally non-shadow lights to stay cheap on mobile.
	var window_z: Array[float] = [-17.0, -9.0, -1.0, 7.0]
	for i in range(window_z.size()):
		for side in [-1.0, 1.0]:
			var window_light := OmniLight3D.new()
			window_light.name = "WindowMoon_%s_%02d" % ["L" if side < 0.0 else "R", i]
			window_light.position = _wp(Vector3(9.85 * side, 2.10, window_z[i]))
			window_light.light_color = Color(0.26, 0.42, 0.72)
			window_light.light_energy = 0.18
			window_light.omni_range = 2.85 * WORLD_SCALE
			window_light.shadow_enabled = false
			add_child(window_light)

	# Balcony support rhythm keeps the rear second floor from floating visually.
	for x in [-8.8, -4.4, 0.0, 4.4, 8.8]:
		_visual_box(
			"BalconySupport_%s" % str(x).replace(".", "_").replace("-", "N"),
			Vector3(0.28, 4.65, 0.28),
			Vector3(x, 2.55, 8.15),
			dark_wood
		)

	print("XZOGOT_CHURCH_V3_POLISH_READY")

func _build_pointed_portal_layer(
	tag: String,
	half_width: float,
	height: float,
	thickness: float,
	z: float,
	color: Color
) -> void:
	var jamb_height: float = height * 0.58
	var arch_len: float = height * 0.48
	var jamb_y: float = jamb_height * 0.5
	var arch_y: float = jamb_height + arch_len * 0.29
	var arch_x: float = half_width * 0.54
	var angle: float = 33.0

	_visual_box(
		"PortalJambL_%s" % tag,
		Vector3(thickness, jamb_height, 0.42),
		Vector3(-half_width, jamb_y, z),
		color
	)
	_visual_box(
		"PortalJambR_%s" % tag,
		Vector3(thickness, jamb_height, 0.42),
		Vector3(half_width, jamb_y, z),
		color
	)
	_visual_box_rotated(
		"PortalArchL_%s" % tag,
		Vector3(thickness, arch_len, 0.42),
		Vector3(-arch_x, arch_y, z),
		Vector3(0.0, 0.0, -angle),
		color
	)
	_visual_box_rotated(
		"PortalArchR_%s" % tag,
		Vector3(thickness, arch_len, 0.42),
		Vector3(arch_x, arch_y, z),
		Vector3(0.0, 0.0, angle),
		color
	)

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
	_interactive_box("RearDoor", Vector3(3.4, 3.8, 0.35), Vector3(0, 1.9, 13.10), Color(0.12, 0.07, 0.035), 0, 750, 0, true, "OPEN FRONT DOOR")
	_interactive_box("BalconyGate", Vector3(3.5, 2.2, 0.30), Vector3(-8.0, 6.0, 7.45), Color(0.13, 0.075, 0.04), 0, 1000, 0, true, "OPEN BALCONY")
	_interactive_box("WallBuy_01", Vector3(0.28, 1.8, 1.7), Vector3(-10.45, 1.7, -5.0), Color(0.16, 0.42, 0.62), 1, 500, 60, false, "BUY AMMO")
	_interactive_box("MysteryBoxSocket", Vector3(2.2, 1.4, 1.1), Vector3(7.4, 0.9, -15.0), Color(0.18, 0.12, 0.30), 2, 950, 0, false, "MYSTERY BOX")
	_interactive_box("PerkSocket", Vector3(1.2, 2.0, 1.2), Vector3(-7.4, 1.2, -15.2), Color(0.42, 0.11, 0.09), 3, 2500, 0, true, "PERK")
	_interactive_box("PowerSwitch", Vector3(0.7, 2.2, 0.7), Vector3(8.6, 1.4, 8.3), Color(0.52, 0.42, 0.12), 4, 0, 0, true, "TURN ON POWER")
	_build_expansion_interactions()
	print("XZOGOT_INTERACTIONS_PREPARED 11")

func _build_expansion_interactions() -> void:
	var gate_color := Color(0.16, 0.055, 0.035)
	# Front courtyard opens into two independent outer-loop routes.
	_interactive_box("WestOuterGate", Vector3(0.35, 3.2, 5.0), Vector3(-13.6, 1.60, 18.0), gate_color, 0, 1000, 0, true, "OPEN WEST YARD")
	_interactive_box("EastOuterGate", Vector3(0.35, 3.2, 5.0), Vector3(13.6, 1.60, 18.0), gate_color, 0, 1000, 0, true, "OPEN EAST YARD")
	# Rear route is deliberately later progression and unlocks the largest training loop.
	_interactive_box("RearRuinsGate", Vector3(5.0, 3.2, 0.35), Vector3(17.0, 1.60, -27.5), gate_color, 0, 1250, 0, true, "OPEN REAR RUINS")
	# Bell tower becomes a risk/reward vertical detour instead of free spawn access.
	_interactive_box("BellTowerGate", Vector3(0.35, 3.2, 4.8), Vector3(-19.5, 1.60, 9.0), gate_color, 0, 1250, 0, true, "OPEN BELL TOWER")
	_interactive_box("CryptGate", Vector3(3.0, 2.8, 0.35), Vector3(16.0, 1.45, -1.1), gate_color, 0, 1250, 0, true, "OPEN CRYPT")
	print("XZOGOT_EXPANSION_BUY_GATES_READY 5")

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
		_add_gothic_window_trim("L", -1.0, i, z)
		_add_gothic_window_trim("R", 1.0, i, z)
		_add_window_threshold_ramp("L", -1.0, i, z)
		_add_window_socket(window_id, "left", z)
		window_id += 1
		_add_window_threshold_ramp("R", 1.0, i, z)
		_add_window_socket(window_id, "right", z)
		window_id += 1
	print("XZOGOT_WINDOWS_PREPARED ", window_id)

func _add_gothic_window_trim(side: String, sx: float, index: int, z: float) -> void:
	var trim := Color(0.095, 0.090, 0.082)
	var x: float = 10.82 * sx
	# Two sloped stone members visually turn the rectangular gameplay opening into a pointed arch.
	_visual_box_rotated(
		"WindowArchA_%s_%02d" % [side, index],
		Vector3(0.22, 0.22, 1.95),
		Vector3(x, 3.15, z - 0.67),
		Vector3(-38.0, 0.0, 0.0),
		trim
	)
	_visual_box_rotated(
		"WindowArchB_%s_%02d" % [side, index],
		Vector3(0.22, 0.22, 1.95),
		Vector3(x, 3.15, z + 0.67),
		Vector3(38.0, 0.0, 0.0),
		trim
	)

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

func _add_direct_spawn_anchor(
	label: String,
	pos: Vector3,
	min_round: int,
	weight: float,
	requires_gate: String,
	entry_kind: String,
	zone: String
) -> void:
	var marker := Marker3D.new()
	marker.name = label
	marker.position = _wp(pos)
	marker.add_to_group("zombie_spawn_anchor")
	marker.set_meta("spawn_id", label)
	marker.set_meta("min_round", min_round)
	marker.set_meta("weight", weight)
	marker.set_meta("requires_gate", requires_gate)
	marker.set_meta("entry_kind", entry_kind)
	marker.set_meta("zone", zone)
	add_child(marker)

func _build_selective_spawn_anchors() -> void:
	# Window spawns remain the core early-round language. These hidden/direct
	# anchors phase in only when their route is purchased and the round allows it.
	# They are placed behind physical cover / map bounds so there is no visible pop-in.
	_add_direct_spawn_anchor(
		"Spawn_WestRuinBreach",
		Vector3(-32.5, 0.12, -19.0),
		3,
		0.78,
		"WestOuterGate",
		"breach",
		"WestOuterLoop"
	)
	_add_direct_spawn_anchor(
		"Spawn_EastGraveyardBreach",
		Vector3(32.5, 0.12, -18.0),
		3,
		0.84,
		"EastOuterGate",
		"graveyard",
		"GraveyardPath"
	)
	_add_direct_spawn_anchor(
		"Spawn_RearRuinsBreach",
		Vector3(0.0, 0.12, -46.5),
		4,
		0.96,
		"RearRuinsGate",
		"breach",
		"RearRuinsYard"
	)
	_add_direct_spawn_anchor(
		"Spawn_FrontCourtyardRoad",
		Vector3(0.0, 0.12, 39.0),
		2,
		0.66,
		"RearDoor",
		"offscreen",
		"FrontCourtyard"
	)
	_add_direct_spawn_anchor(
		"Spawn_CryptCrawl",
		Vector3(16.0, -2.80, -20.2),
		6,
		0.62,
		"CryptGate",
		"crawl",
		"CryptAccess"
	)
	_add_direct_spawn_anchor(
		"Spawn_BellTowerRope",
		Vector3(-25.0, 8.25, 14.4),
		8,
		0.50,
		"BellTowerGate",
		"vertical",
		"BellTowerAccessYard"
	)
	_add_direct_spawn_anchor(
		"Spawn_SecondFloorWest",
		Vector3(-10.75, 5.25, -13.0),
		7,
		0.44,
		"BalconyGate",
		"clerestory",
		"SecondFloorWest"
	)
	_add_direct_spawn_anchor(
		"Spawn_SecondFloorEast",
		Vector3(10.75, 5.25, -13.0),
		7,
		0.44,
		"BalconyGate",
		"clerestory",
		"SecondFloorEast"
	)
	print("XZOGOT_SELECTIVE_SPAWNS_READY 8")

func _build_zombie_path_network() -> void:
	var script_resource: Script = load("res://scripts/zombie_path_network.gd") as Script
	if script_resource == null:
		push_error("ZOMBIE_PATH_NETWORK_SCRIPT_MISSING")
		return
	var network := Node3D.new()
	network.name = "ZombiePathNetwork"
	network.set_script(script_resource)
	add_child(network)
	print("XZOGOT_ZOMBIE_PATHING_BOOTSTRAPPED")

func _build_lights() -> void:
	var light_z: Array[float] = [-17.0, -7.0, 3.0, 10.0]
	for z: float in light_z:
		var lamp := OmniLight3D.new()
		lamp.position = _wp(Vector3(0, 4.2, z))
		lamp.light_color = Color(1.0, 0.52, 0.22)
		lamp.light_energy = 1.42
		lamp.omni_range = 7.0 * WORLD_SCALE
		lamp.shadow_enabled = true
		add_child(lamp)

	var altar_glow := OmniLight3D.new()
	altar_glow.name = "AltarGlow"
	altar_glow.position = _wp(Vector3(0.0, 2.35, -20.10))
	altar_glow.light_color = Color(1.0, 0.30, 0.10)
	altar_glow.light_energy = 1.32
	altar_glow.omni_range = 5.8 * WORLD_SCALE
	altar_glow.shadow_enabled = true
	add_child(altar_glow)
	print("XZOGOT_ALTAR_LIGHT_READY")

	# Low-energy wall sconces reveal architecture without flattening the horror contrast.
	var sconce_z: Array[float] = [-13.0, -3.0, 7.0]
	var sconce_sides: Array[float] = [-1.0, 1.0]
	for i in range(sconce_z.size()):
		var z: float = sconce_z[i]
		for side: float in sconce_sides:
			var sconce := OmniLight3D.new()
			sconce.name = "WallSconce_%s_%02d" % ["L" if side < 0.0 else "R", i]
			sconce.position = _wp(Vector3(9.7 * side, 2.65, z))
			sconce.light_color = Color(1.0, 0.35, 0.12)
			sconce.light_energy = 0.42
			sconce.omni_range = 3.6 * WORLD_SCALE
			sconce.shadow_enabled = false
			add_child(sconce)

			_visual_box(
				"SconceFixture_%s_%02d" % ["L" if side < 0.0 else "R", i],
				Vector3(0.16, 0.34, 0.26),
				Vector3(9.95 * side, 2.65, z),
				Color(0.12, 0.075, 0.035)
			)

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
	# Collision remains simple while the visible silhouette uses thinner, angled church furniture.
	_box("PewSeatCollider", Vector3(4.65, 0.18, 0.76), pos, color)
	_box("PewLegL", Vector3(0.15, 0.52, 0.58), pos + Vector3(-1.95, -0.24, 0), color)
	_box("PewLegR", Vector3(0.15, 0.52, 0.58), pos + Vector3(1.95, -0.24, 0), color)

	_visual_box_rotated(
		"PewBackVisual",
		Vector3(4.65, 0.78, 0.12),
		pos + Vector3(0, 0.48, 0.31),
		Vector3(-8.0, 0.0, 0.0),
		color
	)
	_visual_box("PewTopRail", Vector3(4.72, 0.12, 0.16), pos + Vector3(0, 0.84, 0.37), color)
	_visual_box("PewEndL", Vector3(0.13, 0.76, 0.86), pos + Vector3(-2.28, 0.18, 0.05), color)
	_visual_box("PewEndR", Vector3(0.13, 0.76, 0.86), pos + Vector3(2.28, 0.18, 0.05), color)

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
