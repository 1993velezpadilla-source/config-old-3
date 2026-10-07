extends SceneTree

const MobileLayout = preload("res://scripts/mobile_layout.gd")

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
	var weapon: Node = player.get_node_or_null("Weapon")
	if weapon == null:
		push_error("MOVEMENT_PROBE: Weapon missing")
		quit(26)
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

	var camera: Camera3D = player.get_node_or_null("Head/Camera3D") as Camera3D
	if camera == null:
		push_error("MOVEMENT_PROBE: camera missing")
		quit(13)
		return
	if absf(capsule.radius - 0.36) > 0.01:
		push_error("MOVEMENT_PROBE: player radius wrong: %s" % capsule.radius)
		quit(14)
		return
	if absf(head.position.y - 1.60) > 0.02:
		push_error("MOVEMENT_PROBE: audited eye height wrong: %s" % head.position.y)
		quit(15)
		return
	if absf(camera.fov - 66.0) > 0.1:
		push_error("MOVEMENT_PROBE: base FOV wrong: %s" % camera.fov)
		quit(16)
		return
	if absf(float(player.get("ads_touch_multiplier")) - 0.62) > 0.001:
		push_error("MOVEMENT_PROBE: ADS touch multiplier wrong")
		quit(17)
		return
	if absf(float(player.get("gyro_ads_multiplier")) - 0.65) > 0.001:
		push_error("MOVEMENT_PROBE: gyro ADS multiplier wrong")
		quit(18)
		return
	if absf(float(player.get("mobile_sprint_zone")) - 1.10) > 0.001:
		push_error("MOVEMENT_PROBE: mobile sprint zone wrong")
		quit(24)
		return
	# ADS movement is no longer a player-global guess. It is authored per
	# weapon in DT_Weapons. Prove both a no-penalty pistol and a 50% SMG row.
	if not bool(weapon.call("equip_weapon", "colt", true)):
		push_error("MOVEMENT_PROBE: could not equip Colt for source ADS movement")
		quit(25)
		return
	if absf(float(weapon.call("get_source_ads_move_multiplier")) - 1.0) > 0.001:
		push_error("MOVEMENT_PROBE: Colt source ADS move multiplier wrong")
		quit(25)
		return
	if not bool(weapon.call("equip_weapon", "mp40", true)):
		push_error("MOVEMENT_PROBE: could not equip MP40 for source ADS movement")
		quit(25)
		return
	if absf(float(weapon.call("get_source_ads_move_multiplier")) - 0.50) > 0.001:
		push_error("MOVEMENT_PROBE: MP40 source ADS move multiplier wrong")
		quit(25)
		return
	weapon.call("equip_weapon", "colt", true)
	print("XZOGOT_MOVEMENT_SOURCE_ADS_SPEED_GREEN colt=1.0 mp40=0.5")
	if absf(float(player.get("camera_stance_response")) - 18.0) > 0.01:
		push_error("MOVEMENT_PROBE: stance camera response wrong")
		quit(19)
		return
	if absf(float(player.get("landing_spring_frequency")) - 17.0) > 0.01:
		push_error("MOVEMENT_PROBE: landing spring frequency wrong")
		quit(20)
		return

	if MobileLayout.FIRE_CENTER.distance_to(Vector2(0.885, 0.585)) > 0.001:
		push_error("MOVEMENT_PROBE: canonical fire HUD position wrong")
		quit(22)
		return
	if MobileLayout.JOY_CENTER.distance_to(Vector2(0.170, 0.740)) > 0.001:
		push_error("MOVEMENT_PROBE: canonical joystick HUD position wrong")
		quit(23)
		return

	# Hold a synthetic crouch touch through a physics frame.
	player.set("_crouch_touch", 77)
	await physics_frame
	if absf(capsule.height - 1.16) > 0.02:
		push_error("MOVEMENT_PROBE: crouch capsule height wrong: %s" % capsule.height)
		quit(6)
		return
	if absf(collider.position.y - 0.58) > 0.02:
		push_error("MOVEMENT_PROBE: crouch collider position wrong: %s" % collider.position.y)
		quit(7)
		return

	# Release and make sure standing geometry returns.
	player.set("_crouch_touch", -1)
	await physics_frame
	if absf(capsule.height - 1.76) > 0.02:
		push_error("MOVEMENT_PROBE: stand capsule height wrong: %s" % capsule.height)
		quit(8)
		return
	if absf(collider.position.y - 0.88) > 0.02:
		push_error("MOVEMENT_PROBE: stand collider position wrong: %s" % collider.position.y)
		quit(9)
		return

	# Synthetic full-stick + crouch edge should start one slide.
	player.set("_move_touch", 88)
	player.set("_move_raw_vector", Vector2(0.0, -1.20))
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

	print("XZOGOT_COD_VIEW_PROBE_GREEN")
	print("XZOGOT_MOVEMENT_PROBE_GREEN")
	scene.queue_free()
	await process_frame
	quit(0)
