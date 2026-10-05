class_name WeaponBalanceAAA
extends RefCounted

const DATA_PATH := "res://data/weapon_balance_aaa.json"
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
	var firearms: Dictionary = _table().get("firearms", {}) as Dictionary
	for id_var: Variant in firearms.keys():
		result.append(str(id_var))
	result.sort()
	return result

static func get_record(id: String) -> Dictionary:
	var firearms: Dictionary = _table().get("firearms", {}) as Dictionary
	if not firearms.has(id):
		return {}
	return (firearms[id] as Dictionary).duplicate(true)

static func pack_damage(id: String, fallback: float) -> float:
	var rec := get_record(id)
	return float(rec.get("pack_damage", fallback))

static func pack_magazine(id: String, fallback: int) -> int:
	var rec := get_record(id)
	return int(rec.get("pack_magazine", fallback))

static func has_data(id: String) -> bool:
	return not get_record(id).is_empty()
