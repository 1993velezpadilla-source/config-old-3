class_name WeaponCatalog
extends RefCounted

# Project weapon catalog for Xogot. Names and wall-buy prices are derived from
# the weapon IDs / authored church audits already kept in this repository.
# Binary model/audio paths are optional: gameplay stays functional while an
# approved source asset is being converted into Xogot.

const STARTING_WEAPON_ID := "colt"

const WALL_BUY_ORDER: Array[String] = [
	"m1",
	"mp40",
	"trench",
	"thompson",
	"kar98k",
	"gewehr",
	"ppsh",
	"type100",
	"stg",
	"fg42",
]

const MYSTERY_POOL: Array[Dictionary] = [
	{"id":"thompson","weight":1.00},
	{"id":"bar","weight":0.82},
	{"id":"browning","weight":0.58},
	{"id":"doublebarrel","weight":0.78},
	{"id":"sawnoff","weight":0.72},
	{"id":"fg42","weight":0.82},
	{"id":"gewehr","weight":0.92},
	{"id":"m1a1","weight":0.95},
	{"id":"mp40","weight":1.00},
	{"id":"mg42","weight":0.62},
	{"id":"ppsh","weight":0.68},
	{"id":"ptrs","weight":0.50},
	{"id":"stg","weight":0.72},
	{"id":"type100","weight":0.92},
	{"id":"springfield","weight":0.72},
	{"id":"357","weight":0.70},
	{"id":"arisaka","weight":0.78},
	{"id":"dp28","weight":0.60},
	{"id":"kar98k","weight":0.82},
	{"id":"mosin","weight":0.76},
	{"id":"nambu","weight":0.88},
	{"id":"svt40","weight":0.86},
	{"id":"tt33","weight":0.88},
	{"id":"type99","weight":0.62},
	{"id":"walther","weight":0.90},
	{"id":"ray","weight":0.12},
	{"id":"raymk2","weight":0.07},
	{"id":"tesla","weight":0.08},
]

