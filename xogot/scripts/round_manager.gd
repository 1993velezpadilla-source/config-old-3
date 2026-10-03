extends Node

@export var auto_start: bool = true
@export var first_round_delay: float = 2.5
@export var spawn_interval: float = 0.75
@export var round_break: float = 3.0
@export var base_zombies: int = 4

var current_round: int = 0
var _remaining_to_spawn: int = 0
var _alive: int = 0
var _spawn_timer: float = 0.0
var _break_timer: float = 0.0
var _started: bool = false
var _window_cursor: int = 0

func _ready() -> void:
	set_process(true)
	if auto_start:
		_break_timer = first_round_delay
	print("XZOGOT_ROUND_MANAGER_READY")

func _process(delta: float) -> void:
	if not auto_start and not _started:
		return

	if current_round == 0:
		_break_timer -= delta
		if _break_timer <= 0.0:
			start_next_round()
		return

	if _remaining_to_spawn > 0:
		_spawn_timer -= delta
		if _spawn_timer <= 0.0:
			spawn_one()
			_spawn_timer = spawn_interval
		return

	if _alive <= 0 and _started:
		_break_timer -= delta
		if _break_timer <= 0.0:
			start_next_round()

func start_next_round() -> void:
	_started = true
	current_round += 1
	_remaining_to_spawn = zombies_for_round(current_round)
	_spawn_timer = 0.0
	_break_timer = round_break
	print("XZOGOT_ROUND_START ", current_round, " ", _remaining_to_spawn)

func zombies_for_round(round_number: int) -> int:
	return base_zombies + maxi(0, round_number - 1) * 2

func spawn_one() -> Node:
	var barricades: Array[Node] = get_tree().get_nodes_in_group("zombie_barricade")
	var player: Node3D = get_tree().get_first_node_in_group("player") as Node3D
	if barricades.is_empty() or player == null:
		return null

	var barricade: Node = barricades[_window_cursor % barricades.size()]
	_window_cursor += 1

	var script_resource: Script = load("res://scripts/zombie_dummy.gd") as Script
	var zombie := CharacterBody3D.new()
	zombie.name = "Zombie_R%d_%d" % [current_round, _window_cursor]
	zombie.set_script(script_resource)
	zombie.call("configure", player, barricade)
	zombie.global_position = barricade.call("get_outside_spawn") as Vector3
	zombie.connect("died", Callable(self, "_on_zombie_died"))
	get_parent().add_child(zombie)

	_remaining_to_spawn = maxi(0, _remaining_to_spawn - 1)
	_alive += 1
	print("XZOGOT_ZOMBIE_SPAWN ", current_round, " ", _alive)
	return zombie

func _on_zombie_died(_zombie: Node) -> void:
	_alive = maxi(0, _alive - 1)
	if _remaining_to_spawn == 0 and _alive == 0:
		_break_timer = round_break
		print("XZOGOT_ROUND_CLEAR ", current_round)

func get_round() -> int:
	return current_round

func get_alive() -> int:
	return _alive

func get_remaining_to_spawn() -> int:
	return _remaining_to_spawn
