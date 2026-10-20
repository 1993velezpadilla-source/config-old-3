extends Node3D
## Isolated, reversible FPS bridge: original NZ:P/Vril MP40 MDL vertex frames
## over the EXISTING Xogot church and existing hitscan/ammo/reload logic.
## Never modify the shipped main.tscn, original weapon system or other guns.
##
## Original v_mp40.mdl contains baked hands+gun; it has NO bone skeleton.
## Frame roles are trusted ONLY when source frame names identify contiguous
## groups. Unknown roles stay unclassified rather than inventing animations.

const CATALOG := "res://assets/vril_original/weapons/catalog.json"
const MP40_SOURCE := "mp40/v_mp40.mdl"
const MP40_GLB := "mp40/v_mp40.glb"

@export var force_mp40_in_test_scene: bool = true

var _weapon: Node
var _camera: Camera3D
var _source_model: Node3D
var _source_anim: AnimationPlayer
var _source_animation_name: String = ""
var _original_view: Node3D
var _frames: Array = []
var _fps: float = 10.0
var _source_roles: Dictionary = {}
var _bound: bool = false
var _last_shots: int = -1
var _last_reloading: bool = false
var _playing_role: String = ""
var _clip_end_seconds: float = -1.0
var _manual_preview: bool = false
var _manual_frame: int = 0
var _status: Label


func _ready() -> void:
    # Gallery's exact original viewmodel offset; NOT an invented ADS angle.
    position = Vector3(0.0, -0.12, -0.14)
    call_deferred("_bind_original_mp40")


func _bind_original_mp40() -> void:
    _camera = get_parent() as Camera3D
    _weapon = get_node_or_null("../../../Weapon")
    if _camera == null or _weapon == null:
        push_error("VRIL_CHURCH_RED camera or existing gameplay weapon missing")
        return
    if not FileAccess.file_exists(CATALOG):
        push_error("VRIL_CHURCH_RED source catalog absent; run official NZ:P import")
        return
    var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(CATALOG))
    if not (data is Dictionary):
        push_error("VRIL_CHURCH_RED source catalog invalid")
        return
    var entry: Dictionary = {}
    for candidate in data.get("weapons", []):
        if candidate is Dictionary and str(candidate.get("source", "")) == MP40_SOURCE:
            entry = candidate
            break
    if entry.is_empty() or str(entry.get("resource", "")) != MP40_GLB:
        push_error("VRIL_CHURCH_RED original MP40 identity not pinned in catalog")
        return
    _frames = entry.get("frame_names", [])
    _fps = float(data.get("fps", 10.0))
    if _frames.size() != int(entry.get("frames", -1)) or _frames.is_empty() or _fps < 1.0:
        push_error("VRIL_CHURCH_RED original MP40 frame inventory inconsistent")
        return
    var packed: PackedScene = load("res://assets/vril_original/weapons/" + MP40_GLB) as PackedScene
    if packed == null:
        push_error("VRIL_CHURCH_RED cannot load actual v_mp40 GLB")
        return
    _source_model = packed.instantiate() as Node3D
    if _source_model == null:
        push_error("VRIL_CHURCH_RED original source is not a 3D scene")
        return
    add_child(_source_model)
    _source_anim = _find_animation_player(_source_model)
    if _source_anim == null:
        push_error("VRIL_CHURCH_RED converted source vertex animation missing")
        _source_model.queue_free()
        _source_model = null
        return
    for animation_name: StringName in _source_anim.get_animation_list():
        if str(animation_name).contains("original_frames"):
            _source_animation_name = str(animation_name)
            break
    if _source_animation_name.is_empty():
        push_error("VRIL_CHURCH_RED source timeline original_frames unavailable")
        _source_model.queue_free()
        _source_model = null
        return

    # Match the existing church's first-person light layer, without changing
    # original PCX material, UV, geometry, frame data or church lighting.
    for child in _source_model.find_children("*", "MeshInstance3D", true, false):
        var mesh: MeshInstance3D = child as MeshInstance3D
        mesh.layers = 2
        mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
    _camera.cull_mask |= 2
    _source_roles = _derive_source_roles(_frames)
    if force_mp40_in_test_scene:
        if not bool(_weapon.call("equip_weapon", "mp40", true)):
            push_error("VRIL_CHURCH_RED gameplay MP40 equip failed")
            return
    _original_view = _weapon.get("_view_root") as Node3D
    if _original_view == null:
        push_error("VRIL_CHURCH_RED original weapon view root missing")
        return
    _last_shots = int(_weapon.get("_shots_fired"))
    _last_reloading = bool(_weapon.get("_reloading"))
    _show_frame(0)
    _bound = true
    _make_source_preview_controls()
    set_meta("source_viewmodel", MP40_SOURCE)
    set_meta("source_frame_count", _frames.size())
    set_meta("source_roles", _source_roles)
    print("VRIL_CHURCH_MP40_BOUND original_MDL=true",
          " frames=", _frames.size(),
          " classified_actions=", _source_roles.keys(),
          " originals_only=true")
    if not _source_roles.has("fire") or not _source_roles.has("reload"):
        push_warning("VRIL_CHURCH_ROLE_GATE_AMBER: MDL names do not certify all FPS action ranges")


func _find_animation_player(node: Node) -> AnimationPlayer:
    if node is AnimationPlayer:
        return node as AnimationPlayer
    for child in node.get_children():
        var found: AnimationPlayer = _find_animation_player(child)
        if found != null:
            return found
    return null


