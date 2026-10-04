extends Node

signal round_started(round_number: int, total_zombies: int)
signal round_cleared(round_number: int)

@export var auto_start: bool = true
@export var first_round_delay: float = 5.0
@export var round_break: float = 8.0
@export var max_alive_zombies: int = 24

# Classic Treyarch-style round flow. The total round population grows beyond
# 24; the cap only limits how many can exist simultaneously.
const CLASSIC_SIMULTANEOUS_CAP := 24

var current_round: int = 0
var _remaining_to_spawn: int = 0
var _round_total: int = 0
var _round_spawned: int = 0
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
		# Classic flow: a round can contain hundreds of zombies, but only a
		# bounded wave is alive at one time. Killing one opens a slot for the next.
		if _alive >= get_simultaneous_cap():
			_spawn_timer = minf(_spawn_timer, 0.05)
			return
		_spawn_timer -= delta
		if _spawn_timer <= 0.0:
			spawn_one()
			_spawn_timer = spawn_interval_for_round(current_round)
		return

	if _alive <= 0 and _started:
		_break_timer -= delta
		if _break_timer <= 0.0:
			start_next_round()

func start_next_round() -> void:
	_started = true
	current_round += 1
	_round_total = zombies_for_round(current_round)
	_remaining_to_spawn = _round_total
	_round_spawned = 0
	_spawn_timer = 0.0
	_break_timer = round_break

	for barricade: Node in get_tree().get_nodes_in_group("zombie_barricade"):
		if barricade.has_method("begin_round"):
			barricade.call("begin_round", current_round)

	round_started.emit(current_round, _round_total)
	print(
		"XZOGOT_ROUND_START ",
		current_round,
		" total=", _round_total,
		" cap=", get_simultaneous_cap(),
		" hp=", zombie_health_for_round(current_round),
		" spawn_interval=", spawn_interval_for_round(current_round)
	)

func _active_player_count() -> int:
	return maxi(1, get_tree().get_nodes_in_group("player").size())

func zombies_for_round(round_number: int, player_count: int = -1) -> int:
	# Classic World at War / Black Ops-style population formula.
	var round_id: int = maxi(1, round_number)
	var players: int = maxi(1, player_count if player_count > 0 else _active_player_count())
	var player_term: float = 3.0 if players == 1 else float(players - 1) * 6.0

	if round_id < 10:
		var base: float = 24.0 + player_term * maxf(1.0, float(round_id) / 5.0)
		var early_multiplier: float = 1.0
		match round_id:
			1: early_multiplier = 0.25
			2: early_multiplier = 0.30
			3: early_multiplier = 0.50
			4: early_multiplier = 0.70
			5: early_multiplier = 0.90
		return int(floor(base * early_multiplier))

	return int(floor(
		24.0
		+ player_term
		* (float(round_id) / 5.0)
		* float(round_id)
		* 0.15
	))

func zombie_health_for_round(round_number: int) -> int:
	var round_id: int = maxi(1, round_number)
	if round_id <= 9:
		return round_id * 100 + 50
	return int(floor(950.0 * pow(1.1, float(round_id - 9))))

func spawn_interval_for_round(round_number: int) -> float:
	# Preserve the slow first-round crawl and progressively tighten the stream.
	var round_id: int = maxi(1, round_number)
	if round_id == 1:
		return 1.70
	if round_id == 2:
		return 1.45
	if round_id == 3:
		return 1.20
	if round_id == 4:
		return 1.00
	return maxf(0.32, 0.95 - float(round_id - 4) * 0.055)

