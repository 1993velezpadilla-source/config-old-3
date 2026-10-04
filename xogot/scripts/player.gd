extends CharacterBody3D

const MobileLayout = preload("res://scripts/mobile_layout.gd")

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
@export var gyro_mode: int = 1 # 0=OFF, 1=ALWAYS, 2=ADS ONLY
@export var gyro_sensitivity := 0.70
@export var gyro_sensitivity_x := 0.70
@export var gyro_sensitivity_y := 0.70
@export var gyro_ads_multiplier := 0.65
@export var gyro_deadzone := 0.05
@export var gyro_smoothing := 0.18
@export var gyro_invert_x := false
@export var gyro_invert_y := false
@export var ads_touch_multiplier := 0.62
@export var fire_touch_multiplier := 1.00
@export var ads_toggle_mode := false
@export var auto_knife_enabled := true
@export var knife_button_range_only := true
@export var knife_range_m := 1.65
@export var knife_damage := 150.0
@export var knife_cooldown := 0.72
@export var auto_rebuild_enabled := true
@export var repair_repeat_interval := 0.45
@export var base_fov := 66.0
@export var ads_fov := 52.0
@export var sprint_fov := 69.0
@export var slide_fov := 70.5
@export var camera_stance_response := 18.0
@export var landing_spring_frequency := 17.0
@export var use_nav_spawn := true
@export var interaction_range := 3.4
@export var starting_points := 500
@export var max_health := 100.0

const PLAYER_RADIUS := 0.36
const STAND_HEAD_Y := 1.60
const CROUCH_HEAD_Y := 1.03
const STAND_CAPSULE_HEIGHT := 1.76
const CROUCH_CAPSULE_HEIGHT := 1.16
const STAND_COLLIDER_Y := 0.88
const CROUCH_COLLIDER_Y := 0.58

var points: int = 0
var health: float = 100.0
var downed: bool = false
var _gravity := 18.0
var _move_touch := -1
var _look_touch := -1
var _crouch_touch := -1
var _fire_touch := -1
var _ads_touch := -1
var _adsfire_touch := -1
var _knife_touch := -1
var _use_touch := -1
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
var _sprinting := false
var _was_on_floor := false
var _land_camera_pos := 0.0
var _land_camera_vel := 0.0
var _knife_timer := 0.0
var _knife_anim_timer := 0.0
var _repair_timer := 0.0
var _gyro_filtered := Vector2.ZERO

@onready var _head: Node3D = $Head
@onready var _camera: Camera3D = $Head/Camera3D
@onready var _collider: CollisionShape3D = $CollisionShape3D
@onready var _weapon: Node = $Weapon

func _ready() -> void:
	_gravity = float(ProjectSettings.get_setting("physics/3d/default_gravity", 18.0))
	points = starting_points
	health = max_health
	add_to_group("player")
	var capsule: CapsuleShape3D = _collider.shape as CapsuleShape3D
	if capsule != null:
		capsule.radius = PLAYER_RADIUS
		capsule.height = STAND_CAPSULE_HEIGHT
	_collider.position.y = STAND_COLLIDER_Y
	_head.position.y = STAND_HEAD_Y
	_camera.fov = base_fov
	_was_on_floor = is_on_floor()
	if not OS.has_feature("mobile"):
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	if use_nav_spawn:
		_place_at_spawn()
	var settings: Node = get_node_or_null("../HUD/MobileSettings")
	if settings != null:
		apply_mobile_settings(settings)
	print("XZOGOT_PLAYER_READY")
	print("XZOGOT_MOVEMENT_V2_READY")
	print("XZOGOT_COD_VIEW_READY")
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
	elif event is InputEventKey and event.pressed and event.keycode == KEY_V:
		request_knife()
	elif event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE:
		var settings: Node = get_node_or_null("../HUD/MobileSettings")
		if settings != null and settings.has_method("toggle_menu"):
			settings.call("toggle_menu")
		else:
			Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	elif event is InputEventMouseButton and event.pressed and not OS.has_feature("mobile"):
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	elif event is InputEventScreenTouch:
		_handle_touch(event)
	elif event is InputEventScreenDrag:
		_handle_drag(event)

