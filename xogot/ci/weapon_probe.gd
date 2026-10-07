extends SceneTree

const WeaponCatalog = preload("res://scripts/weapon_catalog.gd")
const WeaponSourceCombat = preload("res://scripts/weapon_source_combat.gd")

func _init() -> void:
	call_deferred("_run_probe")

func _fail(code: int, message: String) -> void:
	push_error("WEAPON_PROBE: " + message)
	quit(code)

func _run_probe() -> void:
	var packed: PackedScene = load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(2, "main scene missing")
		return

	var scene: Node = packed.instantiate()
	root.add_child(scene)
	await process_frame
	await physics_frame

	var weapon: Node = scene.get_node_or_null("Player/Weapon")
	if weapon == null:
		_fail(3, "Weapon missing")
		return

	if str(weapon.call("get_weapon_id")) != "colt":
		_fail(4, "starting weapon is not Colt")
		return
	var colt_mag := WeaponSourceCombat.base_magazine("colt", -1)
	var colt_reserve := WeaponSourceCombat.base_reserve("colt", -1)
	if int(weapon.call("get_magazine")) != colt_mag or int(weapon.call("get_reserve")) != colt_reserve:
		_fail(5, "Colt DT_Weapons starting ammo wrong")
		return
	var colt_stats: Dictionary = weapon.call("get_runtime_stats") as Dictionary
	if (
		absf(float(colt_stats.get("damage", -1.0)) - WeaponSourceCombat.base_damage("colt", -1.0)) > 0.001
		or absf(float(colt_stats.get("fire_interval", -1.0)) - WeaponSourceCombat.base_fire_interval("colt", -1.0)) > 0.0001
	):
		_fail(19, "Colt DT_Weapons combat profile wrong")
		return
	print("XZOGOT_WEAPON_BASE_SOURCE_GREEN colt damage=", colt_stats.get("damage"), " reserve=", colt_reserve)

	weapon.call("request_fire")
	if not bool(weapon.call("is_muzzle_fx_ready")):
		_fail(16, "muzzle FX did not bind to starting real viewmodel")
		return
	if str(weapon.call("get_muzzle_anchor_mode")) == "none":
		_fail(17, "muzzle anchor mode missing")
		return
	if float(weapon.call("get_muzzle_flash_timer")) <= 0.0:
		_fail(18, "muzzle flash did not trigger on shot")
		return
	print("XZOGOT_WEAPON_MUZZLE_FX_GREEN ", weapon.call("get_muzzle_anchor_mode"))
	if int(weapon.call("get_magazine")) != colt_mag - 1:
		_fail(6, "Colt fire did not consume one round")
		return
	if int(weapon.call("get_shots_fired")) != 1:
		_fail(7, "shot counter did not advance")
		return

	weapon.set("_magazine", 4)
	weapon.set("reserve_ammo", colt_reserve)
	weapon.set("_cooldown", 0.0)
	weapon.call("request_reload")
	if not bool(weapon.call("is_reloading")):
		_fail(8, "reload did not start")
		return
	weapon.call("_finish_reload")
	var colt_reload_need := colt_mag - 4
	if int(weapon.call("get_magazine")) != colt_mag or int(weapon.call("get_reserve")) != colt_reserve - colt_reload_need:
		_fail(9, "Colt source reload accounting wrong")
		return

	if not bool(weapon.call("equip_weapon", "mp40", true)):
		_fail(10, "MP40 equip failed")
		return
	if (
		int(weapon.call("get_magazine")) != WeaponSourceCombat.base_magazine("mp40", -1)
		or int(weapon.call("get_reserve")) != WeaponSourceCombat.base_reserve("mp40", -1)
	):
		_fail(11, "MP40 DT_Weapons ammo profile wrong")
		return
	if bool(weapon.call("is_automatic")) != WeaponSourceCombat.base_is_automatic("mp40", false):
		_fail(12, "MP40 DT_Weapons SelectFire wrong")
		return
	if absf(float(weapon.call("get_ads_fov")) - 46.0) > 0.01:
		_fail(13, "MP40 ADS profile wrong")
		return
	var pool_size: int = int(weapon.call("get_mystery_pool_size"))
	if pool_size != WeaponCatalog.MYSTERY_POOL.size():
		_fail(14, "Mystery pool/runtime catalog mismatch")
		return
	if pool_size != 25:
		_fail(14, "Mystery pool must contain the 25 recovered real box firearms, got %d" % pool_size)
		return
	for entry: Dictionary in WeaponCatalog.MYSTERY_POOL:
		var box_id := str(entry.get("id", ""))
		if box_id in ["ray", "raymk2", "tesla"]:
			_fail(14, "Mystery pool exposed a weapon whose real model is still missing: " + box_id)
			return
	for required_id: String in ["357", "arisaka", "dp28", "kar98k", "mosin", "nambu", "svt40", "tt33", "type99", "walther"]:
		if not WeaponCatalog.has_weapon(required_id):
			_fail(14, "Recovered real weapon missing from catalog: " + required_id)
			return

	var mystery_id: String = str(weapon.call("roll_mystery_weapon"))
	if mystery_id.is_empty() or mystery_id == "mp40":
		_fail(15, "Mystery roll failed to choose alternate weapon")
		return

	print("XZOGOT_WEAPON_CATALOG_PROBE_GREEN ", mystery_id)
	print("XZOGOT_WEAPON_PROBE_GREEN")
	scene.queue_free()
	await process_frame
	quit(0)
