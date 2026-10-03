extends CharacterBody3D

const NAV_PATH := "res://data/nav_skeleton.json"

@export var walk_speed := 4.8
@export var sprint_speed := 8.1
@export var crouch_speed := 3.2
@export var slide_speed := 10.6
@export var slide_duration := 0.62
@export var slide_cooldown := 0.35
@export var jump_velocity := 6.0
@export var mouse_sensitivity := 0.0022
@export var touch_sensitivity := 0.0028
@export var gyro_enabled := true
@export var gyro_sensitivity := 0.70
@export var use_nav_spawn := true
@export var interaction_range := 3.4
@export var starting_points := 500
@export var max_health := 100.0

const STAND_HEAD_Y := 1.62
const CROUCH_HEAD_Y := 1.12
const STAND_CAPSULE_HEIGHT := 1.80
const CROUCH_CAPSULE_HEIGHT := 1.18
const STAND_COLLIDER_Y := 0.90
const CROUCH_COLLIDER_Y := 0.59

var points: int = 0
var health: float = 100.0
var downed: bool = false
var _gravity := 18.0
var _move_touch := -1
var _look_touch := -1
var _crouch_touch := -1
var _fire_touch := -1
var _move_origin := Vector2.ZERO
var _move_vector := Vector2.ZERO
var _jump_requested := false
var _pitch := 0.0
var _crouched := false
var _sliding := false
var _crouch_was_pressed := false
var _slide_timer := 0.0
var _slide_cooldown_timer := 0.0
var _slide_direction := Vector3.ZERO

@onready var _head: Node3D = $Head
@onready var _camera: Camera3D = $Head/Camera3D
@onready var _collider: CollisionShape3D = $CollisionShape3D
@onready var _weapon: Node = $Weapon

func _ready() -> void:
	_gravity = float(ProjectSettings.get_setting("physics/3d/default_gravity", 18.0))
	points = starting_points
	health = max_health
	add_to_group("player")
	if not OS.has_feature("mobile"):
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	if use_nav_spawn:
		_place_at_spawn()
	print("XZOGOT_PLAYER_READY")
	print("XZOGOT_MOVEMENT_V2_READY")
	print("XZOGOT_INTERACTION_PLAYER_READY ", points)

func _b2g(a: Array) -> Vector3:
	return Vector3(float(a[0]), float(a[2]), -float(a[1]))

func _place_at_spawn() -> void:
	if not FileAccess.file_exists(NAV_PATH):
		return
	var f: FileAccess = FileAccess.open(NAV_PATH, FileAccess.READ)
	var nav: Variant = JSON.parse_string(f.get_as_text())
	if nav is Dictionary and nav.has("spawn"):
		global_position = _b2g(nav["spawn"]) + Vector3(0.0, 0.18, 0.0)

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		_apply_look(Vector2(event.relative.x, event.relative.y) * mouse_sensitivity)
	elif event is InputEventKey and event.pressed and (event.keycode == KEY_E or event.keycode == KEY_F):
		request_interact()
	elif event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	elif event is InputEventMouseButton and event.pressed and not OS.has_feature("mobile"):
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	elif event is InputEventScreenTouch:
		_handle_touch(event)
	elif event is InputEventScreenDrag:
		_handle_drag(event)

func _handle_touch(event: InputEventScreenTouch) -> void:
	var size: Vector2 = get_viewport().get_visible_rect().size
	var jump_zone: bool = event.position.x > size.x * 0.84 and event.position.y > size.y * 0.72
	var crouch_zone: bool = event.position.x > size.x * 0.68 and event.position.x <= size.x * 0.84 and event.position.y > size.y * 0.72
	var fire_zone: bool = event.position.x > size.x * 0.84 and event.position.y > size.y * 0.46 and event.position.y <= size.y * 0.72
	var reload_zone: bool = event.position.x > size.x * 0.68 and event.position.x <= size.x * 0.84 and event.position.y > size.y * 0.50 and event.position.y <= size.y * 0.72
	var interact_zone: bool = event.position.x > size.x * 0.52 and event.position.x <= size.x * 0.68 and event.position.y > size.y * 0.66

	if event.pressed:
		if event.position.x < size.x * 0.46 and event.position.y > size.y * 0.22 and _move_touch < 0:
			_move_touch = event.index
			_move_origin = event.position
			_move_vector = Vector2.ZERO
		elif jump_zone:
			_jump_requested = true
		elif crouch_zone and _crouch_touch < 0:
			_crouch_touch = event.index
		elif fire_zone and _fire_touch < 0:
			_fire_touch = event.index
			_weapon.call("set_trigger_held", true)
		elif reload_zone:
			_weapon.call("request_reload")
		elif interact_zone:
			request_interact()
		elif _look_touch < 0:
			_look_touch = event.index
	else:
		if event.index == _move_touch:
			_move_touch = -1
			_move_vector = Vector2.ZERO
		if event.index == _look_touch:
			_look_touch = -1
		if event.index == _crouch_touch:
			_crouch_touch = -1
		if event.index == _fire_touch:
			_fire_touch = -1
			_weapon.call("set_trigger_held", false)

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

