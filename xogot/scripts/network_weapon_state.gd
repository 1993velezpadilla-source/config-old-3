extends Node
class_name XzNetworkWeaponState

const WeaponCatalog = preload("res://scripts/weapon_catalog.gd")

var _weapon_id: String = WeaponCatalog.STARTING_WEAPON_ID
var _magazine: int = 8
var reserve_ammo: int = 80
var _upgraded: bool = false
var _mystery_serial: int = 0

func _ready() -> void:
	equip_weapon(_weapon_id, true)

func equip_weapon(id: String, refill: bool = true) -> bool:
	if not WeaponCatalog.has_weapon(id):
		return false
	var def: Dictionary = WeaponCatalog.get_weapon(id)
	if id != _weapon_id:
		_upgraded = false
	_weapon_id = id
	if refill:
		_magazine = int(def.get("magazine", 8))
		reserve_ammo = int(def.get("reserve", _magazine * 4))
	else:
		_magazine = mini(_magazine, int(def.get("magazine", _magazine)))
	set_meta("weapon_id", _weapon_id)
	set_meta("weapon_upgraded", _upgraded)
	return true

func buy_wall_weapon(id: String, player: Node) -> bool:
	if not WeaponCatalog.has_weapon(id) or player == null or not player.has_method("spend_points"):
		return false
	var same_weapon: bool = id == _weapon_id
	var cost: int = WeaponCatalog.ammo_cost(id) if same_weapon else WeaponCatalog.wall_cost(id)
	if cost < 0 or not bool(player.call("spend_points", cost)):
		return false
	if same_weapon:
		reserve_ammo += int(WeaponCatalog.get_weapon(id).get("reserve", 80))
	else:
		_upgraded = false
		equip_weapon(id, true)
	return true

func roll_mystery_weapon() -> String:
	_mystery_serial += 1
	var result: String = WeaponCatalog.roll_mystery(_mystery_serial, _weapon_id)
	_upgraded = false
	equip_weapon(result, true)
	return result

func can_upgrade_current_weapon() -> bool:
	return WeaponCatalog.has_weapon(_weapon_id) and not _upgraded

func upgrade_current_weapon() -> bool:
	if not can_upgrade_current_weapon():
		return false
	_upgraded = true
	set_meta("weapon_upgraded", true)
	return true

func add_reserve_ammo(amount: int) -> void:
	if amount > 0:
		reserve_ammo += amount

func get_weapon_id() -> String:
	return _weapon_id

func is_upgraded() -> bool:
	return _upgraded

func get_magazine() -> int:
	return _magazine

func get_reserve() -> int:
	return reserve_ammo

func get_authoritative_state() -> Dictionary:
	return {
		"id": _weapon_id,
		"magazine": _magazine,
		"reserve": reserve_ammo,
		"upgraded": _upgraded,
	}
