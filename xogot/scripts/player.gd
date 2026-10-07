extends CharacterBody3D

signal downed_state_changed(is_downed: bool)
signal revived_by(reviver: Node)
signal bled_out()

const MobileLayout = preload("res://scripts/mobile_layout.gd")
const PerkCatalog = preload("res://scripts/perk_catalog.gd")
const SourceModifierPolicy = preload("res://scripts/source_modifier_policy.gd")
const CODSourceContract = preload("res://scripts/cod_source_contract.gd")

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
@export var gyro_mode: int = 2 # 0=OFF, 2=ADS ONLY
@export var gyro_sensitivity := 0.70
@export var gyro_sensitivity_x := 0.70
@export var gyro_sensitivity_y := 0.70
@export var gyro_ads_multiplier := CODSourceContract.GYRO_ADS_MULTIPLIER
@export var gyro_deadzone := 0.05
@export var gyro_smoothing := 0.18
@export var gyro_invert_x := false
@export var gyro_invert_y := false
@export var ads_touch_multiplier := CODSourceContract.ADS_TOUCH_MULTIPLIER
@export var fire_touch_multiplier := CODSourceContract.TOUCH_LOOK_MULTIPLIER
@export var ads_toggle_mode := false
@export var mobile_sprint_zone := 1.10
@export var auto_knife_enabled := true
@export var knife_button_range_only := true
@export var knife_range_m := 1.65
@export var knife_damage := 150.0
@export var knife_cooldown := 0.72
@export var auto_rebuild_enabled := true
@export var repair_repeat_interval := 0.45
@export var base_fov := CODSourceContract.BASE_VERTICAL_FOV
@export var ads_fov := CODSourceContract.ADS_VERTICAL_FOV
@export var sprint_fov := CODSourceContract.SPRINT_VERTICAL_FOV
@export var slide_fov := CODSourceContract.SLIDE_VERTICAL_FOV
@export var camera_stance_response := CODSourceContract.STANCE_EYE_RESPONSE_HZ
@export var landing_spring_frequency := CODSourceContract.LANDING_SPRING_HZ
@export var use_nav_spawn := true
@export var interaction_range := 3.4
@export var starting_points := 500
@export var max_health := 100.0
@export var bleedout_duration := 45.0
@export var revive_hold_duration := 4.0
@export var revive_range := 2.4
@export var revive_health_fraction := 0.50
@export var downed_move_multiplier := 0.32

const PLAYER_RADIUS := CODSourceContract.PLAYER_RADIUS
const STAND_HEAD_Y := CODSourceContract.PLAYER_STAND_EYE_HEIGHT
const CROUCH_HEAD_Y := CODSourceContract.PLAYER_CROUCH_EYE_HEIGHT
const STAND_CAPSULE_HEIGHT := CODSourceContract.PLAYER_STAND_CAPSULE_HEIGHT
const CROUCH_CAPSULE_HEIGHT := CODSourceContract.PLAYER_CROUCH_CAPSULE_HEIGHT
const STAND_COLLIDER_Y := 0.88
const CROUCH_COLLIDER_Y := 0.58

var points: int = 0
var health: float = 100.0
var downed: bool = false
var eliminated: bool = false
var _bleedout_remaining: float = 0.0
var _revive_progress: float = 0.0
var _revive_contact_grace: float = 0.0
var _revive_source: Node = null
var _revive_target: Node = null
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
var _move_raw_vector := Vector2.ZERO
var _sprint_suppressed := false
var _reload_restore_ads := false
var _adsfire_trigger_engaged := false
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
var _dev_infinite_health: bool = false
var _dev_infinite_points: bool = false
var _dev_noclip: bool = false
var _dev_speed_boost: bool = false
var _perks: Dictionary = {}
var _base_max_health: float = 100.0

@onready var _head: Node3D = $Head
@onready var _camera: Camera3D = $Head/Camera3D
@onready var _collider: CollisionShape3D = $CollisionShape3D
@onready var _weapon: Node = $Weapon

