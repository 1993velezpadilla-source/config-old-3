extends SceneTree

func _init() -> void:
	call_deferred("_run_probe")

func _fail(code: int, message: String) -> void:
	push_error("INTERACTION_PROBE: " + message)
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
	await physics_frame

	var player: Node = scene.get_node_or_null("Player")
	var weapon: Node = scene.get_node_or_null("Player/Weapon")
	var rear_door: Node = scene.get_node_or_null("RearDoor")
	var balcony_gate: Node = scene.get_node_or_null("BalconyGate")
	var wallbuy: Node = scene.get_node_or_null("WallBuy_M1")
	var mystery: Node = scene.get_node_or_null("MysteryBoxSocket")
	var perk: Node = scene.get_node_or_null("Perk_martyrs_blood")
	var power: Node = scene.get_node_or_null("PowerSwitch")
	var forge: Node = scene.get_node_or_null("SanctumForge")
	var bell: Node = scene.get_node_or_null("BellRope")

	if player == null or weapon == null:
		_fail(3, "player or weapon missing")
		return
	if (
		rear_door == null or balcony_gate == null or wallbuy == null
		or mystery == null or perk == null or power == null
		or forge == null or bell == null
	):
		_fail(4, "one or more current interactables missing")
		return

	if get_nodes_in_group("zombie_interactable").size() != 27:
		_fail(5, "expected 27 current interactables")
		return
	if get_nodes_in_group("wall_buy").size() != 10:
		_fail(6, "expected ten audited wall buys")
		return
	if get_nodes_in_group("wall_buy_chalk").size() != 10:
		_fail(7, "expected ten diegetic chalk silhouettes")
		return
	if get_nodes_in_group("perk_machine").size() != 6:
		_fail(8, "expected six powered perk machines")
		return
	if get_nodes_in_group("weapon_upgrade_machine").size() != 1:
		_fail(9, "expected one Sanctum Forge")
		return
	if get_nodes_in_group("bell_interaction").size() != 1:
		_fail(10, "expected one bell interaction")
		return
	if int(player.call("get_points")) != 500:
		_fail(11, "wrong starting points")
		return

	player.call("add_points", 20000)
	if int(player.call("get_points")) != 20500:
		_fail(12, "add_points failed")
		return

	# Verify actual camera ray opens the front door.
	player.set("interaction_range", 4.4)
	var rear_pos: Vector3 = (rear_door as Node3D).global_position
	(player as Node3D).global_position = Vector3(rear_pos.x, 0.38, rear_pos.z - 3.0)
	(player as Node3D).rotation.y = PI
	await physics_frame
	if not bool(player.call("request_interact")):
		_fail(13, "ray interaction did not open front door")
		return
	if int(player.call("get_points")) != 19750:
		_fail(14, "front door price accounting wrong")
		return

	if str(wallbuy.call("get_weapon_id")) != "m1":
		_fail(15, "M1 wall-buy identity wrong")
		return
	if not bool(wallbuy.call("interact", player)):
		_fail(16, "M1 wall-buy failed")
		return
	if str(weapon.call("get_weapon_id")) != "m1":
		_fail(17, "wall-buy did not equip M1")
		return
	if int(player.call("get_points")) != 19150:
		_fail(18, "M1 price accounting wrong")
		return

	var reserve_before: int = int(weapon.call("get_reserve"))
	if not bool(wallbuy.call("interact", player)):
		_fail(19, "M1 ammo refill purchase failed")
		return
	if int(player.call("get_points")) != 18850:
		_fail(20, "M1 ammo cost wrong")
		return
	if int(weapon.call("get_reserve")) <= reserve_before:
		_fail(21, "M1 ammo purchase did not increase reserve")
		return

	if not bool(mystery.call("interact", player)):
		_fail(22, "mystery box failed")
		return
	if int(player.call("get_points")) != 17900:
		_fail(23, "mystery price accounting wrong")
		return
	var mystery_result: String = str(mystery.call("get_last_result"))
	if mystery_result.is_empty() or mystery_result == "m1":
		_fail(24, "mystery did not equip a different catalog weapon")
		return
	if str(weapon.call("get_weapon_id")) != mystery_result:
		_fail(25, "mystery result/equipped weapon mismatch")
		return

	# Powered machines must refuse use before Power and must not spend points.
	var before_power_points: int = int(player.call("get_points"))
	if bool(perk.call("interact", player)):
		_fail(26, "powered perk worked before Power")
		return
	if int(player.call("get_points")) != before_power_points:
		_fail(27, "failed pre-Power perk consumed points")
		return
	if str(perk.call("get_last_result")) != "POWER_REQUIRED":
		_fail(28, "pre-Power perk did not report POWER_REQUIRED")
		return
	if bool(forge.call("interact", player)):
		_fail(29, "Forge worked before Power")
		return

	if not bool(power.call("interact", player)):
		_fail(30, "power switch failed")
		return
	if not bool(get_meta("power_on", false)):
		_fail(31, "power state not enabled")
		return
	await process_frame

	if not bool(perk.call("interact", player)):
		_fail(32, "Martyr's Blood purchase failed after Power")
		return
	if not bool(player.call("has_perk", "martyrs_blood")):
		_fail(33, "perk purchase did not reach player")
		return
	if float(player.call("get_max_health")) < 200.0:
		_fail(34, "Martyr's Blood did not raise max health")
		return
	if int(player.call("get_points")) != 15400:
		_fail(35, "perk price accounting wrong")
		return

	var damage_before: float = float((weapon.call("get_runtime_stats") as Dictionary).get("damage", 0.0))
	if not bool(forge.call("interact", player)):
		_fail(36, "Sanctum Forge failed")
		return
	if not bool(weapon.call("is_upgraded")):
		_fail(37, "Forge did not mark weapon upgraded")
		return
	var damage_after: float = float((weapon.call("get_runtime_stats") as Dictionary).get("damage", 0.0))
	if damage_after <= damage_before:
		_fail(38, "Forge did not increase weapon damage")
		return
	if int(player.call("get_points")) != 10400:
		_fail(39, "Forge price accounting wrong")
		return

	if not bool(bell.call("interact", player)):
		_fail(40, "bell rope failed")
		return
	if str(bell.call("get_last_result")) != "BELL_RUNG":
		_fail(41, "bell rope result wrong")
		return

	# An intentionally impossible purchase still must remain closed.
	player.set("points", 0)
	if bool(balcony_gate.call("interact", player)):
		_fail(42, "unaffordable balcony gate opened")
		return

	# All six new wall weapons must be paid, equippable and catalog-backed,
	# using the same real interaction method the player uses in the map.
	player.call("add_points", 25000)
	var expected_new_weapons: Array[String] = ["kar98k", "gewehr", "ppsh", "type100", "stg", "fg42"]
	for id: String in expected_new_weapons:
		var machine: Node = scene.get_node_or_null("WallBuy_" + id.to_upper())
		if machine == null or str(machine.call("get_weapon_id")) != id:
			_fail(50, "new wall weapon missing: " + id)
			return
		if not bool(machine.call("interact", player)):
			_fail(51, "new wall weapon purchase failed: " + id)
			return
		if str(weapon.call("get_weapon_id")) != id:
			_fail(52, "new wall weapon was not equipped: " + id)
			return
	print("XZOGOT_REVIVAL_SIX_WALLBUY_PURCHASES_GREEN")

	print("XZOGOT_WALLBUY_PROBE_GREEN")
	print("XZOGOT_MYSTERY_EQUIP_PROBE_GREEN ", mystery_result)
	print("XZOGOT_POWERED_MACHINES_PROBE_GREEN")
	print("XZOGOT_SANCTUM_FORGE_PROBE_GREEN")
	print("XZOGOT_BELL_INTERACTION_PROBE_GREEN")
	print("XZOGOT_INTERACTION_PROBE_GREEN")
	scene.queue_free()
	await process_frame
	quit(0)
