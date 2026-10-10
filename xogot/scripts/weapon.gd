extends Node

const WeaponCatalog = preload("res://scripts/weapon_catalog.gd")
const WeaponAssetRegistry = preload("res://scripts/weapon_asset_registry.gd")
const SourcePresentation = preload("res://scripts/weapon_viewmodel_source_presentation.gd")
const SourceHipPose = preload("res://scripts/weapon_viewmodel_source_pose.gd")

@export var damage: float = 24.0
@export var range_m: float = 95.0
@export var fire_interval: float = 0.17
@export var magazine_size: int = 8
@export var reserve_ammo: int = 80
@export var reload_time: float = 1.48
@export var allow_procedural_weapon_fallback: bool = false

var _weapon_id: String = WeaponCatalog.STARTING_WEAPON_ID
var _display_name: String = "Colt"
var _family: String = "pistol"
var _automatic: bool = false
var _pellets: int = 1
var _ads_fov: float = 49.0
var _hip_spread_deg: float = 1.45
var _ads_spread_deg: float = 0.28
var _visual_recoil_deg: float = 1.55

var _magazine: int = 8
var _cooldown: float = 0.0
var _reload_timer: float = 0.0
var _reloading: bool = false
var _trigger_held: bool = false
var _shots_fired: int = 0
var _mystery_serial: int = 0
var _visual_recoil_pitch: float = 0.0
var _visual_recoil_velocity: float = 0.0
var _ads_pose_alpha: float = 0.0
var _view_pose_position := Vector3(0.22, -0.20, -0.48)
var _view_root: Node3D
var _fire_audio: AudioStreamPlayer3D
var _reload_audio: AudioStreamPlayer3D
var _mechanical_audio: AudioStreamPlayer3D
var _dry_fire_audio: AudioStreamPlayer3D
var _asset_animation_player: AnimationPlayer
var _weapon_model_root: Node3D
var _hands_animation_player: AnimationPlayer
var _hands_model_root: Node3D
var _source_hands_skeleton: Skeleton3D
var _source_weapon_attachment: Node3D
var _source_weapon_bone_idx: int = -1
var _melee_animation_player: AnimationPlayer
var _melee_model_root: Node3D
var _melee_overlay_timer: float = 0.0
var _muzzle_anchor: Node3D
var _shell_anchor: Node3D
var _muzzle_flash_root: Node3D
var _muzzle_light: OmniLight3D
var _smoke_particles: GPUParticles3D
var _shell_particles: GPUParticles3D
var _muzzle_flash_timer: float = 0.0
var _last_ads_state: bool = false
var _real_hands_bound: bool = false
var _source_ads_ready: bool = false
var _source_hip: Vector3 = Vector3.ZERO
var _source_ads: Vector3 = Vector3.ZERO
var _source_ads_quat: Quaternion = Quaternion.IDENTITY
var _dev_infinite_ammo: bool = false
var _upgraded_ids: Dictionary = {}
var _upgraded: bool = false

@onready var _body: CollisionObject3D = get_parent() as CollisionObject3D
@onready var _camera: Camera3D = get_parent().get_node("Head/Camera3D") as Camera3D

func _ready() -> void:
	_build_view_runtime()
	equip_weapon(WeaponCatalog.STARTING_WEAPON_ID, true)
	print("XZOGOT_WEAPON_READY")
	print("XZOGOT_WEAPON_CATALOG_READY ", WeaponCatalog.WEAPONS.size())

func _process(delta: float) -> void:
	if _cooldown > 0.0:
		_cooldown = maxf(0.0, _cooldown - delta)

	if _reloading:
		_reload_timer -= delta
		if _reload_timer <= 0.0:
			_finish_reload()
	else:
		if _trigger_held and _automatic:
			request_fire()

	if _melee_overlay_timer > 0.0:
		_melee_overlay_timer = maxf(0.0, _melee_overlay_timer - delta)
		if _melee_overlay_timer <= 0.0:
			_finish_melee_overlay()
	_update_asset_animation_state()
	_update_visual_recoil(delta)
	_update_weapon_fx(delta)

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		set_trigger_held(event.pressed)
	elif event is InputEventKey and event.pressed and event.keycode == KEY_R:
		request_reload()

func _build_view_runtime() -> void:
	if _camera == null:
		return
	_view_root = Node3D.new()
	_view_root.name = "WeaponViewRoot"
	_view_pose_position = Vector3(0.22, -0.20, -0.48)
	_view_root.position = _view_pose_position
	_camera.add_child(_view_root)

	_fire_audio = AudioStreamPlayer3D.new()
	_fire_audio.name = "WeaponFireAudio"
	_fire_audio.unit_size = 1.4
	_fire_audio.max_distance = 55.0
	_camera.add_child(_fire_audio)

	_reload_audio = AudioStreamPlayer3D.new()
	_reload_audio.name = "WeaponReloadAudio"
	_reload_audio.unit_size = 1.2
	_reload_audio.max_distance = 24.0
	_camera.add_child(_reload_audio)

	_mechanical_audio = AudioStreamPlayer3D.new()
	_mechanical_audio.name = "WeaponMechanicalAudio"
	_mechanical_audio.unit_size = 1.0
	_mechanical_audio.max_distance = 18.0
	_camera.add_child(_mechanical_audio)

	_dry_fire_audio = AudioStreamPlayer3D.new()
	_dry_fire_audio.name = "WeaponDryFireAudio"
	_dry_fire_audio.unit_size = 0.9
	_dry_fire_audio.max_distance = 14.0
	_camera.add_child(_dry_fire_audio)

func _clear_view_model() -> void:
	_asset_animation_player = null
	_weapon_model_root = null
	_hands_animation_player = null
	_hands_model_root = null
	_source_hands_skeleton = null
	_source_weapon_attachment = null
	_source_weapon_bone_idx = -1
	set_meta("weapon_source_weapon_attachment_ready", false)
	set_meta("weapon_source_attachment_meter_units_restored", false)
	_real_hands_bound = false
	_source_ads_ready = false
	_melee_animation_player = null
	_melee_model_root = null
	_melee_overlay_timer = 0.0
	_muzzle_anchor = null
	_shell_anchor = null
	_muzzle_flash_root = null
	_muzzle_light = null
	_smoke_particles = null
	_shell_particles = null
	_muzzle_flash_timer = 0.0
	if _view_root == null:
		return
	for child: Node in _view_root.get_children():
		child.queue_free()

