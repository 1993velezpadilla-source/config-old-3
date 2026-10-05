extends SceneTree

const WeaponCatalog = preload("res://scripts/weapon_catalog.gd")
const WeaponAssetRegistry = preload("res://scripts/weapon_asset_registry.gd")
const WeaponBalanceAAA = preload("res://scripts/weapon_balance_aaa.gd")

const FIREARMS: Array[String] = ["colt","walther","nambu","tt33","357","mp40","thompson","ppsh","type100","stg","m1","m1a1","gewehr","svt40","arisaka","kar98k","springfield","mosin","ptrs","trench","doublebarrel","sawnoff","bar","fg42","mg42","browning","dp28","type99"]

func _init() -> void:
	call_deferred("_run_probe")

func _fail(code: int, message: String) -> void:
	push_error("AAA_WEAPON_RUNTIME_PROBE: " + message)
	quit(code)

func _find_mesh(node: Node) -> MeshInstance3D:
	if node is MeshInstance3D:
		return node as MeshInstance3D
	for child: Node in node.get_children():
		var found := _find_mesh(child)
		if found != null:
			return found
	return null

func _find_animation_player(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node as AnimationPlayer
	for child: Node in node.get_children():
		var found := _find_animation_player(child)
		if found != null:
			return found
	return null

func _run_probe() -> void:
	var packed: PackedScene = load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(2, "main scene missing")
		return

	var scene := packed.instantiate()
	root.add_child(scene)
	await process_frame
	await physics_frame

	var weapon: Node = scene.get_node_or_null("Player/Weapon")
	if weapon == null:
		_fail(3, "weapon runtime missing")
		return

	if WeaponBalanceAAA.firearm_ids().size() != FIREARMS.size():
		_fail(4, "AAA balance table must cover exactly 28 firearms")
		return

	for id: String in FIREARMS:
		if not WeaponCatalog.has_weapon(id):
			_fail(10, "catalog missing " + id)
			return
		if not WeaponBalanceAAA.has_data(id):
			_fail(11, "AAA balance missing " + id)
			return

		var viewmodel_path := WeaponAssetRegistry.preferred_viewmodel_path(id)
		if viewmodel_path.is_empty() or not ResourceLoader.exists(viewmodel_path):
			_fail(12, "real viewmodel missing " + id + " path=" + viewmodel_path)
			return
		var viewmodel_scene := load(viewmodel_path) as PackedScene
		if viewmodel_scene == null:
			_fail(13, "viewmodel not PackedScene " + id)
			return
		var viewmodel := viewmodel_scene.instantiate()
		if viewmodel == null or _find_mesh(viewmodel) == null:
			if viewmodel != null:
				viewmodel.free()
			_fail(14, "viewmodel has no mesh " + id)
			return
		var animation_player := _find_animation_player(viewmodel)
		if animation_player == null:
			viewmodel.free()
			_fail(15, "AnimationPlayer missing " + id)
			return
		for role: String in ["idle", "fire", "reload", "equip"]:
			var animation_name := WeaponAssetRegistry.animation_name_for_role(id, role)
			if animation_name.is_empty():
				viewmodel.free()
				_fail(16, "core animation role missing " + id + "/" + role)
				return
		viewmodel.free()

		var fire_path := WeaponAssetRegistry.preferred_audio_path(id, "fire")
		if fire_path.is_empty() or not ResourceLoader.exists(fire_path):
			_fail(17, "fire audio missing " + id)
			return

		if not bool(weapon.call("equip_weapon", id, true)):
			_fail(18, "equip failed " + id)
			return
		await process_frame

		if str(weapon.get_meta("weapon_asset_lane", "")) == "missing_real_asset":
			_fail(19, "runtime selected missing asset lane " + id)
			return
		var ads_mode := str(weapon.call("get_ads_calibration_mode"))
		if ads_mode == "generic":
			_fail(20, "ADS has no per-model calibration " + id)
			return

		var yaw_fix := float(weapon.get_meta("weapon_model_yaw_correction_deg", 0.0))
		if absf(yaw_fix - 90.0) > 0.01:
			_fail(27, "forward-axis correction missing " + id + " yaw=" + str(yaw_fix))
			return

		var texture_surfaces := int(weapon.get_meta("weapon_texture_surfaces", 0))
		var textured_surfaces := int(weapon.get_meta("weapon_textured_surfaces", 0))
		if not bool(weapon.get_meta("weapon_texture_ready", false)):
			_fail(
				28,
				"texture binding incomplete " + id + " "
				+ str(textured_surfaces) + "/" + str(texture_surfaces)
			)
			return
		if texture_surfaces <= 0 or textured_surfaces != texture_surfaces:
			_fail(29, "texture surface mismatch " + id)
			return

		var view_depth := float(weapon.get_meta("weapon_viewmodel_depth_m", 0.0))
		if view_depth < 0.20 or view_depth > 1.55:
			_fail(30, "viewmodel depth out of sane range " + id + " depth=" + str(view_depth))
			return

		var view_scale := float(weapon.get_meta("weapon_viewmodel_scale_factor", 0.0))
		if view_scale < 0.619 or view_scale > 1.321:
			_fail(31, "viewmodel normalization scale invalid " + id + " scale=" + str(view_scale))
			return

		var ads_near := float(weapon.get_meta("weapon_ads_nearest_camera_z", 0.0))
		if ads_near > -0.16:
			_fail(32, "ADS geometry intersects camera " + id + " near=" + str(ads_near))
			return

		weapon.call("set_dev_infinite_ammo", true)
		var shots_before := int(weapon.call("get_shots_fired"))
		weapon.set("_cooldown", 0.0)
		weapon.call("request_fire")
		if int(weapon.call("get_shots_fired")) != shots_before + 1:
			_fail(21, "fire runtime failed " + id)
			return
		if not bool(weapon.call("is_muzzle_fx_ready")):
			_fail(22, "muzzle FX not bound " + id)
			return

		var base_stats: Dictionary = weapon.call("get_runtime_stats") as Dictionary
		var expected_pack_damage := WeaponBalanceAAA.pack_damage(id, -1.0)
		var expected_pack_mag := WeaponBalanceAAA.pack_magazine(id, -1)
		if not bool(weapon.call("upgrade_current_weapon")):
			_fail(23, "PaP upgrade failed " + id)
			return
		var pack_stats: Dictionary = weapon.call("get_runtime_stats") as Dictionary
		if absf(float(pack_stats.get("damage", -1.0)) - expected_pack_damage) > 0.001:
			_fail(24, "PaP damage mismatch " + id)
			return
		if int(pack_stats.get("magazine_size", -1)) != expected_pack_mag:
			_fail(25, "PaP magazine mismatch " + id)
			return
		if float(pack_stats.get("damage", 0.0)) <= float(base_stats.get("damage", 0.0)):
			_fail(26, "PaP did not increase damage " + id)
			return

		print(
			"XZOGOT_AAA_WEAPON_GREEN ",
			id,
			" ads=", ads_mode,
			" textures=", textured_surfaces, "/", texture_surfaces,
			" depth=", view_depth,
			" near=", ads_near,
			" pap=", expected_pack_damage
		)

	print("XZOGOT_AAA_28_FIREARMS_GREEN 28")
	print("XZOGOT_AAA_WEAPON_RUNTIME_GATE_GREEN")
	scene.queue_free()
	await process_frame
	quit(0)
