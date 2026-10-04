extends Node
class_name XzPowerUpManager

const PICKUP_SCRIPT := preload("res://scripts/powerup_pickup.gd")
const POWERUPS: Array[String] = [
	"max_ammo",
	"double_points",
	"insta_kill",
	"nuke",
	"carpenter",
]

@export var drop_lifetime: float = 30.0
@export var double_points_duration: float = 30.0
@export var insta_kill_duration: float = 30.0
@export var max_active_drops: int = 2
@export var minimum_kills_between_drops: int = 5
@export var guaranteed_drop_kills: int = 18

var _kills_since_drop: int = 0
var _drop_serial: int = 0
var _double_points_timer: float = 0.0
var _insta_kill_timer: float = 0.0
var _network_pickups: Dictionary = {}

func _ready() -> void:
	add_to_group("xz_powerup_manager")
	set_process(true)
	_set_double_points(false)
	_set_insta_kill(false)
	print("XZOGOT_POWERUP_MANAGER_READY kinds=5")

func _process(delta: float) -> void:
	if _double_points_timer > 0.0:
		_double_points_timer = maxf(0.0, _double_points_timer - delta)
		if _double_points_timer <= 0.0:
			_set_double_points(false)
			print("XZOGOT_POWERUP_EXPIRED double_points")
	if _insta_kill_timer > 0.0:
		_insta_kill_timer = maxf(0.0, _insta_kill_timer - delta)
		if _insta_kill_timer <= 0.0:
			_set_insta_kill(false)
			print("XZOGOT_POWERUP_EXPIRED insta_kill")

func _set_double_points(active: bool) -> void:
	get_tree().set_meta("xz_double_points_active", active)
	get_tree().set_meta("xz_double_points_multiplier", 2 if active else 1)

func _set_insta_kill(active: bool) -> void:
	get_tree().set_meta("xz_insta_kill_active", active)

func _active_drop_count() -> int:
	var count: int = 0
	for pickup: Node in get_tree().get_nodes_in_group("xz_powerup_pickup"):
		if bool(pickup.get_meta("network_proxy", false)):
			continue
		count += 1
	return count

func _current_round() -> int:
	var manager: Node = get_parent().get_node_or_null("RoundManager") if get_parent() != null else null
	return int(manager.call("get_round")) if manager != null and manager.has_method("get_round") else 1

func _roll_01(seed_text: String) -> float:
	return float(abs(seed_text.hash()) % 100000) / 100000.0

func _choose_kind() -> String:
	var round_id := _current_round()
	var index: int = absi(("drop:" + str(round_id) + ":" + str(_drop_serial)).hash()) % POWERUPS.size()
	return POWERUPS[index]

func register_zombie_kill(zombie: Node) -> void:
	if bool(get_tree().get_meta("xz_powerup_suppress_drops", false)):
		return
	if zombie != null and bool(zombie.get_meta("suppress_powerup_drop", false)):
		return
	_kills_since_drop += 1
	if _active_drop_count() >= max_active_drops:
		return
	if _kills_since_drop < minimum_kills_between_drops:
		return

	var extra_kills: int = maxi(0, _kills_since_drop - minimum_kills_between_drops)
	var chance: float = minf(0.08 + float(extra_kills) * 0.045, 0.62)
	var guaranteed: bool = _kills_since_drop >= guaranteed_drop_kills
	var roll: float = _roll_01(
		"powerup:%d:%d:%d" % [_current_round(), _drop_serial, _kills_since_drop]
	)
	if not guaranteed and roll > chance:
		return

	var world_pos := Vector3.ZERO
	if zombie is Node3D:
		world_pos = (zombie as Node3D).global_position
	world_pos.y = maxf(world_pos.y, 0.24)
	spawn_powerup(_choose_kind(), world_pos)
	_kills_since_drop = 0

func spawn_powerup(kind: String, world_pos: Vector3) -> Node3D:
	if not POWERUPS.has(kind):
		return null
	if _active_drop_count() >= max_active_drops:
		return null
	_drop_serial += 1
	var pickup := Node3D.new()
	pickup.name = "PowerUp_%s_%d" % [kind, _drop_serial]
	pickup.set_script(PICKUP_SCRIPT)
	pickup.call("configure", kind, self, drop_lifetime)
	get_parent().add_child(pickup)
	pickup.global_position = world_pos + Vector3(0.0, 0.22, 0.0)
	print("XZOGOT_POWERUP_DROPPED ", kind, " round=", _current_round())
	return pickup

func _players() -> Array[Node]:
	return get_tree().get_nodes_in_group("player")

func collect_powerup(kind: String, collector: Node) -> bool:
	if not POWERUPS.has(kind):
		return false
	match kind:
		"max_ammo":
			_apply_max_ammo()
		"double_points":
			_double_points_timer = double_points_duration
			_set_double_points(true)
		"insta_kill":
			_insta_kill_timer = insta_kill_duration
			_set_insta_kill(true)
		"nuke":
			_apply_nuke()
		"carpenter":
			_apply_carpenter()
	print("XZOGOT_POWERUP_COLLECTED ", kind, " by=", collector.name if collector != null else "none")
	var network: Node = get_tree().root.find_child("NetworkManager", true, false)
	if network != null and network.has_method("notify_host_powerup"):
		network.call("notify_host_powerup", kind)
	return true

