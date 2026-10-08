extends SceneTree

# NON-SHIPPING FORENSICS: Arisaka TYPE99 rifle's actual 2026-10-08 Godot
# HIP screenshot has right-hand wrist 25.8cm outside the complete gun AABB.
# In ADS its native animated right wrist can be 80cm from source gun j_gun.
# Do NOT "fix" this by a guessed offset or waive the existing hard-RED gate.
# Compare original recovered hand PSA and gun PSA against each original GLB's
# own native skeleton rest, independent of each other, in both source HIP/ADS.
# Every PNG is genuine Godot, not a fabricated weapon-card approximation.
const STUB = preload("res://ci/ads_dummy_player.gd")
const SOURCE_WEAPON = preload("res://scripts/weapon.gd")
const REGISTRY = preload("res://scripts/weapon_asset_registry.gd")
const OUT := "/tmp/xogot-arisaka-dual-native-rest"

func _init() -> void:
	call_deferred("_run")

func _fail(reason: String) -> void:
	push_error("XZOGOT_ARISAKA_DUAL_REST_RED " + reason)
	quit(3)

func _find_skeleton(n: Node) -> Skeleton3D:
	if n is Skeleton3D:
		return n as Skeleton3D
	for child: Node in n.get_children():
		var found: Skeleton3D = _find_skeleton(child)
		if found != null:
			return found
	return null

func _poses(sk: Skeleton3D) -> Array[Transform3D]:
	var result: Array[Transform3D] = []
	for i in range(sk.get_bone_count()):
		result.append(sk.get_bone_pose(i))
	return result

func _restore(sk: Skeleton3D, poses: Array[Transform3D]) -> void:
	for i in range(poses.size()):
		sk.set_bone_pose(i, poses[i])

func _right_wrist_contact(weapon: Node, hand: Skeleton3D, cam: Camera3D) -> Dictionary:
	var report: Dictionary = weapon.call("get_first_person_debug_snapshot")
	var gun: Dictionary = report.get("weapon", {})
	var pos: Vector3 = gun.get("position", Vector3.ZERO)
	var size: Vector3 = gun.get("size", Vector3.ZERO)
	var idx := hand.find_bone("j_wrist_ri")
	if idx < 0:
		return {"error":"j_wrist_ri_missing"}
	var wrist: Vector3 = cam.to_local(
		(hand.global_transform * hand.get_bone_global_pose(idx)).origin
	)
	var nearest := Vector3(
		clampf(wrist.x, pos.x, pos.x + size.x),
		clampf(wrist.y, pos.y, pos.y + size.y),
		clampf(wrist.z, pos.z, pos.z + size.z)
	)
	var source_bone_idx := hand.find_bone("tag_weapon")
	var socket := Vector3.ZERO
	if source_bone_idx >= 0:
		socket = cam.to_local(
			(hand.global_transform * hand.get_bone_global_pose(source_bone_idx)).origin
		)
	return {
		"wrist_cam": wrist,
		"socket_cam": socket,
		"wrist_to_socket_m": snappedf(wrist.distance_to(socket),0.0001),
		"wrist_to_full_gun_AABB_m": snappedf(wrist.distance_to(nearest),0.0001),
		"gun_AABB": AABB(pos,size),
		"diagnostic_only": "static AABB cannot prove actual palm contact"
	}

func _image(path: String) -> bool:
	await process_frame
	await process_frame
	var im: Image = root.get_texture().get_image()
	return im != null and not im.is_empty() and im.get_width() >= 1024 and (
		im.save_png(OUT + "/" + path + ".png") == OK
	)

func _run() -> void:
	DirAccess.make_dir_recursive_absolute(OUT)
	var studio := Node3D.new()
	root.add_child(studio)
	var world := WorldEnvironment.new()
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color(0.08,0.09,0.11)
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_energy = 0.8
	world.environment = environment
	studio.add_child(world)
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
	player.set_meta("ads_toggled",false)
	if not bool(weapon.call("equip_weapon","arisaka",true)):
		_fail("cannot equip recovered original TYPE99 rifle")
		return
	await create_timer(0.70).timeout
	var gun_model := weapon.get("_weapon_model_root") as Node3D
	var hands_model := weapon.get("_hands_model_root") as Node3D
	var attachment := weapon.get("_source_weapon_attachment") as Node3D
	var gun_player := weapon.get("_asset_animation_player") as AnimationPlayer
	var hands_player := weapon.get("_hands_animation_player") as AnimationPlayer
	var gun: Skeleton3D = _find_skeleton(gun_model)
	var hands: Skeleton3D = _find_skeleton(hands_model)
	var gun_idle: String = REGISTRY.animation_name_for_role("arisaka","idle")
	var hand_idle := "PSA_viewmodel_type99_rifle_idle"
	if (gun_model == null or hands_model == null or attachment == null
		or gun_model.get_parent() != attachment or gun == null or hands == null
		or gun_player == null or hands_player == null
		or not gun_player.has_animation(gun_idle)
		or not hands_player.has_animation(hand_idle)):
		_fail("actual original weapon AND source-hands rest/PSA unavailable: " + gun_idle)
		return
	var captured := 0
	for ads: bool in [false,true]:
		player.set_meta("ads_toggled",ads)
		await create_timer(0.70).timeout
		weapon.set_process(false)
		gun_player.play(gun_idle,0.0)
		gun_player.seek(0.0,true)
		gun_player.pause()
		hands_player.play(hand_idle,0.0)
		hands_player.seek(0.0,true)
		hands_player.pause()
		weapon.call("_sync_source_weapon_attachment")
		var gun_idle_poses := _poses(gun)
		var hand_idle_poses := _poses(hands)
		for scenario: String in ["both-idle","gun-native-rest","hands-native-rest","both-native-rest"]:
			_restore(gun,gun_idle_poses)
			_restore(hands,hand_idle_poses)
			if scenario in ["gun-native-rest","both-native-rest"]:
				gun.reset_bone_poses()
			if scenario in ["hands-native-rest","both-native-rest"]:
				hands.reset_bone_poses()
			weapon.call("_sync_source_weapon_attachment")
			var label := "arisaka-" + ("ads" if ads else "hip") + "-" + scenario
			print("XZOGOT_ARISAKA_DUAL_REST_FRAME ",label,
				" gun_rest=",scenario in ["gun-native-rest","both-native-rest"],
				" hands_rest=",scenario in ["hands-native-rest","both-native-rest"],
				" source_hand_vs_original_mesh=", _right_wrist_contact(weapon,hands,camera))
			if not await _image(label):
				_fail("Godot PNG not saved: " + label)
				return
			captured += 1
		_restore(gun,gun_idle_poses)
		_restore(hands,hand_idle_poses)
		weapon.call("_sync_source_weapon_attachment")
		weapon.set_process(true)
	player.set_meta("ads_toggled",false)
	if captured != 8:
		_fail("only "+str(captured)+"/8 original-frame comparisons")
		return
	print("XZOGOT_ARISAKA_DUAL_REST_AB_GREEN original_PSA_GLB_intact=true 8_independent_Godot_frames=true visual_grip_approval_still_REQUIRED=true")
	quit(0)
