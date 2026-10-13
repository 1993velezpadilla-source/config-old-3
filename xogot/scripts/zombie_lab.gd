extends Node3D
## ISOLATED laboratory. Embeds the existing Black Pines gameplay scene as-is.
## Does NOT touch normal round spawning, maps, player controls or weapon logic.
const MAP: PackedScene = preload("res://black_pines.tscn")
const LAB_ACTOR: Script = preload("res://scripts/zombie_lab_actor.gd")
const PROFILES := {
    "black_white_rig": {
        "path": "res://assets/zombies/monja_elite/play_runtime/monja_black_white_cmu_rig.gltf",
        "name": "black_white_authored_mocap",
        "yaw": 270.0,
        "waw": false
    },
    "black_white_raw": {
        "path": "res://assets/zombies/monja_elite/source/monja_black_white.glb",
        "name": "black_white_raw",
        "yaw": 90.0,
        "waw": false
    },
    "monja_clean_rig": {
        "path": "res://assets/zombies/monja_clean/clean_runtime/monja_basica_clean_rig.gltf",
        "name": "monja_clean_rig",
        "yaw": 90.0,
        "waw": false
    },
    "waw_reference": {
        "path": "res://assets/zombies/source_waw/honorgd/zombie.glb",
        "name": "waw_honorgd",
        "yaw": 0.0,
        "waw": true
    }
}
@export var starting_profile: String = "black_white_raw"
## In the delivered APK the player only sees the normal HUD, not a model editor.
@export var phone_playtest: bool = false

var _level: Node3D
var _actor: CharacterBody3D
var _player: Node3D
var _status: Label
var _current_profile: String = ""
var _chase_enabled: bool = true
var _status_timer: float = 0.0

func _ready() -> void:
    _level = MAP.instantiate() as Node3D
    if _level == null:
        push_error("ZOMBIE_LAB_RED unable to instantiate Black Pines")
        return
    _level.name = "LabBlackPines"
    _level.set("rounds_enabled", false)
    _level.set("preview_no_enemies", true)
    _level.set("prefer_blender_geometry", false)
    add_child(_level)
    _player = _level.get_node_or_null("Player") as Node3D
    if _player == null:
        push_error("ZOMBIE_LAB_RED existing player missing")
        return
    _add_lab_lighting()
    if not phone_playtest:
        _create_controls()
    call_deferred("_begin")

func _add_lab_lighting() -> void:
    # Bright diagnostic lighting without modifying Black Pines production art.
    var key := DirectionalLight3D.new()
    key.name = "LabDiagnosticKey"
    key.rotation_degrees = Vector3(-70.0, -30.0, 0.0)
    key.light_energy = 1.75
    key.shadow_enabled = false
    add_child(key)
    var fill := OmniLight3D.new()
    fill.name = "LabDiagnosticFill"
    fill.position = _player.global_position + Vector3(0.0, 3.6, -2.8)
    fill.light_color = Color(1.0, 0.94, 0.84)
    fill.light_energy = 3.6
    fill.omni_range = 11.0
    fill.shadow_enabled = false
    add_child(fill)

func _begin() -> void:
    spawn_profile(starting_profile)
    if phone_playtest and (not is_instance_valid(_actor) or
        not bool(_actor.get_meta("zombie_rig_ready", false))):
        push_error("ZOMBIE_PHONE_RED: real Black White mocap rig did not load; no fake fallbacks")
        set_meta("phone_playtest_ready", false)
        return
    if phone_playtest:
        set_meta("phone_playtest_ready", true)
        print("ZOMBIE_PHONE_BLACK_WHITE_RIG_READY_NO_DEBUG_UI")
    var weapon: Node = _player.get_node_or_null("Weapon")
    if weapon != null and weapon.has_method("equip_weapon"):
        var equipped: bool = bool(weapon.call("equip_weapon", "mp40", true))
        set_meta("lab_mp40_equipped", equipped)
    set_meta("lab_ready", true)
    print("ZOMBIE_LAB_SCENE_READY profile=", _current_profile)

