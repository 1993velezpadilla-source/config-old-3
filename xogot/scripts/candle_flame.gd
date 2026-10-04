extends Node3D
class_name XzCandleFlame

enum FlameState {
	OFF,
	DIM,
	NORMAL,
	STRONG,
	FLICKER_HEAVY,
}

var state: int = FlameState.NORMAL
var wants_dynamic_light: bool = false
var wax_height_m: float = 0.28
var wax_radius_m: float = 0.035
var world_scale: float = 1.0
var seed_value: int = 1
var base_energy: float = 0.72
var light_range_m: float = 3.6
var shadowed: bool = false
var flame_visible_distance_m: float = 26.0

var _phase: float = 0.0
var _time: float = 0.0
var _light_budget_enabled: bool = false
var _event_timer: float = 0.0
var _event_duration: float = 0.0
var _event_strength: float = 0.0
var _event_phase: float = 0.0
var _round_instability: float = 0.0
var _flame_outer: MeshInstance3D
var _flame_inner: MeshInstance3D
var _wick: MeshInstance3D
var _light: OmniLight3D
var _body: MeshInstance3D

func configure(config: Dictionary) -> void:
	state = int(config.get("state", FlameState.NORMAL))
	wants_dynamic_light = bool(config.get("dynamic_light", false))
	wax_height_m = float(config.get("height", wax_height_m))
	wax_radius_m = float(config.get("radius", wax_radius_m))
	world_scale = float(config.get("world_scale", world_scale))
	seed_value = int(config.get("seed", seed_value))
	base_energy = float(config.get("energy", base_energy))
	light_range_m = float(config.get("range", light_range_m))
	shadowed = bool(config.get("shadowed", false))
	flame_visible_distance_m = float(config.get("visibility_end", flame_visible_distance_m))

func _ready() -> void:
	_phase = float(abs(seed_value * 1103515245 + 12345) % 10000) * 0.000628
	_build_candle()
	_apply_state_static()
	set_process(state != FlameState.OFF)
	add_to_group("xz_candle")
	if wants_dynamic_light:
		add_to_group("xz_candle_light_candidate")

func _make_material(color: Color, roughness: float, emission: Color = Color(0, 0, 0, 1), emission_energy: float = 0.0) -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.roughness = roughness
	if emission_energy > 0.0:
		mat.emission_enabled = true
		mat.emission = emission
		mat.emission_energy_multiplier = emission_energy
	return mat

