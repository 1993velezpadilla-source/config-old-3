extends Node

signal round_started(round_number: int, total_zombies: int)
signal round_cleared(round_number: int)
signal last_zombie_started(round_number: int, zombie: Node)

@export var auto_start: bool = true
@export var first_round_delay: float = 5.0
@export var round_break: float = 8.0
@export var max_alive_zombies: int = 24
# Only independent maps may opt out of legacy sheep-special-wave scheduling;
# default remains unchanged for Church, Nacht, and all prior regression tests.
@export var special_rounds_enabled: bool = true
# Map-local override only; existing maps continue using the original zombie logic.
@export var zombie_script_path: String = "res://scripts/zombie_dummy.gd"
# Black Pines opts into ENDLESS survival. This is a map-local switch so
# Church/Nacht retains its existing classic population/health progression.
# A round number is NOT capped at 20/100/255. The engine uses signed int64.
# Only simultaneous actors and per-wave population/health are bounded for
# mobile performance, so a very high round cannot freeze or overflow Godot.
@export var endless_rounds_enabled: bool = false
@export_range(24, 512, 1) var endless_wave_population_cap: int = 144
@export_range(950, 1000000, 50) var endless_zombie_health_cap: int = 250000

# Classic Treyarch-style round flow. The total round population grows beyond
# 24; the cap only limits how many can exist simultaneously.
const CLASSIC_SIMULTANEOUS_CAP := 24
const SHEEP_FIRST_ROUND := 5
const SHEEP_ROUND_INTERVAL := 5
const SHEEP_RUNNER_PATH := "res://assets/zombies/sheep/sheep_runner_animated.glb"
const SHEEP_BRUTE_PATH := "res://assets/zombies/sheep/sheep_brute_animated.glb"
const ELITE_NUN_PATH := "res://assets/zombies/monja_elite/cmu_runtime/monja_black_white_cmu_rig.gltf"

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
var _last_zombie_announced: bool = false
var _player_focus_serial: int = 0
var _dev_no_zombies: bool = false
var _network_match_active: bool = true
var _special_round_kind: String = ""

func _ready() -> void:
	set_process(true)
	if auto_start:
		_break_timer = first_round_delay
	print("XZOGOT_ROUND_MANAGER_READY")
	print("XZOGOT_SPAWN_DIRECTOR_READY")

func _process(delta: float) -> void:
	if _dev_no_zombies or not _network_match_active:
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
	var planned_sheep_round: bool = special_rounds_enabled and is_sheep_round_number(current_round)
	if planned_sheep_round and _sheep_assets_ready():
		_special_round_kind = "sheep"
		_round_total = sheep_for_round(current_round)
	elif planned_sheep_round:
		_special_round_kind = ""
		_round_total = zombies_for_round(current_round)
		push_warning("XZOGOT_SHEEP_ROUND_ASSETS_PENDING round=%d" % current_round)
	else:
		_special_round_kind = ""
		_round_total = zombies_for_round(current_round)
	_remaining_to_spawn = _round_total
	_round_spawned = 0
	_last_zombie_announced = false
	_spawn_timer = 0.0
	_break_timer = round_break

	for barricade: Node in get_tree().get_nodes_in_group("zombie_barricade"):
		if barricade.has_method("begin_round"):
			barricade.call("begin_round", current_round)

	round_started.emit(current_round, _round_total)
	if _special_round_kind == "sheep":
		print("XZOGOT_SHEEP_ROUND_START round=", current_round, " total=", _round_total)
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
	if endless_rounds_enabled and round_id >= 10:
		# Never convert quadratic late-wave float populations to unbounded
		# int64. Keep late survival challenging, but playable on a phone.
		# This caps zombie COUNT PER WAVE, not the number of ROUNDS.
		var pop_cap: int = maxi(24, endless_wave_population_cap) + (mini(4, players) - 1) * 16
		if round_id >= 100:
			return pop_cap
		var estimate: float = 24.0 + player_term * float(round_id) * float(round_id) * 0.03
		return mini(pop_cap, int(floor(estimate)))

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

func is_sheep_round_number(round_number: int) -> bool:
	var round_id: int = maxi(1, round_number)
	return round_id >= SHEEP_FIRST_ROUND and (round_id - SHEEP_FIRST_ROUND) % SHEEP_ROUND_INTERVAL == 0

func _sheep_assets_ready() -> bool:
	return ResourceLoader.exists(SHEEP_RUNNER_PATH) and ResourceLoader.exists(SHEEP_BRUTE_PATH)

