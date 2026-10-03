extends CharacterBody3D

signal died(zombie: Node)

const MONJA_BASICA_PATH := "res://assets/zombies/monja_basica.glb"

@export var move_speed: float = 1.85
@export var health: float = 100.0
@export var barricade_damage: float = 25.0
@export var player_damage: float = 20.0
@export var attack_interval: float = 0.90
@export var monja_scale: float = 1.76

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
	capsule.radius = 0.34
	capsule.height = 1.72
	cs.shape = capsule
	cs.position.y = 0.86
	add_child(cs)

	if ResourceLoader.exists(MONJA_BASICA_PATH):
		var packed: PackedScene = load(MONJA_BASICA_PATH) as PackedScene
		if packed != null:
			var visual: Node3D = packed.instantiate() as Node3D
			if visual != null:
				visual.name = "MonjaBasicaVisual"
				visual.scale = Vector3.ONE * monja_scale
				visual.position.y = 0.86
				add_child(visual)
				set_meta("zombie_model", "monja_basica")
				print("XZOGOT_MONJA_BASICA_LOADED")
				return

	_build_fallback_visual()
	print("XZOGOT_MONJA_BASICA_FALLBACK")

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