func _build_candle() -> void:
	var body_mesh := CylinderMesh.new()
	body_mesh.top_radius = wax_radius_m * world_scale * 0.92
	body_mesh.bottom_radius = wax_radius_m * world_scale
	body_mesh.height = wax_height_m * world_scale
	body_mesh.radial_segments = 10
	var warm_variation: float = float(abs(seed_value) % 7) * 0.008
	body_mesh.material = _make_material(
		Color(0.74 + warm_variation, 0.60 + warm_variation * 0.5, 0.39, 1.0),
		0.90
	)
	_body = MeshInstance3D.new()
	_body.name = "Wax"
	_body.mesh = body_mesh
	_body.position.y = body_mesh.height * 0.5
	_body.visibility_range_end = flame_visible_distance_m * world_scale
	_body.visibility_range_end_margin = 3.0 * world_scale
	_body.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
	add_child(_body)

	# A small uneven wax lip makes repeated candles less toy-like.
	var lip_mesh := CylinderMesh.new()
	lip_mesh.top_radius = wax_radius_m * world_scale * 0.88
	lip_mesh.bottom_radius = wax_radius_m * world_scale * 1.02
	lip_mesh.height = 0.018 * world_scale
	lip_mesh.radial_segments = 10
	lip_mesh.material = body_mesh.material
	var lip := MeshInstance3D.new()
	lip.name = "MeltedWaxLip"
	lip.mesh = lip_mesh
	lip.position = Vector3(
		sin(_phase * 2.7) * 0.006 * world_scale,
		wax_height_m * world_scale + 0.002 * world_scale,
		cos(_phase * 1.9) * 0.006 * world_scale
	)
	add_child(lip)

	var wick_mesh := CylinderMesh.new()
	wick_mesh.top_radius = 0.0045 * world_scale
	wick_mesh.bottom_radius = 0.0055 * world_scale
	wick_mesh.height = 0.038 * world_scale
	wick_mesh.radial_segments = 6
	wick_mesh.material = _make_material(Color(0.025, 0.018, 0.012, 1.0), 0.96)
	_wick = MeshInstance3D.new()
	_wick.name = "Wick"
	_wick.mesh = wick_mesh
	_wick.position.y = wax_height_m * world_scale + wick_mesh.height * 0.48
	add_child(_wick)

	# Two nested emissive ellipsoids give a proper hot core + orange outer flame
	# without a texture lookup or particle system.
	var outer_mesh := SphereMesh.new()
	outer_mesh.radius = 0.050 * world_scale
	outer_mesh.height = 0.155 * world_scale
	outer_mesh.radial_segments = 8
	outer_mesh.rings = 5
	outer_mesh.material = _make_material(
		Color(1.0, 0.20, 0.025, 1.0),
		0.15,
		Color(1.0, 0.14, 0.015),
		5.2
	)
	_flame_outer = MeshInstance3D.new()
	_flame_outer.name = "FlameOuter"
	_flame_outer.mesh = outer_mesh
	_flame_outer.position.y = (wax_height_m + 0.105) * world_scale
	_flame_outer.visibility_range_end = flame_visible_distance_m * world_scale
	_flame_outer.visibility_range_end_margin = 4.0 * world_scale
	_flame_outer.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
	add_child(_flame_outer)

	var inner_mesh := SphereMesh.new()
	inner_mesh.radius = 0.025 * world_scale
	inner_mesh.height = 0.090 * world_scale
	inner_mesh.radial_segments = 7
	inner_mesh.rings = 4
	inner_mesh.material = _make_material(
		Color(1.0, 0.78, 0.32, 1.0),
		0.08,
		Color(1.0, 0.70, 0.22),
		7.4
	)
	_flame_inner = MeshInstance3D.new()
	_flame_inner.name = "FlameCore"
	_flame_inner.mesh = inner_mesh
	_flame_inner.position.y = (wax_height_m + 0.087) * world_scale
	_flame_inner.visibility_range_end = flame_visible_distance_m * world_scale
	_flame_inner.visibility_range_end_margin = 4.0 * world_scale
	_flame_inner.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
	add_child(_flame_inner)

	_light = OmniLight3D.new()
	_light.name = "CandleLight"
	_light.position.y = (wax_height_m + 0.18) * world_scale
	_light.light_color = Color(1.0, 0.43, 0.14)
	_light.light_energy = base_energy
	_light.omni_range = light_range_m * world_scale
	_light.shadow_enabled = shadowed
	_light.visible = false
	add_child(_light)

func _state_gain() -> float:
	match state:
		FlameState.DIM:
			return 0.48
		FlameState.STRONG:
			return 1.34
		FlameState.FLICKER_HEAVY:
			return 1.10
		FlameState.NORMAL:
			return 1.0
	return 0.0

func _state_flicker_amount() -> float:
	match state:
		FlameState.DIM:
			return 0.08
		FlameState.STRONG:
			return 0.16
		FlameState.FLICKER_HEAVY:
			return 0.34
		FlameState.NORMAL:
			return 0.13
	return 0.0

func _apply_state_static() -> void:
	var burning: bool = state != FlameState.OFF
	if _flame_outer != null:
		_flame_outer.visible = burning
	if _flame_inner != null:
		_flame_inner.visible = burning
	if _light != null:
		_light.visible = burning and wants_dynamic_light and _light_budget_enabled

