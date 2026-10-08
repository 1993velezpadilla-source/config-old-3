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
		var node := stack.pop_back()
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
		var hands_skeleton := _find_skeleton(hands) if hands != null else null
		var gun_skeleton := _find_skeleton(gun) if gun != null else null
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
		if delta_pos < 0.002 and delta_angle < 0.004:
			bad_ads.append(id)
		print("XZOGOT_SIGHT_AUDIT id=",id," mode=",mode,
			" hip_ads_translation_delta_m=",delta_pos,
			" rotation_delta_rad=",delta_angle,
			" gun_forward_cam=",gun_forward,
			" gun_up_cam=",gun_up,
			" muzzle_cam=",muzzle_cam,
			" mesh_local=",gun_geom.get("aabb",AABB()),
			" tags=",candidate_bones)
	print("XZOGOT_SIGHT_AUDIT_ADS_EQUALS_HIP ",bad_ads)
	print("XZOGOT_SIGHT_AUDIT_28_INSPECTED ",FIREARMS.size())
	scene.queue_free()
	await process_frame
	quit(0)
