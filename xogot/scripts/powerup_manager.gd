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
	return get_tree().get_nodes_in_group("xz_powerup_pickup").size()

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

func debug_clear_timed_effects() -> void:
	_double_points_timer = 0.0
	_insta_kill_timer = 0.0
	_set_double_points(false)
	_set_insta_kill(false)

func get_kills_since_drop() -> int:
	return _kills_since_drop
