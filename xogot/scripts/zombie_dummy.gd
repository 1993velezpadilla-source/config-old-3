extends CharacterBody3D

signal died(zombie: Node)

const MONJA_BASICA_PATH := "res://assets/zombies/monja_basica.glb"
const MONJA_CMU_PATH := "res://assets/zombies/monja_clean/cmu_runtime/monja_basica_cmu_rig.gltf"
const MONJA_CLEAN_PATH := "res://assets/zombies/monja_clean/clean_runtime/monja_basica_clean_rig.gltf"
const MONJA_RIGGED_PATH := "res://assets/zombies/monja_basica_rigged.glb"
const MONJA_RIGGED_DISMEMBER_PATH := "res://assets/zombies/monja_basica_rigged_dismember.glb"
const MONJA_RIGID_RIG_PATH := "res://assets/zombies/monja_rigid/monja_basica_rigid_rig.gltf"
const MONJA_ELITE_CMU_PATH := "res://assets/zombies/monja_elite/cmu_runtime/monja_black_white_cmu_rig.gltf"
const MONJA_ELITE_PATH := "res://assets/zombies/monja_elite/clean_runtime/monja_black_white_clean_rig.gltf"
const SHEEP_RUNNER_PATH := "res://assets/zombies/sheep/sheep_runner_animated.glb"
const SHEEP_BRUTE_PATH := "res://assets/zombies/sheep/sheep_brute_animated.glb"
const WAW_HONORGD_PATH := "res://assets/zombies/source_waw/honorgd/zombie.glb"
const WAW_SUMPF_PATH := "res://assets/zombies/source_waw/sumpf/zombie.glb"

const RIGGED_FALLBACK_ANIMS := {
	"idle": ["Zombie_Idle_Loop", "Zombie_Idle_Clean", "Idle_Clean"],
	"walk": ["Zombie_Walk_Fwd_Loop", "Zombie_Walk_Clean", "Walk_Clean"],
	"attack": ["Zombie_Scratch", "Zombie_Attack_Clean", "Attack_Clean"],
	"hit": ["Zombie_Hit_Clean", "Hit_Clean", "Hit_Knockback"],
	"death": ["Zombie_Death_Clean", "Death_Clean", "LayToIdle", "fall_on_face"],
}

const SHEEP_FALLBACK_ANIMS := {
	"idle": ["Sheep_Idle", "Idle"],
	"walk": ["Sheep_Run", "Sheep_Walk", "Run", "Walk"],
	"attack": ["Sheep_Attack", "Attack", "Bite"],
	"death": ["Sheep_Death", "Death"],
}

const MOTION_PROFILES: Array[Dictionary] = [
	{
		"id": "cmu_zombie_walk_104_41",
		"walk_keys": ["zombie_walk", "104_41"],
		"speed_scale": 1.00,
		"source": "res://assets/zombie_mocap/raw/walk/zombie_walk__104_41.fbx",
	},
	{
		"id": "cmu_drag_bad_leg_105_25",
		"walk_keys": ["drag_bad_leg", "105_25"],
		"speed_scale": 0.86,
		"source": "res://assets/zombie_mocap/raw/walk/drag_bad_leg__105_25.fbx",
	},
	{
		"id": "cmu_stiff_74_01",
		"walk_keys": ["stiff", "74_01"],
		"speed_scale": 0.93,
		"source": "res://assets/zombie_mocap/raw/walk/stiff_A__74_01.fbx",
	},
	{
		"id": "cmu_wounded_leg_139_19",
		"walk_keys": ["wounded_leg", "139_19"],
		"speed_scale": 0.82,
		"source": "res://assets/zombie_mocap/raw/walk/wounded_leg_139_A__139_19.fbx",
	},
]

const ATTACK_KEYS: Array[String] = ["strike_A", "02_05", "punch_kick", "111_19"]
const HIT_KEYS: Array[String] = ["Zombie_Hit_Clean", "Hit_Knockback"]
const DEATH_KEYS: Array[String] = ["fall_on_face", "90_16", "Zombie_Death_Clean", "LayToIdle"]
const GETUP_KEYS: Array[String] = ["face_down_A", "140_01"]
const CRAWL_KEYS: Array[String] = ["crawl_A", "111_03"]

const WAW_SOURCE_STATE_KEYS := {
	"idle": ["ai_zombie_idle_v1_delta"],
	"walk": ["ai_zombie_walk_v1"],
	"walk_fast": ["ai_zombie_walk_fast_v1"],
	"run": ["ai_zombie_run_v1"],
	"sprint": ["ai_zombie_sprint_v1"],
	"attack": ["ai_zombie_attack_forward_v1", "ai_zombie_attack_v1"],
	"death": ["ai_zombie_death_v1", "ai_zombie_death_v2"],
	"traverse": ["ai_zombie_traverse_ground_v1_run", "ai_zombie_traverse_v1"],
}

@export var enemy_variant: String = "normal"
@export var move_speed: float = 1.85
@export var health: float = 100.0
@export var barricade_damage: float = 25.0
@export var barricade_attack_max_distance: float = 0.82
@export var player_damage: float = 20.0
@export var attack_interval: float = 0.90
@export var player_attack_impact_delay: float = 0.30
@export var death_linger_time: float = 1.25
@export var window_cross_speed: float = 2.65
@export var turn_lerp: float = 0.22
@export var target_visual_height: float = 1.80
@export var target_visual_max_width: float = 0.90
@export var target_visual_max_depth: float = 0.72
@export var collider_radius: float = 0.34
@export var collider_height: float = 1.78
@export var headshot_multiplier: float = 2.0
@export var headshot_height_ratio: float = 0.84
@export var headshot_bonus_points: int = 10
@export var hit_reaction_duration: float = 0.14
@export var path_refresh_interval: float = 0.62
@export var direct_path_vertical_limit: float = 1.05
@export var waypoint_vertical_tolerance: float = 0.95
@export var stuck_sample_interval: float = 0.72
@export var stuck_timeout: float = 1.75
@export var max_step_height: float = 0.42
@export var step_forward_distance: float = 0.24
@export var dismemberment_enabled: bool = true
@export var head_limb_health: float = 82.0
@export var arm_limb_health: float = 112.0
@export var leg_limb_health: float = 126.0
@export var crawler_speed: float = 0.95

enum Phase {
	APPROACH,
	ATTACK_BARRICADE,
	CHASE_PLAYER,
	DEAD,
	CROSS_WINDOW
}

var target_player: Node3D
var target_barricade: Node
var phase: Phase = Phase.APPROACH
var _attack_timer: float = 0.0
var _player_attack_pending: bool = false
var _player_attack_impact_timer: float = 0.0
var _gravity: float = 18.0
var _hit_reaction_timer: float = 0.0
var _visual_root: Node3D

var _path_network: Node
var _path_points: Array[Vector3] = []
var _path_index: int = 0
var _path_refresh_timer: float = 0.0
var _last_path_target: Vector3 = Vector3.INF

var _stuck_sample_timer: float = 0.0
var _stuck_accum: float = 0.0
var _last_motion_sample: Vector3 = Vector3.ZERO
var _unstuck_count: int = 0

var _motion_profile: Dictionary = {}
var _motion_profile_id: String = ""
var _animation_player: AnimationPlayer
var _motion_state: String = ""

