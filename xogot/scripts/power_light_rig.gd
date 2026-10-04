extends Node3D
class_name XzPowerLightRig

@export var startup_duration: float = 1.55
@export var poll_interval: float = 0.12

var _fixtures: Array[OmniLight3D] = []
var _base_energy: Dictionary = {}
var _powered: bool = false
var _sequence_active: bool = false
var _sequence_time: float = 0.0
var _poll_timer: float = 0.0
var _startup_serial: int = 0

func _ready() -> void:
	add_to_group("xz_power_light_rig")
	_collect_fixtures(self)
	for fixture: OmniLight3D in _fixtures:
		var base: float = fixture.light_energy
		_base_energy[fixture.get_instance_id()] = base
		fixture.light_energy = 0.0
		fixture.visible = false
		fixture.shadow_enabled = false

	_powered = _read_power_state()
	if _powered:
		_apply_stable_power()
		set_process(false)
	else:
		set_process(true)

	print("XZOGOT_POWER_LIGHT_RIG_READY fixtures=", _fixtures.size(), " powered=", _powered)

func _collect_fixtures(node: Node) -> void:
	for child: Node in node.get_children():
		if child is OmniLight3D:
			var fixture := child as OmniLight3D
			_fixtures.append(fixture)
		for nested: Node in child.get_children():
			_collect_fixtures(nested)
		else:
			_collect_fixtures(child)

func _read_power_state() -> bool:
	return get_tree().has_meta("power_on") and bool(get_tree().get_meta("power_on"))

func _base(fixture: OmniLight3D) -> float:
	return float(_base_energy.get(fixture.get_instance_id(), 0.0))

func _set_fixture_gain(fixture: OmniLight3D, gain: float) -> void:
	var value: float = maxf(0.0, _base(fixture) * gain)
	fixture.light_energy = value
	fixture.visible = value > 0.01

func _apply_stable_power() -> void:
	for fixture: OmniLight3D in _fixtures:
		_set_fixture_gain(fixture, 1.0)
	_sequence_active = false
	_sequence_time = 0.0
	set_meta("sequence_active", false)
	print("XZOGOT_POWER_LIGHTS_STABLE ", _fixtures.size())

func _begin_startup_sequence() -> void:
	_powered = true
	_sequence_active = true
	_sequence_time = 0.0
	_startup_serial += 1
	set_meta("sequence_active", true)
	set_process(true)
	print("XZOGOT_POWER_LIGHT_STARTUP_BEGIN ", _startup_serial)

func _fixture_jitter(index: int, time_value: float) -> float:
	var p: float = float(index + 1) * 1.731 + float(_startup_serial) * 0.417
	var a: float = sin(time_value * 31.0 + p)
	var b: float = sin(time_value * 53.0 + p * 2.13)
	return a * 0.63 + b * 0.37

func _apply_startup_frame(t: float) -> void:
	for i in range(_fixtures.size()):
		var fixture: OmniLight3D = _fixtures[i]
		var gain: float = 0.0

		if t < 0.12:
			# First dirty electrical flash.
			gain = 1.55 + maxf(0.0, _fixture_jitter(i, t)) * 0.35
		elif t < 0.30:
			# Breaker trips momentarily.
			gain = 0.0
		elif t < 0.58:
			# Second attempt: only some fixtures catch.
			var gate: float = sin(float(i * 19 + _startup_serial * 7)) * 0.5 + 0.5
			var pulse: float = _fixture_jitter(i, t)
			gain = (0.25 + maxf(0.0, pulse) * 1.05) if gate > 0.34 else 0.0
		elif t < 1.08:
			# All fixtures begin to stabilize but still flicker independently.
			var blend: float = (t - 0.58) / 0.50
			gain = lerpf(0.42, 0.93, blend) + _fixture_jitter(i, t) * (0.24 * (1.0 - blend))
		else:
			var settle: float = clampf((t - 1.08) / maxf(startup_duration - 1.08, 0.01), 0.0, 1.0)
			gain = lerpf(0.90 + _fixture_jitter(i, t) * 0.06, 1.0, settle)

		_set_fixture_gain(fixture, maxf(0.0, gain))

func _process(delta: float) -> void:
	if _sequence_active:
		_sequence_time += delta
		_apply_startup_frame(_sequence_time)
		if _sequence_time >= startup_duration:
			_apply_stable_power()
			set_process(false)
		return

	_poll_timer -= delta
	if _poll_timer > 0.0:
		return
	_poll_timer = poll_interval

	var power_now: bool = _read_power_state()
	if power_now and not _powered:
		_begin_startup_sequence()

func dev_trigger_startup() -> void:
	_powered = false
	_begin_startup_sequence()

func is_powered() -> bool:
	return _powered

func is_sequence_active() -> bool:
	return _sequence_active

func get_fixture_count() -> int:
	return _fixtures.size()

func get_visible_fixture_count() -> int:
	var count: int = 0
	for fixture: OmniLight3D in _fixtures:
		if fixture.visible and fixture.light_energy > 0.01:
			count += 1
	return count
