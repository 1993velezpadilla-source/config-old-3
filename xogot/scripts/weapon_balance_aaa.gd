class_name WeaponBalanceAAA
extends RefCounted

# Kept under the original class name to avoid churn in call sites, but this is
# no longer authored balance. Every value is extracted from Project Aether's
# DT_WeaponsPAP table and tied to the matching DT_Weapons row.
const DATA_PATH := "res://data/weapon_balance_aaa.json"
const SOURCE_AUTHORITY := "Project Aether DT_WeaponsPAP"
static var _cache: Dictionary = {}

static func _table() -> Dictionary:
	if not _cache.is_empty():
		return _cache
	if not FileAccess.file_exists(DATA_PATH):
		return {}
	var file := FileAccess.open(DATA_PATH, FileAccess.READ)
	if file == null:
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if parsed is Dictionary:
		_cache = parsed as Dictionary
	return _cache

static func firearm_ids() -> Array[String]:
	var result: Array[String] = []
	var firearms: Dictionary = _table().get("weapons", {}) as Dictionary
	for id_var: Variant in firearms.keys():
		result.append(str(id_var))
	result.sort()
	return result

static func get_record(id: String) -> Dictionary:
	var firearms: Dictionary = _table().get("weapons", {}) as Dictionary
	if not firearms.has(id):
		return {}
	return (firearms[id] as Dictionary).duplicate(true)

static func pack_damage(id: String, fallback: float) -> float:
	return float(get_record(id).get("max_damage", fallback))

static func pack_min_damage(id: String, fallback: float) -> float:
	return float(get_record(id).get("min_damage", fallback))

static func pack_magazine(id: String, fallback: int) -> int:
	return int(get_record(id).get("clip_ammo", fallback))

static func pack_reserve(id: String, fallback: int) -> int:
	return int(get_record(id).get("reserve_ammo", fallback))

static func pack_fire_interval(id: String, fallback: float) -> float:
	var value := float(get_record(id).get("fire_interval_s", fallback))
	return maxf(0.001, value)

static func pack_pellets(id: String, fallback: int) -> int:
	return maxi(1, int(get_record(id).get("pellet_count", fallback)))

static func pack_name(id: String, fallback: String) -> String:
	return str(get_record(id).get("pap_name", fallback))

static func source_row(id: String) -> int:
	return int(get_record(id).get("row", -1))

static func pack_fire_type(id: String) -> String:
	return str(get_record(id).get("fire_type_enum", ""))

static func pack_burst_shots(id: String) -> int:
	return maxi(0, int(get_record(id).get("burst_shots", 0)))

static func pack_burst_delay(id: String) -> float:
	return maxf(0.0, float(get_record(id).get("burst_delay_s", 0.0)))

static func pack_shot_delay(id: String) -> float:
	return maxf(0.0, float(get_record(id).get("shot_delay_s", 0.0)))

static func pack_hyperburst_rpm(id: String) -> float:
	return maxf(0.0, float(get_record(id).get("hyperburst_rpm", 0.0)))

static func pack_hyperburst_bullets(id: String) -> int:
	return maxi(0, int(get_record(id).get("hyperburst_bullets", 0)))

static func unsupported_changed_fields(id: String) -> Array[String]:
	var out: Array[String] = []
	var raw: Array = get_record(id).get("unsupported_changed_fields", []) as Array
	for value: Variant in raw:
		out.append(str(value))
	return out

static func has_data(id: String) -> bool:
	return not get_record(id).is_empty()
