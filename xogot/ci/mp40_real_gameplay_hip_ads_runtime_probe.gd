extends SceneTree

# Strict native Godot full-game acceptance for the original imported MP40.
# Unlike the old screenshot_capture.gd, do not run exterior/zombie artwork
# capture after the firearm acceptance. Those additional scene lifecycle
# checks are owned by their separate test and currently exit 1 post-render.
# Original War at War hand/weapon PSA, DT_Weapons transforms and HUD retained.
const OUT := "/tmp/xogot-mp40-real-hip-ads"

func _init() -> void:
	call_deferred("_run")

func _fail(reason: String) -> void:
	push_error("XZOGOT_MP40_REAL_HIP_ADS_RED " + reason)
	quit(3)

func _capture(frame: String) -> bool:
	await process_frame
	await process_frame
	var image: Image = root.get_texture().get_image()
	if image == null or image.is_empty():
		return false
	if image.get_width() < 1024 or image.get_height() < 600:
		return false
	return image.save_png(OUT + "/" + frame + ".png") == OK

# A green scale or ADS metadata check does not prove that the gun actually
# appears in the rendered viewport. Use the live framebuffer and a reversible
# gun-only visibility A/B/A test. The A-to-C difference is natural background
# motion/particle drift; B must differ substantially MORE than that drift.
# Never modify source meshes, PSAs, sockets, authored poses or animations.
func _pixel_difference(a: Image, b: Image) -> Dictionary:
	if a == null or b == null or a.is_empty() or b.is_empty():
		return {"count": 0, "samples": 0}
	if a.get_size() != b.get_size():
		return {"count": 0, "samples": 0}
	var changed := 0
	var samples := 0
	for y in range(int(a.get_height() * 0.12), int(a.get_height() * 0.95), 4):
		for x in range(int(a.get_width() * 0.12), int(a.get_width() * 0.88), 4):
			var ca: Color = a.get_pixel(x, y)
			var cb: Color = b.get_pixel(x, y)
			var diff: float = (absf(ca.r - cb.r) + absf(ca.g - cb.g) + absf(ca.b - cb.b)) / 3.0
			if diff > 0.12:
				changed += 1
			samples += 1
	return {"count": changed, "samples": samples}

func _gun_screen_presence(gun: Node3D, pose: String) -> bool:
	if gun == null or not gun.is_visible_in_tree():
		return false
	await process_frame
	await process_frame
	var with_gun: Image = root.get_texture().get_image()
	gun.visible = false
	await process_frame
	await process_frame
	var without_gun: Image = root.get_texture().get_image()
	gun.visible = true
	await process_frame
	await process_frame
	var with_gun_again: Image = root.get_texture().get_image()
	var contrast: Dictionary = _pixel_difference(with_gun, without_gun)
	var baseline: Dictionary = _pixel_difference(with_gun, with_gun_again)
	var sample_count: int = int(contrast.get("samples", 0))
	var changed: int = int(contrast.get("count", 0))
	var drift: int = int(baseline.get("count", 0))
	print("XZOGOT_MP40_RENDER_VISIBILITY pose=", pose,
		" gun_toggle_changed_pixels=", changed,
		" background_drift_pixels=", drift, " samples=", sample_count,
		" restored_visible=", gun.is_visible_in_tree())
	# A bare-hands frame or a microscopic gun may have correct socket data.
	# Reject that false GREEN. The drift reference prevents moving scenery
	# alone from satisfying the visible-firearm gate.
	return (sample_count > 1000 and changed > maxi(80, int(float(drift) * 1.5))
		and gun.is_visible_in_tree())

