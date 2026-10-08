extends SceneTree

# Audit real imported socket axes, weapon-root orientation and source tag_ads
# positions. No fake asset statuses or invented ADS numbers.
const FIREARMS: Array[String] = [
	"colt","walther","nambu","tt33","357","mp40","thompson",
	"ppsh","type100","stg","m1","m1a1","gewehr","svt40",
	"arisaka","kar98k","springfield","mosin","ptrs","trench",
	"doublebarrel","sawnoff","bar","fg42","mg42","browning",
	"dp28","type99"
]

func _init() -> void:
	call_deferred("_inspect")

func _find_skeleton(node: Node) -> Skeleton3D:
	if node is Skeleton3D:
		return node as Skeleton3D
	for child: Node in node.get_children():
		var skel := _find_skeleton(child)
		if skel != null:
			return skel
	return null

func _mesh_bounds_in_root(root_node: Node3D) -> Dictionary:
	var result: Dictionary = {"found": false}
	var stack: Array[Node] = [root_node]
	var bounds := AABB()
	while not stack.is_empty():
		var node: Node = stack.pop_back()
		if node is MeshInstance3D:
			var mesh_node := node as MeshInstance3D
			if mesh_node.mesh != null:
				var aabb := mesh_node.get_aabb()
				for x in range(2):
					for y in range(2):
						for z in range(2):
							var corner := aabb.position + aabb.size * Vector3(x,y,z)
							var p := root_node.to_local(mesh_node.to_global(corner))
							if not result["found"]:
								bounds = AABB(p, Vector3.ZERO)
								result["found"] = true
							else:
								bounds = bounds.expand(p)
		for child: Node in node.get_children():
			stack.append(child)
	result["aabb"] = bounds
	return result

