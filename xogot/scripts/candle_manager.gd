extends Node3D
class_name XzCandleManager

const CandleFlame = preload("res://scripts/candle_flame.gd")

@export var max_dynamic_lights: int = 8
@export var light_budget_radius_m: float = 22.0
@export var budget_refresh_seconds: float = 0.22

var world_scale: float = 1.0
var _player: Node3D
var _candles: Array[Node3D] = []
var _budget_timer: float = 0.0
var _round_manager: Node
var _last_round: int = 0
var _last_power_state: bool = false
var _event_serial: int = 0
var _state_counts: Dictionary = {
	"OFF": 0,
	"DIM": 0,
	"NORMAL": 0,
	"STRONG": 0,
	"FLICKER_HEAVY": 0,
}

func configure(scale_value: float, player: Node3D) -> void:
	world_scale = scale_value
	_player = player

func _ready() -> void:
	add_to_group("xz_candle_manager")
	_round_manager = _find_round_manager()
	_last_round = _read_round()
	_last_power_state = _read_power_state()
	_build_layout()
	_apply_round_instability(_last_round)
	_refresh_light_budget()
	set_process(true)
	print(
		"XZOGOT_CANDLE_SYSTEM_READY candles=",
		_candles.size(),
		" states=",
		_state_counts,
		" light_budget=",
		max_dynamic_lights
	)

func _find_round_manager() -> Node:
	var scene: Node = get_tree().current_scene
	if scene != null:
		var node: Node = scene.get_node_or_null("RoundManager")
		if node != null:
			return node
	return null

func _read_round() -> int:
	if _round_manager == null or not is_instance_valid(_round_manager):
		_round_manager = _find_round_manager()
	if _round_manager != null and _round_manager.has_method("get_round"):
		return int(_round_manager.call("get_round"))
	return 0

func _read_power_state() -> bool:
	return get_tree().has_meta("power_on") and bool(get_tree().get_meta("power_on"))

func _apply_round_instability(round_number: int) -> void:
	for candle: Node3D in _candles:
		if candle.has_method("set_round_instability"):
			candle.call("set_round_instability", round_number)

func _trigger_candle_event(tag: String, duration: float, strength: float) -> void:
	_event_serial += 1
	for i in range(_candles.size()):
		var candle: Node3D = _candles[i]
		if candle.has_method("trigger_event_flicker"):
			var phase_offset: float = float((_event_serial * 17 + i * 31) % 360) * PI / 180.0
			candle.call("trigger_event_flicker", duration, strength, phase_offset)
	print("XZOGOT_CANDLE_EVENT ", tag, " duration=", duration, " strength=", strength)

func _poll_world_events() -> void:
	var power_now: bool = _read_power_state()
	if power_now != _last_power_state:
		_last_power_state = power_now
		if power_now:
			_trigger_candle_event("POWER_ON_SURGE", 2.2, 0.72)
		else:
			_trigger_candle_event("POWER_OFF_GUST", 1.35, 0.44)

	var round_now: int = _read_round()
	if round_now != _last_round:
		_last_round = round_now
		_apply_round_instability(round_now)
		if round_now > 0:
			var strength: float = clampf(0.18 + float(maxi(0, round_now - 5)) * 0.015, 0.18, 0.42)
			_trigger_candle_event("ROUND_%d" % round_now, 0.85, strength)

func _state_for(seed_value: int, lit_bias: float = 0.78) -> int:
	var v: int = abs(seed_value * 37 + 17) % 100
	var off_cut: int = int(round((1.0 - lit_bias) * 100.0))
	if v < off_cut:
		return CandleFlame.FlameState.OFF
	if v < off_cut + 15:
		return CandleFlame.FlameState.DIM
	if v < 76:
		return CandleFlame.FlameState.NORMAL
	if v < 93:
		return CandleFlame.FlameState.STRONG
	return CandleFlame.FlameState.FLICKER_HEAVY

