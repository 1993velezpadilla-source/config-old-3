extends Node3D
## XZIEL / Virin -> Godot 4.6: visual gallery of ORIGINAL NZ:P viewmodels.
## Does not replace game systems or claim all action segments are classified.
## Every source MDL vertex frame was exported into a glTF STEP morph animation.

const CATALOG := "res://assets/vril_original/weapons/catalog.json"
const MAP_DATA := "res://assets/vril_original/dead_cell.json"

var camera: Camera3D
var weapon_mount: Node3D
var weapon_model: Node3D
var weapon_anim: AnimationPlayer
var weapons: Array = []
var selected: int = 0
var status_label: Label
var map_root: Node3D


func _ready() -> void:
	_make_world()
	_make_ui()
	_make_dead_cell()
	_read_catalog()
	if not weapons.is_empty():
		_select(0)


func _make_world() -> void:
	camera = Camera3D.new()
	camera.name = "OriginalVrilFirstPersonCamera"
	camera.current = true
	camera.fov = 75.0
	camera.near = 0.02
	camera.far = 180.0
	camera.position = Vector3(0.0, 1.6, 11.0)
	add_child(camera)
	weapon_mount = Node3D.new()
	weapon_mount.name = "OriginalHandsAndGun"
	camera.add_child(weapon_mount)
	weapon_mount.position = Vector3(0.0, -0.12, -0.14)
	map_root = Node3D.new()
	map_root.name = "DeadCellQuakeMap"
	add_child(map_root)

	var world := WorldEnvironment.new()
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color(0.085, 0.105, 0.13)
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color(0.65, 0.71, 0.83)
	environment.ambient_light_energy = 0.6
	world.environment = environment
	add_child(world)

	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-48, -25, 0)
	sun.light_energy = 1.2
	sun.shadow_enabled = true
	add_child(sun)

	var hand_light := OmniLight3D.new()
	hand_light.omni_range = 5.0
	hand_light.light_energy = 1.1
	hand_light.position = Vector3(0, 0, -1)
	camera.add_child(hand_light)


func _make_ui() -> void:
	var layer := CanvasLayer.new()
	layer.layer = 2
	add_child(layer)
	var hud := PanelContainer.new()
	hud.anchor_right = 1.0
	hud.offset_bottom = 100.0
	layer.add_child(hud)
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	hud.add_child(row)
	var previous := Button.new()
	previous.text = "◀ Previous"
	previous.custom_minimum_size = Vector2(145, 72)
	previous.pressed.connect(func() -> void: _select(-1))
	row.add_child(previous)
	var playback := Button.new()
	playback.text = "▶ Original Frames"
	playback.custom_minimum_size = Vector2(185, 72)
	playback.pressed.connect(_play_original)
	row.add_child(playback)
	var next := Button.new()
	next.text = "Next ▶"
	next.custom_minimum_size = Vector2(145, 72)
	next.pressed.connect(func() -> void: _select(1))
	row.add_child(next)
	status_label = Label.new()
	status_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	status_label.custom_minimum_size = Vector2(420, 65)
	status_label.text = "Virin → Godot 4.6: waiting for original NZ:P imports"
	row.add_child(status_label)


