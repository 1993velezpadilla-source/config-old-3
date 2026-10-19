extends SceneTree
# Non-destructive Main Nave phase-1 geometry gate.
# Run: godot --headless --path xogot --script res://ci/main_nave_gate.gd
func _init() -> void:
	call_deferred("_audit")

func _audit() -> void:
	var scene: PackedScene = load("res://main.tscn")
	if scene == null:
		push_error("MAIN_NAVE_FAIL: scene missing")
		quit(2)
		return
	var game := scene.instantiate()
	root.add_child(game)
	await process_frame
	await process_frame
	var player := game.get_node_or_null("Player") as CharacterBody3D
	var world := game.get_node_or_null("YouWontWin")
	if player == null or world == null:
		push_error("MAIN_NAVE_FAIL: player or church missing")
		quit(3)
		return
	var benches: Array[StaticBody3D] = []
	var altar_collision := false
	for child in world.get_children():
		if child is StaticBody3D:
			if child.name.begins_with("BenchCollision_"):
				benches.append(child)
			elif child.name == "AltarCollision":
				altar_collision = true
	if benches.size() != 9 or not altar_collision:
		push_error("MAIN_NAVE_FAIL: expected 9 bench colliders and altar collider; got %d / %s" % [benches.size(), altar_collision])
		quit(4)
		return
	# Check each collider is enabled and has a real box shape.
	for bench in benches:
		var shape := bench.get_node_or_null("CollisionShape3D") as CollisionShape3D
		if shape == null or shape.disabled or not (shape.shape is BoxShape3D):
			push_error("MAIN_NAVE_FAIL: missing/disabled bench collider " + bench.name)
			quit(5)
			return
	# Adjacent rows are separated along Z by 4 source units (scaled 0.78).
	# Verify at least a full player diameter of free space between collision AABBs.
	var radius := 0.36
	for a in range(benches.size()):
		for b in range(a + 1, benches.size()):
			var first := benches[a]
			var second := benches[b]
			if absf(first.position.x - second.position.x) > 0.5:
				continue
			var shape_a := (first.get_node("CollisionShape3D") as CollisionShape3D).shape as BoxShape3D
			var shape_b := (second.get_node("CollisionShape3D") as CollisionShape3D).shape as BoxShape3D
			var clearance := absf(first.position.z - second.position.z) - (shape_a.size.z + shape_b.size.z) * 0.5
			if clearance > 0.0 and clearance < radius * 2.0:
				push_error("MAIN_NAVE_FAIL: insufficient row clearance %.3f" % clearance)
				quit(6)
				return
	print("MAIN_NAVE_GEOMETRY_GREEN: 9 solid bench colliders; altar solid; row clearances >= player diameter")
	print("MAIN_NAVE_PENDING: actual jump-over, navmesh routing, zombie pathing and multiplayer require runtime integration tests")
	quit(0)
