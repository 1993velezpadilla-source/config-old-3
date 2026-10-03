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

var _used: bool = false
var _interaction_count: int = 0

func interact(player: Node) -> bool:
	if _used and one_shot:
		return false

	if price > 0:
		if not player.has_method("spend_points"):
			return false
		if not bool(player.call("spend_points", price)):
			return false

	match interaction_kind:
		Kind.DOOR:
			_open_door()
		Kind.WALLBUY:
			_use_wallbuy(player)
		Kind.MYSTERY:
			_interaction_count += 1
			print("XZOGOT_MYSTERY_SPIN ", _interaction_count)
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

func _open_door() -> void:
	_interaction_count += 1
	for child: Node in get_children():
		if child is MeshInstance3D:
			(child as MeshInstance3D).visible = false
		elif child is CollisionShape3D:
			(child as CollisionShape3D).set_deferred("disabled", true)
	print("XZOGOT_DOOR_OPEN")

func _use_wallbuy(player: Node) -> void:
	_interaction_count += 1
	var weapon: Node = player.get_node_or_null("Weapon")
	if weapon != null and weapon.has_method("add_reserve_ammo"):
		weapon.call("add_reserve_ammo", reward_amount)
	print("XZOGOT_WALLBUY_USED ", reward_amount)

func get_prompt() -> String:
	if _used and one_shot:
		return ""
	if price > 0:
		return "%s - %d" % [prompt_text, price]
	return prompt_text

func was_used() -> bool:
	return _used

func get_interaction_count() -> int:
	return _interaction_count