func _frame_role(name: String) -> String:
    var value: String = name.strip_edges().to_lower()
    # Source LABELS are the sole authority. Unknown frame sequences remain
    # unclassified. No fabricated 2D bones, ammo cues or speed multipliers.
    if value.begins_with("reloadempty") or value.begins_with("reload_empty"):
        return "reload_empty"
    if value.begins_with("reload") or value.begins_with("mag"):
        return "reload"
    if value.begins_with("fire") or value.begins_with("shoot") or value.begins_with("shot"):
        return "fire"
    if value.begins_with("idle") or value.begins_with("stand") or value.begins_with("hold"):
        return "idle"
    if value.begins_with("draw") or value.begins_with("raise") or value.begins_with("equip"):
        return "equip"
    return ""


func _derive_source_roles(names: Array) -> Dictionary:
    var ranges: Dictionary = {}
    var previous: String = ""
    var start: int = 0
    for i in range(names.size() + 1):
        var role: String = _frame_role(str(names[i])) if i < names.size() else ""
        if role == previous:
            continue
        # At least two original consecutive frames; if duplicates exist,
        # never silently conflate disjoint source action fragments.
        if not previous.is_empty() and i - start >= 2:
            if ranges.has(previous):
                ranges.erase(previous)
                ranges[previous + "_ambiguous"] = true
            elif not ranges.has(previous + "_ambiguous"):
                ranges[previous] = [start, i - 1]
        previous = role
        start = i
    return ranges


func _show_frame(index: int) -> void:
    if _source_anim == null or _frames.is_empty():
        return
    _manual_frame = clampi(index, 0, _frames.size() - 1)
    _source_anim.play(_source_animation_name)
    _source_anim.seek(float(_manual_frame) / _fps + 0.00001, true)
    _source_anim.pause()
    _playing_role = ""
    _clip_end_seconds = -1.0
    _update_label()


func _play_source_range(role: String) -> bool:
    if _source_anim == null or not _source_roles.has(role):
        return false
    var section: Array = _source_roles[role]
    if section.size() != 2:
        return false
    _source_anim.play(_source_animation_name)
    _source_anim.seek(float(section[0]) / _fps + 0.00001, true)
    _clip_end_seconds = float(section[1] + 1) / _fps
    _playing_role = role
    _update_label()
    return true


func _process(_delta: float) -> void:
    if not _bound or _weapon == null or not is_instance_valid(_weapon):
        return
    var active: bool = str(_weapon.get("_weapon_id")) == "mp40"
    # Restore every other existing weapon unchanged.
    _source_model.visible = active
    if is_instance_valid(_original_view):
        _original_view.visible = not active
    if not active:
        return
    if _manual_preview:
        return
    var shots: int = int(_weapon.get("_shots_fired"))
    var reloading: bool = bool(_weapon.get("_reloading"))
    if shots != _last_shots:
        _last_shots = shots
        _play_source_range("fire")
    if reloading and not _last_reloading:
        if not _play_source_range("reload"):
            _status.text = "MP40 original: reload frames UNCLASSIFIED"
    if not reloading and _last_reloading:
        if _source_roles.has("idle"):
            _play_source_range("idle")
    _last_reloading = reloading
    if _clip_end_seconds >= 0.0 and _source_anim.current_animation_position >= _clip_end_seconds:
        if _playing_role == "idle" and not reloading:
            _play_source_range("idle")
        else:
            var end_frame: int = mini(_frames.size() - 1, ceili(_clip_end_seconds * _fps) - 1)
            _show_frame(end_frame)


func _make_source_preview_controls() -> void:
    var layer := CanvasLayer.new()
    layer.name = "VrilMP40SourceDebugHUD"
    layer.layer = 8
    add_child(layer)
    var row := HBoxContainer.new()
    row.position = Vector2(20, 118)
    layer.add_child(row)
    for spec in [
        ["◀ Frame", -1], ["Frame ▶", 1], ["▶ ALL source frames", 2], ["Gameplay", 3]
    ]:
        var button := Button.new()
        button.text = str(spec[0])
        button.custom_minimum_size = Vector2(160, 65)
        var action: int = int(spec[1])
        button.pressed.connect(func() -> void: _source_button(action))
        row.add_child(button)
    _status = Label.new()
    _status.text = "Original Virin MP40 (not PSA)."
    _status.custom_minimum_size = Vector2(260, 65)
    row.add_child(_status)
    _update_label()


func _source_button(action: int) -> void:
    if action == 3:
        _manual_preview = false
        _show_frame(0)
        return
    _manual_preview = true
    if action == 2:
        _source_anim.play(_source_animation_name)
        _source_anim.seek(0.00001, true)
        _playing_role = "original_frames"
        _clip_end_seconds = -1.0
        _update_label()
        return
    _show_frame(_manual_frame + action)


func _update_label() -> void:
    if _status == null or _frames.is_empty():
        return
    _status.text = "NZ:P MP40  [%d/%d]  %s   %s" % [
        _manual_frame + 1, _frames.size(),
        str(_frames[_manual_frame]),
        _playing_role if not _playing_role.is_empty() else "frame"
    ]


func _exit_tree() -> void:
    if is_instance_valid(_original_view):
        _original_view.visible = true
