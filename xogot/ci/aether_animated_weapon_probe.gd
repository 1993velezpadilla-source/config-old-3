extends SceneTree

const WeaponAssetRegistry = preload("res://scripts/weapon_asset_registry.gd")
const INVENTORY_PATH := "res://assets/weapons/aether_waw_real/animated-inventory.json"
const REQUIRED_ROLES := ["idle", "fire", "reload", "equip"]

func _fail(code: int, message: String) -> void:
	push_error("AETHER_ANIMATED_WEAPON_PROBE: " + message)
	quit(code)

func _load_json(path: String) -> Dictionary:
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		return {}
	var parsed: Variant = JSON.parse_string(f.get_as_text())
	return parsed as Dictionary if parsed is Dictionary else {}

func _initialize() -> void:
	var inv := _load_json(INVENTORY_PATH)
	if inv.is_empty():
		_fail(2, "animated inventory missing or invalid")
		return

	var weapons: Array = inv.get("weapons", []) as Array
	if int(inv.get("weapon_count", 0)) != 29:
		_fail(3, "expected 29 recovered Aether entries")
		return
	if int(inv.get("animated_weapon_count", 0)) != 28:
		_fail(4, "expected 28 animated firearms")
		return

	var checked := 0
	var total_animations := 0
	for item_var: Variant in weapons:
		var item := item_var as Dictionary
		var weapon_id := str(item.get("runtime_id", ""))
		if weapon_id == "stielhand":
			if int(item.get("animations", -1)) != 0:
				_fail(5, "Stielhand throwable unexpectedly has firearm animations")
				return
			continue

		var animation_count := int(item.get("animations", 0))
		if animation_count < 1:
			_fail(6, "%s has no embedded animations" % weapon_id)
			return
		total_animations += animation_count

		var names := WeaponAssetRegistry.animation_names_for(weapon_id)
		if names.is_empty():
			_fail(7, "%s imported GLB exposes no animations in Godot" % weapon_id)
			return

		for role: String in REQUIRED_ROLES:
			var resolved := WeaponAssetRegistry.animation_name_for_role(weapon_id, role)
			if resolved.is_empty():
				_fail(8, "%s missing runtime animation role %s; names=%s" % [weapon_id, role, names])
				return
			print("XZOGOT_AETHER_ROLE_GREEN ", weapon_id, " ", role, " -> ", resolved)

		var hip_fire := WeaponAssetRegistry.animation_name_for_role(weapon_id, "fire")
		var hip_fire_lower := hip_fire.to_lower()
		var has_clean_fire := false
		for candidate: String in names:
			var lower := candidate.to_lower()
			if lower.contains("fire") and not lower.contains("ads") and not lower.contains("lastshot") and not lower.contains("lastfire"):
				has_clean_fire = true
				break
		if has_clean_fire and (hip_fire_lower.contains("ads") or hip_fire_lower.contains("lastshot") or hip_fire_lower.contains("lastfire")):
			_fail(12, "%s hip-fire resolved wrong variant: %s" % [weapon_id, hip_fire])
			return

		var normal_reload := WeaponAssetRegistry.animation_name_for_role(weapon_id, "reload")
		var normal_reload_lower := normal_reload.to_lower()
		var has_clean_reload := false
		for candidate: String in names:
			var lower := candidate.to_lower()
			if lower.contains("reload") and not lower.contains("empty") and not lower.contains("partial"):
				has_clean_reload = true
				break
		if has_clean_reload and (normal_reload_lower.contains("empty") or normal_reload_lower.contains("partial")):
			_fail(13, "%s normal reload resolved wrong variant: %s" % [weapon_id, normal_reload])
			return
		print("XZOGOT_AETHER_VARIANT_RESOLUTION_GREEN ", weapon_id, " fire=", hip_fire, " reload=", normal_reload)

		var report := WeaponAssetRegistry.readiness_for(weapon_id)
		if not bool(report.get("animations", false)):
			_fail(9, "%s registry animation readiness is false: %s" % [weapon_id, report])
			return

		checked += 1
		print("XZOGOT_AETHER_ANIMATED_WEAPON_GREEN ", weapon_id, " anims=", animation_count)

	if checked != 28:
		_fail(10, "expected 28 checked firearms, got %d" % checked)
		return
	if total_animations < 500:
		_fail(11, "animation total unexpectedly low: %d" % total_animations)
		return

	print("XZOGOT_AETHER_28_FIREARMS_GODOT_GREEN ", checked)
	print("XZOGOT_AETHER_538_ANIMATIONS_GODOT_GREEN ", total_animations)
	print("XZOGOT_AETHER_ANIMATED_WEAPON_GATE_GREEN")
	quit(0)
