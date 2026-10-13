extends SceneTree
## Real Godot runtime gate for shipping a specific authored Black & White nun,
## not a screenshot-free text or asset-name gate.
const SCENE: PackedScene = preload("res://zombie_lab_play.tscn")
const REQUIRED := ["idle", "walk", "attack", "death", "104_41", "111_19", "90_16"]

func _initialize() -> void:
    call_deferred("_probe")

func _fail(message: String) -> void:
    push_error("ZOMBIE_PHONE_GATE_RED " + message)
    quit(73)

func _probe() -> void:
    var game := SCENE.instantiate() as Node3D
    if game == null:
        _fail("shipping scene could not instantiate")
        return
    root.add_child(game)
    await process_frame
    await physics_frame
    await process_frame

    if game.get_node_or_null("ZombieLabDebugUI") != null:
        _fail("model-turn/debug buttons are visible in the phone build")
        return
    if not bool(game.get_meta("phone_playtest_ready", false)):
        _fail("shipping code did not certify actual rig before gameplay")
        return

    var actor := game.call("get_lab_actor") as CharacterBody3D
    var level := game.call("get_lab_level") as Node3D
    if actor == null or level == null:
        _fail("real actor or level missing")
        return
    if not bool(actor.get_meta("zombie_lab_visual_loaded", false)):
        _fail("real Black White source visual not loaded")
        return
    if str(actor.get_meta("zombie_model", "")) != "black_white_authored_mocap":
        _fail("old zombie substituted for Black White")
        return
    if str(actor.get_meta("zombie_lab_asset_path", "")).find("monja_black_white_cmu_rig.gltf") < 0:
        _fail("shipping rig path not actually used")
        return
    if not bool(actor.get_meta("zombie_rig_ready", false)) or not actor.is_physics_processing():
        _fail("rig missing or chase is disabled")
        return

    var pivot := actor.get_node_or_null("LabModelPivot/SourceModel") as Node3D
    if pivot == null or absf(fposmod(pivot.rotation_degrees.y, 360.0) - 270.0) > 0.01:
        _fail("authored 180-degree forward axis correction not applied in APK")
        return

    var skeletons := actor.find_children("*", "Skeleton3D", true, false)
    if skeletons.is_empty():
        _fail("fake animation with no actual humanoid skeleton")
        return
    var bones: int = 0
    for candidate: Node in skeletons:
        bones = maxi(bones, (candidate as Skeleton3D).get_bone_count())
    if bones < 20:
        _fail("insufficient authored bone count " + str(bones))
        return

    var animations := actor.find_children("*", "AnimationPlayer", true, false)
    if animations.is_empty():
        _fail("no genuine AnimationPlayer")
        return
    var names: String = ""
    for player: Node in animations:
        for name: StringName in (player as AnimationPlayer).get_animation_list():
            names += " " + str(name).to_lower()
    for token: String in REQUIRED:
        if not names.contains(token):
            _fail("missing real motion token: " + token + " from " + names)
            return

    var player_node := level.get_node_or_null("Player") as Node3D
    if player_node == null or player_node.get_node_or_null("Weapon") == null:
        _fail("production player/weapon not connected")
        return
    if not bool(game.get_meta("lab_mp40_equipped", false)):
        _fail("MP40 could not be equipped")
        return
    if str(actor.call("_classify_hit_zone", Vector3(0.0, 1.69, 0.0))) != "head":
        _fail("headshot target invalid")
        return

    var initial_distance := Vector2(
        actor.global_position.x - player_node.global_position.x,
        actor.global_position.z - player_node.global_position.z
    ).length()
    for i in range(120):
        await physics_frame
    if not is_instance_valid(actor):
        _fail("zombie vanished while chasing player")
        return
    var remaining_distance := Vector2(
        actor.global_position.x - player_node.global_position.x,
        actor.global_position.z - player_node.global_position.z
    ).length()
    if remaining_distance >= initial_distance - 0.10:
        _fail("zombie did not actually close the distance to player: " + str(initial_distance) + " -> " + str(remaining_distance))
        return
    var animation_state := str(actor.get_meta("active_animation", "")).to_lower()
    if animation_state.is_empty():
        _fail("zombie moved in world but animation never played")
        return

    print("ZOMBIE_PHONE_BLACKWHITE_REAL_MOCAP_GREEN bones=", bones,
        " start_distance=", initial_distance,
        " end_distance=", remaining_distance,
        " animation=", animation_state)
    print("ZOMBIE_PHONE_NO_MODEL_DEBUG_BUTTONS_GREEN")
    print("ZOMBIE_PHONE_SHIPPING_GAMEPLAY_GREEN")
    game.queue_free()
    await process_frame
    quit(0)