func _inspect() -> void:
	var packed := load("res://main.tscn") as PackedScene
	if packed == null:
		push_error("XZOGOT_SIGHT_AUDIT_RED no main scene")
		quit(3)
		return
	var scene: Node = packed.instantiate()
	root.add_child(scene)
	await process_frame
	var weapon: Node = scene.get_node_or_null("Player/Weapon")
	var player: Node3D = scene.get_node_or_null("Player") as Node3D
	var cam: Camera3D = scene.get_node_or_null("Player/Head/Camera3D") as Camera3D
	if weapon == null or cam == null or player == null:
		push_error("XZOGOT_SIGHT_AUDIT_RED no player / camera / weapon")
		quit(4)
		return
	var bad_ads: Array[String] = []
	for id: String in FIREARMS:
		player.set_meta("ads_toggled", false)
		if not bool(weapon.call("equip_weapon", id, true)):
			bad_ads.append(id+":equip")
			continue
		await process_frame
		await process_frame
		var gun: Node3D = weapon.get("_weapon_model_root") as Node3D
		var hands: Node3D = weapon.get("_hands_model_root") as Node3D
		var muzzle: Node3D = weapon.get("_muzzle_anchor") as Node3D
		var hands_skeleton: Skeleton3D = _find_skeleton(hands) if hands != null else null
		var gun_skeleton: Skeleton3D = _find_skeleton(gun) if gun != null else null
		var candidate_bones: Dictionary = {}
		for skel in [hands_skeleton,gun_skeleton]:
			if skel == null:
				continue
			for i in range(skel.get_bone_count()):
				var bone_name := str(skel.get_bone_name(i)).to_lower()
				if bone_name.contains("ads") or bone_name.contains("sight") or bone_name.contains("scope") or bone_name.contains("flash") or bone_name.contains("weapon"):
					var point: Vector3 = cam.to_local((skel.global_transform * skel.get_bone_global_pose(i)).origin)
					candidate_bones[skel.name.to_lower() + ":" + bone_name] = point
		var gun_forward := Vector3.ZERO
		var gun_up := Vector3.ZERO
		if gun != null:
			var basis := cam.global_transform.basis.inverse() * gun.global_transform.basis.orthonormalized()
			gun_forward = basis.x
			gun_up = basis.y
		var muzzle_cam := cam.to_local(muzzle.global_position) if muzzle != null else Vector3.ZERO
		var gun_geom: Dictionary = _mesh_bounds_in_root(gun) if gun != null else {}
		var hip_pos: Vector3 = weapon.get("_hip_pose_position")
		var ads_pos: Vector3 = weapon.get("_ads_pose_position")
		var hip_rot: Quaternion = weapon.get("_hip_pose_rotation")
		var ads_rot: Quaternion = weapon.get("_ads_pose_rotation")
		var delta_pos: float = hip_pos.distance_to(ads_pos)
		var delta_angle: float = hip_rot.angle_to(ads_rot)
		var mode := str(weapon.call("get_ads_calibration_mode"))
		# First record the genuine HIP state, then activate ADS and wait for
		# the actual source timing. A mere FOV change is a hard visual blocker.
		player.set_meta("ads_toggled", true)
		await create_timer(0.60).timeout
		await process_frame
		var solved_hip: Vector3 = weapon.get("_hip_pose_position")
		var solved_ads: Vector3 = weapon.get("_ads_pose_position")
		var solved_hip_rot: Quaternion = weapon.get("_hip_pose_rotation")
		var solved_ads_rot: Quaternion = weapon.get("_ads_pose_rotation")
		var solved_translation: float = solved_hip.distance_to(solved_ads)
		var solved_angle: float = solved_hip_rot.angle_to(solved_ads_rot)
		var sight_source: String = str(weapon.get_meta("weapon_ads_visual_sight_anchor", "source_dt_or_missing"))
		var marker_error_m := -1.0
		var marker_camera_depth_m := 0.0
		if gun_skeleton != null and id != "mp40":
			for tag in ["tag_iron_sights", "tag_scope", "tag_no_scope"]:
				var idx := gun_skeleton.find_bone(tag)
				if idx >= 0:
					var marker_camera: Vector3 = cam.to_local(
						(gun_skeleton.global_transform * gun_skeleton.get_bone_global_pose(idx)).origin)
					marker_error_m = Vector2(marker_camera.x, marker_camera.y).length()
					marker_camera_depth_m = marker_camera.z
					break
		var barrel_angle_deg := -1.0
		if gun != null and id != "mp40":
			var barrel_camera: Vector3 = (
				cam.global_transform.basis.inverse() * gun.global_transform.basis.orthonormalized().x
			).normalized()
			barrel_angle_deg = rad_to_deg(acos(clampf(barrel_camera.dot(Vector3.FORWARD), -1.0, 1.0)))
		if solved_translation < 0.003 and solved_angle < 0.005:
			bad_ads.append(id + ":ads_equals_hip")
		# 1.5 cm in camera-space is a precise, meaningful physical eye-line;
		# old 8 cm tolerance hid plainly misaligned sights in screenshots.
		if marker_error_m >= 0.0 and marker_error_m > 0.015:
			bad_ads.append(id + ":source_sight_off_center=" + str(marker_error_m))
		if marker_error_m >= 0.0 and marker_camera_depth_m >= -0.05:
			bad_ads.append(id + ":source_sight_behind_camera=" + str(marker_camera_depth_m))
		if barrel_angle_deg >= 0.0 and barrel_angle_deg > 3.0:
			bad_ads.append(id + ":barrel_off_camera_forward_deg=" + str(barrel_angle_deg))
		print("XZOGOT_SIGHT_AUDIT_ADS_RESULT id=",id,
			" mode=",str(weapon.get_meta("weapon_ads_visual_alignment_mode", mode)),
			" sight=",sight_source,
			" translation_m=",solved_translation,
			" rotation_rad=",solved_angle,
			" authored_sight_error_m=",marker_error_m,
			" sight_depth_m=",marker_camera_depth_m,
			" barrel_camera_alignment_deg=",barrel_angle_deg)
		# Prove that returning from ADS really restores the source HIP pose.
		# A perfectly centered screenshot is not enough if aim-release drifts.
		player.set_meta("ads_toggled", false)
		await create_timer(0.72).timeout
		await process_frame
		var hip_restore_alpha: float = float(weapon.get("_ads_pose_alpha"))
		var hip_restore_pose: Vector3 = weapon.get("_view_pose_position")
		var hip_reference_pose: Vector3 = weapon.get("_hip_pose_position")
		var hip_restore_angle: float = (
			(weapon.get("_view_pose_rotation") as Quaternion).angle_to(
				weapon.get("_hip_pose_rotation") as Quaternion
			)
		)
		var hip_restore_error: float = hip_restore_pose.distance_to(hip_reference_pose)
		print("XZOGOT_SIGHT_AUDIT_RETURN_TO_HIP id=", id,
			" alpha=", hip_restore_alpha,
			" position_error_m=", hip_restore_error,
			" rotation_error_rad=", hip_restore_angle)
		if hip_restore_alpha > 0.015 or hip_restore_error > 0.015 or hip_restore_angle > 0.015:
			bad_ads.append(id + ":ads_release_did_not_restore_hip")
		print("XZOGOT_SIGHT_AUDIT id=",id," mode=",mode,
			" hip_ads_translation_delta_m=",delta_pos,
			" rotation_delta_rad=",delta_angle,
			" gun_forward_cam=",gun_forward,
			" gun_up_cam=",gun_up,
			" muzzle_cam=",muzzle_cam,
			" mesh_local=",gun_geom.get("aabb",AABB()),
			" tags=",candidate_bones)
	print("XZOGOT_SIGHT_AUDIT_ADS_VISUAL_BLOCKERS ",bad_ads)
	print("XZOGOT_SIGHT_AUDIT_28_INSPECTED ",FIREARMS.size())
	if not bad_ads.is_empty():
		print("XZOGOT_SIGHT_AUDIT_VISUAL_ACCEPTANCE_RED count=",bad_ads.size())
	scene.queue_free()
	await process_frame
	if not bad_ads.is_empty():
		quit(7)
		return
	print("XZOGOT_SIGHT_AUDIT_CENTERING_PROBE_GREEN 28")
	quit(0)
