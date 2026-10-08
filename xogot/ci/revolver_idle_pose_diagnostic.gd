extends SceneTree

# Actual imported source SW357 animation comparison. This does NOT change
# the game's source gun, exported poses or hand animations.
const STUB_PLAYER = preload("res://ci/ads_dummy_player.gd")
const SOURCE_WEAPON = preload("res://scripts/weapon.gd")
const OUT := "/tmp/xogot-revolver-357-anim"

func _init() -> void:
	call_deferred("_run")

func _screenshot(name: String) -> void:
	await process_frame
	await process_frame
	var img: Image = root.get_texture().get_image()
	if img == null or img.is_empty():
		push_error("XZOGOT_SW357_NO_FRAME " + name)
		return
	var path := OUT + "/" + name + ".png"
	if img.save_png(path) != OK:
		push_error("XZOGOT_SW357_FRAME_WRITE_RED " + path)
	print("XZOGOT_SW357_RENDERED_FRAME " + path)

func _run() -> void:
	DirAccess.make_dir_recursive_absolute(OUT)
	var scene := Node3D.new()
	root.add_child(scene)
	var world := WorldEnvironment.new()
	world.environment = Environment.new()
	world.environment.background_mode = Environment.BG_COLOR
	world.environment.background_color = Color(0.08,0.09,0.11)
	world.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	world.environment.ambient_light_energy = 0.8
	scene.add_child(world)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-32.0,20.0,0.0)
	light.light_energy = 1.25
	scene.add_child(light)
	var player := CharacterBody3D.new()
	player.name = "Player"
	player.set_script(STUB_PLAYER)
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
	await process_frame
	if not bool(weapon.call("equip_weapon", "357", true)):
		push_error("XZOGOT_SW357_CANNOT_EQUIP")
		quit(7)
		return
	await create_timer(0.8).timeout
	var gun_anim: AnimationPlayer = weapon.get("_asset_animation_player") as AnimationPlayer
	if gun_anim == null:
		push_error("XZOGOT_SW357_ANIM_PLAYER_MISSING")
		quit(8)
		return
	var source_idle := str(gun_anim.current_animation)
	print("XZOGOT_SW357_SOURCE_GUN_IDLE name=",source_idle,
		" position=",gun_anim.current_animation_position)
	await _screenshot("01-original-source-hip")
	# A/B test original animated idle against exactly the same source rig
	# in exported mesh bind/rest position (do not adjust any socket offset).
	gun_anim.stop()
	gun_anim.reset()
	await _screenshot("02-raw-import-bind-pose-hip")
	gun_anim.play(source_idle,0.0)
	gun_anim.seek(0.0,true)
	gun_anim.pause()
	await _screenshot("03-original-idle-at-frame-zero")
	gun_anim.play(source_idle,0.0)
	await create_timer(0.55).timeout
	await _screenshot("04-original-idle-frame-33")
	player.set_meta("ads_toggled", true)
	await create_timer(0.6).timeout
	await _screenshot("05-original-idle-ads")
	gun_anim.stop()
	gun_anim.reset()
	await _screenshot("06-bind-pose-ads")
	print("XZOGOT_SW357_ANIMATION_AB_IMAGES_READY 6 source_action=",source_idle)
	quit(0)
