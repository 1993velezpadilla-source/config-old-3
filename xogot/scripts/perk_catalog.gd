class_name PerkCatalog
extends RefCounted

const PERKS: Dictionary = {
	"martyrs_blood": {
		"display_name": "JUGGER-NOG",
		"price": 2500,
		"description": "Source behavior: raises maximum health to 250.",
		"source_perk": "juggernog",
		"source_authority": "COD_ZOMBIES_CLASSIC_BO3",
		"machine_color": [0.48, 0.055, 0.045],
	},
	"quick_hands": {
		"display_name": "SPEED COLA",
		"price": 3000,
		"description": "Source behavior: reload time multiplier 0.50.",
		"source_perk": "speed_cola",
		"source_authority": "perk_weapReloadMultiplier",
		"machine_color": [0.12, 0.38, 0.52],
	},
	"pilgrim_rush": {
		"display_name": "STAMIN-UP",
		"price": 2000,
		"description": "Source behavior: +7% movement speed; 2x sprint endurance when endurance exists.",
		"source_perk": "stamin_up",
		"source_authority": "COD_ZOMBIES_CLASSIC_BO3",
		"machine_color": [0.16, 0.45, 0.18],
	},
	"choir_sight": {
		"display_name": "DEADSHOT DAIQUIRI",
		"price": 1500,
		"description": "Source behavior: 35% spread reduction and ADS sway removal; no invented recoil buff.",
		"source_perk": "deadshot_daiquiri",
		"source_authority": "COD_ZOMBIES_CLASSIC_BO3",
		"machine_color": [0.52, 0.42, 0.10],
	},
	"twin_bells": {
		"display_name": "DOUBLE TAP ROOT BEER II",
		"price": 2000,
		"description": "Source behavior: 0.75 weapon interval multiplier and 2x ordinary projectile damage.",
		"source_perk": "double_tap_ii",
		"source_authority": "perk_weapRateMultiplier+BO3_DOUBLE_TAP_II",
		"machine_color": [0.44, 0.16, 0.47],
	},
	"last_rites": {
		"display_name": "QUICK REVIVE",
		"price": 1500,
		"description": "Source co-op behavior: revive teammates in half the normal time.",
		"source_perk": "quick_revive",
		"source_authority": "COD_ZOMBIES_CLASSIC_BO3",
		"machine_color": [0.22, 0.22, 0.30],
	},
}

static func has_perk(id: String) -> bool:
	return PERKS.has(id)

static func get_perk(id: String) -> Dictionary:
	if not PERKS.has(id):
		return {}
	return (PERKS[id] as Dictionary).duplicate(true)

static func price(id: String) -> int:
	return int(get_perk(id).get("price", -1))

static func display_name(id: String) -> String:
	return str(get_perk(id).get("display_name", id.to_upper()))

static func ids() -> Array[String]:
	var out: Array[String] = []
	for key_var: Variant in PERKS.keys():
		out.append(str(key_var))
	out.sort()
	return out