func _ready() -> void:
	_gravity = float(ProjectSettings.get_setting("physics/3d/default_gravity", 18.0))
	points = starting_points
	_base_max_health = max_health
	health = max_health
	set_meta("owned_perks", [])
	set_meta("downed", false)
	set_meta("eliminated", false)
	set_meta("bleedout_remaining", 0.0)
	set_meta("revive_progress", 0.0)
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

func _set_mobile_trigger_held(held: bool) -> void:
	if _weapon == null:
		return
	if _weapon.has_method("set_mobile_trigger_held"):
		_weapon.call("set_mobile_trigger_held", held)
	else:
		_weapon.call("set_trigger_held", held)

func _mobile_adsfire_release_mode() -> bool:
	return (
		_weapon != null
		and _weapon.has_method("mobile_adsfire_release_mode")
		and bool(_weapon.call("mobile_adsfire_release_mode"))
	)

func _mobile_adsfire_ready() -> bool:
	if _weapon == null or not _weapon.has_method("is_mobile_ads_ready"):
		return true
	return bool(_weapon.call("is_mobile_ads_ready"))

func _mobile_sprint_zone_hot() -> bool:
	if _move_touch < 0:
		return false
	var forward: float = -_move_raw_vector.y
	return forward >= mobile_sprint_zone and absf(_move_raw_vector.x) <= forward * 0.70

func _suppress_mobile_sprint_for_action() -> void:
	if _sprinting or _mobile_sprint_zone_hot():
		_sprint_suppressed = true
	_sprinting = false

func _request_mobile_reload() -> void:
	if _weapon == null:
		return
	var restore_ads: bool = ads_toggle_mode and bool(get_meta("ads_toggled", false))
	_weapon.call("request_reload")
	if restore_ads and _weapon.has_method("is_reloading") and bool(_weapon.call("is_reloading")):
		_reload_restore_ads = true
		set_meta("ads_toggled", false)

func _update_mobile_reload_ads_restore() -> void:
	if not _reload_restore_ads:
		return
	if downed or eliminated or _sprinting:
		_reload_restore_ads = false
		return
	if _weapon == null or not _weapon.has_method("is_reloading"):
		_reload_restore_ads = false
		return
	if not bool(_weapon.call("is_reloading")):
		set_meta("ads_toggled", true)
		_reload_restore_ads = false

