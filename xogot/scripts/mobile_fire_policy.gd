extends RefCounted

# Keep mobile touch emulation from posing as a desktop mouse click.
# Semi-auto source RPM (e.g. Colt M1911 = 1200 trigger RPM / 0.05 s)
# is NOT an appropriate held-touch auto-repeat rate.
# This cap applies only to the OPTIONAL mobile pistol hold assist;
# source weapon RPM and desktop/physical trigger timing remain unchanged.
const MIN_TOUCH_PISTOL_INTERVAL_S := 0.22

static func accepts_desktop_mouse_trigger(mobile_platform: bool) -> bool:
	return not mobile_platform

static func effective_fire_interval(
	source_interval_s: float,
	weapon_family: String,
	mobile_pistol_hold_assist: bool
) -> float:
	var interval := maxf(source_interval_s, 0.001)
	if mobile_pistol_hold_assist and weapon_family == "pistol":
		return maxf(interval, MIN_TOUCH_PISTOL_INTERVAL_S)
	return interval
