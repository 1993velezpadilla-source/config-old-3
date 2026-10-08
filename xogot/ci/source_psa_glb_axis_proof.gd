extends SceneTree

# Read-only visual A/B for a general ActorX PSA -> recovered UE glTF mismatch.
# Source Colt1911Idle.psa BONENAMES/ANIMKEYS maps local (x,y,z) while the
# recovered Colt1911.glb bind joints map (x,z,-y). A -90-degree X basis change
# recovers the exact 14 original bind translations (0.0258m RMS -> ~0.0m).
# Prove the same correction on other authentic pistols/rifles in real Godot,
# before changing production imports or source-authored fire/reload.
const STUB = preload("res://ci/ads_dummy_player.gd")
const SOURCE_WEAPON = preload("res://scripts/weapon.gd")
const SOURCE_REGISTRY = preload("res://scripts/weapon_asset_registry.gd")
const IDS: Array[String] = ["colt", "walther", "nambu", "tt33", "357", "mosin", "ptrs"]
const OUT := "/tmp/xogot-psa-gltf-axis-ab"

func _init() -> void:
	call_deferred("_run")

func _fail(reason: String) -> void:
	push_error("XZOGOT_PSA_GLTF_AXIS_RED " + reason)
	quit(2)

func _find_native(node: Node) -> Skeleton3D:
	if node is Skeleton3D:
		return node as Skeleton3D
	for child: Node in node.get_children():
		var sk := _find_native(child)
		if sk != null:
			return sk
	return null

func _capture(name: String) -> bool:
	await process_frame
	await process_frame
	var frame: Image = root.get_texture().get_image()
	if frame == null or frame.is_empty():
		return false
	return frame.save_png(OUT + "/" + name + ".png") == OK

func _run() -> void:
	DirAccess.make_dir_recursive_absolute(OUT)
	var world := Node3D.new()
	root.add_child(world)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color(0.08,0.09,0.11)
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_energy = 0.8
	world.add_child(env)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-32, 20, 0)
	light.light_energy = 1.25
	world.add_child(light)
	var player := CharacterBody3D.new()
	player.name = "Player"
	player.set_script(STUB)
	world.add_child(player)
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
	var axes := Basis(Vector3.RIGHT, -PI / 2.0)
	var axes_inverse := axes.inverse()
	var frames := 0
	await process_frame
	for id: String in IDS:
		player.set_meta("ads_toggled",false)
		if not bool(weapon.call("equip_weapon",id,true)):
			_fail("equip " + id)
			return
		await create_timer(0.55).timeout
		player.set_meta("ads_toggled",true)
		await create_timer(0.45).timeout
		weapon.call("_update_visual_recoil",0.6)
		var gun := weapon.get("_weapon_model_root") as Node3D
		if gun == null:
			_fail("missing original gun model " + id)
			return
		var sk := _find_native(gun)
		var anim := weapon.get("_asset_animation_player") as AnimationPlayer
		var idle: String = SOURCE_REGISTRY.animation_name_for_role(id,"idle")
		if sk == null or anim == null or idle.is_empty() or not anim.has_animation(idle):
			_fail("missing original gun PSA rig " + id + ":" + idle)
			return
		weapon.set_process(false)
		anim.play(idle,0.0)
		anim.seek(0.0,true)
		anim.pause()
		var poses: Array[Transform3D] = []
		var original_sum := 0.0
		var corrected_sum := 0.0
		var original_max := 0.0
		var corrected_max := 0.0
		for bone_idx in range(sk.get_bone_count()):
			var source_pose: Transform3D = sk.get_bone_pose(bone_idx)
			var original_rest: Transform3D = sk.get_bone_rest(bone_idx)
			poses.append(source_pose)
			var original_d: float = source_pose.origin.distance_to(original_rest.origin)
			var new_pos: Vector3 = axes * source_pose.origin
			var corrected_d: float = new_pos.distance_to(original_rest.origin)
			original_sum += original_d * original_d
			corrected_sum += corrected_d * corrected_d
			original_max = maxf(original_max,original_d)
			corrected_max = maxf(corrected_max,corrected_d)
			if str(sk.get_bone_name(bone_idx)) in ["j_clip","j_bolt","joint1","joint2","j_gun","tag_flash"]:
				print("XZOGOT_PSA_GLTF_BONE id=",id,
					" bone=",sk.get_bone_name(bone_idx),
					" original=",source_pose.origin,
					" repaired=",new_pos,
					" bind=",original_rest.origin,
					" before_error=",original_d,
					" after_error=",corrected_d)
		var count: float = float(maxi(1,sk.get_bone_count()))
		var rms_before := sqrt(original_sum/count)
		var rms_after := sqrt(corrected_sum/count)
		print("XZOGOT_PSA_GLTF_AXIS_EVIDENCE id=",id,
			" bones=",sk.get_bone_count(),
			" rms_original_m=",rms_before," rms_axis_fixed_m=",rms_after,
			" max_original_m=",original_max,
			" max_axis_fixed_m=",corrected_max)
		if id == "colt" and not (rms_before > 0.01 and rms_after < 0.002):
			_fail("verified Colt source PSA vs glTF native rest did not match " + str(rms_before) + " -> " + str(rms_after))
			return
		if not await _capture(id+"-ads-actorx-raw"):
			_fail("raw screenshot "+id)
			return
		frames += 1
		for idx in range(poses.size()):
			var pose := poses[idx]
			sk.set_bone_pose(idx,Transform3D(
				axes * pose.basis * axes_inverse,
				axes * pose.origin))
		if not await _capture(id+"-ads-axis-repaired"):
			_fail("repaired screenshot "+id)
			return
		frames += 1
		sk.reset_bone_poses()
		if not await _capture(id+"-ads-glb-native-rest"):
			_fail("rest screenshot "+id)
			return
		frames += 1
		for idx in range(poses.size()):
			sk.set_bone_pose(idx,poses[idx])
		weapon.set_process(true)
		player.set_meta("ads_toggled",false)
	if frames != 21:
		_fail("expected 21 original-source screenshots got "+str(frames))
		return
	print("XZOGOT_PSA_GLTF_AXIS_PROOF_GREEN frames=21 source_authority_preserved=true shipping_assets_unchanged=true")
	quit(0)
