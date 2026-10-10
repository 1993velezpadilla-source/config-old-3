extends StaticBody3D

enum Kind {
	DOOR,
	WALLBUY,
	MYSTERY,
	PERK,
	POWER,
	UPGRADE,
	BELL
}

@export var interaction_kind: Kind = Kind.DOOR
@export var price: int = 0
@export var reward_amount: int = 0
@export var one_shot: bool = true
@export var prompt_text: String = "INTERACT"
@export var weapon_id: String = ""
@export var perk_id: String = ""
@export var requires_power: bool = false

var _used: bool = false
var _interaction_count: int = 0
var _last_result: String = ""

var _last_power_visual_state: bool = false

const SFX_DOOR := "res://assets/audio/church/world/door_open.ogg"
const SFX_POWER := "res://assets/audio/church/world/power_switch.ogg"
const SFX_MACHINE := "res://assets/audio/church/world/machine_use.ogg"
const SFX_MACHINE_LOOP := "res://assets/audio/church/world/machine_loop.ogg"
const SFX_MYSTERY := "res://assets/audio/church/world/mystery_open.ogg"

var _machine_loop_audio: AudioStreamPlayer3D
var _machine_animation_player: AnimationPlayer
var _machine_animation_role: String = ""

func _network_manager() -> Node:
	return get_tree().root.find_child("NetworkManager", true, false)

func _notify_network_success(player: Node) -> void:
	var network: Node = _network_manager()
	if network != null and network.has_method("notify_host_interaction"):
		network.call("notify_host_interaction", self, player)

func _play_world_sfx(path: String, volume_db: float = -4.0) -> void:
	if not ResourceLoader.exists(path):
		return
	var stream := load(path) as AudioStream
	if stream == null:
		return
	var player := AudioStreamPlayer3D.new()
	player.name = "OneShotSFX"
	player.stream = stream
	player.volume_db = volume_db
	player.unit_size = 2.0
	player.max_distance = 32.0
	add_child(player)
	player.finished.connect(player.queue_free)
	player.play()


func _ready() -> void:
	if interaction_kind == Kind.PERK or interaction_kind == Kind.UPGRADE:
		_build_machine_loop_audio()
		_machine_animation_player = _find_machine_animation_player(self)
		if _machine_animation_player != null:
			_machine_animation_player.animation_finished.connect(_on_machine_animation_finished)
	_last_power_visual_state = not bool(get_tree().get_meta("power_on", false))
	_update_power_visual()
	if interaction_kind == Kind.PERK or interaction_kind == Kind.UPGRADE:
		_play_machine_animation("idle", 0.0)
	set_process(requires_power)

