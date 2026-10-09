extends SceneTree

const STUB_PLAYER = preload("res://ci/ads_dummy_player.gd")
const SOURCE_WEAPON = preload("res://scripts/weapon.gd")
const FIREARMS: Array[String] = [
	"colt","walther","nambu","tt33","357","mp40","thompson",
	"ppsh","type100","stg","m1","m1a1","gewehr","svt40",
	"arisaka","kar98k","springfield","mosin","ptrs","trench",
	"doublebarrel","sawnoff","bar","fg42","mg42","browning",
	"dp28","type99"
]
const OUT := "/tmp/xogot-isolated-sight-proof"

func _init() -> void:
	call_deferred("_start")

func _fail(message: String) -> void:
	push_error("XZOGOT_ISOLATED_SIGHTS_RED " + message)
	quit(6)

# Framebuffer guard derived from captured genuine Godot render pixels.
# A "saved 56 PNGs" pass MUST NOT greenlight weapons that fill the upper
# view or right edge with huge near-plane hands/receivers. The thresholds
# are universal image-space quality gates, not fabricated weapon poses.
func _ads_frame_obstruction(frame: Image) -> Dictionary:
	var backdrop: Color = frame.get_pixel(8, 8)
	var upper_samples := 0
	var upper_foreground := 0
	var right_samples := 0
	var right_foreground := 0
	var upper_edge: int = int(frame.get_height() * 0.25)
	var right_edge: int = int(frame.get_width() * 0.75)
	for y in range(0, frame.get_height(), 10):
		for x in range(0, frame.get_width(), 10):
			if y >= upper_edge and x < right_edge:
				continue
			var pix: Color = frame.get_pixel(x, y)
			var delta: float = maxf(absf(pix.r - backdrop.r),
				maxf(absf(pix.g - backdrop.g), absf(pix.b - backdrop.b)))
			var foreground: bool = delta > 0.10
			if y < upper_edge:
				upper_samples += 1
				if foreground:
					upper_foreground += 1
			if x >= right_edge:
				right_samples += 1
				if foreground:
					right_foreground += 1
	return {
		"upper_fraction": float(upper_foreground) / maxf(float(upper_samples), 1.0),
		"right_fraction": float(right_foreground) / maxf(float(right_samples), 1.0)
	}

# Reversible rendering A/B: distinguish obstruction from the imported hand
# mesh versus the real source firearm. CI-only; never alter source assets.
func _diagnose_occluding_parts(weapon: Node, id: String) -> void:
	var firearm: Node3D = weapon.get("_weapon_model_root") as Node3D
	var hands: Node3D = weapon.get("_hands_model_root") as Node3D
	if firearm == null or hands == null:
		return
	var diagnostic_dir := "/tmp/xogot-sight-component-ab"
	DirAccess.make_dir_recursive_absolute(diagnostic_dir)
	firearm.visible = false
	await process_frame
	await process_frame
	var hands_frame := root.get_texture().get_image()
	if hands_frame != null and not hands_frame.is_empty():
		hands_frame.save_png(diagnostic_dir + "/" + id + "-hands-only.png")
		print("XZOGOT_ADS_AB_HANDS_ONLY ",id," ",_ads_frame_obstruction(hands_frame))
	firearm.visible = true
	var hidden: Array[MeshInstance3D] = []
	for child: Node in hands.find_children("*", "MeshInstance3D", true, false):
		if child is MeshInstance3D and not firearm.is_ancestor_of(child):
			var node := child as MeshInstance3D
			if node.visible:
				hidden.append(node)
				node.visible = false
	await process_frame
	await process_frame
	var firearm_frame := root.get_texture().get_image()
	if firearm_frame != null and not firearm_frame.is_empty():
		firearm_frame.save_png(diagnostic_dir + "/" + id + "-firearm-only.png")
		print("XZOGOT_ADS_AB_FIREARM_ONLY ",id," ",_ads_frame_obstruction(firearm_frame))
	for node: MeshInstance3D in hidden:
		node.visible = true
	await process_frame

# CI-only eye-relief A/B: tests if the *entire untouched original rig*
# is sitting inside the camera near plane. This is NOT a shipping offset.
func _diagnose_eye_relief(weapon: Node, id: String) -> void:
	var view: Node3D = weapon.get("_view_root") as Node3D
	if view == null:
		return
	var baseline: Vector3 = view.position
	weapon.set_process(false)
	for relief_cm: int in [12, 24, 36]:
		view.position = baseline + Vector3(0, 0, -float(relief_cm) / 100.0)
		await process_frame
		await process_frame
		var img: Image = root.get_texture().get_image()
		if img != null and not img.is_empty():
			var filename := "/tmp/xogot-sight-component-ab/" + id + "-eye-relief-" + str(relief_cm) + "cm.png"
			img.save_png(filename)
			print("XZOGOT_ADS_EYE_RELIEF_AB id=",id," relief_cm=",relief_cm,
				" obstruction=",_ads_frame_obstruction(img))
	view.position = baseline
	weapon.set_process(true)
	await process_frame

