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
                if recovered_count != 0 and recovered_count != 104:
                    errors.append("ORIGINAL_TRIPO_SPLIT_104_INCOMPLETE")
                if recovered_count == 104 and staged_fixtures < 8:
                    errors.append("ORIGINAL_TRIPO_FIXTURE_STAGING_INCOMPLETE")
                if staged_fixtures == 0:
                    print("TRIPO_ORIGINALS_FOUND_IN_LIBRARY_NOT_YET_IN_REPOSITORY; NO_SYNTHETIC_CHANDELIERS")

        if game.hud.mp40_frames.size() != 9:
            errors.append("MP40_SOURCE_FRAMES_NOT_9")
        if game.hud.buttons.size() < 6:
            errors.append("TOUCH_HUD_INCOMPLETE")
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
