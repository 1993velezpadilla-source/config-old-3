extends CharacterBody3D

signal died(zombie: Node)

const MONJA_BASICA_PATH := "res://assets/zombies/monja_basica.glb"

const MOTION_PROFILES: Array[Dictionary] = [
	{
		"id": "cmu_zombie_walk_104_41",
		"walk_keys": ["zombie_walk", "104_41"],
		"speed_scale": 1.00,
		"source": "res://assets/zombie_mocap/raw/walk/zombie_walk__104_41.fbx",
	},
	{
		"id": "cmu_drag_bad_leg_105_25",
		"walk_keys": ["drag_bad_leg", "105_25"],
		"speed_scale": 0.86,
		"source": "res://assets/zombie_mocap/raw/walk/drag_bad_leg__105_25.fbx",
	},
	{
		"id": "cmu_stiff_74_01",
		"walk_keys": ["stiff", "74_01"],
		"speed_scale": 0.93,
		"source": "res://assets/zombie_mocap/raw/walk/stiff_A__74_01.fbx",
	},
	{
		"id": "cmu_wounded_leg_139_19",
		"walk_keys": ["wounded_leg", "139_19"],
		"speed_scale": 0.82,
		"source": "res://assets/zombie_mocap/raw/walk/wounded_leg_139_A__139_19.fbx",
	},
]

const ATTACK_KEYS: Array[String] = ["strike_A", "02_05", "punch_kick", "111_19"]
const DEATH_KEYS: Array[String] = ["fall_on_face", "90_16"]
const GETUP_KEYS: Array[String] = ["face_down_A", "140_01"]
const CRAWL_KEYS: Array[String] = ["crawl_A", "111_03"]

@export var move_speed: float = 1.85
@export var health: float = 100.0
@export var barricade_damage: float = 25.0
@export var player_damage: float = 20.0
@export var attack_interval: float = 0.90
@export var window_cross_speed: float = 2.65
@export var turn_lerp: float = 0.22
@export var target_visual_height: float = 1.80
@export var target_visual_max_width: float = 0.90
@export var target_visual_max_depth: float = 0.72
@export var collider_radius: float = 0.34
@export var collider_height: float = 1.78
@export var headshot_multiplier: float = 2.0
@export var headshot_height_ratio: float = 0.84
@export var headshot_bonus_points: int = 10
@export var hit_reaction_duration: float = 0.14
@export var path_refresh_interval: float = 0.62
@export var stuck_sample_interval: float = 0.72
@export var stuck_timeout: float = 1.75

enum Phase {
	APPROACH,
	ATTACK_BARRICADE,
	CHASE_PLAYER,
	DEAD,
	CROSS_WINDOW
}

var target_player: Node3D
var target_barricade: Node
var phase: Phase = Phase.APPROACH
var _attack_timer: float = 0.0
var _gravity: float = 18.0
var _hit_reaction_timer: float = 0.0
var _visual_root: Node3D

var _path_network: Node
var _path_points: Array[Vector3] = []
var _path_index: int = 0
var _path_refresh_timer: float = 0.0
var _last_path_target: Vector3 = Vector3.INF

var _stuck_sample_timer: float = 0.0
var _stuck_accum: float = 0.0
var _last_motion_sample: Vector3 = Vector3.ZERO
var _unstuck_count: int = 0

var _motion_profile: Dictionary = {}
var _motion_profile_id: String = ""
var _animation_player: AnimationPlayer
var _motion_state: String = ""

func _ready() -> void:
	_gravity = float(ProjectSettings.get_setting("physics/3d/default_gravity", 18.0))
	floor_snap_length = 0.24
	add_to_group("zombie")
	_path_network = get_tree().get_first_node_in_group("zombie_path_network")
	_select_motion_profile()
	_build_body()
	_last_motion_sample = global_position
	print("XZOGOT_ZOMBIE_GROUND_SNAP_READY 0.24")
	print("XZOGOT_ZOMBIE_PATHING_READY ", _motion_profile_id)
	print("XZOGOT_ZOMBIE_READY")

func configure(player: Node3D, barricade: Node) -> void:
	target_player = player
	target_barricade = barricade
	phase = Phase.APPROACH
	set_meta("spawn_entry_kind", "window")

