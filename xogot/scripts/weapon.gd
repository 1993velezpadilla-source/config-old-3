extends Node

const WeaponCatalog = preload("res://scripts/weapon_catalog.gd")
const WeaponAssetRegistry = preload("res://scripts/weapon_asset_registry.gd")

@export var damage: float = 24.0
@export var range_m: float = 95.0
@export var fire_interval: float = 0.17
@export var magazine_size: int = 8
@export var reserve_ammo: int = 80
@export var reload_time: float = 1.48

var _weapon_id: String = WeaponCatalog.STARTING_WEAPON_ID
var _display_name: String = "Colt"
var _family: String = "pistol"
var _automatic: bool = false
var _pellets: int = 1
var _ads_fov: float = 49.0
var _hip_spread_deg: float = 1.45
var _ads_spread_deg: float = 0.28
var _visual_recoil_deg: float = 1.55

var _magazine: int = 8
var _cooldown: float = 0.0
var _reload_timer: float = 0.0
var _reloading: bool = false
var _trigger_held: bool = false
var _shots_fired: int = 0
var _mystery_serial: int = 0
var _visual_recoil_pitch: float = 0.0
var _visual_recoil_velocity: float = 0.0
var _view_root: Node3D
var _fire_audio: AudioStreamPlayer3D
var _reload_audio: AudioStreamPlayer3D
var _mechanical_audio: AudioStreamPlayer3D
var _dry_fire_audio: AudioStreamPlayer3D
var _asset_animation_player: AnimationPlayer
var _last_ads_state: bool = false
var _dev_infinite_ammo: bool = false
var _upgraded_ids: Dictionary = {}
var _upgraded: bool = false

@onready var _body: CollisionObject3D = get_parent() as CollisionObject3D
@onready var _camera: Camera3D = get_parent().get_node("Head/Camera3D") as Camera3D

func _ready() -> void:
	_build_view_runtime()
	equip_weapon(WeaponCatalog.STARTING_WEAPON_ID, true)
	print("XZOGOT_WEAPON_READY")
	print("XZOGOT_WEAPON_CATALOG_READY ", WeaponCatalog.WEAPONS.size())

func _process(delta: float) -> void:
	if _cooldown > 0.0:
		_cooldown = maxf(0.0, _cooldown - delta)

	if _reloading:
		_reload_timer -= delta
		if _reload_timer <= 0.0:
			_finish_reload()
	else:
		if _trigger_held and _automatic:
			request_fire()

	_update_asset_animation_state()
	_update_visual_recoil(delta)

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		set_trigger_held(event.pressed)
	elif event is InputEventKey and event.pressed and event.keycode == KEY_R:
		request_reload()

func _build_view_runtime() -> void:
	if _camera == null:
		return
	_view_root = Node3D.new()
	_view_root.name = "WeaponViewRoot"
	_view_root.position = Vector3(0.22, -0.20, -0.48)
	_camera.add_child(_view_root)

	_fire_audio = AudioStreamPlayer3D.new()
	_fire_audio.name = "WeaponFireAudio"
	_fire_audio.unit_size = 1.4
	_fire_audio.max_distance = 55.0
	_camera.add_child(_fire_audio)

	_reload_audio = AudioStreamPlayer3D.new()
	_reload_audio.name = "WeaponReloadAudio"
	_reload_audio.unit_size = 1.2
	_reload_audio.max_distance = 24.0
	_camera.add_child(_reload_audio)

	_mechanical_audio = AudioStreamPlayer3D.new()
	_mechanical_audio.name = "WeaponMechanicalAudio"
	_mechanical_audio.unit_size = 1.0
	_mechanical_audio.max_distance = 18.0
	_camera.add_child(_mechanical_audio)

	_dry_fire_audio = AudioStreamPlayer3D.new()
	_dry_fire_audio.name = "WeaponDryFireAudio"
	_dry_fire_audio.unit_size = 0.9
	_dry_fire_audio.max_distance = 14.0
	_camera.add_child(_dry_fire_audio)

