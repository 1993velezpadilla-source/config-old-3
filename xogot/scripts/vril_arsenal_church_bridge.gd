extends Node3D
## Non-destructive church test: all 41 original NZ:P MDL first-person parts.
## 23 have a matching Xogot gameplay weapon; the remaining 18 are visual
## previews only (blades, dual pieces, muzzle effects, unimplemented weapons).
## A playable crossover is NOT a port of QuakeC gun physics or accurate ADS.
##
## Verifiable source frame roles are in vril_arsenal_quakec_contract.json.
## Never fabricate an action when QuakeC's indices exceed the original MDL.

const MODEL_CATALOG := "res://assets/vril_original/weapons/catalog.json"
const ROLE_CATALOG := "res://data/vril_arsenal_quakec_contract.json"
const SOURCE_PREFIX := "res://assets/vril_original/weapons/"
const FIRST_SOURCE := "mp40/v_mp40.mdl"
const LANDSCAPE := DisplayServer.SCREEN_SENSOR_LANDSCAPE

var _weapon: Node
var _camera: Camera3D
var _native_view: Node3D
var _models: Array = []
var _contracts: Dictionary = {}
var _selected: int = -1
var _model: Node3D
var _anim: AnimationPlayer
var _animation_name: String = ""
var _frame_names: Array = []
var _source_fps: float = 10.0
var _roles: Dictionary = {}
var _durations: Dictionary = {}
var _playing_role: String = ""
var _clip_end_position: float = -1.0
var _clip_forward: bool = true
var _last_shots: int = 0
var _last_reloading: bool = false
var _current_gameplay_id: String = ""
var _preview_only: bool = false
var _manual_mode: bool = false
var _manual_frame: int = 0
var _status: Label
var _bound: bool = false
var _warning_count: int = 0


func _ready() -> void:
    # Quake's first-person model basis is preserved by the exact MDL converter.
    # Do not copy arbitrary per-weapon Aether PSA rotations onto this source.
    position = Vector3(0.0, -0.12, -0.14)
    if OS.has_feature("mobile"):
        DisplayServer.screen_set_orientation(LANDSCAPE)
    call_deferred("_initialize_arsenal")


func _initialize_arsenal() -> void:
    _camera = get_parent() as Camera3D
    _weapon = get_node_or_null("../../../Weapon")
    if _camera == null or _weapon == null:
        push_error("VRIL_ARSENAL_RED real church player/camera/gun missing")
        return
    _native_view = _weapon.get("_view_root") as Node3D
    if _native_view == null:
        push_error("VRIL_ARSENAL_RED Xogot viewmodel root absent")
        return
    if not FileAccess.file_exists(MODEL_CATALOG) or not FileAccess.file_exists(ROLE_CATALOG):
        push_error("VRIL_ARSENAL_RED original model or source action catalog missing")
        return
    var model_json: Variant = JSON.parse_string(FileAccess.get_file_as_string(MODEL_CATALOG))
    var role_json: Variant = JSON.parse_string(FileAccess.get_file_as_string(ROLE_CATALOG))
    if not (model_json is Dictionary) or not (role_json is Dictionary):
        push_error("VRIL_ARSENAL_RED cannot parse authoritative JSON inventories")
        return
    _models = model_json.get("weapons", [])
    _source_fps = float(model_json.get("fps", 0.0))
    var declarations: Array = role_json.get("entries", [])
    if _models.size() != 41 or declarations.size() != 41 or _source_fps < 1.0:
        push_error("VRIL_ARSENAL_RED incomplete 41 source parts or invalid FPS")
        return
    for row: Variant in declarations:
        if not (row is Dictionary):
            push_error("VRIL_ARSENAL_RED malformed source contract")
            return
        _contracts[str(row.get("source", ""))] = row
    var primary_ids: Dictionary = {}
    var crossovers: int = 0
    for entry: Variant in _models:
        if not (entry is Dictionary):
            push_error("VRIL_ARSENAL_RED invalid original MDL row")
            return
        var name: String = str(entry.get("source", ""))
        var contract: Dictionary = _contracts.get(name, {})
        if contract.is_empty() or str(contract.get("resource", "")) != str(entry.get("resource", "")):
            push_error("VRIL_ARSENAL_RED missing model/QuakeC correspondence: " + name)
            return
        if int(contract.get("frames", -1)) != int(entry.get("frames", 0)):
            push_error("VRIL_ARSENAL_RED source frame count mismatch: " + name)
            return
        if not (entry.get("frame_names", []) is Array):
            push_error("VRIL_ARSENAL_RED missing original vertex frame names")
            return
        var gameplay_id: String = str(contract.get("gameplay_id", ""))
        if not gameplay_id.is_empty():
            if primary_ids.has(gameplay_id):
                push_error("VRIL_ARSENAL_RED duplicate gameplay weapon: " + gameplay_id)
                return
            primary_ids[gameplay_id] = true
            crossovers += 1
    if crossovers != 23:
        push_error("VRIL_ARSENAL_RED expected 23 real gameplay counterparts; got %d" % crossovers)
        return

    _camera.cull_mask |= 2
    _make_controls()
    var start_index: int = -1
    for i in range(_models.size()):
        if str(_models[i].get("source", "")) == FIRST_SOURCE:
            start_index = i
            break
    if start_index < 0 or not _select_source(start_index):
        push_error("VRIL_ARSENAL_RED original MP40 missing; abort playable test")
        return
    _bound = true
    set_meta("source_count", 41)
    set_meta("gameplay_crossovers", crossovers)
    set_meta("preview_only_count", 41 - crossovers)
    print("VRIL_ARSENAL_CHURCH_BOUND count=41 gameplay_crossovers=", crossovers,
          " preview_only=", 41-crossovers, " main_game_unchanged=true")