func zombie_speed_for_round(round_number: int, spawn_serial: int = 0) -> float:
	# Deterministic mixed-speed population: shamblers early, runners increasingly
	# common later. Motion-profile scaling is applied by the zombie itself.
	var round_id: int = maxi(1, round_number)
	var base: float = 1.10
	if round_id == 2:
		base = 1.28
	elif round_id == 3:
		base = 1.48
	elif round_id == 4:
		base = 1.68
	elif round_id == 5:
		base = 1.86
	elif round_id <= 9:
		base = 1.95 + float(round_id - 5) * 0.13
	else:
		base = minf(3.25, 2.55 + float(round_id - 10) * 0.035)
	var variation: float = float(abs(("speed:" + str(round_id) + ":" + str(spawn_serial)).hash()) % 1000) / 1000.0
	return base * lerpf(0.86, 1.12, variation)

func get_simultaneous_cap() -> int:
	return maxi(1, max_alive_zombies if max_alive_zombies > 0 else CLASSIC_SIMULTANEOUS_CAP)

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
	if _alive >= get_simultaneous_cap():
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
	zombie.set("health", float(zombie_health_for_round(current_round)))
	zombie.set("move_speed", zombie_speed_for_round(current_round, _spawn_serial))
	zombie.set_meta("classic_round_health", zombie_health_for_round(current_round))
	zombie.set_meta("classic_round_speed", float(zombie.get("move_speed")))

	var entry: Node = candidate["node"] as Node
	if str(candidate["kind"]) == "window":
		zombie.call("configure", player, entry)
	else:
		zombie.call("configure_direct", player, entry)

	zombie.connect("died", Callable(self, "_on_zombie_died"))
	get_parent().add_child(zombie)
	zombie.global_position = candidate["pos"] as Vector3

	_remaining_to_spawn = maxi(0, _remaining_to_spawn - 1)
	_round_spawned += 1
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
	if _alive >= get_simultaneous_cap():
		return null
	var script_resource: Script = load("res://scripts/zombie_dummy.gd") as Script
	var zombie := CharacterBody3D.new()
	_spawn_serial += 1
	zombie.name = "Zombie_Probe_%d" % _spawn_serial
	zombie.set_script(script_resource)
	zombie.set_meta("round_number", current_round)
	zombie.set("health", float(zombie_health_for_round(current_round)))
	zombie.set("move_speed", zombie_speed_for_round(current_round, _spawn_serial))
	zombie.set_meta("classic_round_health", zombie_health_for_round(current_round))
	zombie.set_meta("classic_round_speed", float(zombie.get("move_speed")))
	zombie.call("configure", player, barricade)
	zombie.connect("died", Callable(self, "_on_zombie_died"))
	get_parent().add_child(zombie)
	zombie.global_position = barricade.call("get_outside_spawn") as Vector3
	_remaining_to_spawn = maxi(0, _remaining_to_spawn - 1)
	_round_spawned += 1
	_alive += 1
	_remember_spawn("window:" + barricade.name)
	return zombie

func _on_zombie_died(zombie: Node) -> void:
	var powerups: Node = get_tree().get_first_node_in_group("xz_powerup_manager")
	if powerups != null and powerups.has_method("register_zombie_kill"):
		powerups.call("register_zombie_kill", zombie)
	_alive = maxi(0, _alive - 1)
	if _remaining_to_spawn == 0 and _alive == 0:
		_break_timer = round_break
		round_cleared.emit(current_round)
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
	_spawn_timer = spawn_interval_for_round(maxi(1, current_round))
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

func get_round_total() -> int:
	return _round_total

func get_round_spawned() -> int:
	return _round_spawned

func is_between_rounds() -> bool:
	return current_round > 0 and _remaining_to_spawn == 0 and _alive == 0 and _break_timer > 0.0

func get_round_break_remaining() -> float:
	return maxf(0.0, _break_timer) if is_between_rounds() else 0.0

func is_last_zombie() -> bool:
	return _remaining_to_spawn == 0 and _alive == 1

func get_last_spawn_id() -> String:
	return _last_spawn_id

func get_direct_spawn_count() -> int:
	return get_tree().get_nodes_in_group("zombie_spawn_anchor").size()