const WEAPONS: Dictionary = {
	"colt": {
		"display_name": "Colt",
		"family": "pistol",
		"damage": 24.0,
		"range_m": 95.0,
		"fire_interval": 0.17,
		"magazine": 8,
		"reserve": 80,
		"reload_time": 1.48,
		"automatic": false,
		"ads_fov": 49.0,
		"hip_spread_deg": 1.45,
		"ads_spread_deg": 0.28,
		"visual_recoil_deg": 1.55,
		"wall_cost": -1,
		"ammo_cost": 250,
		"model_path": "res://assets/weapons/colt.glb",
		"fire_audio": "res://assets/audio/weapons/colt_fire.ogg",
		"reload_audio": "res://assets/audio/weapons/colt_reload.ogg",
	},
	"m1": {
		"display_name": "M1",
		"family": "rifle",
		"damage": 55.0,
		"range_m": 150.0,
		"fire_interval": 0.22,
		"magazine": 8,
		"reserve": 96,
		"reload_time": 1.85,
		"automatic": false,
		"ads_fov": 43.0,
		"hip_spread_deg": 1.20,
		"ads_spread_deg": 0.10,
		"visual_recoil_deg": 2.15,
		"wall_cost": 600,
		"ammo_cost": 300,
		"model_path": "res://assets/weapons/m1.glb",
		"fire_audio": "res://assets/audio/weapons/m1_fire.ogg",
		"reload_audio": "res://assets/audio/weapons/m1_reload.ogg",
	},
	"mp40": {
		"display_name": "MP40",
		"family": "smg",
		"damage": 34.0,
		"range_m": 105.0,
		"fire_interval": 0.095,
		"magazine": 32,
		"reserve": 192,
		"reload_time": 1.75,
		"automatic": true,
		"ads_fov": 46.0,
		"hip_spread_deg": 1.65,
		"ads_spread_deg": 0.35,
		"visual_recoil_deg": 0.95,
		"wall_cost": 1000,
		"ammo_cost": 500,
		"model_path": "res://assets/weapons/mp40.glb",
		"fire_audio": "res://assets/audio/weapons/mp40_fire.ogg",
		"reload_audio": "res://assets/audio/weapons/mp40_reload.ogg",
	},
	"trench": {
		"display_name": "Trench Shotgun",
		"family": "shotgun",
		"damage": 31.0,
		"pellets": 8,
		"range_m": 52.0,
		"fire_interval": 0.78,
		"magazine": 6,
		"reserve": 54,
		"reload_time": 2.25,
		"automatic": false,
		"ads_fov": 47.0,
		"hip_spread_deg": 4.20,
		"ads_spread_deg": 2.15,
		"visual_recoil_deg": 4.25,
		"wall_cost": 1500,
		"ammo_cost": 750,
		"model_path": "res://assets/weapons/trench.glb",
		"fire_audio": "res://assets/audio/weapons/trench_fire.ogg",
		"reload_audio": "res://assets/audio/weapons/trench_reload.ogg",
	},
	"thompson": {
		"display_name": "Thompson",
		"family": "smg",
		"damage": 36.0,
		"range_m": 110.0,
		"fire_interval": 0.090,
		"magazine": 30,
		"reserve": 180,
		"reload_time": 1.82,
		"automatic": true,
		"ads_fov": 45.0,
		"hip_spread_deg": 1.72,
		"ads_spread_deg": 0.38,
		"visual_recoil_deg": 1.05,
		"wall_cost": 1200,
		"ammo_cost": 600,
		"model_path": "res://assets/weapons/thompson.glb",
		"fire_audio": "res://assets/audio/weapons/thompson_fire.ogg",
		"reload_audio": "res://assets/audio/weapons/thompson_reload.ogg",
	},
	"bar": {
		"display_name":"BAR","family":"rifle","damage":58.0,"range_m":145.0,
		"fire_interval":0.125,"magazine":20,"reserve":140,"reload_time":2.15,
		"automatic":true,"ads_fov":43.0,"hip_spread_deg":1.55,"ads_spread_deg":0.22,
		"visual_recoil_deg":1.75,"wall_cost":-1,"ammo_cost":700,
		"model_path":"res://assets/weapons/bar.glb","fire_audio":"res://assets/audio/weapons/bar_fire.ogg",
		"reload_audio":"res://assets/audio/weapons/bar_reload.ogg"
	},
	"browning": {
		"display_name":"Browning","family":"lmg","damage":54.0,"range_m":150.0,
		"fire_interval":0.105,"magazine":100,"reserve":300,"reload_time":4.20,
		"automatic":true,"ads_fov":44.0,"hip_spread_deg":2.15,"ads_spread_deg":0.46,
		"visual_recoil_deg":1.45,"wall_cost":-1,"ammo_cost":900,
		"model_path":"res://assets/weapons/browning.glb","fire_audio":"res://assets/audio/weapons/browning_fire.ogg",
		"reload_audio":"res://assets/audio/weapons/browning_reload.ogg"
	},
	"doublebarrel": {
		"display_name":"Double Barrel","family":"shotgun","damage":42.0,"pellets":8,
		"range_m":48.0,"fire_interval":0.34,"magazine":2,"reserve":60,"reload_time":2.45,
		"automatic":false,"ads_fov":47.0,"hip_spread_deg":4.6,"ads_spread_deg":2.35,
		"visual_recoil_deg":5.2,"wall_cost":-1,"ammo_cost":750,
		"model_path":"res://assets/weapons/doublebarrel.glb","fire_audio":"res://assets/audio/weapons/doublebarrel_fire.ogg",
		"reload_audio":"res://assets/audio/weapons/doublebarrel_reload.ogg"
	},
	"sawnoff": {
		"display_name":"Sawed-Off","family":"shotgun","damage":44.0,"pellets":7,
		"range_m":34.0,"fire_interval":0.32,"magazine":2,"reserve":56,"reload_time":2.20,
		"automatic":false,"ads_fov":49.0,"hip_spread_deg":5.3,"ads_spread_deg":2.9,
		"visual_recoil_deg":5.5,"wall_cost":-1,"ammo_cost":750,
		"model_path":"res://assets/weapons/sawnoff.glb","fire_audio":"res://assets/audio/weapons/sawnoff_fire.ogg",
		"reload_audio":"res://assets/audio/weapons/sawnoff_reload.ogg"
	},
	"fg42": {
		"display_name":"FG42","family":"rifle","damage":47.0,"range_m":135.0,
		"fire_interval":0.092,"magazine":20,"reserve":160,"reload_time":2.00,
		"automatic":true,"ads_fov":43.0,"hip_spread_deg":1.55,"ads_spread_deg":0.30,
		"visual_recoil_deg":1.35,"wall_cost":1800,"ammo_cost":700,
		"model_path":"res://assets/weapons/fg42.glb","fire_audio":"res://assets/audio/weapons/fg42_fire.ogg",
		"reload_audio":"res://assets/audio/weapons/fg42_reload.ogg"
	},
	"gewehr": {
		"display_name":"Gewehr","family":"rifle","damage":52.0,"range_m":150.0,
		"fire_interval":0.18,"magazine":10,"reserve":100,"reload_time":1.95,
		"automatic":false,"ads_fov":42.0,"hip_spread_deg":1.25,"ads_spread_deg":0.12,
		"visual_recoil_deg":1.85,"wall_cost":900,"ammo_cost":600,
		"model_path":"res://assets/weapons/gewehr.glb","fire_audio":"res://assets/audio/weapons/gewehr_fire.ogg",
		"reload_audio":"res://assets/audio/weapons/gewehr_reload.ogg"
	},
	"m1a1": {
		"display_name":"M1A1","family":"rifle","damage":45.0,"range_m":135.0,
		"fire_interval":0.16,"magazine":15,"reserve":120,"reload_time":1.90,
		"automatic":false,"ads_fov":44.0,"hip_spread_deg":1.35,"ads_spread_deg":0.18,
		"visual_recoil_deg":1.55,"wall_cost":-1,"ammo_cost":600,
		"model_path":"res://assets/weapons/m1a1.glb","fire_audio":"res://assets/audio/weapons/m1a1_fire.ogg",
		"reload_audio":"res://assets/audio/weapons/m1a1_reload.ogg"
	},
	"mg42": {
		"display_name":"MG42","family":"lmg","damage":48.0,"range_m":145.0,
		"fire_interval":0.070,"magazine":125,"reserve":375,"reload_time":4.45,
		"automatic":true,"ads_fov":45.0,"hip_spread_deg":2.35,"ads_spread_deg":0.52,
		"visual_recoil_deg":1.25,"wall_cost":-1,"ammo_cost":950,
		"model_path":"res://assets/weapons/mg42.glb","fire_audio":"res://assets/audio/weapons/mg42_fire.ogg",
		"reload_audio":"res://assets/audio/weapons/mg42_reload.ogg"
	},
	"ppsh": {
		"display_name":"PPSh","family":"smg","damage":33.0,"range_m":105.0,
		"fire_interval":0.072,"magazine":71,"reserve":284,"reload_time":2.35,
		"automatic":true,"ads_fov":45.0,"hip_spread_deg":1.75,"ads_spread_deg":0.42,
		"visual_recoil_deg":1.05,"wall_cost":2000,"ammo_cost":800,
		"model_path":"res://assets/weapons/ppsh.glb","fire_audio":"res://assets/audio/weapons/ppsh_fire.ogg",
		"reload_audio":"res://assets/audio/weapons/ppsh_reload.ogg"
	},
	"ptrs": {
		"display_name":"PTRS","family":"sniper","damage":190.0,"range_m":260.0,
		"fire_interval":0.72,"magazine":5,"reserve":45,"reload_time":2.65,
		"automatic":false,"ads_fov":28.0,"hip_spread_deg":4.0,"ads_spread_deg":0.03,
		"visual_recoil_deg":5.5,"wall_cost":-1,"ammo_cost":900,
		"model_path":"res://assets/weapons/ptrs.glb","fire_audio":"res://assets/audio/weapons/ptrs_fire.ogg",
		"reload_audio":"res://assets/audio/weapons/ptrs_reload.ogg"
	},
	"stg": {
		"display_name":"STG","family":"rifle","damage":46.0,"range_m":135.0,
		"fire_interval":0.095,"magazine":30,"reserve":180,"reload_time":1.95,
		"automatic":true,"ads_fov":43.0,"hip_spread_deg":1.55,"ads_spread_deg":0.28,
		"visual_recoil_deg":1.25,"wall_cost":2000,"ammo_cost":700,
		"model_path":"res://assets/weapons/stg.glb","fire_audio":"res://assets/audio/weapons/stg_fire.ogg",
		"reload_audio":"res://assets/audio/weapons/stg_reload.ogg"
	},
	"type100": {
		"display_name":"Type 100","family":"smg","damage":31.0,"range_m":102.0,
		"fire_interval":0.090,"magazine":30,"reserve":180,"reload_time":1.85,
		"automatic":true,"ads_fov":46.0,"hip_spread_deg":1.65,"ads_spread_deg":0.38,
		"visual_recoil_deg":0.95,"wall_cost":1000,"ammo_cost":600,
		"model_path":"res://assets/weapons/type100.glb","fire_audio":"res://assets/audio/weapons/type100_fire.ogg",
		"reload_audio":"res://assets/audio/weapons/type100_reload.ogg"
	},
	"springfield": {
		"display_name":"Springfield","family":"sniper","damage":135.0,"range_m":240.0,
		"fire_interval":0.85,"magazine":5,"reserve":50,"reload_time":2.50,
		"automatic":false,"ads_fov":30.0,"hip_spread_deg":3.8,"ads_spread_deg":0.04,
		"visual_recoil_deg":4.4,"wall_cost":-1,"ammo_cost":750,
		"model_path":"res://assets/weapons/springfield.glb","fire_audio":"res://assets/audio/weapons/springfield_fire.ogg",
		"reload_audio":"res://assets/audio/weapons/springfield_reload.ogg"
	},
	"357": {
		"display_name":"357 Magnum","family":"pistol","damage":72.0,"range_m":105.0,
		"fire_interval":0.34,"magazine":6,"reserve":72,"reload_time":2.10,
		"automatic":false,"ads_fov":47.0,"hip_spread_deg":1.8,"ads_spread_deg":0.20,
		"visual_recoil_deg":3.4,"wall_cost":-1,"ammo_cost":600,
		"model_path":"res://assets/weapons/aether_waw_real/357/viewmodel.glb",
		"fire_audio":"res://assets/audio/weapons/mapmod/357/fire.ogg",
		"reload_audio":"res://assets/audio/weapons/mapmod/357/reload.ogg"
	},
	"arisaka": {
		"display_name":"Arisaka","family":"rifle","damage":125.0,"range_m":230.0,
		"fire_interval":0.78,"magazine":5,"reserve":55,"reload_time":2.55,
		"automatic":false,"ads_fov":31.0,"hip_spread_deg":3.2,"ads_spread_deg":0.05,
		"visual_recoil_deg":4.1,"wall_cost":-1,"ammo_cost":750,
		"model_path":"res://assets/weapons/aether_waw_real/arisaka/viewmodel.glb",
		"fire_audio":"res://assets/audio/weapons/mapmod/arisaka/fire.ogg",
		"reload_audio":"res://assets/audio/weapons/mapmod/arisaka/reload.ogg"
	},
	"dp28": {
		"display_name":"DP-28","family":"lmg","damage":51.0,"range_m":145.0,
		"fire_interval":0.105,"magazine":47,"reserve":282,"reload_time":3.65,
		"automatic":true,"ads_fov":44.0,"hip_spread_deg":2.1,"ads_spread_deg":0.45,
		"visual_recoil_deg":1.4,"wall_cost":-1,"ammo_cost":850,
		"model_path":"res://assets/weapons/aether_waw_real/dp28/viewmodel.glb",
		"fire_audio":"res://assets/audio/weapons/mapmod/dp28/fire.ogg",
		"reload_audio":"res://assets/audio/weapons/mapmod/dp28/reload.ogg"
	},
	"kar98k": {
		"display_name":"Kar98k","family":"sniper","damage":132.0,"range_m":245.0,
		"fire_interval":0.82,"magazine":5,"reserve":55,"reload_time":2.60,
		"automatic":false,"ads_fov":30.0,"hip_spread_deg":3.6,"ads_spread_deg":0.04,
		"visual_recoil_deg":4.5,"wall_cost":500,"ammo_cost":750,
		"model_path":"res://assets/weapons/aether_waw_real/kar98k/viewmodel.glb",
		"fire_audio":"res://assets/audio/weapons/mapmod/kar98k/fire.ogg",
		"reload_audio":"res://assets/audio/weapons/mapmod/kar98k/reload.ogg"
	},
	"mosin": {
		"display_name":"Mosin-Nagant","family":"sniper","damage":138.0,"range_m":250.0,
		"fire_interval":0.84,"magazine":5,"reserve":55,"reload_time":2.65,
		"automatic":false,"ads_fov":30.0,"hip_spread_deg":3.7,"ads_spread_deg":0.04,
		"visual_recoil_deg":4.6,"wall_cost":-1,"ammo_cost":750,
		"model_path":"res://assets/weapons/aether_waw_real/mosin/viewmodel.glb",
		"fire_audio":"res://assets/audio/weapons/mapmod/mosin/fire.ogg",
		"reload_audio":"res://assets/audio/weapons/mapmod/mosin/reload.ogg"
	},
	"nambu": {
		"display_name":"Nambu","family":"pistol","damage":28.0,"range_m":90.0,
		"fire_interval":0.18,"magazine":8,"reserve":96,"reload_time":1.65,
		"automatic":false,"ads_fov":49.0,"hip_spread_deg":1.5,"ads_spread_deg":0.28,
		"visual_recoil_deg":1.45,"wall_cost":-1,"ammo_cost":350,
		"model_path":"res://assets/weapons/aether_waw_real/nambu/viewmodel.glb",
		"fire_audio":"res://assets/audio/weapons/mapmod/nambu/fire.ogg",
		"reload_audio":"res://assets/audio/weapons/mapmod/nambu/reload.ogg"
	},
	"svt40": {
		"display_name":"SVT-40","family":"rifle","damage":57.0,"range_m":155.0,
		"fire_interval":0.17,"magazine":10,"reserve":120,"reload_time":2.05,
		"automatic":false,"ads_fov":42.0,"hip_spread_deg":1.3,"ads_spread_deg":0.12,
		"visual_recoil_deg":1.9,"wall_cost":-1,"ammo_cost":650,
		"model_path":"res://assets/weapons/aether_waw_real/svt40/viewmodel.glb",
		"fire_audio":"res://assets/audio/weapons/mapmod/svt40/fire.ogg",
		"reload_audio":"res://assets/audio/weapons/mapmod/svt40/reload.ogg"
	},
	"tt33": {
		"display_name":"TT-33","family":"pistol","damage":31.0,"range_m":92.0,
		"fire_interval":0.17,"magazine":8,"reserve":96,"reload_time":1.60,
		"automatic":false,"ads_fov":49.0,"hip_spread_deg":1.45,"ads_spread_deg":0.26,
		"visual_recoil_deg":1.5,"wall_cost":-1,"ammo_cost":350,
		"model_path":"res://assets/weapons/aether_waw_real/tt33/viewmodel.glb",
		"fire_audio":"res://assets/audio/weapons/mapmod/tt33/fire.ogg",
		"reload_audio":"res://assets/audio/weapons/mapmod/tt33/reload.ogg"
	},
	"type99": {
		"display_name":"Type 99","family":"lmg","damage":49.0,"range_m":145.0,
		"fire_interval":0.10,"magazine":30,"reserve":210,"reload_time":3.10,
		"automatic":true,"ads_fov":44.0,"hip_spread_deg":2.0,"ads_spread_deg":0.42,
		"visual_recoil_deg":1.5,"wall_cost":-1,"ammo_cost":800,
		"model_path":"res://assets/weapons/aether_waw_real/type99/viewmodel.glb",
		"fire_audio":"res://assets/audio/weapons/mapmod/type99/fire.ogg",
		"reload_audio":"res://assets/audio/weapons/mapmod/type99/reload.ogg"
	},
	"walther": {
		"display_name":"Walther P38","family":"pistol","damage":29.0,"range_m":92.0,
		"fire_interval":0.18,"magazine":8,"reserve":96,"reload_time":1.60,
		"automatic":false,"ads_fov":49.0,"hip_spread_deg":1.45,"ads_spread_deg":0.27,
		"visual_recoil_deg":1.45,"wall_cost":-1,"ammo_cost":350,
		"model_path":"res://assets/weapons/aether_waw_real/walther/viewmodel.glb",
		"fire_audio":"res://assets/audio/weapons/mapmod/walther/fire.ogg",
		"reload_audio":"res://assets/audio/weapons/mapmod/walther/reload.ogg"
	},
	"ray": {
		"display_name":"Ray Weapon","family":"wonder","damage":210.0,"range_m":120.0,
		"fire_interval":0.31,"magazine":20,"reserve":160,"reload_time":2.10,
		"automatic":false,"ads_fov":50.0,"hip_spread_deg":0.80,"ads_spread_deg":0.18,
		"visual_recoil_deg":1.6,"wall_cost":-1,"ammo_cost":-1,
		"model_path":"res://assets/weapons/ray.glb","fire_audio":"res://assets/audio/weapons/ray_fire.ogg",
		"reload_audio":"res://assets/audio/weapons/ray_reload.ogg"
	},
	"raymk2": {
		"display_name":"Ray Weapon Mk II","family":"wonder","damage":160.0,"pellets":3,
		"range_m":135.0,"fire_interval":0.42,"magazine":21,"reserve":168,"reload_time":2.20,
		"automatic":false,"ads_fov":47.0,"hip_spread_deg":0.65,"ads_spread_deg":0.12,
		"visual_recoil_deg":1.8,"wall_cost":-1,"ammo_cost":-1,
		"model_path":"res://assets/weapons/raymk2.glb","fire_audio":"res://assets/audio/weapons/raymk2_fire.ogg",
		"reload_audio":"res://assets/audio/weapons/raymk2_reload.ogg"
	},
	"tesla": {
		"display_name":"Tesla Weapon","family":"wonder","damage":420.0,"range_m":95.0,
		"fire_interval":1.05,"magazine":3,"reserve":18,"reload_time":3.0,
		"automatic":false,"ads_fov":50.0,"hip_spread_deg":0.25,"ads_spread_deg":0.05,
		"visual_recoil_deg":2.2,"wall_cost":-1,"ammo_cost":-1,
		"model_path":"res://assets/weapons/tesla.glb","fire_audio":"res://assets/audio/weapons/tesla_fire.ogg",
		"reload_audio":"res://assets/audio/weapons/tesla_reload.ogg"
	},
}

