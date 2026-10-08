extends SceneTree

# SOURCE HANDS AXIS DIAGNOSIS ONLY. The 2008 WaW ActorX hands PSA was
# exported separately from original glTF skinned gun clips. The latter
# needed x,y,z -> x,z,-y to agree with native bind rests. That does NOT
# establish that T4 Marine or Richtofen hands use the same conversion.
# These 21 real Godot A/B frames distinguish the two before any shipping
# animation, skin or model is modified. No heuristically moved hands.
const DUMMY = preload("res://ci/ads_dummy_player.gd")
const WEAPON = preload("res://scripts/weapon.gd")
const IDS: Array[String] = ["colt", "357", "mp40", "mosin", "ptrs", "stg", "ppsh"]
const OUT := "/tmp/xogot-hands-psa-rest-axis"

func _init() -> void:
	call_deferred("_run")

func _red(reason: String) -> void:
	push_error("XZOGOT_SOURCE_HANDS_AXIS_AB_RED " + reason)
	quit(2)

func _native(node: Node) -> Skeleton3D:
	if node is Skeleton3D:
		return node as Skeleton3D
	for child in node.get_children():
		var hit := _native(child)
		if hit != null:
			return hit
	return null

func _screenshot(label: String) -> bool:
	await process_frame
	await process_frame
	var img: Image = root.get_texture().get_image()
	return img != null and not img.is_empty() and img.save_png(OUT + "/" + label + ".png") == OK

func _run() -> void:
	DirAccess.make_dir_recursive_absolute(OUT)
	var world := Node3D.new()
	root.add_child(world)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color(0.085, 0.09, 0.11)
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_energy = 0.85
	world.add_child(env)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-30.0, 25.0, 0.0)
	light.light_energy = 1.1
	world.add_child(light)
	var player := CharacterBody3D.new()
	player.name = "Player"
	player.set_script(DUMMY)
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
	weapon.set_script(WEAPON)
	player.add_child(weapon)
	var axis := Basis(Vector3.RIGHT, -PI * 0.5)
	var inverse_axis := axis.inverse()
	var frames := 0
	await process_frame
	for id: String in IDS:
		player.set_meta("ads_toggled", false)
		if not bool(weapon.call("equip_weapon", id, true)):
			_red("source equip failed " + id)
			return
		await create_timer(0.65).timeout
		var hands := weapon.get("_hands_model_root") as Node3D
		var anim := weapon.get("_hands_animation_player") as AnimationPlayer
		var sk := _native(hands) if hands != null else null
		if hands == null or anim == null or sk == null or sk.get_bone_count() < 30:
			_red("source hands/PSA rig unavailable " + id)
			return
		var idle := str(anim.get_assigned_animation())
		if idle.is_empty() or not anim.has_animation(idle):
			_red("real source idle was not assigned " + id + ":" + idle)
			return
		weapon.set_process(false)
		anim.seek(0.0, true)
		anim.pause()
		var poses: Array[Transform3D] = []
		var raw_sq: float = 0.0
		var corrected_sq: float = 0.0
		var wrists: int = 0
		var near_rest_raw: int = 0
		var near_rest_axis: int = 0
		for index in range(sk.get_bone_count()):
			var p: Transform3D = sk.get_bone_pose(index)
			var rest: Transform3D = sk.get_bone_rest(index)
			var raw_m: float = p.origin.distance_to(rest.origin)
			var corrected_m: float = (axis * p.origin).distance_to(rest.origin)
			raw_sq += raw_m * raw_m
			corrected_sq += corrected_m * corrected_m
			if raw_m < 0.002:
				near_rest_raw += 1
			if corrected_m < 0.002:
				near_rest_axis += 1
			poses.append(p)
			var bone := str(sk.get_bone_name(index))
			if bone.contains("wrist") or bone.contains("thumb") or bone.contains("index") or bone == "tag_weapon":
				if bone.contains("wrist"):
					wrists += 1
				print("XZOGOT_SOURCE_HANDS_BIND_ANCHOR id=", id,
					" bone=", bone, " raw_translation=", p.origin,
					" axis_converted=", axis * p.origin,
					" native_rest=",rest.origin,
					" raw_diff_m=",raw_m," converted_diff_m=",corrected_m)
		var n: float = float(sk.get_bone_count())
		var raw_rms: float = sqrt(raw_sq/n)
		var candidate_rms: float = sqrt(corrected_sq/n)
		# T4 Marine hands are PSK-imported in original centimeter-space and
		# scaled once by their parent Node3D. These bone-local RMS values are
		# SOURCE UNITS, not world-space meters. Previously both were mislabeled.
		print("XZOGOT_SOURCE_HANDS_AXIS_TRUTH id=",id," idle=", idle,
			" bones=",sk.get_bone_count()," wrists=",wrists,
			" source_local_unit=UE_centimeters",
			" raw_rest_rms_source_units=",raw_rms,
			" proposed_axis_rest_rms_source_units=",candidate_rms,
			" raw_within_0_002_source_units=",near_rest_raw,
			" axis_within_0_002_source_units=",near_rest_axis,
			" shipping_source_unchanged=true")
		if wrists < 2 or not is_finite(raw_rms) or not is_finite(candidate_rms):
			_red("invalid hand wrist authority " + id)
			return
		# 21 actual Godot screenshots + all seven numeric source records
		# verified the native hands are ALREADY in the correct glTF basis.
		# The -90° conversion was required for GUN PSA only; applying it
		# to hands twists original T4 wrist/finger poses violently.
		# Require raw PSA substantially closer than converted and 70% of
		# bones agreeing with the original bind rest in source units.
		if raw_rms >= candidate_rms or near_rest_raw < 75 or near_rest_axis > 50:
			_red("source hands axis regression " + id +
				" raw_rms=" + str(raw_rms) +
				" converted_rms=" + str(candidate_rms) +
				" raw_native_near=" + str(near_rest_raw) +
				" converted_native_near=" + str(near_rest_axis))
			return
		print("XZOGOT_NATIVE_SOURCE_HAND_AXIS_LOCK_GREEN id=",id,
			" hand_PSAs_must_not_inherit_gun_PSA_rebake=true")
		if not await _screenshot(id+"-original-psa-hands"):
			_red("missing original Godot frame " + id)
			return
		frames += 1
		for index in range(poses.size()):
			var p: Transform3D = poses[index]
			sk.set_bone_pose(index,Transform3D(
				axis * p.basis * inverse_axis, axis * p.origin))
		if not await _screenshot(id+"-candidate-axis-hands"):
			_red("missing candidate frame " + id)
			return
		frames += 1
		sk.reset_bone_poses()
		if not await _screenshot(id+"-native-bind-rest-hands"):
			_red("missing native rest frame " + id)
			return
		frames += 1
		for index in range(poses.size()):
			sk.set_bone_pose(index, poses[index])
		weapon.set_process(true)
	if frames != 21:
		_red("expected 21 authentic A/B source-hand PNGs got "+str(frames))
		return
	print("XZOGOT_SOURCE_HANDS_AXIS_DIAGNOSTIC_GREEN frames=21 seven_rigs=true source_assets_untouched=true")
	quit(0)
