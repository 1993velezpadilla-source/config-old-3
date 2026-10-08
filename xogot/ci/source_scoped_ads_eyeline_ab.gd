extends SceneTree

# Read-only source optical camera eye-line diagnostic for scoped rifle ADS.
# Preserves original DT_Weapons translations/rotations, source PSA, original
# GLB and hand rig; varies ONLY view-root camera distance for A/B renders.
const DUMMY = preload("res://ci/ads_dummy_player.gd")
const SOURCE_WEAPON = preload("res://scripts/weapon.gd")
const IDS: Array[String] = ["mosin", "ptrs"]
const EYE_DEPTHS_M: Array[float] = [0.0, 0.15, 0.30, 0.50, 0.75]
const OUT := "/tmp/xogot-scoped-eyeline"

func _init() -> void:
	call_deferred("_run")

func _red(msg: String) -> void:
	push_error("XZOGOT_SCOPE_EYELINE_AB_RED " + msg)
	quit(3)

func _screenshot(name: String) -> bool:
	await process_frame
	await process_frame
	var img: Image = root.get_texture().get_image()
	if img == null or img.is_empty():
		return false
	return img.save_png(OUT + "/" + name + ".png") == OK

func _run() -> void:
	DirAccess.make_dir_recursive_absolute(OUT)
	var scene := Node3D.new()
	root.add_child(scene)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color(0.08,0.09,0.11)
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_energy = 0.8
	scene.add_child(env)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-32,20,0)
	light.light_energy = 1.25
	scene.add_child(light)
	var player := CharacterBody3D.new()
	player.name = "Player"
	player.set_script(DUMMY)
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
	weapon.set_script(SOURCE_WEAPON)
	player.add_child(weapon)
	var total := 0
	await process_frame
	for id: String in IDS:
		player.set_meta("ads_toggled",false)
		if not bool(weapon.call("equip_weapon",id,true)):
			_red("cannot equip exact source " + id)
			return
		await create_timer(0.65).timeout
		player.set_meta("ads_toggled",true)
		await create_timer(0.65).timeout
		weapon.call("_update_visual_recoil",0.7)
		var view: Node3D = weapon.get("_view_root") as Node3D
		if view == null:
			_red("missing authored viewroot " + id)
			return
		weapon.set_process(false)
		var hand_anim: AnimationPlayer = weapon.get("_hands_animation_player") as AnimationPlayer
		if hand_anim != null:
			hand_anim.pause()
		var gun_anim: AnimationPlayer = weapon.get("_asset_animation_player") as AnimationPlayer
		if gun_anim != null:
			gun_anim.pause()
		var authored_pose := view.position
		var authored_rotation := view.quaternion
		var authored_ads: Dictionary = weapon.call("get_first_person_debug_snapshot")
		print("XZOGOT_SCOPE_AUTHORED_ADS id=",id,
			" view_pos=",authored_pose," rotation=",authored_rotation,
			" source_datatable=",weapon.call("get_ads_calibration_mode"),
			" snap=",authored_ads)
		for depth: float in EYE_DEPTHS_M:
			view.position = authored_pose + Vector3(0,0,-depth)
			await process_frame
			var optic: Dictionary = weapon.call("_gun_skeleton_bone_world","tag_scope")
			var optic_local: Vector3 = camera.to_local(optic.get("position", Vector3.ZERO))
			var gun_snap: Dictionary = weapon.call("get_first_person_debug_snapshot")
			var gun_bounds: Dictionary = gun_snap.get("weapon", {})
			print("XZOGOT_SCOPE_EYELINE_MEASURE id=",id, " extra_depth_m=",depth,
				" scope_tag_present=",optic.get("found",false),
				" scope_depth_camera_m=",optic_local.z,
				" scope_xy_camera_m=",Vector2(optic_local.x,optic_local.y).length(),
				" weapon_bounds=",gun_bounds.get("size",Vector3.ZERO),
				" source_ads_pose_unchanged=true")
			var label := "%s-ads-depth-%03dcm" % [id,int(round(depth*100))]
			if not await _screenshot(label):
				_red("unable to capture genuine image " + label)
				return
			total += 1
		view.position = authored_pose
		view.quaternion = authored_rotation
		weapon.set_process(true)
		player.set_meta("ads_toggled",false)
	if total != 10:
		_red("expected 10 actual scoped Godot images got "+str(total))
		return
	print("XZOGOT_SCOPE_EYELINE_DIAGNOSTIC_GREEN count=10 guns=2 shipping_ads_unchanged=true")
	quit(0)