func spawn_profile(profile_id: String) -> Node:
    if not PROFILES.has(profile_id) or _level == null or _player == null:
        push_warning("ZOMBIE_LAB_RED unknown profile " + profile_id)
        return null
    if is_instance_valid(_actor):
        _actor.queue_free()
        _actor = null

    var definition: Dictionary = PROFILES[profile_id]
    var actor := CharacterBody3D.new()
    actor.name = "LabZombie"
    actor.set_script(LAB_ACTOR)
    actor.set("enemy_variant", "normal")
    actor.set("lab_asset_path", str(definition["path"]))
    actor.set("lab_model_id", str(definition["name"]))
    actor.set("lab_forward_degrees", float(definition["yaw"]))
    actor.set("lab_source_waw", bool(definition["waw"]))
    actor.call("configure_direct", _player, null)
    actor.set_meta("suppress_powerup_drop", true)
    _level.add_child(actor)
    actor.global_position = _player.global_position + Vector3(0.0, 0.0, -3.8)
    _actor = actor
    _current_profile = profile_id
    # A Tripo source WITHOUT skinning must not pretend to walk/attack.
    _actor.set_physics_process(
        _chase_enabled and bool(_actor.get_meta("zombie_rig_ready", false))
    )
    set_meta("lab_profile", profile_id)
    set_meta("lab_rig_ready", _actor.get_meta("zombie_rig_ready", false))
    set_meta("lab_visual_loaded", _actor.get_meta("zombie_lab_visual_loaded", false))
    set_meta("lab_asset_path", str(definition["path"]))
    print("ZOMBIE_LAB_PROFILE ", profile_id,
        " loaded=", _actor.get_meta("zombie_lab_visual_loaded", false),
        " rig=", _actor.get_meta("zombie_rig_ready", false))
    _update_status()
    return actor

func get_lab_actor() -> CharacterBody3D:
    return _actor

func get_lab_level() -> Node3D:
    return _level

func rotate_model_180() -> void:
    if not is_instance_valid(_actor):
        return
    var source: Node3D = _actor.get_node_or_null("LabModelPivot/SourceModel") as Node3D
    if source == null:
        return
    source.rotation_degrees.y = fposmod(source.rotation_degrees.y + 180.0, 360.0)
    _actor.set_meta("zombie_visual_forward_fix_deg", source.rotation_degrees.y)
    print("ZOMBIE_LAB_FORWARD_YAW ", source.rotation_degrees.y)
    _update_status()

func toggle_chase() -> void:
    _chase_enabled = not _chase_enabled
    if is_instance_valid(_actor):
        _actor.set_physics_process(_chase_enabled and
            bool(_actor.get_meta("zombie_rig_ready", false)))
    _update_status()

func equip_mp40() -> void:
    if _player == null:
        return
    var weapon: Node = _player.get_node_or_null("Weapon")
    if weapon != null and weapon.has_method("equip_weapon"):
        set_meta("lab_mp40_equipped", bool(weapon.call("equip_weapon", "mp40", true)))
    _update_status()

func _create_controls() -> void:
    var layer := CanvasLayer.new()
    layer.name = "ZombieLabDebugUI"
    layer.layer = 20
    add_child(layer)
    var panel := PanelContainer.new()
    panel.position = Vector2(14.0, 14.0)
    panel.custom_minimum_size = Vector2(320.0, 0.0)
    layer.add_child(panel)
    var column := VBoxContainer.new()
    panel.add_child(column)
    var title := Label.new()
    title.text = "ZOMBIE LAB / GODOT 4.6"
    column.add_child(title)
    _status = Label.new()
    _status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
    _status.custom_minimum_size = Vector2(320.0, 92.0)
    column.add_child(_status)
    _add_button(column, "BLACK & WHITE (RAW)", "_on_black_white")
    _add_button(column, "MONJA CLEAN (ANIMATED)", "_on_clean")
    _add_button(column, "WAW ZOMBIE (REFERENCE)", "_on_waw")
    _add_button(column, "ROTATE MODEL 180", "rotate_model_180")
    _add_button(column, "CHASE ON / OFF", "toggle_chase")
    _add_button(column, "EQUIP MP40", "equip_mp40")

func _add_button(column: VBoxContainer, title: String, handler: String) -> void:
    var button := Button.new()
    button.text = title
    button.custom_minimum_size = Vector2(310.0, 48.0)
    button.pressed.connect(Callable(self, handler))
    column.add_child(button)

func _on_black_white() -> void:
    spawn_profile("black_white_raw")

func _on_clean() -> void:
    spawn_profile("monja_clean_rig")

func _on_waw() -> void:
    spawn_profile("waw_reference")

func _process(delta: float) -> void:
    _status_timer -= delta
    if _status_timer <= 0.0:
        _status_timer = 0.5
        _update_status()

func _update_status() -> void:
    if _status == null:
        return
    if not is_instance_valid(_actor):
        _status.text = "No actor"
        return
    var imported: bool = bool(_actor.get_meta("zombie_lab_visual_loaded", false))
    var rigged: bool = bool(_actor.get_meta("zombie_rig_ready", false))
    var state: String = str(_actor.get_meta("active_animation", "(no animation)"))
    var yaw: float = float(_actor.get_meta("zombie_visual_forward_fix_deg", 0.0))
    _status.text = "%s | MESH %s | RIG %s\nANIM: %s\nYAW: %.0f | CHASE: %s | MP40: %s" % [
        _current_profile, "OK" if imported else "MISSING",
        "READY" if rigged else "PENDING", state, yaw,
        "ON" if _chase_enabled and rigged else "OFF",
        "OK" if bool(get_meta("lab_mp40_equipped", false)) else "PENDING"
    ]
