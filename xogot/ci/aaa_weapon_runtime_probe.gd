extends SceneTree

const WeaponCatalog = preload("res://scripts/weapon_catalog.gd")
const WeaponAssetRegistry = preload("res://scripts/weapon_asset_registry.gd")
const WeaponBalanceAAA = preload("res://scripts/weapon_balance_aaa.gd")
const WeaponViewmodelSourcePose = preload("res://scripts/weapon_viewmodel_source_pose.gd")

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
		if id == "mp40":
			if ads_mode != "source_datatable":
				_fail(20, "MP40 must use recovered DT_Weapons ADS transform, got " + ads_mode)
				return
			if not bool(weapon.get_meta("weapon_source_weapon_attachment_ready", false)):
				_fail(35, "MP40 source tag_weapon attachment missing")
				return
			if str(weapon.get_meta("weapon_source_rig_mode", "")) != "legacy_hands_tag_weapon":
				_fail(36, "MP40 source hands rig mode missing")
				return
			if not bool(weapon.get_meta("weapon_hands_animation_ready", false)):
				_fail(37, "MP40 source hands AnimationPlayer missing")
				return
			if not bool(weapon.get_meta("weapon_hands_texture_ready", false)):
				_fail(
					38,
					"MP40 source hands textures incomplete "
					+ str(weapon.get_meta("weapon_hands_textured_surfaces", 0))
					+ "/"
					+ str(weapon.get_meta("weapon_hands_texture_surfaces", 0))
				)
				return
			if str(weapon.get_meta("weapon_source_presentation_table", "")).find("DT_Weapons") < 0:
				_fail(39, "MP40 DT_Weapons provenance missing")
				return
			if int(weapon.get_meta("weapon_source_presentation_row", -1)) != 5:
				_fail(40, "MP40 DT_Weapons row provenance mismatch")
				return
			if absf(float(weapon.get_meta("weapon_source_ads_in_time", 0.0)) - 0.20) > 0.0001:
				_fail(41, "MP40 source ADS-in timing mismatch")
				return
			if absf(float(weapon.get_meta("weapon_source_ads_out_time", 0.0)) - 0.20) > 0.0001:
				_fail(42, "MP40 source ADS-out timing mismatch")
				return
			var hands_report_path := "res://assets/weapons/aether_waw_hands/legacy_richtofen/animation-report.json"
			if not FileAccess.file_exists(hands_report_path):
				_fail(43, "MP40 source hands animation report missing")
				return
			var hands_report_file := FileAccess.open(hands_report_path, FileAccess.READ)
			if hands_report_file == null:
				_fail(44, "MP40 source hands animation report unreadable")
				return
			var hands_report_value: Variant = JSON.parse_string(hands_report_file.get_as_text())
			if not (hands_report_value is Dictionary):
				_fail(45, "MP40 source hands animation report invalid JSON")
				return
			var hands_report: Dictionary = hands_report_value
			if absf(float(hands_report.get("translation_scale", 0.0)) - 0.01) > 0.000001:
				_fail(46, "MP40 source hands PSA translation scale must be UE cm -> GLB m")
				return
		else:
			if ads_mode != "source_pending":
				_fail(20, "ADS must remain source_pending until exact archive metadata is bound " + id)
				return

		var yaw_fix := float(weapon.get_meta("weapon_model_yaw_correction_deg", 0.0))
		if absf(yaw_fix - 90.0) > 0.01:
			_fail(27, "forward-axis correction missing " + id + " yaw=" + str(yaw_fix))
			return

		var texture_surfaces := int(weapon.get_meta("weapon_texture_surfaces", 0))
		var resolved_surfaces := int(weapon.get_meta("weapon_resolved_surfaces", 0))
		var textured_surfaces := int(weapon.get_meta("weapon_textured_surfaces", 0))
		var hidden_surfaces := int(weapon.get_meta("weapon_hidden_surfaces", 0))
		if not bool(weapon.get_meta("weapon_texture_ready", false)):
			_fail(
				28,
				"texture binding incomplete " + id + " "
				+ str(textured_surfaces) + "/" + str(texture_surfaces)
			)
			return
		if texture_surfaces <= 0 or resolved_surfaces != texture_surfaces:
			_fail(
				29,
				"material surface mismatch " + id + " resolved="
				+ str(resolved_surfaces) + "/" + str(texture_surfaces)
			)
			return
		if textured_surfaces + hidden_surfaces != texture_surfaces:
			_fail(33, "visible/hidden accounting mismatch " + id)
			return

		var source_pose_ready := bool(weapon.get_meta("weapon_source_hip_pose_ready", false))
		var source_status := WeaponViewmodelSourcePose.status(id)
		if id == "sawnoff":
			if source_pose_ready or source_status != "missing_idle_hands":
				_fail(30, "Sawed-Off must stay PENDING_SOURCE until idle-hands pose is recovered")
				return
			print("XZOGOT_AAA_WEAPON_SOURCE_PENDING sawnoff missing_idle_hands")
		else:
			if not WeaponViewmodelSourcePose.has_source_hip_pose(id):
				_fail(30, "source-authored HIP pose missing " + id)
				return
			if not source_pose_ready:
				_fail(31, "runtime did not bind source-authored HIP pose " + id)
				return
			if str(weapon.get_meta("weapon_source_idle_psa", "")).is_empty():
				_fail(32, "runtime source idle PSA provenance missing " + id)
				return
			var source_scale := float(weapon.get_meta("weapon_viewmodel_scale_factor", 0.0))
			if absf(source_scale - 1.0) > 0.0001:
				_fail(34, "heuristic viewmodel scaling forbidden " + id + " scale=" + str(source_scale))
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
		var expected_pack_reserve := WeaponBalanceAAA.pack_reserve(id, -1)
		var expected_pack_interval := WeaponBalanceAAA.pack_fire_interval(id, -1.0)
		var expected_pack_name := WeaponBalanceAAA.pack_name(id, "")
		var expected_pack_row := WeaponBalanceAAA.source_row(id)
		var expected_pending := WeaponBalanceAAA.unsupported_changed_fields(id)
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
		if absf(float(pack_stats.get("fire_interval", -1.0)) - expected_pack_interval) > 0.0001:
			_fail(47, "PaP fire interval/RPM mismatch " + id)
			return
		if int(weapon.get("reserve_ammo")) != expected_pack_reserve:
			_fail(48, "PaP reserve mismatch " + id)
			return
		if str(pack_stats.get("display_name", "")) != expected_pack_name:
			_fail(49, "PaP source name mismatch " + id)
			return
		if str(pack_stats.get("pack_balance_authority", "")) != WeaponBalanceAAA.SOURCE_AUTHORITY:
			_fail(50, "PaP source authority mismatch " + id)
			return
		if int(pack_stats.get("pack_source_row", -1)) != expected_pack_row:
			_fail(51, "PaP source row mismatch " + id)
			return
		if bool(pack_stats.get("pack_source_runtime_complete", false)) != expected_pending.is_empty():
			_fail(52, "PaP pending-special-field accounting mismatch " + id)
			return

		if id == "mp40":
			print(
				"XZOGOT_AAA_MP40_SOURCE_RIG_GREEN hands=",
				weapon.get_meta("weapon_hands_asset", ""),
				" hip=", weapon.get_meta("weapon_source_hand_transform_position", Vector3.ZERO),
				" ads=", weapon.get_meta("weapon_source_ads_transform_position", Vector3.ZERO)
			)

		print(
			"XZOGOT_AAA_WEAPON_GREEN ",
			id,
			" ads=", ads_mode,
			" textures=", textured_surfaces,
			" hidden=", hidden_surfaces,
			" resolved=", resolved_surfaces, "/", texture_surfaces,
			" source_pose=", source_pose_ready,
			" source_psa=", str(weapon.get_meta("weapon_source_idle_psa", "")),
			" pap=", expected_pack_damage
		)

	print("XZOGOT_AAA_28_FIREARMS_GREEN 28")
	print("XZOGOT_AAA_WEAPON_RUNTIME_GATE_GREEN")
	scene.queue_free()
	await process_frame
	quit(0)
