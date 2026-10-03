extends SceneTree

func _init() -> void:
	call_deferred("_run_probe")

func _run_probe() -> void:
	var packed: PackedScene = load("res://main.tscn") as PackedScene
	if packed == null:
		push_error("MOVEMENT_PROBE: main scene missing")
		quit(2)
		return

	var scene: Node = packed.instantiate()
	root.add_child(scene)
	await process_frame
	await physics_frame
	await physics_frame

	var player: Node = scene.get_node_or_null("Player")
	if player == null:
		push_error("MOVEMENT_PROBE: Player missing")
		quit(3)
		return

	var collider: CollisionShape3D = player.get_node_or_null("CollisionShape3D") as CollisionShape3D
	var head: Node3D = player.get_node_or_null("Head") as Node3D
	if collider == null or head == null:
		push_error("MOVEMENT_PROBE: collider/head missing")
		quit(4)
		return

	var capsule: CapsuleShape3D = collider.shape as CapsuleShape3D
	if capsule == null:
		push_error("MOVEMENT_PROBE: capsule missing")
		quit(5)
		return

	# Hold a synthetic crouch touch through a physics frame.
	player.set("_crouch_touch", 77)
	await physics_frame
	if absf(capsule.height - 1.18) > 0.02:
		push_error("MOVEMENT_PROBE: crouch capsule height wrong: %s" % capsule.height)
		quit(6)
		return
	if absf(collider.position.y - 0.59) > 0.02:
		push_error("MOVEMENT_PROBE: crouch collider position wrong: %s" % collider.position.y)
		quit(7)
		return

	# Release and make sure standing geometry returns.
	player.set("_crouch_touch", -1)
	await physics_frame
	if absf(capsule.height - 1.80) > 0.02:
		push_error("MOVEMENT_PROBE: stand capsule height wrong: %s" % capsule.height)
		quit(8)
		return
	if absf(collider.position.y - 0.90) > 0.02:
		push_error("MOVEMENT_PROBE: stand collider position wrong: %s" % collider.position.y)
		quit(9)
		return

	# Synthetic full-stick + crouch edge should start one slide.
	player.set("_move_touch", 88)
	player.set("_move_vector", Vector2(0.0, -1.0))
	player.set("_crouch_touch", 77)
	player.set("_crouch_was_pressed", false)
	player.set("_slide_cooldown_timer", 0.0)
	await physics_frame
	if not bool(player.get("_sliding")):
		push_error("MOVEMENT_PROBE: slide did not start")
		quit(10)
		return

	if float(player.get("slide_speed")) <= float(player.get("sprint_speed")):
		push_error("MOVEMENT_PROBE: slide speed must exceed sprint speed")
		quit(11)
		return
	if float(player.get("slide_duration")) <= 0.0:
		push_error("MOVEMENT_PROBE: invalid slide duration")
		quit(12)
		return

	print("XZOGOT_MOVEMENT_PROBE_GREEN")
	scene.queue_free()
	await process_frame
	quit(0)
