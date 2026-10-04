extends SceneTree

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("MOBILE_SURVIVAL_PROBE: " + message)
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

	var player: CharacterBody3D = scene.get_node_or_null("Player") as CharacterBody3D
	var weapon: Node = scene.get_node_or_null("Player/Weapon")
	var settings: Node = scene.get_node_or_null("HUD/MobileSettings")
	var round_manager: Node = scene.get_node_or_null("RoundManager")
	if player == null or weapon == null or settings == null or round_manager == null:
		_fail(3, "player/weapon/settings/round manager missing")
		return
	round_manager.set("auto_start", false)

	# Settings must be live, not decorative.
	var original_ads: bool = bool(player.get("ads_toggle_mode"))
	settings.call("_cycle_ads_mode")
	if bool(player.get("ads_toggle_mode")) == original_ads:
		_fail(4, "ADS mode setting did not reach player")
		return

	var gyro_before: int = int(player.get("gyro_mode"))
	settings.call("_cycle_gyro_mode")
	if int(player.get("gyro_mode")) == gyro_before:
		_fail(5, "gyro mode setting did not reach player")
		return

	var auto_knife_before: bool = bool(player.get("auto_knife_enabled"))
	settings.call("_toggle_auto_knife")
	if bool(player.get("auto_knife_enabled")) == auto_knife_before:
		_fail(6, "auto knife toggle did not reach player")
		return
	# Restore enabled for gameplay probe.
	settings.call("_toggle_auto_knife")

	var barricades: Array[Node] = get_nodes_in_group("zombie_barricade")
	if barricades.is_empty():
		_fail(7, "no barricades")
		return
	var barricade: Node = barricades[0]
	barricade.call("zombie_damage", 50.0)
	var boards_before: int = int(barricade.call("get_boards"))
	player.global_position = (barricade as Node3D).global_position + Vector3(0.0, 0.0, 1.0)
	player.set("_repair_timer", 0.0)
	player.call("_update_mobile_assists", 0.5)
	var boards_after: int = int(barricade.call("get_boards"))
	if boards_after <= boards_before:
		_fail(8, "auto rebuild did not restore a plank")
		return

	# Build a durable test zombie and shoot its leg with the MP40 profile.
	if not bool(weapon.call("equip_weapon", "mp40", true)):
		_fail(9, "could not equip MP40")
		return

	var zombie_script: Script = load("res://scripts/zombie_dummy.gd") as Script
	var zombie := CharacterBody3D.new()
	zombie.name = "Zombie_Dismember_Probe"
	zombie.set_script(zombie_script)
	zombie.set_meta("round_number", 12)
	scene.add_child(zombie)
	zombie.global_position = player.global_position + Vector3(0.0, 0.0, -1.25)
	zombie.set("health", 500.0)
	zombie.call("configure_direct", player, null)
	await physics_frame

	for i in range(5):
		var leg_hit: Vector3 = zombie.to_global(Vector3(-0.26, 0.42, 0.0))
		zombie.call("apply_hitscan_damage", 34.0, player, leg_hit)

	if not bool(zombie.call("is_limb_severed", "left_leg")):
		_fail(10, "left leg did not sever")
		return
	if not bool(zombie.call("is_crawler")):
		_fail(11, "severed leg did not convert zombie to crawler")
		return
	if float(zombie.call("get_health")) <= 0.0:
		_fail(12, "crawler died from limb damage instead of surviving")
		return

	# Manual knife remains available even with auto knife support.
	player.set("auto_knife_enabled", false)
	player.set("_knife_timer", 0.0)
	zombie.global_position = player.global_position + Vector3(0.0, 0.0, -1.0)
	var hp_before_knife: float = float(zombie.call("get_health"))
	if not bool(player.call("request_knife")):
		_fail(13, "manual knife did not connect in native range")
		return
	if float(zombie.call("get_health")) >= hp_before_knife:
		_fail(14, "manual knife did not damage zombie")
		return

	print("XZOGOT_SETTINGS_PROBE_GREEN")
	print("XZOGOT_AUTO_REBUILD_PROBE_GREEN")
	print("XZOGOT_MANUAL_KNIFE_PROBE_GREEN")
	print("XZOGOT_DISMEMBERMENT_CRAWLER_PROBE_GREEN")
	print("XZOGOT_MOBILE_SURVIVAL_PROBE_GREEN")
	scene.queue_free()
	await process_frame
	quit(0)