func _handle_touch(event: InputEventScreenTouch) -> void:
	var size: Vector2 = get_viewport().get_visible_rect().size
	if event.pressed:
		if MobileLayout.inside(event.position, size, MobileLayout.PAUSE_CENTER, MobileLayout.PAUSE_RADIUS):
			var settings: Node = get_node_or_null("../HUD/MobileSettings")
			if settings != null and settings.has_method("toggle_menu"):
				settings.call("toggle_menu")
			return
		if MobileLayout.inside(event.position, size, MobileLayout.ADSFIRE_CENTER, MobileLayout.ADSFIRE_RADIUS) and _adsfire_touch < 0:
			_adsfire_touch = event.index
			_weapon.call("set_trigger_held", true)
		elif MobileLayout.inside(event.position, size, MobileLayout.FIRE_CENTER, MobileLayout.FIRE_RADIUS) and _fire_touch < 0:
			_fire_touch = event.index
			_weapon.call("set_trigger_held", true)
		elif MobileLayout.inside(event.position, size, MobileLayout.ADS_CENTER, MobileLayout.ADS_RADIUS) and _ads_touch < 0:
			if ads_toggle_mode:
				set_meta("ads_toggled", not bool(get_meta("ads_toggled", false)))
			else:
				_ads_touch = event.index
		elif MobileLayout.inside(event.position, size, MobileLayout.RELOAD_CENTER, MobileLayout.RELOAD_RADIUS):
			_weapon.call("request_reload")
		elif MobileLayout.inside(event.position, size, MobileLayout.SLIDE_CENTER, MobileLayout.SLIDE_RADIUS) and _crouch_touch < 0:
			_crouch_touch = event.index
		elif MobileLayout.inside(event.position, size, MobileLayout.JUMP_CENTER, MobileLayout.JUMP_RADIUS):
			_jump_requested = true
		elif MobileLayout.inside(event.position, size, MobileLayout.USE_CENTER, MobileLayout.USE_RADIUS) and _use_touch < 0:
			_use_touch = event.index
			request_interact()
		elif MobileLayout.inside(event.position, size, MobileLayout.KNIFE_CENTER, MobileLayout.KNIFE_RADIUS) and _knife_touch < 0:
			_knife_touch = event.index
			request_knife()
		elif MobileLayout.inside(event.position, size, MobileLayout.JOY_CENTER, MobileLayout.JOY_RADIUS) and _move_touch < 0:
			_move_touch = event.index
			_move_origin = MobileLayout.screen_point(MobileLayout.JOY_CENTER, size)
			_move_vector = (event.position - _move_origin) / maxf(MobileLayout.JOY_RADIUS * size.y * 0.90, 1.0)
			_move_vector = _move_vector.limit_length(1.0)
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
		if event.index == _ads_touch:
			_ads_touch = -1
		if event.index == _fire_touch:
			_fire_touch = -1
			if _adsfire_touch < 0:
				_weapon.call("set_trigger_held", false)
		if event.index == _adsfire_touch:
			_adsfire_touch = -1
			if _fire_touch < 0:
				_weapon.call("set_trigger_held", false)
		if event.index == _use_touch:
			_use_touch = -1
		if event.index == _knife_touch:
			_knife_touch = -1

func _handle_drag(event: InputEventScreenDrag) -> void:
	if event.index == _move_touch:
		var size: Vector2 = get_viewport().get_visible_rect().size
		_move_vector = (event.position - _move_origin) / maxf(MobileLayout.JOY_RADIUS * size.y * 0.90, 1.0)
		_move_vector = _move_vector.limit_length(1.0)
	elif event.index == _fire_touch:
		_apply_look(event.relative * touch_sensitivity * fire_touch_multiplier)
	elif event.index == _adsfire_touch:
		_apply_look(event.relative * touch_sensitivity * fire_touch_multiplier * ads_touch_multiplier)
	elif event.index == _ads_touch:
		_apply_look(event.relative * touch_sensitivity * ads_touch_multiplier)
	elif event.index == _look_touch:
		var multiplier: float = ads_touch_multiplier if _is_ads_active() else 1.0
		_apply_look(event.relative * touch_sensitivity * multiplier)

func _apply_look(delta: Vector2) -> void:
	rotation.y -= delta.x
	_pitch = clamp(_pitch - delta.y, deg_to_rad(-86.0), deg_to_rad(86.0))
	_head.rotation.x = _pitch

func apply_mobile_settings(settings: Node) -> void:
	if settings == null or not settings.has_method("get_setting_value"):
		return
	ads_toggle_mode = bool(settings.call("get_setting_value", "ads_toggle_mode"))
	gyro_mode = int(settings.call("get_setting_value", "gyro_mode"))
	gyro_enabled = gyro_mode != 0
	gyro_invert_x = bool(settings.call("get_setting_value", "gyro_invert_x"))
	gyro_invert_y = bool(settings.call("get_setting_value", "gyro_invert_y"))
	gyro_sensitivity_x = float(settings.call("get_setting_value", "gyro_sensitivity_x"))
	gyro_sensitivity_y = float(settings.call("get_setting_value", "gyro_sensitivity_y"))
	gyro_ads_multiplier = float(settings.call("get_setting_value", "gyro_ads_multiplier"))
	gyro_deadzone = float(settings.call("get_setting_value", "gyro_deadzone"))
	gyro_smoothing = float(settings.call("get_setting_value", "gyro_smoothing"))
	auto_knife_enabled = bool(settings.call("get_setting_value", "auto_knife"))
	knife_button_range_only = bool(settings.call("get_setting_value", "knife_button_range_only"))
	knife_range_m = float(settings.call("get_setting_value", "knife_range_m"))
	auto_rebuild_enabled = bool(settings.call("get_setting_value", "auto_rebuild"))
	repair_repeat_interval = float(settings.call("get_setting_value", "repair_repeat_interval"))
	print("XZOGOT_PLAYER_SETTINGS_APPLIED")

