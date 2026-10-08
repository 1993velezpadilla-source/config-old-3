class_name SourceModifierPolicy
extends RefCounted

# Source-backed Zombies gameplay modifiers.
# Double Tap values below are decoded directly from Project Aether's
# BP_WeaponBase Kismet bytecode; other perk values retain their COD source
# contracts until equivalent Aether bytecode is recovered.
const AUTHORITY := "COD_CLASSIC_DVAR_AND_BO3_ZOMBIES"

const JUGGERNOG_MAX_HEALTH := 250.0
const SPEED_COLA_RELOAD_TIME_MULTIPLIER := 0.50
const STAMIN_UP_MOVE_SPEED_MULTIPLIER := 1.07
const STAMIN_UP_SPRINT_ENDURANCE_MULTIPLIER := 2.0
const DEADSHOT_SPREAD_MULTIPLIER := 0.65
const DOUBLE_TAP_INTERVAL_MULTIPLIER := 0.77
const DOUBLE_TAP_PROJECTILE_DAMAGE_MULTIPLIER := 1.0
const QUICK_REVIVE_TIME_MULTIPLIER := 0.50

const SOURCE_PERK_BY_RUNTIME_ID: Dictionary = {
	"martyrs_blood": "juggernog",
	"quick_hands": "speed_cola",
	"pilgrim_rush": "stamin_up",
	"choir_sight": "deadshot_daiquiri",
	"twin_bells": "double_tap_ii",
	"last_rites": "quick_revive",
}

static func source_perk(runtime_id: String) -> String:
	return str(SOURCE_PERK_BY_RUNTIME_ID.get(runtime_id, ""))

static func fire_interval_multiplier(has_double_tap: bool) -> float:
	return DOUBLE_TAP_INTERVAL_MULTIPLIER if has_double_tap else 1.0

static func projectile_damage_multiplier(has_double_tap: bool, weapon_family: String) -> float:
	if not has_double_tap:
		return 1.0
	# Project Aether BP_WeaponBase::DoubleTapDamage multiplies both MaxDamage
	# and MinDamage by 1.0 when perk index 3 is active. No damage buff here.
	return DOUBLE_TAP_PROJECTILE_DAMAGE_MULTIPLIER

static func reload_time_multiplier(has_speed_cola: bool) -> float:
	return SPEED_COLA_RELOAD_TIME_MULTIPLIER if has_speed_cola else 1.0

static func movement_speed_multiplier(has_stamin_up: bool) -> float:
	return STAMIN_UP_MOVE_SPEED_MULTIPLIER if has_stamin_up else 1.0

static func spread_multiplier(has_deadshot: bool) -> float:
	return DEADSHOT_SPREAD_MULTIPLIER if has_deadshot else 1.0

static func revive_progress_multiplier(has_quick_revive: bool) -> float:
	if not has_quick_revive:
		return 1.0
	return 1.0 / QUICK_REVIVE_TIME_MULTIPLIER
