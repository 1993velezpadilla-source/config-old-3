extends SceneTree
## Actual Godot OpenGL frames from the same Black Pines Player/Weapon hierarchy.
## Do not call this GREEN just because a source bone's track points left.
## Save first-person renders, camera-space bone trajectories and names for
## independent review before a new APK is approved.
const BLACK_PINES := preload("res://black_pines.tscn")
const FRACTIONS := [0.02, 0.18, 0.34, 0.50, 0.68, 0.88]
var _positions: Dictionary = {"tactical": [], "empty": []}
var _offscreen_critical: Dictionary = {"tactical": false, "empty": false}

func _init() -> void:
    call_deferred("_run")

func _fail(message: String) -> void:
    push_error("MP40_REAL_FRAME_AUDIT_RED " + message)
    quit(84)

func _find_mag_skeleton(gun: Node3D) -> Skeleton3D:
    var stack: Array[Node] = [gun]
    while not stack.is_empty():
        var node: Node = stack.pop_back()
        if node is Skeleton3D and (node as Skeleton3D).find_bone("j_clip") >= 0:
            return node as Skeleton3D
        for child: Node in node.get_children():
            stack.append(child)
    return null

func _capture_frame(
        gun_player: AnimationPlayer, hand_player: AnimationPlayer,
        hands_skeleton: Skeleton3D, gun_skeleton: Skeleton3D,
        weapon: Node, camera: Camera3D, label: Label,
        mode: String, frame_idx: int, fraction: float) -> bool:
    var gun_t: float = minf(gun_player.current_animation_length - 0.005, gun_player.current_animation_length * fraction)
    var hand_t: float = minf(hand_player.current_animation_length - 0.005, hand_player.current_animation_length * fraction)
    # Set both authored clips to the exact same normalized reload phase;
    # Godot runtime is paused so _process does not spuriously change state.
    # Pause() made current_animation empty on the first attempt. Explicitly
    # play, seek, and advance both mixers in MANUAL callback mode.
    var gun_clip_name := "PSA_viewmodel_mp40_reload" if mode == "tactical" else "PSA_viewmodel_mp40_reload_empty"
    var hand_clip_name := "PSA_MP40ReloadHands" if mode == "tactical" else "PSA_viewmodel_mp40_reload_empty"
    gun_player.play(gun_clip_name, 0.0)
    hand_player.play(hand_clip_name, 0.0)
    gun_player.seek(gun_t, true)
    hand_player.seek(hand_t, true)
    gun_player.advance(0.0)
    hand_player.advance(0.0)
    if gun_player.current_animation != gun_clip_name or hand_player.current_animation != hand_clip_name:
        _fail("player not playing source clip at " + mode + str(frame_idx))
        return false
    hands_skeleton.force_update_all_bone_transforms()
    gun_skeleton.force_update_all_bone_transforms()
    weapon.call("_sync_source_weapon_attachment")

    # Camera-relative REAL BONE position, not expected transformed key values.
    var index: int = gun_skeleton.find_bone("j_clip")
    var clip_position_world: Vector3 = gun_skeleton.to_global(gun_skeleton.get_bone_global_pose(index).origin)
    var clip_position_camera: Vector3 = camera.to_local(clip_position_world)
    var clip_tip_world: Vector3 = gun_skeleton.to_global(
        gun_skeleton.get_bone_global_pose(index) * Vector3(0.0, -0.15, 0.0))
    # Real source-skin finger distances, not per-frame screenshot guesses.
    for hand_bone: String in ["j_wrist_le", "j_ringpalm_le", "j_thumb_le_1",
                            "j_wrist_ri", "j_ringpalm_ri"]:
        var hand_bone_id: int = hands_skeleton.find_bone(hand_bone)
        if hand_bone_id < 0:
            _fail("source hands joint missing " + hand_bone)
            return false
        var point_world: Vector3 = hands_skeleton.to_global(
            hands_skeleton.get_bone_global_pose(hand_bone_id).origin)
        print("MP40_CLIP_HAND_DISTANCE mode=", mode, " step=", frame_idx,
            " joint=", hand_bone,
            " root_distance_m=", snappedf(point_world.distance_to(clip_position_world), 0.0001),
            " clip_tip_distance_m=", snappedf(point_world.distance_to(clip_tip_world), 0.0001),
            " hand_screen=", camera.unproject_position(point_world))
    (_positions[mode] as Array).append(clip_position_camera)
    var clip_screen: Vector2 = camera.unproject_position(clip_position_world)
    var rect_size: Vector2 = camera.get_viewport().get_visible_rect().size
    if frame_idx == 2:
        var out_of_view := (clip_screen.x < 0.0 or clip_screen.x > rect_size.x
            or clip_screen.y < 0.0 or clip_screen.y > rect_size.y
            or camera.is_position_behind(clip_position_world))
        _offscreen_critical[mode] = out_of_view
        print("MP40_CRITICAL_MAGAZINE_SCREEN mode=", mode, " frame=34%",
            " xy=", clip_screen, " window=", rect_size, " offscreen=", out_of_view)
    var gun_root: Node3D = weapon.get("_weapon_model_root") as Node3D
    var hand_root: Node3D = weapon.get("_hands_model_root") as Node3D
    var barrel_local_camera: Vector3 = camera.global_transform.basis.orthonormalized().inverse() * gun_root.global_transform.basis.orthonormalized() * Vector3.RIGHT
    label.text = "MP40 • " + mode + " • " + str(frame_idx + 1) + "/6  (" + str(roundf(fraction * 100.0)) + "%)"
    print("MP40_ACTUAL_FRAME",
        " mode=", mode, " step=", frame_idx,
        " gun_time=", gun_t, " hands_time=", hand_t,
        " camera_clip=", clip_position_camera, " screen_clip=", clip_screen,
        " gun_root_cam=", camera.to_local(gun_root.global_position),
        " hand_root_cam=", camera.to_local(hand_root.global_position),
        " barrel_forward=", barrel_local_camera,
        " gun_clip=", gun_player.current_animation,
        " hand_clip=", hand_player.current_animation)
    for wait_idx in range(3):
        await process_frame
    var shot: Image = root.get_texture().get_image()
    if shot == null or shot.get_width() < 1200:
        _fail("no rendered camera image at " + mode + str(frame_idx))
        return false
    var save_path: String = "res://mp40-real-" + mode + "-" + str(frame_idx + 1).pad_zeros(2) + ".png"
    if shot.save_png(ProjectSettings.globalize_path(save_path)) != OK:
        _fail("failed to save " + save_path)
        return false
    print("MP40_RUNTIME_FRAME_SAVED path=", save_path)
    return true

