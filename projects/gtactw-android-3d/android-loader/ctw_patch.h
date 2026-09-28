#pragma once

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    CTW_CAMERA_STOCK = 0,
    CTW_CAMERA_THIRD_PERSON = 1,
    CTW_CAMERA_FIRST_PERSON = 2,
} CtwCameraMode;

typedef struct {
    CtwCameraMode mode;

    int camera_enabled;
    float camera_height;
    float camera_distance;
    float camera_pitch_degrees;
    float camera_look_sensitivity_x;
    float camera_look_sensitivity_y;
    int camera_invert_y;
    float camera_min_pitch_degrees;
    float camera_max_pitch_degrees;
    float fov_degrees;
    float near_clip;
    int disable_cinematic_camera;

    int draw_distance_enabled;
    float far_clip_multiplier;
    float stream_radius_multiplier;
    float lod_distance_multiplier;
    float vehicle_distance_multiplier;
    float ped_distance_multiplier;

    int character_fix;
    int extended_character_lod;
    int keep_full_player_body;
    int hide_head_in_first_person;
} Ctw3DConfig;

typedef struct {
    uintptr_t camera_update;
    uintptr_t projection_setup;
    uintptr_t world_stream_update;
    uintptr_t sector_visibility;
    uintptr_t lod_test;
    uintptr_t player_render;
} CtwPatchTargets;

extern Ctw3DConfig g_ctw3d_config;

int ctw_mod_init(void *original_game_handle);
void ctw_mod_shutdown(void);

int ctw_apply_profile(const CtwPatchTargets *targets);
int ctw_arm64_install_abs_jump(void *target, void *replacement, uint8_t saved[16]);
int ctw_arm64_restore_16(void *target, const uint8_t saved[16]);

#ifdef __cplusplus
}
#endif
