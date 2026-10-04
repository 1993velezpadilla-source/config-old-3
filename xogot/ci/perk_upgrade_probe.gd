extends SceneTree

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("PERK_UPGRADE_PROBE: " + message)
	quit(code)

func _run() -> void:
	var packed := load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(2, "main scene missing")
		return
	var scene := packed.instantiate()
	root.add_child(scene)
	await process_frame
	await process_frame

	var player: Node = scene.get_node_or_null("Player")
	var weapon: Node = scene.get_node_or_null("Player/Weapon")
	if player == null or weapon == null:
		_fail(3, "player/weapon missing")
		return

	var perk_nodes: Array[Node] = get_nodes_in_group("perk_machine")
	if perk_nodes.size() != 6:
		_fail(4, "expected six perk machines, got %d" % perk_nodes.size())
		return
	var forge_nodes: Array[Node] = get_nodes_in_group("weapon_upgrade_machine")
	if forge_nodes.size() != 1:
		_fail(5, "expected one Sanctum Forge")
		return

	player.call("add_points", 50000)
	var before_points: int = int(player.call("get_points"))
	var machines_by_id: Dictionary = {}
	for machine_node: Node in perk_nodes:
		if machine_node.has_method("get_perk_id"):
			var machine_id: String = str(machine_node.call("get_perk_id"))
			if not machine_id.is_empty():
				machines_by_id[machine_id] = machine_node
	if machines_by_id.size() != 6:
		_fail(6, "perk machine id registry incomplete")
		return
	var martyr: Node = machines_by_id.get("martyrs_blood") as Node
	if martyr == null:
		_fail(7, "Martyr machine missing")
		return
	if bool(martyr.call("interact", player)):
		_fail(7, "powered perk worked before Power")
		return
	if int(player.call("get_points")) != before_points:
		_fail(8, "failed pre-Power interaction consumed points")
		return

	var power: Node = scene.get_node_or_null("PowerSwitch")
	if power == null or not bool(power.call("interact", player)):
		_fail(9, "Power switch failed")
		return
	await process_frame
	if not bool(get_meta("power_on", false)):
		_fail(10, "Power meta not enabled")
		return

	var perk_ids: Array[String] = [
		"martyrs_blood",
		"quick_hands",
		"pilgrim_rush",
		"choir_sight",
		"twin_bells",
		"last_rites",
	]
	for id: String in perk_ids:
		var machine: Node = machines_by_id.get(id) as Node
		if machine == null:
			_fail(11, "perk machine missing: " + id)
			return
		if not bool(machine.get_meta("powered_visual_on", false)):
			_fail(12, "perk machine visual did not power on: " + id)
			return
		if not bool(machine.call("interact", player)):
			_fail(13, "perk purchase failed: " + id)
			return
		if not bool(player.call("has_perk", id)):
			_fail(14, "perk did not apply: " + id)
			return
		var after_first: int = int(player.call("get_points"))
		if bool(machine.call("interact", player)):
			_fail(15, "duplicate perk purchase should fail: " + id)
			return
		if int(player.call("get_points")) != after_first:
			_fail(16, "duplicate perk purchase consumed points: " + id)
			return

	if absf(float(player.call("get_max_health")) - 200.0) > 0.01:
		_fail(17, "Martyr's Blood health effect wrong")
		return
	if absf(float(player.call("get_reload_multiplier")) - 0.70) > 0.001:
		_fail(18, "Quick Hands effect wrong")
		return
	if absf(float(player.call("get_move_speed_multiplier")) - 1.15) > 0.001:
		_fail(19, "Pilgrim Rush effect wrong")
		return
	if absf(float(player.call("get_spread_multiplier")) - 0.62) > 0.001:
		_fail(20, "Choir Sight spread effect wrong")
		return
	if absf(float(player.call("get_recoil_multiplier")) - 0.68) > 0.001:
		_fail(21, "Choir Sight recoil effect wrong")
		return
	if absf(float(player.call("get_fire_interval_multiplier")) - 0.78) > 0.001:
		_fail(22, "Twin Bells fire-cycle effect wrong")
		return
	if absf(float(player.call("get_weapon_damage_multiplier")) - 1.08) > 0.001:
		_fail(23, "Twin Bells damage effect wrong")
		return

	player.call("apply_damage", 9999.0)
	if bool(player.call("is_downed")):
		_fail(24, "Last Rites did not prevent lethal down")
		return
	if bool(player.call("has_perk", "last_rites")):
		_fail(25, "Last Rites was not consumed")
		return
	if not bool(player.get_meta("last_rites_triggered", false)):
		_fail(26, "Last Rites trigger marker missing")
		return

	if not bool(weapon.call("equip_weapon", "mp40", true)):
		_fail(27, "MP40 equip failed")
		return
	var before: Dictionary = weapon.call("get_runtime_stats") as Dictionary
	var forge: Node = forge_nodes[0]
	if not bool(forge.call("interact", player)):
		_fail(28, "Sanctum Forge purchase failed")
		return
	var after: Dictionary = weapon.call("get_runtime_stats") as Dictionary
	if not bool(after.get("upgraded", false)):
		_fail(29, "Forge did not mark weapon upgraded")
		return
	if float(after.get("damage", 0.0)) <= float(before.get("damage", 0.0)):
		_fail(30, "Forge did not raise damage")
		return
	if int(after.get("magazine_size", 0)) <= int(before.get("magazine_size", 0)):
		_fail(31, "Forge did not increase magazine")
		return
	var forge_points: int = int(player.call("get_points"))
	if bool(forge.call("interact", player)):
		_fail(32, "duplicate Forge upgrade should fail")
		return
	if int(player.call("get_points")) != forge_points:
		_fail(33, "duplicate Forge attempt consumed points")
		return

	print("XZOGOT_PERK_EFFECTS_GREEN 6")
	print("XZOGOT_LAST_RITES_GREEN")
	print("XZOGOT_SANCTUM_FORGE_UPGRADE_GREEN ", before, " -> ", after)
	scene.queue_free()
	await process_frame
	quit(0)