func _find_animation_player(node: Node) -> AnimationPlayer:
    if node is AnimationPlayer:
        return node as AnimationPlayer
    for child: Node in node.get_children():
        var result: AnimationPlayer = _find_animation_player(child)
        if result != null:
            return result
    return null


func _select_source(index: int) -> bool:
    if _models.is_empty() or _weapon == null:
        return false
    index = posmod(index, _models.size())
    var entry: Dictionary = _models[index]
    var path: String = str(entry.get("source", ""))
    var contract: Dictionary = _contracts.get(path, {})
    if contract.is_empty():
        return false
    var resource: String = str(entry.get("resource", ""))
    var packed: PackedScene = load(SOURCE_PREFIX + resource) as PackedScene
    if packed == null:
        push_error("VRIL_ARSENAL_RED actual GLB missing: " + resource)
        return false
    var next_model: Node3D = packed.instantiate() as Node3D
    if next_model == null:
        return false
    var next_anim: AnimationPlayer = _find_animation_player(next_model)
    var clip: String = ""
    if next_anim != null:
        for animation_id: StringName in next_anim.get_animation_list():
            if str(animation_id).contains("original_frames"):
                clip = str(animation_id)
                break
    if clip.is_empty():
        next_model.free()
        push_error("VRIL_ARSENAL_RED real morph sequence missing: " + resource)
        return false
    var frames: Array = entry.get("frame_names", [])
    if frames.size() < 1 or frames.size() != int(contract.get("frames", -1)):
        next_model.free()
        return false
    var source_roles: Dictionary = contract.get("roles", {})
    for role: String in source_roles:
        var window: Array = source_roles[role]
        if window.size() != 2 or mini(int(window[0]), int(window[1])) < 0 or maxi(int(window[0]), int(window[1])) >= frames.size():
            next_model.free()
            push_error("VRIL_ARSENAL_RED invalid QuakeC %s frame indices on %s" % [role, path])
            return false
    var gameplay_id: String = str(contract.get("gameplay_id", ""))
    if not gameplay_id.is_empty():
        if not bool(_weapon.call("equip_weapon", gameplay_id, true)):
            next_model.free()
            push_error("VRIL_ARSENAL_RED Xogot gameplay weapon missing: " + gameplay_id)
            return false
    # Preview-only auxiliaries deliberately do not pretend to have combat.
    var previous_model: Node3D = _model
    _model = next_model
    _model.name = "OriginalVril_" + str(entry.get("name", "viewmodel"))
    add_child(_model)
    if is_instance_valid(previous_model):
        previous_model.queue_free()
    for child: Node in _model.find_children("*", "MeshInstance3D", true, false):
        var visual: MeshInstance3D = child as MeshInstance3D
        visual.layers = 2
        visual.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
    _selected = index
    _anim = next_anim
    _animation_name = clip
    _frame_names = frames
    _roles = source_roles
    _durations = contract.get("duration_seconds", {})
    _preview_only = gameplay_id.is_empty()
    _current_gameplay_id = gameplay_id
    _last_shots = int(_weapon.get("_shots_fired"))
    _last_reloading = bool(_weapon.get("_reloading"))
    _manual_mode = false
    _show_frame(0)
    if is_instance_valid(_native_view):
        _native_view.visible = false
    _model.visible = true
    set_meta("active_original_source", path)
    set_meta("active_gameplay_weapon", gameplay_id)
    set_meta("preview_only", _preview_only)
    set_meta("authored_frame_roles", _roles)
    _update_status()
    print("VRIL_ARSENAL_SELECT source=", path, " frames=", frames.size(),
          " gameplay=", gameplay_id if not _preview_only else "PREVIEW_ONLY",
          " roles=", _roles.keys())
    return true