func _spawn_candle(
	label: String,
	local_position_m: Vector3,
	height_m: float,
	seed_value: int,
	lit_bias: float,
	dynamic_light: bool,
	base_energy: float = 0.72,
	light_range_m: float = 3.6,
	visibility_end_m: float = 26.0
) -> Node3D:
	var candle := Node3D.new()
	candle.name = label
	candle.position = local_position_m * world_scale
	candle.set_script(CandleFlame)
	candle.call(
		"configure",
		{
			"state": _state_for(seed_value, lit_bias),
			"dynamic_light": dynamic_light,
			"height": height_m,
			"radius": 0.032 + float(abs(seed_value) % 4) * 0.0035,
			"world_scale": world_scale,
			"seed": seed_value,
			"energy": base_energy,
			"range": light_range_m,
			"shadowed": false,
			"visibility_end": visibility_end_m,
		}
	)
	add_child(candle)
	_candles.append(candle)
	return candle

func _record_states() -> void:
	for key: String in _state_counts.keys():
		_state_counts[key] = 0
	for candle: Node3D in _candles:
		var state_name: String = str(candle.call("get_state_name"))
		_state_counts[state_name] = int(_state_counts.get(state_name, 0)) + 1

func _add_altar_clusters() -> void:
	# Front altar row: deliberately uneven height and burn state.
	for i in range(9):
		var x: float = -2.40 + float(i) * 0.60
		var height: float = 0.20 + float((i * 5 + 2) % 6) * 0.035
		_spawn_candle(
			"AltarFront_%02d" % i,
			Vector3(x, 1.12, -20.10),
			height,
			101 + i,
			0.86,
			i in [1, 4, 7],
			0.82,
			4.0,
			30.0
		)

	# Rear sanctuary groups are asymmetrical on purpose.
	var rear_positions: Array[Vector3] = [
		Vector3(-2.20, 1.28, -22.36),
		Vector3(-1.75, 1.28, -22.30),
		Vector3(-1.30, 1.28, -22.34),
		Vector3(1.15, 1.28, -22.32),
		Vector3(1.62, 1.28, -22.30),
		Vector3(2.12, 1.28, -22.36),
	]
	for i in range(rear_positions.size()):
		_spawn_candle(
			"AltarRear_%02d" % i,
			rear_positions[i],
			0.27 + float((i * 3) % 4) * 0.045,
			150 + i,
			0.82,
			i == 1 or i == 4,
			0.88,
			4.3,
			31.0
		)

func _add_side_chapel_clusters() -> void:
	var positions: Array[Vector3] = [
		Vector3(13.0, 1.36, -17.72),
		Vector3(13.45, 1.36, -17.72),
		Vector3(13.90, 1.36, -17.72),
		Vector3(16.55, 1.38, -16.05),
		Vector3(16.95, 1.38, -16.05),
		Vector3(17.35, 1.38, -16.05),
		Vector3(17.65, 0.74, -12.25),
		Vector3(17.65, 0.74, -11.82),
	]
	for i in range(positions.size()):
		_spawn_candle(
			"Sacristy_%02d" % i,
			positions[i],
			0.18 + float((i * 7) % 5) * 0.045,
			220 + i,
			0.70,
			i in [0, 4],
			0.64,
			3.2,
			22.0
		)

func _add_crypt_cluster() -> void:
	var positions: Array[Vector3] = [
		Vector3(14.3, -2.65, -15.1),
		Vector3(14.75, -2.65, -15.4),
		Vector3(15.2, -2.65, -15.0),
		Vector3(16.9, -2.65, -16.2),
		Vector3(17.3, -2.65, -16.5),
		Vector3(17.7, -2.65, -16.1),
	]
	for i in range(positions.size()):
		_spawn_candle(
			"Crypt_%02d" % i,
			positions[i],
			0.16 + float((i * 11) % 4) * 0.04,
			310 + i,
			0.60,
			i == 2 or i == 4,
			0.55,
			2.8,
			17.0
		)

func _add_wall_candles() -> void:
	var zs: Array[float] = [-15.0, -7.0, 1.0, 8.0]
	var serial: int = 0
	for z: float in zs:
		for side in [-1.0, 1.0]:
			_spawn_candle(
				"NaveWall_%02d" % serial,
				Vector3(9.72 * side, 2.15, z),
				0.23 + float(serial % 3) * 0.035,
				400 + serial,
				0.68,
				serial in [1, 4, 6],
				0.54,
				3.1,
				24.0
			)
			serial += 1

