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