func _show_frame(index: int) -> void:
    if _anim == null or _frame_names.is_empty():
        return
    _manual_frame = clampi(index, 0, _frame_names.size() - 1)
    _anim.speed_scale = 1.0
    _anim.play(_animation_name)
    _anim.seek(float(_manual_frame) / _source_fps + 0.00001, true)
    _anim.pause()
    _playing_role = ""
    _clip_end_position = -1.0


func _play_role(role: String) -> bool:
    if _anim == null or not _roles.has(role):
        return false
    var frames: Array = _roles[role]
    var from_frame: int = int(frames[0])
    var to_frame: int = int(frames[1])
    if from_frame == to_frame:
        _show_frame(from_frame)
        _playing_role = role
        return true
    var frame_count: int = absi(to_frame - from_frame) + 1
    var frame_seconds: float = float(frame_count) / _source_fps
    var duration: float = float(_durations.get(role, frame_seconds))
    if duration <= 0.0:
        return false
    _clip_forward = to_frame >= from_frame
    _clip_end_position = float(to_frame) / _source_fps
    _playing_role = role
    _manual_frame = from_frame
    var playback_speed: float = frame_seconds / duration
    # Godot multiplies AnimationPlayer.speed_scale by the play() custom_speed.
    # Apply source timing exactly ONCE or the 2.3s MP40 reload accelerates twice.
    _anim.speed_scale = 1.0
    var custom_speed: float = playback_speed if _clip_forward else -playback_speed
    _anim.play(_animation_name, -1.0, custom_speed, not _clip_forward)
    _anim.seek(float(from_frame) / _source_fps + 0.00001, true)
    return true


func _process(_delta: float) -> void:
    if not _bound or _weapon == null or _model == null:
        return
    if _preview_only:
        # Gallery mode only: no false claim of game weapon integration.
        _model.visible = true
        if is_instance_valid(_native_view):
            _native_view.visible = false
        return
    # Real wall-buy/swap external to this test? Never cover the changed gun.
    var active: bool = str(_weapon.get("_weapon_id")) == _current_gameplay_id
    _model.visible = active
    if is_instance_valid(_native_view):
        _native_view.visible = not active
    if not active or _manual_mode:
        return
    var shots: int = int(_weapon.get("_shots_fired"))
    var reloading: bool = bool(_weapon.get("_reloading"))
    if shots != _last_shots:
        _last_shots = shots
        if not reloading:
            _play_role("fire")
    if reloading and not _last_reloading:
        if not _play_role("reload"):
            _warning_count += 1
            _show_frame(0)
    if not reloading and _last_reloading:
        _show_frame(0)
    _last_reloading = reloading
    if _clip_end_position >= 0.0 and _anim != null:
        var cursor: float = _anim.current_animation_position
        var reached: bool = cursor >= _clip_end_position if _clip_forward else cursor <= _clip_end_position
        if reached:
            # Never hold the last muzzle blast or duplicate an invented reload.
            _show_frame(0)
    _update_status()


func _make_controls() -> void:
    var layer := CanvasLayer.new()
    layer.name = "Vril41OriginalArsenalHUD"
    layer.layer = 8
    add_child(layer)
    var row := HBoxContainer.new()
    row.position = Vector2(12.0, 105.0)
    layer.add_child(row)
    for item in [["◀ GUN", -1], ["GUN ▶", 1], ["◀ FRAME", -2], ["FRAME ▶", 2], ["▶ SOURCE", 3], ["GAMEPLAY", 4]]:
        var button := Button.new()
        button.text = str(item[0])
        button.custom_minimum_size = Vector2(115.0, 56.0)
        var action: int = int(item[1])
        button.pressed.connect(func() -> void: _handle_button(action))
        row.add_child(button)
    _status = Label.new()
    _status.custom_minimum_size = Vector2(410, 56)
    _status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
    row.add_child(_status)


func _handle_button(action: int) -> void:
    if action == -1 or action == 1:
        _select_source(_selected + action)
    elif action == -2 or action == 2:
        _manual_mode = true
        _show_frame(_manual_frame + (1 if action == 2 else -1))
    elif action == 3 and _anim != null:
        _manual_mode = true
        _anim.speed_scale = 1.0
        _anim.play(_animation_name)
        _anim.seek(0.00001, true)
    elif action == 4:
        _manual_mode = false
        _show_frame(0)
    _update_status()


func _update_status() -> void:
    if _status == null or _selected < 0:
        return
    var label: String = str(_models[_selected].get("name", "model"))
    var mode: String = "VIEW ONLY" if _preview_only else "GAMEPLAY " + _current_gameplay_id
    var action: String = _playing_role if not _playing_role.is_empty() else "idle"
    var note: String = " | reload VISUAL N/A" if not _preview_only and not _roles.has("reload") else ""
    _status.text = "%s  %d/41 | %s | %d frames | %s%s" % [
        label, _selected + 1, mode, _frame_names.size(), action, note
    ]


func _exit_tree() -> void:
    if is_instance_valid(_native_view):
        _native_view.visible = true