# CI-only original PSA vs native bind REST: identify whether a
# sprawling arm/triangle is created by the imported animation or exists
# in the untouched source mesh/skin. Render BOTH, restore original bones.
func _diagnose_native_hand_rest(weapon: Node, id: String) -> void:
	var hands: Node3D = weapon.get("_hands_model_root") as Node3D
	var gun: Node3D = weapon.get("_weapon_model_root") as Node3D
	var skeleton: Skeleton3D = weapon.get("_source_hands_skeleton") as Skeleton3D
	if hands == null or skeleton == null or gun == null:
		print("XZOGOT_HANDS_BIND_REST_PROBE_MISSING ",id)
		return
	var anim: AnimationPlayer = weapon.get("_hands_animation_player") as AnimationPlayer
	weapon.set_process(false)
	if anim != null:
		anim.pause()
	var before: Array[Transform3D] = []
	for i in range(skeleton.get_bone_count()):
		before.append(skeleton.get_bone_pose(i))
	var original_gun_visible := gun.visible
	gun.visible = false
	# Side-by-side original PSA masking isolates which SOURCE limb chain
	# created the stretched first-person triangle (without moving the gun).
	for side: String in ["_le", "_ri"]:
		var changed_bones := 0
		for index in range(skeleton.get_bone_count()):
			var bone_name: String = str(skeleton.get_bone_name(index)).to_lower()
			if bone_name.ends_with(side):
				skeleton.set_bone_pose(index,Transform3D.IDENTITY)
				changed_bones += 1
		await process_frame
		await process_frame
		var limb_frame: Image = root.get_texture().get_image()
		if limb_frame != null and not limb_frame.is_empty():
			var limb_path := "/tmp/xogot-sight-component-ab/" + id + "-hands-" + side.trim_prefix("_") + "-bones-rest.png"
			limb_frame.save_png(limb_path)
			print("XZOGOT_SOURCE_HAND_LIMB_SIDE_AB id=",id," side=",side,
				" reset_bones=",changed_bones,
				" remaining_obstruction=",_ads_frame_obstruction(limb_frame),
				" frame=",limb_path)
		for index in range(before.size()):
			skeleton.set_bone_pose(index,before[index])
		await process_frame
	skeleton.reset_bone_poses()
	await process_frame
	await process_frame
	var frame: Image = root.get_texture().get_image()
	if frame != null and not frame.is_empty():
		var file := "/tmp/xogot-sight-component-ab/" + id + "-hands-native-bind-rest.png"
		frame.save_png(file)
		print("XZOGOT_SOURCE_HANDS_REST_AB id=",id,
			" original_psa_bones=",before.size(),
			" original_mesh_unchanged=true rest_obstruction=",
			_ads_frame_obstruction(frame)," path=",file)
	for i in range(before.size()):
		skeleton.set_bone_pose(i,before[i])
	gun.visible = original_gun_visible
	if anim != null:
		anim.play()
	weapon.set_process(true)
	await process_frame

# Non-shipping A/B: compare final automated iron-to-muzzle optical
# registration with EXACT original recovered DT_Weapons ADS transform.
# Preserves the imported gun, original hands PSA, GPU materials and timing.
func _diagnose_original_source_dt_vs_registered(weapon: Node,id: String) -> void:
	var view: Node3D = weapon.get("_view_root") as Node3D
	if view == null:
		return
	var registered: Transform3D = view.transform
	var authored_position: Vector3 = weapon.get("_ads_pose_position")
	var authored_rotation: Quaternion = weapon.get("_ads_pose_rotation")
	weapon.set_process(false)
	view.position = authored_position
	view.quaternion = authored_rotation
	await process_frame
	await process_frame
	var original: Image = root.get_texture().get_image()
	if original != null and not original.is_empty():
		var path := "/tmp/xogot-sight-component-ab/" + id + "-original-DT-ADS-before-optical-register.png"
		original.save_png(path)
		print("XZOGOT_ADS_AUTHORED_DT_VS_REGISTERED id=",id,
			" registration_bypassed_for_GPU_AB_only=true original_ads_obstruction=",
			_ads_frame_obstruction(original)," registered_ads=",
			weapon.get_meta("weapon_ads_source_sight_registration", "missing"),
			" output=",path)
	view.transform = registered
	weapon.set_process(true)
	await process_frame

