extends RefCounted
## Iglesia canonical first-person MP40: transparent hand-drawn PNGs ONLY.
## No GLB, Skin, BoneAttachment3D, Marine gloves or rejected 2026-10-19 atlas.
## Missing owner-approved artwork remains missing, never silently substituted.

const ROOT := "res://assets/weapons/mp40_nun_2d/"
const PROFILES := {
    12: {"idle": 1, "ads_idle": 1, "fire": 2, "ads_fire": 1, "reload": 5, "sprint": 1, "equip": 1},
    15: {"idle": 1, "ads_idle": 1, "fire": 2, "ads_fire": 2, "reload": 7, "sprint": 1, "equip": 1},
    24: {"idle": 1, "ads_idle": 1, "fire": 4, "ads_fire": 3, "reload": 12, "sprint": 1, "equip": 2}
}
const ACTIONS := ["idle", "ads_idle", "fire", "ads_fire", "reload", "sprint", "equip"]
# Source atlas has 24 poses total. Lower profiles uniformly sample those
# authored poses, including FIRST+LAST reload, rather than truncating reload.
const SOURCE_COUNTS := {"idle":1,"ads_idle":1,"fire":4,"ads_fire":3,
    "reload":12,"sprint":1,"equip":2}

func source_index(role: String, index: int, count: int) -> int:
    var total: int = int(SOURCE_COUNTS[role])
    if count <= 1 or total <= 1:
        return 0
    return clampi(roundi(float(index) * float(total - 1) / float(count - 1)), 0, total - 1)

const FIRE_VISUAL_SECONDS := 0.105

var profile: int = 15
var frames: Dictionary = {}
var missing: Array[String] = []
var estimated_rgba8_mib: float = 0.0
var last_role: String = ""
var last_index: int = -1
var idle_time: float = 0.0

func _init() -> void:
    set_profile(15)

func set_profile(requested: int) -> void:
    if not PROFILES.has(requested):
        push_error("IGLESIA_INVALID_SPRITE_PROFILE " + str(requested))
        return
    profile = requested
    frames.clear()
    missing.clear()
    var bytes: int = 0
    for role in ACTIONS:
        var textures: Array[Texture2D] = []
        for index in range(int(PROFILES[profile][role])):
            var source_frame: int = source_index(role, index, int(PROFILES[profile][role]))
            var path := "%s%s_%02d.png" % [ROOT, role, source_frame]
            if not ResourceLoader.exists(path):
                missing.append(path)
                continue
            var texture := load(path) as Texture2D
            if texture == null:
                missing.append(path)
                continue
            textures.append(texture)
            bytes += texture.get_width() * texture.get_height() * 4
        frames[role] = textures
    estimated_rgba8_mib = float(bytes) / 1048576.0
    last_role = ""
    last_index = -1
    # Estimate excludes import compression, mipmaps and any texture-sharing.
    print("IGLESIA_SPRITE_PROFILE ",
        JSON.stringify({"profile": profile, "required": required_count(),
            "loaded": required_count() - missing.size(), "missing": missing.size(),
            "rgba8_estimated_mib": snappedf(estimated_rgba8_mib, 0.01)}))
    if estimated_rgba8_mib > 48.0:
        push_warning("IGLESIA_SPRITE_RGBA8_ESTIMATE_OVER_48_MIB")

func required_count() -> int:
    var total: int = 0
    for role in ACTIONS:
        total += int(PROFILES[profile][role])
    return total

func ready_for_art_review() -> bool:
    return missing.is_empty() and frames["idle"].size() == 1

func select_frame(player, delta: float) -> Dictionary:
    idle_time += delta
    var ads: bool = player.ads_active()
    var role: String = "ads_idle" if ads else "idle"
    var phase: float = 0.0
    if player.reload_active:
        role = "reload"
        phase = clampf(1.0 - player.reload_left / maxf(player.reload_seconds, 0.001), 0.0, 0.999)
    elif player.shot_flash > 0.0:
        role = "ads_fire" if ads else "fire"
        phase = clampf(1.0 - player.shot_flash / FIRE_VISUAL_SECONDS, 0.0, 0.999)
    elif Input.is_action_pressed("sprint") and not ads:
        role = "sprint"
    var group: Array = frames.get(role, [])
    # During an incomplete source-art review, never show the old soldier PNGs.
    if group.is_empty():
        return {"role": role, "index": -1, "texture": null}
    var index: int = clampi(int(floor(phase * group.size())), 0, group.size() - 1)
    return {"role": role, "index": index, "texture": group[index]}

func render(player, weapon: TextureRect, delta: float, screen: Vector2) -> void:
    var selection: Dictionary = select_frame(player, delta)
    var role: String = selection["role"]
    var index: int = selection["index"]
    if role != last_role or index != last_index:
        weapon.texture = selection["texture"]
        last_role = role
        last_index = index
    weapon.visible = selection["texture"] != null
    # Subtle camera-space motion uses code, not extra PNG frames / 3D bones.
    var ads: bool = player.ads_active()
    var s: float = maxf(screen.y / 720.0, 0.5)
    var zoom: float = 1.16 if ads else 1.0
    var sway: float = 0.0 if ads or player.reload_active else sin(idle_time * 3.7) * 2.0 * s
    weapon.size = Vector2(600, 440) * s * zoom
    weapon.position = Vector2(screen.x * 0.5 - weapon.size.x * 0.5 + sway,
        screen.y - weapon.size.y + (37.0 if ads else 15.0) * s)
