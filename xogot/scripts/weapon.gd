extends Node

@export var damage: float = 30.0
@export var range_m: float = 120.0
@export var fire_interval: float = 0.095
@export var magazine_size: int = 30
@export var reserve_ammo: int = 120
@export var reload_time: float = 1.55

var _magazine: int = 30
var _cooldown: float = 0.0
var _reload_timer: float = 0.0
var _reloading: bool = false
var _trigger_held: bool = false
var _shots_fired: int = 0

@onready var _body: CollisionObject3D = get_parent() as CollisionObject3D
@onready var _camera: Camera3D = get_parent().get_node("Head/Camera3D") as Camera3D

func _ready() -> void:
	_magazine = magazine_size
	print("XZOGOT_WEAPON_READY")

func _process(delta: float) -> void:
	if _cooldown > 0.0:
		_cooldown = maxf(0.0, _cooldown - delta)

	if _reloading:
		_reload_timer -= delta
		if _reload_timer <= 0.0:
			_finish_reload()
		return

	if _trigger_held:
		request_fire()

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		set_trigger_held(event.pressed)
	elif event is InputEventKey and event.pressed and event.keycode == KEY_R:
		request_reload()

func set_trigger_held(held: bool) -> void:
	_trigger_held = held
	if held:
		request_fire()

func request_fire() -> void:
	if _reloading or _cooldown > 0.0:
		return
	if _magazine <= 0:
		request_reload()
		return

	_magazine -= 1
	_cooldown = fire_interval
	_shots_fired += 1
	_fire_hitscan()

func request_reload() -> void:
	if _reloading or _magazine >= magazine_size or reserve_ammo <= 0:
		return
	_reloading = true
	_trigger_held = false
	_reload_timer = reload_time

func _finish_reload() -> void:
	var needed: int = magazine_size - _magazine
	var loaded: int = mini(needed, reserve_ammo)
	_magazine += loaded
	reserve_ammo -= loaded
	_reloading = false
	_reload_timer = 0.0

func _fire_hitscan() -> void:
	if _camera == null or _body == null:
		return
	var origin: Vector3 = _camera.global_position
	var direction: Vector3 = -_camera.global_transform.basis.z.normalized()
	var target: Vector3 = origin + direction * range_m
	var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(origin, target)
	query.exclude = [_body.get_rid()]
	query.collide_with_areas = true
	query.collide_with_bodies = true
	var hit: Dictionary = _camera.get_world_3d().direct_space_state.intersect_ray(query)
	if hit.is_empty():
		return
	var collider: Object = hit.get("collider") as Object
	if collider != null and collider.has_method("apply_damage"):
		collider.call("apply_damage", damage)

func add_reserve_ammo(amount: int) -> void:
	if amount <= 0:
		return
	reserve_ammo += amount

func get_magazine() -> int:
	return _magazine

func get_reserve() -> int:
	return reserve_ammo

func is_reloading() -> bool:
	return _reloading

func get_shots_fired() -> int:
	return _shots_fired
