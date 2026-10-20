extends SceneTree
## Runtime test of REAL Xogot church + original NZ:P MP40 (not gallery).
## Existing gun physics stays authoritative, and swapping to Colt restores
## the existing Aether weapon model instead of breaking other weapons.

var failures: Array[String] = []


func _initialize() -> void:
    call_deferred("_run_test")


func _bad(message: String) -> void:
    failures.append(message)
    printerr("VRIL_MP40_CHURCH_RED: ", message)


func _run_test() -> void:
    var packed: PackedScene = load("res://vril_mp40_church_test.tscn") as PackedScene
    if packed == null:
        _bad("Cannot load inherited church scene")
        quit(1)
        return
    var game: Node = packed.instantiate()
    if game == null:
        _bad("Cannot instantiate original church scene")
        quit(1)
        return
    root.add_child(game)
    for i in range(8):
        await process_frame
    var bridge: Node = game.get_node_or_null("Player/Head/Camera3D/VrilMP40Bridge")
    var gun: Node = game.get_node_or_null("Player/Weapon")
    if bridge == null or gun == null:
        _bad("Church Player/Weapon or bridge missing")
    elif not bool(bridge.get("_bound")):
        _bad("Original Vril MP40 failed binding")
    else:
        var model: Node3D = bridge.get("_source_model") as Node3D
        var animator: AnimationPlayer = bridge.get("_source_anim") as AnimationPlayer
        var view: Node3D = gun.get("_view_root") as Node3D
        if model == null or animator == null or view == null:
            _bad("Source model, animation or original view missing")
        if str(gun.get("_weapon_id")) != "mp40":
            _bad("MP40 not equipped in separate test scene")
        if int(bridge.get_meta("source_frame_count", 0)) < 2:
            _bad("Original MP40 frames missing")
        if model != null and not model.visible:
            _bad("Original source hands+gun not visible")
        if view != null and view.visible:
            _bad("Original non-Vril model not hidden")
        var original_roles: Dictionary = bridge.get("_source_roles")
        if original_roles.get("fire", []) != [1, 2] or original_roles.get("reload", []) != [4, 31]:
            _bad("NZ:P QuakeC original frame authority not applied")
        if original_roles.has("sprint_out"):
            _bad("Out-of-range QuakeC sprint_out was invented")
        var shots_before: int = int(gun.get("_shots_fired"))
        gun.call("request_fire")
        await process_frame
        if int(gun.get("_shots_fired")) <= shots_before:
            _bad("Existing MP40 hitscan/ammo firearm no longer fires")
        if str(bridge.get("_playing_role")) != "fire":
            _bad("Original Vril MP40 1-2 frame firing action did not play")
        if animator != null and absf(animator.speed_scale - (0.2 / 0.12)) > 0.01:
            _bad("Source firing playback does not respect 0.12 s QuakeC fire delay")
        gun.call("request_reload")
        await process_frame
        if not bool(gun.get("_reloading")):
            _bad("Existing MP40 reload/ammo pathway no longer works")
        if str(bridge.get("_playing_role")) != "reload":
            _bad("Original Vril MP40 frames 4-31 did not start reloading")
        if animator != null and absf(animator.speed_scale - (2.8 / 2.3)) > 0.01:
            _bad("Source reload playback does not respect 2.3 s QuakeC reload delay")
        gun.call("equip_weapon", "colt", true)
        await process_frame
        if str(gun.get("_weapon_id")) != "colt":
            _bad("Original Colt switch failed")
        if view != null and not view.visible:
            _bad("Existing Colt view did not restore")
        if model != null and model.visible:
            _bad("Vril MP40 overlaps restored Colt view")
    game.queue_free()
    await process_frame
    if failures.is_empty():
        print("VRIL_MP40_CHURCH_RUNTIME_GREEN original_source=true game_church=true mp40_original_fire_frames_1to2=true mp40_original_reload_frames_4to31=true colt_preserved=true")
        quit(0)
    else:
        print("VRIL_MP40_CHURCH_RUNTIME_RED count=", failures.size())
        quit(1)
