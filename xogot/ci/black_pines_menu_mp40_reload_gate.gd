extends SceneTree
# Godot Android Black Pines UI/MP40 source-data acceptance. Not an NZ:P test.
const BLACK_PINES := preload("res://black_pines.tscn")

func _init() -> void:
    call_deferred("_run")

func _check(ok: bool, message: String) -> bool:
    if ok:
        return true
    push_error("BLACK_PINES_MENU_MP40_RED " + message)
    quit(74)
    return false

func _run() -> void:
    var scene: Node3D = BLACK_PINES.instantiate() as Node3D
    if not _check(scene != null, "Black Pines scene missing"):
        return
    scene.set("rounds_enabled", false)
    scene.set("preview_no_enemies", true)
    scene.set("prefer_blender_geometry", false)
    root.add_child(scene)
    await process_frame
    var menu: Control = scene.get_node("HUD/MobileSettings") as Control
    var player: Node = scene.get_node("Player")
    var weapon: Node = scene.get_node("Player/Weapon")
    if not _check(menu != null and player != null and weapon != null, "gameplay/menu missing"):
        return
    menu.call("open_pause_menu")
    if not _check(menu.visible and bool(paused) and str(menu.get("_current_page")) == "pause", "PAUSE doesn't suspend gameplay"):
        return
    var pages: Control = menu.get_node("PausePanel/MenuColumn/Pages") as Control
    var nav: HBoxContainer = menu.get_node("PausePanel/MenuColumn/StickyNavigation") as HBoxContainer
    if not _check(pages != null and nav != null and nav.get_node_or_null("GlobalBack") != null and nav.get_node_or_null("GlobalResume") != null, "sticky nav missing"):
        return
    var devscroll: ScrollContainer = pages.get_node("DevPageScroll") as ScrollContainer
    if not _check(devscroll != null and devscroll.horizontal_scroll_mode == ScrollContainer.SCROLL_MODE_DISABLED and devscroll.vertical_scroll_mode == ScrollContainer.SCROLL_MODE_SHOW_ALWAYS, "DEV scroll not mobile touch-safe"):
        return
    menu.call("_show_page", "dev")
    await process_frame
    if not _check(str(menu.get("_current_page")) == "dev" and devscroll.visible, "DEV not visible"):
        return
    # Simulate an Android BACK key while the game is paused.
    var back := InputEventKey.new()
    back.keycode = KEY_BACK
    back.pressed = true
    menu.call("_input", back)
    if not _check(menu.visible and str(menu.get("_current_page")) == "pause", "Android BACK did not leave DEV for PAUSE"):
        return
    menu.call("_show_page", "settings")
    menu.call("_back_navigation")
    if not _check(str(menu.get("_current_page")) == "pause", "sticky BACK did not return to PAUSE"):
        return
    menu.call("_show_page", "network")
    menu.call("_back_navigation")
    if not _check(str(menu.get("_current_page")) == "pause", "network BACK did not return to PAUSE"):
        return
    menu.call("_back_navigation")
    if not _check(not menu.visible and not paused, "BACK did not resume gameplay"):
        return
    # Previously an active fire finger stayed held through the pause menu.
    player.call("_set_mobile_trigger_held", true)
    menu.call("open_pause_menu")
    if not _check(not bool(weapon.get("_trigger_held")), "fire remained held in menu"):
        return
    menu.call("close_menu")
    print("BLACK_PINES_MENU_ANDROID_BACK_GREEN dev_to_pause=true back_to_game=true sticky_nav=true scroll=true no_touch_leak=true")

    if not _check(bool(weapon.call("equip_weapon", "mp40", true)), "source MP40 failed to equip"):
        return
    var animation_player: AnimationPlayer = weapon.get("_asset_animation_player") as AnimationPlayer
    if not _check(animation_player != null, "MP40 has no gun AnimationPlayer"):
        return
    var reload_name: String = str(weapon.call("get", "_weapon_id"))
    if not _check(animation_player.has_animation("PSA_viewmodel_mp40_reload") and animation_player.has_animation("PSA_viewmodel_mp40_reload_empty"), "real MP40 80/102-frame clips missing"):
        return
    var anim: Animation = animation_player.get_animation("PSA_viewmodel_mp40_reload")
    var last: Animation = animation_player.get_animation("PSA_viewmodel_mp40_reload_empty")
    if not _check(anim.length > 3.2 and last.length > 4.1, "authored magazine clips were truncated"):
        return

    # Real source render proved a +90 LOCAL BARREL roll, composed after the
    # animated socket conversion, is needed to mount the physical MP40
    # magazine on the camera LEFT. The preceding gate's DOWN+LEFT static
    # assumptions were incompatible with a source gun held canted for reload.
    # This ONLY proves the intended mount; actual animated screen displacement
    # and hand contact are checked by black_pines_mp40_real_frame_audit.gd.
    var gun_root: Node3D = weapon.get("_weapon_model_root") as Node3D
    var view_root: Node3D = weapon.get("_view_root") as Node3D
    if not _check(gun_root != null and view_root != null, "source camera gun mounting nodes missing"):
        return
    var gun_basis: Basis = view_root.global_transform.basis.orthonormalized().inverse() * gun_root.global_transform.basis.orthonormalized()
    var barrel_forward: Vector3 = gun_basis * Vector3.RIGHT
    var magazine_left: Vector3 = gun_basis * Vector3.DOWN
    print("BLACK_PINES_MP40_SOURCE_LEFT_MOUNT barrel=", barrel_forward, " magazine=", magazine_left)
    if not _check(barrel_forward.z < -0.80, "MP40 barrel not pointing forward"):
        return
    if not _check(magazine_left.x < -0.80, "MP40 still has RIGHT-side instead of left magazine"):
        return
    if not _check(str(weapon.get_meta("weapon_source_mp40_mount_mode", "")) == "original_t4_hands_left_roll_90_beta", "MP40 visual source mount mode not selected"):
        return
    var clip_moving: bool = false
    for a in [anim, last]:
        var present: bool = false
        for track: int in range(a.get_track_count()):
            if a.track_get_type(track) != Animation.TYPE_POSITION_3D:
                continue
            if not str(a.track_get_path(track)).to_lower().contains("j_clip"):
                continue
            var count: int = a.track_get_key_count(track)
            if not _check(count > 20, "j_clip has only a static 2-frame placeholder"):
                return
            var first: Vector3 = a.track_get_key_value(track, 0)
            var finish: Vector3 = a.track_get_key_value(track, count - 1)
            var max_removal_m: float = 0.0
            var peak_displacement_view := Vector3.ZERO
            for frame in range(count):
                var sample: Vector3 = a.track_get_key_value(track, frame)
                var displacement_view: Vector3 = gun_basis * (sample - first)
                if displacement_view.length() > max_removal_m:
                    max_removal_m = displacement_view.length()
                    peak_displacement_view = displacement_view
            # Reject static data here. Authored root/socket motion changes the
            # camera direction per frame, so a static local track direction is
            # NOT proof of actual LEFT extraction. The native camera-frame
            # gauntlet checks it with real skinning and hand contact.
            print("BLACK_PINES_MP40_SOURCE_CLIP_DELTA animation=", a.resource_name,
                " displacement=", peak_displacement_view)
            if not _check(first.distance_to(finish) < 0.03, "magazine never fully returns to the gun"):
                return
            # Empty reload's clip is still halfway engaged at middle frame.
            # Check the whole animation, not just its temporal midpoint.
            if not _check(max_removal_m > 0.10 and first.length() < 2.0, "magazine has no realistic authored removal in meters"):
                return
            present = true
            clip_moving = true
            print("BLACK_PINES_MP40_MAGAZINE_TRACK_GREEN animation=", a.resource_name, " frames=", count, " max_removal_m=", max_removal_m)
        if not _check(present, "real MP40 reload clip has no j_clip positional track"):
            return
    if not _check(clip_moving, "magazine has no moving track"):
        return

    var hands_player: AnimationPlayer = weapon.get("_hands_animation_player") as AnimationPlayer
    if not _check(hands_player != null, "MP40 real hands animation player missing"):
        return
    if not _check(hands_player.has_animation("PSA_MP40ReloadHands") and hands_player.has_animation("PSA_viewmodel_mp40_reload_empty"), "source normal AND empty hands clip missing"):
        return
    var tactical_hands: Animation = hands_player.get_animation("PSA_MP40ReloadHands")
    var empty_hands: Animation = hands_player.get_animation("PSA_viewmodel_mp40_reload_empty")
    if not _check(tactical_hands.length > 3.0 and tactical_hands.length < 3.5 and tactical_hands.get_track_count() > 50, "true source normal MP40ReloadHands is not full 3.25s"):
        return
    if not _check(empty_hands.length > 4.0 and empty_hands.length < 4.5 and empty_hands.get_track_count() > 50, "true source empty MP40 hands reload not found"):
        return
    print("BLACK_PINES_MP40_ORIGINAL_TACTICAL_HANDS length=", tactical_hands.length, " tracks=", tactical_hands.get_track_count())
    print("BLACK_PINES_MP40_ORIGINAL_EMPTY_HANDS length=", empty_hands.length, " tracks=", empty_hands.get_track_count())
    weapon.set("_magazine", 10)
    weapon.call("request_reload")
    if not _check(str(animation_player.current_animation) == "PSA_viewmodel_mp40_reload", "wrong gun tactical reload"):
        return
    if not _check(str(hands_player.current_animation) == "PSA_MP40ReloadHands", "NORMAL reload incorrectly borrowed EMPTY source hands"):
        return
    if not _check(int(weapon.get_meta("mp40_hands_reload_tag_weapon_keys", 0)) > 50, "normal source tag_weapon motion is STATIC"):
        return
    if not _check(absf(hands_player.speed_scale * float(weapon.get("_reload_timer")) - tactical_hands.length) < 0.10, "tactical source gun/hands are out of sync"):
        return
    if not _check(float(weapon.get("_reload_timer")) >= anim.length - 0.1, "gameplay timer ends before normal magazine returns"):
        return
    weapon.call("_finish_reload")
    weapon.set("_magazine", 0)
    weapon.call("request_reload")
    if not _check(str(animation_player.current_animation) == "PSA_viewmodel_mp40_reload_empty", "wrong empty gun clip"):
        return
    if not _check(str(hands_player.current_animation) == "PSA_viewmodel_mp40_reload_empty", "empty reload chose wrong original hands"):
        return
    if not _check(int(weapon.get_meta("mp40_hands_reload_tag_weapon_keys", 0)) > 50, "empty source tag_weapon motion is STATIC"):
        return
    if not _check(absf(hands_player.speed_scale * float(weapon.get("_reload_timer")) - empty_hands.length) < 0.10, "empty source gun/hands playback out of sync"):
        return
    if not _check(float(weapon.get("_reload_timer")) >= last.length - 0.1, "empty gun reload ends too early"):
        return
    print("BLACK_PINES_MP40_FULL_RELOAD_GREEN both_original_hands=true normal=3.25s empty=4.21s visual_fidelity_still_unverified=true")
    weapon.call("_finish_reload")
    scene.queue_free()
    await process_frame
    quit(0)
