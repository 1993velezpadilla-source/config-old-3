extends SceneTree
## Runs in actual Godot 4.6 after import, not a textual grep pretending to render.
## Raw Black & White deliberately EXPECTED to have no rig or animation.
const LAB := preload("res://zombie_lab.tscn")
const MANIFEST := "res://assets/zombies/monja_elite/source_manifest.json"

func _init() -> void:
    call_deferred("_run")

func _red(reason: String) -> void:
    push_error("ZOMBIE_LAB_GATE_RED " + reason)
    quit(78)

func _run() -> void:
    var manifest: Variant = JSON.parse_string(FileAccess.get_file_as_string(MANIFEST))
    if not manifest is Dictionary:
        _red("missing Black White source manifest")
        return
    var source: Dictionary = (manifest as Dictionary).get("source", {})
    if int(source.get("skins", -1)) != 0 or int(source.get("animations", -1)) != 0:
        _red("source rig/animation assumptions changed; re-audit")
        return
    if not ResourceLoader.exists("res://assets/zombies/monja_elite/source/monja_black_white.glb"):
        _red("Black White source not imported; check gdignore")
        return

    var scene := LAB.instantiate() as Node3D
    if scene == null:
        _red("lab scene missing")
        return
    root.add_child(scene)
    await process_frame
    await physics_frame
    var level: Node3D = scene.call("get_lab_level") as Node3D
    if level == null or level.get_node_or_null("Player/Weapon") == null:
        _red("existing Black Pines player and weapon not reused")
        return
    if level.get_node_or_null("RoundManager") == null:
        _red("existing round director missing")
        return

    var actor: CharacterBody3D = scene.call("get_lab_actor") as CharacterBody3D
    if actor == null:
        _red("initial Black White model absent")
        return
    if not bool(actor.get_meta("zombie_lab_visual_loaded", false)):
        _red("Black White visual did not import")
        return
    if str(actor.get_meta("zombie_model", "")) != "black_white_raw":
        _red("Black White silently swapped with unrelated zombie")
        return
    if bool(actor.get_meta("zombie_rig_ready", true)) or actor.is_physics_processing():
        _red("unrigged source falsely presented as animated")
        return
    scene.call("rotate_model_180")
    if absf(float(actor.get_meta("zombie_visual_forward_fix_deg", -100.0)) - 270.0) > 0.01:
        _red("yaw correction control broken")
        return
    print("ZOMBIE_LAB_RAW_BLACK_WHITE_GATE_GREEN no_faked_animations")

    actor = scene.call("spawn_profile", "monja_clean_rig") as CharacterBody3D
    if actor == null or not bool(actor.get_meta("zombie_lab_visual_loaded", false)):
        _red("previously authored animated Monja clean file unavailable")
        return
    if not bool(actor.get_meta("zombie_rig_ready", false)):
        _red("Monja clean rig has no usable animation player")
        return
    for state: String in ["idle", "walk", "attack", "death"]:
        actor.set("_motion_state", "")
        actor.call("_play_motion_state", state)
        var name: String = str(actor.get_meta("active_animation", ""))
        if not name.to_lower().contains(state):
            _red("Monja " + state + " not connected to real animation: " + name)
            return
    print("ZOMBIE_LAB_CLEAN_MONJA_ANIMATIONS_GREEN")

    actor = scene.call("spawn_profile", "waw_reference") as CharacterBody3D
    if actor == null or not bool(actor.get_meta("zombie_lab_visual_loaded", false)):
        _red("reference zombie not imported")
        return
    if not bool(actor.get_meta("zombie_source_waw", false)):
        _red("WaW control actor not using real imported animation")
        return
    if str(actor.call("_classify_hit_zone", Vector3(0.0, 1.69, 0.0))) != "head":
        _red("headshot hit zone still wrong")
        return
    if str(actor.call("_classify_hit_zone", Vector3(0.0, 1.10, 0.0))) != "torso":
        _red("chest shot classified incorrectly")
        return
    if not bool(scene.get_meta("lab_mp40_equipped", false)):
        _red("MP40 not equipped from existing catalog")
        return
    print("ZOMBIE_LAB_WAW_HEADSHOT_MP40_GREEN")
    print("ZOMBIE_LAB_SCENE_GATES_GREEN")
    scene.queue_free()
    await process_frame
    quit(0)
