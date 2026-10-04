extends StaticBody3D

@export var max_boards: int = 6
@export var board_health: float = 42.0
@export var repair_reward: int = 10
@export var repair_reward_cap_per_round: int = 60

var _boards: int = 6
var _health: float = 252.0
var _broken: bool = false
var _board_nodes: Array[MeshInstance3D] = []
var _repair_round: int = 0
var _repair_reward_this_round: int = 0

const SFX_BREAK_A := "res://assets/audio/church/world/wood_break_01.ogg"
const SFX_BREAK_B := "res://assets/audio/church/world/wood_break_02.ogg"
const SFX_REPAIR := "res://assets/audio/church/world/wood_repair.ogg"

func _notify_network_state(player: Node = null) -> void:
	var network: Node = get_tree().root.find_child("NetworkManager", true, false)
	if network != null and network.has_method("notify_host_barricade"):
		network.call("notify_host_barricade", self, player)

func _play_wood_sfx(path: String, volume_db: float = -5.0) -> void:
	if not ResourceLoader.exists(path):
		return
	var stream := load(path) as AudioStream
	if stream == null:
		return
	var player := AudioStreamPlayer3D.new()
	player.stream = stream
	player.volume_db = volume_db
	player.unit_size = 1.3
	player.max_distance = 24.0
	add_child(player)
	player.finished.connect(player.queue_free)
	player.play()

func _ready() -> void:
	_boards = max_boards
	_health = float(max_boards) * board_health
	add_to_group("zombie_barricade")
	_build_visuals()
	_refresh_state()
	print("XZOGOT_BARRICADE_READY ", name, " boards=", max_boards)

func _build_visuals() -> void:
	var wood := StandardMaterial3D.new()
	wood.albedo_color = Color(0.22, 0.12, 0.055)
	wood.roughness = 0.88

	# Six planks overlap vertically like classic round-based window barricades.
	# Alternating angles prevent the perfect toy-like ladder look.
	var angles: Array[float] = [-7.0, 5.0, -3.0, 8.0, -5.0, 4.0]
	for i in range(max_boards):
		var board := MeshInstance3D.new()
		board.name = "Board_%d" % i
		var mesh := BoxMesh.new()
		mesh.size = Vector3(0.20, 0.24, 2.52)
		mesh.material = wood
		board.mesh = mesh
		board.position = Vector3(0.0, -0.93 + float(i) * 0.37, 0.0)
		board.rotation_degrees.x = angles[i % angles.size()]
		add_child(board)
		_board_nodes.append(board)

	var cs := CollisionShape3D.new()
	cs.name = "BarricadeCollision"
	var shape := BoxShape3D.new()
	shape.size = Vector3(0.24, 2.30, 2.62)
	cs.shape = shape
	add_child(cs)

func begin_round(round_number: int) -> void:
	if round_number == _repair_round:
		return
	_repair_round = round_number
	_repair_reward_this_round = 0

func zombie_damage(amount: float) -> bool:
	if _boards <= 0 or amount <= 0.0:
		return false

	var before: int = _boards
	_health = maxf(0.0, _health - amount)
	var target_boards: int = ceili(_health / board_health)
	target_boards = clampi(target_boards, 0, max_boards)
	if target_boards != _boards:
		_boards = target_boards
		_refresh_state()
		var break_sfx: String = SFX_BREAK_A if ((_boards + abs(name.hash())) % 2 == 0) else SFX_BREAK_B
		_play_wood_sfx(break_sfx, -3.5)
		print("XZOGOT_BARRICADE_PLANK_LOST ", name, " ", before, "->", _boards)

	if _boards <= 0:
		_broken = true
		_refresh_state()
		print("XZOGOT_BARRICADE_BROKEN ", name)
	if before != _boards:
		_notify_network_state()
	return true

func interact(player: Node) -> bool:
	if _boards >= max_boards:
		return false

	_boards += 1
	_health = minf(
		float(max_boards) * board_health,
		maxf(_health, float(_boards) * board_health)
	)
	_broken = false
	_refresh_state()
	_play_wood_sfx(SFX_REPAIR, -7.0)

	var awarded: int = 0
	if (
		player != null
		and player.has_method("add_points")
		and _repair_reward_this_round < repair_reward_cap_per_round
	):
		awarded = mini(
			repair_reward,
			repair_reward_cap_per_round - _repair_reward_this_round
		)
		if awarded > 0:
			player.call("add_points", awarded)
			_repair_reward_this_round += awarded

	print(
		"XZOGOT_BARRICADE_REPAIRED ",
		name,
		" boards=", _boards,
		" reward=", awarded,
		" round_budget=", _repair_reward_this_round
	)
	_notify_network_state(player)
	return true

func _refresh_state() -> void:
	for i in range(_board_nodes.size()):
		_board_nodes[i].visible = i < _boards
	var cs: CollisionShape3D = get_node_or_null("BarricadeCollision") as CollisionShape3D
	if cs != null:
		cs.set_deferred("disabled", _boards <= 0)

func repair_full_no_reward() -> bool:
	var changed: bool = _boards < max_boards or _broken
	_boards = max_boards
	_health = float(max_boards) * board_health
	_broken = false
	_refresh_state()
	if changed:
		_play_wood_sfx(SFX_REPAIR, -8.0)
		print("XZOGOT_BARRICADE_CARPENTER_RESTORED ", name)
		_notify_network_state()
	return changed

func apply_network_boards(boards: int) -> void:
	_boards = clampi(boards, 0, max_boards)
	_health = float(_boards) * board_health
	_broken = _boards <= 0
	_refresh_state()
	print("XZOGOT_NETWORK_BARRICADE_STATE ", name, " boards=", _boards)

func get_boards() -> int:
	return _boards

func get_max_boards() -> int:
	return max_boards

func get_repair_reward_this_round() -> int:
	return _repair_reward_this_round

func is_broken() -> bool:
	return _broken or _boards <= 0

func get_outside_spawn() -> Vector3:
	return get_meta("outside_spawn", global_position) as Vector3

func get_outside_approach() -> Vector3:
	return get_meta("outside_approach", global_position) as Vector3

func get_inside_point() -> Vector3:
	return get_meta("inside_point", global_position) as Vector3
