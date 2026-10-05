extends SceneTree

const ROUND_SCRIPT := preload("res://scripts/round_manager.gd")
const ZOMBIE_SCRIPT := preload("res://scripts/zombie_dummy.gd")

func _fail(code: int, message: String) -> void:
	push_error("SPECIAL_ENEMY_ROUND_PROBE: " + message)
	quit(code)

func _initialize() -> void:
	var manager := Node.new()
	manager.set_script(ROUND_SCRIPT)
	manager.set("auto_start", false)
	root.add_child(manager)

	for round_id: int in [5, 10, 15, 20]:
		if not bool(manager.call("is_sheep_round_number", round_id)):
			_fail(2, "expected sheep round %d" % round_id)
			return
	for round_id: int in [1, 4, 6, 9, 11]:
		if bool(manager.call("is_sheep_round_number", round_id)):
			_fail(3, "unexpected sheep round %d" % round_id)
			return

	if int(manager.call("sheep_for_round", 5, 1)) != 8:
		_fail(4, "1P first sheep population mismatch")
		return
	if int(manager.call("sheep_for_round", 10, 1)) != 10:
		_fail(5, "1P second sheep population mismatch")
		return
	if int(manager.call("sheep_for_round", 5, 4)) != 17:
		_fail(6, "4P first sheep population mismatch")
		return

	var sheep_assets_ready: bool = bool(manager.call("_sheep_assets_ready"))
	var elite_asset_ready: bool = bool(manager.call("_elite_nun_asset_ready"))
	manager.set("_special_round_kind", "")
	for serial: int in range(1, 160):
		var guarded_variant: String = str(manager.call("_enemy_variant_for_spawn", 10, serial))
		if guarded_variant.begins_with("sheep_"):
			_fail(7, "sheep variant escaped outside sheep round: " + guarded_variant)
			return
		if not elite_asset_ready and guarded_variant == "nun_elite":
			_fail(7, "elite spawned without full CMU elite asset")
			return
	print(
		"XZOGOT_SPECIAL_ENEMY_NO_PLACEHOLDER_SPAWN_GREEN sheep_assets=",
		sheep_assets_ready,
		" elite_cmu=",
		elite_asset_ready
	)

	manager.set("_special_round_kind", "sheep")
	var seen: Dictionary = {}
	for serial: int in range(1, 100):
		var variant: String = str(manager.call("_enemy_variant_for_spawn", 5, serial))
		seen[variant] = true
	if not seen.has("sheep_runner") or not seen.has("sheep_brute"):
		_fail(7, "both sheep variants must occur: %s" % seen)
		return

	var runner := CharacterBody3D.new()
	runner.set_script(ZOMBIE_SCRIPT)
	manager.call("_apply_enemy_variant_stats", runner, "sheep_runner", 5, 1)
	if str(runner.get("enemy_variant")) != "sheep_runner":
		_fail(8, "runner variant not applied")
		return
	if float(runner.get("move_speed")) < 4.0 or float(runner.get("player_damage")) != 30.0:
		_fail(9, "runner tuning mismatch")
		return
	if not bool(runner.get_meta("suppress_powerup_drop", false)):
		_fail(10, "sheep random powerups must be suppressed")
		return

	var brute := CharacterBody3D.new()
	brute.set_script(ZOMBIE_SCRIPT)
	manager.call("_apply_enemy_variant_stats", brute, "sheep_brute", 5, 2)
	if float(brute.get("health")) <= float(runner.get("health")):
		_fail(11, "brute must be tougher than runner")
		return
	if float(brute.get("player_damage")) <= float(runner.get("player_damage")):
		_fail(12, "brute must hit harder than runner")
		return

	var elite := CharacterBody3D.new()
	elite.set_script(ZOMBIE_SCRIPT)
	manager.call("_apply_enemy_variant_stats", elite, "nun_elite", 10, 3)
	var normal_health: float = float(manager.call("zombie_health_for_round", 10))
	if float(elite.get("health")) < normal_health * 2.3:
		_fail(13, "elite nun health scaling too low")
		return
	if float(elite.get("player_damage")) != 36.0:
		_fail(14, "elite nun damage mismatch")
		return

	print("XZOGOT_SHEEP_ROUND_SCHEDULE_GREEN")
	print("XZOGOT_SHEEP_VARIANTS_GREEN ", seen)
	print("XZOGOT_SHEEP_STATS_GREEN runner_hp=", runner.get("health"), " brute_hp=", brute.get("health"))
	print("XZOGOT_ELITE_NUN_STATS_GREEN hp=", elite.get("health"), " damage=", elite.get("player_damage"))
	print("XZOGOT_SPECIAL_ENEMY_ROUND_GATE_GREEN")
	manager.queue_free()
	runner.free()
	brute.free()
	elite.free()
	quit(0)