var _limb_health: Dictionary = {}
var _severed: Dictionary = {
	"head": false,
	"left_arm": false,
	"right_arm": false,
	"left_leg": false,
	"right_leg": false,
}
var _crawler: bool = false
var _headless: bool = false
var _headless_survivor: bool = false
var _network_proxy_mode: bool = false
var _network_proxy_snapshot_ready: bool = false
var _network_proxy_target_position := Vector3.ZERO
var _network_proxy_target_yaw: float = 0.0

const ZOMBIE_MOANS: Array[String] = [
	"res://assets/audio/church/zombie/moan_01.ogg",
	"res://assets/audio/church/zombie/moan_02.ogg",
	"res://assets/audio/church/zombie/moan_03.ogg",
]
const ZOMBIE_ATTACKS: Array[String] = [
	"res://assets/audio/church/zombie/attack_01.ogg",
	"res://assets/audio/church/zombie/attack_02.ogg",
]
const ZOMBIE_DEATHS: Array[String] = [
	"res://assets/audio/church/zombie/death_01.ogg",
	"res://assets/audio/church/zombie/death_02.ogg",
]
var _moan_timer: float = 0.0
var _voice_serial: int = 0

func _zombie_audio_choice(paths: Array[String]) -> String:
	if paths.is_empty():
		return ""
	var index: int = abs((name + ":" + str(_voice_serial)).hash()) % paths.size()
	_voice_serial += 1
	return paths[index]

func _play_zombie_sfx(path: String, volume_db: float = -7.0, detached: bool = false) -> void:
	if path.is_empty() or not ResourceLoader.exists(path):
		return
	var stream := load(path) as AudioStream
	if stream == null:
		return
	var player := AudioStreamPlayer3D.new()
	player.name = "ZombieVoice"
	player.stream = stream
	player.volume_db = volume_db
	player.unit_size = 1.7
	player.max_distance = 26.0
	if detached and get_parent() != null:
		get_parent().add_child(player)
		player.global_position = global_position + Vector3(0.0, 1.15, 0.0)
	else:
		add_child(player)
		player.position = Vector3(0.0, 1.15, 0.0)
	player.finished.connect(player.queue_free)
	player.play()

func _update_voice(delta: float) -> void:
	_moan_timer -= delta
	if _moan_timer > 0.0:
		return
	var near_player: bool = (
		target_player != null
		and is_instance_valid(target_player)
		and global_position.distance_squared_to(target_player.global_position) <= 22.0 * 22.0
	)
	var last_zombie: bool = bool(get_meta("last_zombie", false))
	if near_player:
		_play_zombie_sfx(
			_zombie_audio_choice(ZOMBIE_MOANS),
			-6.0 if last_zombie else -9.0
		)
	var jitter: float = float(abs((name + ":moan:" + str(_voice_serial)).hash()) % 550) / 100.0
	_moan_timer = (2.0 + jitter * 0.42) if last_zombie else (4.2 + jitter)

func _ready() -> void:
	enemy_variant = str(get_meta("enemy_variant", enemy_variant))
	set_meta("enemy_variant", enemy_variant)
	_gravity = float(ProjectSettings.get_setting("physics/3d/default_gravity", 18.0))
	motion_mode = CharacterBody3D.MOTION_MODE_GROUNDED
	floor_snap_length = 0.38
	floor_max_angle = deg_to_rad(52.0)
	safe_margin = 0.035
	add_to_group("zombie")
	_path_network = get_tree().get_first_node_in_group("zombie_path_network")
	_select_motion_profile()
	_limb_health = {
		"head": head_limb_health,
		"left_arm": arm_limb_health,
		"right_arm": arm_limb_health,
		"left_leg": leg_limb_health,
		"right_leg": leg_limb_health,
	}
	_build_body()
	_last_motion_sample = global_position
	_moan_timer = 1.7 + float(abs(name.hash()) % 330) / 100.0
	print("XZOGOT_ZOMBIE_GROUND_SNAP_READY 0.38")
	print("XZOGOT_ZOMBIE_MULTILEVEL_PATH_GUARD_READY")
	print("XZOGOT_ZOMBIE_PATHING_READY ", _motion_profile_id)
	print("XZOGOT_ZOMBIE_READY")

func set_network_proxy_mode(enabled: bool) -> void:
	_network_proxy_mode = enabled
	set_meta("network_proxy", enabled)
	if enabled:
		target_player = get_parent().get_node_or_null("Player") as Node3D if get_parent() != null else null
		target_barricade = null
		velocity = Vector3.ZERO
		print("XZOGOT_ZOMBIE_NETWORK_PROXY_READY ", name)

func apply_network_proxy_state(
	pos: Vector3,
	yaw: float,
	server_health: float,
	server_phase: int,
	server_crawler: bool,
	server_headless: bool
) -> void:
	if not _network_proxy_mode:
		set_network_proxy_mode(true)
	if not _network_proxy_snapshot_ready:
		global_position = pos
		rotation.y = yaw
		_network_proxy_snapshot_ready = true
	_network_proxy_target_position = pos
	_network_proxy_target_yaw = yaw
	health = maxf(0.0, server_health)
	phase = clampi(server_phase, int(Phase.APPROACH), int(Phase.CROSS_WINDOW))
	if server_crawler and not _crawler:
		_make_crawler()
	_headless = server_headless
	set_meta("crawler", _crawler)
	set_meta("headless", _headless)

func _submit_network_proxy_hit(hit_position: Vector3, melee: bool) -> bool:
	if not _network_proxy_mode:
		return false
	var network: Node = get_parent().get_node_or_null("NetworkManager") if get_parent() != null else null
	if network == null or not network.has_method("submit_zombie_hit"):
		return true
	network.call("submit_zombie_hit", name, hit_position, melee)
	_hit_reaction_timer = hit_reaction_duration
	return true

func set_last_zombie_mode(enabled: bool) -> void:
	set_meta("last_zombie", enabled)
	if enabled:
		_moan_timer = minf(_moan_timer, 0.25)
		print("XZOGOT_LAST_ZOMBIE_VOICE_READY ", name)

func configure(player: Node3D, barricade: Node) -> void:
	target_player = player
	target_barricade = barricade
	phase = Phase.APPROACH
	set_meta("spawn_entry_kind", "window")

func configure_direct(player: Node3D, anchor: Node) -> void:
	target_player = player
	target_barricade = null
	phase = Phase.CHASE_PLAYER
	var entry_kind: String = str(anchor.get_meta("entry_kind", "offscreen")) if anchor != null else "offscreen"
	var zone: String = str(anchor.get_meta("zone", "")) if anchor != null else ""
	set_meta("spawn_entry_kind", entry_kind)
	set_meta("spawn_zone", zone)
	if entry_kind == "crawl":
		set_meta("motion_override", "crawl")
	print("XZOGOT_ZOMBIE_DIRECT_ENTRY ", entry_kind, " ", zone)

