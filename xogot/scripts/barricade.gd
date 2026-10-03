extends StaticBody3D

@export var max_boards: int = 3
@export var board_health: float = 50.0
@export var repair_reward: int = 10

var _boards: int = 3
var _health: float = 150.0
var _broken: bool = false
var _board_nodes: Array[MeshInstance3D] = []

func _ready() -> void:
	_boards = max_boards
	_health = float(max_boards) * board_health
	add_to_group("zombie_barricade")
	_build_visuals()
	_refresh_state()
	print("XZOGOT_BARRICADE_READY ", name)

func _build_visuals() -> void:
	var wood := StandardMaterial3D.new()
	wood.albedo_color = Color(0.22, 0.12, 0.055)
	wood.roughness = 0.88

	for i in range(max_boards):
		var board := MeshInstance3D.new()
		board.name = "Board_%d" % i
		var mesh := BoxMesh.new()
		mesh.size = Vector3(0.20, 0.26, 2.45)
		mesh.material = wood
		board.mesh = mesh
		board.position = Vector3(0.0, -0.62 + float(i) * 0.62, 0.0)
		add_child(board)
		_board_nodes.append(board)

	var cs := CollisionShape3D.new()
	cs.name = "BarricadeCollision"
	var shape := BoxShape3D.new()
	shape.size = Vector3(0.24, 2.15, 2.55)
	cs.shape = shape
	add_child(cs)

func zombie_damage(amount: float) -> bool:
	if _boards <= 0 or amount <= 0.0:
		return false
	_health = maxf(0.0, _health - amount)
	var target_boards: int = ceili(_health / board_health)
	target_boards = clampi(target_boards, 0, max_boards)
	if target_boards != _boards:
		_boards = target_boards
		_refresh_state()
	if _boards <= 0:
		_broken = true
		_refresh_state()
		print("XZOGOT_BARRICADE_BROKEN ", name)
	return true

func interact(player: Node) -> bool:
	if _boards >= max_boards:
		return false
	_boards += 1
	_health = minf(float(max_boards) * board_health, maxf(_health, float(_boards) * board_health))
	_broken = false
	_refresh_state()
	if player != null and player.has_method("add_points"):
		player.call("add_points", repair_reward)
	print("XZOGOT_BARRICADE_REPAIRED ", name, " ", _boards)
	return true

func _refresh_state() -> void:
	for i in range(_board_nodes.size()):
		_board_nodes[i].visible = i < _boards
	var cs: CollisionShape3D = get_node_or_null("BarricadeCollision") as CollisionShape3D
	if cs != null:
		cs.set_deferred("disabled", _boards <= 0)

func get_boards() -> int:
	return _boards

func is_broken() -> bool:
	return _broken or _boards <= 0

func get_outside_spawn() -> Vector3:
	return get_meta("outside_spawn", global_position) as Vector3

func get_outside_approach() -> Vector3:
	return get_meta("outside_approach", global_position) as Vector3

func get_inside_point() -> Vector3:
	return get_meta("inside_point", global_position) as Vector3
