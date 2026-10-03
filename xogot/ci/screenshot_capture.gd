extends SceneTree

# Procedural material realism pass.

# Human scale 0.78 screenshot.

# Current build capture after headshot/window fixes.

# Capture Monja Basica common church zombie.
# Auto-fit Monja screenshot.
# Final proportion pass screenshot.

func _init() -> void:
	call_deferred("_capture")

func _capture() -> void:
	var packed: PackedScene = load("res://main.tscn") as PackedScene
	if packed == null:
		push_error("SCREENSHOT: main scene missing")
		quit(2)
		return

	var scene: Node = packed.instantiate()
	root.add_child(scene)

	for i in range(20):
		await process_frame

	var round_manager: Node = scene.get_node_or_null("RoundManager")
	if round_manager != null:
		round_manager.set("auto_start", false)
		round_manager.call("start_next_round")
		var zombie: Node3D = round_manager.call("spawn_one") as Node3D
		if zombie != null:
			zombie.set("phase", 2)
			zombie.global_position = Vector3(0.0, 0.48, 2.4)
			var player: Node3D = scene.get_node_or_null("Player") as Node3D
			if player != null:
				zombie.look_at(player.global_position, Vector3.UP)
			zombie.set_physics_process(false)

			# Very soft warm fill only for visibility; keep gameplay contrast/shadows intact.
			var inspect_light := OmniLight3D.new()
			inspect_light.name = "ScreenshotSoftFill"
			inspect_light.position = Vector3(0.8, 2.1, 5.2)
			inspect_light.omni_range = 6.5
			inspect_light.light_energy = 0.48
			inspect_light.light_color = Color(0.82, 0.68, 0.52)
			inspect_light.shadow_enabled = true
			scene.add_child(inspect_light)

	for i in range(12):
		await process_frame

	var image: Image = root.get_texture().get_image()
	if image == null or image.is_empty():
		push_error("SCREENSHOT: viewport capture empty")
		quit(3)
		return

	var path := "/tmp/xogot-current-game.png"
	var err: Error = image.save_png(path)
	if err != OK:
		push_error("SCREENSHOT: save_png failed %s" % err)
		quit(4)
		return

	print("XZOGOT_SCREENSHOT_GREEN ", path, " ", image.get_width(), "x", image.get_height())
	quit(0)
