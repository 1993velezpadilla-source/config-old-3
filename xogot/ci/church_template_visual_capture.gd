extends SceneTree

# Screenshots from the real Godot rendering viewport, not concept art.
# This CI-only import contains community reference models. Never distribute
# model bytes themselves; evidence frames are internal QA, not release art.
const OUTPUT := "res://../build/church-visual-evidence"

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, msg: String) -> void:
	push_error("CHURCH_VISUAL_CAPTURE: " + msg)
	quit(code)

func _frames(n: int) -> void:
	for _i in range(n):
		await process_frame

func _photo(label: String, camera: Camera3D, position: Vector3, target: Vector3) -> bool:
	camera.current = true
	camera.global_position = position
	camera.look_at(target, Vector3.UP)
	await _frames(18)
	var image: Image = root.get_texture().get_image()
	if image == null or image.is_empty():
		return false
	image.resize(1280, 720, Image.INTERPOLATE_LANCZOS)
	var err: int = image.save_jpg(OUTPUT + "/" + label + ".jpg", 0.87)
	if err != OK:
		return false
	print("XZOGOT_REAL_INGAME_PHOTO_GREEN ", label, " 1280x720")
	return true

func _run() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUTPUT))
	var packed: PackedScene = load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(2, "Real church scene missing")
		return
	var church: Node = packed.instantiate()
	root.add_child(church)
	await _frames(45)
	var player: Node3D = church.get_node_or_null("Player") as Node3D
	var player_camera: Camera3D = church.get_node_or_null("Player/Head/Camera3D") as Camera3D
	var director: Node = church.get_node_or_null("RoundManager")
	if player == null or player_camera == null or director == null:
		_fail(3, "Gameplay camera/player/round manager missing")
		return
	player.set("auto_knife_enabled", false)
	director.set("_network_match_active", false)
	director.set("auto_start", false)
	var zombie_scene: Script = load("res://scripts/zombie_dummy.gd") as Script
	if zombie_scene == null:
		_fail(4, "Actual zombie script missing")
		return
	var actor := CharacterBody3D.new()
	actor.name = "RealNachtModelVisualQA"
	actor.set_script(zombie_scene)
	actor.position = Vector3(0, 0.38, 2.75)
	actor.call("configure_direct", player, null)
	church.add_child(actor)
	await _frames(7)
	if str(actor.get_meta("zombie_source_lane", "")) != "PAVLOV_UE421_NACHT_REFERENCE":
		_fail(5, "Refuse to photograph substitute mesh labeled as source zombie")
		return
	# Freeze chase movement only during the camera's 18-frame exposure, so
	# the photograph documents actual skinned source appearance, not a blur.
	actor.set_physics_process(false)
	var free_camera := Camera3D.new()
	free_camera.name = "RealSourceVisualQACamera"
	church.add_child(free_camera)
	free_camera.fov = 59.0
	var ok: bool = await _photo("01_zombie_source_102bone", free_camera,
		actor.global_position + Vector3(2.9, 1.45, 3.9), actor.global_position + Vector3(0, 1.0, 0))
	var models: Array[Dictionary] = [
		{"node":"MysteryBoxSocket", "name":"02_mystery_box_source_animated"},
		{"node":"SanctumForge", "name":"03_pack_a_punch_source"},
		{"node":"PowerSwitch", "name":"04_power_switch_source"}
	]
	for item: Dictionary in models:
		var machine: StaticBody3D = church.get_node_or_null(str(item["node"])) as StaticBody3D
		if machine == null or not bool(machine.get_meta("source_reference_visual_loaded", false)):
			_fail(6, "Refuse to photograph unmounted source model " + str(item["node"]))
			return
		var center: Vector3 = machine.global_position
		ok = ok and await _photo(str(item["name"]), free_camera,
			center + Vector3(2.6, 1.2, 3.4), center + Vector3(0, 0.4, 0))
	# Actual playable FPS view: runtime gun with recovered hand rig.
	free_camera.current = false
	player_camera.current = true
	var weapon: Node = player.get_node_or_null("Weapon")
	if weapon == null or not bool(weapon.call("equip_weapon", "mp40", true)):
		_fail(7, "MP40 real viewmodel missing")
		return
	player.global_position = Vector3(0, 0.38, 6.7)
	player.rotation.y = 0
	var head: Node3D = player.get_node_or_null("Head") as Node3D
	if head != null:
		head.rotation.x = deg_to_rad(-2.0)
	await _frames(12)
	if not bool(weapon.get_meta("weapon_source_weapon_attachment_ready", false)):
		_fail(8, "Real skinned source hands grip not ready")
		return
	# Reuse Nacht/Project Aether acceptance evidence. Older church code
	# counted a tag_weapon node as GREEN even when the gun inherited another
	# centimeter import scale or followed tag_weapon_end instead of tag_weapon.
	var gun: Node3D = weapon.get("_weapon_model_root") as Node3D
	var source_socket: Node3D = weapon.get("_source_weapon_attachment") as Node3D
	if gun == null or source_socket == null or gun.get_parent() != source_socket:
		_fail(10, "MP40 not attached to exact source hand rig socket")
		return
	if str(weapon.get_meta("weapon_source_attachment_bone_name", "")) != "tag_weapon":
		_fail(11, "MP40 is using helper/end bone rather than source tag_weapon")
		return
	var gun_world_scale: Vector3 = gun.global_transform.basis.get_scale()
	if not bool(weapon.get_meta("weapon_source_attachment_meter_units_restored", false)) or gun_world_scale.distance_to(Vector3.ONE) > 0.015:
		_fail(12, "Nacht centimeter-to-meter weapon inheritance still RED: " + str(gun_world_scale))
		return
	if str(weapon.get_meta("weapon_ads_calibration_mode", "")) != "source_datatable":
		_fail(13, "MP40 missing original Project Aether ADS table position")
		return
	print("XZOGOT_CHURCH_REUSED_NACHT_MP40_SOURCE_RIG_GATE_GREEN world_scale=", gun_world_scale)
	var img: Image = root.get_texture().get_image()
	if img != null and not img.is_empty():
		img.resize(1280, 720, Image.INTERPOLATE_LANCZOS)
		ok = ok and img.save_jpg(OUTPUT + "/05_fps_mp40_real_hands.jpg", 0.87) == OK
		print("XZOGOT_REAL_INGAME_PHOTO_GREEN 05_fps_mp40_real_hands 1280x720")
	else:
		ok = false
	if not ok:
		_fail(9, "One of five real rendered frames failed to save")
		return
	print("XZOGOT_CHURCH_FIVE_FRAMES_CAPTURED_VISUAL_APPROVAL_PENDING")
	quit(0)