func request_interact() -> bool:
	if _camera == null:
		return false
	var world: World3D = _camera.get_world_3d()
	if world == null:
		return false
	var origin: Vector3 = _camera.global_position
	var direction: Vector3 = -_camera.global_transform.basis.z.normalized()
	var target: Vector3 = origin + direction * interaction_range
	var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(origin, target)
	query.exclude = [get_rid()]
	query.collide_with_areas = true
	query.collide_with_bodies = true
	var hit: Dictionary = world.direct_space_state.intersect_ray(query)
	if hit.is_empty():
		return false
	var collider: Object = hit.get("collider") as Object
	return try_interact_with(collider)

func try_interact_with(target: Object) -> bool:
	if target == null or not target.has_method("interact"):
		return false
	return bool(target.call("interact", self))

func spend_points(amount: int) -> bool:
	if amount < 0 or points < amount:
		return false
	points -= amount
	return true

func add_points(amount: int) -> void:
	if amount > 0:
		points += amount

func get_points() -> int:
	return points

func apply_damage(amount: float) -> void:
	if downed or amount <= 0.0:
		return
	health = maxf(0.0, health - amount)
	if health <= 0.0:
		downed = true
		_weapon.call("set_trigger_held", false)
		print("XZOGOT_PLAYER_DOWN")

func heal_full() -> void:
	health = max_health
	downed = false

func get_health() -> float:
	return health

func is_downed() -> bool:
	return downed

func _set_crouched(enabled: bool) -> void:
	if _crouched == enabled:
		return
	_crouched = enabled
	var capsule: CapsuleShape3D = _collider.shape as CapsuleShape3D
	if capsule != null:
		capsule.height = CROUCH_CAPSULE_HEIGHT if enabled else STAND_CAPSULE_HEIGHT
	_collider.position.y = CROUCH_COLLIDER_Y if enabled else STAND_COLLIDER_Y

func _update_stance(delta: float, crouch_pressed: bool) -> void:
	var target_head_y: float = CROUCH_HEAD_Y if (_crouched or _sliding) else STAND_HEAD_Y
	_head.position.y = move_toward(_head.position.y, target_head_y, 5.5 * delta)

	if _sliding:
		_slide_timer -= delta
		if _slide_timer <= 0.0 or not is_on_floor():
			_sliding = false
			_slide_cooldown_timer = slide_cooldown
			if not crouch_pressed:
				_set_crouched(false)
		return

	if crouch_pressed:
		_set_crouched(true)
	else:
		_set_crouched(false)

func _physics_process(delta: float) -> void:
	if _slide_cooldown_timer > 0.0:
		_slide_cooldown_timer = maxf(0.0, _slide_cooldown_timer - delta)

	if gyro_enabled and OS.has_feature("mobile") and _look_touch < 0:
		var gyro: Vector3 = Input.get_gyroscope()
		if gyro.length() > 0.05:
			rotation.y -= gyro.y * gyro_sensitivity * delta
			_pitch = clamp(_pitch - gyro.x * gyro_sensitivity * delta, deg_to_rad(-86.0), deg_to_rad(86.0))
			_head.rotation.x = _pitch

	if not is_on_floor():
		velocity.y -= _gravity * delta
	if (_jump_requested or Input.is_key_pressed(KEY_SPACE)) and is_on_floor() and not _sliding:
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

	var wish := transform.basis * Vector3(input_2d.x, 0.0, input_2d.y)
	wish.y = 0.0
	if wish.length_squared() > 0.001:
		wish = wish.normalized()

	var crouch_pressed: bool = _crouch_touch >= 0 or Input.is_key_pressed(KEY_CTRL) or Input.is_key_pressed(KEY_C)
	var crouch_just_pressed: bool = crouch_pressed and not _crouch_was_pressed
	var sprinting: bool = Input.is_key_pressed(KEY_SHIFT) or input_2d.length() > 0.92

	if crouch_just_pressed and sprinting and input_2d.length() > 0.72 and is_on_floor() and not _sliding and _slide_cooldown_timer <= 0.0:
		_sliding = true
		_slide_timer = slide_duration
		_slide_direction = wish if wish.length_squared() > 0.001 else -transform.basis.z
		_set_crouched(true)

	_update_stance(delta, crouch_pressed)

	if _sliding:
		var slide_factor: float = clampf(_slide_timer / slide_duration, 0.0, 1.0)
		var current_slide_speed: float = lerpf(crouch_speed, slide_speed, slide_factor)
		velocity.x = _slide_direction.x * current_slide_speed
		velocity.z = _slide_direction.z * current_slide_speed
	else:
		var speed: float = crouch_speed if _crouched else (sprint_speed if sprinting else walk_speed)
		velocity.x = move_toward(velocity.x, wish.x * speed, 22.0 * delta)
		velocity.z = move_toward(velocity.z, wish.z * speed, 22.0 * delta)

	move_and_slide()
	_crouch_was_pressed = crouch_pressed