func _add_chandelier_ring(
	tag: String,
	center_m: Vector3,
	radius_m: float,
	count: int,
	seed_base: int,
	lit_bias: float
) -> void:
	for i in range(count):
		var angle: float = TAU * float(i) / float(count)
		var wobble: float = 1.0 + sin(float(seed_base + i) * 0.77) * 0.06
		var p := center_m + Vector3(
			cos(angle) * radius_m * wobble,
			sin(angle * 2.0 + float(seed_base)) * 0.025,
			sin(angle) * radius_m * wobble
		)
		_spawn_candle(
			"%s_%02d" % [tag, i],
			p,
			0.18 + float((seed_base + i * 3) % 5) * 0.026,
			seed_base + i,
			lit_bias,
			i == 0 or i == int(count / 2),
			0.58,
			3.4,
			34.0
		)

func _add_chandelier_clusters() -> void:
	# Each fixture has a different burn ratio. Some are almost complete,
	# some have several dead candles, so the nave never reads copy-pasted.
	_add_chandelier_ring("Chandelier01", Vector3(0.0, 5.98, 8.2), 0.58, 7, 510, 0.88)
	_add_chandelier_ring("Chandelier02", Vector3(0.0, 5.98, 1.2), 0.54, 6, 540, 0.68)
	_add_chandelier_ring("Chandelier03", Vector3(0.0, 5.98, -6.0), 0.61, 8, 570, 0.80)
	_add_chandelier_ring("Chandelier04", Vector3(0.0, 5.98, -13.0), 0.52, 6, 610, 0.58)
	_add_chandelier_ring("SanctuaryChandelier", Vector3(0.0, 5.72, -19.3), 0.66, 8, 650, 0.92)

func _build_layout() -> void:
	_add_altar_clusters()
	_add_side_chapel_clusters()
	_add_crypt_cluster()
	_add_wall_candles()
	_add_chandelier_clusters()
	_record_states()

func _process(delta: float) -> void:
	_budget_timer -= delta
	if _budget_timer <= 0.0:
		_budget_timer = budget_refresh_seconds
		_poll_world_events()
		_refresh_light_budget()

func _refresh_light_budget() -> void:
	var candidates: Array[Node3D] = []
	for candle: Node3D in _candles:
		if candle.has_method("set_light_budget_enabled"):
			candle.call("set_light_budget_enabled", false)
		if candle.has_method("has_real_light_request") and bool(candle.call("has_real_light_request")):
			candidates.append(candle)

	var selected: Dictionary = {}
	var radius_sq: float = light_budget_radius_m * light_budget_radius_m * world_scale * world_scale
	for budget_index in range(max_dynamic_lights):
		var best: Node3D = null
		var best_d2: float = INF
		for candle: Node3D in candidates:
			if selected.has(candle.get_instance_id()):
				continue
			var anchor: Vector3 = candle.global_position
			if candle.has_method("get_light_anchor_position"):
				anchor = candle.call("get_light_anchor_position")
			var d2: float = 0.0
			if _player != null and is_instance_valid(_player):
				d2 = _player.global_position.distance_squared_to(anchor)
				if d2 > radius_sq:
					continue
			else:
				d2 = candle.get_index()
			if d2 < best_d2:
				best_d2 = d2
				best = candle
		if best == null:
			break
		selected[best.get_instance_id()] = true
		best.call("set_light_budget_enabled", true)

	set_meta("active_dynamic_lights", selected.size())

func get_last_observed_round() -> int:
	return _last_round

func get_last_power_state() -> bool:
	return _last_power_state

func get_event_serial() -> int:
	return _event_serial

func get_candle_count() -> int:
	return _candles.size()

func get_active_dynamic_light_count() -> int:
	return int(get_meta("active_dynamic_lights", 0))

func get_state_counts() -> Dictionary:
	return _state_counts.duplicate(true)
