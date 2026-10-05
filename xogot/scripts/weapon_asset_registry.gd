class_name WeaponAssetRegistry
extends RefCounted

const MANIFEST_PATH := "res://assets/weapons/mapmod_weapon_asset_manifest.json"

static var _manifest_cache: Dictionary = {}
static var _inspection_cache: Dictionary = {}

static func _manifest() -> Dictionary:
	if not _manifest_cache.is_empty():
		return _manifest_cache
	if not FileAccess.file_exists(MANIFEST_PATH):
		return {}
	var file := FileAccess.open(MANIFEST_PATH, FileAccess.READ)
	if file == null:
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if parsed is Dictionary:
		_manifest_cache = parsed as Dictionary
	return _manifest_cache

static func weapon_ids() -> Array[String]:
	var result: Array[String] = []
	var root: Dictionary = _manifest()
	var weapons: Dictionary = root.get("weapons", {}) as Dictionary
	for id_var: Variant in weapons.keys():
		result.append(str(id_var))
	result.sort()
	return result

static func get_record(id: String) -> Dictionary:
	var weapons: Dictionary = _manifest().get("weapons", {}) as Dictionary
	if not weapons.has(id):
		return {}
	return (weapons[id] as Dictionary).duplicate(true)

static func source_status(id: String) -> String:
	return str(get_record(id).get("status", "MISSING"))

static func _forbidden_tokens() -> Array:
	return (_manifest().get("policy", {}) as Dictionary).get("forbidden_final_source_tokens", []) as Array

static func is_forbidden_final_path(path: String) -> bool:
	var lower := path.to_lower()
	for token_var: Variant in _forbidden_tokens():
		var token := str(token_var).to_lower()
		if not token.is_empty() and lower.contains(token):
			return true
	return false

static func _exists_approved(path: String) -> bool:
	return not path.is_empty() and not is_forbidden_final_path(path) and ResourceLoader.exists(path)

static func _collect_animation_names(node: Node, out: Array[String]) -> void:
	if node is AnimationPlayer:
		var player := node as AnimationPlayer
		for lib_name: StringName in player.get_animation_library_list():
			var lib: AnimationLibrary = player.get_animation_library(lib_name)
			if lib == null:
				continue
			for anim_name: StringName in lib.get_animation_list():
				var full_name: String = str(anim_name)
				if str(lib_name) != "":
					full_name = str(lib_name) + "/" + full_name
				out.append(full_name.to_lower())
	for child: Node in node.get_children():
		_collect_animation_names(child, out)

static func animation_names_for(id: String) -> Array[String]:
	var cache_key := id + ":animations"
	if _inspection_cache.has(cache_key):
		var cached_names: Array[String] = []
		for value: Variant in _inspection_cache[cache_key] as Array:
			cached_names.append(str(value))
		return cached_names
	var rec := get_record(id)
	var runtime: Dictionary = rec.get("runtime", {}) as Dictionary
	var path: String = str(runtime.get("viewmodel", ""))
	var names: Array[String] = []
	if _exists_approved(path):
		var packed := load(path) as PackedScene
		if packed != null:
			var instance := packed.instantiate()
			if instance != null:
				_collect_animation_names(instance, names)
				instance.free()
	_inspection_cache[cache_key] = names
	return names.duplicate()

static func _role_found(names: Array[String], aliases: Array) -> bool:
	for name: String in names:
		for alias_var: Variant in aliases:
			var alias := str(alias_var).to_lower()
			if not alias.is_empty() and name.contains(alias):
				return true
	return false

static func inspect(id: String) -> Dictionary:
	if _inspection_cache.has(id):
		return (_inspection_cache[id] as Dictionary).duplicate(true)
	var rec := get_record(id)
	if rec.is_empty():
		return {"id":id,"status":"MISSING","complete":false}

	var runtime: Dictionary = rec.get("runtime", {}) as Dictionary
	var audio: Dictionary = runtime.get("audio", {}) as Dictionary
	var vm_path: String = str(runtime.get("viewmodel", ""))
	var wm_path: String = str(runtime.get("worldmodel", ""))
	var vm_ok := _exists_approved(vm_path)
	var wm_ok := _exists_approved(wm_path)
	var fire_ok := _exists_approved(str(audio.get("fire", "")))
	var reload_ok := _exists_approved(str(audio.get("reload", "")))
	var mechanical_ok := _exists_approved(str(audio.get("mechanical", "")))
	var dry_ok := _exists_approved(str(audio.get("dry_fire", "")))

	var names: Array[String] = []
	if vm_ok:
		names = animation_names_for(id)
	var aliases: Dictionary = rec.get("required_animation_aliases", {}) as Dictionary
	var missing_roles: Array[String] = []
	for role_var: Variant in aliases.keys():
		var role := str(role_var)
		if not _role_found(names, aliases[role] as Array):
			missing_roles.append(role)
	var anim_ok := vm_ok and not aliases.is_empty() and missing_roles.is_empty()

	var runtime_complete := (
		vm_ok and wm_ok and anim_ok
		and fire_ok and reload_ok and mechanical_ok and dry_ok
	)
	var declared: String = str(rec.get("status", "MISSING"))
	var final_status: String = "MISSING"
	if runtime_complete and declared == "READY":
		final_status = "READY"
	elif vm_ok or wm_ok or anim_ok or fire_ok or reload_ok or mechanical_ok or dry_ok or declared == "REFERENCE_PARTIAL" or declared == "PARTIAL":
		final_status = "PARTIAL"

	var report := {
		"id": id,
		"declared_status": declared,
		"status": final_status,
		"complete": final_status == "READY",
		"viewmodel": vm_ok,
		"worldmodel": wm_ok,
		"animations": anim_ok,
		"animation_names": names,
		"missing_animation_roles": missing_roles,
		"fire_sfx": fire_ok,
		"reload_sfx": reload_ok,
		"mechanical_sfx": mechanical_ok,
		"dry_fire_sfx": dry_ok,
		"viewmodel_path": vm_path,
		"worldmodel_path": wm_path,
	}
	_inspection_cache[id] = report
	return report.duplicate(true)

