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
            var middle: Vector3 = a.track_get_key_value(track, count / 2)
            var finish: Vector3 = a.track_get_key_value(track, count-1)
            if not _check(first.distance_to(finish) < 0.03, "magazine never fully returns to the gun"):
                return
            if not _check(first.distance_to(middle) > 0.10 and first.length() < 2.0, "magazine has no realistic authored removal in meters"):
                return
            present = true
            clip_moving = true
            print("BLACK_PINES_MP40_MAGAZINE_TRACK_GREEN animation=", a.resource_name, " frames=", count, " delta_m=", first.distance_to(middle))
        if not _check(present, "real MP40 reload clip has no j_clip positional track"):
            return
    if not _check(clip_moving, "magazine has no moving track"):
        return

    weapon.set("_magazine", 10)
    weapon.call("request_reload")
    if not _check(str(animation_player.current_animation) == "PSA_viewmodel_mp40_reload", "wrong gun reload clip selected (hands placeholder)"):
        return
    if not _check(float(weapon.get("_reload_timer")) >= anim.length - 0.1, "gameplay timer ends before magazine returns"):
        return
    weapon.call("_finish_reload")
    weapon.set("_magazine", 0)
    weapon.call("request_reload")
    if not _check(str(animation_player.current_animation) == "PSA_viewmodel_mp40_reload_empty", "wrong empty-mag reload clip selected"):
        return
    if not _check(float(weapon.get("_reload_timer")) >= last.length - 0.1, "empty-magazine reload cut short"):
        return
    print("BLACK_PINES_MP40_FULL_RELOAD_GREEN gun_reinsert=true authored_mag_motion=true mag_empty=true reload_time_synced=true")
    weapon.call("_finish_reload")
    scene.queue_free()
    await process_frame
    quit(0)
