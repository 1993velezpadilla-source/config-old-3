extends SceneTree

# Actual Godot viewport screenshots in a temporary open-air reference QA bay
# inside the existing church level. We stage the real live gameplay nodes to
# remove occluding walls, NOT generate concept art or invent source geometry.
# These copyrighted community workshop reference models remain CI-only.
const OUTPUT := "res://../build/church-visual-evidence"

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, msg: String) -> void:
	push_error("CHURCH_VISUAL_CAPTURE: " + msg)
	quit(code)

func _frames(count: int) -> void:
	for i in range(count):
		await process_frame

func _photo(label: String, camera: Camera3D, position: Vector3, target: Vector3) -> bool:
	camera.current = true
	camera.global_position = position
	camera.look_at(target, Vector3.UP)
	await _frames(22)
	var captured: Image = root.get_texture().get_image()
	if captured == null or captured.is_empty():
		return false
	captured.resize(1280, 720, Image.INTERPOLATE_LANCZOS)
	if captured.save_jpg(OUTPUT + "/" + label + ".jpg", 0.92) != OK:
		return false
	print("XZOGOT_REAL_INGAME_FOCUSED_PHOTO_GREEN ", label, " 1280x720")
	return true

func _qa_lighting(church: Node, center: Vector3) -> void:
	var original_environment: WorldEnvironment = church.find_child("WorldEnvironment",true,false) as WorldEnvironment
	if original_environment != null and original_environment.environment != null:
		var env: Environment = original_environment.environment
		env.fog_enabled = false
		env.ambient_light_energy = 1.25
		env.ambient_light_color = Color(0.72,0.76,0.88)
	for info: Dictionary in [
		{"name":"QAWarmKey","offset":Vector3(-2.2,3.8,2.8),"energy":7.5,"color":Color(1.0,0.89,0.71)},
		{"name":"QACoolFill","offset":Vector3(2.1,2.5,-2.0),"energy":5.0,"color":Color(0.65,0.79,1.0)},
	]:
		var light := OmniLight3D.new()
		light.name = str(info["name"])
		church.add_child(light)
		light.global_position = center + (info["offset"] as Vector3)
		light.light_energy = float(info["energy"])
		light.light_color = info["color"] as Color
		light.omni_range = 12.0
		light.shadow_enabled = false

