#define _GNU_SOURCE
#include "ctw_runtime_adapters.h"

#include "ctw_camera.h"
#include "ctw_hooks.h"
#include "ctw_mod_runtime.h"
#include "ctw_patch.h"

#include <dlfcn.h>
#include <math.h>
#include <stdint.h>
#include <string.h>

#define CTW_FIXED_ONE 4096.0f
#define CTW_PI 3.14159265358979323846f

enum {
    CTW_BASECAM_FOV = 0x20,
    CTW_BASECAM_POS_X = 0xB8,
    CTW_BASECAM_POS_Y = 0xBC,
    CTW_BASECAM_POS_Z = 0xC0,
    CTW_BASECAM_PITCH = 0xE4,
    CTW_BASECAM_TARGET_X = 0x128,
    CTW_BASECAM_TARGET_Y = 0x12C,
    CTW_BASECAM_TARGET_Z = 0x130,
};

typedef void (*CtwFollowPedUpdateFn)(void *camera, const void *yoke);
typedef void (*CtwSetCameraBehindTargetFn)(
    void *camera,
    int snap_to_target,
    int explicit_heading,
    int16_t heading
);
typedef void (*CtwRecalculateMatrixFn)(void *camera);
typedef void (*CtwSetFovFn)(void *camera, int16_t fov);
typedef int (*CtwProcessLoadingFn)(void *world);
typedef void (*CtwProcessVisibilityFn)(void *world);
typedef int (*CtwFarDistanceFn)(void *position, const void *reference);
typedef void (*CtwPlayerRenderFn)(const void *player);

static CtwSetCameraBehindTargetFn g_set_camera_behind_target;
static CtwRecalculateMatrixFn g_recalculate_matrix;

static int32_t read_i32(const void *base, size_t offset) {
    int32_t value = 0;
    memcpy(&value, (const uint8_t *)base + offset, sizeof(value));
    return value;
}

static void write_i32(void *base, size_t offset, int32_t value) {
    memcpy((uint8_t *)base + offset, &value, sizeof(value));
}

static void write_i16(void *base, size_t offset, int16_t value) {
    memcpy((uint8_t *)base + offset, &value, sizeof(value));
}

static int16_t angle_from_degrees(float degrees) {
    while (degrees > 180.0f)
        degrees -= 360.0f;
    while (degrees < -180.0f)
        degrees += 360.0f;

    const float scaled = degrees * (65536.0f / 360.0f);
    const int32_t rounded = (int32_t)(
        scaled >= 0.0f ? scaled + 0.5f : scaled - 0.5f
    );
    return (int16_t)rounded;
}

static int16_t angle_from_camera_vector(
    int32_t camera_x,
    int32_t camera_y,
    int32_t target_x,
    int32_t target_y
) {
    const float dx = (float)(target_x - camera_x);
    const float dy = (float)(target_y - camera_y);
    if (fabsf(dx) < 1.0f && fabsf(dy) < 1.0f)
        return 0;

    const float radians = atan2f(dx, dy);
    const float scaled = radians * (32768.0f / CTW_PI);
    const int32_t rounded = (int32_t)(
        scaled >= 0.0f ? scaled + 0.5f : scaled - 0.5f
    );
    return (int16_t)rounded;
}

static int16_t add_angles(int16_t a, int16_t b) {
    return (int16_t)((uint16_t)a + (uint16_t)b);
}

static int16_t fov_from_degrees(float degrees) {
    if (!isfinite(degrees))
        degrees = 72.0f;
    if (degrees < 1.0f)
        degrees = 1.0f;
    if (degrees > 179.0f)
        degrees = 179.0f;
    return angle_from_degrees(degrees);
}

static void apply_pitch(void *camera, float view_pitch_degrees) {
    /*
     * cBaseCam::RecalculateMatrix() feeds (-16384 - field_0xE4) to the
     * X rotation. Convert the desired view pitch back into that stored field.
     */
    const int32_t view_angle = (int32_t)angle_from_degrees(
        view_pitch_degrees
    );
    const int16_t stored_pitch = (int16_t)(-16384 - view_angle);
    write_i16(camera, CTW_BASECAM_PITCH, stored_pitch);
}

static void shorten_native_third_person_distance(
    void *camera,
    float desired_distance
) {
    if (!isfinite(desired_distance) || desired_distance <= 0.0f)
        return;

    const int32_t tx = read_i32(camera, CTW_BASECAM_TARGET_X);
    const int32_t ty = read_i32(camera, CTW_BASECAM_TARGET_Y);
    const int32_t cx = read_i32(camera, CTW_BASECAM_POS_X);
    const int32_t cy = read_i32(camera, CTW_BASECAM_POS_Y);

    const float dx = (float)(cx - tx);
    const float dy = (float)(cy - ty);
    const float current = sqrtf(dx * dx + dy * dy);
    const float desired = desired_distance * CTW_FIXED_ONE;

    /*
     * Never extend beyond Rockstar's collision-resolved position here.
     * We only shorten its safe camera ray on this first runtime pass.
     */
    if (current <= desired || current < 1.0f)
        return;

    const float scale = desired / current;
    write_i32(
        camera,
        CTW_BASECAM_POS_X,
        tx + (int32_t)(dx * scale)
    );
    write_i32(
        camera,
        CTW_BASECAM_POS_Y,
        ty + (int32_t)(dy * scale)
    );
}

