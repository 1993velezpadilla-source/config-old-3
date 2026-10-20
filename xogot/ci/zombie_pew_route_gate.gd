extends SceneTree
# Route gate: verify actual player-target progress across pew rows.
# A failed gate is diagnostic; never treat motion alone as navigation success.
func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var packed := load("res://main.tscn") as PackedScene
	if packed == null:
		push_error("ZOMBIE_ROUTE_FAIL: missing main scene")
		quit(2)
		return
	var game := packed.instantiate()
	root.add_child(game)
	await process_frame
	await process_frame
	var player := game.get_node_or_null("Player") as CharacterBody3D
	if player == null:
		push_error("ZOMBIE_ROUTE_FAIL: missing player")
		quit(3)
		return
	# Park the target on the other side of several bench rows.
	player.global_position = Vector3(4.75 * 0.78, 0.38, 4.0)
	var zombie_script := load("res://scripts/zombie_dummy.gd") as Script
	if zombie_script == null:
		push_error("ZOMBIE_ROUTE_FAIL: missing zombie script")
		quit(4)
		return
	var zombie := CharacterBody3D.new()
	zombie.set_script(zombie_script)
	zombie.name = "PewRouteProbe"
	game.add_child(zombie)
	zombie.global_position = Vector3(4.75 * 0.78, 0.38, -12.0)
	zombie.set("target_player", player)
	zombie.set("phase", 2)
	var start_distance := zombie.global_position.distance_to(player.global_position)
	var closest_distance := start_distance
	for tick in range(1200):
		await physics_frame
		if not is_instance_valid(zombie) or not zombie.global_position.is_finite():
			push_error("ZOMBIE_ROUTE_FAIL: invalid zombie state")
			quit(5)
			return
		var distance := Vector2(zombie.global_position.x - player.global_position.x, zombie.global_position.z - player.global_position.z).length()
		closest_distance = minf(closest_distance, distance)
		if distance <= 1.5:
			print("ZOMBIE_ROUTE_GREEN: reached target in %d frames; start=%.2f closest=%.2f" % [tick, start_distance, closest_distance])
			quit(0)
			return
	push_error("ZOMBIE_ROUTE_FAIL: could not reach target across pew rows after 1200 frames; start=%.2f closest=%.2f final=%s" % [start_distance, closest_distance, str(zombie.global_position)])
	quit(6)
