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
var _spawn_serial: int = 0
var _recent_spawn_ids: Array[String] = []
var _last_spawn_id: String = ""
var _dev_no_zombies: bool = false

func _ready() -> void:
	set_process(true)
	if auto_start:
		_break_timer = first_round_delay
	print("XZOGOT_ROUND_MANAGER_READY")
	print("XZOGOT_SPAWN_DIRECTOR_READY")

func _process(delta: float) -> void:
	if _dev_no_zombies:
		return
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

	for barricade: Node in get_tree().get_nodes_in_group("zombie_barricade"):
		if barricade.has_method("begin_round"):
			barricade.call("begin_round", current_round)

	print("XZOGOT_ROUND_START ", current_round, " ", _remaining_to_spawn)

func zombies_for_round(round_number: int) -> int:
	return base_zombies + maxi(0, round_number - 1) * 2

func _gate_open(gate_name: String) -> bool:
	if gate_name.is_empty():
		return true
	var scene_root: Node = get_parent()
	if scene_root == null:
		return false
	var gate: Node = scene_root.get_node_or_null(gate_name)
	if gate == null:
		return false
	if gate.has_method("was_used"):
		return bool(gate.call("was_used"))
	return false

func _spawn_visible_to_player(player: Node3D, world_pos: Vector3) -> bool:
	var camera: Camera3D = player.get_node_or_null("Head/Camera3D") as Camera3D
	if camera == null:
		return false
	if camera.is_position_behind(world_pos):
		return false

	var viewport_size: Vector2 = camera.get_viewport().get_visible_rect().size
	var screen_pos: Vector2 = camera.unproject_position(world_pos)
	var screen_rect := Rect2(Vector2.ZERO, viewport_size).grow(64.0)
	if not screen_rect.has_point(screen_pos):
		return false

	var world: World3D = camera.get_world_3d()
	if world == null:
		return false
	var ray := PhysicsRayQueryParameters3D.create(
		camera.global_position,
		world_pos + Vector3(0.0, 0.85, 0.0)
	)
	ray.exclude = [player.get_rid()]
	var hit: Dictionary = world.direct_space_state.intersect_ray(ray)
	return hit.is_empty()

func _score_candidate(
	player: Node3D,
	id: String,
	pos: Vector3,
	base_weight: float,
	kind: String,
	allow_visible: bool
) -> float:
	var distance: float = player.global_position.distance_to(pos)
	if distance < 5.0:
		return -INF
	if distance > 58.0:
		return -INF

	var visible: bool = _spawn_visible_to_player(player, pos)
	if visible and not allow_visible:
		return -INF

	var ideal_distance: float = 22.0
	var distance_score: float = 1.0 - minf(absf(distance - ideal_distance) / ideal_distance, 1.0)
	var score: float = base_weight + distance_score * 2.25

	if visible:
		score -= 4.5
	if _recent_spawn_ids.has(id):
		score -= 1.65
	if id == _last_spawn_id:
		score -= 1.25

	if kind == "window":
		score += 1.60 if current_round <= 4 else 0.35
	else:
		score += minf(float(maxi(0, current_round - 3)) * 0.10, 0.80)

	var jitter_seed: int = abs((id + "_" + str(_spawn_serial)).hash())
	score += float(jitter_seed % 997) / 997.0 * 0.42
	return score

func _build_spawn_candidates(player: Node3D, allow_visible: bool) -> Array[Dictionary]:
	var candidates: Array[Dictionary] = []

	for barricade: Node in get_tree().get_nodes_in_group("zombie_barricade"):
		if not barricade.has_method("get_outside_spawn"):
			continue
		var pos: Vector3 = barricade.call("get_outside_spawn") as Vector3
		var id: String = "window:" + barricade.name
		var score: float = _score_candidate(player, id, pos, 1.0, "window", allow_visible)
		if barricade.has_method("is_broken") and bool(barricade.call("is_broken")):
			score += 1.10
		if score > -INF:
			candidates.append({
				"kind": "window",
				"id": id,
				"node": barricade,
				"pos": pos,
				"score": score,
			})

	for anchor: Node in get_tree().get_nodes_in_group("zombie_spawn_anchor"):
		if not (anchor is Node3D):
			continue
		var min_round: int = int(anchor.get_meta("min_round", 1))
		if current_round < min_round:
			continue
		var gate: String = str(anchor.get_meta("requires_gate", ""))
		if not _gate_open(gate):
			continue
		var pos: Vector3 = (anchor as Node3D).global_position
		var id: String = "direct:" + str(anchor.get_meta("spawn_id", anchor.name))
		var weight: float = float(anchor.get_meta("weight", 0.7))
		var score: float = _score_candidate(player, id, pos, weight, "direct", allow_visible)
		if score > -INF:
			candidates.append({
				"kind": "direct",
				"id": id,
				"node": anchor,
				"pos": pos,
				"score": score,
			})

	return candidates

