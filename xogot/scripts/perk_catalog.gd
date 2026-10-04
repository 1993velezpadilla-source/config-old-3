class_name PerkCatalog
extends RefCounted

const PERKS: Dictionary = {
	"martyrs_blood": {
		"display_name": "MARTYR'S BLOOD",
		"price": 2500,
		"description": "Raises maximum health to 200.",
		"machine_color": [0.48, 0.055, 0.045],
	},
	"quick_hands": {
		"display_name": "QUICK HANDS",
		"price": 2000,
		"description": "Reloads 30% faster.",
		"machine_color": [0.12, 0.38, 0.52],
	},
	"pilgrim_rush": {
		"display_name": "PILGRIM RUSH",
		"price": 3000,
		"description": "Increases movement speed by 15%.",
		"machine_color": [0.16, 0.45, 0.18],
	},
	"choir_sight": {
		"display_name": "CHOIR SIGHT",
		"price": 1500,
		"description": "Tightens spread and softens recoil.",
		"machine_color": [0.52, 0.42, 0.10],
	},
	"twin_bells": {
		"display_name": "TWIN BELLS",
		"price": 3000,
		"description": "Faster weapon cycle with a small damage lift.",
		"machine_color": [0.44, 0.16, 0.47],
	},
	"last_rites": {
		"display_name": "LAST RITES",
		"price": 3500,
		"description": "Consumes itself to survive one lethal hit.",
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
