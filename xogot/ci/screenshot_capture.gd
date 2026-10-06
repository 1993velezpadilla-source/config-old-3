extends SceneTree

# Capture rebuilt source-authored hands after stale-action purge.

# Weapon presentation acceptance: real texture binding + +X to -Z axis correction.

# Church V3 sanctuary + window-light readability capture.
# Final grounded altar-facing furniture capture.

# Normalized altar bench + Monja facing capture.

# Architectural shell V2 screenshot.

# Gothic anti toy pass.

# Procedural material realism pass.

# Human scale 0.78 screenshot.

# Current build capture after headshot/window fixes.

# Capture Monja Basica common church zombie.
# Auto-fit Monja screenshot.
# Final proportion pass screenshot.

func _init() -> void:
	call_deferred("_capture")

func _capture() -> void:
	var orientation_setting: int = int(ProjectSettings.get_setting("display/window/handheld/orientation", -1))
	if orientation_setting != 4:
		push_error("SCREENSHOT: landscape sensor lock missing")
		quit(7)
		return
	print("XZOGOT_SCREENSHOT_LANDSCAPE_LOCK_GREEN")

	var packed: PackedScene = load("res://main.tscn") as PackedScene
	if packed == null:
		push_error("SCREENSHOT: main scene missing")
		quit(2)
		return

	var scene: Node = packed.instantiate()
	root.add_child(scene)

	var player: Node3D = scene.get_node_or_null("Player") as Node3D
	if player != null:
		player.global_position = Vector3(3.4, 0.38, 6.2)
		player.rotation.y = deg_to_rad(7.2)
		player.set_meta("ads_toggled", false)

	var weapon: Node = scene.get_node_or_null("Player/Weapon")
	if weapon != null and weapon.has_method("equip_weapon"):
		if not bool(weapon.call("equip_weapon", "mp40", true)):
			push_error("SCREENSHOT: MP40 real-viewmodel equip failed")
			quit(8)
			return
		print("XZOGOT_SCREENSHOT_REAL_MP40_READY")

	# The source MP40 equip action is 0.4667 s. CI rendering is uncapped,
	# so a frame count is not a valid time wait; use real simulation time.
	await create_timer(0.62).timeout
	for i in range(2):
		await process_frame

	if weapon != null:
		if weapon.has_method("get_first_person_debug_snapshot"):
			print("XZOGOT_FIRST_PERSON_CAMERA_SNAPSHOT_HIP ", weapon.call("get_first_person_debug_snapshot"))
		var yaw_fix := float(weapon.get_meta("weapon_model_yaw_correction_deg", 0.0))
		if absf(yaw_fix - 90.0) > 0.01:
			push_error("SCREENSHOT: weapon forward-axis correction missing")
			quit(11)
			return
		if not bool(weapon.get_meta("weapon_source_hip_pose_ready", false)):
			push_error("SCREENSHOT: MP40 source-authored HIP pose missing")
			quit(13)
			return
		if str(weapon.get_meta("weapon_source_idle_psa", "")) != "HandIdleMP40.psa":
			push_error("SCREENSHOT: MP40 source PSA provenance mismatch")
			quit(16)
			return
		if absf(float(weapon.get_meta("weapon_viewmodel_scale_factor", 0.0)) - 1.0) > 0.0001:
			push_error("SCREENSHOT: heuristic viewmodel scale detected")
			quit(17)
			return
		if not bool(weapon.get_meta("weapon_texture_ready", false)):
			push_error(
				"SCREENSHOT: weapon texture binding incomplete "
				+ str(weapon.get_meta("weapon_resolved_surfaces", 0))
				+ "/"
				+ str(weapon.get_meta("weapon_texture_surfaces", 0))
			)
			quit(12)
			return
		print(
			"XZOGOT_SCREENSHOT_SOURCE_HIP_GREEN yaw=", yaw_fix,
			" psa=", weapon.get_meta("weapon_source_idle_psa", ""),
			" pos=", weapon.get_meta("weapon_source_hip_position", Vector3.ZERO),
			" materials=", weapon.get_meta("weapon_resolved_surfaces", 0),
			"/", weapon.get_meta("weapon_texture_surfaces", 0)
		)

	var round_manager: Node = scene.get_node_or_null("RoundManager")
	if round_manager != null:
		round_manager.set("auto_start", false)
		round_manager.call("start_next_round")
		var zombie: Node3D = round_manager.call("spawn_one") as Node3D
		if zombie != null:
			zombie.set("phase", 2)
			zombie.global_position = Vector3(0.35, 0.35, 1.75)
			if player != null:
				zombie.look_at(player.global_position, Vector3.UP)
			if zombie.has_method("_play_motion_state"):
				zombie.call("_play_motion_state", "walk")
			if str(zombie.get_meta("zombie_model", "")) != "waw_honorgd":
				push_error("SCREENSHOT: WaW source zombie baseline not selected")
				quit(9)
				return
			if not bool(zombie.get_meta("zombie_source_waw", false)):
				push_error("SCREENSHOT: WaW source authority metadata missing")
				quit(23)
				return
			print("XZOGOT_SCREENSHOT_WAW_SOURCE_ZOMBIE_READY")
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

	print("XZOGOT_SCREENSHOT_SIDE_COMPOSITION_READY")

	for i in range(12):
		await process_frame

	var image: Image = root.get_texture().get_image()
	if image == null or image.is_empty():
		push_error("SCREENSHOT: viewport capture empty")
		quit(3)
		return

	if image.get_width() <= image.get_height():
		push_error("SCREENSHOT: capture is not landscape")
		quit(10)
		return
	print("XZOGOT_SCREENSHOT_LANDSCAPE_FRAME_GREEN ", image.get_width(), "x", image.get_height())

	var path := "/tmp/xogot-current-game.png"
	var err: Error = image.save_png(path)
	if err != OK:
		push_error("SCREENSHOT: save_png failed %s" % err)
		quit(4)
		return
	print("XZOGOT_SCREENSHOT_HIP_GREEN ", path, " ", image.get_width(), "x", image.get_height())
	print("XZOGOT_SCREENSHOT_GREEN ", path, " ", image.get_width(), "x", image.get_height())

	# Independent source-authored ADS acceptance frame. DT_Weapons row 5 is now
	# authoritative for MP40 HandTransform / ADSTransform and 0.20 s transitions.
	if player != null and weapon != null:
		if str(weapon.call("get_ads_calibration_mode")) != "source_datatable":
			push_error("SCREENSHOT: MP40 is not using recovered DT_Weapons ADS")
			quit(18)
			return
		if not bool(weapon.get_meta("weapon_source_weapon_attachment_ready", false)):
			push_error("SCREENSHOT: MP40 tag_weapon attachment missing")
			quit(19)
			return
		if not bool(weapon.get_meta("weapon_hands_animation_ready", false)):
			push_error("SCREENSHOT: MP40 source hands animation missing")
			quit(20)
			return
		var hands_report_path := "res://assets/weapons/aether_waw_hands/legacy_richtofen/animation-report.json"
		var hands_report_file := FileAccess.open(hands_report_path, FileAccess.READ)
		if hands_report_file == null:
			push_error("SCREENSHOT: MP40 source hands animation report unreadable")
			quit(23)
			return
		var hands_report_value: Variant = JSON.parse_string(hands_report_file.get_as_text())
		if not (hands_report_value is Dictionary):
			push_error("SCREENSHOT: MP40 source hands animation report invalid")
			quit(24)
			return
		var hands_report: Dictionary = hands_report_value
		if absf(float(hands_report.get("translation_scale", 0.0)) - 0.01) > 0.000001:
			push_error("SCREENSHOT: MP40 hand PSA translation units are not cm->m")
			quit(25)
			return
		print("XZOGOT_SCREENSHOT_HAND_UNITS_GREEN scale=0.01")
		player.set_meta("ads_toggled", true)
		# Recovered DT_Weapons ADS in/out time is 0.20 s; wait beyond the
		# authored transition so the screenshot captures settled ADS.
		await create_timer(0.28).timeout
		for i in range(2):
			await process_frame
		if weapon.has_method("get_first_person_debug_snapshot"):
			print("XZOGOT_FIRST_PERSON_CAMERA_SNAPSHOT_ADS ", weapon.call("get_first_person_debug_snapshot"))
		var ads_image: Image = root.get_texture().get_image()
		if ads_image == null or ads_image.is_empty():
			push_error("SCREENSHOT: ADS viewport capture empty")
			quit(21)
			return
		var ads_path := "/tmp/xogot-current-ads.png"
		var ads_err: Error = ads_image.save_png(ads_path)
		if ads_err != OK:
			push_error("SCREENSHOT: ADS save_png failed %s" % ads_err)
			quit(22)
			return
		print(
			"XZOGOT_SCREENSHOT_ADS_GREEN ", ads_path, " ",
			ads_image.get_width(), "x", ads_image.get_height(),
			" mode=", weapon.call("get_ads_calibration_mode"),
			" alpha=", weapon.get_meta("weapon_ads_pose_alpha", 0.0)
		)

	# Third independent view: exterior/front facade audit from the playable yard.
	if player != null:
		player.set_meta("ads_toggled", false)
		player.global_position = Vector3(0.0, 0.38, 27.0)
		player.rotation.y = 0.0
		for i in range(16):
			await process_frame

		var exterior_image: Image = root.get_texture().get_image()
		if exterior_image == null or exterior_image.is_empty():
			push_error("SCREENSHOT: exterior viewport capture empty")
			quit(5)
			return

		var exterior_path := "/tmp/xogot-current-exterior.png"
		var exterior_err: Error = exterior_image.save_png(exterior_path)
		if exterior_err != OK:
			push_error("SCREENSHOT: exterior save_png failed %s" % exterior_err)
			quit(6)
			return
		print("XZOGOT_EXTERIOR_SCREENSHOT_GREEN ", exterior_path, " ", exterior_image.get_width(), "x", exterior_image.get_height())

	quit(0)
