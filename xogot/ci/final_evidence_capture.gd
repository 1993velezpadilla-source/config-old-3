extends SceneTree

const OUT_DIR := "/tmp/xogot-final-evidence"
const VIDEO_DIR := "/tmp/xogot-final-evidence/video_frames"
const VIEW_SIZE := Vector2i(1920, 1080)

var _scene: Node
var _player: Node3D
var _player_camera: Camera3D
var _free_camera: Camera3D
var _round_manager: Node
var _zombie: Node3D

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("FINAL_EVIDENCE: " + message)
	quit(code)

func _wait_frames(count: int) -> void:
	for _i in range(count):
		await process_frame

func _save_png(name: String) -> bool:
	await _wait_frames(4)
	var image: Image = root.get_texture().get_image()
	if image == null or image.is_empty():
		return false
	var path := OUT_DIR + "/" + name + ".png"
	var err := image.save_png(path)
	if err != OK:
		return false
	print("XZOGOT_FINAL_CAPTURE ", name, " ", image.get_width(), "x", image.get_height())
	return true

func _set_free_view(name: String, pos: Vector3, target: Vector3, fov: float = 66.0) -> bool:
	_player_camera.current = false
	_free_camera.current = true
	_free_camera.global_position = pos
	_free_camera.fov = fov
	_free_camera.look_at(target, Vector3.UP)
	await _wait_frames(8)
	return await _save_png(name)

func _set_gameplay_view(name: String, player_pos: Vector3, yaw_deg: float, pitch_deg: float = 0.0) -> bool:
	_free_camera.current = false
	_player_camera.current = true
	_player.global_position = player_pos
	_player.rotation.y = deg_to_rad(yaw_deg)
	var head: Node3D = _player.get_node_or_null("Head") as Node3D
	if head != null:
		head.rotation.x = deg_to_rad(pitch_deg)
	await _wait_frames(8)
	return await _save_png(name)

func _prepare_gameplay_zombie() -> void:
	if _round_manager == null:
		return
	if _round_manager.has_method("set"):
		_round_manager.set("auto_start", false)
	if _round_manager.has_method("start_next_round"):
		_round_manager.call("start_next_round")
	if _round_manager.has_method("spawn_one"):
		_zombie = _round_manager.call("spawn_one") as Node3D
	if _zombie == null:
		return
	_zombie.global_position = Vector3(0.25, 0.38, -3.8)
	_zombie.set("phase", 2)
	if _zombie.has_method("configure_direct"):
		_zombie.call("configure_direct", _player, null)
	_zombie.set_meta("final_evidence_zombie", true)

func _record_gameplay_video() -> bool:
	DirAccess.make_dir_recursive_absolute(VIDEO_DIR)
	_free_camera.current = false
	_player_camera.current = true
	_player.global_position = Vector3(0.0, 0.38, 7.2)
	_player.rotation.y = 0.0
	var head: Node3D = _player.get_node_or_null("Head") as Node3D
	if head != null:
		head.rotation.x = deg_to_rad(-2.0)

	if _zombie == null or not is_instance_valid(_zombie):
		_prepare_gameplay_zombie()
	if _zombie == null:
		return false
	_zombie.global_position = Vector3(0.0, 0.38, -5.8)
	_zombie.set("phase", 2)

	var frame_count := 96
	for i in range(frame_count):
		# Slow player retreat keeps the Monja in front of the camera while her
		# chase/attack animation is driven by the real gameplay state machine.
		if i > 18 and i < 78:
			_player.global_position.z += 0.018
		if i == 62 and _player.has_method("request_knife"):
			_player.call("request_knife")
		await create_timer(1.0 / 16.0).timeout
		var image: Image = root.get_texture().get_image()
		if image == null or image.is_empty():
			return false
		var frame_path := VIDEO_DIR + "/frame_%04d.png" % i
		if image.save_png(frame_path) != OK:
			return false

	print("XZOGOT_FINAL_VIDEO_FRAMES_GREEN ", frame_count)
	return true