static func _animation_role_score(role: String, animation_name: String, aliases: Array) -> int:
	var lower := animation_name.to_lower()
	var score := -100000
	for alias_var: Variant in aliases:
		var alias := str(alias_var).to_lower()
		if alias.is_empty() or not lower.contains(alias):
			continue
		score = maxi(score, 100 + alias.length())
	if score < 0:
		return score

	# Broad aliases such as "fire" and "reload" intentionally cover inconsistent
	# source naming, but they must not make hip-fire select ADS/last-shot clips or
	# a normal reload select empty/partial reload when a proper clip exists.
	match role:
		"fire":
			if lower.contains("ads"):
				score -= 120
			if lower.contains("lastshot") or lower.contains("lastfire"):
				score -= 120
			if lower.contains("_fire") or lower.ends_with("fire"):
				score += 28
			if lower.contains("shoot"):
				score += 18
		"fire_ads":
			if lower.contains("ads"):
				score += 100
			else:
				score -= 150
		"lastshot":
			if lower.contains("lastshot") or lower.contains("lastfire"):
				score += 120
		"reload":
			# WaW Colt names its ordinary tactical reload "reload_notempty".
			# Do not classify the "empty" substring inside "notempty" as an
			# empty-mag reload.
			var is_notempty := lower.contains("notempty") or lower.contains("not_empty")
			var is_empty := (lower.contains("empty") and not is_notempty)
			if lower.contains("reload") and not is_empty and not lower.contains("partial"):
				score += 70
			if is_empty:
				score -= 120
			if lower.contains("partial"):
				score -= 55
			if lower.contains("rechamber"):
				score -= 20
		"reload_empty":
			var is_notempty := lower.contains("notempty") or lower.contains("not_empty")
			if lower.contains("reload") and lower.contains("empty") and not is_notempty:
				score += 120
			else:
				score -= 140
		"equip":
			if lower.contains("equip"):
				score += 80
			elif lower.contains("pullout") or lower.contains("bringout"):
				score += 65
			elif lower.contains("raise"):
				score += 30
		"idle":
			if lower.ends_with("idle") or lower.contains("_idle"):
				score += 45
	return score

static func animation_name_for_role(id: String, role: String) -> String:
	var rec := get_record(id)
	var required: Dictionary = rec.get("required_animation_aliases", {}) as Dictionary
	var optional: Dictionary = rec.get("optional_animation_aliases", {}) as Dictionary
	var role_aliases: Array = []
	if required.has(role):
		role_aliases = required[role] as Array
	elif optional.has(role):
		role_aliases = optional[role] as Array
	else:
		return ""

	var best_name := ""
	var best_score := -100000
	for name: String in animation_names_for(id):
		var score := _animation_role_score(role, name, role_aliases)
		if score > best_score:
			best_score = score
			best_name = name
	return best_name if best_score >= 0 else ""

static func preferred_worldmodel_path(id: String, fallback: String = "") -> String:
	var report := inspect(id)
	var path := str(report.get("worldmodel_path", ""))
	return path if bool(report.get("worldmodel", false)) else fallback

static func preferred_viewmodel_path(id: String, fallback: String = "") -> String:
	var report := inspect(id)
	var path := str(report.get("viewmodel_path", ""))
	return path if bool(report.get("viewmodel", false)) else fallback

static func preferred_audio_path(id: String, role: String, fallback: String = "") -> String:
	var rec := get_record(id)
	var runtime: Dictionary = rec.get("runtime", {}) as Dictionary
	var audio: Dictionary = runtime.get("audio", {}) as Dictionary
	var path := str(audio.get(role, ""))
	return path if _exists_approved(path) else fallback

static func lab_status_text(id: String) -> String:
	var r := inspect(id)
	var source := source_status(id)
	var sfx_count := 0
	for key: String in ["fire_sfx","reload_sfx","mechanical_sfx","dry_fire_sfx"]:
		if bool(r.get(key, false)):
			sfx_count += 1
	return "%s | VM %s WM %s | ANIM %s | SFX %d/4" % [
		source,
		"OK" if bool(r.get("viewmodel", false)) else "—",
		"OK" if bool(r.get("worldmodel", false)) else "—",
		"OK" if bool(r.get("animations", false)) else "—",
		sfx_count,
	]

static func clear_cache() -> void:
	_inspection_cache.clear()
