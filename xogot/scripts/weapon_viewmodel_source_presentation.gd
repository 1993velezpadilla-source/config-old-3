class_name WeaponViewmodelSourcePresentation
extends RefCounted

const DATA_PATH := "res://data/weapon_viewmodel_source_presentation.json"
const MOVEMENT_DATA_PATH := "res://data/weapon_source_movement.json"
static var _cache: Dictionary = {}
static var _movement_cache: Dictionary = {}

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

static func _movement_data() -> Dictionary:
	if not _movement_cache.is_empty():
		return _movement_cache
	if not FileAccess.file_exists(MOVEMENT_DATA_PATH):
		return {}
	var f := FileAccess.open(MOVEMENT_DATA_PATH, FileAccess.READ)
	if f == null:
		return {}
	var parsed: Variant = JSON.parse_string(f.get_as_text())
	if parsed is Dictionary:
		_movement_cache = parsed as Dictionary
	return _movement_cache

static func movement_record(id: String) -> Dictionary:
	var weapons: Dictionary = _movement_data().get("weapons", {}) as Dictionary
	if not weapons.has(id):
		return {}
	return (weapons[id] as Dictionary).duplicate(true)

static func has_source_movement(id: String) -> bool:
	return not movement_record(id).is_empty()

static func record(id: String) -> Dictionary:
	var weapons: Dictionary = _data().get("weapons", {}) as Dictionary
	if not weapons.has(id):
		return {}
	return (weapons[id] as Dictionary).duplicate(true)

static func has_source_presentation(id: String) -> bool:
	return str(record(id).get("status", "")) == "source_datatable"

static func _vec3(values: Variant) -> Vector3:
	if not (values is Array):
		return Vector3.ZERO
	var a := values as Array
	if a.size() != 3:
		return Vector3.ZERO
	return Vector3(float(a[0]), float(a[1]), float(a[2]))

static func _quat(values: Variant) -> Quaternion:
	if not (values is Array):
		return Quaternion.IDENTITY
	var a := values as Array
	if a.size() != 4:
		return Quaternion.IDENTITY
	return Quaternion(float(a[0]), float(a[1]), float(a[2]), float(a[3])).normalized()

static func hip_position(id: String) -> Vector3:
	var rec := record(id)
	var t: Dictionary = rec.get("hand_transform_godot", {}) as Dictionary
	return _vec3(t.get("translation_m", []))

static func hip_rotation(id: String) -> Quaternion:
	var rec := record(id)
	var t: Dictionary = rec.get("hand_transform_godot", {}) as Dictionary
	return _quat(t.get("rotation_xyzw", []))

static func ads_position(id: String) -> Vector3:
	var rec := record(id)
	var t: Dictionary = rec.get("ads_transform_godot", {}) as Dictionary
	return _vec3(t.get("translation_m", []))

static func ads_rotation(id: String) -> Quaternion:
	var rec := record(id)
	var t: Dictionary = rec.get("ads_transform_godot", {}) as Dictionary
	return _quat(t.get("rotation_xyzw", []))

static func ads_in_time(id: String, fallback: float = 0.20) -> float:
	var source := movement_record(id)
	if source.has("ads_in"):
		return maxf(0.001, float(source["ads_in"]))
	return maxf(0.001, float(record(id).get("ads_in_time_s", fallback)))

static func ads_out_time(id: String, fallback: float = 0.20) -> float:
	var source := movement_record(id)
	if source.has("ads_out"):
		return maxf(0.001, float(source["ads_out"]))
	return maxf(0.001, float(record(id).get("ads_out_time_s", fallback)))

static func ads_fov_multiplier(id: String, fallback: float = 1.0) -> float:
	var source := movement_record(id)
	if source.has("ads_fov_mult"):
		return float(source["ads_fov_mult"])
	return float(record(id).get("ads_fov_multiplier", fallback))

static func source_table(id: String) -> String:
	return str(record(id).get("source_table", ""))

static func source_row_index(id: String) -> int:
	return int(record(id).get("source_row_index", -1))

static func source_runtime_profile(id: String) -> Dictionary:
	var rec := record(id)
	var profile: Variant = rec.get("source_runtime_profile", {})
	return (profile as Dictionary).duplicate(true) if profile is Dictionary else {}

static func source_movement_profile(id: String) -> Dictionary:
	var compact := movement_record(id)
	if not compact.is_empty():
		return {
			"MoveSpeedScale": float(compact.get("move_speed_scale", 1.0)),
			"AdsMoveSpeedScale": float(compact.get("ads_move_speed_scale", 1.0)),
			"SprintScale": float(compact.get("sprint_scale", 1.0)),
		}
	var profile := source_runtime_profile(id)
	var movement: Variant = profile.get("Movement", {})
	return (movement as Dictionary).duplicate(true) if movement is Dictionary else {}

static func source_ads_move_scale_raw(id: String) -> float:
	var movement := source_movement_profile(id)
	return float(movement.get("AdsMoveSpeedScale", -1.0))

static func source_ads_move_multiplier(id: String) -> float:
	var source_scale := source_ads_move_scale_raw(id)
	if source_scale <= 0.0:
		return -1.0
	# World at War applies a 50% ADS movement baseline; the per-weapon
	# adsMoveSpeedScale modifies it. Pistols carry 2.0, cancelling that loss.
	return 0.5 * source_scale