func _select_motion_profile() -> void:
	if enemy_variant.begins_with("sheep_"):
		_motion_profile = {
			"id": enemy_variant + "_quadruped",
			"walk_keys": SHEEP_FALLBACK_ANIMS["walk"],
			"speed_scale": 1.0,
			"source": "authored_blender_quadruped",
		}
		_motion_profile_id = str(_motion_profile["id"])
		set_meta("motion_profile", _motion_profile_id)
		set_meta("motion_source", str(_motion_profile["source"]))
		return
	if enemy_variant == "nun_elite":
		# Elite uses a distinct captured limp gait but keeps the stronger variant's
		# gameplay speed; do not apply the normal wounded-zombie slowdown again.
		_motion_profile = {
			"id": "elite_cmu_wounded_139_19",
			"walk_keys": ["wounded_leg", "139_19"],
			"speed_scale": 1.0,
			"source": "res://assets/zombie_mocap/raw/walk/wounded_leg_139_A__139_19.fbx",
		}
		_motion_profile_id = str(_motion_profile["id"])
		set_meta("motion_profile", _motion_profile_id)
		set_meta("motion_source", str(_motion_profile["source"]))
		return
	var idx: int = abs(name.hash()) % MOTION_PROFILES.size()
	_motion_profile = MOTION_PROFILES[idx]
	_motion_profile_id = str(_motion_profile["id"])
	move_speed *= float(_motion_profile.get("speed_scale", 1.0))
	set_meta("motion_profile", _motion_profile_id)
	set_meta("motion_source", str(_motion_profile.get("source", "")))

func _build_body() -> void:
	var cs := CollisionShape3D.new()
	cs.name = "ZombieCollider"
	var capsule := CapsuleShape3D.new()
	capsule.radius = collider_radius
	capsule.height = collider_height
	cs.shape = capsule
	cs.position.y = collider_height * 0.5
	add_child(cs)

	var selected_path: String = MONJA_BASICA_PATH
	var using_rigged: bool = false
	var using_rigged_dismember: bool = false
	var using_rigid_rig: bool = false
	var using_source_waw: bool = false
	var special_model_id: String = ""
	if enemy_variant == "sheep_runner":
		selected_path = SHEEP_RUNNER_PATH
		special_model_id = "sheep_runner"
	elif enemy_variant == "sheep_brute":
		selected_path = SHEEP_BRUTE_PATH
		special_model_id = "sheep_brute"
	elif enemy_variant == "nun_elite":
		selected_path = MONJA_ELITE_CMU_PATH if ResourceLoader.exists(MONJA_ELITE_CMU_PATH) else MONJA_ELITE_PATH
		using_rigged = true
		special_model_id = "monja_elite_cmu" if selected_path == MONJA_ELITE_CMU_PATH else "monja_elite"
	else:
		# Source-first golden baseline: normal gameplay uses the recovered WaW
		# zombie body + WaW animation contract before any Monja reskin.  Keep
		# geometry at authored meter scale; custom art may replace this visual
		# only after the source runtime is visually/gameplay GREEN.
		var source_variant: String = str(get_meta("source_waw_variant", "honorgd"))
		if source_variant == "sumpf" and ResourceLoader.exists(WAW_SUMPF_PATH):
			selected_path = WAW_SUMPF_PATH
			using_rigged = true
			using_source_waw = true
			special_model_id = "waw_sumpf"
		elif ResourceLoader.exists(WAW_HONORGD_PATH):
			selected_path = WAW_HONORGD_PATH
			using_rigged = true
			using_source_waw = true
			special_model_id = "waw_honorgd"
		elif ResourceLoader.exists(MONJA_CLEAN_PATH):
			# Fail-soft development fallback only; source gate rejects this when
			# the WaW assets are expected to be present.
			selected_path = MONJA_CLEAN_PATH
			using_rigged = true
			special_model_id = "monja_clean_fallback"

	if ResourceLoader.exists(selected_path):
		var packed: PackedScene = load(selected_path) as PackedScene
		if packed != null:
			var imported: Node3D = packed.instantiate() as Node3D
			if imported != null:
				var visual := Node3D.new()
				visual.name = "MonjaBasicaVisual" if enemy_variant == "normal" else ("EnemyVisual_" + enemy_variant)
				add_child(visual)
				_visual_root = visual
				imported.name = "EnemySource_" + enemy_variant
				imported.rotation_degrees.y = 0.0 if using_source_waw else 90.0
				visual.add_child(imported)
				var visual_ready: bool = (
					_place_source_visual_on_feet(visual, imported)
					if using_source_waw
					else _fit_visual_to_gameplay_bounds(
						visual,
						imported,
						target_visual_height,
						target_visual_max_width,
						target_visual_max_depth
					)
				)
				if visual_ready:
					_animation_player = _find_animation_player(imported)
					var model_id: String = special_model_id
					if model_id.is_empty():
						model_id = (
							"monja_basica_rigid_rig" if using_rigid_rig
							else (
								"monja_basica_rigged_dismember" if using_rigged_dismember
								else ("monja_basica_rigged" if using_rigged else "monja_basica")
							)
						)
					set_meta("zombie_model", model_id)
					set_meta("zombie_visual_forward_fix_deg", 0.0 if using_source_waw else 90.0)
					set_meta("zombie_rig_ready", _animation_player != null)
					set_meta("zombie_rigged_asset", using_rigged)
					set_meta("zombie_source_waw", using_source_waw)
					set_meta("zombie_authored_dismember_asset", using_rigged_dismember)
					set_meta("zombie_rigid_region_rig", using_rigid_rig)
					print("XZOGOT_ENEMY_MODEL_LOADED variant=", enemy_variant, " model=", model_id)
					if using_source_waw:
						print("XZOGOT_WAW_ZOMBIE_SOURCE_LOADED model=", model_id, " scale=", visual.scale)
					elif enemy_variant == "normal":
						print("XZOGOT_MONJA_BASICA_FALLBACK")
					if _animation_player != null:
						print("XZOGOT_MONJA_RIGGED_ANIMATION_PLAYER_READY")
						_play_motion_state("idle")
					elif using_rigged or enemy_variant.begins_with("sheep_"):
						push_warning("XZOGOT_ENEMY_RIGGED_ASSET_MISSING_ANIMATION_PLAYER variant=" + enemy_variant)
					else:
						print("XZOGOT_MONJA_RETARGET_PENDING")
					return
				visual.queue_free()

	_build_fallback_visual()
	print("XZOGOT_ENEMY_VISUAL_FALLBACK variant=", enemy_variant)