func _update_mobile_adsfire_trigger() -> void:
	if _adsfire_touch < 0 or _mobile_adsfire_release_mode() or _adsfire_trigger_engaged:
		return
	if _mobile_adsfire_ready():
		_set_mobile_trigger_held(true)
		_adsfire_trigger_engaged = true

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
			_adsfire_trigger_engaged = false
			_suppress_mobile_sprint_for_action()
			# PRESS waits for source ADS-ready; RELEASE stays armed until finger-up.
			if not _mobile_adsfire_release_mode() and _mobile_adsfire_ready():
				_set_mobile_trigger_held(true)
				_adsfire_trigger_engaged = true
		elif MobileLayout.inside(event.position, size, MobileLayout.FIRE_CENTER, MobileLayout.FIRE_RADIUS) and _fire_touch < 0:
			_fire_touch = event.index
			_suppress_mobile_sprint_for_action()
			_set_mobile_trigger_held(true)
		elif MobileLayout.inside(event.position, size, MobileLayout.ADS_CENTER, MobileLayout.ADS_RADIUS) and _ads_touch < 0:
			_reload_restore_ads = false
			_suppress_mobile_sprint_for_action()
			if ads_toggle_mode:
				set_meta("ads_toggled", not bool(get_meta("ads_toggled", false)))
			else:
				_ads_touch = event.index
		elif MobileLayout.inside(event.position, size, MobileLayout.RELOAD_CENTER, MobileLayout.RELOAD_RADIUS):
			_request_mobile_reload()
		elif MobileLayout.inside(event.position, size, MobileLayout.SLIDE_CENTER, MobileLayout.SLIDE_RADIUS) and _crouch_touch < 0:
			_crouch_touch = event.index
		elif MobileLayout.inside(event.position, size, MobileLayout.JUMP_CENTER, MobileLayout.JUMP_RADIUS):
			_jump_requested = true
		elif MobileLayout.inside(event.position, size, MobileLayout.USE_CENTER, MobileLayout.USE_RADIUS) and _use_touch < 0:
			_use_touch = event.index
			request_interact()
		elif MobileLayout.inside(event.position, size, MobileLayout.KNIFE_CENTER, MobileLayout.KNIFE_RADIUS) and _knife_touch < 0:
			_knife_touch = event.index
			_suppress_mobile_sprint_for_action()
			request_knife()
		elif MobileLayout.inside(event.position, size, MobileLayout.JOY_CENTER, MobileLayout.JOY_RADIUS) and _move_touch < 0:
			_move_touch = event.index
			_move_origin = MobileLayout.screen_point(MobileLayout.JOY_CENTER, size)
			_move_raw_vector = (event.position - _move_origin) / maxf(MobileLayout.JOY_RADIUS * size.y * 0.90, 1.0)
			_move_vector = _move_raw_vector.limit_length(1.0)
		elif _look_touch < 0:
			_look_touch = event.index
	else:
		if event.index == _move_touch:
			_move_touch = -1
			_move_vector = Vector2.ZERO
			_move_raw_vector = Vector2.ZERO
			_sprint_suppressed = false
		if event.index == _look_touch:
			_look_touch = -1
		if event.index == _crouch_touch:
			_crouch_touch = -1
		if event.index == _ads_touch:
			_ads_touch = -1
		if event.index == _fire_touch:
			_fire_touch = -1
			if _adsfire_touch < 0:
				_set_mobile_trigger_held(false)
		if event.index == _adsfire_touch:
			# Early release before source ADS-ready cancels the shot.
			if _mobile_adsfire_release_mode() and _fire_touch < 0 and _mobile_adsfire_ready():
				if _weapon.has_method("request_mobile_release_fire"):
					_weapon.call("request_mobile_release_fire")
			_adsfire_touch = -1
			_adsfire_trigger_engaged = false
			if _fire_touch < 0:
				_set_mobile_trigger_held(false)
		if event.index == _use_touch:
			_use_touch = -1
		if event.index == _knife_touch:
			_knife_touch = -1

func _handle_drag(event: InputEventScreenDrag) -> void:
	if event.index == _move_touch:
		var size: Vector2 = get_viewport().get_visible_rect().size
		_move_raw_vector = (event.position - _move_origin) / maxf(MobileLayout.JOY_RADIUS * size.y * 0.90, 1.0)
		_move_vector = _move_raw_vector.limit_length(1.0)
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
	mobile_sprint_zone = float(settings.call("get_setting_value", "mobile_sprint_zone"))
	gyro_mode = 0 if int(settings.call("get_setting_value", "gyro_mode")) == 0 else 2
	gyro_enabled = gyro_mode == 2
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

func apply_dev_flags(
	infinite_health: bool,
	infinite_points: bool,
	noclip: bool,
	speed_boost: bool
) -> void:
	_dev_infinite_health = infinite_health
	_dev_infinite_points = infinite_points
	_dev_noclip = noclip
	_dev_speed_boost = speed_boost
	if _dev_infinite_health:
		health = max_health
		downed = false
		eliminated = false
		_bleedout_remaining = 0.0
		_revive_progress = 0.0
		set_meta("downed", false)
		set_meta("eliminated", false)
	if _collider != null:
		_collider.set_deferred("disabled", _dev_noclip)
	set_meta("dev_infinite_health", _dev_infinite_health)
	set_meta("dev_infinite_points", _dev_infinite_points)
	set_meta("dev_noclip", _dev_noclip)
	set_meta("dev_speed_boost", _dev_speed_boost)
	print(
		"XZOGOT_DEV_PLAYER_FLAGS ",
		_dev_infinite_health, " ",
		_dev_infinite_points, " ",
		_dev_noclip, " ",
		_dev_speed_boost
	)


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
	_suppress_mobile_sprint_for_action()

	# COD-style behavior: the knife swing is an input action, not a hit-only
	# animation. Always play the first-person slash; damage is conditional.
	var weapon: Node = get_node_or_null("Weapon")
	if weapon != null and weapon.has_method("play_melee_animation"):
		weapon.call("play_melee_animation")
	_knife_timer = knife_cooldown
	_knife_anim_timer = 0.34

	var zombie: Node3D = _nearest_zombie(knife_range_m)
	if zombie == null:
		print("XZOGOT_KNIFE_MISS no_target")
		return true

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
				print("XZOGOT_KNIFE_MISS blocked")
				return true

	if zombie.has_method("apply_melee_damage"):
		zombie.call("apply_melee_damage", knife_damage, self, zombie.global_position + Vector3(0.0, 0.95, 0.0))
	elif zombie.has_method("apply_damage"):
		zombie.call("apply_damage", knife_damage, self)
	else:
		print("XZOGOT_KNIFE_MISS invalid_target")
		return true

	print("XZOGOT_KNIFE_HIT ", zombie.name)
	return true