func _find_machine_animation_player(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node as AnimationPlayer
	for child: Node in node.get_children():
		var found := _find_machine_animation_player(child)
		if found != null:
			return found
	return null

func _machine_animation_aliases(role: String) -> Array[String]:
	match role:
		"idle":
			return ["idle", "loop", "powered_idle", "machine_idle"]
		"power_on":
			return ["power_on", "powerup", "power_up", "turn_on", "startup", "activate"]
		"power_off":
			return ["power_off", "shutdown", "turn_off", "inactive", "off"]
		"purchase":
			return ["purchase", "buy", "dispense", "vend", "use", "drink", "bottle"]
		"upgrade":
			return ["upgrade", "pack", "process", "forge", "use"]
		_:
			return [role]

func _machine_animation_name_for_role(role: String) -> String:
	if _machine_animation_player == null or not is_instance_valid(_machine_animation_player):
		return ""
	var aliases := _machine_animation_aliases(role)
	var best := ""
	var best_score := -1
	for anim_name: StringName in _machine_animation_player.get_animation_list():
		var candidate := str(anim_name)
		var lower := candidate.to_lower()
		for alias: String in aliases:
			var token := alias.to_lower()
			if lower == token:
				return candidate
			if lower.contains(token):
				var score := token.length()
				if score > best_score:
					best_score = score
					best = candidate
	return best

func _play_machine_animation(role: String, blend: float = 0.08) -> bool:
	if _machine_animation_player == null or not is_instance_valid(_machine_animation_player):
		return false
	var animation_name := _machine_animation_name_for_role(role)
	if animation_name.is_empty():
		return false
	_machine_animation_role = role
	_machine_animation_player.play(animation_name, blend)
	set_meta("machine_animation_role", role)
	set_meta("machine_animation_name", animation_name)
	print("XZOGOT_MACHINE_ANIMATION ", name, " role=", role, " clip=", animation_name)
	return true

func _on_machine_animation_finished(_animation_name: StringName) -> void:
	if interaction_kind != Kind.PERK and interaction_kind != Kind.UPGRADE:
		return
	if _machine_animation_role in ["purchase", "upgrade", "power_on"]:
		_play_machine_animation("idle", 0.08)

func _build_machine_loop_audio() -> void:
	if not ResourceLoader.exists(SFX_MACHINE_LOOP):
		return
	var stream := load(SFX_MACHINE_LOOP) as AudioStream
	if stream == null:
		return
	if stream is AudioStreamOggVorbis:
		(stream as AudioStreamOggVorbis).loop = true
	_machine_loop_audio = AudioStreamPlayer3D.new()
	_machine_loop_audio.name = "MachineLoopAudio"
	_machine_loop_audio.stream = stream
	_machine_loop_audio.volume_db = -18.0
	_machine_loop_audio.unit_size = 1.4
	_machine_loop_audio.max_distance = 13.0
	add_child(_machine_loop_audio)
	_machine_loop_audio.play()

func _process(_delta: float) -> void:
	if not requires_power:
		return
	var power_now: bool = bool(get_tree().get_meta("power_on", false))
	if power_now != _last_power_visual_state:
		_update_power_visual()

func _update_power_visual() -> void:
	var powered: bool = not requires_power or bool(get_tree().get_meta("power_on", false))
	_last_power_visual_state = powered
	for node: Node in find_children("*", "", true, false):
		if not bool(node.get_meta("powered_visual", false)):
			continue
		if node is Light3D:
			(node as Light3D).visible = powered
		elif node is Label3D:
			var label := node as Label3D
			label.modulate.a = 1.0 if powered else 0.18
		elif node is GeometryInstance3D:
			var geometry := node as GeometryInstance3D
			geometry.transparency = 0.0 if powered else 0.68
	if _machine_loop_audio != null:
		_machine_loop_audio.stream_paused = not powered
	if interaction_kind == Kind.PERK or interaction_kind == Kind.UPGRADE:
		if powered:
			if not _play_machine_animation("power_on", 0.10):
				_play_machine_animation("idle", 0.10)
		else:
			_play_machine_animation("power_off", 0.10)
	if requires_power:
		set_meta("powered_visual_on", powered)

func _animate_mystery_box() -> void:
	var visual: Node = find_child("ArchivedWorkshopReference3D", true, false)
	if visual != null:
		var animation: AnimationPlayer = _find_machine_animation_player(visual)
		if animation != null and animation.has_animation("open"):
			animation.play("open", 0.04)
			set_meta("source_box_open_animation_played", true)
			return
	var lid := find_child("MysteryLid", true, false) as Node3D
	if lid == null:
		return
	var tween := create_tween()
	tween.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tween.tween_property(lid, "rotation_degrees:x", -72.0, 0.26)
	tween.tween_interval(0.55)
	tween.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN_OUT)
	tween.tween_property(lid, "rotation_degrees:x", 0.0, 0.34)

	var glow := find_child("MysteryGlow", true, false) as OmniLight3D
	if glow != null:
		var glow_tween := create_tween()
		glow_tween.tween_property(glow, "light_energy", 1.25, 0.14)
		glow_tween.tween_interval(0.56)
		glow_tween.tween_property(glow, "light_energy", 0.42, 0.35)

func _animate_power_lever() -> void:
	var lever := find_child("PowerLever", true, false) as Node3D
	if lever != null:
		var tween := create_tween()
		tween.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
		tween.tween_property(lever, "rotation_degrees:x", 42.0, 0.32)
	var indicator := find_child("PowerIndicator", true, false) as OmniLight3D
	if indicator != null:
		indicator.light_color = Color(0.12, 0.95, 0.28)
		var t := create_tween()
		t.tween_property(indicator, "light_energy", 0.78, 0.18)
		t.tween_property(indicator, "light_energy", 0.30, 0.45)

func _animate_forge() -> void:
	var rings: Array[Node3D] = []
	for child: Node in find_children("ForgeRing_*", "Node3D", true, false):
		if child is Node3D:
			rings.append(child as Node3D)
	for i in range(rings.size()):
		var ring: Node3D = rings[i]
		var tween := create_tween()
		var direction: float = -1.0 if i % 2 == 0 else 1.0
		tween.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
		tween.tween_property(
			ring,
			"rotation_degrees:z",
			ring.rotation_degrees.z + direction * 360.0,
			0.95 + float(i) * 0.12
		)

func _pulse_perk_machine() -> void:
	var glow := find_child("MachineGlow", true, false) as OmniLight3D
	if glow == null:
		return
	var base: float = glow.light_energy
	var tween := create_tween()
	tween.tween_property(glow, "light_energy", maxf(base * 3.0, 0.75), 0.12)
	tween.tween_property(glow, "light_energy", base, 0.48)

