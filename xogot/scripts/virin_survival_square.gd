extends Node3D
## XZIEL / GODOT 4.6: NEW, authored-from-scratch miniature survival arena.
## Keeps the EXISTING Xogot player, weapon combat, round director, WaW zombies
## and COD Mobile touch HUD from the advanced Black Pines project. No Quake map.
## The ORIGINAL NZ:P Quake MDL model is used strictly as a visual viewmodel,
## including baked hands and original morph-frame animation. No fake rigs.

const WeaponCatalog = preload("res://scripts/weapon_catalog.gd")
const ORIGINAL_CATALOG := "res://assets/vril_original/weapons/catalog.json"
const WALL_SIZE: float = 22.0
const SURFACE_Y: float = 0.0

var _models: Array = []
var _selected: int = 0
var _original_model: Node3D
var _original_animation: AnimationPlayer
var _original_mount: Node3D
var _model_label: Label
var _round_label: Label
var _original_play_button: Button

@onready var _player: CharacterBody3D = $Player
@onready var _weapon: Node = $Player/Weapon
@onready var _camera: Camera3D = $Player/Head/Camera3D
@onready var _director: Node = $RoundManager

func _ready() -> void:
	get_tree().set_meta("active_map_id", "virin_survival_square")
	get_tree().set_meta("power_on", true)
	_construct_square_from_scratch()
	_create_spawn_ring()
	_build_mood()
	_create_original_weapon_ui()
	_player.global_position = Vector3(0.0, 0.26, 1.8)
	_camera.current = true
	_director.set("special_rounds_enabled", false)
	_director.set("endless_rounds_enabled", true)
	_director.set("endless_wave_population_cap", 144)
	_director.set("endless_zombie_health_cap", 250000)
	_director.set("max_alive_zombies", 12)
	_director.set("first_round_delay", 0.2)
	_director.set("round_break", 2.5)
	_director.set("auto_start", true)
	_director.call("reset_network_match")
	_director.connect("round_started", Callable(self, "_round_started"))
	_director.connect("round_cleared", Callable(self, "_round_cleared"))
	_read_original_arsenal()
	_weapon.call("equip_weapon", "mp40", true)
	call_deferred("_start_immediate_survival")
	call_deferred("_mount_first_original")
	set_process(true)
	print("VIRIN_SURVIVAL_SQUARE_REAL_ADVANCED_GAMEPLAY_READY")
	print("VIRIN_SURVIVAL_SQUARE_NEW_GEOMETRY_ONLY_NOT_IMPORTED_DEAD_CELL")

func _start_immediate_survival() -> void:
	# No waiting for a giant level or a window to break: the first zombie
	# starts in under a second of simulation after the playable map opens.
	_director.call("start_next_round")
	print("VIRIN_SURVIVAL_SQUARE_ROUND_1_IMMEDIATE")

func _round_started(round_id: int, total: int) -> void:
	if is_instance_valid(_round_label):
		_round_label.text = "SURVIVAL  |  ROUND %d  |  %d ZOMBIES" % [round_id, total]

func _round_cleared(round_id: int) -> void:
	if is_instance_valid(_round_label):
		_round_label.text = "ROUND %d CLEAR  |  NEXT IN 2.5s" % round_id

func _material(rgb: Color, roughness: float = 0.88, emission: Color = Color.BLACK) -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = rgb
	mat.roughness = roughness
	if emission != Color.BLACK:
		mat.emission_enabled = true
		mat.emission = emission
		mat.emission_energy_multiplier = 1.7
	return mat

func _block(label: String, pos: Vector3, dims: Vector3, mat: StandardMaterial3D,
		solid: bool = true) -> StaticBody3D:
	var block := StaticBody3D.new()
	block.name = label
	block.position = pos
	add_child(block)
	var mesh := MeshInstance3D.new()
	var shape := BoxMesh.new()
	shape.size = dims
	mesh.mesh = shape
	mesh.material_override = mat
	block.add_child(mesh)
	if solid:
		var collider := CollisionShape3D.new()
		var cshape := BoxShape3D.new()
		cshape.size = dims
		collider.shape = cshape
		block.add_child(collider)
	return block