func _find_animation_player(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node as AnimationPlayer
	for child: Node in node.get_children():
		var found: AnimationPlayer = _find_animation_player(child)
		if found != null:
			return found
	return null

func _place_source_visual_on_feet(wrapper: Node3D, imported: Node3D) -> bool:
	var points: Array[Vector3] = []
	_collect_mesh_bounds(imported, Transform3D.IDENTITY, points)
	if points.is_empty():
		return false

	var min_v: Vector3 = points[0]
	var max_v: Vector3 = points[0]
	for point: Vector3 in points:
		min_v.x = minf(min_v.x, point.x)
		min_v.y = minf(min_v.y, point.y)
		min_v.z = minf(min_v.z, point.z)
		max_v.x = maxf(max_v.x, point.x)
		max_v.y = maxf(max_v.y, point.y)
		max_v.z = maxf(max_v.z, point.z)

	var raw_size := max_v - min_v
	if raw_size.x <= 0.0001 or raw_size.y <= 0.0001 or raw_size.z <= 0.0001:
		return false

	var center_x := (min_v.x + max_v.x) * 0.5
	var center_z := (min_v.z + max_v.z) * 0.5
	wrapper.scale = Vector3.ONE
	wrapper.position = Vector3(-center_x, -min_v.y, -center_z)

	set_meta("zombie_visual_height_m", raw_size.y)
	set_meta("zombie_visual_width_m", raw_size.x)
	set_meta("zombie_visual_depth_m", raw_size.z)
	set_meta("zombie_visual_scale_xyz", Vector3.ONE)
	set_meta("zombie_visual_centered_on_feet", true)
	set_meta("zombie_source_scale_preserved", true)
	print("XZOGOT_WAW_ZOMBIE_SCALE_GREEN raw=", raw_size, " scale=1")
	return true

func _fit_visual_to_gameplay_bounds(
	wrapper: Node3D,
	imported: Node3D,
	target_height: float,
	max_width: float,
	max_depth: float
) -> bool:
	var points: Array[Vector3] = []
	_collect_mesh_bounds(imported, Transform3D.IDENTITY, points)
	if points.is_empty():
		return false

	var min_v: Vector3 = points[0]
	var max_v: Vector3 = points[0]
	for point: Vector3 in points:
		min_v.x = minf(min_v.x, point.x)
		min_v.y = minf(min_v.y, point.y)
		min_v.z = minf(min_v.z, point.z)
		max_v.x = maxf(max_v.x, point.x)
		max_v.y = maxf(max_v.y, point.y)
		max_v.z = maxf(max_v.z, point.z)

	var raw_size: Vector3 = max_v - min_v
	if raw_size.y <= 0.0001 or raw_size.x <= 0.0001 or raw_size.z <= 0.0001:
		return false

	var scale_y: float = target_height / raw_size.y
	var scale_x: float = max_width / raw_size.x
	var scale_z: float = max_depth / raw_size.z
	var center_x: float = (min_v.x + max_v.x) * 0.5
	var center_z: float = (min_v.z + max_v.z) * 0.5

	wrapper.scale = Vector3(scale_x, scale_y, scale_z)
	wrapper.position = Vector3(
		-center_x * scale_x,
		-min_v.y * scale_y,
		-center_z * scale_z
	)

	var fitted_size := Vector3(
		raw_size.x * scale_x,
		raw_size.y * scale_y,
		raw_size.z * scale_z
	)

	set_meta("zombie_visual_height_m", fitted_size.y)
	set_meta("zombie_visual_width_m", fitted_size.x)
	set_meta("zombie_visual_depth_m", fitted_size.z)
	set_meta("zombie_visual_scale_xyz", Vector3(scale_x, scale_y, scale_z))
	set_meta("zombie_visual_centered_on_feet", true)
	print(
		"XZOGOT_MONJA_FIT ",
		"raw=", raw_size,
		" scale_xyz=", Vector3(scale_x, scale_y, scale_z),
		" fitted=", fitted_size
	)
	return true

func _collect_mesh_bounds(node: Node3D, parent_transform: Transform3D, points: Array[Vector3]) -> void:
	var current_transform: Transform3D = parent_transform * node.transform
	if node is MeshInstance3D:
		var mesh_instance := node as MeshInstance3D
		if mesh_instance.mesh != null:
			var bounds: AABB = mesh_instance.mesh.get_aabb()
			for xi in range(2):
				for yi in range(2):
					for zi in range(2):
						var corner := bounds.position + Vector3(
							bounds.size.x * float(xi),
							bounds.size.y * float(yi),
							bounds.size.z * float(zi)
						)
						points.append(current_transform * corner)

	for child: Node in node.get_children():
		if child is Node3D:
			_collect_mesh_bounds(child as Node3D, current_transform, points)

func _build_fallback_visual() -> void:
	var visual := MeshInstance3D.new()
	visual.name = "FallbackZombieVisual"
	var mesh := CapsuleMesh.new()
	mesh.radius = 0.38
	mesh.height = target_visual_height
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.17, 0.22, 0.16)
	mat.roughness = 0.96
	mesh.material = mat
	visual.mesh = mesh
	visual.position.y = target_visual_height * 0.5
	add_child(visual)

func _physics_process(delta: float) -> void:
	_update_hit_reaction(delta)
	_update_player_attack_impact(delta)
	if _network_proxy_mode:
		_update_voice(delta)
		var distance: float = global_position.distance_to(_network_proxy_target_position)
		var blend: float = 1.0 - exp(-14.0 * delta)
		global_position = global_position.lerp(_network_proxy_target_position, blend)
		rotation.y = lerp_angle(rotation.y, _network_proxy_target_yaw, blend)
		if phase == Phase.DEAD:
			_play_motion_state("death")
		elif _hit_reaction_timer > 0.0:
			_play_motion_state("hit")
		elif _crawler:
			_play_motion_state("crawl")
		elif distance > 0.025:
			_play_motion_state("walk")
		else:
			_play_motion_state("idle")
		return
	_update_voice(delta)
	if phase == Phase.DEAD:
		return
	if _hit_reaction_timer > 0.0:
		_play_motion_state("hit")
		velocity.x = 0.0
		velocity.z = 0.0
		if not is_on_floor():
			velocity.y -= _gravity * delta
		move_and_slide()
		return

	_path_refresh_timer = maxf(0.0, _path_refresh_timer - delta)
	if _attack_timer > 0.0:
		_attack_timer = maxf(0.0, _attack_timer - delta)

	if not is_on_floor():
		velocity.y -= _gravity * delta

	match phase:
		Phase.APPROACH:
			_tick_approach()
		Phase.ATTACK_BARRICADE:
			_tick_barricade()
		Phase.CHASE_PLAYER:
			_tick_chase()
		Phase.CROSS_WINDOW:
			_tick_cross_window()

	_update_stuck_watchdog(delta)

func _tick_approach() -> void:
	_play_motion_state("walk")
	if target_barricade == null or not is_instance_valid(target_barricade):
		phase = Phase.CHASE_PLAYER
		return
	if bool(target_barricade.call("is_broken")):
		_begin_window_cross()
		return
	var target: Vector3 = target_barricade.call("get_outside_approach") as Vector3
	if _move_toward_flat(target, 0.45):
		velocity.x = 0.0
		velocity.z = 0.0
		phase = Phase.ATTACK_BARRICADE

func _tick_barricade() -> void:
	_play_motion_state("attack")
	if target_barricade == null or not is_instance_valid(target_barricade):
		phase = Phase.CHASE_PLAYER
		return
	if bool(target_barricade.call("is_broken")):
		_begin_window_cross()
		return

	# Do not allow a zombie to remain forever in ATTACK_BARRICADE after a
	# collision nudge, step-up, network correction, or bad approach transform
	# moved it away from the actual window. Re-acquire the authored approach.
	var approach: Vector3 = target_barricade.call("get_outside_approach") as Vector3
	var attack_distance := Vector2(
		global_position.x - approach.x,
		global_position.z - approach.z
	).length()
	if attack_distance > barricade_attack_max_distance:
		phase = Phase.APPROACH
		_attack_timer = 0.0
		_path_refresh_timer = 0.0
		print("XZOGOT_ZOMBIE_BARRICADE_REACQUIRE ", name, " distance=", attack_distance)
		return

	velocity.x = 0.0
	velocity.z = 0.0
	if _attack_timer <= 0.0:
		var damaged: bool = bool(target_barricade.call("zombie_damage", barricade_damage))
		if not damaged and not bool(target_barricade.call("is_broken")):
			# A live barricade that rejected damage must not trap the AI in a
			# zero-velocity attack state forever.
			phase = Phase.APPROACH
			_path_refresh_timer = 0.0
			print("XZOGOT_ZOMBIE_BARRICADE_DAMAGE_RETRY ", name)
			return
		_play_zombie_sfx(_zombie_audio_choice(ZOMBIE_ATTACKS), -8.0)
		_attack_timer = attack_interval