func configure_direct(player: Node3D, anchor: Node) -> void:
	target_player = player
	target_barricade = null
	phase = Phase.CHASE_PLAYER
	var entry_kind: String = str(anchor.get_meta("entry_kind", "offscreen")) if anchor != null else "offscreen"
	var zone: String = str(anchor.get_meta("zone", "")) if anchor != null else ""
	set_meta("spawn_entry_kind", entry_kind)
	set_meta("spawn_zone", zone)
	if entry_kind == "crawl":
		set_meta("motion_override", "crawl")
	print("XZOGOT_ZOMBIE_DIRECT_ENTRY ", entry_kind, " ", zone)

func _select_motion_profile() -> void:
	var idx: int = abs(name.hash()) % MOTION_PROFILES.size()
	_motion_profile = MOTION_PROFILES[idx]
	_motion_profile_id = str(_motion_profile["id"])
	move_speed *= float(_motion_profile.get("speed_scale", 1.0))
	set_meta("motion_profile", _motion_profile_id)
	set_meta("motion_source", str(_motion_profile.get("source", "")))

func _build_body() -> void:
	var cs := CollisionShape3D.new()
	cs.name = "ZombieCollider"
	var capsule := CapsuleShape3D.new()
	capsule.radius = collider_radius
	capsule.height = collider_height
	cs.shape = capsule
	cs.position.y = collider_height * 0.5
	add_child(cs)

	if ResourceLoader.exists(MONJA_BASICA_PATH):
		var packed: PackedScene = load(MONJA_BASICA_PATH) as PackedScene
		if packed != null:
			var imported: Node3D = packed.instantiate() as Node3D
			if imported != null:
				var visual := Node3D.new()
				visual.name = "MonjaBasicaVisual"
				add_child(visual)
				_visual_root = visual
				imported.name = "MonjaBasicaSource"
				imported.rotation_degrees.y = 90.0
				visual.add_child(imported)
				if _fit_visual_to_gameplay_bounds(
					visual,
					imported,
					target_visual_height,
					target_visual_max_width,
					target_visual_max_depth
				):
					_animation_player = _find_animation_player(imported)
					set_meta("zombie_model", "monja_basica")
					set_meta("zombie_visual_forward_fix_deg", 90.0)
					set_meta("zombie_rig_ready", _animation_player != null)
					print("XZOGOT_MONJA_FORWARD_FIXED 90")
					print("XZOGOT_MONJA_BASICA_LOADED")
					if _animation_player != null:
						print("XZOGOT_MONJA_RIGGED_ANIMATION_PLAYER_READY")
					else:
						print("XZOGOT_MONJA_RETARGET_PENDING")
					return
				visual.queue_free()

	_build_fallback_visual()
	print("XZOGOT_MONJA_BASICA_FALLBACK")

func _find_animation_player(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node as AnimationPlayer
	for child: Node in node.get_children():
		var found: AnimationPlayer = _find_animation_player(child)
		if found != null:
			return found
	return null

func _fit_visual_to_gameplay_bounds(
	wrapper: Node3D,
	imported: Node3D,
	target_height: float,
	max_width: float,
	max_depth: float
) -> bool:
	var points: Array[Vector3] = []
	_collect_mesh_bounds(imported, Transform3D.IDENTITY, points)
	if points.is_empty():
		return false

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
	if raw_size.y <= 0.0001 or raw_size.x <= 0.0001 or raw_size.z <= 0.0001:
		return false

	var scale_y: float = target_height / raw_size.y
	var scale_x: float = max_width / raw_size.x
	var scale_z: float = max_depth / raw_size.z
	var center_x: float = (min_v.x + max_v.x) * 0.5
	var center_z: float = (min_v.z + max_v.z) * 0.5

	wrapper.scale = Vector3(scale_x, scale_y, scale_z)
	wrapper.position = Vector3(
		-center_x * scale_x,
		-min_v.y * scale_y,
		-center_z * scale_z
	)

	var fitted_size := Vector3(
		raw_size.x * scale_x,
		raw_size.y * scale_y,
		raw_size.z * scale_z
	)

	set_meta("zombie_visual_height_m", fitted_size.y)
	set_meta("zombie_visual_width_m", fitted_size.x)
	set_meta("zombie_visual_depth_m", fitted_size.z)
	set_meta("zombie_visual_scale_xyz", Vector3(scale_x, scale_y, scale_z))
	set_meta("zombie_visual_centered_on_feet", true)
	print(
		"XZOGOT_MONJA_FIT ",
		"raw=", raw_size,
		" scale_xyz=", Vector3(scale_x, scale_y, scale_z),
		" fitted=", fitted_size
	)
	return true

func _collect_mesh_bounds(node: Node3D, parent_transform: Transform3D, points: Array[Vector3]) -> void:
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
			_collect_mesh_bounds(child as Node3D, current_transform, points)

func _build_fallback_visual() -> void:
	var visual := MeshInstance3D.new()
	visual.name = "FallbackZombieVisual"
	var mesh := CapsuleMesh.new()
	mesh.radius = 0.38
	mesh.height = target_visual_height
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.17, 0.22, 0.16)
	mat.roughness = 0.96
	mesh.material = mat
	visual.mesh = mesh
	visual.position.y = target_visual_height * 0.5
	add_child(visual)