func _run() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUTPUT))
	var packed: PackedScene = load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(2, "Original live church scene missing")
		return
	var church: Node = packed.instantiate()
	root.add_child(church)
	await _frames(35)
	var player: CharacterBody3D = church.get_node_or_null("Player") as CharacterBody3D
	var fps: Camera3D = church.get_node_or_null("Player/Head/Camera3D") as Camera3D
	var director: Node = church.get_node_or_null("RoundManager")
	if player == null or fps == null or director == null:
		_fail(3, "Original gameplay/player/camera missing")
		return
	var hud: CanvasLayer = church.get_node_or_null("HUD") as CanvasLayer
	if hud != null:
		hud.visible = false # QA images isolate source model, no touch overlays
	director.set("_network_match_active",false)
	director.set("auto_start",false)
	player.set("auto_knife_enabled",false)
	var stage_center: Vector3 = church.call("_wp", Vector3(39.0,0.38,-3.0))
	_qa_lighting(church,stage_center)
	player.set_physics_process(false)
	player.global_position = stage_center + Vector3(0,0,5)
	var camera := Camera3D.new()
	camera.name = "ChurchSourceRealityCamera"
	church.add_child(camera)
	camera.fov = 50.0
	camera.near = 0.05
	var source_script: Script = load("res://scripts/zombie_dummy.gd") as Script
	if source_script == null:
		_fail(4,"Actual zombie AI script missing")
		return
	var actor := CharacterBody3D.new()
	actor.name = "AuthenticSkinnedZombieInspection"
	actor.set_script(source_script)
	actor.position = stage_center
	actor.call("configure_direct",player,null)
	church.add_child(actor)
	await _frames(8)
	if str(actor.get_meta("zombie_source_lane","")) != "PAVLOV_UE421_NACHT_REFERENCE":
		_fail(5,"Original source mesh is not loaded into gameplay zombie")
		return
	actor.set_physics_process(false)
	var ok: bool = await _photo("01_real_nacht_zombie_clear_view",camera,
		stage_center+Vector3(1.8,1.75,3.1),stage_center+Vector3(0,0.9,0))
	actor.visible = false
	# Move existing *working* interactive physics nodes into one clear exterior
	# preview bay, one at a time. Production map coordinates never change.
	var scenes: Array[Dictionary] = [
		{"node":"MysteryBoxSocket","name":"02_real_animated_mystery_box"},
		{"node":"SanctumForge","name":"03_real_pack_a_punch_geometry"},
		{"node":"PowerSwitch","name":"04_real_power_switch_geometry"}
	]
	for item: Dictionary in scenes:
		var body: StaticBody3D = church.get_node_or_null(str(item["node"])) as StaticBody3D
		if body == null or not bool(body.get_meta("source_reference_visual_loaded",false)):
			_fail(6,"Original reference source mesh missing for "+str(item["node"]))
			return
		var prior: Transform3D = body.global_transform
		body.global_position = stage_center+Vector3(0,1.10,0)
		body.global_rotation = Vector3.ZERO
		ok = (await _photo(str(item["name"]),camera,
			stage_center+Vector3(1.65,1.8,3.05),stage_center+Vector3(0,1.08,0))) and ok
		body.global_transform = prior
	# First person: keep full source hands and complete MP40 rig active.
	var gun: Node = player.get_node_or_null("Weapon")
	if gun == null or not bool(gun.call("equip_weapon","mp40",true)):
		_fail(7,"Real MP40 asset not loaded")
		return
	if not bool(gun.get_meta("weapon_source_weapon_attachment_ready",false)):
		_fail(8,"Recovered hands tag_weapon socket not attached")
		return
	player.global_position = stage_center+Vector3(0,0,3)
	player.rotation.y = 0.0
	var head: Node3D = player.get_node_or_null("Head") as Node3D
	if head != null:
		head.rotation.x = deg_to_rad(-1.0)
	fps.current = true
	gun.call("_play_asset_animation","idle",0.0)
	await _frames(36)
	# Camera is switched to the actual player's playable FPS viewpoint.
	var saved: Image = root.get_texture().get_image()
	if saved == null or saved.is_empty():
		_fail(9,"Real FPS screenshot framebuffer missing")
		return
	saved.resize(1280,720,Image.INTERPOLATE_LANCZOS)
	ok = saved.save_jpg(OUTPUT+"/05_mp40_actual_hip_with_hands.jpg",0.92) == OK and ok
	print("XZOGOT_REAL_INGAME_FOCUSED_PHOTO_GREEN 05_mp40_actual_hip_with_hands 1280x720")
	player.set_meta("ads_toggled",true)
	gun.call("_update_visual_recoil",0.35)
	await _frames(20)
	var aim_frame: Image = root.get_texture().get_image()
	if aim_frame == null or aim_frame.is_empty():
		_fail(10,"ADS screenshot framebuffer missing")
		return
	aim_frame.resize(1280,720,Image.INTERPOLATE_LANCZOS)
	ok = aim_frame.save_jpg(OUTPUT+"/06_mp40_actual_aim_down_sights.jpg",0.92) == OK and ok
	print("XZOGOT_REAL_INGAME_FOCUSED_PHOTO_GREEN 06_mp40_actual_aim_down_sights 1280x720")
	if not ok:
		_fail(11,"Some real QA render outputs failed")
		return
	print("XZOGOT_REAL_CHURCH_SIX_SOURCE_INSPECTION_PHOTOS_GREEN")
	quit(0)