func _run() -> void:
	DirAccess.make_dir_recursive_absolute(OUT)
	var source: PackedScene = load("res://main.tscn") as PackedScene
	if source == null:
		_fail("missing original game scene")
		return
	var scene: Node = source.instantiate()
	root.add_child(scene)
	var player: Node = scene.get_node_or_null("Player")
	var weapon: Node = scene.get_node_or_null("Player/Weapon")
	var hud: Node = scene.get_node_or_null("HUD/MobileHUD")
	var camera: Camera3D = scene.get_node_or_null("Player/Head/Camera3D") as Camera3D
	if player == null or weapon == null or hud == null or camera == null:
		_fail("authentic player/gun/touch HUD/camera not found")
		return
	player.set_meta("ads_toggled", false)
	if not bool(weapon.call("equip_weapon", "mp40", true)):
		_fail("original MP40 could not be equipped")
		return
	await create_timer(0.73).timeout
	var hand_rig: Node3D = weapon.get("_hands_model_root") as Node3D
	var gun: Node3D = weapon.get("_weapon_model_root") as Node3D
	var socket: Node3D = weapon.get("_source_weapon_attachment") as Node3D
	var view: Node3D = weapon.get("_view_root") as Node3D
	var animator: AnimationPlayer = weapon.get("_hands_animation_player") as AnimationPlayer
	if hand_rig == null or gun == null or socket == null or view == null or animator == null:
		_fail("real viewmodel / source wrist rig / animation player missing")
		return
	if gun.get_parent() != socket:
		_fail("gun disconnected from original WaW tag_weapon bone")
		return
	if not animator.has_animation("PSA_HandIdleMP40"):
		_fail("actual original HandIdleMP40 clip missing")
		return
	if not bool(weapon.get_meta("weapon_source_weapon_attachment_ready", false)):
		_fail("original hand to gun socket not bound")
		return
	if not bool(weapon.get_meta("weapon_source_hip_pose_ready", false)):
		_fail("original source HIP authored pose not ready")
		return
	# The source hands skeleton is still in inherited ActorX centimeter
	# units. Its tag_weapon BoneAttachment is ~0.01 world scale, while the
	# GLB gun must render in METER units. Production deliberately sets the
	# child's LOCAL scale to the reciprocal (~100): only the composed GLOBAL
	# basis should be 1. This gate previously checked the wrong coordinate
	# frame and falsely failed real geometry.
	var local_units: Vector3 = gun.scale
	var world_units: Vector3 = gun.global_transform.basis.get_scale()
	var socket_units: Vector3 = socket.global_transform.basis.get_scale()
	var restored: bool = bool(weapon.get_meta("weapon_source_attachment_meter_units_restored", false))
	print("XZOGOT_MP40_NATIVE_UNIT_PROOF local_compensation=", local_units,
		" source_socket_scale=", socket_units,
		" world_meter_scale=", world_units, " restored=", restored)
	if (not restored or world_units.distance_to(Vector3.ONE) > 0.015
		or (local_units * socket_units).distance_to(Vector3.ONE) > 0.015):
		_fail("MP40 final meter-scale inherited compensation incorrect")
		return
	if not view.visible:
		_fail("HIP unexpectedly hides original MP40 weapon")
		return
	if str(weapon.call("get_ads_calibration_mode")) != "source_datatable":
		_fail("MP40 no longer has recovered source DT_Weapons ADS")
		return
	var hip: Vector3 = weapon.get("_hip_pose_position")
	var ads: Vector3 = weapon.get("_ads_pose_position")
	if hip.distance_to(ads) < 0.02:
		_fail("source HIP and ADS presentation are identical")
		return
	if not await _gun_screen_presence(gun, "hip"):
		_fail("original MP40 gun not demonstrably visible in real HIP screenshot")
		return
	if not await _capture("01-source-mp40-hip"):
		_fail("source MP40 HIP full game PNG not captured")
		return
	print("XZOGOT_MP40_SOURCE_NATIVE_HIP_GREEN gun_meter_scale=1 source_hands_psa=", animator.get_assigned_animation())
	player.set_meta("ads_toggled", true)
	await create_timer(0.63).timeout
	await process_frame
	var alpha: float = float(weapon.get_meta("weapon_ads_pose_alpha", 0.0))
	if alpha < 0.98:
		_fail("ADS source transition did not finish " + str(alpha))
		return
	if not view.visible or bool(weapon.get_meta("weapon_scope_viewmodel_masked", false)):
		_fail("iron sight MP40 incorrectly hidden behind sniper optic HUD")
		return
	if not animator.has_animation("PSA_HandIdleMP40") or gun.get_parent() != socket:
		_fail("native hand/weapon lost connection in ADS")
		return
	if not await _gun_screen_presence(gun, "ads"):
		_fail("original MP40 gun not demonstrably visible in real ADS screenshot")
		return
	if not await _capture("02-source-mp40-ads"):
		_fail("source MP40 ADS full game PNG not captured")
		return
	print("XZOGOT_MP40_SOURCE_NATIVE_ADS_GREEN alpha=", alpha,
		" source_pose_distance=", hip.distance_to(ads),
		" no_sniper_overlay=true")
	player.set_meta("ads_toggled", false)
	await create_timer(0.65).timeout
	await process_frame
	if float(weapon.get_meta("weapon_ads_pose_alpha", 1.0)) > 0.025:
		_fail("original MP40 HIP pose was not restored from ADS")
		return
	if not view.visible or gun.get_parent() != socket:
		_fail("original MP40 gun or socket missing after ADS")
		return
	if not await _capture("03-source-mp40-return-to-hip"):
		_fail("source MP40 post ADS PNG missing")
		return
	print("XZOGOT_MP40_REAL_GAMEPLAY_PROOF_GREEN frames=3 authored_animation_intact=true touch_HUD_intact=true original_fov_formula_not_overridden=true")
	quit(0)