func interact(player: Node) -> bool:
	if _used and one_shot:
		return false

	if requires_power and not bool(get_tree().get_meta("power_on", false)):
		_last_result = "POWER_REQUIRED"
		print("XZOGOT_INTERACTION_POWER_REQUIRED ", name)
		return false

	if interaction_kind == Kind.WALLBUY:
		var wall_success: bool = _use_wallbuy_weapon(player)
		if wall_success:
			_notify_network_success(player)
		return wall_success

	var weapon: Node = _find_player_weapon(player)
	if interaction_kind == Kind.PERK:
		if perk_id.is_empty() or player == null or not player.has_method("can_buy_perk"):
			return false
		if not bool(player.call("can_buy_perk", perk_id)):
			_last_result = "ALREADY_OWNED"
			return false
	elif interaction_kind == Kind.UPGRADE:
		if weapon == null or not weapon.has_method("can_upgrade_current_weapon"):
			return false
		if not bool(weapon.call("can_upgrade_current_weapon")):
			_last_result = "ALREADY_UPGRADED"
			return false

	# Payment happens only after the interaction has passed all eligibility
	# checks so duplicate perks/upgrades can never eat points.
	if price > 0:
		if player == null or not player.has_method("spend_points"):
			return false
		if not bool(player.call("spend_points", price)):
			_last_result = "INSUFFICIENT_POINTS"
			return false

	match interaction_kind:
		Kind.DOOR:
			_open_door()
			_play_world_sfx(SFX_DOOR)
		Kind.MYSTERY:
			_use_mystery(player)
			if weapon != null and weapon.has_method("play_interaction_animation"):
				weapon.call("play_interaction_animation", "machine_use")
			_animate_mystery_box()
			_play_world_sfx(SFX_MYSTERY)
		Kind.PERK:
			if not bool(player.call("grant_perk", perk_id)):
				return false
			if weapon != null and weapon.has_method("play_interaction_animation"):
				weapon.call("play_interaction_animation", "perk_use")
			_interaction_count += 1
			_last_result = perk_id
			_pulse_perk_machine()
			_play_machine_animation("purchase", 0.04)
			_play_world_sfx(SFX_MACHINE, -6.0)
			print("XZOGOT_PERK_MACHINE_USED ", perk_id)
		Kind.POWER:
			_interaction_count += 1
			if weapon != null and weapon.has_method("play_interaction_animation"):
				weapon.call("play_interaction_animation", "machine_use")
			get_tree().set_meta("power_on", true)
			_last_result = "POWER_ON"
			_animate_power_lever()
			_play_world_sfx(SFX_POWER, -2.0)
			print("XZOGOT_POWER_ON")
		Kind.UPGRADE:
			if not bool(weapon.call("upgrade_current_weapon")):
				return false
			if weapon.has_method("play_interaction_animation"):
				weapon.call("play_interaction_animation", "machine_use")
			_interaction_count += 1
			_last_result = str(weapon.call("get_weapon_id"))
			_animate_forge()
			_play_machine_animation("upgrade", 0.04)
			_play_world_sfx(SFX_MACHINE, -1.5)
			print("XZOGOT_SANCTUM_FORGE_USED ", _last_result)
		Kind.BELL:
			_interaction_count += 1
			var rung: bool = false
			for audio_node: Node in get_tree().get_nodes_in_group("church_audio_runtime"):
				if audio_node.has_method("ring_bell"):
					rung = bool(audio_node.call("ring_bell")) or rung
			if not rung:
				return false
			_last_result = "BELL_RUNG"
			print("XZOGOT_BELL_ROPE_USED ", _interaction_count)

	if one_shot:
		_used = true
	_notify_network_success(player)
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

func _apply_door_open_visual() -> void:
	for child: Node in get_children():
		if child is MeshInstance3D:
			(child as MeshInstance3D).visible = false
		elif child is CollisionShape3D:
			(child as CollisionShape3D).set_deferred("disabled", true)

func _open_door() -> void:
	_interaction_count += 1
	_apply_door_open_visual()
	print("XZOGOT_DOOR_OPEN")

func apply_network_world_state(
	used: bool,
	power_on: bool,
	last_result: String
) -> void:
	get_tree().set_meta("power_on", power_on)
	_last_result = last_result
	if one_shot and used:
		_used = true
	_update_power_visual()

	match interaction_kind:
		Kind.DOOR:
			if used:
				_apply_door_open_visual()
		Kind.MYSTERY:
			if not last_result.is_empty():
				_animate_mystery_box()
				_play_world_sfx(SFX_MYSTERY, -7.0)
		Kind.PERK:
			if not last_result.is_empty():
				_pulse_perk_machine()
				_play_machine_animation("purchase", 0.04)
				_play_world_sfx(SFX_MACHINE, -8.0)
		Kind.POWER:
			if power_on:
				_animate_power_lever()
				_play_world_sfx(SFX_POWER, -4.0)
		Kind.UPGRADE:
			if not last_result.is_empty():
				_animate_forge()
				_play_machine_animation("upgrade", 0.04)
				_play_world_sfx(SFX_MACHINE, -5.0)
		Kind.BELL:
			if last_result == "BELL_RUNG":
				for audio_node: Node in get_tree().get_nodes_in_group("church_audio_runtime"):
					if audio_node.has_method("ring_bell"):
						audio_node.call("ring_bell")
		_:
			pass

	print(
		"XZOGOT_NETWORK_WORLD_INTERACTION ",
		name,
		" used=", used,
		" power=", power_on,
		" result=", last_result
	)

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
	if requires_power and not bool(get_tree().get_meta("power_on", false)):
		return "POWER REQUIRED"
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

func get_perk_id() -> String:
	return perk_id

func is_power_required() -> bool:
	return requires_power