func set_light_budget_enabled(enabled: bool) -> void:
	_light_budget_enabled = enabled
	if _light != null:
		_light.visible = enabled and wants_dynamic_light and state != FlameState.OFF

func has_real_light_request() -> bool:
	return wants_dynamic_light and state != FlameState.OFF

func get_light_anchor_position() -> Vector3:
	if _light != null:
		return _light.global_position
	return global_position

func trigger_event_flicker(duration: float, strength: float, phase_offset: float = 0.0) -> void:
	if state == FlameState.OFF:
		return
	_event_duration = maxf(duration, 0.01)
	_event_timer = _event_duration
	_event_strength = clampf(strength, 0.0, 1.0)
	_event_phase = phase_offset

func set_round_instability(round_number: int) -> void:
	if round_number < 8:
		_round_instability = 0.0
		return
	_round_instability = clampf(float(round_number - 7) * 0.012, 0.0, 0.16)

func is_event_active() -> bool:
	return _event_timer > 0.0

func get_state_name() -> String:
	match state:
		FlameState.OFF:
			return "OFF"
		FlameState.DIM:
			return "DIM"
		FlameState.NORMAL:
			return "NORMAL"
		FlameState.STRONG:
			return "STRONG"
		FlameState.FLICKER_HEAVY:
			return "FLICKER_HEAVY"
	return "UNKNOWN"

func _process(delta: float) -> void:
	if state == FlameState.OFF:
		return
	_time += delta
	_event_timer = maxf(0.0, _event_timer - delta)

	var speed: float = 5.1
	if state == FlameState.DIM:
		speed = 3.2
	elif state == FlameState.STRONG:
		speed = 5.8
	elif state == FlameState.FLICKER_HEAVY:
		speed = 8.4

	var a: float = sin(_time * speed + _phase)
	var b: float = sin(_time * speed * 1.77 + _phase * 2.3)
	var d: float = sin(_time * speed * 0.47 + _phase * 0.71)
	var flicker: float = a * 0.55 + b * 0.30 + d * 0.15
	var amount: float = _state_flicker_amount() + _round_instability
	var gain: float = _state_gain()

	var event_wave: float = 0.0
	var event_envelope: float = 0.0
	if _event_timer > 0.0:
		var progress: float = 1.0 - (_event_timer / maxf(_event_duration, 0.01))
		event_envelope = sin(progress * PI)
		event_wave = (
			sin(_time * 20.0 + _phase + _event_phase) * 0.62
			+ sin(_time * 33.0 + _phase * 1.7 + _event_phase) * 0.38
		) * _event_strength * event_envelope
		flicker += event_wave

	var sway_x: float = sin(_time * speed * 0.61 + _phase) * (0.020 + event_envelope * _event_strength * 0.018) * world_scale
	var sway_z: float = cos(_time * speed * 0.49 + _phase * 1.3) * 0.014 * world_scale
	var flame_scale: float = 1.0 + flicker * (0.08 + amount * 0.22)

	if _flame_outer != null:
		_flame_outer.position.x = sway_x
		_flame_outer.position.z = sway_z
		_flame_outer.scale = Vector3(
			1.0 - flicker * 0.045,
			maxf(0.72, flame_scale),
			1.0 - flicker * 0.045
		)
	if _flame_inner != null:
		_flame_inner.position.x = sway_x * 0.72
		_flame_inner.position.z = sway_z * 0.72
		_flame_inner.scale.y = maxf(0.78, 1.0 + flicker * 0.07)

	if _light != null and _light.visible:
		var energy_flicker: float = 1.0 + flicker * amount
		var event_gain: float = 1.0 + event_wave * 0.38
		_light.light_energy = maxf(0.05, base_energy * gain * energy_flicker * event_gain)
		var warmth: float = clampf(0.42 + flicker * 0.045, 0.34, 0.52)
		_light.light_color = Color(1.0, warmth, 0.105 + warmth * 0.11)