func _physics_process(delta: float) -> void:
	_update_hit_reaction(delta)
	if phase == Phase.DEAD:
		return

	_path_refresh_timer = maxf(0.0, _path_refresh_timer - delta)
	if _attack_timer > 0.0:
		_attack_timer = maxf(0.0, _attack_timer - delta)

	if not is_on_floor():
		velocity.y -= _gravity * delta

	match phase:
		Phase.APPROACH:
			_tick_approach()
		Phase.ATTACK_BARRICADE:
			_tick_barricade()
		Phase.CHASE_PLAYER:
			_tick_chase()
		Phase.CROSS_WINDOW:
			_tick_cross_window()

	_update_stuck_watchdog(delta)

func _tick_approach() -> void:
	_play_motion_state("walk")
	if target_barricade == null or not is_instance_valid(target_barricade):
		phase = Phase.CHASE_PLAYER
		return
	if bool(target_barricade.call("is_broken")):
		_begin_window_cross()
		return
	var target: Vector3 = target_barricade.call("get_outside_approach") as Vector3
	if _move_toward_flat(target, 0.45):
		velocity.x = 0.0
		velocity.z = 0.0
		phase = Phase.ATTACK_BARRICADE

func _tick_barricade() -> void:
	_play_motion_state("attack")
	if target_barricade == null or not is_instance_valid(target_barricade):
		phase = Phase.CHASE_PLAYER
		return
	if bool(target_barricade.call("is_broken")):
		_begin_window_cross()
		return
	velocity.x = 0.0
	velocity.z = 0.0
	if _attack_timer <= 0.0:
		target_barricade.call("zombie_damage", barricade_damage)
		_attack_timer = attack_interval

func _begin_window_cross() -> void:
	if target_barricade == null or not is_instance_valid(target_barricade):
		phase = Phase.CHASE_PLAYER
		return
	phase = Phase.CROSS_WINDOW
	_path_points.clear()
	_path_index = 0
	print("XZOGOT_ZOMBIE_WINDOW_CROSS_BEGIN")

func _tick_cross_window() -> void:
	_play_motion_state("walk")
	if target_barricade == null or not is_instance_valid(target_barricade):
		phase = Phase.CHASE_PLAYER
		return
	var inside: Vector3 = target_barricade.call("get_inside_point") as Vector3
	if _move_toward_flat_speed(inside, 0.22, window_cross_speed):
		velocity.x = 0.0
		velocity.z = 0.0
		phase = Phase.CHASE_PLAYER
		_path_refresh_timer = 0.0
		print("XZOGOT_ZOMBIE_ENTERED")

func _tick_chase() -> void:
	_play_motion_state("walk")
	if target_player == null or not is_instance_valid(target_player):
		velocity.x = 0.0
		velocity.z = 0.0
		return
	var target: Vector3 = target_player.global_position
	var flat_distance: float = Vector2(global_position.x - target.x, global_position.z - target.z).length()
	if flat_distance <= 1.25 and absf(global_position.y - target.y) < 1.7:
		velocity.x = 0.0
		velocity.z = 0.0
		_play_motion_state("attack")
		if _attack_timer <= 0.0 and target_player.has_method("apply_damage"):
			target_player.call("apply_damage", player_damage)
			_attack_timer = attack_interval
		return
	_move_toward_navigated(target, 0.0)