func _nearest_zombie(max_distance: float) -> Node3D:
	var best: Node3D = null
	var best_d2: float = max_distance * max_distance
	for node: Node in get_tree().get_nodes_in_group("zombie"):
		if not (node is Node3D):
			continue
		var zombie := node as Node3D
		var d2: float = global_position.distance_squared_to(zombie.global_position)
		if d2 < best_d2:
			best_d2 = d2
			best = zombie
	return best

func is_knife_target_near() -> bool:
	return _nearest_zombie(knife_range_m) != null

func is_knifing() -> bool:
	return _knife_anim_timer > 0.0

func request_knife() -> bool:
	if downed or _knife_timer > 0.0:
		return false
	var zombie: Node3D = _nearest_zombie(knife_range_m)
	if zombie == null:
		return false

	var world: World3D = get_world_3d()
	if world != null:
		var origin: Vector3 = _camera.global_position
		var target: Vector3 = zombie.global_position + Vector3(0.0, 0.9, 0.0)
		var ray := PhysicsRayQueryParameters3D.create(origin, target)
		ray.exclude = [get_rid()]
		var hit: Dictionary = world.direct_space_state.intersect_ray(ray)
		if not hit.is_empty():
			var collider: Object = hit.get("collider") as Object
			if collider != zombie:
				return false

	if zombie.has_method("apply_melee_damage"):
		zombie.call("apply_melee_damage", knife_damage, self, zombie.global_position + Vector3(0.0, 0.95, 0.0))
	elif zombie.has_method("apply_damage"):
		zombie.call("apply_damage", knife_damage, self)
	else:
		return false

	_knife_timer = knife_cooldown
	_knife_anim_timer = 0.22
	print("XZOGOT_KNIFE_HIT ", zombie.name)
	return true

func _nearest_repairable_barricade() -> Node:
	var best: Node = null
	var best_d2: float = interaction_range * interaction_range
	for barricade: Node in get_tree().get_nodes_in_group("zombie_barricade"):
		if not barricade.has_method("get_boards") or not barricade.has_method("get_max_boards"):
			continue
		if int(barricade.call("get_boards")) >= int(barricade.call("get_max_boards")):
			continue
		if not (barricade is Node3D):
			continue
		var d2: float = global_position.distance_squared_to((barricade as Node3D).global_position)
		if d2 < best_d2:
			best_d2 = d2
			best = barricade
	return best

func _update_mobile_assists(delta: float) -> void:
	_knife_timer = maxf(0.0, _knife_timer - delta)
	_knife_anim_timer = maxf(0.0, _knife_anim_timer - delta)
	_repair_timer = maxf(0.0, _repair_timer - delta)

	if auto_knife_enabled and _knife_timer <= 0.0 and is_knife_target_near():
		request_knife()

	var manual_repair_held: bool = _use_touch >= 0 or Input.is_key_pressed(KEY_E) or Input.is_key_pressed(KEY_F)
	if _repair_timer <= 0.0 and (auto_rebuild_enabled or manual_repair_held):
		var barricade: Node = _nearest_repairable_barricade()
		if barricade != null and barricade.has_method("interact"):
			if bool(barricade.call("interact", self)):
				_repair_timer = repair_repeat_interval
				print("XZOGOT_BARRICADE_AUTO_REPAIR ", barricade.name)

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

func get_move_vector() -> Vector2:
	return _move_vector

func is_move_touch_active() -> bool:
	return _move_touch >= 0

func is_fire_pressed() -> bool:
	return _fire_touch >= 0

func is_ads_pressed() -> bool:
	return _is_ads_active() and _adsfire_touch < 0

func is_adsfire_pressed() -> bool:
	return _adsfire_touch >= 0

func is_slide_pressed() -> bool:
	return _crouch_touch >= 0

func is_sprinting() -> bool:
	return _sprinting

func is_sliding() -> bool:
	return _sliding

func get_camera_eye_height() -> float:
	return _head.position.y

func get_camera_fov() -> float:
	return _camera.fov

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

func _is_ads_active() -> bool:
	return bool(get_meta("ads_toggled", false)) or _ads_touch >= 0 or _adsfire_touch >= 0

