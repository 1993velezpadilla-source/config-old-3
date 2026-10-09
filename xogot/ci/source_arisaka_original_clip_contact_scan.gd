extends SceneTree

# Compare ALL 13 recovered TYPE99/Arisaka hand PSA actions and their
# authored timestamps, without editing any gun/hands animation or DT_Weapons.
# A real 28-gun grip gate found a 25.8cm trigger-wrist gap. Source native
# rest improves this but destroys the authored weapon pose, so test whether
# the correct original HAND action is being played before editing runtime.
const STUB = preload("res://ci/ads_dummy_player.gd")
const SOURCE_WEAPON = preload("res://scripts/weapon.gd")
const OUT := "/tmp/xogot-arisaka-original-action-contact"

func _init() -> void:
	call_deferred("_run")

func _red(reason: String) -> void:
	push_error("XZOGOT_ARISAKA_ACTION_CONTACT_RED " + reason)
	quit(2)

func _camera_contact(weapon: Node, sk: Skeleton3D, cam: Camera3D) -> Dictionary:
	var snapshot: Dictionary = weapon.call("get_first_person_debug_snapshot")
	var geom: Dictionary = snapshot.get("weapon", {})
	var pos: Vector3 = geom.get("position", Vector3.ZERO)
	var size: Vector3 = geom.get("size", Vector3.ZERO)
	if size.length_squared() < 0.001:
		return {"error": "no recovered source weapon mesh"}
	var point_cam: Dictionary = {}
	for bone: String in ["j_wrist_ri", "j_wrist_le", "tag_weapon", "j_shoulder_ri", "j_elbow_ri"]:
		var index := sk.find_bone(bone)
		if index < 0:
			return {"error":"missing original source bone " + bone}
		point_cam[bone] = cam.to_local(
			(sk.global_transform * sk.get_bone_global_pose(index)).origin)
	var point: Vector3 = point_cam["j_wrist_ri"]
	var nearest := Vector3(
		clampf(point.x, pos.x, pos.x+size.x),
		clampf(point.y, pos.y, pos.y+size.y),
		clampf(point.z, pos.z, pos.z+size.z))
	return {
		"trigger_wrist_to_gun_aabb_m": snappedf(point.distance_to(nearest),0.0001),
		"trigger_wrist_to_socket_m": snappedf(point.distance_to(point_cam["tag_weapon"]),0.0001),
		"wrist_cam":point,
		"socket_cam":point_cam["tag_weapon"],
		"right_shoulder_cam":point_cam["j_shoulder_ri"],
		"right_elbow_cam":point_cam["j_elbow_ri"],
		"gun_bounds_cam":AABB(pos,size),
	}

func _capture(name: String) -> bool:
	await process_frame
	await process_frame
	var image: Image = root.get_texture().get_image()
	return image != null and not image.is_empty() and image.get_width() == 1280 and image.save_png(OUT+"/"+name+".png") == OK

func _run() -> void:
	DirAccess.make_dir_recursive_absolute(OUT)
	var world := Node3D.new()
	root.add_child(world)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color(0.085,0.09,0.11)
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_energy = 0.85
	world.add_child(env)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-32.0,20.0,0.0)
	light.light_energy = 1.2
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
	camera.near = 0.025
	camera.fov = 66
	head.add_child(camera)
	var weapon := Node.new()
	weapon.name = "Weapon"
	weapon.set_script(SOURCE_WEAPON)
	player.add_child(weapon)
	await process_frame
	if not bool(weapon.call("equip_weapon","arisaka",true)):
		_red("source TYPE99 unable to equip")
		return
	await create_timer(0.85).timeout
	var hand_anim: AnimationPlayer = weapon.get("_hands_animation_player") as AnimationPlayer
	var hands: Skeleton3D = weapon.get("_source_hands_skeleton") as Skeleton3D
	if hand_anim == null or hands == null or hands.get_bone_count() != 113:
		_red("recovered Arisaka 113-bone Marine hands not present")
		return
	var clips: Array[String] = []
	for name: String in hand_anim.get_animation_list():
		if name.begins_with("PSA_viewmodel_type99_rifle_"):
			clips.append(name)
	clips.sort()
	if clips.size() < 12:
		_red("13 recovered Arisaka source actions not imported: " + str(clips))
		return
	var best: Dictionary = {"gap": INF}
	var scanned: int = 0
	var captured: int = 0
	for ads: bool in [false,true]:
		player.set_meta("ads_toggled",ads)
		await create_timer(0.70).timeout
		weapon.set_process(false)
		for clip: String in clips:
			var anim: Animation = hand_anim.get_animation(clip)
			if anim == null or anim.length <= 0.0:
				_red("authored source PSA length missing " + clip)
				return
			for part: float in [0.0,0.50,0.95]:
				hand_anim.play(clip,0.0)
				hand_anim.seek(part*anim.length,true)
				hand_anim.pause()
				weapon.call("_sync_source_weapon_attachment")
				var result: Dictionary = _camera_contact(weapon,hands,camera)
				if result.has("error"):
					_red(str(result["error"]))
					return
				var gap: float = float(result["trigger_wrist_to_gun_aabb_m"])
				print("XZOGOT_ARISAKA_AUTHORED_ACTION_CONTACT mode=",
					"ADS" if ads else "HIP", " clip=",clip," fraction=",part,
					" length=",snappedf(anim.length,0.0001)," details=",result)
				scanned += 1
				if gap < float(best["gap"]):
					best = {
						"clip":clip,
						"part":part,
						"ads":ads,
						"gap":gap,
						"wrist_to_socket_m":result["trigger_wrist_to_socket_m"]}
				if clip.ends_with("_idle") and part == 0.0:
					if not await _capture("arisaka-"+("ads" if ads else "hip")+"-source-idle"):
						_red("original source idle capture unavailable")
						return
					captured += 1
		weapon.set_process(true)
	# Restore the source idle and only capture the best authentic variant for
	# independent visual inspection (NOT shipping a new action choice).
	for ads: bool in [false,true]:
		player.set_meta("ads_toggled",ads)
		await create_timer(0.70).timeout
		weapon.set_process(false)
		var best_clip: String = str(best["clip"])
		var best_anim: Animation = hand_anim.get_animation(best_clip)
		hand_anim.play(best_clip,0.0)
		hand_anim.seek(float(best["part"])*best_anim.length,true)
		hand_anim.pause()
		weapon.call("_sync_source_weapon_attachment")
		if not await _capture("arisaka-"+("ads" if ads else "hip")+"-best-existing-clip"):
			_red("best source action frame unavailable")
			return
		captured += 1
		weapon.set_process(true)
	if scanned != clips.size()*6 or captured != 4:
		_red("incomplete source clip audit scanned="+str(scanned)+" images="+str(captured))
		return
	print("XZOGOT_ARISAKA_AUTHORED_CLIP_SCAN_GREEN source_clips=",clips.size(),
		" scans=",scanned," images=",captured," best_original_source=",best,
		" code_and_source_animations_untouched=true visual_grip_signoff_REQUIRED=true")
	quit(0)