func _has_clear_path_to(target: Vector3) -> bool:
	var world: World3D = get_world_3d()
	if world == null:
		return true
	var from: Vector3 = global_position + Vector3(0.0, 0.80, 0.0)
	var to: Vector3 = target + Vector3(0.0, 0.80, 0.0)
	var ray := PhysicsRayQueryParameters3D.create(from, to)
	ray.exclude = [get_rid()]
	var hit: Dictionary = world.direct_space_state.intersect_ray(ray)
	if hit.is_empty():
		return true
	var collider: Object = hit.get("collider") as Object
	return collider == target_player

func _move_toward_navigated(target: Vector3, stop_distance: float) -> bool:
	if _has_clear_path_to(target):
		_path_points.clear()
		_path_index = 0
		return _move_toward_flat(target, stop_distance)

	if _path_network == null or not is_instance_valid(_path_network):
		_path_network = get_tree().get_first_node_in_group("zombie_path_network")
	if _path_network == null or not _path_network.has_method("request_path"):
		return _move_toward_flat(target, stop_distance)

	if (
		_path_refresh_timer <= 0.0
		or _path_points.is_empty()
		or _last_path_target == Vector3.INF
		or _last_path_target.distance_to(target) > 1.8
	):
		_path_points = _path_network.call("request_path", global_position, target) as Array[Vector3]
		_path_index = 0
		_last_path_target = target
		_path_refresh_timer = path_refresh_interval + float(abs(name.hash()) % 17) * 0.007

	while _path_index < _path_points.size():
		var waypoint: Vector3 = _path_points[_path_index]
		if Vector2(global_position.x - waypoint.x, global_position.z - waypoint.z).length() <= 0.55:
			_path_index += 1
			continue
		return _move_toward_flat(waypoint, 0.22)

	return _move_toward_flat(target, stop_distance)

func _move_toward_flat(target: Vector3, stop_distance: float) -> bool:
	return _move_toward_flat_speed(target, stop_distance, move_speed)

func _move_toward_flat_speed(target: Vector3, stop_distance: float, speed: float) -> bool:
	var delta_pos := Vector3(target.x - global_position.x, 0.0, target.z - global_position.z)
	var distance: float = delta_pos.length()
	if distance <= stop_distance:
		return true
	var direction: Vector3 = delta_pos.normalized()
	var target_yaw: float = atan2(-direction.x, -direction.z)
	rotation.y = lerp_angle(rotation.y, target_yaw, turn_lerp)
	velocity.x = direction.x * speed
	velocity.z = direction.z * speed
	move_and_slide()
	return false

func _update_stuck_watchdog(delta: float) -> void:
	if phase == Phase.DEAD or phase == Phase.ATTACK_BARRICADE:
		_stuck_accum = 0.0
		_stuck_sample_timer = 0.0
		_last_motion_sample = global_position
		return

	_stuck_sample_timer += delta
	if _stuck_sample_timer < stuck_sample_interval:
		return

	var moved: float = Vector2(
		global_position.x - _last_motion_sample.x,
		global_position.z - _last_motion_sample.z
	).length()
	var expected: float = Vector2(velocity.x, velocity.z).length()

	if expected > 0.25 and moved < 0.07:
		_stuck_accum += _stuck_sample_timer
	else:
		_stuck_accum = 0.0
		_unstuck_count = 0

	_last_motion_sample = global_position
	_stuck_sample_timer = 0.0

	if _stuck_accum >= stuck_timeout:
		_attempt_unstuck()
		_stuck_accum = 0.0

