extends SceneTree

# Real Godot main-scene acceptance for WaW scoped rifles. HIP and reload must
# show the original viewmodel; full ADS must display a shared original-art
# multiplayer-style sniper scope overlay and hide the opaque 3D scope tube.
# FOV, recoil, hands, source DT_Weapons and original GLBs remain unchanged.
const OUT := "/tmp/xogot-source-sniper-overlay"

func _init() -> void:
	call_deferred("_run")

func _fail(s: String) -> void:
	push_error("XZOGOT_SOURCE_SNIPER_SCOPE_OVERLAY_RED " + s)
	quit(3)

func _frame(s: String) -> bool:
	await process_frame
	await process_frame
	var picture: Image = root.get_texture().get_image()
	return picture != null and not picture.is_empty() and picture.save_png(OUT + "/" + s + ".png") == OK

func _run() -> void:
	DirAccess.make_dir_recursive_absolute(OUT)
	var source: PackedScene = load("res://main.tscn") as PackedScene
	if source == null:
		_fail("real main game scene unavailable")
		return
	var scene: Node = source.instantiate()
	root.add_child(scene)
	var player := scene.get_node_or_null("Player")
	var gun := scene.get_node_or_null("Player/Weapon")
	var mobile_hud := scene.get_node_or_null("HUD/MobileHUD")
	if player == null or gun == null or mobile_hud == null:
		_fail("authentic game player / gun / HUD not instantiated")
		return
	var mask: ColorRect = mobile_hud.get_node_or_null("SourceSniperScopeMask") as ColorRect
	if mask == null or mask.material == null or mask.mouse_filter != Control.MOUSE_FILTER_IGNORE:
		_fail("transparent touch-safe shader scope overlay missing")
		return
	var total := 0
	for id in ["mosin", "ptrs", "mp40"]:
		player.set_meta("ads_toggled", false)
		if not bool(gun.call("equip_weapon", id, true)):
			_fail("cannot equip real source weapon " + id)
			return
		await create_timer(0.8).timeout
		var view: Node3D = gun.get("_view_root") as Node3D
		if view == null or not view.visible or mask.visible:
			_fail("HIP must keep authentic 3D model visible and overlay off: " + id)
			return
		if not await _frame(id + "-hip-original"):
			_fail("original HIP PNG missing " + id)
			return
		total += 1
		player.set_meta("ads_toggled", true)
		await create_timer(0.85).timeout
		var is_scoped := id in ["mosin", "ptrs"]
		if mask.visible != is_scoped:
			_fail("scope overlay state wrong in ADS " + id)
			return
		if view.visible == is_scoped or bool(gun.get_meta("weapon_scope_viewmodel_masked", false)) != is_scoped:
			_fail("original gun mesh must be masked only for scope reticle " + id)
			return
		if not await _frame(id + "-ads-real-scope"):
			_fail("scoped ADS PNG missing " + id)
			return
		total += 1
		player.set_meta("ads_toggled", false)
		await create_timer(0.85).timeout
		if mask.visible or not view.visible:
			_fail("original scope HUD and viewmodel not restored after ADS " + id)
			return
		print("XZOGOT_WAW_SNIPER_SOURCE_SCOPE_TRANSITION_GREEN id=", id,
			" full_scope=", is_scoped, " original_reload_and_hip_mesh_preserved=true")
	if total != 6:
		_fail("expected six actual original main-scene HIP/ADS screenshots, got " + str(total))
		return
	print("XZOGOT_WAW_SNIPER_SCOPE_OVERLAY_GREEN frames=6 original_mobile_hud_touch_safe=true MP40_unmodified=true")
	quit(0)
