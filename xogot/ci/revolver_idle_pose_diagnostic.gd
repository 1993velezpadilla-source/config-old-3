extends SceneTree

# Actual imported source SW357 animation comparison. This does NOT change
# the game's source gun, exported poses or hand animations.
const STUB_PLAYER = preload("res://ci/ads_dummy_player.gd")
const SOURCE_WEAPON = preload("res://scripts/weapon.gd")
const SourceReload = preload("res://scripts/weapon_sw357_reload_geometry.gd")
const SOURCE_REGISTRY = preload("res://scripts/weapon_asset_registry.gd")
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

func _reset_gun_to_import_rest(gun_root: Node3D) -> void:
	var stack: Array[Node] = [gun_root]
	while not stack.is_empty():
		var current: Node = stack.pop_back()
		if current is Skeleton3D:
			(current as Skeleton3D).reset_bone_poses()
		for child in current.get_children():
			stack.append(child)

# The production helper now owns the source geometry filter; this A/B
# must validate the exact runtime code instead of duplicating its algorithm.
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
	var sw357_meshes: Dictionary = weapon.get("_sw357_reload_meshes") as Dictionary
	if sw357_meshes.is_empty() or int(sw357_meshes.get("removed_triangles", 0)) <= 0:
		push_error("XZOGOT_SW357_PRODUCTION_IDLE_FILTER_MISSING")
		quit(11)
		return
	print("XZOGOT_SW357_PRODUCTION_MESH_READY removed_triangles=", sw357_meshes.get("removed_triangles"),
		" removed_vertices=", sw357_meshes.get("removed_vertices"))
	# The first six captures must show the original unfiltered imported mesh.
	if not SourceReload.set_reload_props_visible(sw357_meshes, true):
		push_error("XZOGOT_SW357_CANNOT_RESTORE_SOURCE_RELOAD_MESH")
		quit(12)
		return
	var gun_anim: AnimationPlayer = weapon.get("_asset_animation_player") as AnimationPlayer
	if gun_anim == null:
		push_error("XZOGOT_SW357_ANIM_PLAYER_MISSING")
		quit(8)
		return
	var source_idle := SOURCE_REGISTRY.animation_name_for_role("357", "idle")
	if source_idle.is_empty() or not gun_anim.has_animation(source_idle):
		push_error("XZOGOT_SW357_EXACT_SOURCE_IDLE_NOT_AVAILABLE name=" + source_idle)
		quit(10)
		return
	gun_anim.play(source_idle, 0.0)
	await process_frame
	print("XZOGOT_SW357_SOURCE_GUN_IDLE name=", source_idle,
		" position=", gun_anim.current_animation_position)
	await _screenshot("01-original-source-hip")
	# A/B test original animated idle against exactly the same source rig
	# in exported mesh bind/rest position (do not adjust any socket offset).
	weapon.set_process(false)
	gun_anim.stop()
	_reset_gun_to_import_rest(weapon.get("_weapon_model_root") as Node3D)
	await _screenshot("02-raw-import-bind-pose-hip")
	gun_anim.play(source_idle,0.0)
	gun_anim.seek(0.0,true)
	gun_anim.pause()
	await _screenshot("03-original-idle-at-frame-zero")
	gun_anim.play(source_idle,0.0)
	await create_timer(0.55).timeout
	await _screenshot("04-original-idle-frame-33")
	player.set_meta("ads_toggled", true)
	weapon.call("_update_visual_recoil",0.6)
	await create_timer(0.6).timeout
	await _screenshot("05-original-idle-ads")
	gun_anim.stop()
	_reset_gun_to_import_rest(weapon.get("_weapon_model_root") as Node3D)
	await _screenshot("06-bind-pose-ads")
	if not SourceReload.set_reload_props_visible(sw357_meshes, false):
		push_error("XZOGOT_SW357_FILTER_TEST_NOT_RESOLVED")
		quit(9)
		return
	await _screenshot("07-authored-idle-reload-only-geometry-hidden")
	var sw357_node: MeshInstance3D = sw357_meshes.get("node") as MeshInstance3D
	if sw357_node == null or sw357_node.mesh != sw357_meshes.get("idle"):
		push_error("XZOGOT_SW357_IDLE_MESH_NOT_ACTIVE")
		quit(13)
		return
	if not SourceReload.set_reload_props_visible(sw357_meshes, true):
		push_error("XZOGOT_SW357_RELOAD_CANNOT_RESTORE_ORIGINAL")
		quit(14)
		return
	if sw357_node.mesh != sw357_meshes.get("original"):
		push_error("XZOGOT_SW357_ORIGINAL_RELOAD_MESH_MISMATCH")
		quit(15)
		return
	if not SourceReload.set_reload_props_visible(sw357_meshes, false):
		push_error("XZOGOT_SW357_CANNOT_RETURN_TO_IDLE")
		quit(16)
		return
	print("XZOGOT_SW357_PRODUCTION_RELOAD_MESH_SWITCH_GREEN original_restored_then_hidden=true")
	print("XZOGOT_SW357_ANIMATION_AB_IMAGES_READY 7 source_action=",source_idle)
	quit(0)