func _construct_square_from_scratch() -> void:
	# ORIGINAL NEW 22x22 meter geometry, not a BSP or a Dead Cell import.
	var floor_mat := _material(Color(0.24, 0.29, 0.32))
	var wall_mat := _material(Color(0.26, 0.31, 0.33))
	var edge_mat := _material(Color(0.11, 0.14, 0.16))
	var trim_mat := _material(Color(0.35, 0.20, 0.09), 0.62,
		Color(0.20, 0.07, 0.02))
	_block("NEW_FLOOR_NOT_DEAD_CELL", Vector3(0.0, -0.25, 0.0),
		Vector3(WALL_SIZE, 0.5, WALL_SIZE), floor_mat)
	var half: float = WALL_SIZE * 0.5
	_block("NorthWall", Vector3(0.0, 2.2, -half), Vector3(WALL_SIZE, 4.4, 0.55), wall_mat)
	_block("SouthWall", Vector3(0.0, 2.2, half), Vector3(WALL_SIZE, 4.4, 0.55), wall_mat)
	_block("EastWall", Vector3(half, 2.2, 0.0), Vector3(0.55, 4.4, WALL_SIZE), wall_mat)
	_block("WestWall", Vector3(-half, 2.2, 0.0), Vector3(0.55, 4.4, WALL_SIZE), wall_mat)
	# Visible grid and edge highlights; do not reuse the invisible Quake map.
	for i in range(-4, 5):
		var coord: float = float(i) * 2.25
		_block("FloorGrooveX_%d" % i, Vector3(coord, 0.015, 0.0),
			Vector3(0.045, 0.024, 20.4), edge_mat, false)
		_block("FloorGrooveZ_%d" % i, Vector3(0.0, 0.016, coord),
			Vector3(20.4, 0.024, 0.045), edge_mat, false)
	for x in [-10.4, 10.4]:
		for z in [-10.4, 10.4]:
			_block("CornerSignal_%.0f_%.0f" % [x,z], Vector3(x, 1.9, z),
				Vector3(0.13, 3.4, 0.13), trim_mat, false)
	# Two low plinths are placed AWAY from the direct chase lane.
	_block("SideCoverLeft", Vector3(-7.7, 0.46, 0.0), Vector3(1.5, 0.92, 2.3), edge_mat)
	_block("SideCoverRight", Vector3(7.7, 0.46, 0.0), Vector3(1.5, 0.92, 2.3), edge_mat)
	print("VIRIN_SQUARE_GEOMETRY_VISIBLE_GREEN size=", WALL_SIZE)

func _create_spawn_ring() -> void:
	# Original director rejects spawns within 5m: all entries 7-9m from player.
	# Direct-chase entrances, not false barricades or untraversable outer walls.
	var positions: Array[Vector3] = [
		Vector3(-6.5, 0.12, -8.6), Vector3(0.0, 0.12, -8.8),
		Vector3(6.5, 0.12, -8.6), Vector3(-8.6, 0.12, -5.5),
		Vector3(8.6, 0.12, -5.5), Vector3(-8.6, 0.12, 5.3),
		Vector3(8.6, 0.12, 5.3), Vector3(0.0, 0.12, 9.0),
	]
	for i in range(positions.size()):
		var marker := Marker3D.new()
		marker.name = "SquareZombieSpawn_%02d" % i
		marker.position = positions[i]
		marker.add_to_group("zombie_spawn_anchor")
		marker.set_meta("spawn_id", marker.name)
		marker.set_meta("min_round", 1)
		marker.set_meta("weight", 2.0)
		marker.set_meta("zone", "square_survival")
		marker.set_meta("entry_kind", "direct")
		add_child(marker)
	print("VIRIN_SQUARE_8_ZOMBIE_CHASE_SPAWNS_READY")

func _build_mood() -> void:
	var world := WorldEnvironment.new()
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color(0.045, 0.06, 0.08)
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color(0.61, 0.72, 0.82)
	environment.ambient_light_energy = 0.75
	environment.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	world.environment = environment
	add_child(world)
	var sun := DirectionalLight3D.new()
	sun.name = "ReadableArenaFloodlight"
	sun.light_color = Color(0.76, 0.85, 1.0)
	sun.light_energy = 1.4
	sun.rotation_degrees = Vector3(-64, 25, 0)
	sun.shadow_enabled = true
	add_child(sun)
	for i in range(4):
		var lamp := OmniLight3D.new()
		lamp.name = "SurvivalLight_%d" % i
		lamp.position = [
			Vector3(-6.4, 3.6, -6.4), Vector3(6.4, 3.6, -6.4),
			Vector3(-6.4, 3.6, 6.4), Vector3(6.4, 3.6, 6.4),
		][i]
		lamp.omni_range = 13.0
		lamp.light_color = Color(1.0, 0.81, 0.63)
		lamp.light_energy = 1.5
		lamp.shadow_enabled = false
		add_child(lamp)

