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
    assert(feq(cfg.camera_look_sensitivity_x, 110.0f));
    assert(feq(cfg.camera_look_sensitivity_y, 90.0f));
    assert(cfg.camera_invert_y == 0);
    assert(feq(cfg.camera_min_pitch_degrees, -70.0f));
    assert(feq(cfg.camera_max_pitch_degrees, 35.0f));
    assert(cfg.camera_collision_enabled == 1);
    assert(feq(cfg.camera_collision_margin, 0.18f));
    assert(feq(cfg.fov_degrees, 72.0f));
    assert(feq(cfg.near_clip, 0.05f));
    assert(feq(cfg.far_clip_multiplier, 2.5f));
    assert(cfg.forward_streaming_bias_enabled == 0);
    assert(feq(cfg.forward_streaming_bias_sectors, 1.0f));
    assert(feq(cfg.vehicle_distance_multiplier, 2.0f));
    assert(feq(cfg.ped_distance_multiplier, 2.0f));

    const char *ini =
        "[Camera]\n"
        "Enabled=1\n"
        "Height=9.0\n"
        "Distance=7.25\n"
        "Pitch=-12\n"
        "LookSensitivityX=150\n"
        "LookSensitivityY=75\n"
        "InvertY=1\n"
        "MinPitch=-55\n"
        "MaxPitch=25\n"
        "Collision=0\n"
        "CollisionMargin=0.35\n"
        "FOV=85\n"
        "NearClip=0.08\n"
        "DisableCineCam=0\n"
        "\n"
        "[World]\n"
        "Enabled=1\n"
        "DrawDistance=3.2\n"
        "ForwardBias=1\n"
        "ForwardBiasSectors=0.75\n"
        "VehicleDistance=5.0\n"
        "PedDistance=1.5\n"
        "\n"
        "[Characters]\n"
        "FixBillboards=0\n"
        "ExtendedLOD=1\n"
        "KeepFullBody=0\n"
        "HideHeadFirstPerson=0\n";

    const int applied = ctw_config_parse_text(&cfg, ini);
    assert(applied == 24);
    assert(feq(cfg.camera_height, 4.0f)); /* clamped */
    assert(feq(cfg.camera_distance, 7.25f));
    assert(feq(cfg.camera_pitch_degrees, -12.0f));
    assert(feq(cfg.camera_look_sensitivity_x, 150.0f));
    assert(feq(cfg.camera_look_sensitivity_y, 75.0f));
    assert(cfg.camera_invert_y == 1);
    assert(feq(cfg.camera_min_pitch_degrees, -55.0f));
    assert(feq(cfg.camera_max_pitch_degrees, 25.0f));
    assert(cfg.camera_collision_enabled == 0);
    assert(feq(cfg.camera_collision_margin, 0.35f));
    assert(feq(cfg.fov_degrees, 85.0f));
    assert(feq(cfg.near_clip, 0.08f));
    assert(cfg.disable_cinematic_camera == 0);
    assert(feq(cfg.far_clip_multiplier, 3.2f));
    assert(feq(cfg.stream_radius_multiplier, 3.2f));
    assert(feq(cfg.lod_distance_multiplier, 3.2f));
    assert(cfg.forward_streaming_bias_enabled == 1);
    assert(feq(cfg.forward_streaming_bias_sectors, 0.75f));
    assert(feq(cfg.vehicle_distance_multiplier, 4.0f)); /* clamped */
    assert(feq(cfg.ped_distance_multiplier, 1.5f));
    assert(cfg.character_fix == 0);
    assert(cfg.extended_character_lod == 1);
    assert(cfg.keep_full_player_body == 0);
    assert(cfg.hide_head_in_first_person == 0);


    Ctw3DConfig advanced;
    ctw_config_set_defaults(&advanced);
    const char *advanced_world =
        "[World]\n"
        "DrawDistance=3.0\n"
        "FarClip=4.1\n"
        "StreamRadius=3.8\n"
        "LODDistance=2.7\n";
    assert(ctw_config_parse_text(&advanced, advanced_world) == 4);
    assert(feq(advanced.far_clip_multiplier, 4.1f));
    assert(feq(advanced.stream_radius_multiplier, 3.8f));
    assert(feq(advanced.lod_distance_multiplier, 2.7f));

    const char *disable = "[Camera]\nEnabled=0\n";
    assert(ctw_config_parse_text(&cfg, disable) == 1);
    assert(cfg.camera_enabled == 0);
    assert(cfg.mode == CTW_CAMERA_STOCK);

    return 0;
}
