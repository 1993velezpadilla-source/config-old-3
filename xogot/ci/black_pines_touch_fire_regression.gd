extends SceneTree
# Touch-input regression for the existing Black Pines Godot APK, not NZ:P.
# A look/joystick touch cannot fire. Semi-auto weapons fire once per press.
const BLACK_PINES := preload("res://black_pines.tscn")
const MOBILE_LAYOUT := preload("res://scripts/mobile_layout.gd")

func _init() -> void:
    call_deferred("_run")

func _fail(message: String) -> void:
    push_error("BLACK_PINES_TOUCH_FIRE_RED " + message)
    quit(63)

func _tap(player: Node, index: int, position: Vector2, pressed: bool) -> void:
    var ev := InputEventScreenTouch.new()
    ev.index = index
    ev.position = position
    ev.pressed = pressed
    player.call("_handle_touch", ev)

func _run() -> void:
    # The Android-specific guard is otherwise unavailable in Linux headless CI.
    var weapon_source: String = FileAccess.get_file_as_string("res://scripts/weapon.gd")
    if not weapon_source.contains('if not OS.has_feature("mobile") and event is InputEventMouseButton'):
        _fail("touch-emulated mouse clicks are still global FIRE")
        return

    var scene: Node3D = BLACK_PINES.instantiate() as Node3D
    if scene == null:
        _fail("existing Black Pines scene cannot be instantiated")
        return
    scene.set("rounds_enabled", false)
    scene.set("preview_no_enemies", true)
    scene.set("prefer_blender_geometry", false)
    root.add_child(scene)
    await process_frame

    var player: Node = scene.get_node_or_null("Player")
    var weapon: Node = scene.get_node_or_null("Player/Weapon")
    var perk: Node = scene.get_node_or_null("Machines/Perk_martyrs_blood")
    if player == null or weapon == null or perk == null:
        _fail("existing gameplay nodes are missing")
        return
    var nameplate: Label3D = perk.get_node_or_null("Identification") as Label3D
    if nameplate == null or nameplate.position.y < 1.3:
        _fail("world label remains buried inside its solid machine")
        return

    if not bool(weapon.call("equip_weapon", "colt", true)):
        _fail("Colt is missing from original weapon catalog")
        return
    var size: Vector2 = player.get_viewport().get_visible_rect().size
    var look_at: Vector2 = Vector2(size.x * 0.49, size.y * 0.48)
    var fire_at: Vector2 = MOBILE_LAYOUT.screen_point(MOBILE_LAYOUT.FIRE_CENTER, size)
    var adsfire_at: Vector2 = MOBILE_LAYOUT.screen_point(MOBILE_LAYOUT.ADSFIRE_CENTER, size)
    var joy_at: Vector2 = MOBILE_LAYOUT.screen_point(MOBILE_LAYOUT.JOY_CENTER, size)
    var before: int = int(weapon.get("_shots_fired"))

    _tap(player, 3, look_at, true)
    await process_frame
    if int(weapon.get("_shots_fired")) != before or int(player.get("_look_touch")) != 3:
        _fail("looking around fired a shot")
        return
    _tap(player, 3, look_at, false)
    _tap(player, 4, joy_at, true)
    await process_frame
    if int(weapon.get("_shots_fired")) != before:
        _fail("joystick fired a shot")
        return
    _tap(player, 4, joy_at, false)

    _tap(player, 5, fire_at, true)
    await process_frame
    if int(weapon.get("_shots_fired")) != before + 1:
        _fail("FIRE button failed to fire exactly once")
        return
    await create_timer(0.24).timeout
    if int(weapon.get("_shots_fired")) != before + 1:
        _fail("holding FIRE converted semi-auto Colt to a machine gun")
        return
    _tap(player, 5, fire_at, false)

    # The ADS+FIRE button used to repeat the Colt every 0.05 s (1200 RPM).
    weapon.set("_ads_pose_alpha", 1.0)
    _tap(player, 6, adsfire_at, true)
    await process_frame
    if int(weapon.get("_shots_fired")) != before + 2:
        _fail("ADS+FIRE did not fire one Colt shot")
        return
    await create_timer(0.25).timeout
    if int(weapon.get("_shots_fired")) != before + 2:
        _fail("holding ADS+FIRE auto-repeated a semi-auto Colt")
        return
    _tap(player, 6, adsfire_at, false)

    if not bool(weapon.call("equip_weapon", "mp40", true)):
        _fail("original automatic MP40 is missing")
        return
    var auto_before: int = int(weapon.get("_shots_fired"))
    _tap(player, 7, fire_at, true)
    await create_timer(0.36).timeout
    _tap(player, 7, fire_at, false)
    if int(weapon.get("_shots_fired")) < auto_before + 2:
        _fail("source automatic MP40 was incorrectly converted to semi-auto")
        return

    print("BLACK_PINES_TOUCH_FIRE_GREEN look_safe=true joystick_safe=true mobile_mouse_blocked=true")
    print("BLACK_PINES_TOUCH_FIRE_GREEN colt_fire_single=true adsfire_single=true mp40_automatic_preserved=true")
    print("BLACK_PINES_HUD_LABEL_GREEN machine_text_not_buried=true")
    scene.queue_free()
    await process_frame
    quit(0)