func _nearest_downed_teammate(max_distance: float = revive_range) -> Node:
	var best: Node = null
	var best_d2: float = max_distance * max_distance
	for node: Node in get_tree().get_nodes_in_group("player"):
		if node == self or not (node is Node3D):
			continue
		if not node.has_method("is_downed") or not bool(node.call("is_downed")):
			continue
		if node.has_method("is_eliminated") and bool(node.call("is_eliminated")):
			continue
		var d2: float = global_position.distance_squared_to((node as Node3D).global_position)
		if d2 < best_d2:
			best_d2 = d2
			best = node
	return best

func _is_use_held() -> bool:
	return _use_touch >= 0 or Input.is_key_pressed(KEY_E) or Input.is_key_pressed(KEY_F)

func _network_manager() -> Node:
	return get_node_or_null("../NetworkManager")

func _network_client_mode() -> bool:
	var network: Node = _network_manager()
	return (
		network != null
		and network.has_method("get_mode")
		and str(network.call("get_mode")) == "client"
	)

func contribute_revive(target: Node, delta: float) -> bool:
	if downed or eliminated or target == null or delta <= 0.0:
		return false
	if not (target is Node3D):
		return false
	if global_position.distance_to((target as Node3D).global_position) > revive_range:
		return false
	_revive_target = target
	var source_revive_delta: float = delta * SourceModifierPolicy.revive_progress_multiplier(
		has_perk("last_rites")
	)

	var target_peer_id: int = int(target.get_meta("network_peer_id", 0))
	var self_peer_id: int = int(get_meta("network_peer_id", 0))
	var network: Node = _network_manager()
	if (
		network != null
		and target_peer_id > 0
		and target_peer_id != self_peer_id
		and network.has_method("is_network_session")
		and bool(network.call("is_network_session"))
		and network.has_method("submit_revive_hold")
	):
		return bool(network.call("submit_revive_hold", target_peer_id, source_revive_delta))

	if not target.has_method("receive_revive_progress"):
		return false
	return bool(target.call("receive_revive_progress", self, source_revive_delta))

func receive_revive_progress(reviver: Node, delta: float) -> bool:
	if not downed or eliminated or reviver == null or delta <= 0.0:
		return false
	if not (reviver is Node3D):
		return false
	if global_position.distance_to((reviver as Node3D).global_position) > revive_range:
		return false
	if _revive_source != null and _revive_source != reviver:
		_revive_progress = 0.0
	_revive_source = reviver
	_revive_contact_grace = 0.30
	_revive_progress = minf(revive_hold_duration, _revive_progress + delta)
	set_meta("revive_progress", _revive_progress)
	set_meta("revive_progress_ratio", get_revive_progress_ratio())
	if _revive_progress + 0.0001 >= revive_hold_duration:
		_complete_revive(reviver)
	return true

