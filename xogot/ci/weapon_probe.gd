extends SceneTree

const WeaponCatalog = preload("res://scripts/weapon_catalog.gd")

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
	if int(weapon.call("get_magazine")) != 8 or int(weapon.call("get_reserve")) != 80:
		_fail(5, "Colt starting ammo wrong")
		return

	weapon.call("request_fire")
	if int(weapon.call("get_magazine")) != 7:
		_fail(6, "Colt fire did not consume one round")
		return
	if int(weapon.call("get_shots_fired")) != 1:
		_fail(7, "shot counter did not advance")
		return

	weapon.set("_magazine", 4)
	weapon.set("reserve_ammo", 80)
	weapon.set("_cooldown", 0.0)
	weapon.call("request_reload")
	if not bool(weapon.call("is_reloading")):
		_fail(8, "reload did not start")
		return
	weapon.call("_finish_reload")
	if int(weapon.call("get_magazine")) != 8 or int(weapon.call("get_reserve")) != 76:
		_fail(9, "Colt reload accounting wrong")
		return

	if not bool(weapon.call("equip_weapon", "mp40", true)):
		_fail(10, "MP40 equip failed")
		return
	if int(weapon.call("get_magazine")) != 32 or int(weapon.call("get_reserve")) != 192:
		_fail(11, "MP40 ammo profile wrong")
		return
	if not bool(weapon.call("is_automatic")):
		_fail(12, "MP40 should be automatic")
		return
	if absf(float(weapon.call("get_ads_fov")) - 46.0) > 0.01:
		_fail(13, "MP40 ADS profile wrong")
		return
	var pool_size: int = int(weapon.call("get_mystery_pool_size"))
	if pool_size != WeaponCatalog.MYSTERY_POOL.size():
		_fail(14, "Mystery pool/runtime catalog mismatch")
		return
	if pool_size < 28:
		_fail(14, "Mystery pool unexpectedly lost recovered real weapons")
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
