extends SceneTree

# NON-SHIPPING original-source forensic A/B for 8 guns whose authentic Godot
# frames show loose/oversized pieces. Compare the real imported PSA idle at
# frame zero with the same GLB native bind/rest pose, at HIP and ADS.
# Source weapon/hand meshes, clips, timings, rotations and placements untouched.
const STUB = preload("res://ci/ads_dummy_player.gd")
const SOURCE_WEAPON = preload("res://scripts/weapon.gd")
const REGISTRY = preload("res://scripts/weapon_asset_registry.gd")
const OUT := "/tmp/xogot-long-gun-native-rest"
const IDS: Array[String] = ["arisaka","fg42","gewehr","svt40","m1","mosin","ptrs","m1a1"]

func _init() -> void:
	call_deferred("_run")

func _fail(message: String) -> void:
	push_error("XZOGOT_LONG_NATIVE_REST_RED " + message)
	quit(2)

func _find_skeleton(node: Node) -> Skeleton3D:
	if node is Skeleton3D:
		return node as Skeleton3D
	for child: Node in node.get_children():
		var found: Skeleton3D = _find_skeleton(child)
		if found != null:
			return found
	return null

func _capture(name: String) -> bool:
	await process_frame
	await process_frame
	var image: Image = root.get_texture().get_image()
	return (image != null and not image.is_empty()
		and image.get_width() >= 1024 and image.get_height() >= 600
		and image.save_png(OUT + "/" + name + ".png") == OK)

func _bone_spread(native: Skeleton3D, camera: Camera3D) -> Dictionary:
	var span := AABB()
	var initialized := false
	var outliers: Array[Dictionary] = []
	for i in range(native.get_bone_count()):
		# Native 3D pose: the original rig's animated transform; never proxy
		# model bounds to a static imported AABB as a deformed skin metric.
		var p: Vector3 = camera.to_local(
			(native.global_transform * native.get_bone_global_pose(i)).origin
		)
		if not initialized:
			span = AABB(p, Vector3.ZERO)
			initialized = true
		else:
			span = span.expand(p)
		var name: String = str(native.get_bone_name(i))
		if name.contains("tag_") or name.contains("j_clip") or name.contains("j_bolt"):
			outliers.append({"name": name, "at_camera_m": p})
	return {"bones": native.get_bone_count(), "camera_aabb": span,
		"tracked_bones": outliers}

func _run() -> void:
	DirAccess.make_dir_recursive_absolute(OUT)
	var studio := Node3D.new()
	root.add_child(studio)
	var environment := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.08, 0.09, 0.11)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_energy = 0.8
	environment.environment = env
	studio.add_child(environment)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-32.0,20.0,0.0)
	light.light_energy = 1.25
	studio.add_child(light)
	var player := CharacterBody3D.new()
	player.name = "Player"
	player.set_script(STUB)
	studio.add_child(player)
	var head := Node3D.new()
	head.name = "Head"
	player.add_child(head)
	var camera := Camera3D.new()
	camera.name = "Camera3D"
	camera.current = true
	camera.near = 0.025
	camera.fov = 66
	head.add_child(camera)
	var weapon := Node.new()
	weapon.name = "Weapon"
	weapon.set_script(SOURCE_WEAPON)
	player.add_child(weapon)
	await process_frame
	var start_idx := clampi(int(OS.get_environment("XOGOT_REST_START").to_int()),0,8)
	var stop_idx := clampi(int(OS.get_environment("XOGOT_REST_END").to_int()),start_idx,8)
	if OS.get_environment("XOGOT_REST_END").is_empty():
		stop_idx = IDS.size()
	var images := 0
	for slot in range(start_idx,stop_idx):
		var id: String = IDS[slot]
		player.set_meta("ads_toggled",false)
		if not bool(weapon.call("equip_weapon",id,true)):
			_fail("cannot equip " + id)
			return
		await create_timer(0.65).timeout
		var gun: Node3D = weapon.get("_weapon_model_root") as Node3D
		var attachment: Node3D = weapon.get("_source_weapon_attachment") as Node3D
		var animator: AnimationPlayer = weapon.get("_asset_animation_player") as AnimationPlayer
		var real_idle: String = REGISTRY.animation_name_for_role(id,"idle")
		if (gun == null or attachment == null or gun.get_parent() != attachment
			or animator == null or not animator.has_animation(real_idle)):
			_fail("source gun/rig/native idle disconnected " + id + " " + real_idle)
			return
		var native: Skeleton3D = _find_skeleton(gun)
		if native == null or native.get_bone_count() < 2:
			_fail("original gun skin skeleton absent " + id)
			return
		for ads in [false,true]:
			player.set_meta("ads_toggled",ads)
			await create_timer(0.60).timeout
			# Freeze only gameplay-driven gun state for the reversible PSA A/B.
			# Keep original hands, source socket, model roll and HUD unchanged.
			weapon.set_process(false)
			animator.play(real_idle, 0.0)
			animator.seek(0.0, true)
			animator.pause()
			var poses: Array[Transform3D] = []
			for index in range(native.get_bone_count()):
				poses.append(native.get_bone_pose(index))
			print("XZOGOT_LONG_NATIVE_AB_SOURCE id=",id," ads=",ads,
				" original_psa=",real_idle," source_grip=",
				weapon.get_meta("weapon_source_attachment_bone_name",""),
				" source_bone_positions=", _bone_spread(native,camera))
			var prefix := id + ("-ads" if ads else "-hip")
			if not await _capture(prefix + "-original-idle"):
				_fail("source idle picture not saved " + prefix)
				return
			images += 1
			native.reset_bone_poses()
			print("XZOGOT_LONG_NATIVE_AB_BIND id=",id," ads=",ads,
				" native_rest_bones=", _bone_spread(native,camera))
			if not await _capture(prefix + "-all-bones-native-rest"):
				_fail("original bind/rest picture not saved " + prefix)
				return
			images += 1
			for index in range(poses.size()):
				native.set_bone_pose(index,poses[index])
			weapon.set_process(true)
		player.set_meta("ads_toggled",false)
	var expected := (stop_idx - start_idx) * 4
	if images != expected:
		_fail("expected " + str(expected) + " original pictures got " + str(images))
		return
	print("XZOGOT_LONG_NATIVE_REST_SOURCE_AB_GREEN frames=",images,
		" shard=",start_idx,"-",stop_idx,
		" original_animations_unchanged=true original_meshes_unchanged=true")
	quit(0)
