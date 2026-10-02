extends Node3D

const NAV_PATH := "res://data/nav_skeleton.json"

func _ready() -> void:
	_configure_environment()
	_add_moon()
	_add_nave_practicals()

func _read_nav() -> Dictionary:
	if not FileAccess.file_exists(NAV_PATH):
		return {}
	var f := FileAccess.open(NAV_PATH, FileAccess.READ)
	var parsed = JSON.parse_string(f.get_as_text())
	return parsed if parsed is Dictionary else {}

func _b2g(a: Array) -> Vector3:
	# Blender Z-up -> Godot Y-up. This matches Blender's glTF Y-up export.
	return Vector3(float(a[0]), float(a[2]), -float(a[1]))

func _configure_environment() -> void:
	var world_env := WorldEnvironment.new()
	world_env.name = "NightEnvironment"
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.008, 0.012, 0.022)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.20, 0.26, 0.40)
	env.ambient_light_energy = 0.58
	env.reflected_light_source = Environment.REFLECTION_SOURCE_DISABLED
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = 1.12
	env.fog_enabled = true
	env.fog_light_color = Color(0.10, 0.14, 0.22)
	env.fog_light_energy = 0.65
	env.fog_density = 0.006
	env.fog_height = 2.0
	env.fog_height_density = 0.035
	world_env.environment = env
	add_child(world_env)

func _add_moon() -> void:
	var moon := DirectionalLight3D.new()
	moon.name = "MoonKey"
	moon.light_color = Color(0.46, 0.60, 1.0)
	moon.light_energy = 1.05
	moon.shadow_enabled = true
	moon.directional_shadow_max_distance = 70.0
	moon.rotation_degrees = Vector3(-54.0, -32.0, 0.0)
	add_child(moon)

func _add_nave_practicals() -> void:
	var nav := _read_nav()
	if nav.is_empty():
		return
	var nave: Dictionary = {}
	for floor in nav.get("floors", []):
		if str(floor.get("id", "")) == "nave_center":
			nave = floor
			break
	if nave.is_empty():
		return
	var mn: Array = nave["min"]
	var mx: Array = nave["max"]
	var x := (float(mn[0]) + float(mx[0])) * 0.5
	var z := float(mx[2]) + 2.7
	for t in [0.20, 0.50, 0.80]:
		var by := lerp(float(mn[1]), float(mx[1]), float(t))
		var light := OmniLight3D.new()
		light.name = "WarmPractical_%02d" % int(float(t) * 100.0)
		light.position = _b2g([x, by, z])
		light.light_color = Color(1.0, 0.43, 0.16)
		light.light_energy = 4.2
		light.omni_range = 8.0
		light.shadow_enabled = true
		add_child(light)
