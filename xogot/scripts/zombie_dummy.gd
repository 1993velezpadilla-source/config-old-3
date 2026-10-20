extends CharacterBody3D

signal died(zombie: Node)

const MONJA_BASICA_PATH := "res://assets/zombies/monja_basica.glb"
const NUN_ENEMY_01_SPRITE := "res://assets/zombies/nun_enemy_01_master.png"

@export var move_speed: float = 1.85
@export var health: float = 100.0
@export var barricade_damage: float = 25.0
@export var player_damage: float = 20.0
@export var attack_interval: float = 0.90
@export var window_cross_speed: float = 2.65
@export var turn_lerp: float = 0.22
@export var target_visual_height: float = 1.76
@export var target_visual_max_width: float = 0.82
@export var target_visual_max_depth: float = 0.66
@export var collider_radius: float = 0.31
@export var collider_height: float = 1.72
@export var headshot_multiplier: float = 2.0
@export var headshot_height_ratio: float = 0.84
@export var headshot_bonus_points: int = 10
@export var hit_reaction_duration: float = 0.14

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
var _avoidance_side: float = 1.0
var _avoidance_timer: float = 0.0
var _last_chase_position: Vector3 = Vector3.ZERO
var _stuck_seconds: float = 0.0
var _unstick_seconds: float = 0.0
const OBSTACLE_PROBE_DISTANCE := 1.45
const OBSTACLE_PROBE_HEIGHT := 0.52

func _ready() -> void:
	_gravity = float(ProjectSettings.get_setting("physics/3d/default_gravity", 18.0))
	floor_snap_length = 0.24
	add_to_group("zombie")
	_build_body()
	_last_chase_position = global_position
	print("XZOGOT_ZOMBIE_GROUND_SNAP_READY 0.24")
	print("XZOGOT_ZOMBIE_READY")

func configure(player: Node3D, barricade: Node) -> void:
	target_player = player
	target_barricade = barricade

func _build_body() -> void:
	var cs := CollisionShape3D.new()
	cs.name = "ZombieCollider"
	var capsule := CapsuleShape3D.new()
	capsule.radius = collider_radius
	capsule.height = collider_height
	cs.shape = capsule
	cs.position.y = collider_height * 0.5
	add_child(cs)

	if _build_nun_sprite_visual():
		return

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
				# 3DH/Tripo export authored this character facing +X.
				# Godot gameplay forward is -Z, so rotate the SOURCE before fitting
				# to keep final world width/depth correct while fixing visual facing.
				imported.rotation_degrees.y = 90.0
				visual.add_child(imported)
				if _fit_visual_to_gameplay_bounds(
					visual,
					imported,
					target_visual_height,
					target_visual_max_width,
					target_visual_max_depth
				):
					set_meta("zombie_model", "monja_basica")
					set_meta("zombie_visual_forward_fix_deg", 90.0)
					print("XZOGOT_MONJA_FORWARD_FIXED 90")
					print("XZOGOT_MONJA_BASICA_LOADED")
					return
				visual.queue_free()

	_build_fallback_visual()
	print("XZOGOT_MONJA_BASICA_FALLBACK")

