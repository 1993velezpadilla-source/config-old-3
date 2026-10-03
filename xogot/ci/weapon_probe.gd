extends SceneTree

func _init() -> void:
	call_deferred("_run_probe")

func _run_probe() -> void:
	var packed: PackedScene = load("res://main.tscn") as PackedScene
	if packed == null:
		push_error("WEAPON_PROBE: main scene missing")
		quit(2)
		return

	var scene: Node = packed.instantiate()
	root.add_child(scene)
	await process_frame
	await physics_frame

	var weapon: Node = scene.get_node_or_null("Player/Weapon")
	if weapon == null:
		push_error("WEAPON_PROBE: Weapon missing")
		quit(3)
		return

	if int(weapon.call("get_magazine")) != 30:
		push_error("WEAPON_PROBE: wrong starting magazine")
		quit(4)
		return
	if int(weapon.call("get_reserve")) != 120:
		push_error("WEAPON_PROBE: wrong starting reserve")
		quit(5)
		return

	weapon.call("request_fire")
	if int(weapon.call("get_magazine")) != 29:
		push_error("WEAPON_PROBE: fire did not consume one round")
		quit(6)
		return
	if int(weapon.call("get_shots_fired")) != 1:
		push_error("WEAPON_PROBE: shot counter did not advance")
		quit(7)
		return

	weapon.set("_magazine", 20)
	weapon.set("reserve_ammo", 120)
	weapon.set("_cooldown", 0.0)
	weapon.call("request_reload")
	if not bool(weapon.call("is_reloading")):
		push_error("WEAPON_PROBE: reload did not start")
		quit(8)
		return

	weapon.call("_finish_reload")
	if int(weapon.call("get_magazine")) != 30:
		push_error("WEAPON_PROBE: reload did not refill magazine")
		quit(9)
		return
	if int(weapon.call("get_reserve")) != 110:
		push_error("WEAPON_PROBE: reload reserve accounting wrong")
		quit(10)
		return

	print("XZOGOT_WEAPON_PROBE_GREEN")
	scene.queue_free()
	await process_frame
	quit(0)
