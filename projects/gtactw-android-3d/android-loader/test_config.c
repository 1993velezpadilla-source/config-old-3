#include "ctw_config.h"

#include <assert.h>
#include <math.h>

static int feq(float a, float b) {
    return fabsf(a - b) < 0.0001f;
}

int main(void) {
    Ctw3DConfig cfg;
    ctw_config_set_defaults(&cfg);

    assert(cfg.mode == CTW_CAMERA_THIRD_PERSON);
    assert(feq(cfg.camera_height, 1.35f));
    assert(feq(cfg.camera_distance, 5.8f));
    assert(feq(cfg.camera_pitch_degrees, -7.0f));
    assert(feq(cfg.fov_degrees, 72.0f));
    assert(feq(cfg.far_clip_multiplier, 2.5f));
    assert(feq(cfg.vehicle_distance_multiplier, 2.0f));
    assert(feq(cfg.ped_distance_multiplier, 2.0f));

    const char *ini =
        "[Camera]\n"
        "Enabled=1\n"
        "Height=9.0\n"
        "Distance=7.25\n"
        "Pitch=-12\n"
        "FOV=85\n"
        "DisableCineCam=0\n"
        "\n"
        "[World]\n"
        "Enabled=1\n"
        "DrawDistance=3.2\n"
        "VehicleDistance=5.0\n"
        "PedDistance=1.5\n"
        "\n"
        "[Characters]\n"
        "FixBillboards=0\n"
        "ExtendedLOD=1\n";

    const int applied = ctw_config_parse_text(&cfg, ini);
    assert(applied == 12);
    assert(feq(cfg.camera_height, 4.0f)); /* clamped */
    assert(feq(cfg.camera_distance, 7.25f));
    assert(feq(cfg.camera_pitch_degrees, -12.0f));
    assert(feq(cfg.fov_degrees, 85.0f));
    assert(cfg.disable_cinematic_camera == 0);
    assert(feq(cfg.far_clip_multiplier, 3.2f));
    assert(feq(cfg.stream_radius_multiplier, 3.2f));
    assert(feq(cfg.vehicle_distance_multiplier, 4.0f)); /* clamped */
    assert(feq(cfg.ped_distance_multiplier, 1.5f));
    assert(cfg.character_fix == 0);
    assert(cfg.extended_character_lod == 1);

    const char *disable = "[Camera]\nEnabled=0\n";
    assert(ctw_config_parse_text(&cfg, disable) == 1);
    assert(cfg.camera_enabled == 0);
    assert(cfg.mode == CTW_CAMERA_STOCK);

    return 0;
}