func _complete_revive(reviver: Node) -> void:
	downed = false
	eliminated = false
	health = maxf(1.0, max_health * clampf(revive_health_fraction, 0.05, 1.0))
	_bleedout_remaining = 0.0
	_revive_progress = 0.0
	_revive_contact_grace = 0.0
	_revive_source = null
	set_meta("downed", false)
	set_meta("eliminated", false)
	set_meta("bleedout_remaining", 0.0)
	set_meta("revive_progress", 0.0)
	set_meta("revive_progress_ratio", 0.0)
	downed_state_changed.emit(false)
	revived_by.emit(reviver)
	print("XZOGOT_PLAYER_REVIVED health=", health, " by=", reviver.name if reviver != null else "unknown")

func _enter_downed() -> void:
	if downed:
		return
	downed = true
	eliminated = false
	_bleedout_remaining = maxf(1.0, bleedout_duration)
	_revive_progress = 0.0
	_revive_contact_grace = 0.0
	_revive_source = null
	_sliding = false
	_sprinting = false
	_jump_requested = false
	_reload_restore_ads = false
	set_meta("ads_toggled", false)
	set_meta("downed", true)
	set_meta("eliminated", false)
	set_meta("bleedout_remaining", _bleedout_remaining)
	set_meta("revive_progress", 0.0)
	set_meta("revive_progress_ratio", 0.0)
	if _weapon != null:
		_weapon.call("set_trigger_held", false)
	_set_crouched(true)
	downed_state_changed.emit(true)
	print("XZOGOT_PLAYER_DOWN bleedout=", _bleedout_remaining)

func _bleed_out() -> void:
	if not downed or eliminated:
		return
	eliminated = true
	health = 0.0
	_revive_progress = 0.0
	_revive_source = null
	set_meta("eliminated", true)
	set_meta("revive_progress", 0.0)
	set_meta("revive_progress_ratio", 0.0)
	bled_out.emit()
	print("XZOGOT_PLAYER_BLED_OUT")

func _tick_downed_state(delta: float) -> void:
	# In a network client session, bleedout/revive state comes from the host.
	if _network_client_mode():
		return
	if not downed:
		return
	if eliminated:
		return
	_bleedout_remaining = maxf(0.0, _bleedout_remaining - delta)
	set_meta("bleedout_remaining", _bleedout_remaining)
	if _revive_contact_grace > 0.0:
		_revive_contact_grace = maxf(0.0, _revive_contact_grace - delta)
	if _revive_contact_grace <= 0.0 and _revive_progress > 0.0:
		_revive_progress = 0.0
		_revive_source = null
		set_meta("revive_progress", 0.0)
		set_meta("revive_progress_ratio", 0.0)
		print("XZOGOT_REVIVE_CANCELLED")
	if _bleedout_remaining <= 0.0:
		_bleed_out()

func _update_revive_support(delta: float) -> bool:
	if downed or eliminated:
		_revive_target = null
		return false
	if not _is_use_held():
		_revive_target = null
		return false
	var target: Node = _nearest_downed_teammate(revive_range)
	if target == null:
		_revive_target = null
		return false
	return contribute_revive(target, delta)

func get_bleedout_remaining() -> float:
	return _bleedout_remaining

func get_bleedout_ratio() -> float:
	if not downed:
		return 0.0
	return clampf(_bleedout_remaining / maxf(bleedout_duration, 0.001), 0.0, 1.0)

func get_revive_progress() -> float:
	return _revive_progress

func get_revive_progress_ratio() -> float:
	return clampf(_revive_progress / maxf(revive_hold_duration, 0.001), 0.0, 1.0)

func get_active_revive_progress_ratio() -> float:
	if _revive_target == null or not is_instance_valid(_revive_target):
		return 0.0
	if not _revive_target.has_method("get_revive_progress_ratio"):
		return 0.0
	return float(_revive_target.call("get_revive_progress_ratio"))

func is_reviving_teammate() -> bool:
	return (
		_revive_target != null
		and is_instance_valid(_revive_target)
		and _revive_target.has_method("is_downed")
		and bool(_revive_target.call("is_downed"))
	)