func _make_dead_cell() -> void:
	if not FileAccess.file_exists(MAP_DATA):
		push_warning("DEAD CELL map not yet imported: " + MAP_DATA)
		return
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(MAP_DATA))
	if typeof(data) != TYPE_DICTIONARY:
		push_error("DEAD CELL JSON is invalid")
		return
	var materials: Dictionary = {}
	var count: int = 0
	for item in data.get("brushes", []):
		if not item.get("visible", false):
			continue
		var position := _vector(item.get("position", [0, 0, 0]))
		var size := _vector(item.get("size", [1, 1, 1]))
		size = Vector3(maxf(0.01, size.x), maxf(0.01, size.y), maxf(0.01, size.z))
		var kind: String = str(item.get("classname", "worldspawn"))
		var color := Color(0.28, 0.34, 0.38)
		if kind == "func_door_nzp":
			color = Color(0.52, 0.35, 0.19)
		if not materials.has(kind):
			var material := StandardMaterial3D.new()
			material.albedo_color = color
			material.roughness = 0.78
			materials[kind] = material
		var body := StaticBody3D.new()
		body.name = "QuakeBrush_%03d_%s" % [count, kind]
		body.position = position
		map_root.add_child(body)
		var mesh_instance := MeshInstance3D.new()
		var box := BoxMesh.new()
		box.size = size
		mesh_instance.mesh = box
		mesh_instance.material_override = materials[kind]
		body.add_child(mesh_instance)
		if item.get("solid", false):
			var collision := CollisionShape3D.new()
			var shape := BoxShape3D.new()
			shape.size = size
			collision.shape = shape
			body.add_child(collision)
		count += 1
	# Original gameplay entity positions and properties are preserved in JSON.
	# Only the authoring map is previewed here; QuakeC mechanics are NOT faked.
	for entity in data.get("entities", []):
		if str(entity.get("classname", "")) == "info_player_1_spawn":
			var p := _vector(entity.get("position", [0, 1, 11]))
			camera.position = p + Vector3(0, 0.9, 0)
			break
	print("VRIL_DEAD_CELL_IMPORTED %d visible brushes" % count)


func _vector(values: Array) -> Vector3:
	if values.size() < 3:
		return Vector3.ZERO
	return Vector3(float(values[0]), float(values[1]), float(values[2]))


func _read_catalog() -> void:
	if not FileAccess.file_exists(CATALOG):
		_report("Import output missing: run vril-original-godot-import workflow first")
		return
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(CATALOG))
	if typeof(data) != TYPE_DICTIONARY:
		_report("Invalid catalog JSON")
		return
	weapons = data.get("weapons", [])
	print("VRIL_ORIGINAL_WEAPONS_CATALOG_LOADED count=", weapons.size())


func _select(offset: int) -> void:
	if weapons.is_empty():
		return
	selected = posmod(selected + offset, weapons.size())
	if is_instance_valid(weapon_model):
		weapon_model.queue_free()
		weapon_model = null
		weapon_anim = null
	var entry: Dictionary = weapons[selected]
	var path := "res://assets/vril_original/weapons/" + str(entry.get("resource", ""))
	var packed := load(path) as PackedScene
	if packed == null:
		_report("Cannot load original MDL conversion: " + path)
		return
	weapon_model = packed.instantiate() as Node3D
	if weapon_model == null:
		_report("Weapon GLB is not a scene: " + path)
		return
	weapon_mount.add_child(weapon_model)
	weapon_anim = _animation_player(weapon_model)
	_report("%s  |  %d/%d  |  %d original frames  |  %d tris" % [
		str(entry.get("name", "unknown")),
		selected + 1, weapons.size(),
		int(entry.get("frames", 0)), int(entry.get("triangles", 0)),
	])
	print("VRIL_ORIGINAL_VIEWMODEL_LOADED ", entry.get("name", ""))


func _animation_player(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node as AnimationPlayer
	for child in node.get_children():
		var found := _animation_player(child)
		if found != null:
			return found
	return null


func _play_original() -> void:
	if weapon_anim == null:
		_report("This source model has no imported AnimationPlayer")
		return
	for animation_name in weapon_anim.get_animation_list():
		if animation_name != "RESET":
			weapon_anim.stop()
			weapon_anim.play(animation_name)
			return
	_report("No animation imported from original MDL")


func _report(message: String) -> void:
	if status_label != null:
		status_label.text = message


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_left"):
		_select(-1)
	elif event.is_action_pressed("ui_right"):
		_select(1)
	elif event.is_action_pressed("ui_accept"):
		_play_original()