func _begin_window_cross() -> void:
	if target_barricade == null or not is_instance_valid(target_barricade):
		phase = Phase.CHASE_PLAYER
		return
	phase = Phase.CROSS_WINDOW
	_path_points.clear()
	_path_index = 0
	print("XZOGOT_ZOMBIE_WINDOW_CROSS_BEGIN")

func _tick_cross_window() -> void:
	# Source WaW has a recovered authored window/ground traversal clip. Use it
	# in the live crossing path instead of validating it only in CI while the
	# actual zombie continues to walk through the barricade opening.
	if bool(get_meta("zombie_source_waw", false)):
		_play_motion_state("traverse")
	else:
		_play_motion_state("walk")
	if target_barricade == null or not is_instance_valid(target_barricade):
		phase = Phase.CHASE_PLAYER
		return
	var inside: Vector3 = target_barricade.call("get_inside_point") as Vector3
	if _move_toward_flat_speed(inside, 0.22, window_cross_speed):
		velocity.x = 0.0
		velocity.z = 0.0
		phase = Phase.CHASE_PLAYER
		_path_refresh_timer = 0.0
		print("XZOGOT_ZOMBIE_ENTERED")

func _tick_chase() -> void:
	_play_motion_state("walk")
	if target_player == null or not is_instance_valid(target_player):
		velocity.x = 0.0
		velocity.z = 0.0
		return
	var target: Vector3 = target_player.global_position
	var flat_distance: float = Vector2(global_position.x - target.x, global_position.z - target.z).length()
	if flat_distance <= 1.25 and absf(global_position.y - target.y) < 1.7:
		velocity.x = 0.0
		velocity.z = 0.0
		_play_motion_state("attack")
		if _attack_timer <= 0.0 and not _player_attack_pending:
			_queue_player_attack()
		return
	_move_toward_navigated(target, 0.0)

func _effective_player_attack_damage() -> float:
	var arm_factor: float = 1.0
	if bool(_severed["left_arm"]):
		arm_factor -= 0.22
	if bool(_severed["right_arm"]):
		arm_factor -= 0.22
	if _headless:
		arm_factor *= 0.88
	return player_damage * maxf(arm_factor, 0.42)

func _queue_player_attack() -> void:
	if target_player == null or not is_instance_valid(target_player):
		return
	_player_attack_pending = true
	_player_attack_impact_timer = maxf(0.0, player_attack_impact_delay)
	_attack_timer = attack_interval
	_motion_state = ""
	_play_motion_state("attack")
	_play_zombie_sfx(_zombie_audio_choice(ZOMBIE_ATTACKS), -6.0)
	set_meta("player_attack_pending", true)
	set_meta("player_attack_impact_delay", _player_attack_impact_timer)

func _update_player_attack_impact(delta: float) -> void:
	if not _player_attack_pending:
		return
	_player_attack_impact_timer = maxf(0.0, _player_attack_impact_timer - delta)
	if _player_attack_impact_timer > 0.0:
		return

	_player_attack_pending = false
	set_meta("player_attack_pending", false)
	if phase == Phase.DEAD:
		return
	if target_player == null or not is_instance_valid(target_player):
		return
	if not target_player.has_method("apply_damage"):
		return
	if target_player.has_method("is_downed") and bool(target_player.call("is_downed")):
		return

	var flat_distance: float = Vector2(
		global_position.x - target_player.global_position.x,
		global_position.z - target_player.global_position.z
	).length()
	if flat_distance > 1.45 or absf(global_position.y - target_player.global_position.y) >= 1.7:
		set_meta("player_attack_missed", true)
		return

	target_player.call("apply_damage", _effective_player_attack_damage())
	set_meta("player_attack_missed", false)
	set_meta("player_attack_hit", true)
	print("XZOGOT_ZOMBIE_ATTACK_IMPACT_SYNC ", name)

func _has_clear_path_to(target: Vector3) -> bool:
	# Never shortcut graph routing across floors. A clear horizontal ray can
	# otherwise make a zombie chase the X/Z below a balcony or above a crypt.
	if absf(global_position.y - target.y) > direct_path_vertical_limit:
		return false
	var world: World3D = get_world_3d()
	if world == null:
		return true
	var from: Vector3 = global_position + Vector3(0.0, 0.80, 0.0)
	var to: Vector3 = target + Vector3(0.0, 0.80, 0.0)
	var ray := PhysicsRayQueryParameters3D.create(from, to)
	ray.exclude = [get_rid()]
	var hit: Dictionary = world.direct_space_state.intersect_ray(ray)
	if hit.is_empty():
		return true
	var collider: Object = hit.get("collider") as Object
	return collider == target_player

func _move_toward_navigated(target: Vector3, stop_distance: float) -> bool:
	if _has_clear_path_to(target):
		_path_points.clear()
		_path_index = 0
		return _move_toward_flat(target, stop_distance)

	if _path_network == null or not is_instance_valid(_path_network):
		_path_network = get_tree().get_first_node_in_group("zombie_path_network")
	if _path_network == null or not _path_network.has_method("request_path"):
		return _move_toward_flat(target, stop_distance)

	# Independent maps may enforce locked-door topology with can_reach().
	# Existing Church/Nacht networks expose no such method: unchanged behavior.
	# Do not chase through a wall just because a graph returned no route.
	if _path_network.has_method("can_reach") and not bool(
		_path_network.call("can_reach", global_position, target)
	):
		_path_points.clear()
		_path_index = 0
		velocity.x = 0.0
		velocity.z = 0.0
		move_and_slide()
		return false

	if (
		_path_refresh_timer <= 0.0
		or _path_points.is_empty()
		or _last_path_target == Vector3.INF
		or _last_path_target.distance_to(target) > 1.8
	):
		_path_points = _path_network.call("request_path", global_position, target) as Array[Vector3]
		_path_index = 0
		_last_path_target = target
		_path_refresh_timer = path_refresh_interval + float(abs(name.hash()) % 17) * 0.007

	while _path_index < _path_points.size():
		var waypoint: Vector3 = _path_points[_path_index]
		var waypoint_flat_distance := Vector2(
			global_position.x - waypoint.x,
			global_position.z - waypoint.z
		).length()
		var waypoint_vertical_distance := absf(global_position.y - waypoint.y)
		# Do not skip a balcony/crypt waypoint just because X/Z overlaps while
		# the zombie is still on the wrong floor.
		if (
			waypoint_flat_distance <= 0.55
			and waypoint_vertical_distance <= waypoint_vertical_tolerance
		):
			_path_index += 1
			continue
		return _move_toward_flat(waypoint, 0.22)

	return _move_toward_flat(target, stop_distance)

func _move_toward_flat(target: Vector3, stop_distance: float) -> bool:
	return _move_toward_flat_speed(target, stop_distance, move_speed)

func _move_toward_flat_speed(target: Vector3, stop_distance: float, speed: float) -> bool:
	var delta_pos := Vector3(target.x - global_position.x, 0.0, target.z - global_position.z)
	var distance: float = delta_pos.length()
	if distance <= stop_distance:
		return true
	var direction: Vector3 = delta_pos.normalized()
	var target_yaw: float = atan2(-direction.x, -direction.z)
	rotation.y = lerp_angle(rotation.y, target_yaw, turn_lerp)
	velocity.x = direction.x * speed
	velocity.z = direction.z * speed
	var before_move := global_position
	move_and_slide()
	var horizontal_moved := Vector2(
		global_position.x - before_move.x,
		global_position.z - before_move.z
	).length()
	if is_on_floor() and horizontal_moved < 0.003:
		_try_step_up(direction)
	return false

