extends Node3D

func _ready() -> void:
	_build_world()
	print("YOU_WONT_WIN: fresh foundation ready")

func _build_world() -> void:
	var world := WorldEnvironment.new()
	world.name = "WorldEnvironment"
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.012, 0.016, 0.025)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.20, 0.24, 0.32)
	env.ambient_light_energy = 0.55
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	world.environment = env
	add_child(world)

	var moon := DirectionalLight3D.new()
	moon.name = "Moon"
	moon.rotation_degrees = Vector3(-52.0, -28.0, 0.0)
	moon.light_color = Color(0.58, 0.68, 1.0)
	moon.light_energy = 1.1
	moon.shadow_enabled = true
	add_child(moon)

	_add_box("Ground", Vector3(60.0, 0.5, 70.0), Vector3(0.0, -0.25, 0.0), Color(0.055, 0.06, 0.07))
	_add_box("ChurchFloor", Vector3(20.0, 0.35, 34.0), Vector3(0.0, 0.18, -4.0), Color(0.16, 0.14, 0.12))
	_add_box("LeftWall", Vector3(0.7, 7.0, 34.0), Vector3(-10.0, 3.5, -4.0), Color(0.22, 0.20, 0.18))
	_add_box("RightWall", Vector3(0.7, 7.0, 34.0), Vector3(10.0, 3.5, -4.0), Color(0.22, 0.20, 0.18))
	_add_box("BackWall", Vector3(20.0, 7.0, 0.7), Vector3(0.0, 3.5, -21.0), Color(0.20, 0.18, 0.16))
	_add_box("FrontLeft", Vector3(7.5, 7.0, 0.7), Vector3(-6.25, 3.5, 13.0), Color(0.20, 0.18, 0.16))
	_add_box("FrontRight", Vector3(7.5, 7.0, 0.7), Vector3(6.25, 3.5, 13.0), Color(0.20, 0.18, 0.16))

	var camera := Camera3D.new()
	camera.name = "FoundationCamera"
	camera.position = Vector3(0.0, 8.5, 25.0)
	camera.rotation_degrees = Vector3(-12.0, 0.0, 0.0)
	camera.current = true
	add_child(camera)

func _add_box(label: String, size: Vector3, pos: Vector3, color: Color) -> void:
	var body := StaticBody3D.new()
	body.name = label
	body.position = pos
	var mesh_instance := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = size
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = 0.88
	mesh.material = material
	mesh_instance.mesh = mesh
	body.add_child(mesh_instance)
	var collider := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	collider.shape = shape
	body.add_child(collider)
	add_child(body)
