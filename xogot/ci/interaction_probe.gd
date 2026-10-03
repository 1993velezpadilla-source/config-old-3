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
	var wallbuy: Node = scene.get_node_or_null("WallBuy_01")
	var mystery: Node = scene.get_node_or_null("MysteryBoxSocket")
	var perk: Node = scene.get_node_or_null("PerkSocket")
	var power: Node = scene.get_node_or_null("PowerSwitch")

	if player == null or weapon == null:
		_fail(3, "player or weapon missing")
		return
	if rear_door == null or balcony_gate == null or wallbuy == null or mystery == null or perk == null or power == null:
		_fail(4, "one or more interactables missing")
		return
	if get_nodes_in_group("zombie_interactable").size() != 6:
		_fail(5, "expected six interactables")
		return
	if int(player.call("get_points")) != 500:
		_fail(6, "wrong starting points")
		return

	player.call("add_points", 5000)
	if int(player.call("get_points")) != 5500:
		_fail(7, "add_points failed")
		return

	# Verify the actual camera ray can purchase/open the rear door.
	player.set("interaction_range", 4.4)
	var rear_pos: Vector3 = (rear_door as Node3D).global_position
	(player as Node3D).global_position = Vector3(rear_pos.x, 0.38, rear_pos.z + 3.0)
	(player as Node3D).rotation.y = 0.0
	await physics_frame
	if not bool(player.call("request_interact")):
		_fail(8, "ray interaction did not open rear door")
		return
	if int(player.call("get_points")) != 4750:
		_fail(9, "rear door price accounting wrong")
		return
	if not bool(rear_door.call("was_used")):
		_fail(10, "rear door not marked used")
		return

	var points_before_repeat: int = int(player.call("get_points"))
	if bool(rear_door.call("interact", player)):
		_fail(11, "one-shot rear door allowed repeat use")
		return
	if int(player.call("get_points")) != points_before_repeat:
		_fail(12, "repeat door use changed points")
		return

	var reserve_before: int = int(weapon.call("get_reserve"))
	if not bool(wallbuy.call("interact", player)):
		_fail(13, "wallbuy failed")
		return
	if int(weapon.call("get_reserve")) != reserve_before + 60:
		_fail(14, "wallbuy ammo reward wrong")
		return
	if int(player.call("get_points")) != 4250:
		_fail(15, "wallbuy price accounting wrong")
		return

	if not bool(mystery.call("interact", player)):
		_fail(16, "mystery socket failed")
		return
	if int(mystery.call("get_interaction_count")) != 1:
		_fail(17, "mystery interaction count wrong")
		return
	if int(player.call("get_points")) != 3300:
		_fail(18, "mystery price accounting wrong")
		return

	if not bool(perk.call("interact", player)):
		_fail(19, "perk socket failed")
		return
	if not bool(player.get_meta("perk_socket_used", false)):
		_fail(20, "perk state not stored on player")
		return
	if int(player.call("get_points")) != 800:
		_fail(21, "perk price accounting wrong")
		return

	if not bool(power.call("interact", player)):
		_fail(22, "power switch failed")
		return
	if not bool(get_meta("power_on", false)):
		_fail(23, "power state not enabled")
		return
	if int(player.call("get_points")) != 800:
		_fail(24, "free power switch changed points")
		return

	# Player only has 800 now, so the 1000 balcony gate must reject cleanly.
	if bool(balcony_gate.call("interact", player)):
		_fail(25, "unaffordable balcony gate opened")
		return
	if bool(balcony_gate.call("was_used")):
		_fail(26, "unaffordable balcony gate marked used")
		return
	if int(player.call("get_points")) != 800:
		_fail(27, "failed purchase changed points")
		return

	print("XZOGOT_INTERACTION_PROBE_GREEN")
	scene.queue_free()
	await process_frame
	quit(0)
