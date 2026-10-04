extends SceneTree

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("DEV_MENU_PROBE: " + message)
	paused = false
	quit(code)

func _run() -> void:
	var packed: PackedScene = load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(2, "main scene missing")
		return

	var scene: Node = packed.instantiate()
	root.add_child(scene)
	await process_frame
	await physics_frame

	var settings: Node = scene.get_node_or_null("HUD/MobileSettings")
	var player: Node = scene.get_node_or_null("Player")
	var weapon: Node = scene.get_node_or_null("Player/Weapon")
	var rounds: Node = scene.get_node_or_null("RoundManager")
	if settings == null or player == null or weapon == null or rounds == null:
		_fail(3, "DEV dependencies missing")
		return

	if not bool(settings.get("dev_menu_visible_in_release")):
		_fail(4, "DEV menu is not enabled for release testing")
		return
	if settings.find_child("OpenDev", true, false) == null:
		_fail(5, "DEV LAB entry button missing")
		return
	if settings.find_child("Dev_infinite_health", true, false) == null:
		_fail(6, "DEV toggle UI missing")
		return
	if settings.find_child("Weapon_mp40", true, false) == null:
		_fail(7, "weapon lab button missing")
		return

	settings.call("open_pause_menu")
	if not paused or not bool(settings.call("is_menu_open")):
		_fail(8, "pause menu did not pause tree")
		return
	settings.call("close_menu")
	if paused or bool(settings.call("is_menu_open")):
		_fail(9, "pause menu did not resume tree")
		return
	print("XZOGOT_RELEASE_PAUSE_PROBE_GREEN")

	settings.call("_set_dev_flag", "infinite_health", true)
	settings.call("_set_dev_flag", "infinite_points", true)
	settings.call("_set_dev_flag", "infinite_ammo", true)
	settings.call("_set_dev_flag", "no_zombies", true)
	settings.call("_set_dev_flag", "noclip", true)
	settings.call("_set_dev_flag", "speed_boost", true)

	player.set("health", 25.0)
	player.call("apply_damage", 50.0)
	if absf(float(player.call("get_health")) - float(player.get("max_health"))) > 0.01:
		_fail(10, "infinite health failed")
		return

	var raw_points: int = int(player.get("points"))
	if not bool(player.call("spend_points", 99999)):
		_fail(11, "infinite points refused purchase")
		return
	if int(player.get("points")) != raw_points or int(player.call("get_points")) != 999999:
		_fail(12, "infinite points accounting failed")
		return

	weapon.call("equip_weapon", "mp40", true)
	var mag_before: int = int(weapon.call("get_magazine"))
	weapon.set("_cooldown", 0.0)
	weapon.call("request_fire")
	if int(weapon.call("get_magazine")) != mag_before:
		_fail(13, "infinite ammo consumed magazine")
		return
	if not bool(weapon.call("is_dev_infinite_ammo")):
		_fail(14, "infinite ammo state missing")
		return

	if not bool(rounds.call("is_dev_no_zombies")):
		_fail(15, "no-zombies state missing")
		return
	if not bool(player.get_meta("dev_noclip", false)):
		_fail(16, "noclip player state missing")
		return
	if not bool(player.get_meta("dev_speed_boost", false)):
		_fail(17, "speed boost player state missing")
		return
	print("XZOGOT_RELEASE_DEV_FLAGS_PROBE_GREEN")

	settings.call("_dev_unlock_all")
	for gate_name: String in [
		"RearDoor",
		"BalconyGate",
		"WestOuterGate",
		"EastOuterGate",
		"RearRuinsGate",
		"BellTowerGate",
		"CryptGate",
	]:
		var gate: Node = scene.get_node_or_null(gate_name)
		if gate == null or not gate.has_method("was_used") or not bool(gate.call("was_used")):
			_fail(18, "DEV unlock failed: " + gate_name)
			return
	print("XZOGOT_RELEASE_DEV_UNLOCK_PROBE_GREEN")

	settings.call("_dev_equip_weapon", "trench")
	if str(weapon.call("get_weapon_id")) != "trench":
		_fail(19, "weapon lab did not equip Trench")
		return
	print("XZOGOT_RELEASE_WEAPON_LAB_PROBE_GREEN")

	settings.call("_set_dev_flag", "no_zombies", false)
	var spawned: Node = rounds.call("dev_spawn_one") as Node
	if spawned == null:
		_fail(20, "DEV spawn-one failed")
		return
	rounds.call("dev_clear_zombies")
	if int(rounds.call("get_alive")) != 0:
		_fail(21, "DEV clear zombies failed")
		return

	for key: String in [
		"infinite_health",
		"infinite_points",
		"infinite_ammo",
		"noclip",
		"speed_boost",
	]:
		settings.call("_set_dev_flag", key, false)

	print("XZOGOT_RELEASE_DEV_MENU_PROBE_GREEN")
	scene.queue_free()
	await process_frame
	quit(0)