func _choose_candidate(player: Node3D) -> Dictionary:
	var candidates: Array[Dictionary] = _build_spawn_candidates(player, false)
	if candidates.is_empty():
		# Never hard-stall a round because every legal entrance is briefly visible.
		# Visible fallback is still scored heavily against direct pop-in.
		candidates = _build_spawn_candidates(player, true)
	if candidates.is_empty():
		return {}

	var best: Dictionary = candidates[0]
	for candidate: Dictionary in candidates:
		if float(candidate["score"]) > float(best["score"]):
			best = candidate
	return best

func _remember_spawn(id: String) -> void:
	_last_spawn_id = id
	_recent_spawn_ids.append(id)
	while _recent_spawn_ids.size() > 3:
		_recent_spawn_ids.pop_front()

func spawn_one() -> Node:
	var player: Node3D = get_tree().get_first_node_in_group("player") as Node3D
	if player == null:
		return null

	var candidate: Dictionary = _choose_candidate(player)
	if candidate.is_empty():
		push_warning("XZOGOT_SPAWN_DIRECTOR_NO_LEGAL_ENTRY")
		return null

	var script_resource: Script = load("res://scripts/zombie_dummy.gd") as Script
	var zombie := CharacterBody3D.new()
	_spawn_serial += 1
	zombie.name = "Zombie_R%d_%d" % [current_round, _spawn_serial]
	zombie.set_script(script_resource)
	zombie.set_meta("round_number", current_round)

	var entry: Node = candidate["node"] as Node
	if str(candidate["kind"]) == "window":
		zombie.call("configure", player, entry)
	else:
		zombie.call("configure_direct", player, entry)

	zombie.connect("died", Callable(self, "_on_zombie_died"))
	get_parent().add_child(zombie)
	zombie.global_position = candidate["pos"] as Vector3

	_remaining_to_spawn = maxi(0, _remaining_to_spawn - 1)
	_alive += 1
	_remember_spawn(str(candidate["id"]))
	print(
		"XZOGOT_ZOMBIE_SPAWN ",
		current_round,
		" alive=", _alive,
		" entry=", candidate["id"],
		" score=", candidate["score"]
	)
	return zombie

func spawn_from_barricade(barricade: Node) -> Node:
	# Deterministic CI/debug path that does not weaken live spawn selection.
	var player: Node3D = get_tree().get_first_node_in_group("player") as Node3D
	if player == null or barricade == null:
		return null
	var script_resource: Script = load("res://scripts/zombie_dummy.gd") as Script
	var zombie := CharacterBody3D.new()
	_spawn_serial += 1
	zombie.name = "Zombie_Probe_%d" % _spawn_serial
	zombie.set_script(script_resource)
	zombie.set_meta("round_number", current_round)
	zombie.call("configure", player, barricade)
	zombie.connect("died", Callable(self, "_on_zombie_died"))
	get_parent().add_child(zombie)
	zombie.global_position = barricade.call("get_outside_spawn") as Vector3
	_remaining_to_spawn = maxi(0, _remaining_to_spawn - 1)
	_alive += 1
	_remember_spawn("window:" + barricade.name)
	return zombie

func _on_zombie_died(_zombie: Node) -> void:
	_alive = maxi(0, _alive - 1)
	if _remaining_to_spawn == 0 and _alive == 0:
		_break_timer = round_break
		print("XZOGOT_ROUND_CLEAR ", current_round)


func set_dev_no_zombies(enabled: bool) -> void:
	_dev_no_zombies = enabled
	if enabled:
		dev_clear_zombies()
	else:
		_break_timer = 0.0
	print("XZOGOT_DEV_NO_ZOMBIES ", enabled)

func dev_clear_zombies() -> void:
	var cleared: int = 0
	for zombie: Node in get_tree().get_nodes_in_group("zombie"):
		if is_instance_valid(zombie):
			zombie.queue_free()
			cleared += 1
	_alive = 0
	_remaining_to_spawn = 0
	_spawn_timer = spawn_interval
	print("XZOGOT_DEV_CLEAR_ZOMBIES ", cleared)

func dev_spawn_one() -> Node:
	var prior_remaining: int = _remaining_to_spawn
	if _remaining_to_spawn <= 0:
		_remaining_to_spawn = 1
	var zombie: Node = spawn_one()
	if zombie == null:
		_remaining_to_spawn = prior_remaining
	print("XZOGOT_DEV_SPAWN_ONE ", zombie != null)
	return zombie

func is_dev_no_zombies() -> bool:
	return _dev_no_zombies

func get_round() -> int:
	return current_round

func get_alive() -> int:
	return _alive

func get_remaining_to_spawn() -> int:
	return _remaining_to_spawn

func get_last_spawn_id() -> String:
	return _last_spawn_id

func get_direct_spawn_count() -> int:
	return get_tree().get_nodes_in_group("zombie_spawn_anchor").size()