func is_eliminated() -> bool:
	return eliminated

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

	var reviving: bool = _update_revive_support(delta)
	var manual_repair_held: bool = _is_use_held()
	if (
		not downed
		and not eliminated
		and not reviving
		and _repair_timer <= 0.0
		and (auto_rebuild_enabled or manual_repair_held)
	):
		var barricade: Node = _nearest_repairable_barricade()
		if barricade != null and barricade.has_method("interact"):
			if bool(barricade.call("interact", self)):
				_repair_timer = repair_repeat_interval
				print("XZOGOT_BARRICADE_AUTO_REPAIR ", barricade.name)

func request_interact() -> bool:
	if downed or eliminated:
		return false
	var teammate: Node = _nearest_downed_teammate(revive_range)
	if teammate != null:
		_revive_target = teammate
		print("XZOGOT_REVIVE_TARGET ", teammate.name)
		return true
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
	if _network_client_mode() and target is Node:
		var node := target as Node
		if node.is_in_group("zombie_interactable") or node.is_in_group("zombie_barricade"):
			var network: Node = _network_manager()
			if network != null and network.has_method("submit_interaction"):
				return bool(network.call("submit_interaction", node))
	return bool(target.call("interact", self))

func can_buy_perk(id: String) -> bool:
	return PerkCatalog.has_perk(id) and not _perks.has(id) and not downed

func grant_perk(id: String) -> bool:
	if not can_buy_perk(id):
		return false
	_perks[id] = true

	match id:
		"martyrs_blood":
			max_health = SourceModifierPolicy.JUGGERNOG_MAX_HEALTH
			health = max_health
		"quick_hands":
			pass
		"pilgrim_rush":
			pass
		"choir_sight":
			pass
		"twin_bells":
			pass
		"last_rites":
			pass

	set_meta("owned_perks", get_owned_perks())
	set_meta("perk_source_authority", SourceModifierPolicy.AUTHORITY)
	set_meta("perk_source_id_" + id, SourceModifierPolicy.source_perk(id))
	print("XZOGOT_PERK_GRANTED ", id, " source=", SourceModifierPolicy.source_perk(id), " total=", _perks.size())
	return true

func has_perk(id: String) -> bool:
	return _perks.has(id)

func get_owned_perks() -> Array[String]:
	var result: Array[String] = []
	for id_var: Variant in _perks.keys():
		result.append(str(id_var))
	result.sort()
	return result

func get_reload_multiplier() -> float:
	return SourceModifierPolicy.reload_time_multiplier(has_perk("quick_hands"))

func get_move_speed_multiplier() -> float:
	return SourceModifierPolicy.movement_speed_multiplier(has_perk("pilgrim_rush"))

func get_spread_multiplier() -> float:
	return SourceModifierPolicy.spread_multiplier(has_perk("choir_sight"))

func get_recoil_multiplier() -> float:
	# Deadshot removes ADS sway / reduces spread; do not invent a recoil multiplier.
	return 1.0

func get_fire_interval_multiplier() -> float:
	return SourceModifierPolicy.fire_interval_multiplier(has_perk("twin_bells"))

func get_weapon_damage_multiplier_for(_weapon_id: String, weapon_family: String) -> float:
	return SourceModifierPolicy.projectile_damage_multiplier(has_perk("twin_bells"), weapon_family)

func get_weapon_damage_multiplier() -> float:
	# Compatibility path for callers that cannot provide a weapon family.
	return SourceModifierPolicy.DOUBLE_TAP_PROJECTILE_DAMAGE_MULTIPLIER if has_perk("twin_bells") else 1.0

func get_max_health() -> float:
	return max_health

func spend_points(amount: int) -> bool:
	if amount < 0:
		return false
	if _dev_infinite_points:
		return true
	if points < amount:
		return false
	points -= amount
	return true

func add_points(amount: int) -> void:
	if amount > 0:
		var multiplier: int = int(get_tree().get_meta("xz_double_points_multiplier", 1))
		points += amount * maxi(1, multiplier)

func get_points() -> int:
	return 999999 if _dev_infinite_points else points

func apply_authoritative_network_points(server_points: int) -> void:
	if _network_client_mode():
		points = maxi(0, server_points)
		set_meta("network_authoritative_points", points)

