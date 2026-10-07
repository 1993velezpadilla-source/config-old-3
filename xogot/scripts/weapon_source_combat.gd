class_name WeaponSourceCombat
extends RefCounted

const DATA_PATH := "res://data/weapon_source_combat.json"
const SOURCE_AUTHORITY := "Project Aether DT_Weapons"
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
	var out: Array[String] = []
	var rows: Dictionary = _table().get("weapons", {}) as Dictionary
	for id_var: Variant in rows.keys():
		out.append(str(id_var))
	out.sort()
	return out

static func get_record(id: String) -> Dictionary:
	var rows: Dictionary = _table().get("weapons", {}) as Dictionary
	if not rows.has(id):
		return {}
	return (rows[id] as Dictionary).duplicate(true)

static func has_data(id: String) -> bool:
	return not get_record(id).is_empty()

static func source_row(id: String) -> int:
	return int(get_record(id).get("row", -1))

static func source_name(id: String, fallback: String = "") -> String:
	return str(get_record(id).get("source_name", fallback))

static func base_damage(id: String, fallback: float) -> float:
	return float(get_record(id).get("max_damage", fallback))

static func base_min_damage(id: String, fallback: float) -> float:
	return float(get_record(id).get("min_damage", fallback))

static func base_fire_interval(id: String, fallback: float) -> float:
	return maxf(0.001, float(get_record(id).get("fire_interval_s", fallback)))

static func base_magazine(id: String, fallback: int) -> int:
	return maxi(1, int(get_record(id).get("clip_ammo", fallback)))

static func base_reserve(id: String, fallback: int) -> int:
	return maxi(0, int(get_record(id).get("reserve_ammo", fallback)))

static func base_select_fire(id: String) -> String:
	return str(get_record(id).get("select_fire", ""))

static func base_is_automatic(id: String, fallback: bool) -> bool:
	match base_select_fire(id):
		"E_FireType::NewEnumerator1":
			return true
		"E_FireType::NewEnumerator0":
			return false
		_:
			return fallback

static func base_pellets(id: String, fallback: int) -> int:
	return maxi(1, int(get_record(id).get("pellet_count", fallback)))
