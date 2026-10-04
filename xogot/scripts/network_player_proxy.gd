extends CharacterBody3D
class_name XzNetworkPlayerProxy

@export var interpolation_speed: float = 14.0
@export var bleedout_duration: float = 45.0
@export var revive_hold_duration: float = 4.0

var peer_id: int = 0
var display_name: String = ""
var health: float = 100.0
var max_health: float = 100.0
var downed: bool = false
var eliminated: bool = false
var bleedout_remaining: float = 0.0
var revive_progress: float = 0.0
var _revive_contact_grace: float = 0.0
var _revive_source: Node = null
var _target_position := Vector3.ZERO
var _target_yaw: float = 0.0
var _target_pitch: float = 0.0
var _snapshot_ready: bool = false

func configure(id: int, label: String = "") -> void:
	peer_id = id
	display_name = label if not label.is_empty() else "PLAYER %d" % id
	name = "RemotePlayer_%d" % id
	set_meta("network_peer_id", id)
	set_meta("network_remote", true)

func _ready() -> void:
	add_to_group("player")
	add_to_group("network_remote_player")
	_target_position = global_position
	_build_visual()
	set_process(true)
	print("XZOGOT_NETWORK_PROXY_READY peer=", peer_id)

func _build_visual() -> void:
	var mesh_instance := MeshInstance3D.new()
	mesh_instance.name = "RemoteBody"
	var capsule := CapsuleMesh.new()
	capsule.radius = 0.34
	capsule.height = 1.76
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.16, 0.18, 0.20)
	mat.roughness = 0.78
	mat.metallic = 0.10
	capsule.material = mat
	mesh_instance.mesh = capsule
	mesh_instance.position.y = 0.88
	add_child(mesh_instance)

	var label := Label3D.new()
	label.name = "RemoteName"
	label.text = display_name
	label.position = Vector3(0.0, 2.02, 0.0)
	label.font_size = 28
	label.outline_size = 7
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	add_child(label)

func _process(delta: float) -> void:
	if _snapshot_ready:
		var blend: float = 1.0 - exp(-interpolation_speed * delta)
		global_position = global_position.lerp(_target_position, blend)
		rotation.y = lerp_angle(rotation.y, _target_yaw, blend)
	if downed and not eliminated:
		bleedout_remaining = maxf(0.0, bleedout_remaining - delta)
		if _revive_contact_grace > 0.0:
			_revive_contact_grace = maxf(0.0, _revive_contact_grace - delta)
		if _revive_contact_grace <= 0.0 and revive_progress > 0.0:
			revive_progress = 0.0
			_revive_source = null
		if bleedout_remaining <= 0.0:
			eliminated = true

func apply_network_state(
	pos: Vector3,
	yaw: float,
	pitch: float,
	server_health: float,
	server_downed: bool,
	server_eliminated: bool,
	server_bleedout: float,
	server_revive_ratio: float
) -> void:
	if not _snapshot_ready:
		global_position = pos
		_snapshot_ready = true
	_target_position = pos
	_target_yaw = yaw
	_target_pitch = pitch
	health = maxf(0.0, server_health)
	downed = server_downed
	eliminated = server_eliminated
	bleedout_remaining = maxf(0.0, server_bleedout)
	revive_progress = clampf(server_revive_ratio, 0.0, 1.0) * revive_hold_duration
	set_meta("downed", downed)
	set_meta("eliminated", eliminated)
	set_meta("bleedout_remaining", bleedout_remaining)
	set_meta("revive_progress_ratio", get_revive_progress_ratio())

func apply_damage(amount: float) -> void:
	if eliminated or downed or amount <= 0.0:
		return
	health = maxf(0.0, health - amount)
	if health <= 0.0:
		downed = true
		bleedout_remaining = bleedout_duration
		revive_progress = 0.0
		set_meta("downed", true)
		print("XZOGOT_NETWORK_PROXY_DOWN peer=", peer_id)

func receive_revive_progress(reviver: Node, delta: float) -> bool:
	if not downed or eliminated or reviver == null or delta <= 0.0:
		return false
	if not (reviver is Node3D):
		return false
	if global_position.distance_to((reviver as Node3D).global_position) > 2.4:
		return false
	if _revive_source != null and _revive_source != reviver:
		revive_progress = 0.0
	_revive_source = reviver
	_revive_contact_grace = 0.30
	revive_progress = minf(revive_hold_duration, revive_progress + delta)
	if revive_progress + 0.0001 >= revive_hold_duration:
		downed = false
		eliminated = false
		health = maxf(1.0, max_health * 0.50)
		bleedout_remaining = 0.0
		revive_progress = 0.0
		_revive_source = null
		print("XZOGOT_NETWORK_PROXY_REVIVED peer=", peer_id)
	return true

func is_downed() -> bool:
	return downed

func is_eliminated() -> bool:
	return eliminated

func get_health() -> float:
	return health

func get_bleedout_remaining() -> float:
	return bleedout_remaining

func get_revive_progress_ratio() -> float:
	return clampf(revive_progress / maxf(revive_hold_duration, 0.001), 0.0, 1.0)

func get_network_pitch() -> float:
	return _target_pitch

func get_network_peer_id() -> int:
	return peer_id
