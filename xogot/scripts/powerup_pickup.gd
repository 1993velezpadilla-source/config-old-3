extends Node3D
class_name XzPowerUpPickup

var kind: String = ""
var manager: Node
var lifetime: float = 30.0
var _base_y: float = 0.0
var _age: float = 0.0
var _collected: bool = false
var _network_proxy: bool = false

func configure(powerup_kind: String, owner_manager: Node, seconds: float = 30.0) -> void:
	kind = powerup_kind
	manager = owner_manager
	lifetime = seconds
	_network_proxy = false

func configure_network_proxy(powerup_kind: String, seconds: float = 30.0) -> void:
	kind = powerup_kind
	manager = null
	lifetime = seconds
	_network_proxy = true
	set_meta("network_proxy", true)

func is_network_proxy() -> bool:
	return _network_proxy

func get_powerup_kind() -> String:
	return kind

func get_lifetime() -> float:
	return lifetime

func _ready() -> void:
	add_to_group("xz_powerup_pickup")
	_base_y = position.y
	_build_visual()
	set_process(true)
	print("XZOGOT_POWERUP_DROP_READY ", kind)

func _build_visual() -> void:
	var root := Node3D.new()
	root.name = "PowerUpVisual"
	add_child(root)

	var mesh_instance := MeshInstance3D.new()
	mesh_instance.name = "PowerUpCore"
	var mesh := CylinderMesh.new()
	mesh.top_radius = 0.30
	mesh.bottom_radius = 0.30
	mesh.height = 0.18
	var mat := StandardMaterial3D.new()
	mat.roughness = 0.24
	mat.metallic = 0.18
	mat.emission_enabled = true
	match kind:
		"max_ammo":
			mat.albedo_color = Color(0.20, 0.72, 0.26)
			mat.emission = Color(0.08, 0.45, 0.12)
		"double_points":
			mat.albedo_color = Color(0.95, 0.72, 0.16)
			mat.emission = Color(0.68, 0.38, 0.05)
		"insta_kill":
			mat.albedo_color = Color(0.86, 0.18, 0.16)
			mat.emission = Color(0.52, 0.04, 0.03)
		"nuke":
			mat.albedo_color = Color(0.32, 0.80, 0.76)
			mat.emission = Color(0.06, 0.52, 0.48)
		"carpenter":
			mat.albedo_color = Color(0.56, 0.34, 0.14)
			mat.emission = Color(0.28, 0.12, 0.03)
		_:
			mat.albedo_color = Color(0.85, 0.85, 0.85)
			mat.emission = Color(0.35, 0.35, 0.35)
	mat.emission_energy_multiplier = 2.6
	mesh.material = mat
	mesh_instance.mesh = mesh
	root.add_child(mesh_instance)

	var label := Label3D.new()
	label.name = "PowerUpLabel"
	label.text = _display_name()
	label.font_size = 34
	label.outline_size = 8
	label.position = Vector3(0.0, 0.48, 0.0)
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	root.add_child(label)

func _display_name() -> String:
	match kind:
		"max_ammo": return "MAX AMMO"
		"double_points": return "DOUBLE POINTS"
		"insta_kill": return "INSTA-KILL"
		"nuke": return "NUKE"
		"carpenter": return "CARPENTER"
	return kind.to_upper()

func _process(delta: float) -> void:
	if _collected:
		return
	_age += delta
	lifetime -= delta
	rotation.y += delta * 1.85
	position.y = _base_y + sin(_age * 3.1) * 0.10

	if lifetime <= 0.0:
		print("XZOGOT_POWERUP_DROP_EXPIRED ", kind)
		queue_free()
		return

	if _network_proxy:
		return

	for player: Node in get_tree().get_nodes_in_group("player"):
		if not (player is Node3D):
			continue
		if global_position.distance_to((player as Node3D).global_position) <= 1.35:
			_collected = true
			if manager != null and is_instance_valid(manager) and manager.has_method("collect_powerup"):
				manager.call("collect_powerup", kind, player)
			queue_free()
			return