func _elite_nun_asset_ready() -> bool:
	return ResourceLoader.exists(ELITE_NUN_PATH)

func sheep_for_round(round_number: int, player_count: int = -1) -> int:
	var round_id: int = maxi(SHEEP_FIRST_ROUND, round_number)
	var wave_index: int = maxi(1, 1 + (round_id - SHEEP_FIRST_ROUND) / SHEEP_ROUND_INTERVAL)
	var players: int = maxi(1, player_count if player_count > 0 else _active_player_count())
	return 6 + wave_index * 2 + maxi(0, players - 1) * 3

func _elite_nun_chance(round_number: int) -> float:
	if round_number < 7:
		return 0.0
	return minf(0.18, 0.055 + float(round_number - 7) * 0.0075)

func _enemy_variant_for_spawn(round_number: int, spawn_serial: int) -> String:
	if _special_round_kind == "sheep":
		var sheep_roll: int = abs(("sheep:%d:%d" % [round_number, spawn_serial]).hash()) % 100
		return "sheep_runner" if sheep_roll < 62 else "sheep_brute"
	if _elite_nun_asset_ready():
		var elite_roll: float = float(abs(("elite_nun:%d:%d" % [round_number, spawn_serial]).hash()) % 10000) / 10000.0
		if elite_roll < _elite_nun_chance(round_number):
			return "nun_elite"
	return "normal"

func _apply_enemy_variant_stats(zombie: Node, variant: String, round_number: int, spawn_serial: int) -> void:
	var base_health: float = float(zombie_health_for_round(round_number))
	var base_speed: float = zombie_speed_for_round(round_number, spawn_serial)
	zombie.set("enemy_variant", variant)
	zombie.set_meta("enemy_variant", variant)
	match variant:
		"sheep_runner":
			zombie.set("health", maxf(260.0, base_health * 0.78))
			zombie.set("move_speed", maxf(4.10, base_speed * 1.34))
			zombie.set("player_damage", 30.0)
			zombie.set("barricade_damage", 34.0)
			zombie.set("attack_interval", 0.72)
			zombie.set("target_visual_height", 0.88)
			zombie.set("target_visual_max_width", 1.18)
			zombie.set("target_visual_max_depth", 0.78)
			zombie.set("collider_radius", 0.32)
			zombie.set("collider_height", 0.92)
			zombie.set("dismemberment_enabled", false)
			zombie.set_meta("suppress_powerup_drop", true)
		"sheep_brute":
			zombie.set("health", maxf(420.0, base_health * 1.28))
			zombie.set("move_speed", maxf(3.45, base_speed * 1.13))
			zombie.set("player_damage", 42.0)
			zombie.set("barricade_damage", 48.0)
			zombie.set("attack_interval", 0.82)
			zombie.set("target_visual_height", 1.02)
			zombie.set("target_visual_max_width", 1.34)
			zombie.set("target_visual_max_depth", 0.90)
			zombie.set("collider_radius", 0.38)
			zombie.set("collider_height", 1.08)
			zombie.set("dismemberment_enabled", false)
			zombie.set_meta("suppress_powerup_drop", true)
		"nun_elite":
			zombie.set("health", maxf(900.0, base_health * 2.35))
			zombie.set("move_speed", base_speed * 1.12)
			zombie.set("player_damage", 36.0)
			zombie.set("barricade_damage", 46.0)
			zombie.set("attack_interval", 0.76)
			zombie.set("head_limb_health", 155.0)
			zombie.set("arm_limb_health", 205.0)
			zombie.set("leg_limb_health", 230.0)
		_:
			zombie.set("health", base_health)
			zombie.set("move_speed", base_speed)
	zombie.set_meta("classic_round_health", float(zombie.get("health")))
	zombie.set_meta("classic_round_speed", float(zombie.get("move_speed")))

func get_special_round_kind() -> String:
	return _special_round_kind

func zombie_health_for_round(round_number: int) -> int:
	var round_id: int = maxi(1, round_number)
	if round_id <= 9:
		return round_id * 100 + 50
	if endless_rounds_enabled:
		# pow(1.1, round-9) overflows on high rounds. Clamp BEFORE pow
		# at rounds far above the hit-point ceiling. Do not turn 1e6 rounds
		# into an infinite-health or negative-health zombie.
		var hp_cap: int = maxi(950, endless_zombie_health_cap)
		if round_id >= 90:
			return hp_cap
		return mini(hp_cap, int(floor(950.0 * pow(1.1, float(round_id - 9)))))
	return int(floor(950.0 * pow(1.1, float(round_id - 9))))

