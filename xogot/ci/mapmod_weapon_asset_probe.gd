extends SceneTree

const WeaponCatalog = preload("res://scripts/weapon_catalog.gd")
const WeaponAssetRegistry = preload("res://scripts/weapon_asset_registry.gd")

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("MAPMOD_WEAPON_PROBE: " + message)
	quit(code)

func _run() -> void:
	var manifest_path := "res://assets/weapons/mapmod_weapon_asset_manifest.json"
	if not FileAccess.file_exists(manifest_path):
		_fail(2, "MapMod weapon manifest missing")
		return

	var f := FileAccess.open(manifest_path, FileAccess.READ)
	var parsed: Variant = JSON.parse_string(f.get_as_text())
	if not (parsed is Dictionary):
		_fail(3, "MapMod weapon manifest invalid JSON")
		return
	var manifest := parsed as Dictionary
	var weapons: Dictionary = manifest.get("weapons", {}) as Dictionary
	var policy: Dictionary = manifest.get("policy", {}) as Dictionary

	if int(manifest.get("weapon_count", 0)) != WeaponCatalog.WEAPONS.size():
		_fail(4, "weapon_count differs from WeaponCatalog")
		return
	if weapons.size() != WeaponCatalog.WEAPONS.size():
		_fail(5, "manifest weapon table differs from WeaponCatalog")
		return

	var required_roles: Array = policy.get("required_animation_roles", []) as Array
	for role: String in ["idle","fire","reload","equip"]:
		if not required_roles.has(role):
			_fail(6, "required core animation role missing: " + role)
			return
	var optional_roles: Array = policy.get("optional_animation_roles", []) as Array
	for role: String in ["ads_in","ads_out","lower","melee","fire_ads","reload_empty","lastshot"]:
		if not optional_roles.has(role):
			_fail(6, "optional authored animation role missing from policy: " + role)
			return

	var final_requirements: Array = policy.get("final_ready_requires", []) as Array
	for requirement: String in [
		"viewmodel","worldmodel","animations","fire_sfx",
		"reload_sfx","mechanical_sfx","dry_fire_sfx"
	]:
		if not final_requirements.has(requirement):
			_fail(7, "final-ready requirement missing: " + requirement)
			return

	var ready_count: int = 0
	var partial_count: int = 0
	var missing_count: int = 0

	for id_var: Variant in WeaponCatalog.WEAPONS.keys():
		var id := str(id_var)
		if not weapons.has(id):
			_fail(8, "catalog weapon absent from MapMod manifest: " + id)
			return

		var rec := weapons[id] as Dictionary
		var source_lane := str(rec.get("desired_source_lane", ""))
		if source_lane not in ["cod_zombies_mapmod", "project_aether_waw_real"]:
			_fail(9, "unapproved desired source lane for %s: %s" % [id, source_lane])
			return
		if source_lane == "project_aether_waw_real":
			var aether_vm := str((rec.get("runtime", {}) as Dictionary).get("viewmodel", ""))
			if not aether_vm.begins_with("res://assets/weapons/aether_waw_real/"):
				_fail(9, "Aether source lane points outside real Aether weapon tree: " + id)
				return

		var runtime: Dictionary = rec.get("runtime", {}) as Dictionary
		var audio: Dictionary = runtime.get("audio", {}) as Dictionary
		var paths: Array[String] = [
			str(runtime.get("viewmodel", "")),
			str(runtime.get("worldmodel", "")),
			str(audio.get("fire", "")),
			str(audio.get("reload", "")),
			str(audio.get("mechanical", "")),
			str(audio.get("dry_fire", "")),
		]
		for path: String in paths:
			if WeaponAssetRegistry.is_forbidden_final_path(path):
				_fail(10, "forbidden Quake/NZP final path for %s: %s" % [id, path])
				return

		var aliases: Dictionary = rec.get("required_animation_aliases", {}) as Dictionary
		var optional_aliases: Dictionary = rec.get("optional_animation_aliases", {}) as Dictionary
		for role: String in required_roles:
			if not aliases.has(role) or (aliases[role] as Array).is_empty():
				_fail(11, "core animation aliases missing for %s/%s" % [id, role])
				return
		for role: String in optional_roles:
			if optional_aliases.has(role) and (optional_aliases[role] as Array).is_empty():
				_fail(11, "optional animation aliases empty for %s/%s" % [id, role])
				return

		var report := WeaponAssetRegistry.inspect(id)
		var declared := str(rec.get("status", "MISSING"))
		if declared == "READY":
			ready_count += 1
			if not bool(report.get("complete", false)):
				_fail(12, "weapon declared READY without complete package: " + id)
				return
		elif declared in ["PARTIAL","REFERENCE_PARTIAL"]:
			partial_count += 1
			if bool(report.get("complete", false)):
				_fail(13, "partial weapon incorrectly surfaced READY: " + id)
				return
		else:
			missing_count += 1

	var thompson: Dictionary = weapons.get("thompson", {}) as Dictionary
	if str(thompson.get("status", "")) != "REFERENCE_PARTIAL":
		_fail(14, "Thompson reference must remain partial until MapMod package is verified")
		return
	var reference: Dictionary = thompson.get("reference", {}) as Dictionary
	var reference_anims: Array = reference.get("animations", []) as Array
	if reference_anims.size() != 11:
		_fail(15, "Thompson golden reference animation count changed")
		return
	if bool(reference.get("audio_verified", true)):
		_fail(16, "Thompson reference audio must not be claimed verified")
		return

	var packed: PackedScene = load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(17, "main scene missing")
		return
	var scene := packed.instantiate()
	root.add_child(scene)
	await process_frame
	var settings: Node = scene.get_node_or_null("HUD/MobileSettings")
	if settings == null:
		_fail(18, "DEV lab missing")
		return
	var thompson_button := settings.find_child("Weapon_thompson", true, false) as Button
	if thompson_button == null:
		_fail(19, "Thompson DEV lab button missing")
		return
	if not thompson_button.text.contains("REFERENCE_PARTIAL"):
		_fail(20, "DEV lab does not expose Thompson partial status")
		return
	if not thompson_button.text.contains("ANIM"):
		_fail(21, "DEV lab does not expose animation readiness")
		return

	print(
		"XZOGOT_MAPMOD_WEAPON_GATE_GREEN total=",
		weapons.size(),
		" ready=", ready_count,
		" partial=", partial_count,
		" missing=", missing_count
	)
	print("XZOGOT_QUAKE_FINAL_WEAPONS_BLOCKED")
	print("XZOGOT_THOMPSON_REFERENCE_PARTIAL_LOCKED")
	scene.queue_free()
	await process_frame
	quit(0)