func apply_authoritative_network_perks(perk_ids: Array[String]) -> void:
	if not _network_client_mode():
		return
	var had_martyr: bool = _perks.has("martyrs_blood")
	_perks.clear()
	for id: String in perk_ids:
		if PerkCatalog.has_perk(id):
			_perks[id] = true
	var has_martyr: bool = _perks.has("martyrs_blood")
	max_health = maxf(_base_max_health * 2.0, 200.0) if has_martyr else _base_max_health
	if has_martyr and not had_martyr:
		health = max_health
	else:
		health = minf(health, max_health)
	set_meta("owned_perks", get_owned_perks())
	print("XZOGOT_NETWORK_PERKS_SYNC ", get_owned_perks())

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
	if _network_client_mode():
		return
	if _dev_infinite_health:
		health = max_health
		downed = false
		eliminated = false
		_bleedout_remaining = 0.0
		return
	if downed or amount <= 0.0:
		return

	health = maxf(0.0, health - amount)
	if health <= 0.0:
		_enter_downed()

func apply_authoritative_network_vitals(
	server_health: float,
	server_downed: bool,
	server_eliminated: bool,
	server_bleedout: float,
	server_revive_ratio: float
) -> void:
	var was_downed: bool = downed
	health = clampf(server_health, 0.0, max_health)
	downed = server_downed
	eliminated = server_eliminated
	_bleedout_remaining = maxf(0.0, server_bleedout)
	_revive_progress = clampf(server_revive_ratio, 0.0, 1.0) * revive_hold_duration
	set_meta("downed", downed)
	set_meta("eliminated", eliminated)
	set_meta("bleedout_remaining", _bleedout_remaining)
	set_meta("revive_progress", _revive_progress)
	set_meta("revive_progress_ratio", server_revive_ratio)
	if downed and not was_downed:
		_sliding = false
		_sprinting = false
		set_meta("ads_toggled", false)
		if _weapon != null:
			_weapon.call("set_trigger_held", false)
		_set_crouched(true)
		downed_state_changed.emit(true)
	elif was_downed and not downed:
		downed_state_changed.emit(false)
	print(
		"XZOGOT_NETWORK_VITALS peer=", int(get_meta("network_peer_id", 0)),
		" hp=", health,
		" down=", downed,
		" out=", eliminated
	)

func heal_full() -> void:
	health = max_health
	downed = false
	eliminated = false
	_bleedout_remaining = 0.0
	_revive_progress = 0.0
	_revive_source = null
	set_meta("downed", false)
	set_meta("eliminated", false)
	set_meta("bleedout_remaining", 0.0)
	set_meta("revive_progress", 0.0)

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
	if slide_t < CODSourceContract.SLIDE_ENTRY_PHASE:
		var u: float = slide_t / CODSourceContract.SLIDE_ENTRY_PHASE
		return u * u * (3.0 - 2.0 * u)
	if slide_t < CODSourceContract.SLIDE_HOLD_END_PHASE:
		return 1.0
	var u: float = (slide_t - CODSourceContract.SLIDE_HOLD_END_PHASE) / (1.0 - CODSourceContract.SLIDE_HOLD_END_PHASE)
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
	var entering_ads := _is_ads_active()
	var target_fov: float = base_fov
	var source_transition_time: float = -1.0
	if entering_ads:
		target_fov = ads_fov
		if _weapon != null:
			var source_target: float = -1.0
			if _weapon.has_method("get_source_ads_target_fov"):
				source_target = float(_weapon.call("get_source_ads_target_fov", base_fov))
			if source_target > 0.0:
				target_fov = source_target
			elif _weapon.has_method("get_ads_fov"):
				target_fov = float(_weapon.call("get_ads_fov"))
			if _weapon.has_method("get_source_ads_transition_time"):
				source_transition_time = float(_weapon.call("get_source_ads_transition_time", true))
	elif _sliding:
		target_fov = slide_fov
	elif _sprinting:
		target_fov = sprint_fov
	elif _weapon != null and _weapon.has_method("get_source_ads_transition_time"):
		source_transition_time = float(_weapon.call("get_source_ads_transition_time", false))

	if source_transition_time > 0.0 and not _sliding and not _sprinting:
		var full_span := maxf(absf(base_fov - target_fov), 0.001)
		var fov_rate := full_span / source_transition_time
		_camera.fov = move_toward(_camera.fov, target_fov, fov_rate * delta)
		set_meta("camera_ads_transition_authority", "DT_Weapons.WeaponStats.Movement")
	else:
		var blend: float = 1.0 - exp(-10.0 * delta)
		_camera.fov = lerpf(_camera.fov, target_fov, blend)
		set_meta("camera_ads_transition_authority", "SOURCE_PENDING_FALLBACK")