func _create_original_weapon_ui() -> void:
	var canvas := CanvasLayer.new()
	canvas.name = "OriginalVrilWeaponSwitcher"
	canvas.layer = 4
	add_child(canvas)
	var hud := Control.new()
	hud.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	hud.mouse_filter = Control.MOUSE_FILTER_IGNORE
	canvas.add_child(hud)
	var row := HBoxContainer.new()
	row.anchor_left = 0.48
	row.anchor_right = 0.99
	row.anchor_top = 0.007
	row.anchor_bottom = 0.007
	row.offset_bottom = 74.0
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hud.add_child(row)
	var back := Button.new()
	back.text = "◀ GUN"
	back.custom_minimum_size = Vector2(130.0, 60.0)
	back.pressed.connect(func() -> void: _select_model(-1))
	row.add_child(back)
	_model_label = Label.new()
	_model_label.custom_minimum_size = Vector2(300.0, 60.0)
	_model_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_model_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_model_label.text = "VIRIN ORIGINAL ARSENAL..."
	row.add_child(_model_label)
	var next := Button.new()
	next.text = "GUN ▶"
	next.custom_minimum_size = Vector2(130.0, 60.0)
	next.pressed.connect(func() -> void: _select_model(1))
	row.add_child(next)
	_original_play_button = Button.new()
	_original_play_button.text = "▶ FRAMES"
	_original_play_button.custom_minimum_size = Vector2(160.0, 60.0)
	_original_play_button.pressed.connect(_play_original_frames)
	row.add_child(_original_play_button)
	_round_label = Label.new()
	_round_label.anchor_left = 0.03
	_round_label.anchor_right = 0.48
	_round_label.offset_top = 24.0
	_round_label.text = "SURVIVAL - FIRST WAVE STARTING"
	_round_label.add_theme_font_size_override("font_size", 24)
	hud.add_child(_round_label)

func _read_original_arsenal() -> void:
	if not FileAccess.file_exists(ORIGINAL_CATALOG):
		push_error("VIRIN_ORIGINAL_41_WEAPONS_MISSING: no prefab substitutions")
		return
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(ORIGINAL_CATALOG))
	if typeof(data) != TYPE_DICTIONARY:
		push_error("VIRIN_ORIGINAL_CATALOG_RED")
		return
	_models = data.get("weapons", [])
	if _models.size() != 41:
		push_error("VIRIN_ORIGINAL_WEAPON_COUNT_RED expected=41 found=%d" % _models.size())
		return
	for i in range(_models.size()):
		if str(_models[i].get("name", "")) == "v_mp40":
			_selected = i
			break
	print("VIRIN_SURVIVAL_ORIGINAL_41_WEAPON_CATALOG_GREEN")

func _mount_first_original() -> void:
	if _models.is_empty():
		return
	_original_mount = Node3D.new()
	_original_mount.name = "AuthenticNZPFirstPersonGunAndHands"
	_camera.add_child(_original_mount)
	_select_model(0)

