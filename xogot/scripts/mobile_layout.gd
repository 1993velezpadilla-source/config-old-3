extends RefCounted

# Canonical COD-style mobile HUD layout recovered from the original XZIEL mobile audits.
const JOY_CENTER := Vector2(0.170, 0.740)
const FIRE_CENTER := Vector2(0.885, 0.585)
const ADSFIRE_CENTER := Vector2(0.795, 0.435)
const ADS_CENTER := Vector2(0.695, 0.575)
const RELOAD_CENTER := Vector2(0.805, 0.785)
const USE_CENTER := Vector2(0.605, 0.675)
const JUMP_CENTER := Vector2(0.695, 0.790)
const SLIDE_CENTER := Vector2(0.745, 0.825)
const KNIFE_CENTER := Vector2(0.915, 0.800)
const PAUSE_CENTER := Vector2(0.965, 0.075)
const GRENADE_CENTER := Vector2(0.835, 0.300)

const JOY_RADIUS := 0.120
const JOY_VISUAL_RADIUS := 0.095
const FIRE_RADIUS := 0.073
const ADSFIRE_RADIUS := 0.056
const ADS_RADIUS := 0.047
const RELOAD_RADIUS := 0.044
const USE_RADIUS := 0.050
const JUMP_RADIUS := 0.044
const SLIDE_RADIUS := 0.044
const KNIFE_RADIUS := 0.044
const PAUSE_RADIUS := 0.036
const GRENADE_RADIUS := 0.041

static func screen_point(center: Vector2, viewport_size: Vector2) -> Vector2:
	return Vector2(center.x * viewport_size.x, center.y * viewport_size.y)

static func inside(pixel_point: Vector2, viewport_size: Vector2, center: Vector2, radius_h: float) -> bool:
	var c: Vector2 = screen_point(center, viewport_size)
	var radius_px: float = radius_h * viewport_size.y
	return pixel_point.distance_squared_to(c) <= radius_px * radius_px


# Every control keeps its source COD-style default until the player explicitly
# changes it. Shared static state is used by both hit tests and HUD rendering.
const LAYOUT_CONFIG_PATH := "user://xogot_touch_hud_layout.cfg"
static var _custom_centers: Dictionary = {}

static func control_keys() -> PackedStringArray:
	return PackedStringArray([
		"joy", "fire", "adsfire", "ads", "reload", "use",
		"jump", "slide", "knife", "pause", "grenade"
	])

static func default_center(key: String) -> Vector2:
	match key:
		"joy": return JOY_CENTER
		"fire": return FIRE_CENTER
		"adsfire": return ADSFIRE_CENTER
		"ads": return ADS_CENTER
		"reload": return RELOAD_CENTER
		"use": return USE_CENTER
		"jump": return JUMP_CENTER
		"slide": return SLIDE_CENTER
		"knife": return KNIFE_CENTER
		"pause": return PAUSE_CENTER
		"grenade": return GRENADE_CENTER
	return Vector2(-1.0, -1.0)

static func control_radius(key: String) -> float:
	match key:
		"joy": return JOY_RADIUS
		"fire": return FIRE_RADIUS
		"adsfire": return ADSFIRE_RADIUS
		"ads": return ADS_RADIUS
		"reload": return RELOAD_RADIUS
		"use": return USE_RADIUS
		"jump": return JUMP_RADIUS
		"slide": return SLIDE_RADIUS
		"knife": return KNIFE_RADIUS
		"pause": return PAUSE_RADIUS
		"grenade": return GRENADE_RADIUS
	return 0.0

static func center_for(key: String) -> Vector2:
	var default_position := default_center(key)
	if default_position.x < 0.0:
		return default_position
	if _custom_centers.has(key):
		var position: Vector2 = _custom_centers[key]
		return position
	return default_position

static func set_center(key: String, normalized: Vector2) -> bool:
	if default_center(key).x < 0.0 or not normalized.is_finite():
		return false
	# Keep buttons reachable above navigation bars, cut-outs and rounded edges.
	_custom_centers[key] = Vector2(
		clampf(normalized.x, 0.055, 0.945),
		clampf(normalized.y, 0.07, 0.93)
	)
	return true

static func reset_centers() -> void:
	_custom_centers.clear()

static func snapshot() -> Dictionary:
	return _custom_centers.duplicate(true)

static func restore_snapshot(value: Dictionary) -> void:
	reset_centers()
	for key: String in control_keys():
		if value.has(key) and value[key] is Vector2:
			set_center(key, value[key])

static func save_centers() -> Error:
	var cfg := ConfigFile.new()
	for key: String in control_keys():
		if _custom_centers.has(key):
			cfg.set_value("positions", key, _custom_centers[key])
	return cfg.save(LAYOUT_CONFIG_PATH)

static func load_centers() -> void:
	reset_centers()
	var cfg := ConfigFile.new()
	if cfg.load(LAYOUT_CONFIG_PATH) != OK:
		return
	for key: String in control_keys():
		var raw: Variant = cfg.get_value("positions", key, null)
		if raw is Vector2:
			set_center(key, raw)

static func inside_control(pixel_point: Vector2, viewport_size: Vector2, key: String) -> bool:
	var radius := control_radius(key)
	if radius <= 0.0:
		return false
	return inside(pixel_point, viewport_size, center_for(key), radius)