func spawn_interval_for_round(round_number: int) -> float:
	# Preserve the slow first-round crawl and progressively tighten the stream.
	var round_id: int = maxi(1, round_number)
	if round_id == current_round and _special_round_kind == "sheep":
		return maxf(0.46, 0.72 - float(maxi(0, round_id - SHEEP_FIRST_ROUND)) * 0.012)
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
	var base_cap: int = maxi(1, max_alive_zombies if max_alive_zombies > 0 else CLASSIC_SIMULTANEOUS_CAP)
	if _special_round_kind == "sheep":
		return mini(base_cap, 10 + maxi(0, _active_player_count() - 1) * 2)
	return base_cap

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

func _select_focus_player() -> Node3D:
	var candidates: Array[Node3D] = []
	for node: Node in get_tree().get_nodes_in_group("player"):
		if not (node is Node3D):
			continue
		if node.has_method("is_eliminated") and bool(node.call("is_eliminated")):
			continue
		candidates.append(node as Node3D)
	if candidates.is_empty():
		return null
	candidates.sort_custom(func(a: Node3D, b: Node3D): return a.name < b.name)
	var chosen: Node3D = candidates[_player_focus_serial % candidates.size()]
	_player_focus_serial += 1
	return chosen

func spawn_one() -> Node:
	var player: Node3D = _select_focus_player()
	if player == null:
		return null
	if _alive >= get_simultaneous_cap():
		return null

	var candidate: Dictionary = _choose_candidate(player)
	if candidate.is_empty():
		push_warning("XZOGOT_SPAWN_DIRECTOR_NO_LEGAL_ENTRY")
		return null

	var script_resource: Script = load(zombie_script_path) as Script
	var zombie := CharacterBody3D.new()
	_spawn_serial += 1
	var variant: String = _enemy_variant_for_spawn(current_round, _spawn_serial)
	zombie.name = ("%s_R%d_%d" % [variant.capitalize(), current_round, _spawn_serial]).replace(" ", "")
	zombie.set_script(script_resource)
	zombie.set_meta("round_number", current_round)
	_apply_enemy_variant_stats(zombie, variant, current_round, _spawn_serial)

	var entry: Node = candidate["node"] as Node
	if str(candidate["kind"]) == "window":
		zombie.call("configure", player, entry)
	elif entry.has_meta("routed_window_name"):
		# Black Pines' four offscreen outdoor anchors must enter through a
		# REAL window. Never let a direct spawn walk against an intact wall.
		var window_name: String=str(entry.get_meta("routed_window_name"))
		var routed_window: Node=get_parent().get_node_or_null("Architecture/"+window_name)
		if routed_window == null:
			push_error("BLACK_PINES_SPAWN_ROUTE_RED "+window_name)
			zombie.free()
			return null
		zombie.call("configure", player, routed_window)
		zombie.set_meta("spawn_entry_kind", "offscreen_to_window")
	else:
		zombie.call("configure_direct", player, entry)

	zombie.connect("died", Callable(self, "_on_zombie_died"))
	get_parent().add_child(zombie)
	zombie.global_position = candidate["pos"] as Vector3

	_remaining_to_spawn = maxi(0, _remaining_to_spawn - 1)
	_round_spawned += 1
	_alive += 1
	_remember_spawn(str(candidate["id"]))
	_refresh_last_zombie_state()
	print(
		"XZOGOT_ZOMBIE_SPAWN ",
		current_round,
		" alive=", _alive,
		" entry=", candidate["id"],
		" score=", candidate["score"],
		" variant=", str(zombie.get_meta("enemy_variant", "normal"))
	)
	return zombie

func spawn_from_barricade(barricade: Node) -> Node:
	# Deterministic CI/debug path that does not weaken live spawn selection.
	var player: Node3D = _select_focus_player()
	if player == null or barricade == null:
		return null
	if _alive >= get_simultaneous_cap():
		return null
	var script_resource: Script = load(zombie_script_path) as Script
	var zombie := CharacterBody3D.new()
	_spawn_serial += 1
	var variant: String = _enemy_variant_for_spawn(current_round, _spawn_serial)
	zombie.name = "Zombie_Probe_%d" % _spawn_serial
	zombie.set_script(script_resource)
	zombie.set_meta("round_number", current_round)
	_apply_enemy_variant_stats(zombie, variant, current_round, _spawn_serial)
	zombie.call("configure", player, barricade)
	zombie.connect("died", Callable(self, "_on_zombie_died"))
	get_parent().add_child(zombie)
	zombie.global_position = barricade.call("get_outside_spawn") as Vector3
	_remaining_to_spawn = maxi(0, _remaining_to_spawn - 1)
	_round_spawned += 1
	_alive += 1
	_remember_spawn("window:" + barricade.name)
	_refresh_last_zombie_state()
	return zombie

