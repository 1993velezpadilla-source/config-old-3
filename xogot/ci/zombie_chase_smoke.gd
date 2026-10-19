extends SceneTree
# CI smoke: instantiate church and exercise the real zombie chase code.
# This is NOT proof of successful pathfinding around all furniture.
func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var scene := load("res://main.tscn") as PackedScene
	if scene == null:
		push_error("ZOMBIE_SMOKE_FAIL scene")
		quit(2)
		return
	var game := scene.instantiate()
	root.add_child(game)
	await process_frame
	var player := game.get_node_or_null("Player") as CharacterBody3D
	if player == null:
		push_error("ZOMBIE_SMOKE_FAIL player")
		quit(3)
		return
	var script := load("res://scripts/zombie_dummy.gd") as Script
	if script == null:
		push_error("ZOMBIE_SMOKE_FAIL zombie script")
		quit(4)
		return
	var zombies: Array[CharacterBody3D] = []
	for i in range(10):
		var zombie := CharacterBody3D.new()
		zombie.set_script(script)
		zombie.name = "SmokeZombie_%02d" % i
		zombie.set("target_player", player)
		zombie.set("phase", 2) # CHASE_PLAYER
		game.add_child(zombie)
		zombie.global_position = Vector3(2.5 + float(i % 5) * 0.5, 1.0, -9.0 + float(i / 5) * 1.0)
		zombies.append(zombie)
	for frame in range(90):
		await physics_frame
		for zombie in zombies:
			if not is_instance_valid(zombie):
				push_error("ZOMBIE_SMOKE_FAIL zombie freed")
				quit(5)
				return
			if not zombie.global_position.is_finite():
				push_error("ZOMBIE_SMOKE_FAIL nonfinite position")
				quit(6)
				return
	print("ZOMBIE_CHASE_SMOKE_GREEN: 10 zombies survived 90 physics frames")
	print("ZOMBIE_CHASE_PENDING: route-completion, obstacle avoidance quality, stairs, network sync")
	quit(0)
