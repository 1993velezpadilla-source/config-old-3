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
	for id: String in FIREARMS:
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