func _clear_view_model() -> void:
	_asset_animation_player = null
	if _view_root == null:
		return
	for child: Node in _view_root.get_children():
		child.queue_free()

func _build_fallback_view_model() -> void:
	if _view_root == null:
		return

	var metal := StandardMaterial3D.new()
	metal.albedo_color = Color(0.075, 0.072, 0.067)
	metal.roughness = 0.40
	metal.metallic = 0.72

	var wood := StandardMaterial3D.new()
	wood.albedo_color = Color(0.16, 0.082, 0.035)
	wood.roughness = 0.72

	var receiver := MeshInstance3D.new()
	receiver.name = "FallbackReceiver"
	var receiver_mesh := BoxMesh.new()
	var receiver_size := Vector3(0.11, 0.10, 0.34)
	if _family == "pistol":
		receiver_size = Vector3(0.09, 0.09, 0.22)
	elif _family == "shotgun":
		receiver_size = Vector3(0.12, 0.11, 0.48)
	elif _family == "lmg":
		receiver_size = Vector3(0.14, 0.14, 0.52)
	elif _family == "sniper":
		receiver_size = Vector3(0.10, 0.10, 0.58)
	elif _family == "wonder":
		receiver_size = Vector3(0.14, 0.14, 0.38)
	receiver_mesh.size = receiver_size
	receiver_mesh.material = metal
	receiver.mesh = receiver_mesh
	receiver.position.z = -receiver_size.z * 0.45
	_view_root.add_child(receiver)

	var barrel := MeshInstance3D.new()
	barrel.name = "FallbackBarrel"
	var barrel_mesh := CylinderMesh.new()
	barrel_mesh.top_radius = 0.018
	barrel_mesh.bottom_radius = 0.022
	barrel_mesh.height = 0.30 if _family != "pistol" else 0.16
	barrel_mesh.radial_segments = 10
	barrel_mesh.material = metal
	barrel.mesh = barrel_mesh
	barrel.rotation_degrees.x = 90.0
	barrel.position = Vector3(0.0, 0.015, -receiver_size.z * 0.90 - barrel_mesh.height * 0.42)
	_view_root.add_child(barrel)

	if _family in ["rifle", "smg", "shotgun", "lmg", "sniper"]:
		var stock := MeshInstance3D.new()
		stock.name = "FallbackStock"
		var stock_mesh := BoxMesh.new()
		stock_mesh.size = Vector3(0.10, 0.13, 0.28)
		stock_mesh.material = wood
		stock.mesh = stock_mesh
		stock.position = Vector3(0.0, -0.025, 0.20)
		stock.rotation_degrees.x = -7.0
		_view_root.add_child(stock)

	set_meta("weapon_view_fallback", true)