func _on_zombie_died(zombie: Node) -> void:
	var powerups: Node = get_tree().get_first_node_in_group("xz_powerup_manager")
	if powerups != null and powerups.has_method("register_zombie_kill"):
		powerups.call("register_zombie_kill", zombie)
	_alive = maxi(0, _alive - 1)
	_refresh_last_zombie_state()
	if _remaining_to_spawn == 0 and _alive == 0:
		_break_timer = round_break
		if _special_round_kind == "sheep":
			_drop_sheep_round_max_ammo(zombie)
		round_cleared.emit(current_round)
		print("XZOGOT_ROUND_CLEAR ", current_round, " special=", _special_round_kind)


func _drop_sheep_round_max_ammo(last_enemy: Node) -> void:
	var powerups: Node = get_tree().get_first_node_in_group("xz_powerup_manager")
	if powerups == null or not powerups.has_method("spawn_powerup"):
		push_warning("XZOGOT_SHEEP_ROUND_MAX_AMMO_MANAGER_MISSING")
		return
	var world_pos := Vector3.ZERO
	if last_enemy is Node3D:
		world_pos = (last_enemy as Node3D).global_position + Vector3(0.0, 0.35, 0.0)
	else:
		var player := _select_focus_player()
		if player != null:
			world_pos = player.global_position + Vector3(0.0, 0.35, 0.0)
	powerups.call("spawn_powerup", "max_ammo", world_pos)
	print("XZOGOT_SHEEP_ROUND_MAX_AMMO round=", current_round)

func _refresh_last_zombie_state() -> void:
	if not is_last_zombie():
		return
	var survivor: Node = null
	for zombie: Node in get_tree().get_nodes_in_group("zombie"):
		if is_instance_valid(zombie):
			survivor = zombie
			break
	if survivor == null:
		return
	if survivor.has_method("set_last_zombie_mode"):
		survivor.call("set_last_zombie_mode", true)
	else:
		survivor.set_meta("last_zombie", true)
	if not _last_zombie_announced:
		_last_zombie_announced = true
		last_zombie_started.emit(current_round, survivor)
		print("XZOGOT_LAST_ZOMBIE_STARTED round=", current_round, " zombie=", survivor.name)

func reset_network_match() -> void:
	dev_clear_zombies()
	current_round = 0
	_remaining_to_spawn = 0
	_round_total = 0
	_round_spawned = 0
	_alive = 0
	_spawn_timer = 0.0
	_break_timer = first_round_delay
	_started = false
	_spawn_serial = 0
	_recent_spawn_ids.clear()
	_last_spawn_id = ""
	_last_zombie_announced = false
	_player_focus_serial = 0
	print("XZOGOT_NETWORK_MATCH_ROUND_RESET")

func set_network_match_active(active: bool) -> void:
	_network_match_active = active
	if active and current_round == 0 and _break_timer <= 0.0:
		_break_timer = first_round_delay
	print("XZOGOT_NETWORK_MATCH_ROUNDS_ACTIVE ", active)

func is_network_match_active() -> bool:
	return _network_match_active

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
	_last_zombie_announced = false
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

func apply_network_round_state(
	round_number: int,
	round_total: int,
	remaining_to_spawn: int,
	alive_count: int,
	break_remaining: float
) -> void:
	current_round = maxi(0, round_number)
	_round_total = maxi(0, round_total)
	_remaining_to_spawn = maxi(0, remaining_to_spawn)
	_alive = maxi(0, alive_count)
	_break_timer = maxf(0.0, break_remaining)
	_round_spawned = maxi(0, _round_total - _remaining_to_spawn)
	_started = current_round > 0
	set_meta("network_round_state", true)
	print(
		"XZOGOT_NETWORK_ROUND_STATE round=", current_round,
		" total=", _round_total,
		" remaining=", _remaining_to_spawn,
		" alive=", _alive,
		" break=", _break_timer
	)

func get_round() -> int:
	return current_round

func is_endless_survival() -> bool:
	return endless_rounds_enabled

func get_configured_round_limit() -> int:
	# 0 is explicitly unlimited rounds; late-wave population/health budgets
	# do NOT impose a terminal round on the survival mode.
	return 0 if endless_rounds_enabled else -1

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