func _start() -> void:
	DirAccess.make_dir_recursive_absolute(OUT)
	# Reproducible uncluttered studio: imported gun+hands are exactly the same
	# objects as the main game, but zombies, map particles and HUD are omitted.
	var studio := Node3D.new()
	studio.name = "SourceWeaponStudio"
	root.add_child(studio)
	var background := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.12,0.14,0.16)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(1.0,1.0,1.0)
	env.ambient_light_energy = 0.75
	background.environment = env
	studio.add_child(background)
	var keylight := DirectionalLight3D.new()
	keylight.rotation_degrees = Vector3(-32, 30, 0)
	keylight.light_energy = 1.3
	studio.add_child(keylight)
	var player := CharacterBody3D.new()
	player.name = "Player"
	player.set_script(STUB_PLAYER)
	studio.add_child(player)
	var head := Node3D.new()
	head.name = "Head"
	player.add_child(head)
	var camera := Camera3D.new()
	camera.name = "Camera3D"
	camera.fov = 66.0
	camera.near = 0.025
	camera.current = true
	head.add_child(camera)
	var weapon := Node.new()
	weapon.name = "Weapon"
	weapon.set_script(SOURCE_WEAPON)
	player.add_child(weapon)
	# A distant 3D target shows exactly where the camera's forward axis lands.
	var target := MeshInstance3D.new()
	target.name = "SightTarget"
	var disk := CylinderMesh.new()
	disk.top_radius = 0.05
	disk.bottom_radius = 0.05
	disk.height = 0.006
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.9,0.8,0.38)
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	disk.material = mat
	target.mesh = disk
	target.position = Vector3(0.0, 0.0, -9.0)
	target.rotation_degrees = Vector3(90,0,0)
	studio.add_child(target)
	await process_frame
	var total := 0
	var errs: Array[String] = []
	var reference_path := "res://data/waw_2008_iron_sight_visual_reference.json"
	var original_references: Variant = JSON.parse_string(
		FileAccess.get_file_as_string(reference_path)
	)
	if not (original_references is Dictionary):
		_fail("missing original 2008 World at War ADS source screenshot index")
		return
	var authored_references: Dictionary = (original_references as Dictionary).get("weapons", {})
	if authored_references.size() != 28:
		_fail("original WaW reference list is not complete")
		return
	for id: String in FIREARMS:
		if not authored_references.has(id):
			errs.append(id+":missing_original_2008_reference")
			continue
		var original: Dictionary = authored_references[id]
		print("XZOGOT_WAW_2008_ORIGINAL_SIGHT_COMPARE_REQUIRED id=",id,
			" original_aim_photo=",original.get("original_2008_imfdb_ads_image_number"),
			" original_hip_photo=",original.get("original_2008_imfdb_hip_image_number"),
			" original_scope_photo=",original.get("alternate_ads_image_number"),
			" aim_type=",original.get("aim_view"),
			" source=",original.get("source_url"),
			" match_status=NOT_YET_VISUALLY_VERIFIED")
		player.set_meta("ads_toggled", false)
		if not bool(weapon.call("equip_weapon", id, true)):
			errs.append(id+":equip")
			continue
		await create_timer(0.6).timeout
		for pose: String in ["hip","ads"]:
			player.set_meta("ads_toggled", pose == "ads")
			await create_timer(0.7).timeout
			await process_frame
			var image: Image = root.get_texture().get_image()
			if image == null or image.is_empty():
				errs.append(id+":"+pose+":frame_missing")
				continue
			var output := OUT + "/" + id + "-" + pose + ".png"
			if image.save_png(output) != OK:
				errs.append(id+":"+pose+":png_failed")
				continue
			total += 1
			# Baseline before scope-glass fix: Mosin central glass mean 211/255,
			# PTRS 197/255 in 48px optical aperture (completely opaque).
			# Check actual rendered pixel transmission, not merely shader flags.
			if pose == "ads" and (id == "mosin" or id == "ptrs"):
				var sx: int = image.get_width() / 2
				var sy: int = image.get_height() / 2
				var sum_luminance: float = 0.0
				var samples: int = 0
				for ix in range(-22, 23, 4):
					for iy in range(-22, 23, 4):
						if absi(ix) < 8 and absi(iy) < 8:
							continue
						var pix: Color = image.get_pixel(sx + ix, sy + iy)
						sum_luminance += (pix.r + pix.g + pix.b) / 3.0
						samples += 1
				var aperture_light: float = sum_luminance / maxf(float(samples), 1.0)
				print("XZOGOT_SCOPED_LENS_TRANSMISSION id=",id,
					" aperture_mean_0_1=",aperture_light,
					" old_opaque_baseline_mosin_0_1=0.827 ptrs_0_1=0.771")
				if aperture_light > 0.59:
					errs.append(id+":scope_lens_blocks_camera_optical_axis="+str(aperture_light))
				var gun_node: Node3D = weapon.get("_weapon_model_root") as Node3D
				var glass_seen := false
				if gun_node != null:
					for render_node: Node in gun_node.find_children("*", "MeshInstance3D", true, false):
						if not (render_node is MeshInstance3D):
							continue
						var mesh_node := render_node as MeshInstance3D
						if mesh_node.mesh == null:
							continue
						for surface_idx in range(mesh_node.mesh.get_surface_count()):
							var surf_material := mesh_node.get_active_material(surface_idx)
							if surf_material != null and "scope_glass" in surf_material.resource_name:
								glass_seen = true
								if surf_material is StandardMaterial3D:
									var glass := surf_material as StandardMaterial3D
									if glass.transparency != BaseMaterial3D.TRANSPARENCY_ALPHA:
										errs.append(id+":scope_lens_material_still_opaque")
				if not glass_seen:
					errs.append(id+":real_scope_glass_surface_not_found")
			if pose == "ads":
				var occlusion: Dictionary = _ads_frame_obstruction(image)
				var upper_fraction: float = float(occlusion.get("upper_fraction", 0.0))
				var right_fraction: float = float(occlusion.get("right_fraction", 0.0))
				print("XZOGOT_ISOLATED_ADS_GPU_OCCLUSION id=",id,
					" upper_view_obstruction_fraction=",upper_fraction,
					" right_edge_obstruction_fraction=",right_fraction)
				if upper_fraction > 0.20 or right_fraction > 0.50:
					errs.append(id+":real_gpu_viewmodel_overobstructs_camera="+str(occlusion))
				if id in ["gewehr", "fg42", "arisaka"]:
					await _diagnose_occluding_parts(weapon, id)
					await _diagnose_eye_relief(weapon, id)
					if id in ["fg42", "arisaka"]:
						await _diagnose_native_hand_rest(weapon,id)
				if id in ["fg42", "gewehr"]:
					await _diagnose_original_source_dt_vs_registered(weapon,id)
			var result_angle := float(weapon.get_meta("weapon_ads_visual_bore_error_deg", -1.0))
			var result_sight := float(weapon.get_meta("weapon_ads_source_sight_error_m", -1.0))
			if pose == "ads":
				var source_mode: String = str(weapon.call("get_ads_calibration_mode"))
				if source_mode != "source_datatable":
					errs.append(id+":source_ads_not_bound="+source_mode)
				if not bool(weapon.get_meta("weapon_source_weapon_attachment_ready", false)):
					errs.append(id+":source_hands_tag_weapon_unbound")
				var hip_pos: Vector3 = weapon.get("_hip_pose_position")
				var ads_pos: Vector3 = weapon.get("_ads_pose_position")
				if hip_pos.distance_to(ads_pos) < 0.002:
					errs.append(id+":ads_physical_pose_same_as_hip")
				var scope_kind: String = str(weapon.get_meta("weapon_ads_source_sight_socket",""))
				if not scope_kind.is_empty() and result_sight > 0.01:
					errs.append(id+":source_sight_off_camera="+str(result_sight))
				if not scope_kind.is_empty():
					var optical_depth: float = float(weapon.get_meta("weapon_ads_source_sight_depth_m", 0.0))
					if optical_depth > -0.16:
						errs.append(id+":source_sight_clips_near_plane="+str(optical_depth))
			print("XZOGOT_ISOLATED_SIGHT_FRAME ",id," ",pose,
				" bore_error_deg=",result_angle,
				" rear_marker_error_m=",result_sight," png=",output)
	print("XZOGOT_ISOLATED_SIGHT_FRAMES total=",total," expected=56")
	if total != 56 or not errs.is_empty():
		_fail("capture total mismatch or missing files "+str(errs))
		return
	print("XZOGOT_ISOLATED_ALL_28_SOURCE_ADS_CAPTURE_GREEN 56 ; MANUAL_VISUAL_GRIP_APPROVAL_STILL_REQUIRED")
	studio.queue_free()
	await process_frame
	quit(0)