static int16_t establish_native_heading(
    void *camera,
    float yaw_offset_degrees
) {
    /*
     * First ask the original camera to place itself behind the target using
     * Rockstar's collision/facing path. That gives us the correct target-
     * relative baseline heading without reverse-engineering ped heading.
     */
    g_set_camera_behind_target(camera, 0, 0, 0);

    const int16_t base = angle_from_camera_vector(
        read_i32(camera, CTW_BASECAM_POS_X),
        read_i32(camera, CTW_BASECAM_POS_Y),
        read_i32(camera, CTW_BASECAM_TARGET_X),
        read_i32(camera, CTW_BASECAM_TARGET_Y)
    );
    const int16_t offset = angle_from_degrees(yaw_offset_degrees);
    const int16_t heading = add_angles(base, offset);

    if (offset != 0) {
        /*
         * Re-run the same native placement/collision path at the explicit
         * orbit heading instead of rotating into walls ourselves.
         */
        g_set_camera_behind_target(camera, 0, 1, heading);
    }
    return heading;
}

int ctw_runtime_adapters_bind(void *original_game_handle) {
    if (!original_game_handle)
        return -1;

    dlerror();
    g_set_camera_behind_target = (CtwSetCameraBehindTargetFn)dlsym(
        original_game_handle,
        "_ZN13cFollowPedCam21SetCameraBehindTargetEbbs"
    );
    if (dlerror() != NULL || !g_set_camera_behind_target)
        return -2;

    dlerror();
    g_recalculate_matrix = (CtwRecalculateMatrixFn)dlsym(
        original_game_handle,
        "_ZN8cBaseCam17RecalculateMatrixEv"
    );
    if (dlerror() != NULL || !g_recalculate_matrix) {
        g_set_camera_behind_target = NULL;
        return -3;
    }

    return 0;
}

void ctw_camera_update_adapter_v1(void *camera, const void *yoke) {
    CtwFollowPedUpdateFn original = (CtwFollowPedUpdateFn)
        ctw_mod_original_for_hook(CTW_HOOK_CAMERA_UPDATE);
    if (!original)
        return;

    /* Preserve all stock target selection, mission state and transitions. */
    original(camera, yoke);

    const CtwCameraInputSnapshot input = ctw_camera_snapshot();
    if (!g_ctw3d_config.camera_enabled ||
        input.mode == CTW_CAMERA_STOCK ||
        !g_set_camera_behind_target ||
        !g_recalculate_matrix) {
        return;
    }

    const CtwCameraOrbitState orbit = ctw_camera_orbit_snapshot();
    (void)establish_native_heading(camera, orbit.yaw_degrees);

    if (input.mode == CTW_CAMERA_THIRD_PERSON) {
        shorten_native_third_person_distance(
            camera,
            g_ctw3d_config.camera_distance
        );
    } else if (input.mode == CTW_CAMERA_FIRST_PERSON) {
        const int32_t tx = read_i32(camera, CTW_BASECAM_TARGET_X);
        const int32_t ty = read_i32(camera, CTW_BASECAM_TARGET_Y);
        const int32_t tz = read_i32(camera, CTW_BASECAM_TARGET_Z);
        const float height = isfinite(g_ctw3d_config.camera_height)
            ? g_ctw3d_config.camera_height
            : 1.35f;

        write_i32(camera, CTW_BASECAM_POS_X, tx);
        write_i32(camera, CTW_BASECAM_POS_Y, ty);
        write_i32(
            camera,
            CTW_BASECAM_POS_Z,
            tz + (int32_t)(height * CTW_FIXED_ONE)
        );
    }

    apply_pitch(camera, orbit.pitch_degrees);
    g_recalculate_matrix(camera);
}

void ctw_projection_setup_adapter_v1(void *camera, int16_t fov) {
    CtwSetFovFn original = (CtwSetFovFn)
        ctw_mod_original_for_hook(CTW_HOOK_PROJECTION_SETUP);
    if (!original)
        return;

    const CtwCameraInputSnapshot input = ctw_camera_snapshot();
    if (g_ctw3d_config.camera_enabled && input.mode != CTW_CAMERA_STOCK)
        fov = fov_from_degrees(g_ctw3d_config.fov_degrees);

    original(camera, fov);
}

int ctw_world_stream_update_passthrough_v1(void *world) {
    CtwProcessLoadingFn original = (CtwProcessLoadingFn)
        ctw_mod_original_for_hook(CTW_HOOK_WORLD_STREAM_UPDATE);
    return original ? original(world) : 0;
}

void ctw_world_visibility_passthrough_v1(void *world) {
    CtwProcessVisibilityFn original = (CtwProcessVisibilityFn)
        ctw_mod_original_for_hook(CTW_HOOK_SECTOR_VISIBILITY);
    if (original)
        original(world);
}

int ctw_lod_test_passthrough_v1(
    void *position,
    const void *reference
) {
    CtwFarDistanceFn original = (CtwFarDistanceFn)
        ctw_mod_original_for_hook(CTW_HOOK_LOD_TEST);
    return original ? original(position, reference) : 0;
}

void ctw_player_render_passthrough_v1(const void *player) {
    CtwPlayerRenderFn original = (CtwPlayerRenderFn)
        ctw_mod_original_for_hook(CTW_HOOK_PLAYER_RENDER);
    if (original)
        original(player);
}
