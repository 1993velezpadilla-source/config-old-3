extends SceneTree
const SourcePresentation = preload("res://scripts/weapon_viewmodel_source_presentation.gd")
func _init() -> void:
	call_deferred("_test")
func _fail(n: int, reason: String) -> void:
	push_error("CHURCH_HANDS_ADS_PROBE: "+reason)
	quit(n)
func _test() -> void:
	var packed: PackedScene = load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(2,"Church scene missing")
		return
	var church: Node = packed.instantiate()
	root.add_child(church)
	await process_frame
	await physics_frame
	var player: Node = church.get_node_or_null("Player")
	var weapon: Node = church.get_node_or_null("Player/Weapon")
	if player == null or weapon == null:
		_fail(3,"Church gun/player missing")
		return
	for id: String in ["colt","mp40"]:
		if not bool(weapon.call("equip_weapon",id,true)):
			_fail(4,"Real gun unavailable "+id)
			return
		await process_frame
		if not bool(weapon.get_meta("weapon_source_weapon_attachment_ready",false)):
			_fail(5,"tag_weapon not attached: "+id)
			return
		if not bool(weapon.get_meta("weapon_hands_animation_ready",false)):
			_fail(6,"Actual hand PSAs not mounted: "+id)
			return
		if bool(weapon.get_meta("weapon_view_fallback",true)):
			_fail(7,"Procedural firearm substituted: "+id)
			return
		var model: Node3D = weapon.get("_weapon_model_root") as Node3D
		if model == null or model.get_parent() == null or model.get_parent().name != "SourceTagWeapon":
			_fail(8,"Model not parented under actual animated hand socket: "+id)
			return
		print("XZOGOT_CHURCH_"+id.to_upper()+"_SOURCE_HANDS_GRIP_GREEN")
	if not SourcePresentation.has_source_presentation("mp40"):
		_fail(9,"Exact prior DT_Weapons MP40 ADS table not mounted")
		return
	var target: Vector3 = SourcePresentation.ads_position("mp40")
	var declared: Vector3 = weapon.get_meta("weapon_source_ads_transform_position",Vector3.ZERO)
	if target.distance_to(declared)>0.00001:
		_fail(10,"ADS position differs from recovered source table")
		return
	if str(weapon.get_meta("weapon_ads_calibration_mode",""))!="source_datatable":
		_fail(11,"MP40 did not select source-authored ADS instead of guess")
		return
	player.set_meta("ads_toggled",true)
	weapon.call("_update_visual_recoil",0.22)
	var modelroot: Node3D = weapon.get("_view_root") as Node3D
	if modelroot==null or modelroot.position.distance_to(target)>0.002:
		_fail(12,"ADS physically fails to move source hands/gun rig to exact target")
		return
	if absf(float(weapon.get_meta("weapon_ads_pose_alpha",0))-1.0)>0.001:
		_fail(13,"ADS did not reach center")
		return
	print("XZOGOT_CHURCH_MP40_DTWEAPONS_ADS_TRANSFORM_GREEN ",target)
	player.set_meta("ads_toggled",false)
	weapon.call("_update_visual_recoil",0.22)
	if modelroot.position.distance_to(SourcePresentation.hip_position("mp40"))>0.002:
		_fail(14,"ADS exit does not return to authored hip")
		return
	print("XZOGOT_CHURCH_MP40_AUTHORED_ADS_HIP_LOOP_GREEN")
	church.queue_free()
	await process_frame
	quit(0)