func _try_step_up(direction: Vector3) -> bool:
	# CharacterBody3D will happily stop on a tiny hard lip.  Probe a short set of
	# human-sized step heights and advance only when both the vertical clearance
	# and the raised forward move are collision-free.
	if direction.length_squared() <= 0.0001:
		return false
	var step_heights: Array[float] = [0.10, 0.18, 0.26, 0.34, max_step_height]
	for step_height: float in step_heights:
		if step_height <= 0.0 or step_height > max_step_height + 0.001:
			continue
		var up := Vector3.UP * step_height
		if test_move(global_transform, up):
			continue
		var raised_transform := global_transform.translated(up)
		var forward := direction.normalized() * step_forward_distance
		if test_move(raised_transform, forward):
			continue
		global_position += up + forward
		velocity.y = 0.0
		apply_floor_snap()
		set_meta("last_step_up_height", step_height)
		print("XZOGOT_ZOMBIE_STEP_UP ", name, " height=", step_height)
		return true
	return false

func _update_stuck_watchdog(delta: float) -> void:
	if phase == Phase.DEAD or phase == Phase.ATTACK_BARRICADE:
		_stuck_accum = 0.0
		_stuck_sample_timer = 0.0
		_last_motion_sample = global_position
		return

	_stuck_sample_timer += delta
	if _stuck_sample_timer < stuck_sample_interval:
		return

	var moved: float = Vector2(
		global_position.x - _last_motion_sample.x,
		global_position.z - _last_motion_sample.z
	).length()
	var expected: float = Vector2(velocity.x, velocity.z).length()

	if expected > 0.25 and moved < 0.07:
		_stuck_accum += _stuck_sample_timer
	else:
		_stuck_accum = 0.0
		_unstuck_count = 0

	_last_motion_sample = global_position
	_stuck_sample_timer = 0.0

	if _stuck_accum >= stuck_timeout:
		_attempt_unstuck()
		_stuck_accum = 0.0

func _attempt_unstuck() -> void:
	if target_player == null or not is_instance_valid(target_player):
		return

	_unstuck_count += 1
	_path_refresh_timer = 0.0
	_path_points.clear()
	_path_index = 0

	var recovery_goal: Vector3 = target_player.global_position
	if target_barricade != null and is_instance_valid(target_barricade):
		if phase == Phase.APPROACH and target_barricade.has_method("get_outside_approach"):
			recovery_goal = target_barricade.call("get_outside_approach") as Vector3
		elif phase == Phase.CROSS_WINDOW and target_barricade.has_method("get_inside_point"):
			recovery_goal = target_barricade.call("get_inside_point") as Vector3

	var recovery: Vector3 = recovery_goal
	if _path_network != null and is_instance_valid(_path_network) and _path_network.has_method("recovery_point"):
		recovery = _path_network.call("recovery_point", global_position, recovery_goal) as Vector3

	var flat := Vector3(recovery.x - global_position.x, 0.0, recovery.z - global_position.z)
	if flat.length_squared() <= 0.0001:
		return
	var forward: Vector3 = flat.normalized()
	if is_on_floor() and _try_step_up(forward):
		print("XZOGOT_ZOMBIE_UNSTUCK_STEP ", name, " attempt=", _unstuck_count)
		return
	var right := Vector3(-forward.z, 0.0, forward.x)
	var candidates: Array[Vector3] = [
		forward * 0.42,
		right * 0.34,
		-right * 0.34,
		forward * 0.64 + right * 0.24,
		forward * 0.64 - right * 0.24,
		right * 0.58,
		-right * 0.58,
		-forward * 0.24,
	]
	for motion: Vector3 in candidates:
		if not test_move(global_transform, motion):
			global_position += motion
			print("XZOGOT_ZOMBIE_UNSTUCK ", name, " attempt=", _unstuck_count)
			return

	print("XZOGOT_ZOMBIE_UNSTUCK_REPATH ", name, " attempt=", _unstuck_count)

func _animation_name_for_keys(keys: Array[String]) -> String:
	if _animation_player == null:
		return ""
	for anim_name: StringName in _animation_player.get_animation_list():
		var lower: String = str(anim_name).to_lower()
		for key: String in keys:
			if lower.contains(key.to_lower()):
				return str(anim_name)
	return ""

func _rigged_fallback_animation(state: String) -> String:
	if _animation_player == null:
		return ""
	var alias_table: Dictionary = SHEEP_FALLBACK_ANIMS if enemy_variant.begins_with("sheep_") else RIGGED_FALLBACK_ANIMS
	if not alias_table.has(state):
		return ""
	var aliases: Array = alias_table[state] as Array
	for alias_var: Variant in aliases:
		var alias: String = str(alias_var)
		for anim_name: StringName in _animation_player.get_animation_list():
			var candidate: String = str(anim_name)
			if candidate.to_lower().contains(alias.to_lower()):
				return candidate
	return ""

func _waw_source_keys(role: String) -> Array[String]:
	var result: Array[String] = []
	var raw: Variant = WAW_SOURCE_STATE_KEYS.get(role, [])
	if raw is Array:
		for value: Variant in raw as Array:
			result.append(str(value))
	return result

func _animation_speed_for_state(state: String) -> float:
	if enemy_variant == "sheep_runner":
		match state:
			"walk": return 1.38
			"attack": return 1.16
			"death": return 1.08
			_: return 1.0
	if enemy_variant == "sheep_brute":
		match state:
			"walk": return 0.92
			"attack": return 0.88
			"death": return 0.82
			_: return 0.94
	if enemy_variant == "nun_elite":
		match state:
			"walk": return 1.04
			"attack": return 1.08
			"hit": return 1.05
			_: return 1.0
	return 1.0

func _animation_blend_for_state(state: String) -> float:
	match state:
		"attack": return 0.06
		"hit": return 0.04
		"death": return 0.08
		_: return 0.10