func is_ads_active() -> bool:
	return _is_ads_active()

func _current_ads_move_multiplier() -> float:
	if _weapon != null and _weapon.has_method("get_source_ads_move_multiplier"):
		return float(_weapon.call("get_source_ads_move_multiplier"))
	return 1.0

func gyro_should_apply(mobile_feature: bool = OS.has_feature("mobile")) -> bool:
	return (
		gyro_enabled
		and gyro_mode == 2
		and mobile_feature
		and _is_ads_active()
	)

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
	_head.rotation.z = lerpf(_head.rotation.z, deg_to_rad(-CODSourceContract.SLIDE_CAMERA_ROLL_DEG * sin(slide_pose * PI)), blend)

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
	_tick_downed_state(delta)
	_update_mobile_adsfire_trigger()
	if _slide_cooldown_timer > 0.0:
		_slide_cooldown_timer = maxf(0.0, _slide_cooldown_timer - delta)

	var gyro_active: bool = gyro_should_apply()
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

	if not _dev_noclip:
		if not is_on_floor():
			velocity.y -= _gravity * delta
		if (
			not downed
			and not eliminated
			and (_jump_requested or Input.is_key_pressed(KEY_SPACE))
			and is_on_floor()
			and not _sliding
		):
			velocity.y = jump_velocity
	else:
		velocity = Vector3.ZERO

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

	var crouch_pressed: bool = (
		downed
		or _crouch_touch >= 0
		or Input.is_key_pressed(KEY_CTRL)
		or Input.is_key_pressed(KEY_C)
	)
	var crouch_just_pressed: bool = crouch_pressed and not _crouch_was_pressed
	var touch_sprint_hot: bool = _mobile_sprint_zone_hot()
	if _move_touch >= 0 and not touch_sprint_hot:
		_sprint_suppressed = false
	var sprinting: bool
	if _move_touch >= 0:
		sprinting = touch_sprint_hot and not _sprint_suppressed
	else:
		sprinting = Input.is_key_pressed(KEY_SHIFT) or pad.length() > 0.92
	_sprinting = sprinting and not downed and not eliminated and not _is_ads_active()
	_update_mobile_reload_ads_restore()

	if _dev_noclip:
		var dev_speed: float = sprint_speed * (2.8 if _dev_speed_boost else 1.45)
		var vertical_axis: float = 0.0
		if _jump_requested or Input.is_key_pressed(KEY_SPACE):
			vertical_axis += 1.0
		if crouch_pressed:
			vertical_axis -= 1.0
		global_position += (wish * dev_speed + Vector3.UP * vertical_axis * dev_speed) * delta
		_jump_requested = false
		_update_camera_fov(delta)
		_update_mobile_assists(delta)
		_crouch_was_pressed = crouch_pressed
		return

	_jump_requested = false

	if (
		not downed
		and not eliminated
		and crouch_just_pressed
		and sprinting
		and input_2d.length() > 0.72
		and is_on_floor()
		and not _sliding
		and _slide_cooldown_timer <= 0.0
	):
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
		speed *= get_move_speed_multiplier()
		if _is_ads_active():
			speed *= _current_ads_move_multiplier()
		if downed:
			speed *= downed_move_multiplier
		if eliminated:
			speed = 0.0
		if _dev_speed_boost:
			speed *= 2.35
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