func _run() -> void:
	DirAccess.make_dir_recursive_absolute(OUT_DIR)
	DirAccess.make_dir_recursive_absolute(VIDEO_DIR)
	var packed: PackedScene = load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(2, "main scene missing")
		return
	_scene = packed.instantiate()
	root.add_child(_scene)
	await _wait_frames(30)

	_player = _scene.get_node_or_null("Player") as Node3D
	if _player == null:
		_fail(3, "player missing")
		return
	_player_camera = _scene.get_node_or_null("Player/Head/Camera3D") as Camera3D
	if _player_camera == null:
		_fail(4, "player camera missing")
		return
	_round_manager = _scene.get_node_or_null("RoundManager")

	# Turn on final-map electrical presentation without bypassing its startup rig.
	get_tree().set_meta("power_on", true)
	for node: Node in get_tree().get_nodes_in_group("xz_power_light_rig"):
		if node.has_method("dev_trigger_startup"):
			node.call("dev_trigger_startup")
	await create_timer(1.8).timeout

	_free_camera = Camera3D.new()
	_free_camera.name = "FinalEvidenceCamera"
	_free_camera.current = false
	_scene.add_child(_free_camera)

	var ok := true
	# Non-gameplay / architectural views.
	ok = ok and await _set_free_view("01_overview_full_map", Vector3(0.0, 48.0, 8.0), Vector3(0.0, 0.0, -5.0), 60.0)
	ok = ok and await _set_free_view("02_exterior_front", Vector3(0.0, 8.2, 41.0), Vector3(0.0, 5.0, 5.0), 58.0)
	ok = ok and await _set_free_view("03_exterior_rear_ruins", Vector3(-5.0, 9.0, -48.0), Vector3(0.0, 2.2, -20.0), 62.0)
	ok = ok and await _set_free_view("04_graveyard_east", Vector3(36.0, 7.5, -23.0), Vector3(14.0, 1.8, -12.0), 60.0)
	ok = ok and await _set_free_view("05_sanctuary_altar", Vector3(0.0, 3.3, -10.0), Vector3(0.0, 1.5, -21.0), 55.0)
	ok = ok and await _set_free_view("06_second_floor_choir", Vector3(0.0, 8.6, -13.0), Vector3(0.0, 4.9, -2.0), 61.0)
	ok = ok and await _set_free_view("07_bell_tower", Vector3(-35.0, 12.0, 18.0), Vector3(-25.0, 7.0, 9.0), 56.0)
	ok = ok and await _set_free_view("08_generator_power_room", Vector3(-10.3, 2.7, 6.2), Vector3(-12.0, 1.2, 4.0), 64.0)
	ok = ok and await _set_free_view("09_crypt_reliquary", Vector3(6.2, -0.35, -18.0), Vector3(6.2, -2.0, -21.0), 68.0)
	ok = ok and await _set_free_view("10_sacristy", Vector3(10.2, 2.5, -7.2), Vector3(11.8, 1.1, -12.0), 62.0)

	_prepare_gameplay_zombie()
	await _wait_frames(18)
	# Real first-person gameplay views with HUD.
	ok = ok and await _set_gameplay_view("11_gameplay_nave", Vector3(0.0, 0.38, 6.2), 0.0, -2.0)
	ok = ok and await _set_gameplay_view("12_gameplay_sanctuary", Vector3(1.4, 0.38, -9.0), 0.0, -1.0)
	ok = ok and await _set_gameplay_view("13_gameplay_front_exterior", Vector3(0.0, 0.38, 28.0), 180.0, -3.0)
	ok = ok and await _set_gameplay_view("14_gameplay_rear_ruins", Vector3(-3.0, 0.38, -30.0), 0.0, -2.0)

	if not ok:
		_fail(5, "one or more PNG captures failed")
		return
	if not await _record_gameplay_video():
		_fail(6, "video frame capture failed")
		return

	var rigged_seen := false
	var animated_seen := false
	for node: Node in get_tree().get_nodes_in_group("zombie"):
		if bool(node.get_meta("zombie_rigged_asset", false)):
			rigged_seen = true
		var anim_name := str(node.get_meta("active_animation", ""))
		if not anim_name.is_empty():
			animated_seen = true

	print("XZOGOT_FINAL_EVIDENCE_RIGGED_MONJA ", rigged_seen)
	print("XZOGOT_FINAL_EVIDENCE_ANIMATED_MONJA ", animated_seen)
	if not ResourceLoader.exists("res://assets/zombies/monja_basica_rigged.glb"):
		_fail(7, "final evidence requires rigged Monja asset")
		return
	if not rigged_seen or not animated_seen:
		_fail(8, "final evidence requires visibly animated rigged Monja")
		return

	print("XZOGOT_FINAL_EVIDENCE_CAPTURE_GREEN 14_png 96_video_frames")
	quit(0)
