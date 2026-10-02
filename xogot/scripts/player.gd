extends CharacterBody3D

const NAV_PATH := "res://data/nav_skeleton.json"

@export var walk_speed := 4.8
@export var sprint_speed := 8.1
@export var jump_velocity := 6.0
@export var mouse_sensitivity := 0.0022
@export var touch_sensitivity := 0.0028
@export var gyro_enabled := true
@export var gyro_sensitivity := 0.70

var _gravity := 18.0
var _move_touch := -1
var _look_touch := -1
var _move_origin := Vector2.ZERO
var _move_vector := Vector2.ZERO
var _jump_requested := false
var _pitch := 0.0

@onready var _head: Node3D = $Head

func _ready() -> void:
	_gravity = float(ProjectSettings.get_setting("physics/3d/default_gravity", 18.0))
	if not OS.has_feature("mobile"):
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	_place_at_spawn()

func _b2g(a: Array) -> Vector3:
	return Vector3(float(a[0]), float(a[2]), -float(a[1]))

func _place_at_spawn() -> void:
	if not FileAccess.file_exists(NAV_PATH):
		return
	var f := FileAccess.open(NAV_PATH, FileAccess.READ)
	var nav = JSON.parse_string(f.get_as_text())
	if nav is Dictionary and nav.has("spawn"):
		global_position = _b2g(nav["spawn"]) + Vector3(0.0, 0.18, 0.0)

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		_apply_look(Vector2(event.relative.x, event.relative.y) * mouse_sensitivity)
	elif event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	elif event is InputEventMouseButton and event.pressed and not OS.has_feature("mobile"):
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	elif event is InputEventScreenTouch:
		_handle_touch(event)
	elif event is InputEventScreenDrag:
		_handle_drag(event)

func _handle_touch(event: InputEventScreenTouch) -> void:
	var size := get_viewport().get_visible_rect().size
	if event.pressed:
		if event.position.x < size.x * 0.46 and event.position.y > size.y * 0.22 and _move_touch < 0:
			_move_touch = event.index
			_move_origin = event.position
			_move_vector = Vector2.ZERO
		elif event.position.x > size.x * 0.80 and event.position.y > size.y * 0.76:
			_jump_requested = true
		elif _look_touch < 0:
			_look_touch = event.index
	else:
		if event.index == _move_touch:
			_move_touch = -1
			_move_vector = Vector2.ZERO
		if event.index == _look_touch:
			_look_touch = -1

func _handle_drag(event: InputEventScreenDrag) -> void:
	if event.index == _move_touch:
		_move_vector = (event.position - _move_origin) / 115.0
		_move_vector = _move_vector.limit_length(1.0)
	elif event.index == _look_touch:
		_apply_look(event.relative * touch_sensitivity)

func _apply_look(delta: Vector2) -> void:
	rotation.y -= delta.x
	_pitch = clamp(_pitch - delta.y, deg_to_rad(-86.0), deg_to_rad(86.0))
	_head.rotation.x = _pitch

func _physics_process(delta: float) -> void:
	if gyro_enabled and OS.has_feature("mobile") and _look_touch < 0:
		var gyro := Input.get_gyroscope()
		if gyro.length() > 0.05:
			rotation.y -= gyro.y * gyro_sensitivity * delta
			_pitch = clamp(_pitch - gyro.x * gyro_sensitivity * delta, deg_to_rad(-86.0), deg_to_rad(86.0))
			_head.rotation.x = _pitch

	if not is_on_floor():
		velocity.y -= _gravity * delta
	if (_jump_requested or Input.is_key_pressed(KEY_SPACE)) and is_on_floor():
		velocity.y = jump_velocity
	_jump_requested = false

	var input_2d := Vector2.ZERO
	input_2d.x = float(Input.is_key_pressed(KEY_D)) - float(Input.is_key_pressed(KEY_A))
	input_2d.y = float(Input.is_key_pressed(KEY_S)) - float(Input.is_key_pressed(KEY_W))
	if _move_touch >= 0:
		input_2d = _move_vector

	var pad := Vector2(Input.get_joy_axis(0, JOY_AXIS_LEFT_X), Input.get_joy_axis(0, JOY_AXIS_LEFT_Y))
	if pad.length() > 0.16:
		input_2d = pad.limit_length(1.0)
	if input_2d.length() > 1.0:
		input_2d = input_2d.normalized()

	var wish := (transform.basis * Vector3(input_2d.x, 0.0, input_2d.y))
	wish.y = 0.0
	if wish.length_squared() > 0.001:
		wish = wish.normalized()

	var sprinting := Input.is_key_pressed(KEY_SHIFT) or input_2d.length() > 0.92
	var speed := sprint_speed if sprinting else walk_speed
	velocity.x = move_toward(velocity.x, wish.x * speed, 22.0 * delta)
	velocity.z = move_toward(velocity.z, wish.z * speed, 22.0 * delta)

	move_and_slide()
