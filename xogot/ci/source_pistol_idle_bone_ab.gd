extends SceneTree

# Diagnostic only. Never changes DT_Weapons, original PSA, source GLB or
# shipping weapon placement. A/B isolates the +90-degree X roll that was
# generalized from MP40 to all 28 guns without a pistol sight proof.
const STUB_PLAYER = preload("res://ci/ads_dummy_player.gd")
const Weapon = preload("res://scripts/weapon.gd")
const Registry = preload("res://scripts/weapon_asset_registry.gd")
const OUT := "/tmp/xogot-pistol-native-ab"
const IDS: Array[String] = ["colt", "walther", "nambu", "tt33", "357"]
const ROLLS: Array[float] = [180.0]

func _init() -> void:
	call_deferred("_run")

func _fail(message: String) -> void:
	push_error("XZOGOT_PISTOL_ROLL_AB_RED " + message)
	quit(2)

func _save_frame(name: String) -> bool:
	await process_frame
	await process_frame
	var img: Image = root.get_texture().get_image()
	if img == null or img.is_empty():
		push_error("XZOGOT_PISTOL_ROLL_FRAME_MISSING " + name)
		return false
	if img.save_png(OUT + "/" + name + ".png") != OK:
		push_error("XZOGOT_PISTOL_ROLL_FRAME_SAVE_RED " + name)
		return false
	return true

func _original_skeleton(root: Node) -> Skeleton3D:
	if root is Skeleton3D:
		return root as Skeleton3D
	for child: Node in root.get_children():
		var found := _original_skeleton(child)
		if found != null:
			return found
	return null

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
	for id: String in IDS:
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
				print("XZOGOT_ROLL_AB_SAMPLE id=", id, " ads=", ads,
					" model_roll_deg=", roll, " bore_camera=", bore,
					" off_camera_forward_deg=", off_forward,
					" original_socket_up_camera=", socket_up,
					" source_idle_psa=", real_idle,
					" model_local_scale=", gun.scale)
				if not await _save_frame(frame_name):
					_fail("PNG capture missing: " + frame_name)
					return
				frames += 1
				if ads:
					var native := _original_skeleton(gun)
					if native == null:
						_fail("no original skinned skeleton " + id)
						return
					weapon.set_process(false)
					animator.play(real_idle,0.0)
					animator.seek(0.0,true)
					animator.pause()
					for bone_name: String in ["j_clip","joint1","joint2","j_bolt"]:
						var bone_idx := native.find_bone(bone_name)
						if bone_idx < 0:
							continue
						var pose := native.get_bone_pose(bone_idx)
						var rest := native.get_bone_rest(bone_idx)
						print("XZOGOT_NATIVE_PISTOL_BONE id=",id," bone=",bone_name,
							" idle_pose=",pose," rest=",rest,
							" different=",not pose.is_equal_approx(rest))
						native.reset_bone_pose(bone_idx)
						if not await _save_frame(id + "-ads-rest-" + bone_name):
							_fail("unable to capture " + id + " " + bone_name)
							return
						frames += 1
						native.set_bone_pose(bone_idx,pose)
					weapon.set_process(true)
		player.set_meta("ads_toggled", false)
	if frames < 20:
		_fail("expected at least 20 genuine captures got " + str(frames))
		return
	print("XZOGOT_NATIVE_IDLE_AB_FRAMES count=", frames,
		" six_guns=true five_original_pistols=true source_skeleton_unchanged=true",
		" original_HIP_ADS_table_unchanged=true")
	quit(0)
