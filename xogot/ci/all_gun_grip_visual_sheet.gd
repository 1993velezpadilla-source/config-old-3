extends SceneTree

# Real Godot, 28-weapon x (HIP, ADS) capture. This is visual evidence; the
# source transform/PSA and hand grip must not be "approved" by logs alone.
const FIREARMS: Array[String] = [
	"colt", "walther", "nambu", "tt33", "357", "mp40", "thompson",
	"ppsh", "type100", "stg", "m1", "m1a1", "gewehr", "svt40",
	"arisaka", "kar98k", "springfield", "mosin", "ptrs", "trench",
	"doublebarrel", "sawnoff", "bar", "fg42", "mg42", "browning",
	"dp28", "type99"
]
const FRAME_DIRECTORY := "/tmp/xogot-all-guns"

func _init() -> void:
	call_deferred("_capture")

func _fail(code: int, message: String) -> void:
	push_error("ALL_GUN_GRIP_VISUAL_RED " + message)
	quit(code)

# Measure genuine animated source wrists against imported gun camera AABB.
# Diagnostic only: bounds include receiver/barrel, not actual grip contours,
# so visual approval still requires the authentic HIP/ADS screenshot review.
func _source_wrist_distances(weapon: Node, gun_aabb: AABB) -> Dictionary:
	var skel: Skeleton3D = weapon.get("_source_hands_skeleton") as Skeleton3D
	var camera: Camera3D = weapon.get("_camera") as Camera3D
	if skel == null or camera == null:
		return {"available": false}
	var distances: Dictionary = {"available": true}
	for bone_name: String in ["j_wrist_le", "j_wrist_ri", "j_thumb_le_3", "j_thumb_ri_3"]:
		var idx: int = skel.find_bone(bone_name)
		if idx < 0:
			distances[bone_name] = -1.0
			continue
		var point: Vector3 = camera.to_local(
			(skel.global_transform * skel.get_bone_global_pose(idx)).origin
		)
		var nearest: Vector3 = Vector3(
			clampf(point.x, gun_aabb.position.x, gun_aabb.end.x),
			clampf(point.y, gun_aabb.position.y, gun_aabb.end.y),
			clampf(point.z, gun_aabb.position.z, gun_aabb.end.z)
		)
		distances[bone_name] = snappedf(point.distance_to(nearest), 0.0001)
	return distances

func _capture() -> void:
	DirAccess.make_dir_recursive_absolute(FRAME_DIRECTORY)
	var packed := load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(2, "main scene unavailable")
		return
	var scene := packed.instantiate()
	root.add_child(scene)
	var player := scene.get_node_or_null("Player") as Node3D
	var weapon: Node = scene.get_node_or_null("Player/Weapon")
	if player == null or weapon == null:
		_fail(3, "player or weapon runtime unavailable")
		return
	player.global_position = Vector3(3.4, 0.38, 6.2)
	player.rotation.y = deg_to_rad(7.2)
	# Run in two parallel CI shards: 14 weapons each so all 56 original
	# Godot screenshots can finish without a single 11-minute GPU timeout.
	var first_index: int = clampi(int(OS.get_environment("XOGOT_GRIP_START").to_int()), 0, 28)
	var last_index: int = clampi(int(OS.get_environment("XOGOT_GRIP_END").to_int()), first_index, 28)
	if OS.get_environment("XOGOT_GRIP_END").is_empty():
		last_index = FIREARMS.size()
	var expected_frames: int = (last_index - first_index) * 2
	var images_saved := 0
	var failures: Array[String] = []
	for weapon_idx in range(first_index, last_index):
		var weapon_id: String = FIREARMS[weapon_idx]
		player.set_meta("ads_toggled", false)
		if not bool(weapon.call("equip_weapon", weapon_id, true)):
			failures.append(weapon_id + ":equip")
			continue
		# Source equip / animated-socket state must have settled before capture.
		await create_timer(0.80).timeout
		for pose: String in ["hip", "ads"]:
			player.set_meta("ads_toggled", pose == "ads")
			await create_timer(0.68).timeout
			await process_frame
			var report: Dictionary = weapon.call("get_first_person_debug_snapshot")
			var gun: Dictionary = report.get("weapon", {}) as Dictionary
			var size: Vector3 = gun.get("size", Vector3.ZERO)
			# A correct mesh dimension or source ADS timing says nothing about
			# actual fingers touching a correct pistol grip. Require exact
			# tag_weapon (never tag_weapon_end/tag_weapon1) and log native joints.
			var bound_bone: String = str(weapon.get_meta("weapon_source_attachment_bone_name", ""))
			if bound_bone != "tag_weapon":
				failures.append(weapon_id + ":" + pose + ":wrong_grip_socket=" + bound_bone)
			var camera_bounds := AABB(
				gun.get("position", Vector3.ZERO),
				gun.get("size", Vector3.ZERO)
			)
			var hand_contact: Dictionary = _source_wrist_distances(weapon, camera_bounds)
			print("XZOGOT_28_HAND_GRIP_CONTACT id=", weapon_id,
				" pose=", pose, " source_bone=", bound_bone,
				" actual_wrist_thumb_to_gun_bounds_m=", hand_contact)
			var largest: float = maxf(size.x, maxf(size.y, size.z))
			var roll: float = float(weapon.get_meta("weapon_source_gun_roll_correction_deg", -1.0))
			var centered_source_ads: bool = weapon_id == "mp40" and pose == "ads"
			if not bool(gun.get("found", false)) or largest < 0.15 or largest > 2.5:
				failures.append(weapon_id + ":" + pose + ":bounds=" + str(largest))
			var source_pistol: bool = weapon_id in ["colt", "walther", "nambu", "tt33", "357"]
			# See independent original HIP+ADS 4-way rotation matrix #37857367033.
			var confirmed_upright_long: bool = weapon_id in ["stg", "browning", "type99"]
			var expected_roll := 180.0 if source_pistol or confirmed_upright_long else 90.0
			if absf(roll - expected_roll) > 0.01:
				failures.append(weapon_id + ":" + pose + ":roll=" + str(roll) + " expected=" + str(expected_roll))
			var frame: Image = root.get_texture().get_image()
			if frame == null or frame.is_empty():
				failures.append(weapon_id + ":" + pose + ":empty_image")
				continue
			var path := FRAME_DIRECTORY + "/" + weapon_id + "-" + pose + ".png"
			if frame.save_png(path) != OK:
				failures.append(weapon_id + ":" + pose + ":png_save")
				continue
			images_saved += 1
			print("XZOGOT_ALL_GUN_GRIP_IMAGE ", weapon_id, " ", pose,
				" longest_m=", largest, " roll_deg=", roll,
				" source_ads=", centered_source_ads,
				" path=", path)
	player.set_meta("ads_toggled", false)
	print("XZOGOT_ALL_GUNS_VISUAL_CAPTURE_TOTAL ", images_saved, "/", expected_frames, " shard=",first_index,"-",last_index)
	if failures.size() > 0:
		print("XZOGOT_ALL_GUNS_VISUAL_FAILURES ", failures)
		scene.queue_free()
		await process_frame
		_fail(4, "visual suite found: " + str(failures))
		return
	if images_saved != expected_frames:
		scene.queue_free()
		await process_frame
		_fail(5, "expected " + str(expected_frames) + " actual images, got " + str(images_saved))
		return
	print("XZOGOT_ALL_GUNS_VISUAL_SHARD_GREEN count=", images_saved, " start=", first_index, " end=", last_index)
	scene.queue_free()
	await process_frame
	quit(0)
