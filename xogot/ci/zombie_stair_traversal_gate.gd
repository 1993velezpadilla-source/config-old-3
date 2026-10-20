extends SceneTree
# Stair traversal is deliberately RED until a real character ascends and descends.
# Tests both directions, vertical displacement and final position.
func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var scene := load("res://main.tscn") as PackedScene
	var zombie_script := load("res://scripts/zombie_dummy.gd") as Script
	if scene == null or zombie_script == null:
		push_error("STAIR_TRAVERSAL_FAIL: scene or zombie script missing")
		quit(2)
		return
	for ascending in [true, false]:
		var game := scene.instantiate()
		root.add_child(game)
		await process_frame
		await process_frame
		var player := game.get_node_or_null("Player") as CharacterBody3D
		var ramp := game.get_node_or_null("BalconyStairRamp") as StaticBody3D
		# The purchasable BalconyGate sits across the ramp at z=7.45*.78.
		# Open it using the actual door implementation before traversal;
		# a closed purchasable gate is SUPPOSED to block zombies.
		var gate := game.get_node_or_null("BalconyGate")
		if gate == null or not gate.has_method("_open_door"):
			push_error("STAIR_TRAVERSAL_FAIL: BalconyGate unavailable")
			quit(6)
			return
		gate.call("_open_door")
		await physics_frame
		var gate_shape := gate.get_child(gate.get_child_count() - 1) as CollisionShape3D
		if gate_shape == null or not gate_shape.disabled:
			push_error("STAIR_TRAVERSAL_FAIL: open balcony gate still collides")
			quit(7)
			return
		print("STAIR_GATE_OPEN_GREEN: purchased gate collision removed")
		if player == null or ramp == null:
			push_error("STAIR_TRAVERSAL_FAIL: missing player or ramp")
			quit(3)
			return
		# Authored ramp goes from (-8, .38, .60) to (-8, 5.60, 7.55), scaled by .78.
		var bottom := Vector3(-6.24, 0.50, 0.20)
		var top := Vector3(-6.24, 4.80, 6.20)
		var origin: Vector3 = bottom if ascending else top
		var destination: Vector3 = top if ascending else bottom
		player.global_position = destination
		player.set_physics_process(false)
		var rounds := game.get_node_or_null("RoundManager")
		if rounds != null:
			rounds.set_process(false)
			rounds.set_physics_process(false)
		var zombie := CharacterBody3D.new()
		zombie.set_script(zombie_script)
		game.add_child(zombie)
		zombie.global_position = origin
		zombie.set("target_player", player)
		zombie.set("phase", 2)
		var reached := false
		var initial_y := zombie.global_position.y
		var extreme_y := initial_y
		for tick in range(1200):
			await physics_frame
			if not is_instance_valid(zombie) or not zombie.global_position.is_finite():
				push_error("STAIR_TRAVERSAL_FAIL: invalid zombie")
				quit(4)
				return
			extreme_y = maxf(extreme_y, zombie.global_position.y) if ascending else minf(extreme_y, zombie.global_position.y)
			if tick % 240 == 0:
				print("STAIR_TRACE %s tick=%d position=%s floor=%s velocity=%s" % ["up" if ascending else "down", tick, zombie.global_position, zombie.is_on_floor(), zombie.velocity])
			var horizontal := Vector2(zombie.global_position.x - destination.x, zombie.global_position.z - destination.z).length()
			if horizontal <= 1.5 and absf(zombie.global_position.y - destination.y) <= 1.7:
				reached = true
				print("STAIR_TRAVERSAL_PASS %s tick=%d vertical=%.2f" % ["up" if ascending else "down", tick, absf(extreme_y - initial_y)])
				break
		game.queue_free()
		await process_frame
		if not reached or absf(extreme_y - initial_y) < 2.0:
			push_error("STAIR_TRAVERSAL_FAIL: %s failed ascent/descent (vertical=%.2f)" % ["up" if ascending else "down", absf(extreme_y - initial_y)])
			quit(5)
			return
	print("STAIR_TRAVERSAL_GREEN: zombie climbed and descended balcony ramp")
	quit(0)
