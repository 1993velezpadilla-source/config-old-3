extends SceneTree

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("COOP_REVIVE_PROBE: " + message)
	quit(code)

func _run() -> void:
	var packed := load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(2, "main scene missing")
		return
	var scene: Node = packed.instantiate()
	root.add_child(scene)
	await process_frame
	await physics_frame

	var player: Node = scene.get_node_or_null("Player")
	if player == null:
		_fail(3, "primary player missing")
		return

	var teammate: Node = player.duplicate()
	teammate.name = "Teammate"
	teammate.set("use_nav_spawn", false)
	scene.add_child(teammate)
	await process_frame
	await physics_frame
	var teammate_cam: Camera3D = teammate.get_node_or_null("Head/Camera3D") as Camera3D
	if teammate_cam != null:
		teammate_cam.current = false

	(player as Node3D).global_position = Vector3(0.0, 0.38, 6.24)
	(teammate as Node3D).global_position = Vector3(1.0, 0.38, 6.24)

	player.call("apply_damage", 9999.0)
	if not bool(player.call("is_downed")):
		_fail(4, "player did not enter downed state")
		return
	if bool(player.call("is_eliminated")):
		_fail(5, "player eliminated immediately instead of bleedout")
		return
	if absf(float(player.call("get_bleedout_remaining")) - 45.0) > 0.1:
		_fail(6, "classic bleedout timer wrong")
		return
	print("XZOGOT_COOP_DOWNED_STATE_GREEN")

	# Touch Use/Claw prioritizes the nearby downed teammate.
	if not bool(teammate.call("request_interact")):
		_fail(7, "Use did not prioritize downed teammate")
		return
	teammate.set("_use_touch", 77)
	teammate.call("_update_revive_support", 2.0)
	var half_ratio: float = float(player.call("get_revive_progress_ratio"))
	if half_ratio < 0.49 or half_ratio > 0.51:
		_fail(8, "half revive progress wrong: " + str(half_ratio))
		return
	if not bool(player.call("is_downed")):
		_fail(9, "partial revive completed too early")
		return
	print("XZOGOT_COOP_REVIVE_HOLD_GREEN")

	# Releasing Use cancels the current revive after the small contact grace.
	teammate.set("_use_touch", -1)
	teammate.call("_update_revive_support", 0.01)
	player.call("_tick_downed_state", 0.31)
	if float(player.call("get_revive_progress_ratio")) > 0.001:
		_fail(10, "revive progress did not cancel after release")
		return
	print("XZOGOT_COOP_REVIVE_CANCEL_GREEN")

	# Hold for the full 4 seconds.
	teammate.set("_use_touch", 78)
	teammate.call("_update_revive_support", 4.1)
	teammate.set("_use_touch", -1)
	if bool(player.call("is_downed")):
		_fail(11, "full revive did not lift player")
		return
	if bool(player.call("is_eliminated")):
		_fail(12, "revived player remained eliminated")
		return
	var expected_health: float = float(player.get("max_health")) * 0.50
	if absf(float(player.call("get_health")) - expected_health) > 0.1:
		_fail(13, "revive health fraction wrong")
		return
	print("XZOGOT_COOP_REVIVE_COMPLETE_GREEN")

	# Distance is authoritative.
	player.call("apply_damage", 9999.0)
	(teammate as Node3D).global_position = Vector3(5.0, 0.38, 6.24)
	if bool(teammate.call("contribute_revive", player, 4.1)):
		_fail(14, "revive succeeded outside range")
		return
	if not bool(player.call("is_downed")):
		_fail(15, "out-of-range revive changed downed state")
		return
	print("XZOGOT_COOP_REVIVE_RANGE_GREEN")

	# Bleedout is final until an explicit respawn/heal path resets the player.
	player.set("bleedout_duration", 1.0)
	player.call("heal_full")
	player.call("apply_damage", 9999.0)
	player.call("_tick_downed_state", 1.1)
	if not bool(player.call("is_eliminated")):
		_fail(16, "bleedout did not eliminate player")
		return
	if bool(teammate.call("contribute_revive", player, 4.1)):
		_fail(17, "eliminated player was revivable")
		return
	print("XZOGOT_COOP_BLEEDOUT_GREEN")

	player.call("heal_full")
	if bool(player.call("is_downed")) or bool(player.call("is_eliminated")):
		_fail(18, "heal/respawn reset did not clear lifecycle state")
		return
	print("XZOGOT_COOP_RESPAWN_RESET_GREEN")
	print("XZOGOT_COOP_REVIVE_SYSTEM_GREEN")

	scene.queue_free()
	await process_frame
	quit(0)