# Optional approved 2.5D visual. Physics, AI, hitboxes and rounds remain unchanged.
# Keep the existing 3D nun as fallback until the full-resolution PNG is present.
func _build_nun_sprite_visual() -> bool:
	if not ResourceLoader.exists(NUN_ENEMY_01_SPRITE):
		return false
	var texture := load(NUN_ENEMY_01_SPRITE) as Texture2D
	if texture == null or texture.get_width() < 512 or texture.get_height() < 1024:
		push_warning("NUN_01_SPRITE_REJECTED: source must be >= 512x1024")
		return false
	var sprite := Sprite3D.new()
	sprite.name = "NunEnemy01Sprite"
	sprite.texture = texture
	sprite.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	sprite.transparent = true
	sprite.shaded = true
	sprite.alpha_cut = SpriteBase3D.ALPHA_CUT_DISCARD
	sprite.pixel_size = target_visual_height / float(texture.get_height())
	sprite.position.y = target_visual_height * 0.5
	sprite.no_depth_test = false
	add_child(sprite)
	_visual_root = sprite
	set_meta("zombie_model", "nun_enemy_01_2_5d")
	set_meta("zombie_visual_height_m", target_visual_height)
	set_meta("zombie_visual_centered_on_feet", true)
	print("XZOGOT_NUN_01_SPRITE_READY ", texture.get_width(), "x", texture.get_height())
	return true

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
	if raw_size.y <= 0.0001:
		return false

	var scale_y: float = target_height / raw_size.y

	# These are authored gameplay silhouette targets, not loose maximums.
	# After correcting the GLB forward axis, fit X/Z directly so the common
	# church zombie keeps the intended regular human mass from every export.
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
	mesh.radius = 0.34
	mesh.height = 1.72
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.17, 0.22, 0.16)
	mat.roughness = 0.96
	mesh.material = mat
	visual.mesh = mesh
	visual.position.y = 0.86
	add_child(visual)

func _physics_process(delta: float) -> void:
	_update_hit_reaction(delta)
	_avoidance_timer = maxf(0.0, _avoidance_timer - delta)
	if phase == Phase.DEAD:
		return
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
			_tick_chase(delta)
		Phase.CROSS_WINDOW:
			_tick_cross_window()

func _tick_approach() -> void:
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
	print("XZOGOT_ZOMBIE_WINDOW_CROSS_BEGIN")

func _tick_cross_window() -> void:
	if target_barricade == null or not is_instance_valid(target_barricade):
		phase = Phase.CHASE_PLAYER
		return
	var inside: Vector3 = target_barricade.call("get_inside_point") as Vector3
	if _move_toward_flat_speed(inside, 0.22, window_cross_speed):
		velocity.x = 0.0
		velocity.z = 0.0
		phase = Phase.CHASE_PLAYER
		print("XZOGOT_ZOMBIE_ENTERED")

func _tick_chase(delta: float) -> void:
	if target_player == null or not is_instance_valid(target_player):
		velocity.x = 0.0
		velocity.z = 0.0
		return
	var target: Vector3 = target_player.global_position
	# Descending from the balcony: keep moving along the ramp rather than
	# steering sideways into its upper landing. Only activate when the
	# target is substantially lower and the zombie is within the ramp lane.
	if global_position.y > target.y + 1.8 and absf(global_position.x + 6.24) < 1.8 and global_position.z > 0.0 and global_position.z < 7.2:
		# The upper landing overlaps the ramp entry. Drive along the
		# ramp's downhill tangent, rather than directly at a low target
		# through the landing's vertical collision face.
		var ramp_exit := Vector3(-6.24, target.y, 0.20)
		var downhill := Vector3(0.0, 0.0, -1.0)
		velocity.x = 0.0
		velocity.z = downhill.z * move_speed
		# A grounded CharacterBody3D cannot cross a raised lip by
		# horizontal motion alone. A tiny upward step assist is allowed
		# only while blocked at the top of the authored ramp.
		if is_on_wall() and is_on_floor() and global_position.z > 5.8:
			velocity.y = maxf(velocity.y, 2.2)
		move_and_slide()
		return
	# An inclined walkable ramp is a floor, not furniture to dodge.
	# Floor snap must remain active on the slope and the character must
	# accept slopes below the authored ramp's 36.91 degree incline.
	floor_max_angle = deg_to_rad(45.0)
	floor_snap_length = maxf(floor_snap_length, 0.32)
	var flat_distance: float = Vector2(global_position.x - target.x, global_position.z - target.z).length()
	if flat_distance <= 1.25:
		velocity.x = 0.0
		velocity.z = 0.0
		if _attack_timer <= 0.0 and target_player.has_method("apply_damage"):
			target_player.call("apply_damage", player_damage)
			_attack_timer = attack_interval
		return
	# Detect genuine lack of progress rather than changing sides every frame.
	var progress := Vector2(global_position.x - _last_chase_position.x, global_position.z - _last_chase_position.z).length()
	if progress < 0.015:
		_stuck_seconds += delta
	else:
		_stuck_seconds = 0.0
	_last_chase_position = global_position
	if _stuck_seconds > 0.85:
		_avoidance_side *= -1.0
		_unstick_seconds = 1.1
		_stuck_seconds = 0.0
	_unstick_seconds = maxf(0.0, _unstick_seconds - delta)
	_move_toward_flat(target, 0.0, true)