func _slide_visual_pose() -> float:
	if not _sliding or slide_duration <= 0.001:
		return 0.0
	var slide_t: float = clampf(1.0 - (_slide_timer / slide_duration), 0.0, 1.0)
	if slide_t < 0.14:
		var u: float = slide_t / 0.14
		return u * u * (3.0 - 2.0 * u)
	if slide_t < 0.72:
		return 1.0
	var u: float = (slide_t - 0.72) / 0.28
	var smooth: float = u * u * (3.0 - 2.0 * u)
	return 1.0 - smooth

func _update_landing_spring(delta: float) -> void:
	var frequency: float = landing_spring_frequency
	var acceleration: float = (-frequency * frequency * _land_camera_pos) - (2.0 * frequency * _land_camera_vel)
	_land_camera_vel += acceleration * delta
	_land_camera_pos += _land_camera_vel * delta
	_land_camera_pos = clampf(_land_camera_pos, -0.060, 0.012)
	if absf(_land_camera_pos) < 0.00005 and absf(_land_camera_vel) < 0.0005:
		_land_camera_pos = 0.0
		_land_camera_vel = 0.0

func _update_camera_fov(delta: float) -> void:
	var target_fov: float = base_fov
	if _is_ads_active():
		target_fov = ads_fov
		if _weapon != null and _weapon.has_method("get_ads_fov"):
			target_fov = float(_weapon.call("get_ads_fov"))
	elif _sliding:
		target_fov = slide_fov
	elif _sprinting:
		target_fov = sprint_fov
	var blend: float = 1.0 - exp(-10.0 * delta)
	_camera.fov = lerpf(_camera.fov, target_fov, blend)

func is_ads_active() -> bool:
	return _is_ads_active()

func _update_stance(delta: float, crouch_pressed: bool) -> void:
	_update_landing_spring(delta)
	var slide_pose: float = _slide_visual_pose()
	var target_head_y: float = CROUCH_HEAD_Y if (_crouched or _sliding) else STAND_HEAD_Y
	if _sprinting and not _crouched and not _sliding:
		target_head_y -= 0.025
	target_head_y -= 0.080 * slide_pose
	target_head_y += _land_camera_pos
	var blend: float = 1.0 - exp(-camera_stance_response * delta)
	_head.position.y = lerpf(_head.position.y, target_head_y, blend)
	_head.rotation.z = lerpf(_head.rotation.z, deg_to_rad(-1.15 * sin(slide_pose * PI)), blend)

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

	var gyro_active: bool = gyro_enabled and gyro_mode != 0 and OS.has_feature("mobile")
	if gyro_mode == 2 and not _is_ads_active():
		gyro_active = false
	if gyro_active:
		var gyro: Vector3 = Input.get_gyroscope()
		var raw := Vector2(gyro.y, gyro.x)
		if absf(raw.x) < gyro_deadzone:
			raw.x = 0.0
		if absf(raw.y) < gyro_deadzone:
			raw.y = 0.0
		if gyro_invert_x:
			raw.x = -raw.x
		if gyro_invert_y:
			raw.y = -raw.y
		var smoothing_blend: float = 1.0 if gyro_smoothing <= 0.001 else (1.0 - exp(-delta / maxf(gyro_smoothing, 0.001)))
		_gyro_filtered = _gyro_filtered.lerp(raw, smoothing_blend)
		var gyro_mult: float = gyro_ads_multiplier if _is_ads_active() else 1.0
		rotation.y -= _gyro_filtered.x * gyro_sensitivity_x * gyro_mult * delta
		_pitch = clamp(_pitch - _gyro_filtered.y * gyro_sensitivity_y * gyro_mult * delta, deg_to_rad(-86.0), deg_to_rad(86.0))
		_head.rotation.x = _pitch
	else:
		_gyro_filtered = _gyro_filtered.lerp(Vector2.ZERO, minf(delta * 12.0, 1.0))

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
	_sprinting = sprinting and not _is_ads_active()

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
		var speed: float = crouch_speed if _crouched else (sprint_speed if _sprinting else walk_speed)
		velocity.x = move_toward(velocity.x, wish.x * speed, 22.0 * delta)
		velocity.z = move_toward(velocity.z, wish.z * speed, 22.0 * delta)

	var vertical_before_move: float = velocity.y
	move_and_slide()
	if not _was_on_floor and is_on_floor() and vertical_before_move < -3.0:
		var impact: float = minf(absf(vertical_before_move), 18.0)
		_land_camera_vel -= impact * 0.18
	_was_on_floor = is_on_floor()
	_update_camera_fov(delta)
	_update_mobile_assists(delta)
	_crouch_was_pressed = crouch_pressed
