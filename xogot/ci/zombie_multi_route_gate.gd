extends SceneTree
# Multiple route-completion probes. Each scenario is isolated in a fresh scene.
# This gate verifies arrival, not perfect route choice or multiplayer sync.
const CASES := [
	{"name": "right_pews", "start": Vector3(3.705, 0.38, -12.0), "goal": Vector3(3.705, 0.38, 4.0)},
	{"name": "left_pews", "start": Vector3(-3.705, 0.38, -12.0), "goal": Vector3(-3.705, 0.38, 4.0)},
	{"name": "center_aisle", "start": Vector3(0.0, 0.38, -12.0), "goal": Vector3(0.0, 0.38, 4.0)}
]

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var packed := load("res://main.tscn") as PackedScene
	var zombie_script := load("res://scripts/zombie_dummy.gd") as Script
	if packed == null or zombie_script == null:
		push_error("MULTI_ROUTE_FAIL: required scene/script missing")
		quit(2)
		return
	for test_case in CASES:
		var game := packed.instantiate()
		root.add_child(game)
		await process_frame
		await process_frame
		var player := game.get_node_or_null("Player") as CharacterBody3D
		if player == null:
			push_error("MULTI_ROUTE_FAIL: player missing")
			quit(3)
			return
		player.global_position = test_case["goal"]
		var zombie := CharacterBody3D.new()
		zombie.set_script(zombie_script)
		zombie.name = "RouteProbe_" + str(test_case["name"])
		game.add_child(zombie)
		zombie.global_position = test_case["start"]
		zombie.set("target_player", player)
		zombie.set("phase", 2)
		var arrived := false
		var closest := INF
		for tick in range(1200):
			await physics_frame
			if not is_instance_valid(zombie) or not zombie.global_position.is_finite():
				push_error("MULTI_ROUTE_FAIL: invalid zombie %s" % test_case["name"])
				quit(4)
				return
			var distance := Vector2(zombie.global_position.x - player.global_position.x, zombie.global_position.z - player.global_position.z).length()
			closest = minf(closest, distance)
			if distance <= 1.5:
				print("MULTI_ROUTE_PASS %s tick=%d" % [test_case["name"], tick])
				arrived = true
				break
		game.queue_free()
		await process_frame
		if not arrived:
			push_error("MULTI_ROUTE_FAIL: %s closest=%.2fm" % [test_case["name"], closest])
			quit(5)
			return
	print("MULTI_ROUTE_GREEN: 3 / 3 church routes completed")
	quit(0)