func _build_fallback_view_model() -> void:
	if _view_root == null:
		return

	var metal := StandardMaterial3D.new()
	metal.albedo_color = Color(0.075, 0.072, 0.067)
	metal.roughness = 0.40
	metal.metallic = 0.72

	var wood := StandardMaterial3D.new()
	wood.albedo_color = Color(0.16, 0.082, 0.035)
	wood.roughness = 0.72

	var receiver := MeshInstance3D.new()
	receiver.name = "FallbackReceiver"
	var receiver_mesh := BoxMesh.new()
	var receiver_size := Vector3(0.11, 0.10, 0.34)
	if _family == "pistol":
		receiver_size = Vector3(0.09, 0.09, 0.22)
	elif _family == "shotgun":
		receiver_size = Vector3(0.12, 0.11, 0.48)
	elif _family == "lmg":
		receiver_size = Vector3(0.14, 0.14, 0.52)
	elif _family == "sniper":
		receiver_size = Vector3(0.10, 0.10, 0.58)
	elif _family == "wonder":
		receiver_size = Vector3(0.14, 0.14, 0.38)
	receiver_mesh.size = receiver_size
	receiver_mesh.material = metal
	receiver.mesh = receiver_mesh
	receiver.position.z = -receiver_size.z * 0.45
	_view_root.add_child(receiver)

	var barrel := MeshInstance3D.new()
	barrel.name = "FallbackBarrel"
	var barrel_mesh := CylinderMesh.new()
	barrel_mesh.top_radius = 0.018
	barrel_mesh.bottom_radius = 0.022
	barrel_mesh.height = 0.30 if _family != "pistol" else 0.16
	barrel_mesh.radial_segments = 10
	barrel_mesh.material = metal
	barrel.mesh = barrel_mesh
	barrel.rotation_degrees.x = 90.0
	barrel.position = Vector3(0.0, 0.015, -receiver_size.z * 0.90 - barrel_mesh.height * 0.42)
	_view_root.add_child(barrel)

	if _family in ["rifle", "smg", "shotgun", "lmg", "sniper"]:
		var stock := MeshInstance3D.new()
		stock.name = "FallbackStock"
		var stock_mesh := BoxMesh.new()
		stock_mesh.size = Vector3(0.10, 0.13, 0.28)
		stock_mesh.material = wood
		stock.mesh = stock_mesh
		stock.position = Vector3(0.0, -0.025, 0.20)
		stock.rotation_degrees.x = -7.0
		_view_root.add_child(stock)

	set_meta("weapon_view_fallback", true)