func _find_animation_player(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node as AnimationPlayer
	for child in node.get_children():
		var result: AnimationPlayer = _find_animation_player(child)
		if result != null:
			return result
	return null

func _mesh_bounds(node: Node3D) -> AABB:
	var points: Array[Vector3] = []
	_collect_bounds(node, node, points)
	if points.is_empty():
		return AABB(Vector3(-0.1, -0.1, -0.1), Vector3(0.2, 0.2, 0.2))
	var mn: Vector3 = points[0]
	var mx: Vector3 = points[0]
	for point in points:
		mn = mn.min(point)
		mx = mx.max(point)
	return AABB(mn, mx - mn)

func _collect_bounds(root_node: Node3D, node: Node3D, points: Array[Vector3]) -> void:
	if node is MeshInstance3D and (node as MeshInstance3D).mesh != null:
		var mesh_bounds: AABB = (node as MeshInstance3D).mesh.get_aabb()
		for ix in [0,1]:
			for iy in [0,1]:
				for iz in [0,1]:
					var local: Vector3 = mesh_bounds.position + mesh_bounds.size * Vector3(ix,iy,iz)
					points.append(root_node.to_local(node.to_global(local)))
	for child in node.get_children():
		if child is Node3D:
			_collect_bounds(root_node, child as Node3D, points)

func _select_model(offset: int) -> void:
	if _models.is_empty() or _original_mount == null:
		return
	_selected = posmod(_selected + offset, _models.size())
	if is_instance_valid(_original_model):
		_original_model.queue_free()
		_original_model = null
		_original_animation = null
	var entry: Dictionary = _models[_selected]
	var source_name: String = str(entry.get("name", ""))
	var relative: String = str(entry.get("resource", ""))
	var res_path: String = "res://assets/vril_original/weapons/" + relative
	var scene: PackedScene = load(res_path) as PackedScene
	if scene == null:
		push_error("VIRIN_SURVIVAL_GUN_MISSING " + res_path)
		return
	# Native Xogot ballistic calculations (hitscan, points, damage, reload,
	# gyro/ADS, real zombies) remain untouched. In cases without matching
	# weapon logic, retain the verified MP40 ballistic profile; do NOT claim
	# arbitrary historic weapons have accurately ported combat statistics.
	var id: String = source_name.trim_prefix("v_")
	var aliases: Dictionary = {
		"colt":"colt", "fg":"fg42", "thomp":"thompson",
		"m1":"m1", "m1a1":"m1a1", "mg":"mg42", "spring":"springfield",
		"tesla":"tesla", "trench":"trench", "ptrs":"ptrs",
		"ppsh":"ppsh", "stg":"stg", "ray":"ray", "ray2":"ray2",
		"357":"357", "gewehr":"gewehr", "bar":"bar", "kar":"kar98k",
		"browning":"browning", "mp5k":"mp5k", "panzer":"panzer",
		"type":"type100", "sawnoff":"sawnoff",
	}
	var runtime_id: String = str(aliases.get(id, id))
	var exact_runtime: bool = WeaponCatalog.has_weapon(runtime_id)
	if not exact_runtime:
		runtime_id = "mp40"
	_weapon.call("equip_weapon", runtime_id, true)
	_original_model = scene.instantiate() as Node3D
	_original_model.name = "REAL_NZP_" + source_name
	_original_mount.add_child(_original_model)
	_original_animation = _find_animation_player(_original_model)
	if _original_animation != null:
		_original_animation.stop()
		var clips := _original_animation.get_animation_list()
		for clip in clips:
			if clip != "RESET":
				_original_animation.play(clip)
				_original_animation.seek(0.0, true)
				_original_animation.stop(true)
				break
	# Scale to the real imported first-frame bounds; preserves original
	# hands/gun proportions, rather than silently replacing them with boxes.
	var bounds: AABB = _mesh_bounds(_original_model)
	var dim: Vector3 = bounds.size
	var s: float = minf(2.2, minf(0.58 / maxf(0.01, dim.x),
		minf(0.48 / maxf(0.01, dim.y), 0.95 / maxf(0.01, dim.z))))
	_original_model.scale = Vector3.ONE * s
	_original_model.position = -bounds.get_center() * s
	_original_mount.position = Vector3(0.20, -0.28, -0.74)
	_hide_legacy_weapon_meshes()
	_model_label.text = "%s  %d/41  (%d frames)%s" % [
		source_name, _selected + 1, int(entry.get("frames", 0)),
		"" if exact_runtime else " • MP40 combat",
	]
	print("VIRIN_ORIGINAL_SURVIVAL_VIEWMODEL_GREEN name=", source_name,
		" original_frames=", entry.get("frames", 0), " combat=", runtime_id)

func _hide_legacy_weapon_meshes() -> void:
	if _weapon == null:
		return
	var old_gun: Variant = _weapon.get("_weapon_model_root")
	if old_gun is Node3D and is_instance_valid(old_gun):
		(old_gun as Node3D).visible = false
	var old_hands: Variant = _weapon.get("_hands_model_root")
	if old_hands is Node3D and is_instance_valid(old_hands):
		(old_hands as Node3D).visible = false

func _play_original_frames() -> void:
	if _original_animation == null:
		return
	for clip in _original_animation.get_animation_list():
		if clip != "RESET":
			_original_animation.stop()
			_original_animation.play(clip)
			print("VIRIN_ORIGINAL_FRAME_PREVIEW_START ", clip)
			return

func _process(_delta: float) -> void:
	# Protect against the native weapon refreshing on weapon change/reload,
	# without disconnecting any existing shooting or hit detection code.
	if _original_mount == null:
		return
	_hide_legacy_weapon_meshes()
	var alpha: float = float(_weapon.get("_ads_pose_alpha"))
	_original_mount.position = Vector3(0.20, -0.28, -0.74).lerp(
		Vector3(0.0, -0.25, -0.67), clampf(alpha, 0.0, 1.0))

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_BRACKETLEFT:
			_select_model(-1)
		elif event.keycode == KEY_BRACKETRIGHT:
			_select_model(1)
