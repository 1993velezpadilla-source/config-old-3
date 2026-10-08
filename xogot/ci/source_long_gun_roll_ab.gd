extends SceneTree

# Diagnostic only. Retain source DT_Weapons, original PSA, GLB and shipped
# viewmodel. A/B tests 4 roll poses after real socket and global-unit scaling
# revealed severely misaligned long-gun ADS in genuine Godot screenshots.
const STUB_PLAYER = preload("res://ci/ads_dummy_player.gd")
const Weapon = preload("res://scripts/weapon.gd")
const Registry = preload("res://scripts/weapon_asset_registry.gd")
const OUT := "/tmp/xogot-long-guns-roll-ab"
const IDS: Array[String] = ["arisaka", "fg42", "gewehr", "svt40", "m1", "type99", "stg", "browning"]
const ROLLS: Array[float] = [90.0, 0.0, -90.0, 180.0]
# CI shards: exactly four weapons each; do not exhaust one job's render budget.

func _init() -> void:
	call_deferred("_run")

func _fail(message: String) -> void:
	push_error("XZOGOT_LONG_GUN_ROLL_AB_RED " + message)
	quit(2)

func _save_frame(name: String) -> bool:
	await process_frame
	await process_frame
	var img: Image = root.get_texture().get_image()
	if img == null or img.is_empty():
		push_error("XZOGOT_LONG_GUN_ROLL_FRAME_MISSING " + name)
		return false
	if img.save_png(OUT + "/" + name + ".png") != OK:
		push_error("XZOGOT_LONG_GUN_ROLL_FRAME_SAVE_RED " + name)
		return false
	return true

func _run() -> void:
	DirAccess.make_dir_recursive_absolute(OUT)
	var scene := Node3D.new()
	root.add_child(scene)
	var environment := WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color(0.08, 0.09, 0.11)
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_energy = 0.8
	scene.add_child(environment)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-32.0, 20.0, 0.0)
	light.light_energy = 1.25
	scene.add_child(light)
	var player := CharacterBody3D.new()
	player.name = "Player"
	player.set_script(STUB_PLAYER)
	scene.add_child(player)
	var head := Node3D.new()
	head.name = "Head"
	player.add_child(head)
	var camera := Camera3D.new()
	camera.name = "Camera3D"
	camera.current = true
	camera.fov = 66
	camera.near = 0.025
	head.add_child(camera)
	var weapon := Node.new()
	weapon.name = "Weapon"
	weapon.set_script(Weapon)
	player.add_child(weapon)
	await process_frame
	var frames := 0
	var begin_idx: int = clampi(int(OS.get_environment("XOGOT_LONG_START").to_int()), 0, IDS.size())
	var end_idx: int = clampi(int(OS.get_environment("XOGOT_LONG_END").to_int()), begin_idx, IDS.size())
	if OS.get_environment("XOGOT_LONG_END").is_empty():
		end_idx = IDS.size()
	for idx in range(begin_idx, end_idx):
		var id: String = IDS[idx]
		player.set_meta("ads_toggled", false)
		if not bool(weapon.call("equip_weapon", id, true)):
			_fail("equip failed: " + id)
			return
		await create_timer(0.65).timeout
		var gun := weapon.get("_weapon_model_root") as Node3D
		var socket := weapon.get("_source_weapon_attachment") as Node3D
		if gun == null or socket == null or gun.get_parent() != socket:
			_fail("original animated socket unavailable: " + id)
			return
		var real_idle: String = Registry.animation_name_for_role(id, "idle")
		var animator := weapon.get("_asset_animation_player") as AnimationPlayer
		if animator == null or not animator.has_animation(real_idle):
			_fail("exact gun PSA idle unavailable: " + id + " / " + real_idle)
			return
		for ads: bool in [false, true]:
			player.set_meta("ads_toggled", ads)
			await create_timer(0.5).timeout
			weapon.call("_update_visual_recoil", 0.7)
			for roll: float in ROLLS:
				# Only vary gun roll, retaining original animated hand grip,
				# source datatable ADS, original gun animation and source socket.
				gun.quaternion = Quaternion(Vector3.RIGHT, deg_to_rad(roll))
				await process_frame
				var bore: Vector3 = (
					camera.global_transform.basis.inverse() *
					gun.global_transform.basis.orthonormalized().x
				).normalized()
				var off_forward: float = rad_to_deg(
					acos(clampf(bore.dot(Vector3.FORWARD), -1.0, 1.0)))
				var socket_up: Vector3 = (
					camera.global_transform.basis.inverse() *
					socket.global_transform.basis.orthonormalized().y
				).normalized()
				var frame_name := "%s-%s-roll-%d" % [
					id, "ads" if ads else "hip", int(roll)]
				print("XZOGOT_LONG_ROLL_AB_SAMPLE id=", id, " ads=", ads,
					" model_roll_deg=", roll, " bore_camera=", bore,
					" off_camera_forward_deg=", off_forward,
					" original_socket_up_camera=", socket_up,
					" source_idle_psa=", real_idle,
					" model_local_scale=", gun.scale)
				if not await _save_frame(frame_name):
					_fail("PNG capture missing: " + frame_name)
					return
				frames += 1
		player.set_meta("ads_toggled", false)
	var expected_frames: int = (end_idx - begin_idx) * 2 * ROLLS.size()
	if frames != expected_frames:
		_fail("expected " + str(expected_frames) + " genuine captures got " + str(frames))
		return
	print("XZOGOT_LONG_ROLL_SOURCE_DIAGNOSTIC_CAPTURED count=", frames,
		" shard=",begin_idx,"-",end_idx," source_skeleton_unchanged=true",
		" original_HIP_ADS_table_unchanged=true")
	quit(0)