func _find_animation_player(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node as AnimationPlayer
	for child: Node in node.get_children():
		var found := _find_animation_player(child)
		if found != null:
			return found
	return null

func _aux_animation_aliases(role: String) -> Array[String]:
	match role:
		"idle":
			return ["idle", "hold"]
		"fire":
			return ["fire", "shoot", "recoil"]
		"fire_ads":
			return ["ads_fire", "fire_ads", "aim_fire"]
		"reload":
			return ["reload", "rechamber", "mag", "clip"]
		"reload_empty":
			return ["reload_empty", "reloadempty", "empty_reload"]
		"equip":
			return ["equip", "pullout", "bringout", "raise"]
		"ads_in":
			return ["ads_in", "ads_up", "aim_in"]
		"ads_out":
			return ["ads_out", "ads_down", "aim_out"]
		"melee":
			return ["knife", "melee", "stab", "slash", "bash"]
		"perk_use":
			return ["perk", "drink", "bottle", "purchase", "use", "interact"]
		"machine_use":
			return ["use", "interact", "grab", "press", "machine"]
		_:
			return [role]

func _animation_name_for_aux_player(player: AnimationPlayer, role: String) -> String:
	if player == null or not is_instance_valid(player):
		return ""
	var aliases := _aux_animation_aliases(role)
	var best := ""
	var best_score := -1
	for anim_name: StringName in player.get_animation_list():
		var candidate := str(anim_name)
		var lower := candidate.to_lower()
		for alias: String in aliases:
			var token := alias.to_lower()
			if lower == token:
				return candidate
			if lower.contains(token) and token.length() > best_score:
				best_score = token.length()
				best = candidate
	return best

func _play_aux_animation(player: AnimationPlayer, role: String, blend: float = 0.06) -> bool:
	var animation_name := _animation_name_for_aux_player(player, role)
	if animation_name.is_empty():
		return false
	player.play(animation_name, blend)
	return true

func _play_asset_animation(role: String, blend: float = 0.06) -> bool:
	var played := false
	if _asset_animation_player != null and is_instance_valid(_asset_animation_player):
		var animation_name: String = WeaponAssetRegistry.animation_name_for_role(_weapon_id, role)
		if not animation_name.is_empty() and _asset_animation_player.has_animation(animation_name):
			_asset_animation_player.play(animation_name, blend)
			played = true
	if _hands_animation_player != null and is_instance_valid(_hands_animation_player):
		played = _play_aux_animation(_hands_animation_player, role, blend) or played
	return played

func _ensure_asset_idle() -> void:
	if _asset_animation_player == null or not is_instance_valid(_asset_animation_player):
		return
	if _asset_animation_player.is_playing():
		return
	_play_asset_animation("idle", 0.10)

func _update_asset_animation_state() -> void:
	var ads_now: bool = is_ads_active()
	if ads_now != _last_ads_state:
		_last_ads_state = ads_now
		if not _reloading:
			_play_asset_animation("ads_in" if ads_now else "ads_out", 0.05)
	elif not _reloading and _cooldown <= 0.0:
		_ensure_asset_idle()

func _finish_melee_overlay() -> void:
	if _melee_model_root != null and is_instance_valid(_melee_model_root):
		_melee_model_root.visible = false
	if _weapon_model_root != null and is_instance_valid(_weapon_model_root):
		_weapon_model_root.visible = true
	if _hands_model_root != null and is_instance_valid(_hands_model_root):
		_hands_model_root.visible = true
	set_meta("weapon_melee_overlay_active", false)

func play_melee_animation() -> void:
	var overlay_played := false
	if _melee_model_root != null and is_instance_valid(_melee_model_root):
		_melee_model_root.visible = true
		if _weapon_model_root != null and is_instance_valid(_weapon_model_root):
			_weapon_model_root.visible = false
		if _hands_model_root != null and is_instance_valid(_hands_model_root):
			_hands_model_root.visible = false
		overlay_played = _play_aux_animation(_melee_animation_player, "melee", 0.035)
		_melee_overlay_timer = 0.34
		if _melee_animation_player != null and is_instance_valid(_melee_animation_player):
			_melee_overlay_timer = clampf(_melee_animation_player.current_animation_length, 0.22, 0.72)
		set_meta("weapon_melee_overlay_active", true)
	if not overlay_played:
		_play_asset_animation("melee", 0.04)
	print("XZOGOT_FIRST_PERSON_MELEE_ANIM ", _weapon_id, " overlay=", overlay_played)

func play_interaction_animation(role: String = "machine_use") -> void:
	if _hands_animation_player != null and is_instance_valid(_hands_animation_player):
		if _play_aux_animation(_hands_animation_player, role, 0.06):
			print("XZOGOT_FIRST_PERSON_HANDS_INTERACTION ", _weapon_id, " role=", role)

func get_mapmod_asset_status() -> Dictionary:
	return WeaponAssetRegistry.inspect(_weapon_id)

func get_worldmodel_path() -> String:
	return WeaponAssetRegistry.preferred_worldmodel_path(_weapon_id)

func _load_optional_asset(path: String) -> Resource:
	if path.is_empty() or not ResourceLoader.exists(path):
		return null
	return load(path)

func _find_named_node3d(node: Node, aliases: Array[String]) -> Node3D:
	if node is Node3D:
		var lower_name: String = node.name.to_lower()
		for alias: String in aliases:
			if lower_name == alias.to_lower() or lower_name.contains(alias.to_lower()):
				return node as Node3D
	for child: Node in node.get_children():
		var found := _find_named_node3d(child, aliases)
		if found != null:
			return found
	return null

# Reuse the original Nacht/Project Aether animated tag_weapon hierarchy.
# FX/muzzle sockets remain separate from the hand-to-gun grip socket.
func _sync_source_weapon_attachment() -> void:
	if _source_hands_skeleton == null or _source_weapon_attachment == null or _source_weapon_bone_idx < 0:
		return
	if not is_instance_valid(_source_hands_skeleton) or not is_instance_valid(_source_weapon_attachment):
		return
	_source_weapon_attachment.transform = _source_hands_skeleton.get_bone_global_pose(_source_weapon_bone_idx)
	if _weapon_model_root == null or not is_instance_valid(_weapon_model_root):
		return
	if _weapon_model_root.get_parent() != _source_weapon_attachment:
		return
	# Existing PR #126 proved the imported hands keep centimeter-scale ancestry,
	# while the Aether weapon meshes themselves are already authored in meters.
	# Reparenting without inverse scale shrinks the visible MP40 about 100x.
	var inherited: Vector3 = _source_weapon_attachment.global_transform.basis.get_scale()
	if minf(inherited.x, minf(inherited.y, inherited.z)) <= 0.000001:
		set_meta("weapon_source_attachment_meter_units_restored", false)
		return
	_weapon_model_root.scale = Vector3(1.0 / inherited.x, 1.0 / inherited.y, 1.0 / inherited.z)
	var world_scale: Vector3 = _weapon_model_root.global_transform.basis.get_scale()
	var restored: bool = world_scale.distance_to(Vector3.ONE) <= 0.015
	set_meta("weapon_source_attachment_inherited_scale", inherited)
	set_meta("weapon_source_attachment_world_scale", world_scale)
	set_meta("weapon_source_attachment_meter_units_restored", restored)

func _on_source_hands_skeleton_updated() -> void:
	_sync_source_weapon_attachment()

func _find_skeleton_bone_attachment(node: Node, aliases: Array[String], attachment_name: String) -> Node3D:
	if node is Skeleton3D:
		var skeleton := node as Skeleton3D
		for bone_idx in range(skeleton.get_bone_count()):
			var bone_name: String = str(skeleton.get_bone_name(bone_idx))
			var lower_name: String = bone_name.to_lower()
			for alias: String in aliases:
				# Do not bind the rifle to tag_weapon_end, tag_weapon1, or a fake
				# convenience helper: original source PSA uses exact tag_weapon.
				var found: bool = lower_name == alias.to_lower() if attachment_name == "SourceTagWeapon" else (lower_name == alias.to_lower() or lower_name.contains(alias.to_lower()))
				if not found:
					continue
				if attachment_name == "SourceTagWeapon":
					var grip := Node3D.new()
					grip.name = attachment_name
					skeleton.add_child(grip)
					_source_hands_skeleton = skeleton
					_source_weapon_attachment = grip
					_source_weapon_bone_idx = bone_idx
					set_meta("weapon_source_attachment_bone_name", bone_name)
					if not skeleton.skeleton_updated.is_connected(_on_source_hands_skeleton_updated):
						skeleton.skeleton_updated.connect(_on_source_hands_skeleton_updated)
					_sync_source_weapon_attachment()
					return grip
				var fx_socket := BoneAttachment3D.new()
				fx_socket.name = attachment_name
				fx_socket.bone_name = skeleton.get_bone_name(bone_idx)
				skeleton.add_child(fx_socket)
				return fx_socket
	for child: Node in node.get_children():
		var found_socket := _find_skeleton_bone_attachment(child, aliases, attachment_name)
		if found_socket != null:
			return found_socket
	return null

func _fallback_barrel_anchor(model: Node3D) -> Node3D:
	var points: Array[Vector3] = []
	var stack: Array[Node] = [model]
	while not stack.is_empty():
		var node: Node = stack.pop_back()
		if node is MeshInstance3D:
			var mesh_node := node as MeshInstance3D
			var aabb: AABB = mesh_node.get_aabb()
			for x_idx in range(2):
				for y_idx in range(2):
					for z_idx in range(2):
						var corner := Vector3(
							aabb.position.x + aabb.size.x * float(x_idx),
							aabb.position.y + aabb.size.y * float(y_idx),
							aabb.position.z + aabb.size.z * float(z_idx)
						)
						points.append(_view_root.to_local(mesh_node.to_global(corner)))
		for child: Node in node.get_children():
			stack.append(child)

	var anchor := Node3D.new()
	anchor.name = "RuntimeMuzzleAnchor"
	model.add_child(anchor)
	if points.is_empty():
		anchor.position = model.to_local(_view_root.to_global(Vector3(0.0, 0.0, -0.50)))
		set_meta("weapon_muzzle_anchor_mode", "fallback_default")
		return anchor

	var min_z: float = INF
	var max_z: float = -INF
	for point: Vector3 in points:
		min_z = minf(min_z, point.z)
		max_z = maxf(max_z, point.z)
	var front_band: float = maxf(0.015, (max_z - min_z) * 0.10)
	var front_sum := Vector3.ZERO
	var front_count: int = 0
	for point: Vector3 in points:
		if point.z <= min_z + front_band:
			front_sum += point
			front_count += 1
	var muzzle_in_view: Vector3 = front_sum / float(maxi(front_count, 1))
	anchor.position = model.to_local(_view_root.to_global(muzzle_in_view))
	set_meta("weapon_muzzle_anchor_mode", "geometry_front")
	return anchor

func _make_flash_material() -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.albedo_color = Color(1.0, 0.46, 0.08, 0.92)
	mat.emission_enabled = true
	mat.emission = Color(1.0, 0.24, 0.025)
	mat.emission_energy_multiplier = 5.0
	mat.no_depth_test = true
	return mat

func _build_muzzle_flash(anchor: Node3D) -> void:
	_muzzle_flash_root = Node3D.new()
	_muzzle_flash_root.name = "MuzzleFlash"
	anchor.add_child(_muzzle_flash_root)

	var mat := _make_flash_material()
	for rot_deg in [0.0, 45.0]:
		var quad := QuadMesh.new()
		quad.size = Vector2(0.105, 0.105)
		quad.material = mat
		var mesh_instance := MeshInstance3D.new()
		mesh_instance.mesh = quad
		mesh_instance.rotation_degrees.z = rot_deg
		_muzzle_flash_root.add_child(mesh_instance)

	_muzzle_light = OmniLight3D.new()
	_muzzle_light.name = "MuzzleFlashLight"
	_muzzle_light.light_color = Color(1.0, 0.49, 0.17)
	_muzzle_light.light_energy = 0.0
	_muzzle_light.omni_range = 2.4
	_muzzle_light.shadow_enabled = false
	anchor.add_child(_muzzle_light)
	_muzzle_flash_root.visible = false

	var smoke_mat := StandardMaterial3D.new()
	smoke_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	smoke_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	smoke_mat.albedo_color = Color(0.34, 0.34, 0.34, 0.32)
	var smoke_quad := QuadMesh.new()
	smoke_quad.size = Vector2(0.042, 0.042)
	smoke_quad.material = smoke_mat
	var smoke_process := ParticleProcessMaterial.new()
	smoke_process.direction = Vector3(0.0, 0.08, -1.0)
	smoke_process.spread = 18.0
	smoke_process.initial_velocity_min = 0.12
	smoke_process.initial_velocity_max = 0.38
	smoke_process.gravity = Vector3(0.0, 0.22, 0.0)
	smoke_process.scale_min = 0.65
	smoke_process.scale_max = 1.45
	_smoke_particles = GPUParticles3D.new()
	_smoke_particles.name = "MuzzleSmoke"
	_smoke_particles.amount = 7
	_smoke_particles.lifetime = 0.42
	_smoke_particles.one_shot = true
	_smoke_particles.explosiveness = 0.95
	_smoke_particles.process_material = smoke_process
	_smoke_particles.draw_pass_1 = smoke_quad
	_smoke_particles.emitting = false
	anchor.add_child(_smoke_particles)

func _build_shell_eject(anchor: Node3D) -> void:
	var brass := StandardMaterial3D.new()
	brass.albedo_color = Color(0.54, 0.34, 0.10)
	brass.metallic = 0.78
	brass.roughness = 0.32
	var casing := CylinderMesh.new()
	casing.top_radius = 0.0032
	casing.bottom_radius = 0.0032
	casing.height = 0.014
	casing.material = brass
	var process := ParticleProcessMaterial.new()
	process.direction = Vector3(1.0, 0.58, 0.12)
	process.spread = 22.0
	process.initial_velocity_min = 0.65
	process.initial_velocity_max = 1.35
	process.gravity = Vector3(0.0, -3.8, 0.0)
	process.angular_velocity_min = 520.0
	process.angular_velocity_max = 1100.0
	process.scale_min = 0.90
	process.scale_max = 1.05
	_shell_particles = GPUParticles3D.new()
	_shell_particles.name = "ShellEject"
	_shell_particles.amount = 1
	_shell_particles.lifetime = 0.62
	_shell_particles.one_shot = true
	_shell_particles.explosiveness = 1.0
	_shell_particles.process_material = process
	_shell_particles.draw_pass_1 = casing
	_shell_particles.emitting = false
	anchor.add_child(_shell_particles)

func _bind_weapon_fx(model: Node3D) -> void:
	_weapon_model_root = model
	var muzzle_aliases: Array[String] = ["tag_flash", "muzzle_flash", "muzzle", "flash"]
	_muzzle_anchor = _find_named_node3d(model, muzzle_aliases)
	if _muzzle_anchor != null:
		set_meta("weapon_muzzle_anchor_mode", "node_socket")
	else:
		_muzzle_anchor = _find_skeleton_bone_attachment(model, muzzle_aliases, "MuzzleBoneAttachment")
		if _muzzle_anchor != null:
			set_meta("weapon_muzzle_anchor_mode", "bone_socket")
	if _muzzle_anchor == null:
		_muzzle_anchor = _fallback_barrel_anchor(model)

	var shell_aliases: Array[String] = ["tag_brass", "brass", "eject", "shell"]
	_shell_anchor = _find_named_node3d(model, shell_aliases)
	if _shell_anchor == null:
		_shell_anchor = _find_skeleton_bone_attachment(model, shell_aliases, "ShellBoneAttachment")
	if _shell_anchor == null:
		_shell_anchor = _muzzle_anchor

	_build_muzzle_flash(_muzzle_anchor)
	_build_shell_eject(_shell_anchor)
	set_meta("weapon_muzzle_fx_ready", true)
	print("XZOGOT_WEAPON_MUZZLE_FX_READY ", _weapon_id, " mode=", get_meta("weapon_muzzle_anchor_mode", "unknown"))

func _trigger_weapon_fx() -> void:
	if _muzzle_flash_root == null:
		return
	_muzzle_flash_timer = 0.050
	_muzzle_flash_root.visible = true
	var pulse: float = 0.86 + float(_shots_fired % 4) * 0.07
	_muzzle_flash_root.scale = Vector3.ONE * pulse
	_muzzle_flash_root.rotation_degrees.z = float((_shots_fired * 37) % 90)
	if _muzzle_light != null:
		_muzzle_light.light_energy = 3.6 if is_ads_active() else 4.4
	if _smoke_particles != null:
		_smoke_particles.restart()
		_smoke_particles.emitting = true
	if _shell_particles != null and _family != "wonder":
		_shell_particles.restart()
		_shell_particles.emitting = true
	set_meta("weapon_muzzle_flash_active", true)

func _update_weapon_fx(delta: float) -> void:
	if _muzzle_flash_timer <= 0.0:
		return
	_muzzle_flash_timer = maxf(0.0, _muzzle_flash_timer - delta)
	var alpha: float = clampf(_muzzle_flash_timer / 0.050, 0.0, 1.0)
	if _muzzle_light != null:
		_muzzle_light.light_energy = 4.4 * alpha
	if _muzzle_flash_timer <= 0.0:
		if _muzzle_flash_root != null:
			_muzzle_flash_root.visible = false
		if _muzzle_light != null:
			_muzzle_light.light_energy = 0.0
		set_meta("weapon_muzzle_flash_active", false)

func is_muzzle_fx_ready() -> bool:
	return _muzzle_flash_root != null and _muzzle_anchor != null

func get_muzzle_anchor_mode() -> String:
	return str(get_meta("weapon_muzzle_anchor_mode", "none"))

func get_muzzle_flash_timer() -> float:
	return _muzzle_flash_timer

func _bind_real_hands_source_grip() -> void:
	if _hands_model_root == null or _weapon_model_root == null:
		return
	var socket: Node3D = _find_skeleton_bone_attachment(_hands_model_root, ["tag_weapon"], "SourceTagWeapon")
	if socket == null:
		push_warning("XZOGOT_AUTHORED_HANDS_NO_TAG_WEAPON " + _weapon_id)
		return
	_weapon_model_root.reparent(socket, false)
	_weapon_model_root.transform = Transform3D.IDENTITY
	# Apply only the source-verified roll choices from the existing Nacht
	# 48/64-frame A/B audits on PR #126. Do not invent a new family offset.
	var source_pistols: Array[String] = ["colt", "walther", "nambu", "tt33", "357"]
	var source_upright_longs: Array[String] = ["stg", "browning", "type99", "bar", "dp28", "thompson", "trench", "ppsh"]
	var gun_roll_deg: float = 180.0 if _weapon_id in source_pistols or _weapon_id in source_upright_longs else 90.0
	_weapon_model_root.quaternion = Quaternion(Vector3.RIGHT, deg_to_rad(gun_roll_deg))
	_weapon_model_root.scale = Vector3.ONE
	_sync_source_weapon_attachment()
	if not bool(get_meta("weapon_source_attachment_meter_units_restored", false)):
		push_warning("XZOGOT_CHURCH_SOURCE_METER_SCALE_RED " + _weapon_id)
		return
	_real_hands_bound = true
	set_meta("weapon_source_gun_roll_correction_deg", gun_roll_deg)
	_source_hip = SourceHipPose.hip_position(_weapon_id) if SourceHipPose.has_source_hip_pose(_weapon_id) else Vector3.ZERO
	_source_ads_ready = SourcePresentation.has_source_presentation(_weapon_id)
	if _source_ads_ready:
		_source_hip = SourcePresentation.hip_position(_weapon_id)
		_source_ads = SourcePresentation.ads_position(_weapon_id)
		_source_ads_quat = SourcePresentation.ads_rotation(_weapon_id)
	set_meta("weapon_source_weapon_attachment_ready", true)
	set_meta("weapon_ads_calibration_mode", "source_datatable" if _source_ads_ready else "source_pending")
	set_meta("weapon_source_hand_transform_position", _source_hip)
	set_meta("weapon_source_ads_transform_position", _source_ads)
	print("XZOGOT_CHURCH_TAG_WEAPON_GRIP_READY ", _weapon_id, " source_ads=", _source_ads_ready)

func _refresh_view_assets(def: Dictionary) -> void:
	_clear_view_model()
	set_meta("weapon_view_fallback", false)

	var fallback_model_path: String = str(def.get("model_path", ""))
	var model_path: String = WeaponAssetRegistry.preferred_viewmodel_path(_weapon_id, fallback_model_path)
	var using_mapmod: bool = model_path != fallback_model_path
	var model_res: Resource = _load_optional_asset(model_path)
	if model_res is PackedScene and _view_root != null:
		var model: Node = (model_res as PackedScene).instantiate()
		model.name = "MapModWeaponModel" if using_mapmod else "AuthoredWeaponModel"
		_view_root.add_child(model)
		_asset_animation_player = _find_animation_player(model)
		if model is Node3D:
			_bind_weapon_fx(model as Node3D)
		else:
			push_warning("XZOGOT_WEAPON_MODEL_NOT_NODE3D " + _weapon_id)
		set_meta("weapon_asset_lane", "mapmod" if using_mapmod else "legacy_optional")
		print(
			"XZOGOT_WEAPON_MODEL_LOADED ",
			_weapon_id,
			" lane=",
			"mapmod" if using_mapmod else "legacy_optional"
		)
	else:
		# Never ship the old BoxMesh/CylinderMesh placeholder as a gun. The
		# procedural shape is retained only as an explicit developer opt-in.
		if allow_procedural_weapon_fallback:
			_build_fallback_view_model()
			set_meta("weapon_asset_lane", "procedural_fallback_dev_only")
			push_warning("XZOGOT_WEAPON_DEV_FALLBACK " + _weapon_id + " " + model_path)
		else:
			set_meta("weapon_asset_lane", "missing_real_asset")
			push_warning("XZOGOT_REAL_WEAPON_ASSET_REQUIRED " + _weapon_id + " " + model_path)

	var hands_path := WeaponAssetRegistry.preferred_hands_path(_weapon_id)
	var hands_res: Resource = _load_optional_asset(hands_path)
	if hands_res is PackedScene and _view_root != null:
		var hands_node: Node = (hands_res as PackedScene).instantiate()
		hands_node.name = "FirstPersonHands"
		_view_root.add_child(hands_node)
		if hands_node is Node3D:
			_hands_model_root = hands_node as Node3D
		_hands_animation_player = _find_animation_player(hands_node)
		set_meta("weapon_hands_asset", hands_path)
		set_meta("weapon_hands_animation_ready", _hands_animation_player != null)
		print("XZOGOT_FIRST_PERSON_HANDS_LOADED ", _weapon_id, " ", hands_path)
		_bind_real_hands_source_grip()

	var melee_path := WeaponAssetRegistry.preferred_melee_viewmodel_path(_weapon_id)
	var melee_res: Resource = _load_optional_asset(melee_path)
	if melee_res is PackedScene and _view_root != null:
		var melee_node: Node = (melee_res as PackedScene).instantiate()
		melee_node.name = "FirstPersonMeleeOverlay"
		_view_root.add_child(melee_node)
		if melee_node is Node3D:
			_melee_model_root = melee_node as Node3D
			_melee_model_root.visible = false
		_melee_animation_player = _find_animation_player(melee_node)
		set_meta("weapon_melee_viewmodel_asset", melee_path)
		set_meta("weapon_melee_animation_ready", _melee_animation_player != null)
		print("XZOGOT_FIRST_PERSON_MELEE_VIEWMODEL_LOADED ", _weapon_id, " ", melee_path)

	if _fire_audio != null:
		var fire_path: String = WeaponAssetRegistry.preferred_audio_path(
			_weapon_id,
			"fire",
			str(def.get("fire_audio", ""))
		)
		var fire_res: Resource = _load_optional_asset(fire_path)
		_fire_audio.stream = fire_res as AudioStream
		if _fire_audio.stream == null:
			print("XZOGOT_WEAPON_FIRE_AUDIO_PENDING ", _weapon_id)

	if _reload_audio != null:
		var reload_path: String = WeaponAssetRegistry.preferred_audio_path(
			_weapon_id,
			"reload",
			str(def.get("reload_audio", ""))
		)
		var reload_res: Resource = _load_optional_asset(reload_path)
		_reload_audio.stream = reload_res as AudioStream

	if _mechanical_audio != null:
		var mechanical_path := WeaponAssetRegistry.preferred_audio_path(_weapon_id, "mechanical")
		_mechanical_audio.stream = _load_optional_asset(mechanical_path) as AudioStream

	if _dry_fire_audio != null:
		var dry_path := WeaponAssetRegistry.preferred_audio_path(_weapon_id, "dry_fire")
		_dry_fire_audio.stream = _load_optional_asset(dry_path) as AudioStream

func _player_modifier(method_name: String, default_value: float = 1.0) -> float:
	if _body != null and _body.has_method(method_name):
		return float(_body.call(method_name))
	return default_value

func _apply_upgrade_stats() -> void:
	if not _upgraded:
		return
	damage *= 1.85
	fire_interval *= 0.92
	magazine_size = maxi(magazine_size + 1, int(ceil(float(magazine_size) * 1.35)))
	reload_time *= 0.90
	_display_name = "SANCTIFIED " + _display_name

func can_upgrade_current_weapon() -> bool:
	return not _weapon_id.is_empty() and WeaponCatalog.has_weapon(_weapon_id) and not _upgraded

func upgrade_current_weapon() -> bool:
	if not can_upgrade_current_weapon():
		return false
	_upgraded_ids[_weapon_id] = true
	var id := _weapon_id
	if not equip_weapon(id, true):
		_upgraded_ids.erase(id)
		return false
	set_meta("weapon_upgraded", true)
	print("XZOGOT_WEAPON_SANCTIFIED ", id)
	return true

func is_upgraded() -> bool:
	return _upgraded

func get_runtime_stats() -> Dictionary:
	return {
		"id": _weapon_id,
		"display_name": _display_name,
		"damage": damage,
		"fire_interval": fire_interval,
		"magazine_size": magazine_size,
		"reload_time": reload_time,
		"hip_spread_deg": _hip_spread_deg,
		"ads_spread_deg": _ads_spread_deg,
		"visual_recoil_deg": _visual_recoil_deg,
		"upgraded": _upgraded,
	}

func equip_weapon(id: String, refill: bool = true) -> bool:
	if not WeaponCatalog.has_weapon(id):
		return false

	var def: Dictionary = WeaponCatalog.get_weapon(id)
	_weapon_id = id
	_display_name = str(def.get("display_name", id))
	_family = str(def.get("family", "rifle"))
	damage = float(def.get("damage", 30.0))
	range_m = float(def.get("range_m", 120.0))
	fire_interval = float(def.get("fire_interval", 0.10))
	magazine_size = int(def.get("magazine", 30))
	reload_time = float(def.get("reload_time", 1.55))
	_automatic = bool(def.get("automatic", false))
	_pellets = maxi(1, int(def.get("pellets", 1)))
	_ads_fov = float(def.get("ads_fov", 48.0))
	_hip_spread_deg = float(def.get("hip_spread_deg", 1.5))
	_ads_spread_deg = float(def.get("ads_spread_deg", 0.25))
	_visual_recoil_deg = float(def.get("visual_recoil_deg", 1.2))
	_upgraded = bool(_upgraded_ids.get(id, false))
	_apply_upgrade_stats()

	if refill:
		_magazine = magazine_size
		reserve_ammo = int(def.get("reserve", magazine_size * 4))
	else:
		_magazine = mini(_magazine, magazine_size)

	_reloading = false
	_reload_timer = 0.0
	_cooldown = 0.0
	_trigger_held = false
	_refresh_view_assets(def)
	_ads_pose_alpha = 0.0
	_view_pose_position = _source_hip if _real_hands_bound else Vector3(0.22, -0.20, -0.48)
	if _view_root != null:
		_view_root.position = _view_pose_position
		_view_root.quaternion = Quaternion.IDENTITY
	_last_ads_state = is_ads_active()
	_play_asset_animation("equip", 0.0)

	set_meta("weapon_id", _weapon_id)
	set_meta("weapon_family", _family)
	set_meta("weapon_upgraded", _upgraded)
	print(
		"XZOGOT_WEAPON_EQUIPPED ",
		_weapon_id,
		" mag=", magazine_size,
		" reserve=", reserve_ammo,
		" ads=", _ads_fov
	)
	return true

func apply_authoritative_network_loadout(
	id: String,
	magazine: int,
	reserve: int,
	upgraded: bool
) -> bool:
	if not WeaponCatalog.has_weapon(id):
		return false
	if upgraded:
		_upgraded_ids[id] = true
	else:
		_upgraded_ids.erase(id)
	if not equip_weapon(id, true):
		return false
	_magazine = clampi(magazine, 0, magazine_size)
	reserve_ammo = maxi(0, reserve)
	_reloading = false
	_reload_timer = 0.0
	set_meta("weapon_upgraded", _upgraded)
	print(
		"XZOGOT_NETWORK_LOADOUT_SYNC ", id,
		" mag=", _magazine,
		" reserve=", reserve_ammo,
		" upgraded=", _upgraded
	)
	return true

func buy_wall_weapon(id: String, player: Node) -> bool:
	if not WeaponCatalog.has_weapon(id):
		return false
	var def: Dictionary = WeaponCatalog.get_weapon(id)
	var same_weapon: bool = id == _weapon_id
	var cost: int = WeaponCatalog.ammo_cost(id) if same_weapon else int(def.get("wall_cost", -1))
	if cost < 0:
		return false
	if player == null or not player.has_method("spend_points"):
		return false
	if not bool(player.call("spend_points", cost)):
		return false

	if same_weapon:
		reserve_ammo += int(def.get("reserve", magazine_size * 4))
		print("XZOGOT_WALLBUY_AMMO ", id, " cost=", cost)
	else:
		equip_weapon(id, true)
		print("XZOGOT_WALLBUY_WEAPON ", id, " cost=", cost)
	return true

func roll_mystery_weapon() -> String:
	_mystery_serial += 1
	var result: String = WeaponCatalog.roll_mystery(_mystery_serial, _weapon_id)
	equip_weapon(result, true)
	print("XZOGOT_MYSTERY_RESULT ", result, " spin=", _mystery_serial)
	return result

func set_trigger_held(held: bool) -> void:
	var pressed_now: bool = held and not _trigger_held
	_trigger_held = held
	if pressed_now:
		request_fire()

func request_fire() -> void:
	if _reloading or _cooldown > 0.0:
		return
	if _magazine <= 0:
		if reserve_ammo > 0:
			request_reload()
		else:
			if _dry_fire_audio != null and _dry_fire_audio.stream != null:
				_dry_fire_audio.play()
			print("XZOGOT_WEAPON_DRY_FIRE ", _weapon_id)
		return

	if not _dev_infinite_ammo:
		_magazine -= 1
	_cooldown = fire_interval * _player_modifier("get_fire_interval_multiplier")
	_shots_fired += 1
	_apply_recoil_impulse()
	_trigger_weapon_fx()
	var ads: bool = is_ads_active()
	var is_last_round: bool = not _dev_infinite_ammo and _magazine == 0
	var fire_role: String = "lastshot" if is_last_round else ("fire_ads" if ads else "fire")
	if not _play_asset_animation(fire_role, 0.025):
		if ads and fire_role != "fire_ads" and _play_asset_animation("fire_ads", 0.025):
			pass
		elif fire_role != "fire":
			_play_asset_animation("fire", 0.025)
	if _fire_audio != null and _fire_audio.stream != null:
		_fire_audio.play()
	if _mechanical_audio != null and _mechanical_audio.stream != null:
		_mechanical_audio.play()

	var spread: float = (_ads_spread_deg if ads else _hip_spread_deg) * _player_modifier("get_spread_multiplier")
	for pellet in range(_pellets):
		_fire_hitscan(spread, pellet)
	print("XZOGOT_WEAPON_FIRED ", _weapon_id, " ads=", ads, " pellets=", _pellets)

func request_reload() -> void:
	if _dev_infinite_ammo:
		_magazine = magazine_size
		_reloading = false
		return
	if _reloading or _magazine >= magazine_size or reserve_ammo <= 0:
		return
	_reloading = true
	_trigger_held = false
	_reload_timer = reload_time * _player_modifier("get_reload_multiplier")
	var reload_role: String = "reload_empty" if _magazine <= 0 else "reload"
	if not _play_asset_animation(reload_role, 0.06) and reload_role != "reload":
		_play_asset_animation("reload", 0.06)
	if _reload_audio != null and _reload_audio.stream != null:
		_reload_audio.play()

func _finish_reload() -> void:
	if _dev_infinite_ammo:
		_magazine = magazine_size
		_reloading = false
		_reload_timer = 0.0
		return
	var needed: int = magazine_size - _magazine
	var loaded: int = mini(needed, reserve_ammo)
	_magazine += loaded
	reserve_ammo -= loaded
	_reloading = false
	_reload_timer = 0.0

func is_ads_active() -> bool:
	if _body != null and _body.has_method("is_ads_active"):
		return bool(_body.call("is_ads_active"))
	return false

func _spread_direction(base: Vector3, spread_deg: float, pellet: int) -> Vector3:
	if spread_deg <= 0.001 or _camera == null:
		return base

	# Deterministic shot cone: multiplayer/server authority can reproduce this from
	# weapon id + shot serial + pellet index without relying on wall-clock RNG.
	var seed_text: String = "%s:%d:%d" % [_weapon_id, _shots_fired, pellet]
	var seed: int = abs(seed_text.hash())
	var rng := RandomNumberGenerator.new()
	rng.seed = seed
	var radius: float = sqrt(rng.randf()) * tan(deg_to_rad(spread_deg))
	var angle: float = rng.randf_range(0.0, TAU)
	var right: Vector3 = _camera.global_transform.basis.x.normalized()
	var up: Vector3 = _camera.global_transform.basis.y.normalized()
	return (base + right * cos(angle) * radius + up * sin(angle) * radius).normalized()

func _fire_hitscan(spread_deg: float, pellet: int) -> void:
	if _camera == null or _body == null:
		return

	var origin: Vector3 = _camera.global_position
	var base_direction: Vector3 = -_camera.global_transform.basis.z.normalized()
	var direction: Vector3 = _spread_direction(base_direction, spread_deg, pellet)
	var target: Vector3 = origin + direction * range_m
	var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(origin, target)
	query.exclude = [_body.get_rid()]
	query.collide_with_areas = true
	query.collide_with_bodies = true
	var hit: Dictionary = _camera.get_world_3d().direct_space_state.intersect_ray(query)
	if hit.is_empty():
		return

	var collider: Object = hit.get("collider") as Object
	if collider == null:
		return
	var hit_position: Vector3 = hit.get("position", target) as Vector3
	if collider.has_method("apply_hitscan_damage"):
		var final_damage: float = damage * _player_modifier("get_weapon_damage_multiplier")
		collider.call("apply_hitscan_damage", final_damage, _body, hit_position)
	elif collider.has_method("apply_damage"):
		var final_damage: float = damage * _player_modifier("get_weapon_damage_multiplier")
		collider.call("apply_damage", final_damage, _body)

func _apply_recoil_impulse() -> void:
	_visual_recoil_velocity += (
		_visual_recoil_deg
		* (0.88 if is_ads_active() else 1.0)
		* _player_modifier("get_recoil_multiplier")
	)

func _update_visual_recoil(delta: float) -> void:
	# Presentation only. Ballistic ray direction/spread was already computed above.
	var spring: float = 54.0
	var damping: float = 13.5
	_visual_recoil_velocity += (-spring * _visual_recoil_pitch - damping * _visual_recoil_velocity) * delta
	_visual_recoil_pitch += _visual_recoil_velocity * delta
	_visual_recoil_pitch = clampf(_visual_recoil_pitch, -0.5, 7.5)

	if _camera != null:
		_camera.rotation.x = deg_to_rad(-_visual_recoil_pitch)
	if _view_root != null:
		# ADS must physically bring the first-person weapon onto the sight line,
		# not only narrow the camera FOV.  Asset-specific animations still play
		# on top of this camera-space pose.
		var ads_target: float = 1.0 if is_ads_active() else 0.0
		var transition: float = SourcePresentation.ads_in_time(_weapon_id) if ads_target > _ads_pose_alpha else SourcePresentation.ads_out_time(_weapon_id)
		var ads_speed: float = (1.0 / maxf(transition, 0.001)) if _source_ads_ready else (12.0 if ads_target > _ads_pose_alpha else 15.0)
		_ads_pose_alpha = move_toward(_ads_pose_alpha, ads_target, ads_speed * delta)
		var hip_position: Vector3 = _source_hip if _real_hands_bound else Vector3(0.22, -0.20, -0.48)
		var ads_position: Vector3 = _source_ads if _source_ads_ready else Vector3(0.0, -0.145, -0.365)
		var target_position: Vector3 = hip_position.lerp(ads_position, _ads_pose_alpha)
		var pose_blend: float = 1.0 - exp(-22.0 * delta)
		_view_pose_position = _view_pose_position.lerp(target_position, pose_blend)
		var recoil_push: float = minf(_visual_recoil_pitch * 0.0025, 0.022)
		_view_root.position = _view_pose_position + Vector3(0.0, 0.0, recoil_push)
		_view_root.quaternion = Quaternion.IDENTITY.slerp(_source_ads_quat, _ads_pose_alpha) if _source_ads_ready else Quaternion.IDENTITY
		set_meta("weapon_ads_pose_alpha", _ads_pose_alpha)

func set_dev_infinite_ammo(enabled: bool) -> void:
	_dev_infinite_ammo = enabled
	if enabled:
		_magazine = magazine_size
		_reloading = false
	set_meta("dev_infinite_ammo", enabled)
	print("XZOGOT_DEV_INFINITE_AMMO ", enabled)

func is_dev_infinite_ammo() -> bool:
	return _dev_infinite_ammo

func add_reserve_ammo(amount: int) -> void:
	if amount <= 0:
		return
	reserve_ammo += amount

func refill_max_ammo() -> void:
	if not WeaponCatalog.has_weapon(_weapon_id):
		return
	var def: Dictionary = WeaponCatalog.get_weapon(_weapon_id)
	_magazine = magazine_size
	reserve_ammo = int(def.get("reserve", magazine_size * 4))
	_reloading = false
	_reload_timer = 0.0
	print("XZOGOT_WEAPON_MAX_AMMO ", _weapon_id, " mag=", _magazine, " reserve=", reserve_ammo)

func get_magazine() -> int:
	return _magazine

func get_reserve() -> int:
	return 9999 if _dev_infinite_ammo else reserve_ammo

func is_reloading() -> bool:
	return _reloading

func get_shots_fired() -> int:
	return _shots_fired

func get_weapon_id() -> String:
	return _weapon_id

func get_display_name() -> String:
	return _display_name

func get_family() -> String:
	return _family

func get_ads_fov() -> float:
	return _ads_fov

func is_automatic() -> bool:
	return _automatic

func get_mystery_pool_size() -> int:
	return WeaponCatalog.MYSTERY_POOL.size()