static func has_weapon(id: String) -> bool:
	return WEAPONS.has(id)

static func get_weapon(id: String) -> Dictionary:
	if WEAPONS.has(id):
		return (WEAPONS[id] as Dictionary).duplicate(true)
	return (WEAPONS[STARTING_WEAPON_ID] as Dictionary).duplicate(true)

static func wall_cost(id: String) -> int:
	return int(get_weapon(id).get("wall_cost", -1))

static func ammo_cost(id: String) -> int:
	return int(get_weapon(id).get("ammo_cost", 500))

static func mystery_pool_ids() -> Array[String]:
	var result: Array[String] = []
	for item: Dictionary in MYSTERY_POOL:
		result.append(str(item["id"]))
	return result

static func roll_mystery(serial: int, avoid_id: String = "") -> String:
	var total: float = 0.0
	for item: Dictionary in MYSTERY_POOL:
		var id: String = str(item["id"])
		if id == avoid_id:
			continue
		total += float(item["weight"])
	if total <= 0.0:
		return "thompson"

	# Deterministic-but-varied RNG seed keeps CI and multiplayer authority reproducible.
	var rng := RandomNumberGenerator.new()
	rng.seed = int(0x5A17) + serial * 7919
	var pick: float = rng.randf_range(0.0, total)
	var cursor: float = 0.0
	for item: Dictionary in MYSTERY_POOL:
		var id: String = str(item["id"])
		if id == avoid_id:
			continue
		cursor += float(item["weight"])
		if pick <= cursor:
			return id
	return str(MYSTERY_POOL[0]["id"])
