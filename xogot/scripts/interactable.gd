extends StaticBody3D

enum Kind {
	DOOR,
	WALLBUY,
	MYSTERY,
	PERK,
	POWER
}

@export var interaction_kind: Kind = Kind.DOOR
@export var price: int = 0
@export var reward_amount: int = 0
@export var one_shot: bool = true
@export var prompt_text: String = "INTERACT"
@export var weapon_id: String = ""

var _used: bool = false
var _interaction_count: int = 0
var _last_result: String = ""

func interact(player: Node) -> bool:
	if _used and one_shot:
		return false

	if interaction_kind == Kind.WALLBUY:
		return _use_wallbuy_weapon(player)

	# Mystery keeps the classic fixed box price. The weapon itself is granted
	# after payment so a failed purchase never consumes a roll.
	if price > 0:
		if player == null or not player.has_method("spend_points"):
			return false
		if not bool(player.call("spend_points", price)):
			return false

	match interaction_kind:
		Kind.DOOR:
			_open_door()
		Kind.MYSTERY:
			_use_mystery(player)
		Kind.PERK:
			_interaction_count += 1
			player.set_meta("perk_socket_used", true)
			print("XZOGOT_PERK_SOCKET_USED")
		Kind.POWER:
			_interaction_count += 1
			get_tree().set_meta("power_on", true)
			print("XZOGOT_POWER_ON")

	if one_shot:
		_used = true
	return true

func _find_player_weapon(player: Node) -> Node:
	if player == null:
		return null
	var direct: Node = player.get_node_or_null("Weapon")
	if direct != null:
		return direct
	return null

func _use_wallbuy_weapon(player: Node) -> bool:
	if weapon_id.is_empty():
		# Legacy ammo-only wallbuy compatibility for old probes/maps.
		if price > 0:
			if player == null or not player.has_method("spend_points"):
				return false
			if not bool(player.call("spend_points", price)):
				return false
		var legacy_weapon: Node = _find_player_weapon(player)
		if legacy_weapon != null and legacy_weapon.has_method("add_reserve_ammo"):
			legacy_weapon.call("add_reserve_ammo", reward_amount)
			_interaction_count += 1
			print("XZOGOT_WALLBUY_LEGACY_AMMO ", reward_amount)
			return true
		return false

	var weapon: Node = _find_player_weapon(player)
	if weapon == null or not weapon.has_method("buy_wall_weapon"):
		return false
	if not bool(weapon.call("buy_wall_weapon", weapon_id, player)):
		return false
	_interaction_count += 1
	_last_result = weapon_id
	print("XZOGOT_WALLBUY_USED ", weapon_id, " count=", _interaction_count)
	return true

func _use_mystery(player: Node) -> void:
	_interaction_count += 1
	var weapon: Node = _find_player_weapon(player)
	if weapon != null and weapon.has_method("roll_mystery_weapon"):
		_last_result = str(weapon.call("roll_mystery_weapon"))
	else:
		_last_result = ""
	print("XZOGOT_MYSTERY_SPIN ", _interaction_count, " result=", _last_result)

func _open_door() -> void:
	_interaction_count += 1
	for child: Node in get_children():
		if child is MeshInstance3D:
			(child as MeshInstance3D).visible = false
		elif child is CollisionShape3D:
			(child as CollisionShape3D).set_deferred("disabled", true)
	print("XZOGOT_DOOR_OPEN")

func dev_force_open() -> bool:
	if interaction_kind != Kind.DOOR:
		return false
	if _used:
		return false
	_open_door()
	_used = true
	print("XZOGOT_DEV_FORCE_OPEN ", name)
	return true

func get_prompt() -> String:
	if _used and one_shot:
		return ""
	if interaction_kind == Kind.WALLBUY and not weapon_id.is_empty():
		if price > 0:
			return "%s - %d" % [prompt_text, price]
		return prompt_text
	if price > 0:
		return "%s - %d" % [prompt_text, price]
	return prompt_text

func was_used() -> bool:
	return _used

func get_interaction_count() -> int:
	return _interaction_count

func get_last_result() -> String:
	return _last_result

func get_weapon_id() -> String:
	return weapon_id
