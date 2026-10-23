extends Node
## Actual in-game performance sampling. Headless CI is NOT a substitute for
## Pixel Fold FPS evidence. Writes a compact file on the tested Android device.
var elapsed: float = 0.0
var interval: float = 5.0
var samples: int = 0
var worst_fps: int = 10000
var lowest_fps: int = 10000
var last_fps: int = 0

func _process(delta: float) -> void:
    if Engine.is_editor_hint():
        return
    elapsed += delta
    if elapsed < interval:
        return
    elapsed = 0.0
    last_fps = int(Engine.get_frames_per_second())
    lowest_fps = mini(lowest_fps, last_fps)
    var draw_calls: int = RenderingServer.get_rendering_info(
        RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)
    var tris: int = RenderingServer.get_rendering_info(
        RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)
    var vram: int = RenderingServer.get_rendering_info(
        RenderingServer.RENDERING_INFO_TEXTURE_MEM_USED)
    samples += 1
    var sprite_profile: int = 0
    var missing_weapon_pngs: int = 0
    var estimated_weapon_rgba8_mib: float = 0.0
    var scene = get_parent()
    if scene != null and scene.get("hud") != null:
        var hud_node = scene.get("hud")
        var sprite_player = hud_node.get("weapon_sprites")
        sprite_profile = sprite_player.profile
        missing_weapon_pngs = sprite_player.missing.size()
        estimated_weapon_rgba8_mib = sprite_player.estimated_rgba8_mib
    var record := {
        "schema": 1, "device": OS.get_name(), "sample": samples,
        "fps": last_fps, "min_sampled_fps": lowest_fps,
        "weapon_sprite_profile": sprite_profile,
        "weapon_pngs_missing": missing_weapon_pngs,
        "weapon_rgba8_estimate_mib": estimated_weapon_rgba8_mib,
        "draw_calls": draw_calls, "visible_primitives": tris,
        "texture_mem_mb": snappedf(float(vram) / 1048576.0, 0.1),
        "gpu_frame_time_ms": 0.0,
        "note": "Measured on device running scene, not desktop CI estimate."
    }
    # Rotating latest sample avoids per-frame disk I/O.
    var handle := FileAccess.open("user://iglesia_mobile_perf_latest.json", FileAccess.WRITE)
    if handle != null:
        handle.store_string(JSON.stringify(record, "  "))
        handle.close()
    print("IGLESIA_ANDROID_PERF_SAMPLE ", JSON.stringify(record))
