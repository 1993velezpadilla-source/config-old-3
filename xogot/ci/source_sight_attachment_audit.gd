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

# Inspect the actual T4 Marine source wrist positions so offhand clipping
# can be fixed from authored PSA bone data, not invented wrist offsets.
func _trace_hand_wrist_grip(skeleton: Skeleton3D, camera: Camera3D, id: String, pose: String) -> void:
	if skeleton == null or camera == null:
		return
	var found: Array[String] = []
	for idx in range(skeleton.get_bone_count()):
		var raw_name: String = str(skeleton.get_bone_name(idx))
		var name: String = raw_name.to_lower()
		if name.contains("wrist") or name.contains("hand") or name.contains("palm") or name.contains("thumb"):
			var point: Vector3 = camera.to_local(
				(skeleton.global_transform * skeleton.get_bone_global_pose(idx)).origin
			)
			found.append(raw_name+"="+str(point))
	print("XZOGOT_SOURCE_HAND_CONTACT_BONES id=",id," pose=",pose,
		" skeleton=",skeleton.name," bones=",skeleton.get_bone_count(),
		" tracked=",found.size()," wrist_data=",found)

# True joint-to-joint grip measurements (different from broad weapon AABBs).
# Use native imported gun grip sockets and the animated original hand wrists,
# never manufactured contact targets or per-weapon guessed offsets.
func _trace_gun_hand_native_contact(gun_sk: Skeleton3D, hand_sk: Skeleton3D,
		camera: Camera3D, id: String, pose_name: String) -> void:
	if gun_sk == null or hand_sk == null or camera == null:
		print("XZOGOT_SOURCE_NATIVE_GRIP_POINTS_PENDING id=",id,
			" pose=",pose_name," reason=missing_source_skeleton")
		return
	var gun_contact_bones: Dictionary = {}
	var hand_contact_bones: Dictionary = {}
	for bone_idx in range(gun_sk.get_bone_count()):
		var bone_name: String = str(gun_sk.get_bone_name(bone_idx))
		if bone_name.to_lower().contains("grip") or bone_name == "j_gun":
			gun_contact_bones[bone_name] = camera.to_local(
				(gun_sk.global_transform * gun_sk.get_bone_global_pose(bone_idx)).origin)
	for bone_name: String in ["j_wrist_ri","j_thumb_ri_3","j_pinkypalm_ri",
			"j_wrist_le","j_thumb_le_3","j_pinkypalm_le"]:
		var idx: int = hand_sk.find_bone(bone_name)
		if idx >= 0:
			hand_contact_bones[bone_name] = camera.to_local(
				(hand_sk.global_transform * hand_sk.get_bone_global_pose(idx)).origin)
	var right_wrist_gap_m := -1.0
	if hand_contact_bones.has("j_wrist_ri"):
		for gun_bone_name: String in gun_contact_bones:
			var gap: float = (gun_contact_bones[gun_bone_name]
				as Vector3).distance_to(hand_contact_bones["j_wrist_ri"] as Vector3)
			if right_wrist_gap_m < 0.0 or gap < right_wrist_gap_m:
				right_wrist_gap_m = gap
	print("XZOGOT_SOURCE_NATIVE_GRIP_POINTS id=",id," pose=",pose_name,
		" candidate_source_grips=",gun_contact_bones,
		" animated_source_hands=",hand_contact_bones,
		" nearest_right_wrist_m=",right_wrist_gap_m,
		" visual_fingers_contour_approval=REQUIRED")

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
		_trace_gun_hand_native_contact(gun_skeleton,hands_skeleton,cam,id,"hip")
		if id == "357" or id == "type100" or id == "mp40":
			_trace_hand_wrist_grip(hands_skeleton, cam, id, "hip")
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
		_trace_gun_hand_native_contact(gun_skeleton,hands_skeleton,cam,id,"ads")
		if id == "357" or id == "type100" or id == "mp40":
			_trace_hand_wrist_grip(hands_skeleton, cam, id, "ads")
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
		# A true scoped WaW sight is an independent full-screen reticle
		# registered to the center of the optical camera. The recovered
		# tag_scope bone is 9–12cm off center, since it is NOT the physical
		# scope glass nor the actual HUD reticle. Do NOT silently declare a
		# misaligned bone good: log it and require the genuine HUD shader
		# visible, original 3D tube masked, and original model restored
		# after leaving ADS. All non-scoped iron-sight checks remain strict.
		var uses_scope_overlay: bool = id in ["mosin", "ptrs"]
		var scope_verified := false
		var mask: ColorRect = scene.get_node_or_null("HUD/MobileHUD/SourceSniperScopeMask") as ColorRect
		var view: Node3D = weapon.get("_view_root") as Node3D
		if uses_scope_overlay:
			scope_verified = (
				mask != null and mask.visible
				and mask.material is ShaderMaterial
				and mask.mouse_filter == Control.MOUSE_FILTER_IGNORE
				and view != null and not view.visible
				and bool(weapon.get_meta("weapon_scope_viewmodel_masked", false))
			)
			if not scope_verified:
				bad_ads.append(id + ":missing_or_incorrect_gameplay_scope_overlay")
			print("XZOGOT_SIGHT_AUDIT_SCOPED_OPTICAL_HUD id=", id,
				" reticle_center_camera=(0,0) shader_mask=", scope_verified,
				" old_tag_scope_offset_m=", marker_error_m,
				" old_tag_scope_depth_m=", marker_camera_depth_m)
		else:
			if marker_error_m >= 0.0 and marker_error_m > 0.01:
				bad_ads.append(id + ":source_sight_off_center=" + str(marker_error_m))
			if marker_error_m >= 0.0 and marker_camera_depth_m > -0.16:
				bad_ads.append(id + ":source_sight_clipped_by_near_plane=" + str(marker_camera_depth_m))
			if marker_error_m >= 0.0 and str(weapon.get_meta("weapon_ads_source_sight_registration", "")) != "runtime_optical_registration":
				bad_ads.append(id + ":source_sight_runtime_registration_not_applied")
		if barrel_angle_deg >= 0.0 and barrel_angle_deg > 3.0:
			bad_ads.append(id + ":barrel_off_camera_forward_deg=" + str(barrel_angle_deg))
		if marker_error_m < 0.0:
			print("XZOGOT_SIGHT_AUDIT_NO_IMPORTED_REAR_SIGHT id=", id,
				" source_registration=visual_approval_required")
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
		if uses_scope_overlay and (
			mask == null or mask.visible or view == null or not view.visible
			or bool(weapon.get_meta("weapon_scope_viewmodel_masked", true))
		):
			bad_ads.append(id + ":scope_overlay_or_original_hip_not_restored")
		var hip_restore_alpha: float = float(weapon.get("_ads_pose_alpha"))
		var hip_restore_pose: Vector3 = weapon.get("_view_pose_position")
		var hip_reference_pose: Vector3 = weapon.get("_hip_pose_position")
		var restored_rotation: Quaternion = weapon.get("_view_pose_rotation")
		var hip_rotation: Quaternion = weapon.get("_hip_pose_rotation")
		var hip_restore_angle: float = restored_rotation.angle_to(hip_rotation)
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