# Local obstacle steering for pews. This is deliberately NOT a navmesh solution:
# it prevents repeated straight-line collisions while full pathfinding is built.
func _steer_around_furniture(forward: Vector3) -> Vector3:
	var space := get_world_3d().direct_space_state
	if space == null:
		return forward
	var origin := global_position + Vector3.UP * OBSTACLE_PROBE_HEIGHT
	var query := PhysicsRayQueryParameters3D.create(origin, origin + forward * OBSTACLE_PROBE_DISTANCE)
	query.exclude = [get_rid()]
	query.collision_mask = collision_mask
	var hit := space.intersect_ray(query)
	if hit.is_empty() and _unstick_seconds <= 0.0:
		_avoidance_timer = 0.0
		return forward
	var obstacle: Object = hit.get("collider")
	if obstacle is StaticBody3D and (obstacle as StaticBody3D).is_in_group("walkable_stair_ramp"):
		return forward
	if not (obstacle is StaticBody3D) and _unstick_seconds <= 0.0:
		return forward
	if _avoidance_timer <= 0.0 and _unstick_seconds <= 0.0:
		var right := Vector3(-forward.z, 0.0, forward.x)
		var left_query := PhysicsRayQueryParameters3D.create(origin, origin + (forward - right * 0.85).normalized() * OBSTACLE_PROBE_DISTANCE)
		var right_query := PhysicsRayQueryParameters3D.create(origin, origin + (forward + right * 0.85).normalized() * OBSTACLE_PROBE_DISTANCE)
		left_query.exclude = [get_rid()]
		right_query.exclude = [get_rid()]
		left_query.collision_mask = collision_mask
		right_query.collision_mask = collision_mask
		var left_clear := space.intersect_ray(left_query).is_empty()
		var right_clear := space.intersect_ray(right_query).is_empty()
		if left_clear != right_clear:
			_avoidance_side = -1.0 if left_clear else 1.0
		_avoidance_timer = 0.75
	var lateral := Vector3(-forward.z, 0.0, forward.x) * _avoidance_side
	return (forward * 0.18 + lateral).normalized()

func _move_toward_flat(target: Vector3, stop_distance: float, avoid_obstacles: bool = false) -> bool:
	return _move_toward_flat_speed(target, stop_distance, move_speed, avoid_obstacles)

func _move_toward_flat_speed(target: Vector3, stop_distance: float, speed: float, avoid_obstacles: bool = false) -> bool:
	var delta_pos := Vector3(target.x - global_position.x, 0.0, target.z - global_position.z)
	var distance: float = delta_pos.length()
	if distance <= stop_distance:
		return true
	var direction: Vector3 = delta_pos.normalized()
	if avoid_obstacles:
		direction = _steer_around_furniture(direction)
	var target_yaw: float = atan2(-direction.x, -direction.z)
	rotation.y = lerp_angle(rotation.y, target_yaw, turn_lerp)
	velocity.x = direction.x * speed
	velocity.z = direction.z * speed
	move_and_slide()
	return false

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
	if source != null and source.has_method("add_points"):
		source.call("add_points", 60)
	print("XZOGOT_ZOMBIE_KILLED")
	died.emit(self)
	queue_free()

func get_phase() -> int:
	return int(phase)
