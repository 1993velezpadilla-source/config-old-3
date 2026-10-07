extends SceneTree

const WeaponSourcePresentation = preload("res://scripts/weapon_viewmodel_source_presentation.gd")
const SourceModifierPolicy = preload("res://scripts/source_modifier_policy.gd")

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

	var source_profile_file := FileAccess.open("res://data/weapon_source_movement.json", FileAccess.READ)
	if source_profile_file == null:
		_fail(43, "28-gun source movement profile missing")
		return
	var source_profile_payload: Variant = JSON.parse_string(source_profile_file.get_as_text())
	if not (source_profile_payload is Dictionary) or int((source_profile_payload as Dictionary).get("weapon_count", 0)) != 28:
		_fail(44, "source movement profile did not contain 28 guns")
		return
	var timing_checks := {
		"colt": Vector2(0.10, 0.10),
		"mp40": Vector2(0.20, 0.20),
		"bar": Vector2(0.35, 0.35),
		"mg42": Vector2(0.50, 0.50),
		"ptrs": Vector2(0.40, 0.60),
	}
	for source_id: String in timing_checks.keys():
		var expected: Vector2 = timing_checks[source_id]
		if absf(WeaponSourcePresentation.ads_in_time(source_id) - expected.x) > 0.0001 or absf(WeaponSourcePresentation.ads_out_time(source_id) - expected.y) > 0.0001:
			_fail(45, "source ADS timing mismatch for " + source_id)
			return
	if absf(WeaponSourcePresentation.source_ads_move_multiplier("colt") - 1.0) > 0.0001:
		_fail(46, "Colt ADS movement did not cancel WaW 50 percent penalty")
		return
	if absf(WeaponSourcePresentation.source_ads_move_multiplier("mp40") - 0.5) > 0.0001:
		_fail(47, "MP40 ADS movement did not preserve WaW 50 percent penalty")
		return
	print("XZOGOT_28_SOURCE_ADS_PROFILES_GREEN weapons=28 colt=0.10 mp40=0.20 bar=0.35 mg42=0.50 ptrs=0.40/0.60")

	if (
		absf(SourceModifierPolicy.SPEED_COLA_RELOAD_TIME_MULTIPLIER - 0.50) > 0.0001
		or absf(SourceModifierPolicy.STAMIN_UP_MOVE_SPEED_MULTIPLIER - 1.07) > 0.0001
		or absf(SourceModifierPolicy.DEADSHOT_SPREAD_MULTIPLIER - 0.65) > 0.0001
		or absf(SourceModifierPolicy.DOUBLE_TAP_INTERVAL_MULTIPLIER - 0.75) > 0.0001
		or absf(SourceModifierPolicy.DOUBLE_TAP_PROJECTILE_DAMAGE_MULTIPLIER - 2.0) > 0.0001
		or absf(SourceModifierPolicy.JUGGERNOG_MAX_HEALTH - 250.0) > 0.0001
	):
		_fail(48, "COD source perk constants drifted")
		return
	print("XZOGOT_SOURCE_PERK_CONSTANTS_GREEN reload=0.50 move=1.07 spread=0.65 rate=0.75 damage=2.0 jug=250")

	for perk_id: String in ["quick_hands", "pilgrim_rush", "choir_sight", "twin_bells", "martyrs_blood", "last_rites"]:
		if not bool(player.call("grant_perk", perk_id)):
			_fail(49, "could not grant source-mapped perk " + perk_id)
			return
	if absf(float(player.call("get_reload_multiplier")) - 0.50) > 0.0001:
		_fail(50, "Speed Cola source reload multiplier mismatch")
		return
	if absf(float(player.call("get_move_speed_multiplier")) - 1.07) > 0.0001:
		_fail(51, "Stamin-Up source move multiplier mismatch")
		return
	if absf(float(player.call("get_spread_multiplier")) - 0.65) > 0.0001 or absf(float(player.call("get_recoil_multiplier")) - 1.0) > 0.0001:
		_fail(52, "Deadshot source spread/no-recoil-policy mismatch")
		return
	if absf(float(player.call("get_fire_interval_multiplier")) - 0.75) > 0.0001:
		_fail(53, "Double Tap source fire interval mismatch")
		return
	if absf(float(player.call("get_weapon_damage_multiplier_for", "mp40", "smg")) - 2.0) > 0.0001:
		_fail(54, "Double Tap II projectile damage mismatch")
		return
	if absf(float(player.call("get_weapon_damage_multiplier_for", "raygun", "wonder")) - 1.0) > 0.0001:
		_fail(55, "Double Tap II incorrectly doubled wonder weapon damage")
		return
	if absf(float(player.call("get_max_health")) - 250.0) > 0.0001:
		_fail(56, "Jugger-Nog source health mismatch")
		return
	print("XZOGOT_SOURCE_PERK_RUNTIME_GREEN")

	if not bool(weapon.call("equip_weapon", "bar", true)):
		_fail(57, "could not equip BAR for source Pack-a-Punch proof")
		return
	if not bool(weapon.call("upgrade_current_weapon")):
		_fail(58, "could not Pack-a-Punch BAR")
		return
	var pack_stats: Dictionary = weapon.call("get_runtime_stats") as Dictionary
	if absf(float(pack_stats.get("damage", 0.0)) - 355.0) > 0.001:
		_fail(59, "BAR PaP MaxDamage did not come from DT_WeaponsPAP")
		return
	if absf(float(pack_stats.get("fire_interval", 0.0)) - (60.0 / 545.0)) > 0.0001:
		_fail(60, "BAR PaP RPM/fire interval did not come from DT_WeaponsPAP")
		return
	if int(pack_stats.get("magazine_size", 0)) != 30:
		_fail(61, "BAR PaP clip did not come from DT_WeaponsPAP")
		return
	if int(weapon.call("get_reserve")) != 180:
		_fail(62, "BAR PaP reserve did not come from DT_WeaponsPAP")
		return
	if str(pack_stats.get("display_name", "")) != "The Widow Maker":
		_fail(63, "BAR PaP name did not come from DT_WeaponsPAP")
		return
	if str(pack_stats.get("pack_balance_authority", "")) != "Project Aether DT_WeaponsPAP":
		_fail(64, "PaP source authority marker missing")
		return
	print("XZOGOT_PACK_SOURCE_TABLE_GREEN bar_damage=355 rpm=545 clip=30 reserve=180")

	for skin_path: String in [
		"res://assets/hud/latest_12/hud_ads.webp",
		"res://assets/hud/latest_12/hud_ads_fire.webp",
		"res://assets/hud/latest_12/hud_fire.png",
		"res://assets/hud/latest_12/hud_reload.webp",
		"res://assets/hud/latest_12/hud_knife.webp",
		"res://assets/hud/latest_12/hud_slide.webp",
		"res://assets/hud/latest_12/hud_sprint.webp",
		"res://assets/hud/latest_12/hud_swap.webp",
		"res://assets/hud/latest_12/hud_grenade.webp",
		"res://assets/hud/latest_12/hud_claw.webp",
		"res://assets/hud/latest_12/hud_crouch.webp",
		"res://assets/hud/latest_12/hud_prone.webp",
		"res://assets/hud/latest_12/hud_jump.png",
	]:
		if not ResourceLoader.exists(skin_path):
			_fail(20, "custom mobile skin missing: " + skin_path)
			return
	print("XZOGOT_MOBILE_CUSTOM_SKINS_GREEN")

	if not bool(weapon.call("equip_weapon", "colt", true)):
		_fail(21, "could not equip Colt for mobile auto-fire")
		return
	var pistol_before: int = int(weapon.call("get_shots_fired"))
	weapon.call("set_mobile_trigger_held", true)
	for i in range(24):
		weapon.call("_process", 0.02)
	weapon.call("set_mobile_trigger_held", false)
	var pistol_after: int = int(weapon.call("get_shots_fired"))
	if pistol_after - pistol_before < 2:
		_fail(22, "mobile pistol hold-fire did not auto-tap")
		return
	print("XZOGOT_MOBILE_PISTOL_AUTOFIRE_GREEN shots=", pistol_after - pistol_before)

	if not bool(weapon.call("equip_weapon", "kar98k", true)):
		_fail(23, "could not equip Kar98k for release-fire")
		return
	if not bool(weapon.call("mobile_adsfire_release_mode")):
		_fail(24, "Kar98k was not classified release-to-fire")
		return
	var viewport_size: Vector2 = root.get_viewport().get_visible_rect().size
	var adsfire_pos := Vector2(0.795 * viewport_size.x, 0.435 * viewport_size.y)
	var ads_down := InputEventScreenTouch.new()
	ads_down.index = 77
	ads_down.position = adsfire_pos
	ads_down.pressed = true
	var release_before: int = int(weapon.call("get_shots_fired"))
	player.call("_handle_touch", ads_down)
	if int(weapon.call("get_shots_fired")) != release_before:
		_fail(25, "release-to-fire weapon fired on touch-down")
		return
	for i in range(20):
		weapon.call("_process", 0.02)
	if not bool(weapon.call("is_mobile_ads_ready")):
		_fail(32, "release-to-fire weapon never reached source ADS readiness")
		return
	print("XZOGOT_MOBILE_ADS_READY_GATE_GREEN")
	var ads_up := InputEventScreenTouch.new()
	ads_up.index = 77
	ads_up.position = adsfire_pos
	ads_up.pressed = false
	player.call("_handle_touch", ads_up)
	if int(weapon.call("get_shots_fired")) != release_before + 1:
		_fail(26, "release-to-fire weapon did not fire exactly once on touch-up")
		return
	print("XZOGOT_MOBILE_RELEASE_FIRE_GREEN")

	if not bool(weapon.call("equip_weapon", "mp40", true)):
		_fail(27, "could not equip MP40 for sprint reload")
		return
	weapon.call("request_fire")
	weapon.set("_cooldown", 0.0)
	weapon.call("request_reload")
	if not bool(weapon.call("is_reloading")):
		_fail(28, "reload did not start before sprint test")
		return
	player.set("_move_touch", 901)
	player.set("_move_raw_vector", Vector2(0.0, -1.20))
	player.set("_move_vector", Vector2(0.0, -1.0))
	player.call("_physics_process", 0.05)
	if not bool(player.call("is_sprinting")):
		_fail(29, "auto-sprint did not engage for reload test")
		return
	if not bool(weapon.call("is_reloading")):
		_fail(30, "sprinting cancelled gun reload")
		return
	weapon.call("_process", 0.10)
	if not bool(weapon.call("is_reloading")):
		_fail(31, "reload was cancelled during sprint timeline")
		return
	player.set("_move_touch", -1)
	player.set("_move_raw_vector", Vector2.ZERO)
	player.set("_move_vector", Vector2.ZERO)
	player.set("_sprint_suppressed", false)
	print("XZOGOT_SPRINT_RELOAD_PRESERVED_GREEN")

	player.set("_move_touch", 902)
	player.set("_move_raw_vector", Vector2(0.0, -1.20))
	player.set("_move_vector", Vector2(0.0, -1.0))
	player.set("_sprint_suppressed", false)
	player.call("_physics_process", 0.05)
	if not bool(player.call("is_sprinting")):
		_fail(33, "physical sprint zone did not engage")
		return
	print("XZOGOT_MOBILE_SPRINT_ZONE_GREEN")

	var fire_pos := Vector2(0.885 * viewport_size.x, 0.585 * viewport_size.y)
	var fire_down := InputEventScreenTouch.new()
	fire_down.index = 78
	fire_down.position = fire_pos
	fire_down.pressed = true
	player.call("_handle_touch", fire_down)
	player.call("_physics_process", 0.05)
	if bool(player.call("is_sprinting")) or not bool(player.get("_sprint_suppressed")):
		_fail(34, "FIRE did not suppress active sprint")
		return
	var fire_up := InputEventScreenTouch.new()
	fire_up.index = 78
	fire_up.position = fire_pos
	fire_up.pressed = false
	player.call("_handle_touch", fire_up)
	player.call("_physics_process", 0.05)
	if bool(player.call("is_sprinting")):
		_fail(35, "sprint re-armed before stick left sprint zone")
		return
	player.set("_move_raw_vector", Vector2.ZERO)
	player.set("_move_vector", Vector2.ZERO)
	player.call("_physics_process", 0.05)
	if bool(player.get("_sprint_suppressed")):
		_fail(36, "sprint suppression did not clear after leaving zone")
		return
	player.set("_move_touch", -1)
	print("XZOGOT_MOBILE_ACTION_SPRINT_SUPPRESSION_GREEN")

	if not bool(weapon.call("equip_weapon", "mp40", true)):
		_fail(37, "could not equip MP40 for ADS reload restore")
		return
	weapon.call("request_fire")
	weapon.set("_cooldown", 0.0)
	player.set("ads_toggle_mode", true)
	player.set_meta("ads_toggled", true)
	player.call("_request_mobile_reload")
	if not bool(weapon.call("is_reloading")) or bool(player.get_meta("ads_toggled", false)):
		_fail(38, "toggle ADS did not hip out for reload")
		return
	weapon.call("_finish_reload")
	player.call("_physics_process", 0.01)
	if not bool(player.get_meta("ads_toggled", false)) or bool(player.get("_reload_restore_ads")):
		_fail(39, "toggle ADS did not restore after reload")
		return
	print("XZOGOT_MOBILE_ADS_RELOAD_RESTORE_GREEN")

	player.set_meta("ads_toggled", true)
	player.set("_move_touch", 903)
	player.set("_move_raw_vector", Vector2(0.0, -0.90))
	player.set("_move_vector", Vector2(0.0, -0.90))
	player.velocity = Vector3.ZERO
	for i in range(8):
		player.call("_physics_process", 0.05)
	var horizontal_speed := Vector2(player.velocity.x, player.velocity.z).length()
	var source_ads_move: float = float(weapon.call("get_source_ads_move_multiplier"))
	var expected_ads_speed: float = float(player.get("walk_speed")) * source_ads_move * float(player.call("get_move_speed_multiplier"))
	if absf(horizontal_speed - expected_ads_speed) > 0.08:
		_fail(40, "ADS walk speed multiplier mismatch: %.3f vs %.3f" % [horizontal_speed, expected_ads_speed])
		return
	player.set_meta("ads_toggled", false)
	player.set("_move_touch", -1)
	player.set("_move_raw_vector", Vector2.ZERO)
	player.set("_move_vector", Vector2.ZERO)
	print("XZOGOT_MOBILE_ADS_WALK_SPEED_GREEN speed=", horizontal_speed, " source_mult=", source_ads_move)
	print("XZOGOT_ADS_MOVE_SOURCE_POLICY_GREEN authority=", weapon.get_meta("weapon_source_ads_move_authority", ""))

	# Restore the Settings-owned ADS mode after the forced toggle-ADS runtime
	# test above so the settings propagation test starts from canonical state.
	player.set("ads_toggle_mode", bool(settings.call("get_setting_value", "ads_toggle_mode")))
	player.set_meta("ads_toggled", false)

	# Settings must be live, not decorative.
	var original_ads: bool = bool(player.get("ads_toggle_mode"))
	settings.call("_cycle_ads_mode")
	if bool(player.get("ads_toggle_mode")) == original_ads:
		_fail(4, "ADS mode setting did not reach player")
		return

	var gyro_before: int = int(player.get("gyro_mode"))
	if gyro_before != 0 and gyro_before != 2:
		_fail(5, "gyro exposed a forbidden non-ADS-only mode")
		return
	settings.call("_cycle_gyro_mode")
	var gyro_after: int = int(player.get("gyro_mode"))
	if gyro_after == gyro_before or (gyro_after != 0 and gyro_after != 2):
		_fail(5, "gyro OFF/ADS ONLY setting did not reach player")
		return
	# Restore ADS ONLY and prove it cannot apply from the hip.
	if gyro_after == 0:
		settings.call("_cycle_gyro_mode")
	player.set_meta("ads_toggled", false)
	if bool(player.call("gyro_should_apply", true)):
		_fail(41, "gyro applied while hip-fire")
		return
	player.set_meta("ads_toggled", true)
	if not bool(player.call("gyro_should_apply", true)):
		_fail(42, "gyro did not apply while ADS")
		return
	player.set_meta("ads_toggled", false)
	print("XZOGOT_GYRO_ADS_ONLY_GREEN")

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
