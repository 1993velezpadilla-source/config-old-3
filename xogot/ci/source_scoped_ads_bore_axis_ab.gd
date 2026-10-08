extends SceneTree

# Real Godot 4.6 scoped source ADS proof. DT_Weapons source pose untouched.
# Compare a one-time source-gun-forward (+X) -> camera (-Z) quaternion,
# then source gun up -> camera up. No per-weapon invented offsets or FOV.
const DUMMY = preload("res://ci/ads_dummy_player.gd")
const SOURCE_WEAPON = preload("res://scripts/weapon.gd")
const OUT := "/tmp/xogot-scoped-bore-axis"
const IDS: Array[String] = ["mosin", "ptrs"]
const MODES: Array[String] = ["source", "align_bore", "align_bore_and_up", "align_bore_up_depth15"]

func _init() -> void:
	call_deferred("_run")

func _red(msg: String) -> void:
	push_error("XZOGOT_SCOPED_BORE_AB_RED " + msg)
	quit(2)

func _frame(name: String) -> bool:
	await process_frame
	await process_frame
	var frame: Image = root.get_texture().get_image()
	return frame != null and not frame.is_empty() and frame.save_png(OUT + "/" + name + ".png") == OK

func _run() -> void:
	DirAccess.make_dir_recursive_absolute(OUT)
	var scene := Node3D.new()
	root.add_child(scene)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color(0.08, 0.09, 0.11)
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
	var frames := 0
	await process_frame
	for id: String in IDS:
		player.set_meta("ads_toggled",false)
		if not bool(weapon.call("equip_weapon",id,true)):
			_red("unable to equip " + id)
			return
		await create_timer(0.65).timeout
		player.set_meta("ads_toggled",true)
		await create_timer(0.7).timeout
		weapon.call("_update_visual_recoil",0.7)
		var view := weapon.get("_view_root") as Node3D
		var gun := weapon.get("_weapon_model_root") as Node3D
		if view == null or gun == null:
			_red("source hierarchy missing " + id)
			return
		weapon.set_process(false)
		var hands_anim := weapon.get("_hands_animation_player") as AnimationPlayer
		if hands_anim != null:
			hands_anim.pause()
		var source_anim := weapon.get("_asset_animation_player") as AnimationPlayer
		if source_anim != null:
			source_anim.pause()
		var pos := view.position
		var rot := view.quaternion
		# The source scope marker is NOT sufficient to prove the barrel faces
		# forward: previous automated sight gates passed with huge sideways ADS.
		for mode: String in MODES:
			view.position = pos
			view.quaternion = rot
			if mode != "source":
				var gun_axes := (camera.global_transform.basis.inverse()
					* gun.global_transform.basis).orthonormalized()
				var forward := gun_axes.x.normalized()
				var up := gun_axes.y.normalized()
				if not forward.is_finite() or not up.is_finite():
					_red("invalid source axes " + id)
					return
				var bore_align := Quaternion(forward, Vector3.FORWARD).normalized()
				var correct := bore_align
				if mode != "align_bore":
					var rolled_up := bore_align * up
					var upright := Quaternion(Vector3.FORWARD,
						-atan2(rolled_up.x, rolled_up.y))
					correct = (upright * bore_align).normalized()
				view.quaternion = (correct * view.quaternion).normalized()
				var tag: Dictionary = weapon.call("_gun_skeleton_bone_world","tag_scope")
				if not bool(tag.get("found",false)):
					_red("source scope tag missing " + id)
					return
				var point := camera.to_local(tag.get("position",Vector3.ZERO))
				view.position += Vector3(-point.x,-point.y,0.0)
				if mode == "align_bore_up_depth15":
					view.position.z -= 0.15
			await process_frame
			var axes_out := (camera.global_transform.basis.inverse()
				* gun.global_transform.basis).orthonormalized()
			var actual_forward := axes_out.x.normalized()
			var actual_up := axes_out.y.normalized()
			var bore_error := rad_to_deg(acos(clampf(actual_forward.dot(Vector3.FORWARD),-1.0,1.0)))
			var scope: Dictionary = weapon.call("_gun_skeleton_bone_world","tag_scope")
			var scope_pos := camera.to_local(scope.get("position",Vector3.ZERO))
			print("XZOGOT_SCOPED_BORE_AXIS_METRIC id=",id,
				" mode=",mode, " bore_error_deg=",bore_error,
				" up_camera=",actual_up," scope_camera=",scope_pos,
				" source_dt_unchanged=true")
			if not await _frame(id+"-ads-"+mode):
				_red("real PNG missing " + id + ":" + mode)
				return
			frames += 1
		view.position = pos
		view.quaternion = rot
		weapon.set_process(true)
		player.set_meta("ads_toggled",false)
	if frames != 8:
		_red("expected 8 original-source frames got "+str(frames))
		return
	print("XZOGOT_SCOPED_BORE_AXIS_PROOF_GREEN frames=8 no_shipping_changes=true")
	quit(0)
