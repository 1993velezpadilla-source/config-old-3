class_name WeaponViewmodelSourcePose
extends RefCounted

const DATA_PATH := "res://data/weapon_viewmodel_source_pose.json"
static var _cache: Dictionary = {}

static func _data() -> Dictionary:
	if not _cache.is_empty():
		return _cache
	if not FileAccess.file_exists(DATA_PATH):
		return {}
	var f := FileAccess.open(DATA_PATH, FileAccess.READ)
	if f == null:
		return {}
	var parsed: Variant = JSON.parse_string(f.get_as_text())
	if parsed is Dictionary:
		_cache = parsed as Dictionary
	return _cache

static func record(id: String) -> Dictionary:
	var weapons: Dictionary = _data().get("weapons", {}) as Dictionary
	if not weapons.has(id):
		return {}
	return (weapons[id] as Dictionary).duplicate(true)

static func has_source_hip_pose(id: String) -> bool:
	var rec := record(id)
	return (
		str(rec.get("status", "")) == "source_authored"
		and (rec.get("godot_position_m", []) as Array).size() == 3
	)

static func hip_position(id: String) -> Vector3:
	var rec := record(id)
	var a: Array = rec.get("godot_position_m", []) as Array
	if a.size() != 3:
		return Vector3.ZERO
	return Vector3(float(a[0]), float(a[1]), float(a[2]))

static func source_idle_psa(id: String) -> String:
	return str(record(id).get("idle_psa", ""))

static func status(id: String) -> String:
	return str(record(id).get("status", "missing"))

static func authored_count() -> int:
	return int(_data().get("source_authored_count", 0))
