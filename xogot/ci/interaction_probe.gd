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
	var perk: Node = scene.get_node_or_null("PerkSocket")
	var power: Node = scene.get_node_or_null("PowerSwitch")

	if player == null or weapon == null:
		_fail(3, "player or weapon missing")
		return
	if rear_door == null or balcony_gate == null or wallbuy == null or mystery == null or perk == null or power == null:
		_fail(4, "one or more interactables missing")
		return
	if get_nodes_in_group("zombie_interactable").size() != 14:
		_fail(5, "expected fourteen interactables")
		return
	if get_nodes_in_group("wall_buy").size() != 4:
		_fail(6, "expected four audited wall buys")
		return
	if get_nodes_in_group("wall_buy_chalk").size() != 4:
		_fail(7, "expected four diegetic chalk silhouettes")
		return
	if int(player.call("get_points")) != 500:
		_fail(8, "wrong starting points")
		return

	player.call("add_points", 5000)
	if int(player.call("get_points")) != 5500:
		_fail(9, "add_points failed")
		return

	# Verify actual camera ray opens the front door.
	player.set("interaction_range", 4.4)
	var rear_pos: Vector3 = (rear_door as Node3D).global_position
	(player as Node3D).global_position = Vector3(rear_pos.x, 0.38, rear_pos.z - 3.0)
	(player as Node3D).rotation.y = PI
	await physics_frame
	if not bool(player.call("request_interact")):
		_fail(10, "ray interaction did not open front door")
		return
	if int(player.call("get_points")) != 4750:
		_fail(11, "front door price accounting wrong")
		return

	if str(wallbuy.call("get_weapon_id")) != "m1":
		_fail(12, "M1 wall-buy identity wrong")
		return
	if not bool(wallbuy.call("interact", player)):
		_fail(13, "M1 wall-buy failed")
		return
	if str(weapon.call("get_weapon_id")) != "m1":
		_fail(14, "wall-buy did not equip M1")
		return
	if int(player.call("get_points")) != 4150:
		_fail(15, "M1 price accounting wrong")
		return

	var reserve_before: int = int(weapon.call("get_reserve"))
	if not bool(wallbuy.call("interact", player)):
		_fail(16, "M1 ammo refill purchase failed")
		return
	if int(player.call("get_points")) != 3850:
		_fail(17, "M1 ammo cost wrong")
		return
	if int(weapon.call("get_reserve")) <= reserve_before:
		_fail(18, "M1 ammo purchase did not increase reserve")
		return

	if not bool(mystery.call("interact", player)):
		_fail(19, "mystery socket failed")
		return
	if int(player.call("get_points")) != 2900:
		_fail(20, "mystery price accounting wrong")
		return
	var mystery_result: String = str(mystery.call("get_last_result"))
	if mystery_result.is_empty() or mystery_result == "m1":
		_fail(21, "mystery did not equip a different catalog weapon")
		return
	if str(weapon.call("get_weapon_id")) != mystery_result:
		_fail(22, "mystery result/equipped weapon mismatch")
		return

	if not bool(perk.call("interact", player)):
		_fail(23, "perk socket failed")
		return
	if int(player.call("get_points")) != 400:
		_fail(24, "perk price accounting wrong")
		return
	if not bool(power.call("interact", player)):
		_fail(25, "power switch failed")
		return
	if not bool(get_meta("power_on", false)):
		_fail(26, "power state not enabled")
		return

	# 400 points cannot buy the 1000-point balcony route.
	if bool(balcony_gate.call("interact", player)):
		_fail(27, "unaffordable balcony gate opened")
		return

	print("XZOGOT_WALLBUY_PROBE_GREEN")
	print("XZOGOT_MYSTERY_EQUIP_PROBE_GREEN ", mystery_result)
	print("XZOGOT_INTERACTION_PROBE_GREEN")
	scene.queue_free()
	await process_frame
	quit(0)
