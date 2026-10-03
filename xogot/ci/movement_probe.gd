extends SceneTree

func _init() -> void:
	call_deferred("_run_probe")

func _run_probe() -> void:
	var packed := load("res://main.tscn") as PackedScene
	if packed == null:
		push_error("MOVEMENT_PROBE: main scene missing")
		quit(2)
		return

	var scene := packed.instantiate()
	root.add_child(scene)
	await process_frame
	await process_frame

	var player := scene.get_node_or_null("Player")
	if player == null:
		push_error("MOVEMENT_PROBE: Player missing")
		quit(3)
		return

	var collider := player.get_node_or_null("CollisionShape3D") as CollisionShape3D
	var head := player.get_node_or_null("Head") as Node3D
	if collider == null or head == null:
		push_error("MOVEMENT_PROBE: collider/head missing")
		quit(4)
		return

	var capsule := collider.shape as CapsuleShape3D
	if capsule == null:
		push_error("MOVEMENT_PROBE: capsule missing")
		quit(5)
		return

	player.call("_set_crouched", true)
	await process_frame
	if absf(capsule.height - 1.18) > 0.02:
		push_error("MOVEMENT_PROBE: crouch capsule height wrong")
		quit(6)
		return
	if absf(collider.position.y - 0.59) > 0.02:
		push_error("MOVEMENT_PROBE: crouch collider position wrong")
		quit(7)
		return

	player.call("_set_crouched", false)
	await process_frame
	if absf(capsule.height - 1.80) > 0.02:
		push_error("MOVEMENT_PROBE: stand capsule height wrong")
		quit(8)
		return
	if absf(collider.position.y - 0.90) > 0.02:
		push_error("MOVEMENT_PROBE: stand collider position wrong")
		quit(9)
		return

	if float(player.get("slide_speed")) <= float(player.get("sprint_speed")):
		push_error("MOVEMENT_PROBE: slide speed must exceed sprint speed")
		quit(10)
		return
	if float(player.get("slide_duration")) <= 0.0:
		push_error("MOVEMENT_PROBE: invalid slide duration")
		quit(11)
		return

	print("XZOGOT_MOVEMENT_PROBE_GREEN")
	scene.queue_free()
	await process_frame
	quit(0)