func _find_animation_player(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node as AnimationPlayer
	for child: Node in node.get_children():
		var found := _find_animation_player(child)
		if found != null:
			return found
	return null

func _play_asset_animation(role: String, blend: float = 0.06) -> bool:
	if _asset_animation_player == null or not is_instance_valid(_asset_animation_player):
		return false
	var animation_name: String = WeaponAssetRegistry.animation_name_for_role(_weapon_id, role)
	if animation_name.is_empty() or not _asset_animation_player.has_animation(animation_name):
		return false
	_asset_animation_player.play(animation_name, blend)
	return true

func _ensure_asset_idle() -> void:
	if _asset_animation_player == null or not is_instance_valid(_asset_animation_player):
		return
	if _asset_animation_player.is_playing():
		return
	_play_asset_animation("idle", 0.10)

func _update_asset_animation_state() -> void:
	var ads_now: bool = is_ads_active()
	if ads_now != _last_ads_state:
		_last_ads_state = ads_now
		if not _reloading:
			_play_asset_animation("ads_in" if ads_now else "ads_out", 0.05)
	elif not _reloading and _cooldown <= 0.0:
		_ensure_asset_idle()

func play_melee_animation() -> void:
	_play_asset_animation("melee", 0.04)

func get_mapmod_asset_status() -> Dictionary:
	return WeaponAssetRegistry.inspect(_weapon_id)

func get_worldmodel_path() -> String:
	return WeaponAssetRegistry.preferred_worldmodel_path(_weapon_id)

func _load_optional_asset(path: String) -> Resource:
	if path.is_empty() or not ResourceLoader.exists(path):
		return null
	return load(path)

func _refresh_view_assets(def: Dictionary) -> void:
	_clear_view_model()
	set_meta("weapon_view_fallback", false)

	var fallback_model_path: String = str(def.get("model_path", ""))
	var model_path: String = WeaponAssetRegistry.preferred_viewmodel_path(_weapon_id, fallback_model_path)
	var using_mapmod: bool = model_path != fallback_model_path
	var model_res: Resource = _load_optional_asset(model_path)
	if model_res is PackedScene and _view_root != null:
		var model: Node = (model_res as PackedScene).instantiate()
		model.name = "MapModWeaponModel" if using_mapmod else "AuthoredWeaponModel"
		_view_root.add_child(model)
		_asset_animation_player = _find_animation_player(model)
		set_meta("weapon_asset_lane", "mapmod" if using_mapmod else "legacy_optional")
		print(
			"XZOGOT_WEAPON_MODEL_LOADED ",
			_weapon_id,
			" lane=",
			"mapmod" if using_mapmod else "legacy_optional"
		)
	else:
		_build_fallback_view_model()
		set_meta("weapon_asset_lane", "procedural_fallback")
		print("XZOGOT_WEAPON_MODEL_PENDING ", _weapon_id, " ", model_path)

	if _fire_audio != null:
		var fire_path: String = WeaponAssetRegistry.preferred_audio_path(
			_weapon_id,
			"fire",
			str(def.get("fire_audio", ""))
		)
		var fire_res: Resource = _load_optional_asset(fire_path)
		_fire_audio.stream = fire_res as AudioStream
		if _fire_audio.stream == null:
			print("XZOGOT_WEAPON_FIRE_AUDIO_PENDING ", _weapon_id)

	if _reload_audio != null:
		var reload_path: String = WeaponAssetRegistry.preferred_audio_path(
			_weapon_id,
			"reload",
			str(def.get("reload_audio", ""))
		)
		var reload_res: Resource = _load_optional_asset(reload_path)
		_reload_audio.stream = reload_res as AudioStream

	if _mechanical_audio != null:
		var mechanical_path := WeaponAssetRegistry.preferred_audio_path(_weapon_id, "mechanical")
		_mechanical_audio.stream = _load_optional_asset(mechanical_path) as AudioStream

	if _dry_fire_audio != null:
		var dry_path := WeaponAssetRegistry.preferred_audio_path(_weapon_id, "dry_fire")
		_dry_fire_audio.stream = _load_optional_asset(dry_path) as AudioStream

func _player_modifier(method_name: String, default_value: float = 1.0) -> float:
	if _body != null and _body.has_method(method_name):
		return float(_body.call(method_name))
	return default_value

func _apply_upgrade_stats() -> void:
	if not _upgraded:
		return
	damage *= 1.85
	fire_interval *= 0.92
	magazine_size = maxi(magazine_size + 1, int(ceil(float(magazine_size) * 1.35)))
	reload_time *= 0.90
	_display_name = "SANCTIFIED " + _display_name

func can_upgrade_current_weapon() -> bool:
	return not _weapon_id.is_empty() and WeaponCatalog.has_weapon(_weapon_id) and not _upgraded

func upgrade_current_weapon() -> bool:
	if not can_upgrade_current_weapon():
		return false
	_upgraded_ids[_weapon_id] = true
	var id := _weapon_id
	if not equip_weapon(id, true):
		_upgraded_ids.erase(id)
		return false
	set_meta("weapon_upgraded", true)
	print("XZOGOT_WEAPON_SANCTIFIED ", id)
	return true

func is_upgraded() -> bool:
	return _upgraded

func get_runtime_stats() -> Dictionary:
	return {
		"id": _weapon_id,
		"display_name": _display_name,
		"damage": damage,
		"fire_interval": fire_interval,
		"magazine_size": magazine_size,
		"reload_time": reload_time,
		"hip_spread_deg": _hip_spread_deg,
		"ads_spread_deg": _ads_spread_deg,
		"visual_recoil_deg": _visual_recoil_deg,
		"upgraded": _upgraded,
	}

func equip_weapon(id: String, refill: bool = true) -> bool:
	if not WeaponCatalog.has_weapon(id):
		return false

	var def: Dictionary = WeaponCatalog.get_weapon(id)
	_weapon_id = id
	_display_name = str(def.get("display_name", id))
	_family = str(def.get("family", "rifle"))
	damage = float(def.get("damage", 30.0))
	range_m = float(def.get("range_m", 120.0))
	fire_interval = float(def.get("fire_interval", 0.10))
	magazine_size = int(def.get("magazine", 30))
	reload_time = float(def.get("reload_time", 1.55))
	_automatic = bool(def.get("automatic", false))
	_pellets = maxi(1, int(def.get("pellets", 1)))
	_ads_fov = float(def.get("ads_fov", 48.0))
	_hip_spread_deg = float(def.get("hip_spread_deg", 1.5))
	_ads_spread_deg = float(def.get("ads_spread_deg", 0.25))
	_visual_recoil_deg = float(def.get("visual_recoil_deg", 1.2))
	_upgraded = bool(_upgraded_ids.get(id, false))
	_apply_upgrade_stats()

	if refill:
		_magazine = magazine_size
		reserve_ammo = int(def.get("reserve", magazine_size * 4))
	else:
		_magazine = mini(_magazine, magazine_size)

	_reloading = false
	_reload_timer = 0.0
	_cooldown = 0.0
	_trigger_held = false
	_refresh_view_assets(def)
	_last_ads_state = is_ads_active()
	_play_asset_animation("equip", 0.0)

	set_meta("weapon_id", _weapon_id)
	set_meta("weapon_family", _family)
	set_meta("weapon_upgraded", _upgraded)
	print(
		"XZOGOT_WEAPON_EQUIPPED ",
		_weapon_id,
		" mag=", magazine_size,
		" reserve=", reserve_ammo,
		" ads=", _ads_fov
	)
	return true

func apply_authoritative_network_loadout(
	id: String,
	magazine: int,
	reserve: int,
	upgraded: bool
) -> bool:
	if not WeaponCatalog.has_weapon(id):
		return false
	if upgraded:
		_upgraded_ids[id] = true
	else:
		_upgraded_ids.erase(id)
	if not equip_weapon(id, true):
		return false
	_magazine = clampi(magazine, 0, magazine_size)
	reserve_ammo = maxi(0, reserve)
	_reloading = false
	_reload_timer = 0.0
	set_meta("weapon_upgraded", _upgraded)
	print(
		"XZOGOT_NETWORK_LOADOUT_SYNC ", id,
		" mag=", _magazine,
		" reserve=", reserve_ammo,
		" upgraded=", _upgraded
	)
	return true

func buy_wall_weapon(id: String, player: Node) -> bool:
	if not WeaponCatalog.has_weapon(id):
		return false
	var def: Dictionary = WeaponCatalog.get_weapon(id)
	var same_weapon: bool = id == _weapon_id
	var cost: int = WeaponCatalog.ammo_cost(id) if same_weapon else int(def.get("wall_cost", -1))
	if cost < 0:
		return false
	if player == null or not player.has_method("spend_points"):
		return false
	if not bool(player.call("spend_points", cost)):
		return false

	if same_weapon:
		reserve_ammo += int(def.get("reserve", magazine_size * 4))
		print("XZOGOT_WALLBUY_AMMO ", id, " cost=", cost)
	else:
		equip_weapon(id, true)
		print("XZOGOT_WALLBUY_WEAPON ", id, " cost=", cost)
	return true

func roll_mystery_weapon() -> String:
	_mystery_serial += 1
	var result: String = WeaponCatalog.roll_mystery(_mystery_serial, _weapon_id)
	equip_weapon(result, true)
	print("XZOGOT_MYSTERY_RESULT ", result, " spin=", _mystery_serial)
	return result

func set_trigger_held(held: bool) -> void:
	var pressed_now: bool = held and not _trigger_held
	_trigger_held = held
	if pressed_now:
		request_fire()

func request_fire() -> void:
	if _reloading or _cooldown > 0.0:
		return
	if _magazine <= 0:
		if reserve_ammo > 0:
			request_reload()
		else:
			if _dry_fire_audio != null and _dry_fire_audio.stream != null:
				_dry_fire_audio.play()
			print("XZOGOT_WEAPON_DRY_FIRE ", _weapon_id)
		return

	if not _dev_infinite_ammo:
		_magazine -= 1
	_cooldown = fire_interval * _player_modifier("get_fire_interval_multiplier")
	_shots_fired += 1
	_apply_recoil_impulse()
	_play_asset_animation("fire", 0.025)
	if _fire_audio != null and _fire_audio.stream != null:
		_fire_audio.play()
	if _mechanical_audio != null and _mechanical_audio.stream != null:
		_mechanical_audio.play()

	var ads: bool = is_ads_active()
	var spread: float = (_ads_spread_deg if ads else _hip_spread_deg) * _player_modifier("get_spread_multiplier")
	for pellet in range(_pellets):
		_fire_hitscan(spread, pellet)
	print("XZOGOT_WEAPON_FIRED ", _weapon_id, " ads=", ads, " pellets=", _pellets)

func request_reload() -> void:
	if _dev_infinite_ammo:
		_magazine = magazine_size
		_reloading = false
		return
	if _reloading or _magazine >= magazine_size or reserve_ammo <= 0:
		return
	_reloading = true
	_trigger_held = false
	_reload_timer = reload_time * _player_modifier("get_reload_multiplier")
	_play_asset_animation("reload", 0.06)
	if _reload_audio != null and _reload_audio.stream != null:
		_reload_audio.play()

func _finish_reload() -> void:
	if _dev_infinite_ammo:
		_magazine = magazine_size
		_reloading = false
		_reload_timer = 0.0
		return
	var needed: int = magazine_size - _magazine
	var loaded: int = mini(needed, reserve_ammo)
	_magazine += loaded
	reserve_ammo -= loaded
	_reloading = false
	_reload_timer = 0.0

func is_ads_active() -> bool:
	if _body != null and _body.has_method("is_ads_active"):
		return bool(_body.call("is_ads_active"))
	return false

func _spread_direction(base: Vector3, spread_deg: float, pellet: int) -> Vector3:
	if spread_deg <= 0.001 or _camera == null:
		return base

	# Deterministic shot cone: multiplayer/server authority can reproduce this from
	# weapon id + shot serial + pellet index without relying on wall-clock RNG.
	var seed_text: String = "%s:%d:%d" % [_weapon_id, _shots_fired, pellet]
	var seed: int = abs(seed_text.hash())
	var rng := RandomNumberGenerator.new()
	rng.seed = seed
	var radius: float = sqrt(rng.randf()) * tan(deg_to_rad(spread_deg))
	var angle: float = rng.randf_range(0.0, TAU)
	var right: Vector3 = _camera.global_transform.basis.x.normalized()
	var up: Vector3 = _camera.global_transform.basis.y.normalized()
	return (base + right * cos(angle) * radius + up * sin(angle) * radius).normalized()

func _fire_hitscan(spread_deg: float, pellet: int) -> void:
	if _camera == null or _body == null:
		return

	var origin: Vector3 = _camera.global_position
	var base_direction: Vector3 = -_camera.global_transform.basis.z.normalized()
	var direction: Vector3 = _spread_direction(base_direction, spread_deg, pellet)
	var target: Vector3 = origin + direction * range_m
	var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(origin, target)
	query.exclude = [_body.get_rid()]
	query.collide_with_areas = true
	query.collide_with_bodies = true
	var hit: Dictionary = _camera.get_world_3d().direct_space_state.intersect_ray(query)
	if hit.is_empty():
		return

	var collider: Object = hit.get("collider") as Object
	if collider == null:
		return
	var hit_position: Vector3 = hit.get("position", target) as Vector3
	if collider.has_method("apply_hitscan_damage"):
		var final_damage: float = damage * _player_modifier("get_weapon_damage_multiplier")
		collider.call("apply_hitscan_damage", final_damage, _body, hit_position)
	elif collider.has_method("apply_damage"):
		var final_damage: float = damage * _player_modifier("get_weapon_damage_multiplier")
		collider.call("apply_damage", final_damage, _body)

func _apply_recoil_impulse() -> void:
	_visual_recoil_velocity += (
		_visual_recoil_deg
		* (0.88 if is_ads_active() else 1.0)
		* _player_modifier("get_recoil_multiplier")
	)

func _update_visual_recoil(delta: float) -> void:
	# Presentation only. Ballistic ray direction/spread was already computed above.
	var spring: float = 54.0
	var damping: float = 13.5
	_visual_recoil_velocity += (-spring * _visual_recoil_pitch - damping * _visual_recoil_velocity) * delta
	_visual_recoil_pitch += _visual_recoil_velocity * delta
	_visual_recoil_pitch = clampf(_visual_recoil_pitch, -0.5, 7.5)

	if _camera != null:
		_camera.rotation.x = deg_to_rad(-_visual_recoil_pitch)
	if _view_root != null:
		_view_root.position.z = -0.48 + minf(_visual_recoil_pitch * 0.0025, 0.022)

func set_dev_infinite_ammo(enabled: bool) -> void:
	_dev_infinite_ammo = enabled
	if enabled:
		_magazine = magazine_size
		_reloading = false
	set_meta("dev_infinite_ammo", enabled)
	print("XZOGOT_DEV_INFINITE_AMMO ", enabled)

func is_dev_infinite_ammo() -> bool:
	return _dev_infinite_ammo

func add_reserve_ammo(amount: int) -> void:
	if amount <= 0:
		return
	reserve_ammo += amount

func refill_max_ammo() -> void:
	if not WeaponCatalog.has_weapon(_weapon_id):
		return
	var def: Dictionary = WeaponCatalog.get_weapon(_weapon_id)
	_magazine = magazine_size
	reserve_ammo = int(def.get("reserve", magazine_size * 4))
	_reloading = false
	_reload_timer = 0.0
	print("XZOGOT_WEAPON_MAX_AMMO ", _weapon_id, " mag=", _magazine, " reserve=", reserve_ammo)

func get_magazine() -> int:
	return _magazine

func get_reserve() -> int:
	return 9999 if _dev_infinite_ammo else reserve_ammo

func is_reloading() -> bool:
	return _reloading

func get_shots_fired() -> int:
	return _shots_fired

func get_weapon_id() -> String:
	return _weapon_id

func get_display_name() -> String:
	return _display_name

func get_family() -> String:
	return _family

func get_ads_fov() -> float:
	return _ads_fov

func is_automatic() -> bool:
	return _automatic

func get_mystery_pool_size() -> int:
	return WeaponCatalog.MYSTERY_POOL.size()
