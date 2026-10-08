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

func _reset_gun_to_import_rest(gun_root: Node3D) -> void:
	var stack: Array[Node] = [gun_root]
	while not stack.is_empty():
		var current: Node = stack.pop_back()
		if current is Skeleton3D:
			(current as Skeleton3D).reset_bone_poses()
		for child in current.get_children():
			stack.append(child)

# In the original single-surface Aether SW357 mesh, these exact source
# bones skin the reload-only speedloader and six ejected cartridges.
# Make a non-destructive Godot ArrayMesh copy for an isolated A/B capture.
func _idle_mesh_without_original_reload_props(model: Node3D) -> bool:
	var skeleton: Skeleton3D = null
	var gun_mesh: MeshInstance3D = null
	var stack: Array[Node] = [model]
	while not stack.is_empty():
		var item: Node = stack.pop_back()
		if item is Skeleton3D:
			skeleton = item as Skeleton3D
		if item is MeshInstance3D and not (item as MeshInstance3D).mesh is PrimitiveMesh:
			gun_mesh = item as MeshInstance3D
		for child in item.get_children():
			stack.append(child)
	if skeleton == null or gun_mesh == null or gun_mesh.mesh == null:
		push_error("XZOGOT_SW357_MISSING_SKIN_OR_GUN")
		return false
	var skin: Skin = gun_mesh.skin
	if skin == null:
		push_error("XZOGOT_SW357_MISSING_NATIVE_SKIN")
		return false
	var source_mesh: Mesh = gun_mesh.mesh
	var filtered: ArrayMesh = ArrayMesh.new()
	var dropped_total: int = 0
	for surface_idx in range(source_mesh.get_surface_count()):
		var a: Array = source_mesh.surface_get_arrays(surface_idx)
		var bones: PackedInt32Array = a[Mesh.ARRAY_BONES]
		var weights: PackedFloat32Array = a[Mesh.ARRAY_WEIGHTS]
		var vertices: PackedVector3Array = a[Mesh.ARRAY_VERTEX]
		var orig: PackedInt32Array = a[Mesh.ARRAY_INDEX]
		var stride: int = 8 if (source_mesh.surface_get_format(surface_idx) & Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS) else 4
		if orig.is_empty() or bones.size() < vertices.size() * stride:
			push_error("XZOGOT_SW357_SKIN_ARRAY_MISMATCH")
			return false
		var auxiliary: PackedByteArray = PackedByteArray()
		auxiliary.resize(vertices.size())
		for v in range(vertices.size()):
			var best: float = 0.0
			var best_name: String = ""
			for influence in range(stride):
				var offset: int = v * stride + influence
				if weights[offset] > best:
					best = weights[offset]
					var binding: int = bones[offset]
					best_name = str(skin.get_bind_name(binding))
					if best_name.is_empty() and binding < skeleton.get_bone_count():
						best_name = str(skeleton.get_bone_name(binding))
			auxiliary[v] = 1 if (
				best >= 0.25 and (
				best_name.begins_with("tag_spent") or
				best_name == "tag_speedloader" or best_name == "tag_bullets"
				)
			) else 0
		var keep: PackedInt32Array = PackedInt32Array()
		for tri in range(0,orig.size(),3):
			var i0: int = orig[tri]
			var i1: int = orig[tri+1]
			var i2: int = orig[tri+2]
			if auxiliary[i0] != 0 and auxiliary[i1] != 0 and auxiliary[i2] != 0:
				dropped_total += 1
			else:
				keep.append_array(PackedInt32Array([i0,i1,i2]))
		a[Mesh.ARRAY_INDEX] = keep
		# Keep the source 8-bone weight layout; passing default flags made
		# Godot reject the source vertex arrays as an invalid surface.
		var format_flags: int = source_mesh.surface_get_format(surface_idx) & Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS
		filtered.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,a,[],{},format_flags)
		if filtered.get_surface_count() != surface_idx + 1:
			push_error("XZOGOT_SW357_FILTER_ARRAY_BUILD_RED surface=" + str(surface_idx))
			return false
		filtered.surface_set_material(surface_idx,source_mesh.surface_get_material(surface_idx))
	gun_mesh.mesh = filtered
	print("XZOGOT_SW357_ORIGINAL_RELOAD_ONLY_FACES_SUPPRESSED triangles=",dropped_total,
		" original_skin_preserved=",gun_mesh.skin != null)
	return dropped_total > 0

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
	if not _idle_mesh_without_original_reload_props(weapon.get("_weapon_model_root") as Node3D):
		push_error("XZOGOT_SW357_FILTER_TEST_NOT_RESOLVED")
		quit(9)
		return
	await _screenshot("07-authored-idle-reload-only-geometry-hidden")
	print("XZOGOT_SW357_ANIMATION_AB_IMAGES_READY 7 source_action=",source_idle)
	quit(0)
