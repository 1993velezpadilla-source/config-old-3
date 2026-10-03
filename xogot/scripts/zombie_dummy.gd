extends CharacterBody3D

signal died(zombie: Node)

const MONJA_BASICA_PATH := "res://assets/zombies/monja_basica.glb"

@export var move_speed: float = 1.85
@export var health: float = 100.0
@export var barricade_damage: float = 25.0
@export var player_damage: float = 20.0
@export var attack_interval: float = 0.90
@export var target_visual_height: float = 1.74
@export var target_visual_max_width: float = 0.75
@export var target_visual_max_depth: float = 0.60
@export var collider_radius: float = 0.30
@export var collider_height: float = 1.70

enum Phase {
	APPROACH,
	ATTACK_BARRICADE,
	CHASE_PLAYER,
	DEAD
}

var target_player: Node3D
var target_barricade: Node
var phase: Phase = Phase.APPROACH
var _attack_timer: float = 0.0
var _gravity: float = 18.0

func _ready() -> void:
	_gravity = float(ProjectSettings.get_setting("physics/3d/default_gravity", 18.0))
	add_to_group("zombie")
	_build_body()
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

	if ResourceLoader.exists(MONJA_BASICA_PATH):
		var packed: PackedScene = load(MONJA_BASICA_PATH) as PackedScene
		if packed != null:
			var imported: Node3D = packed.instantiate() as Node3D
			if imported != null:
				var visual := Node3D.new()
				visual.name = "MonjaBasicaVisual"
				add_child(visual)
				imported.name = "MonjaBasicaSource"
				visual.add_child(imported)
				if _fit_visual_to_gameplay_bounds(
					visual,
					imported,
					target_visual_height,
					target_visual_max_width,
					target_visual_max_depth
				):
					set_meta("zombie_model", "monja_basica")
					print("XZOGOT_MONJA_BASICA_LOADED")
					return
				visual.queue_free()

	_build_fallback_visual()
	print("XZOGOT_MONJA_BASICA_FALLBACK")

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
	var uniform_width: float = raw_size.x * scale_y
	var uniform_depth: float = raw_size.z * scale_y

	# Keep the authored vertical proportions, but gently constrain oversized robe width/depth
	# so the common church zombie fits doors, pew aisles and the gameplay collider naturally.
	var width_adjust: float = 1.0
	var depth_adjust: float = 1.0
	if uniform_width > max_width:
		width_adjust = clampf(max_width / uniform_width, 0.78, 1.0)
	if uniform_depth > max_depth:
		depth_adjust = clampf(max_depth / uniform_depth, 0.78, 1.0)

	var scale_x: float = scale_y * width_adjust
	var scale_z: float = scale_y * depth_adjust
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
			_tick_chase()

func _tick_approach() -> void:
	if target_barricade == null or not is_instance_valid(target_barricade):
		phase = Phase.CHASE_PLAYER
		return
	if bool(target_barricade.call("is_broken")):
		_cross_window()
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
		_cross_window()
		return
	velocity.x = 0.0
	velocity.z = 0.0
	if _attack_timer <= 0.0:
		target_barricade.call("zombie_damage", barricade_damage)
		_attack_timer = attack_interval

func _cross_window() -> void:
	if target_barricade != null and is_instance_valid(target_barricade):
		global_position = target_barricade.call("get_inside_point") as Vector3
	phase = Phase.CHASE_PLAYER
	print("XZOGOT_ZOMBIE_ENTERED")

func _tick_chase() -> void:
	if target_player == null or not is_instance_valid(target_player):
		velocity.x = 0.0
		velocity.z = 0.0
		return
	var target: Vector3 = target_player.global_position
	var flat_distance: float = Vector2(global_position.x - target.x, global_position.z - target.z).length()
	if flat_distance <= 1.25:
		velocity.x = 0.0
		velocity.z = 0.0
		if _attack_timer <= 0.0 and target_player.has_method("apply_damage"):
			target_player.call("apply_damage", player_damage)
			_attack_timer = attack_interval
		return
	_move_toward_flat(target, 0.0)

func _move_toward_flat(target: Vector3, stop_distance: float) -> bool:
	var delta_pos := Vector3(target.x - global_position.x, 0.0, target.z - global_position.z)
	var distance: float = delta_pos.length()
	if distance <= stop_distance:
		return true
	var direction: Vector3 = delta_pos.normalized()
	rotation.y = atan2(-direction.x, -direction.z)
	velocity.x = direction.x * move_speed
	velocity.z = direction.z * move_speed
	move_and_slide()
	return false

func apply_damage(amount: float, source: Node = null) -> void:
	if phase == Phase.DEAD or amount <= 0.0:
		return
	health -= amount
	if source != null and source.has_method("add_points"):
		source.call("add_points", 10)
	if health <= 0.0:
		_die(source)

func _die(source: Node) -> void:
	phase = Phase.DEAD
	if source != null and source.has_method("add_points"):
		source.call("add_points", 60)
	print("XZOGOT_ZOMBIE_KILLED")
	died.emit(self)
	queue_free()

func get_phase() -> int:
	return int(phase)