func _apply_max_ammo() -> void:
	var affected := 0
	for player: Node in _players():
		var weapon: Node = player.get_node_or_null("Weapon")
		if weapon != null and weapon.has_method("refill_max_ammo"):
			weapon.call("refill_max_ammo")
			affected += 1
	print("XZOGOT_POWERUP_MAX_AMMO ", affected)

func _award_all_players(points: int) -> void:
	for player: Node in _players():
		if player.has_method("add_points"):
			player.call("add_points", points)

func _apply_nuke() -> void:
	get_tree().set_meta("xz_powerup_suppress_drops", true)
	var killed := 0
	var zombies := get_tree().get_nodes_in_group("zombie")
	for zombie: Node in zombies:
		if is_instance_valid(zombie) and zombie.has_method("powerup_kill"):
			zombie.set_meta("suppress_powerup_drop", true)
			zombie.call("powerup_kill")
			killed += 1
	get_tree().set_meta("xz_powerup_suppress_drops", false)
	_award_all_players(400)
	print("XZOGOT_POWERUP_NUKE killed=", killed)

func _apply_carpenter() -> void:
	var repaired := 0
	for barricade: Node in get_tree().get_nodes_in_group("zombie_barricade"):
		if barricade.has_method("repair_full_no_reward"):
			if bool(barricade.call("repair_full_no_reward")):
				repaired += 1
	_award_all_players(200)
	print("XZOGOT_POWERUP_CARPENTER repaired=", repaired)

func is_double_points_active() -> bool:
	return _double_points_timer > 0.0

func is_insta_kill_active() -> bool:
	return _insta_kill_timer > 0.0

func get_effect_remaining(kind: String) -> float:
	match kind:
		"double_points": return _double_points_timer
		"insta_kill": return _insta_kill_timer
	return 0.0

func get_active_effects() -> Dictionary:
	var result := {}
	if _double_points_timer > 0.0:
		result["double_points"] = _double_points_timer
	if _insta_kill_timer > 0.0:
		result["insta_kill"] = _insta_kill_timer
	return result

func get_network_pickup_states() -> Array:
	var states: Array = []
	for pickup: Node in get_tree().get_nodes_in_group("xz_powerup_pickup"):
		if bool(pickup.get_meta("network_proxy", false)) or not (pickup is Node3D):
			continue
		var kind_value: String = str(pickup.call("get_powerup_kind")) if pickup.has_method("get_powerup_kind") else ""
		var lifetime_value: float = float(pickup.call("get_lifetime")) if pickup.has_method("get_lifetime") else 0.0
		if kind_value.is_empty() or lifetime_value <= 0.0:
			continue
		states.append([
			pickup.name,
			kind_value,
			(pickup as Node3D).global_position,
			lifetime_value,
		])
	return states

func apply_network_effect_state(double_points_remaining: float, insta_kill_remaining: float) -> void:
	_double_points_timer = maxf(0.0, double_points_remaining)
	_insta_kill_timer = maxf(0.0, insta_kill_remaining)
	_set_double_points(_double_points_timer > 0.0)
	_set_insta_kill(_insta_kill_timer > 0.0)
	print(
		"XZOGOT_NETWORK_POWERUP_EFFECTS double=", _double_points_timer,
		" insta=", _insta_kill_timer
	)

func apply_network_pickup_snapshot(states: Array) -> void:
	var seen: Dictionary = {}
	for state_var: Variant in states:
		if not (state_var is Array):
			continue
		var state: Array = state_var as Array
		if state.size() < 4:
			continue
		var source_id: String = str(state[0])
		var kind_value: String = str(state[1])
		var world_pos: Vector3 = state[2] as Vector3
		var lifetime_value: float = float(state[3])
		if source_id.is_empty() or not POWERUPS.has(kind_value) or lifetime_value <= 0.0:
			continue
		seen[source_id] = true
		var pickup: Node3D = _network_pickups.get(source_id, null) as Node3D
		if pickup == null or not is_instance_valid(pickup):
			pickup = Node3D.new()
			pickup.name = "Net_" + source_id
			pickup.set_script(PICKUP_SCRIPT)
			pickup.call("configure_network_proxy", kind_value, lifetime_value)
			get_parent().add_child(pickup)
			_network_pickups[source_id] = pickup
		pickup.global_position = world_pos
		pickup.set("lifetime", lifetime_value)

	for id_var: Variant in _network_pickups.keys().duplicate():
		var source_id: String = str(id_var)
		if seen.has(source_id):
			continue
		var stale: Node = _network_pickups[source_id] as Node
		_network_pickups.erase(source_id)
		if is_instance_valid(stale):
			stale.queue_free()
	print("XZOGOT_NETWORK_POWERUP_PICKUPS ", seen.size())

func clear_network_pickups() -> void:
	for id_var: Variant in _network_pickups.keys().duplicate():
		var pickup: Node = _network_pickups[id_var] as Node
		if is_instance_valid(pickup):
			pickup.queue_free()
	_network_pickups.clear()

func get_network_pickup_count() -> int:
	var count: int = 0
	for pickup_var: Variant in _network_pickups.values():
		var pickup: Node = pickup_var as Node
		if is_instance_valid(pickup):
			count += 1
	return count

func debug_clear_timed_effects() -> void:
	_double_points_timer = 0.0
	_insta_kill_timer = 0.0
	_set_double_points(false)
	_set_insta_kill(false)

func get_kills_since_drop() -> int:
	return _kills_since_drop