func _play_motion_state(state: String) -> void:
	if _motion_state == state:
		# Imported GLTF clips are not guaranteed to be flagged as loops.  If a
		# walk/idle clip reached its end, restart it instead of letting the model
		# slide rigidly through the world.
		if _animation_player == null or _animation_player.is_playing():
			return
	_motion_state = state
	set_meta("motion_state", state)
	if _animation_player == null:
		return

	var keys: Array[String] = []
	var source_waw: bool = str(get_meta("zombie_model", "")).begins_with("waw_")
	if source_waw:
		match state:
			"idle":
				keys.assign(WAW_SOURCE_STATE_KEYS["idle"])
			"walk":
				if str(get_meta("motion_override", "")) == "crawl":
					# Exact WaW crawler clip is still being recovered from the
					# Nacht lane. Do not substitute an unrelated authored clip.
					set_meta("crawler_visual_source_pending", true)
					keys = []
				elif move_speed >= 3.55:
					keys.assign(WAW_SOURCE_STATE_KEYS["sprint"])
				elif move_speed >= 2.55:
					keys.assign(WAW_SOURCE_STATE_KEYS["run"])
				elif move_speed >= 2.05:
					keys.assign(WAW_SOURCE_STATE_KEYS["walk_fast"])
				else:
					keys.assign(WAW_SOURCE_STATE_KEYS["walk"])
			"attack":
				keys.assign(WAW_SOURCE_STATE_KEYS["attack"])
			"death":
				keys.assign(WAW_SOURCE_STATE_KEYS["death"])
			"traverse":
				keys.assign(WAW_SOURCE_STATE_KEYS["traverse"])
			"hit":
				# No WaW hit-reaction clip exists in the validated 57-PSA set.
				# Gameplay hit reaction remains procedural; do not fake a source clip.
				keys = []
			_:
				keys = []
	elif state == "walk":
		if str(get_meta("motion_override", "")) == "crawl":
			keys = CRAWL_KEYS
		else:
			var profile_keys: Array = _motion_profile.get("walk_keys", []) as Array
			for key_var: Variant in profile_keys:
				keys.append(str(key_var))
	elif state == "attack":
		keys = ATTACK_KEYS
	elif state == "hit":
		keys = HIT_KEYS
	elif state == "death":
		keys = DEATH_KEYS
	elif state == "getup":
		keys = GETUP_KEYS

	var anim_name: String = _animation_name_for_keys(keys)
	if anim_name.is_empty() and not source_waw:
		anim_name = _rigged_fallback_animation(state)
	if not anim_name.is_empty():
		var anim_speed: float = _animation_speed_for_state(state)
		var anim_blend: float = _animation_blend_for_state(state)
		_animation_player.play(anim_name, anim_blend, anim_speed)
		set_meta("active_animation", anim_name)
		set_meta("active_animation_speed", anim_speed)
		print("XZOGOT_ENEMY_ANIM ", enemy_variant, " ", state, " -> ", anim_name, " speed=", anim_speed)

func _classify_hit_zone(local_hit: Vector3) -> String:
	if local_hit.y >= target_visual_height * headshot_height_ratio:
		return "head"
	if local_hit.y <= 0.78:
		return "left_leg" if local_hit.x < 0.0 else "right_leg"
	if local_hit.y >= 0.88 and absf(local_hit.x) >= 0.22:
		return "left_arm" if local_hit.x < 0.0 else "right_arm"
	return "torso"

func _weapon_dismember_multiplier(source: Node) -> float:
	if source == null:
		return 1.0
	var weapon: Node = source.get_node_or_null("Weapon")
	if weapon == null or not weapon.has_method("get_family"):
		return 1.0
	var family: String = str(weapon.call("get_family"))
	match family:
		"pistol": return 0.62
		"smg": return 0.82
		"rifle": return 1.08
		"lmg": return 1.18
		"shotgun": return 1.78
		"sniper": return 1.52
		"wonder": return 2.75
	return 1.0

func _authored_limb_name(zone: String) -> String:
	match zone:
		"head": return "Dismember_Head"
		"left_arm": return "Dismember_LeftArm"
		"right_arm": return "Dismember_RightArm"
		"left_leg": return "Dismember_LeftLeg"
		"right_leg": return "Dismember_RightLeg"
	return ""

func _find_authored_limbs(zone: String) -> Array[MeshInstance3D]:
	var result: Array[MeshInstance3D] = []
	if _visual_root == null:
		return result
	var limb_name: String = _authored_limb_name(zone)
	if limb_name.is_empty():
		return result
	var token := limb_name.to_lower()
	for node: Node in _visual_root.find_children("*", "MeshInstance3D", true, false):
		if node is MeshInstance3D and node.name.to_lower().contains(token):
			result.append(node as MeshInstance3D)
	return result

func _find_authored_limb(zone: String) -> MeshInstance3D:
	var limbs := _find_authored_limbs(zone)
	return limbs[0] if not limbs.is_empty() else null

func _spawn_detached_proxy(zone: String, source_part: MeshInstance3D = null) -> void:
	var rigid := RigidBody3D.new()
	rigid.name = "Detached_" + zone
	rigid.mass = 2.1 if "leg" in zone else (1.25 if "arm" in zone else 1.6)
	rigid.collision_layer = 0
	rigid.collision_mask = 1
	get_parent().add_child(rigid)

	var mesh_instance := MeshInstance3D.new()
	var shape := CollisionShape3D.new()
	if source_part != null and source_part.mesh != null:
		rigid.global_transform = source_part.global_transform
		mesh_instance.mesh = source_part.mesh
		var authored_shape := CapsuleShape3D.new()
		authored_shape.radius = 0.12
		authored_shape.height = 0.42
		shape.shape = authored_shape
	else:
		rigid.global_position = global_position + Vector3(
			-0.26 if "left" in zone else (0.26 if "right" in zone else 0.0),
			1.55 if zone == "head" else (1.05 if "arm" in zone else 0.45),
			0.0
		)
		var mat := StandardMaterial3D.new()
		mat.albedo_color = Color(0.10, 0.095, 0.09) if zone != "head" else Color(0.34, 0.26, 0.22)
		mat.roughness = 0.92
		if zone == "head":
			var sphere := SphereMesh.new()
			sphere.radius = 0.17
			sphere.height = 0.34
			sphere.material = mat
			mesh_instance.mesh = sphere
			var sphere_shape := SphereShape3D.new()
			sphere_shape.radius = 0.17
			shape.shape = sphere_shape
		else:
			var capsule_mesh := CapsuleMesh.new()
			capsule_mesh.radius = 0.105 if "arm" in zone else 0.13
			capsule_mesh.height = 0.58 if "arm" in zone else 0.74
			capsule_mesh.material = mat
			mesh_instance.mesh = capsule_mesh
			var capsule_shape := CapsuleShape3D.new()
			capsule_shape.radius = 0.10 if "arm" in zone else 0.12
			capsule_shape.height = 0.56 if "arm" in zone else 0.70
			shape.shape = capsule_shape

	rigid.add_child(mesh_instance)
	rigid.add_child(shape)
	var away: Vector3 = Vector3(
		-1.0 if "left" in zone else (1.0 if "right" in zone else 0.25),
		0.8,
		0.35
	).normalized()
	rigid.apply_central_impulse(away * 2.2 + Vector3.UP * 1.4)
	rigid.apply_torque_impulse(Vector3(0.7, 1.1, 0.5))

	var timer := Timer.new()
	timer.one_shot = true
	timer.wait_time = 8.0
	timer.autostart = true
	timer.timeout.connect(rigid.queue_free)
	rigid.add_child(timer)

func _make_crawler() -> void:
	if _crawler:
		return
	_crawler = true
	move_speed = minf(move_speed, crawler_speed)
	window_cross_speed = minf(window_cross_speed, crawler_speed * 1.25)
	set_meta("motion_override", "crawl")
	set_meta("crawler", true)
	var cs: CollisionShape3D = get_node_or_null("ZombieCollider") as CollisionShape3D
	if cs != null and cs.shape is CapsuleShape3D:
		var capsule := cs.shape as CapsuleShape3D
		capsule.radius = 0.30
		capsule.height = 0.78
		cs.position.y = 0.39
	if _animation_player == null and _visual_root != null:
		_visual_root.rotation_degrees.x = 72.0
		_visual_root.position.y = 0.32
	print("XZOGOT_ZOMBIE_CRAWLER_CONVERTED")

