extends SceneTree
## Real Godot integration test: ORIGINAL church + 41 source GLBs.
## 23 real Xogot weapon IDs / 18 preview-only source parts.
## No fake shared MP40 gameplay for auxiliaries.

var errors: Array[String] = []


func _initialize() -> void:
    call_deferred("_test")


func _fail(message: String) -> void:
    errors.append(message)
    printerr("VRIL_ARSENAL_CHURCH_RED ", message)


func _test() -> void:
    var packed: PackedScene = load("res://vril_arsenal_church_test.tscn") as PackedScene
    if packed == null:
        _fail("Cannot load original church with 41 original selector")
        quit(1)
        return
    var game: Node = packed.instantiate()
    root.add_child(game)
    for _i in range(10):
        await process_frame
    var bridge: Node = game.get_node_or_null("Player/Head/Camera3D/Vril41OriginalWeaponBridge")
    var weapon: Node = game.get_node_or_null("Player/Weapon")
    if bridge == null or weapon == null or not bool(bridge.get("_bound")):
        _fail("Real church, source bridge or existing weapon not initialized")
        quit(1)
        return
    var previous_model: Node3D = weapon.get("_view_root") as Node3D
    if previous_model == null:
        _fail("Existing church gun render authority missing")
        quit(1)
        return
    if int(bridge.get_meta("source_count", -1)) != 41:
        _fail("Original 41 model inventory missing")
    if int(bridge.get_meta("gameplay_crossovers", -1)) != 23:
        _fail("All 23 independent verified Xogot runtime crossovers missing")
    if int(bridge.get_meta("preview_only_count", -1)) != 18:
        _fail("18 nonplayable component models falsely promoted")

    var entries: Array = bridge.get("_models")
    var main_count: int = 0
    var preview_count: int = 0
    var real_playable: Dictionary = {}
    for i in range(entries.size()):
        if not bool(bridge.call("_select_source", i)):
            _fail("Original MDL cannot load/switch source index " + str(i))
            break
        var entry: Dictionary = entries[i]
        var frame_count: int = int(entry.get("frames", 0))
        var model: Node3D = bridge.get("_model") as Node3D
        var animator: AnimationPlayer = bridge.get("_anim") as AnimationPlayer
        if model == null or animator == null:
            _fail("Real source rig/animation missing on " + str(entry.get("source", "")))
            break
        if frame_count <= 0 or frame_count != (bridge.get("_frame_names") as Array).size():
            _fail("Original MDL frame inventory corrupt")
        if previous_model.visible:
            _fail("Source MP40/other model double-draws with native gun")
        var gameplay_id: String = str(bridge.get("_current_gameplay_id"))
        var preview_only: bool = bool(bridge.get("_preview_only"))
        if preview_only:
            preview_count += 1
            if not gameplay_id.is_empty():
                _fail("Preview-only source falsely bound to gameplay")
        else:
            main_count += 1
            real_playable[gameplay_id] = true
            if str(weapon.get("_weapon_id")) != gameplay_id:
                _fail("Gun and source weapon ID differ at "+str(entry.get("source","")))
            if not bool(bridge.call("_play_role", "fire")):
                _fail("QuakeC source firing frames absent at "+str(entry.get("source","")))
        # Frame-audit every source against actual imported animation.
        var frames: Array = bridge.get("_frame_names")
        if str(frames[0]).is_empty():
            _fail("Empty original source animation frame name")
    if main_count != 23 or preview_count != 18:
        _fail("Inventory not exhaustively tested; %d gameplay %d preview" % [main_count, preview_count])
    if not real_playable.has("kar98k") or not real_playable.has("thompson"):
        _fail("Kar98k or Thompson real gameplay not connected")

    var start_index: int = -1
    for i in range(entries.size()):
        if str(entries[i].get("source","")) == "mp40/v_mp40.mdl":
            start_index = i
            break
    if start_index < 0 or not bool(bridge.call("_select_source",start_index)):
        _fail("MP40 original source not selectable")
    else:
        var roles: Dictionary = bridge.get("_roles")
        var original_fire: Array = roles.get("fire", [])
        var original_reload: Array = roles.get("reload", [])
        # JSON numeric entries may be parsed as float, so normalize before
        # comparing exact frame indices; never compare heterogeneous arrays.
        var fire_ok: bool = (original_fire.size() == 2 and
            int(original_fire[0]) == 1 and int(original_fire[1]) == 2)
        var reload_ok: bool = (original_reload.size() == 2 and
            int(original_reload[0]) == 4 and int(original_reload[1]) == 31)
        if not fire_ok or not reload_ok:
            _fail("Original QuakeC MP40 frames incorrect; fire=%s reload=%s" % [
                str(original_fire), str(original_reload)])
        if roles.has("sprint_out"):
            _fail("Invented out-of-bounds MP40 sprint-out frame 46")
        var shots_before: int = int(weapon.get("_shots_fired"))
        weapon.call("request_fire")
        await process_frame
        if int(weapon.get("_shots_fired")) <= shots_before:
            _fail("Original church MP40 hitfire/ammo pathway broken")
        if str(bridge.get("_playing_role")) != "fire":
            _fail("Source MP40 did not animate firing in gameplay")
        weapon.call("request_reload")
        await process_frame
        if not bool(weapon.get("_reloading")):
            _fail("Existing gameplay reload lost")
        if str(bridge.get("_playing_role")) != "reload":
            _fail("Source original MP40 reload did not play")
    game.queue_free()
    await process_frame
    if errors.is_empty():
        print("VRIL_ARSENAL_CHURCH_RUNTIME_GREEN original_parts=41 live_gameplay_crossover=23 preview_only=18 mp40_quakec_fire_reload=true kar98k_thompson_present=true church_intact=true")
        quit(0)
    else:
        print("VRIL_ARSENAL_CHURCH_RUNTIME_RED failures=",errors.size())
        quit(1)
