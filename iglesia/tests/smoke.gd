extends SceneTree
## Real Godot headless scene smoke. Does not claim GPU or phone visual validation.
func _initialize() -> void:
    call_deferred("_run")

func _run() -> void:
    var errors: Array[String] = []
    var packed = load("res://scenes/iglesia.tscn")
    if not (packed is PackedScene):
        push_error("IGLESIA_SCENE_NOT_IMPORTABLE")
        quit(1)
        return
    var game = packed.instantiate()
    root.add_child(game)
    await process_frame
    await physics_frame
    if game.level == null or game.player == null or game.hud == null:
        errors.append("MISSING_CORE_RUNTIME")
    else:
        if game.level.debug_missing_art:
            errors.append("APPROVED_GLBS_NOT_IMPORTED")
        var pew_colliders := 0
        for child in game.level.get_children():
            if child.name.begins_with("PewSolidCollision_"):
                pew_colliders += 1
        if pew_colliders != 14:
            errors.append("PEW_COLLISION_COUNT %d/14" % pew_colliders)
        if not game.level.has_node("AltarCollisionNoWalkThrough"):
            errors.append("ALTAR_NO_COLLISION")
        var altar_art = game.level.get_node_or_null("ApprovedTripoAltar")
        var altar_proxy = game.level.get_node_or_null("AltarCollisionNoWalkThrough")
        if altar_art == null:
            errors.append("ALTAR_ORIGINAL_ASSET_MISSING")
        else:
            # Source is permitted art only, no synthetic replacement.
            # Godot forward = -Z; yaw 180 points the altar's front toward
            # the player's +Z main aisle rather than the rear stone wall.
            var altar_direction: Vector3 = (altar_art as Node3D).global_basis * Vector3.FORWARD
            if altar_direction.z < 0.98:
                errors.append("ALTAR_FACE_NOT_TOWARD_MAIN_AISLE")
            var bounds: AABB = game.level._scene_bounds(altar_art)
            if bounds.size.length() < 0.001:
                errors.append("ALTAR_BOUNDING_BOX_MISSING")
            else:
                var y_floor: float = (altar_art as Node3D).position.y + bounds.position.y * (altar_art as Node3D).scale.y
                if absf(y_floor - 0.51) > 0.075:
                    errors.append("ALTAR_FLOOR_CONTACT_WRONG")
        if altar_proxy != null:
            # Procedurally created CollisionShape3D nodes have Godot-generated
            # unique names; resolve by class, NOT by a guessed node path.
            var colliders: Array[Node] = altar_proxy.find_children("*", "CollisionShape3D", false, false)
            if colliders.is_empty() or not ((colliders[0] as CollisionShape3D).shape is BoxShape3D):
                errors.append("ALTAR_COLLIDER_SHAPE_MISSING")
            elif absf(((colliders[0] as CollisionShape3D).shape as BoxShape3D).size.x - 4.1) > 0.02:
                errors.append("ALTAR_COLLIDER_NOT_RESIZED")
        var nav_path = game.level.nav.get_id_path(
            game.level.world_to_cell(Vector3(-7.0, 0.0, 10.0)),
            game.level.world_to_cell(Vector3(0.0, 0.0, -10.0)))
        if nav_path.size() < 5:
            errors.append("ZOMBIE_NAV_NO_CROSSING")
        for pt in nav_path:
            if game.level.nav.is_point_solid(pt):
                errors.append("ZOMBIE_NAV_INTERSECTS_PEW")
                break

        var fixture_catalog := "res://assets/tripo/fixtures_catalog.json"
        if not FileAccess.file_exists(fixture_catalog):
            errors.append("TRIPO_FIXTURE_CATALOG_MISSING")
        else:
            var fixture_inventory = JSON.parse_string(FileAccess.get_file_as_string(fixture_catalog))
            if not (fixture_inventory is Dictionary):
                errors.append("TRIPO_FIXTURE_CATALOG_INVALID")
            else:
                var staged_fixtures: int = int(fixture_inventory.get("fixture_count", 0))
                var in_world: int = get_nodes_in_group("iglesia_tripo_fixture").size()
                if staged_fixtures != in_world:
                    errors.append("TRIPO_FIXTURE_COUNT_RED %d/%d" % [in_world, staged_fixtures])
                var recovered_count: int = int(fixture_inventory.get("original_split_model_count", 0))
                var firstroom_preview: bool = bool(fixture_inventory.get("firstroom_preview", false))
                if recovered_count != 0 and recovered_count != 104 and not (firstroom_preview and recovered_count == 30):
                    errors.append("ORIGINAL_TRIPO_SOURCE_CENSUS_INVALID")
                if recovered_count == 104 or (firstroom_preview and recovered_count == 30):
                    if staged_fixtures != 10:
                        errors.append("ORIGINAL_TRIPO_FIXTURE_STAGING_INCOMPLETE")
                    var practicals := 0
                    for obj in game.level.get_children():
                        if obj.name.begins_with("SourceTripoLight_"):
                            practicals += 1
                    if practicals != 4:
                        errors.append("ORIGINAL_TRIPO_PRACTICAL_LIGHT_RED %d/4" % practicals)
                if staged_fixtures == 0:
                    print("TRIPO_ORIGINALS_FOUND_IN_LIBRARY_NOT_YET_IN_REPOSITORY; NO_SYNTHETIC_CHANDELIERS")

        var perf_probe = game.get_node_or_null("MobilePerformanceTelemetry")
        if perf_probe == null:
            errors.append("PERFORMANCE_TELEMETRY_NOT_INSTALLED")
        # Authored Nun source viewmodel: original MP40 model and the original
        # 113-bone hands must actually instantiate and be animated. Never
        # consider the old nine PNG files a substitute for this gate.
        var rig = game.player.nun_viewmodel
        if rig == null:
            errors.append("NUN_MP40_CAMERA_RIG_MISSING")
        elif not rig.source_ready:
            errors.append("NUN_MP40_REAL_SOURCE_RIG_NOT_READY")
        else:
            if rig.gun == null or rig.hands == null:
                errors.append("NUN_MP40_GUN_OR_SKINNED_HANDS_MISSING")
            if rig.gun_animation == null or rig.hands_animation == null:
                errors.append("NUN_MP40_AUTHORED_ANIMATIONS_MISSING")
            if rig.style_surface_roles.is_empty():
                errors.append("NUN_HAND_SKIN_MATERIALS_NOT_BOUND")
            if rig.last_role != "idle":
                errors.append("NUN_MP40_IDLE_CLIP_NOT_SET")
            rig._switch_animation("fire")
            if rig.last_role != "fire":
                errors.append("NUN_MP40_AUTHORED_FIRE_CLIP_NOT_PLAYING")
            rig._switch_animation("reload")
            if rig.last_role != "reload":
                errors.append("NUN_MP40_AUTHORED_RELOAD_CLIP_NOT_PLAYING")
            rig._switch_animation("idle")
            if rig.last_role != "idle":
                errors.append("NUN_MP40_IDLE_CLIP_NOT_RESUMED")
            # HUD must not draw old mixed realistic/pixel pictures when this
            # new source rig is ready. Deferred process lets HUD update it.
            await process_frame
            if game.hud.weapon.visible:
                errors.append("REJECTED_MP40_SPRITES_VISIBLE_OVER_NEW_NUN_RIG")
        if game.hud.mp40_frames.size() != 9:
            errors.append("MP40_SOURCE_FRAMES_NOT_9")
        if game.hud.buttons.size() < 6:
            errors.append("TOUCH_HUD_INCOMPLETE")
        for action in ["fire", "ads", "reload", "jump", "slide", "interact"]:
            if not game.hud.buttons.has(action):
                errors.append("TOUCH_ACTION_BUTTON_MISSING_" + action)
                continue
            var touch_button = game.hud.buttons[action]
            if not (touch_button is TextureButton):
                errors.append("TOUCH_BUTTON_NOT_TEXTURE_BUTTON_" + action)
                continue
            if touch_button.texture_normal == null:
                errors.append("TOUCH_OFFICIAL_ART_MISSING_" + action)
            var desired_filter: int = Control.MOUSE_FILTER_IGNORE if OS.has_feature("mobile") else Control.MOUSE_FILTER_STOP
            if not touch_button.visible or touch_button.mouse_filter != desired_filter:
                errors.append("TOUCH_BUTTON_RENDER_OR_INPUT_FILTER_BAD_" + action)
        for dims in [Vector2(1280, 720), Vector2(2340, 1080), Vector2(1920, 1440), Vector2(960, 540)]:
            game.hud._layout(dims)
            var fire_btn: Control = game.hud.buttons["fire"]
            var ads_btn: Control = game.hud.buttons["ads"]
            for action in ["fire", "ads"]:
                var hitbox: Rect2 = game.hud.buttons[action].get_rect()
                if hitbox.position.x < 0 or hitbox.position.y < 0 or hitbox.end.x > dims.x or hitbox.end.y > dims.y:
                    errors.append("TOUCH_BUTTON_OUTSIDE_SCREEN_%s_%s" % [action, str(dims)])
            if fire_btn.get_rect().intersects(ads_btn.get_rect()):
                errors.append("FIRE_ADS_TOUCH_TARGET_OVERLAP_" + str(dims))
        game.hud._layout()
        # Touch ID routing is tested independent of OS.has_feature("mobile"),
        # including simultaneous FIRE+ADS and release outside original hitbox.
        var fire_touch: Vector2 = game.hud.buttons["fire"].get_global_rect().get_center()
        var ads_touch: Vector2 = game.hud.buttons["ads"].get_global_rect().get_center()
        Input.action_release("fire")
        Input.action_release("ads")
        if game.hud._touch_button_at(Vector2(40, 130)) != "":
            errors.append("EMPTY_SCREEN_TOUCH_CAPTURED_BY_A_BUTTON")
        var bullets_before: int = game.player.magazine
        if not game.hud._route_touch_button(11, true, fire_touch):
            errors.append("NATIVE_FIRE_TOUCH_NOT_CAPTURED")
        if not Input.is_action_pressed("fire"):
            errors.append("NATIVE_FIRE_ACTION_NOT_PRESSED")
        game.player.ads_toggle_mode = false
        if not game.hud._route_touch_button(12, true, ads_touch):
            errors.append("NATIVE_ADS_TOUCH_NOT_CAPTURED")
        if not Input.is_action_pressed("ads"):
            errors.append("NATIVE_ADS_ACTION_NOT_PRESSED")
        if game.hud.touch_actions.size() != 2:
            errors.append("FIRE_ADS_MULTITOUCH_NOT_INDEPENDENT")
        game.hud._route_touch_button(11, false, Vector2.ZERO)
        if Input.is_action_pressed("fire") or not Input.is_action_pressed("ads"):
            errors.append("FIRE_RELEASE_CANCELS_ADS_OR_STICKS")
        game.hud._route_touch_button(12, false, Vector2.ZERO)
        if Input.is_action_pressed("ads") or not game.hud.touch_actions.is_empty():
            errors.append("ADS_TOUCH_RELEASE_STUCK")
        if game.player.magazine != bullets_before:
            errors.append("TOUCH_ROUTING_FIRES_BEFORE_PHYSICS")
        game.player.ads_toggle_mode = true
        for action in ["fire", "ads"]:
            if not game.hud.label_badges.has(action) or not game.hud.label_badges[action].visible:
                errors.append("MISSING_PERSISTENT_ACTION_LABEL_" + action)
        # A tap on empty space must not activate the MP40's mapped mouse fire.
        if bool(ProjectSettings.get_setting("input_devices/pointing/emulate_mouse_from_touch", true)):
            errors.append("TOUCH_EMULATES_MOUSE_FIRE_REGRESSION")
        Input.action_release("fire")
        Input.action_release("ads")
        game.hud._press_action("fire")
        if not Input.is_action_pressed("fire"):
            errors.append("FIRE_TOUCH_PRESS_DOES_NOT_FIRE")
        game.hud._release_action("fire")
        if Input.is_action_pressed("fire"):
            errors.append("FIRE_TOUCH_RELEASE_STUCK")
        game.player.ads_toggle_mode = false
        game.hud._press_action("ads")
        if not Input.is_action_pressed("ads"):
            errors.append("ADS_TOUCH_PRESS_DOES_NOT_AIM")
        game.hud._release_action("ads")
        if Input.is_action_pressed("ads"):
            errors.append("ADS_TOUCH_RELEASE_STUCK")
        game.player.ads_toggle_mode = true
        for node in get_nodes_in_group("iglesia_tripo_fixture"):
            if str(node.get_meta("fixture_kind", node.get_meta("anchor_kind", ""))) == "standing_candelabrum" or str(node.name).begins_with("ApprovedTripo_standing_candelabrum"):
                var geometry = game.level._scene_bounds(node)
                var size_y: float = geometry.size.y * (node as Node3D).scale.y
                if size_y > 0.94:
                    errors.append("FLOOR_TRIPLE_CUP_CANDLEHOLDER_TOO_BIG " + str(size_y))
                var bottom: float = (node as Node3D).position.y + geometry.position.y * (node as Node3D).scale.y
                if absf(bottom - 0.02) > 0.06:
                    errors.append("FLOOR_CANDLEHOLDER_NOT_GROUNDED " + str(bottom))
        if not game.player.camera.current:
            errors.append("FPS_CAMERA_MISSING")
        if game.round_number != 1 or game.round_remaining < 5:
            errors.append("ROUND_DIRECTOR_FAILED")
        if game.player.reload_seconds <= 0.0:
            errors.append("RELOAD_TIMER_FAILED")
    if errors.is_empty():
        print("IGLESIA_HEADLESS_SMOKE_GREEN: nav/pews/altar/hud/mp40/rounds")
        quit(0)
    else:
        for err in errors:
            push_error("IGLESIA_HEADLESS_SMOKE_RED: " + err)
        quit(1)
