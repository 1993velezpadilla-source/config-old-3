extends SceneTree
## Actual Godot OpenGL frames from the same Black Pines Player/Weapon hierarchy.
## Do not call this GREEN just because a source bone's track points left.
## Save first-person renders, camera-space bone trajectories and names for
## independent review before a new APK is approved.
const BLACK_PINES := preload("res://black_pines.tscn")
const FRACTIONS := [0.02, 0.18, 0.34, 0.50, 0.68, 0.88]
var _positions: Dictionary = {"tactical": [], "empty": []}

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
    var hand_clip_name := "PSA_viewmodel_mp40_reload_empty"
    gun_player.play(gun_clip_name, 0.0)
    hand_player.play(hand_clip_name, 0.0)
    gun_player.seek(gun_t, true)
    hand_player.seek(hand_t, true)
    gun_player.advance(0.0)
    hand_player.advance(0.0)
    weapon.call("_mp40_retarget_motion_for_render")
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
    (_positions[mode] as Array).append(clip_position_camera)
    var clip_screen: Vector2 = camera.unproject_position(clip_position_world)
    var gun_root: Node3D = weapon.get("_weapon_model_root") as Node3D
    var hand_root: Node3D = weapon.get("_hands_model_root") as Node3D
    var barrel_local_camera: Vector3 = camera.global_transform.basis.orthonormalized().inverse() * gun_root.global_transform.basis.orthonormalized() * Vector3.RIGHT
    label.text = "MP40 EXPERIMENT MOTION-MIRROR • " + mode + " • " + str(frame_idx + 1) + "/6  (" + str(roundf(fraction * 100.0)) + "%)"
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
    weapon.set("mp40_reload_rig_retarget_mode", "mirror_reload_motion")
    if not bool(weapon.call("equip_weapon", "mp40", true)):
        _fail("real MP40 failed equip")
        return

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
    print("MP40_RUNTIME_FRAMES_CAPTURED_12 EXPERIMENT_MIRROR_RELOAD source_pose_preserved=true visual_approval=REQUIRED actual_godot=true new_apk=false")
    scene.queue_free()
    await process_frame
    quit(0)