func _run() -> void:
    var scene: Node3D = BLACK_PINES.instantiate() as Node3D
    if scene == null:
        _fail("Black Pines not loaded")
        return
    scene.set("rounds_enabled", false)
    scene.set("preview_no_enemies", true)
    # Original map's geometry is not the test subject; force fallback to
    # avoid a giant Blender artifact download. Gameplay and gun are identical.
    scene.set("prefer_blender_geometry", false)
    root.add_child(scene)
    for i in range(6):
        await process_frame

    var weapon: Node = scene.get_node_or_null("Player/Weapon")
    var camera: Camera3D = scene.get_node_or_null("Player/Head/Camera3D") as Camera3D
    if weapon == null or camera == null:
        _fail("live Player/Weapon/Camera3D missing")
        return
    if not bool(weapon.call("equip_weapon", "mp40", true)):
        _fail("real MP40 failed equip")
        return
    # Experiment ONLY: compare the REAL imported MP40 mesh/anim rotation
    # around its source +X longitudinal barrel axis, leaving authored T4 hand
    # skeleton and timestamps untouched. This is not yet a production fix.
    var roll_arg: float = 0.0
    for argument: String in OS.get_cmdline_user_args():
        if argument.begins_with("--mp40-source-roll="):
            roll_arg = float(argument.trim_prefix("--mp40-source-roll="))
    var experimental_gun_root: Node3D = weapon.get("_weapon_model_root") as Node3D
    if experimental_gun_root == null:
        _fail("missing gun root for roll matrix")
        return
    experimental_gun_root.quaternion = (
        experimental_gun_root.quaternion * Quaternion(Vector3.RIGHT, deg_to_rad(roll_arg))
    ).normalized()
    weapon.set_meta("mp40_experiment_roll_deg", roll_arg)
    print("MP40_SOURCE_MESH_ROLL_EXPERIMENT_DEGREES=", roll_arg)

    var gun_player: AnimationPlayer = weapon.get("_asset_animation_player") as AnimationPlayer
    var hand_player: AnimationPlayer = weapon.get("_hands_animation_player") as AnimationPlayer
    var gun_root: Node3D = weapon.get("_weapon_model_root") as Node3D
    var hands_skeleton: Skeleton3D = weapon.get("_source_hands_skeleton") as Skeleton3D
    if gun_player == null or hand_player == null or gun_root == null or hands_skeleton == null:
        _fail("source gun / hands / animation players missing")
        return
    var gun_skeleton: Skeleton3D = _find_mag_skeleton(gun_root)
    if gun_skeleton == null:
        _fail("real MP40 j_clip skeleton missing")
        return
    if not gun_root.is_visible_in_tree():
        _fail("MP40 model not visible")
        return

    var hud: CanvasLayer = scene.get_node_or_null("HUD") as CanvasLayer
    if hud != null:
        hud.visible = false # diagnostic images only; production HUD untouched
    var overlay := CanvasLayer.new()
    overlay.layer = 20
    scene.add_child(overlay)
    var label := Label.new()
    label.add_theme_font_size_override("font_size", 28)
    label.position = Vector2(30.0, 24.0)
    overlay.add_child(label)

    # Render in live Godot while sample time is manually driven; never
    # pause() a player whose current_animation must remain selected.
    gun_player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
    hand_player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
    weapon.set_process(false)
    var player: Node = scene.get_node_or_null("Player")
    if player != null:
        player.set_process(false)
        player.set_physics_process(false)
    for mode in ["tactical", "empty"]:
        weapon.call("_finish_reload")
        weapon.set("_magazine", 10 if mode == "tactical" else 0)
        weapon.call("request_reload")
        if not bool(weapon.get("_reloading")):
            _fail(mode + " reload never started")
            return
        if gun_player.current_animation != ("PSA_viewmodel_mp40_reload" if mode == "tactical" else "PSA_viewmodel_mp40_reload_empty"):
            _fail(mode + " chose wrong gun animation")
            return
        var expected_hands := "PSA_MP40ReloadHands" if mode == "tactical" else "PSA_viewmodel_mp40_reload_empty"
        if hand_player.current_animation != expected_hands:
            _fail(mode + " wrong hand animation: " + str(hand_player.current_animation))
            return
        if int(weapon.get_meta("mp40_hands_reload_tag_weapon_keys", -1)) < 50:
            _fail(mode + " source tag_weapon keys missing")
            return
        print("MP40_SOURCE_CORRECT_PAIRED_RELOAD mode=", mode,
            " gun_duration=", gun_player.current_animation_length,
            " hands_duration=", hand_player.current_animation_length,
            " keys=", weapon.get_meta("mp40_hands_reload_tag_weapon_keys", 0))
        print("MP40_REAL_FRAME_CASE mode=", mode, " gun=", gun_player.current_animation, " hands=", hand_player.current_animation)
        for idx in range(FRACTIONS.size()):
            if not await _capture_frame(gun_player, hand_player, hands_skeleton, gun_skeleton, weapon, camera, label, mode, idx, float(FRACTIONS[idx])):
                return
        var positions: Array = _positions[mode] as Array
        var first: Vector3 = positions[0] as Vector3
        var max_movement := 0.0
        for point: Vector3 in positions:
            max_movement = maxf(max_movement, first.distance_to(point))
        print("MP40_RENDERED_MAGAZINE_CAMERA_MOVEMENT mode=", mode, " max_m=", max_movement)
        if max_movement < 0.12:
            _fail(mode + " static magazine / false animation: camera motion only " + str(max_movement))
            return
    print("MP40_RUNTIME_FRAMES_CAPTURED_12 visual_approval=REQUIRED actual_godot=true new_apk=false")
    if bool(_offscreen_critical["tactical"]) or bool(_offscreen_critical["empty"]):
        print("MP40_ROLL_EXPERIMENT_VISUAL_RED_AWARE tactical=", _offscreen_critical["tactical"],
            " empty=", _offscreen_critical["empty"]) # matrix needs all variants
    scene.queue_free()
    await process_frame
    quit(0)
