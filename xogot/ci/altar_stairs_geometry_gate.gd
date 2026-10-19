extends SceneTree
# Validate altar and balcony ramp collision topology before claiming stair traversal.
func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var scene := load("res://main.tscn") as PackedScene
	if scene == null:
		push_error("ALTAR_STAIRS_FAIL missing main scene")
		quit(2)
		return
	var game := scene.instantiate()
	root.add_child(game)
	await process_frame
	await process_frame
	var altar := game.get_node_or_null("AltarCollision") as StaticBody3D
	var ramp := game.get_node_or_null("BalconyStairRamp") as StaticBody3D
	if altar == null or ramp == null:
		push_error("ALTAR_STAIRS_FAIL missing altar or stair ramp collider")
		quit(3)
		return
	if not ramp.is_in_group("walkable_stair_ramp"):
		push_error("ALTAR_STAIRS_FAIL ramp missing walkable group")
		quit(4)
		return
	for body in [altar, ramp]:
		var shape := body.get_child(0) as CollisionShape3D
		if shape == null or shape.disabled or not (shape.shape is BoxShape3D):
			push_error("ALTAR_STAIRS_FAIL invalid collision on %s" % body.name)
			quit(5)
			return
	var ramp_shape := (ramp.get_child(0) as CollisionShape3D).shape as BoxShape3D
	if ramp_shape.size.z < 4.0 or absf(ramp.rotation_degrees.x) < 5.0:
		push_error("ALTAR_STAIRS_FAIL ramp slope or length invalid")
		quit(6)
		return
	print("ALTAR_STAIRS_GEOMETRY_GREEN: solid altar and inclined balcony ramp")
	print("ALTAR_STAIRS_PENDING: player/zombie ascent and descent require physics route tests")
	quit(0)