func _headless_survival_roll() -> bool:
	var round_number: int = int(get_meta("round_number", 1))
	var chance: float = clampf(0.04 + float(maxi(0, round_number - 10)) * 0.025, 0.04, 0.38)
	var roll: float = float(abs((name + ":headless:" + str(round_number)).hash()) % 10000) / 10000.0
	set_meta("headless_survival_chance", chance)
	return roll < chance

func _sever_limb(zone: String, source: Node, impulse_damage: float) -> bool:
	if not _severed.has(zone) or bool(_severed[zone]):
		return false
	_severed[zone] = true
	set_meta("severed_" + zone, true)

	var authored_limbs := _find_authored_limbs(zone)
	var authored: MeshInstance3D = authored_limbs[0] if not authored_limbs.is_empty() else null
	_spawn_detached_proxy(zone, authored)
	if not authored_limbs.is_empty():
		for part: MeshInstance3D in authored_limbs:
			part.visible = false
		print("XZOGOT_AUTHORED_LIMB_DETACHED ", zone, " meshes=", authored_limbs.size())
	else:
		print("XZOGOT_LIMB_PROXY_DETACHED ", zone)

	if zone == "left_leg" or zone == "right_leg":
		_make_crawler()
	elif zone == "head":
		_headless = true
		set_meta("headless", true)
		_headless_survivor = _headless_survival_roll()
		if _headless_survivor:
			health = maxf(health, impulse_damage + 35.0)
			print("XZOGOT_HEADLESS_SURVIVOR round=", int(get_meta("round_number", 1)))
		else:
			print("XZOGOT_HEAD_DISMEMBER_FATAL")
			_die(source)
			return true
	return false

func _apply_limb_damage(zone: String, amount: float, source: Node) -> bool:
	if not dismemberment_enabled or zone == "torso" or not _limb_health.has(zone):
		return false
	if bool(_severed.get(zone, false)):
		return false
	var scaled: float = amount * _weapon_dismember_multiplier(source)
	_limb_health[zone] = float(_limb_health[zone]) - scaled
	set_meta("limb_hp_" + zone, maxf(0.0, float(_limb_health[zone])))
	if float(_limb_health[zone]) <= 0.0:
		return _sever_limb(zone, source, amount)
	return false

func _core_damage_multiplier_for_zone(zone: String) -> float:
	match zone:
		"left_arm", "right_arm": return 0.42
		"left_leg", "right_leg": return 0.35
		"head": return 1.0
	return 1.0

func apply_hitscan_damage(amount: float, source: Node = null, hit_position: Vector3 = Vector3.ZERO) -> void:
	if phase == Phase.DEAD or amount <= 0.0:
		return
	if _submit_network_proxy_hit(hit_position, false):
		return
	var local_hit: Vector3 = to_local(hit_position)
	var zone: String = _classify_hit_zone(local_hit)
	var is_headshot: bool = zone == "head"
	var applied_amount: float = amount * (headshot_multiplier if is_headshot else 1.0)
	set_meta("last_hit_headshot", is_headshot)
	set_meta("last_hit_zone", zone)
	if is_headshot:
		print("XZOGOT_ZOMBIE_HEADSHOT")
	if _apply_limb_damage(zone, applied_amount, source):
		return
	var core_damage: float = applied_amount * _core_damage_multiplier_for_zone(zone)
	_take_damage(core_damage, source, is_headshot)

func apply_melee_damage(amount: float, source: Node = null, hit_position: Vector3 = Vector3.ZERO) -> void:
	if phase == Phase.DEAD or amount <= 0.0:
		return
	if _submit_network_proxy_hit(hit_position, true):
		return
	set_meta("last_damage_kind", "melee")
	set_meta("last_melee_hit_position", hit_position)
	_take_damage(amount, source, false)

func apply_damage(amount: float, source: Node = null) -> void:
	if _network_proxy_mode:
		return
	_take_damage(amount, source, false)

func _take_damage(amount: float, source: Node, headshot: bool) -> void:
	if phase == Phase.DEAD or amount <= 0.0:
		return
	var applied_amount: float = amount
	if source != null and bool(get_tree().get_meta("xz_insta_kill_active", false)):
		applied_amount = maxf(applied_amount, health)
		set_meta("insta_kill_hit", true)
		print("XZOGOT_INSTA_KILL_HIT ", name)
	health -= applied_amount
	_hit_reaction_timer = hit_reaction_duration
	if health > 0.0:
		_motion_state = ""
		_play_motion_state("hit")
	if source != null and source.has_method("add_points"):
		source.call("add_points", 10)
		if headshot:
			source.call("add_points", headshot_bonus_points)
	if health <= 0.0:
		_die(source)

func _update_hit_reaction(delta: float) -> void:
	if _visual_root == null or not is_instance_valid(_visual_root):
		return
	if _hit_reaction_timer > 0.0:
		_hit_reaction_timer = maxf(0.0, _hit_reaction_timer - delta)
		var ratio: float = _hit_reaction_timer / maxf(hit_reaction_duration, 0.001)
		_visual_root.rotation.z = deg_to_rad(sin(ratio * PI) * 4.5)
	else:
		_visual_root.rotation.z = move_toward(_visual_root.rotation.z, 0.0, delta * 4.5)

func get_health() -> float:
	return health

func is_crawler() -> bool:
	return _crawler

func is_headless() -> bool:
	return _headless

func survived_headless() -> bool:
	return _headless_survivor

func is_limb_severed(zone: String) -> bool:
	return bool(_severed.get(zone, false))

func get_limb_health(zone: String) -> float:
	return float(_limb_health.get(zone, 0.0))

func get_dismemberment_state() -> Dictionary:
	return {
		"crawler": _crawler,
		"headless": _headless,
		"headless_survivor": _headless_survivor,
		"severed": _severed.duplicate(true),
		"limb_health": _limb_health.duplicate(true),
	}

func powerup_kill() -> void:
	if phase == Phase.DEAD:
		return
	set_meta("suppress_powerup_drop", true)
	_die(null)

func _die(source: Node) -> void:
	if phase == Phase.DEAD:
		return
	phase = Phase.DEAD
	_player_attack_pending = false
	_player_attack_impact_timer = 0.0
	velocity = Vector3.ZERO
	collision_layer = 0
	collision_mask = 0
	_play_motion_state("death")
	_play_zombie_sfx(_zombie_audio_choice(ZOMBIE_DEATHS), -4.0, true)
	if source != null and source.has_method("add_points"):
		source.call("add_points", 60)
	print("XZOGOT_ZOMBIE_KILLED ", _motion_profile_id, " variant=", enemy_variant)
	died.emit(self)

	# Let the authored death clip remain visible.  Previously queue_free() ran in
	# the same frame as AnimationPlayer.play(), so sheep/nun death animations
	# existed in the asset but could never be seen.
	var linger: float = maxf(0.35, death_linger_time)
	if enemy_variant == "sheep_runner":
		linger = maxf(linger, 1.05)
	elif enemy_variant == "sheep_brute":
		linger = maxf(linger, 1.20)
	elif enemy_variant == "nun_elite":
		linger = maxf(linger, 1.40)
	set_meta("death_animation_linger", linger)
	var cleanup_timer := get_tree().create_timer(linger)
	cleanup_timer.timeout.connect(_finish_death_cleanup)

func _finish_death_cleanup() -> void:
	if is_instance_valid(self):
		queue_free()

func get_phase() -> int:
	return int(phase)

func get_motion_profile_id() -> String:
	return _motion_profile_id

func get_unstuck_count() -> int:
	return _unstuck_count