func _attempt_unstuck() -> void:
	if target_player == null or not is_instance_valid(target_player):
		return

	_unstuck_count += 1
	_path_refresh_timer = 0.0
	_path_points.clear()
	_path_index = 0

	var recovery: Vector3 = target_player.global_position
	if _path_network != null and is_instance_valid(_path_network) and _path_network.has_method("recovery_point"):
		recovery = _path_network.call("recovery_point", global_position, target_player.global_position) as Vector3

	var flat := Vector3(recovery.x - global_position.x, 0.0, recovery.z - global_position.z)
	if flat.length_squared() <= 0.0001:
		return
	var forward: Vector3 = flat.normalized()
	var candidates: Array[Vector3] = [
		forward * 0.42,
		Vector3(-forward.z, 0.0, forward.x) * 0.34,
		Vector3(forward.z, 0.0, -forward.x) * 0.34,
		-forward * 0.24,
	]
	for motion: Vector3 in candidates:
		if not test_move(global_transform, motion):
			global_position += motion
			print("XZOGOT_ZOMBIE_UNSTUCK ", name, " attempt=", _unstuck_count)
			return

	print("XZOGOT_ZOMBIE_UNSTUCK_REPATH ", name, " attempt=", _unstuck_count)

func _animation_name_for_keys(keys: Array[String]) -> String:
	if _animation_player == null:
		return ""
	for anim_name: StringName in _animation_player.get_animation_list():
		var lower: String = str(anim_name).to_lower()
		for key: String in keys:
			if lower.contains(key.to_lower()):
				return str(anim_name)
	return ""

func _play_motion_state(state: String) -> void:
	if _motion_state == state:
		return
	_motion_state = state
	set_meta("motion_state", state)
	if _animation_player == null:
		return

	var keys: Array[String] = []
	if state == "walk":
		if str(get_meta("motion_override", "")) == "crawl":
			keys = CRAWL_KEYS
		else:
			keys = _motion_profile.get("walk_keys", []) as Array[String]
	elif state == "attack":
		keys = ATTACK_KEYS
	elif state == "death":
		keys = DEATH_KEYS
	elif state == "getup":
		keys = GETUP_KEYS

	var anim_name: String = _animation_name_for_keys(keys)
	if not anim_name.is_empty():
		_animation_player.play(anim_name)

func apply_hitscan_damage(amount: float, source: Node = null, hit_position: Vector3 = Vector3.ZERO) -> void:
	if phase == Phase.DEAD or amount <= 0.0:
		return
	var local_hit: Vector3 = to_local(hit_position)
	var head_threshold: float = target_visual_height * headshot_height_ratio
	var is_headshot: bool = local_hit.y >= head_threshold
	var applied_amount: float = amount * (headshot_multiplier if is_headshot else 1.0)
	set_meta("last_hit_headshot", is_headshot)
	if is_headshot:
		print("XZOGOT_ZOMBIE_HEADSHOT")
	_take_damage(applied_amount, source, is_headshot)

func apply_damage(amount: float, source: Node = null) -> void:
	_take_damage(amount, source, false)

func _take_damage(amount: float, source: Node, headshot: bool) -> void:
	if phase == Phase.DEAD or amount <= 0.0:
		return
	health -= amount
	_hit_reaction_timer = hit_reaction_duration
	if source != null and source.has_method("add_points"):
		source.call("add_points", 10)
		if headshot:
			source.call("add_points", headshot_bonus_points)
	if health <= 0.0:
		_die(source)

func _update_hit_reaction(delta: float) -> void:
	if _visual_root == null or not is_instance_valid(_visual_root):
		return
	if _hit_reaction_timer > 0.0:
		_hit_reaction_timer = maxf(0.0, _hit_reaction_timer - delta)
		var ratio: float = _hit_reaction_timer / maxf(hit_reaction_duration, 0.001)
		_visual_root.rotation.z = deg_to_rad(sin(ratio * PI) * 4.5)
	else:
		_visual_root.rotation.z = move_toward(_visual_root.rotation.z, 0.0, delta * 4.5)

func get_health() -> float:
	return health

func _die(source: Node) -> void:
	phase = Phase.DEAD
	_play_motion_state("death")
	if source != null and source.has_method("add_points"):
		source.call("add_points", 60)
	print("XZOGOT_ZOMBIE_KILLED ", _motion_profile_id)
	died.emit(self)
	queue_free()

func get_phase() -> int:
	return int(phase)

func get_motion_profile_id() -> String:
	return _motion_profile_id

func get_unstuck_count() -> int:
	return _unstuck_count
