#define _GNU_SOURCE
#include "ctw_runtime_adapters.h"

#include "ctw_camera.h"
#include "ctw_character.h"
#include "ctw_hooks.h"
#include "ctw_mod_runtime.h"
#include "ctw_patch.h"

#include <dlfcn.h>
#include <math.h>
#include <stdatomic.h>
#include <stdint.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#define CTW_FIXED_ONE 4096.0f
#define CTW_PI 3.14159265358979323846f
#define CTW_WORLD_SECTOR_SIZE_FIXED (60.0f * CTW_FIXED_ONE)
#define CTW_PED_BUCKET_BIND_GOT_RVA 0xDF0AC0u
#define CTW_PLAYER_HANDLE_AIMING_VTABLE_RVA 0xD81960u
#define CTW_YOKE_AIM_ANGLE_OFFSET 0x22u
#define CTW_YOKE_EXPLICIT_AIM_OFFSET 0xB0u
#define CTW_PED_SPRITE_PRIMARY_OFFSET 0x224u
#define CTW_PED_SPRITE_SECONDARY_OFFSET 0x26Cu

enum {
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
typedef void (*CtwRenderWorldProcessFn)(void *world);
typedef void (*CtwProcessVisibilityFn)(void *world);
typedef int (*CtwFarDistanceFn)(void *position, const void *reference);
typedef void (*CtwPedSpriteRenderFn)(
    void *sprite,
    const void *position,
    const void *forward,
    uintptr_t arg3,
    uintptr_t arg4,
    uintptr_t arg5,
    uintptr_t arg6,
    uintptr_t arg7,
    uintptr_t arg8
);
typedef void (*CtwPedBucketBindFn)(
    void *renderer,
    void *depth,
    uint32_t color,
    uint32_t component,
    const void *anim_frame,
    const void *sprite,
    uint32_t body_type
);
typedef void (*CtwPlayerHandleAimingFn)(
    void *player,
    void *yoke,
    const void **target
);

typedef struct {
    int active;
    void *camera;
    int32_t true_x;
    int32_t true_y;
    int32_t biased_x;
    int32_t biased_y;
} CtwStreamBiasState;

static CtwSetCameraBehindTargetFn g_set_camera_behind_target;
static CtwSetFovFn g_set_fov;
static CtwRecalculateMatrixFn g_recalculate_matrix;
static void **g_active_camera_slot;
static void **g_players;
static int *g_local_player_id;
static CtwPedBucketBindFn g_ped_bucket_bind_original;
static void **g_ped_bucket_bind_got;
static CtwPlayerHandleAimingFn g_player_handle_aiming_original;
static void **g_player_handle_aiming_vtable;
static int g_aux_hooks_installed;
static _Thread_local int g_rendering_local_player_sprite;

static atomic_int g_stream_heading = ATOMIC_VAR_INIT(0);
static atomic_int g_stream_heading_valid = ATOMIC_VAR_INIT(0);
static _Thread_local CtwStreamBiasState g_stream_bias;

static size_t runtime_page_size(void) {
    const long value = sysconf(_SC_PAGESIZE);
    return value > 0 ? (size_t)value : 4096u;
}

static int runtime_make_data_writable(void *address) {
    const size_t page = runtime_page_size();
    const uintptr_t start =
        (uintptr_t)address & ~(uintptr_t)(page - 1u);
    return mprotect((void *)start, page, PROT_READ | PROT_WRITE);
}

static int runtime_restore_data_readonly(void *address) {
    const size_t page = runtime_page_size();
    const uintptr_t start =
        (uintptr_t)address & ~(uintptr_t)(page - 1u);
    return mprotect((void *)start, page, PROT_READ);
}

static int16_t read_i16(const void *base, size_t offset) {
    int16_t value = 0;
    memcpy(&value, (const uint8_t *)base + offset, sizeof(value));
    return value;
}

static uint8_t read_u8(const void *base, size_t offset) {
    uint8_t value = 0;
    memcpy(&value, (const uint8_t *)base + offset, sizeof(value));
    return value;
}

static void write_u8(void *base, size_t offset, uint8_t value) {
    memcpy((uint8_t *)base + offset, &value, sizeof(value));
}

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
    g_set_camera_behind_target(camera, 0, 0, 0);

    const int16_t base = angle_from_camera_vector(
        read_i32(camera, CTW_BASECAM_POS_X),
        read_i32(camera, CTW_BASECAM_POS_Y),
        read_i32(camera, CTW_BASECAM_TARGET_X),
        read_i32(camera, CTW_BASECAM_TARGET_Y)
    );
    const int16_t offset = angle_from_degrees(yaw_offset_degrees);
    const int16_t heading = add_angles(base, offset);

    if (offset != 0)
        g_set_camera_behind_target(camera, 0, 1, heading);
    return heading;
}

static int stream_bias_enabled(void) {
    const CtwCameraInputSnapshot input = ctw_camera_snapshot();
    return
        g_ctw3d_config.draw_distance_enabled &&
        g_ctw3d_config.forward_streaming_bias_enabled &&
        input.mode != CTW_CAMERA_STOCK &&
        g_active_camera_slot &&
        atomic_load_explicit(
            &g_stream_heading_valid,
            memory_order_relaxed
        );
}

static int32_t stream_bias_component(float v) {
    if (v > (float)INT32_MAX)
        return INT32_MAX;
    if (v < (float)INT32_MIN)
        return INT32_MIN;
    return (int32_t)v;
}

static void stream_bias_begin(void *camera) {
    float sectors = g_ctw3d_config.forward_streaming_bias_sectors;
    if (!isfinite(sectors))
        sectors = 0.0f;
    if (sectors < 0.0f)
        sectors = 0.0f;
    if (sectors > 1.0f)
        sectors = 1.0f;

    const int16_t heading = (int16_t)atomic_load_explicit(
        &g_stream_heading,
        memory_order_relaxed
    );
    const float radians = (float)heading * (CTW_PI / 32768.0f);
    const float distance = sectors * CTW_WORLD_SECTOR_SIZE_FIXED;
    const int32_t dx = stream_bias_component(sinf(radians) * distance);
    const int32_t dy = stream_bias_component(cosf(radians) * distance);

    g_stream_bias = (CtwStreamBiasState){
        .active = 1,
        .camera = camera,
        .true_x = read_i32(camera, CTW_BASECAM_POS_X),
        .true_y = read_i32(camera, CTW_BASECAM_POS_Y),
    };
    g_stream_bias.biased_x = g_stream_bias.true_x + dx;
    g_stream_bias.biased_y = g_stream_bias.true_y + dy;

    write_i32(camera, CTW_BASECAM_POS_X, g_stream_bias.biased_x);
    write_i32(camera, CTW_BASECAM_POS_Y, g_stream_bias.biased_y);
}

static void stream_bias_end(void) {
    if (!g_stream_bias.active || !g_stream_bias.camera)
        return;

    write_i32(
        g_stream_bias.camera,
        CTW_BASECAM_POS_X,
        g_stream_bias.true_x
    );
    write_i32(
        g_stream_bias.camera,
        CTW_BASECAM_POS_Y,
        g_stream_bias.true_y
    );
    memset(&g_stream_bias, 0, sizeof(g_stream_bias));
}

static int sprite_is_local_player(const void *sprite) {
    if (!sprite || !g_players || !g_local_player_id)
        return 0;

    const int player_id = *g_local_player_id;
    if (player_id < 0 || player_id > 1)
        return 0;

    void *player = g_players[player_id];
    if (!player)
        return 0;

    const uintptr_t base = (uintptr_t)player;
    const uintptr_t value = (uintptr_t)sprite;
    return value == base + CTW_PED_SPRITE_PRIMARY_OFFSET ||
           value == base + CTW_PED_SPRITE_SECONDARY_OFFSET;
}

static void ctw_player_handle_aiming_aux(
    void *player,
    void *yoke,
    const void **target
) {
    if (!g_player_handle_aiming_original)
        return;

    const CtwCameraInputSnapshot input = ctw_camera_snapshot();
    if (!yoke ||
        !g_ctw3d_config.camera_enabled ||
        input.mode == CTW_CAMERA_STOCK ||
        !atomic_load_explicit(
            &g_stream_heading_valid,
            memory_order_relaxed
        )) {
        g_player_handle_aiming_original(player, yoke, target);
        return;
    }

    const uint8_t old_explicit = read_u8(
        yoke,
        CTW_YOKE_EXPLICIT_AIM_OFFSET
    );
    const int16_t old_angle = read_i16(
        yoke,
        CTW_YOKE_AIM_ANGLE_OFFSET
    );
    const int16_t camera_heading = (int16_t)atomic_load_explicit(
        &g_stream_heading,
        memory_order_relaxed
    );

    /*
     * HandleAiming already has a native explicit-angle path. Feed it the
     * camera heading only for this call, preserving scripted targets,
     * sensor-cone auto-target and all weapon logic inside Rockstar code.
     */
    write_u8(yoke, CTW_YOKE_EXPLICIT_AIM_OFFSET, 1u);
    write_i16(yoke, CTW_YOKE_AIM_ANGLE_OFFSET, camera_heading);

    g_player_handle_aiming_original(player, yoke, target);

    write_i16(yoke, CTW_YOKE_AIM_ANGLE_OFFSET, old_angle);
    write_u8(yoke, CTW_YOKE_EXPLICIT_AIM_OFFSET, old_explicit);
}

static void ctw_ped_bucket_bind_aux(
    void *renderer,
    void *depth,
    uint32_t color,
    uint32_t component,
    const void *anim_frame,
    const void *sprite,
    uint32_t body_type
) {
    if (!g_ped_bucket_bind_original)
        return;

    const CtwCameraMode mode = ctw_camera_snapshot().mode;
    if (ctw_character_hide_body_type(
            &g_ctw3d_config,
            mode,
            g_rendering_local_player_sprite,
            body_type
        )) {
        return;
    }

    g_ped_bucket_bind_original(
        renderer,
        depth,
        color,
        component,
        anim_frame,
        sprite,
        body_type
    );
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
    g_set_fov = (CtwSetFovFn)dlsym(
        original_game_handle,
        "_ZN8cBaseCam6SetFovEs"
    );
    if (dlerror() != NULL || !g_set_fov) {
        g_set_camera_behind_target = NULL;
        return -3;
    }

    dlerror();
    g_recalculate_matrix = (CtwRecalculateMatrixFn)dlsym(
        original_game_handle,
        "_ZN8cBaseCam17RecalculateMatrixEv"
    );
    if (dlerror() != NULL || !g_recalculate_matrix) {
        g_set_camera_behind_target = NULL;
        g_set_fov = NULL;
        return -4;
    }

    dlerror();
    g_active_camera_slot = (void **)dlsym(
        original_game_handle,
        "_ZN8cBaseCam14msActiveCameraE"
    );
    if (dlerror() != NULL || !g_active_camera_slot) {
        g_set_camera_behind_target = NULL;
        g_set_fov = NULL;
        g_recalculate_matrix = NULL;
        return -5;
    }

    dlerror();
    g_players = (void **)dlsym(original_game_handle, "gPlayers");
    if (dlerror() != NULL || !g_players)
        return -6;

    dlerror();
    g_local_player_id = (int *)dlsym(
        original_game_handle,
        "gLocalPlayerId"
    );
    if (dlerror() != NULL || !g_local_player_id)
        return -7;

    dlerror();
    g_ped_bucket_bind_original = (CtwPedBucketBindFn)dlsym(
        original_game_handle,
        "_ZN18cPedBucketRenderer4BindE6cFixedILj4ELj12EEjjPK10sAnimFramePK10cPedSpriteN19cSpriteFrameManager9eBodyTypeE"
    );
    if (dlerror() != NULL || !g_ped_bucket_bind_original)
        return -8;

    Dl_info info;
    if (dladdr((void *)g_ped_bucket_bind_original, &info) == 0 ||
        !info.dli_fbase) {
        return -9;
    }

    g_ped_bucket_bind_got = (void **)((
        uintptr_t)info.dli_fbase + CTW_PED_BUCKET_BIND_GOT_RVA
    );

    dlerror();
    g_player_handle_aiming_original =
        (CtwPlayerHandleAimingFn)dlsym(
            original_game_handle,
            "_ZN7cPlayer12HandleAimingER9sVirtYokeRPK7cEntity"
        );
    if (dlerror() != NULL || !g_player_handle_aiming_original)
        return -10;

    g_player_handle_aiming_vtable = (void **)((
        uintptr_t)info.dli_fbase +
        CTW_PLAYER_HANDLE_AIMING_VTABLE_RVA
    );
    return 0;
}

static int runtime_swap_pointer(
    void **slot,
    void *expected,
    void *replacement
) {
    if (!slot || !expected || !replacement)
        return -1;
    if (*slot != expected)
        return -2;
    if (runtime_make_data_writable(slot) != 0)
        return -3;

    *slot = replacement;

    if (runtime_restore_data_readonly(slot) != 0) {
        if (runtime_make_data_writable(slot) == 0) {
            *slot = expected;
            (void)runtime_restore_data_readonly(slot);
        }
        return -4;
    }
    return 0;
}

int ctw_runtime_adapters_install_aux(void) {
    if (g_aux_hooks_installed)
        return 0;

    int rc = runtime_swap_pointer(
        g_ped_bucket_bind_got,
        (void *)g_ped_bucket_bind_original,
        (void *)&ctw_ped_bucket_bind_aux
    );
    if (rc != 0)
        return -10 + rc;

    rc = runtime_swap_pointer(
        g_player_handle_aiming_vtable,
        (void *)g_player_handle_aiming_original,
        (void *)&ctw_player_handle_aiming_aux
    );
    if (rc != 0) {
        (void)runtime_swap_pointer(
            g_ped_bucket_bind_got,
            (void *)&ctw_ped_bucket_bind_aux,
            (void *)g_ped_bucket_bind_original
        );
        return -20 + rc;
    }

    g_aux_hooks_installed = 1;
    return 0;
}

int ctw_runtime_adapters_uninstall_aux(void) {
    if (!g_aux_hooks_installed)
        return 0;

    const int aim_rc = runtime_swap_pointer(
        g_player_handle_aiming_vtable,
        (void *)&ctw_player_handle_aiming_aux,
        (void *)g_player_handle_aiming_original
    );
    const int ped_rc = runtime_swap_pointer(
        g_ped_bucket_bind_got,
        (void *)&ctw_ped_bucket_bind_aux,
        (void *)g_ped_bucket_bind_original
    );

    if (aim_rc == 0 && ped_rc == 0) {
        g_aux_hooks_installed = 0;
        return 0;
    }

    if (aim_rc != 0)
        return -20 + aim_rc;
    return -10 + ped_rc;
}

void ctw_camera_update_adapter_v1(void *camera, const void *yoke) {
    CtwFollowPedUpdateFn original = (CtwFollowPedUpdateFn)
        ctw_mod_original_for_hook(CTW_HOOK_CAMERA_UPDATE);
    if (!original)
        return;

    original(camera, yoke);

    const CtwCameraInputSnapshot input = ctw_camera_snapshot();
    if (!g_ctw3d_config.camera_enabled ||
        input.mode == CTW_CAMERA_STOCK ||
        !g_set_camera_behind_target ||
        !g_recalculate_matrix) {
        return;
    }

    const CtwCameraOrbitState orbit = ctw_camera_orbit_snapshot();
    const int16_t heading = establish_native_heading(
        camera,
        orbit.yaw_degrees
    );
    atomic_store_explicit(
        &g_stream_heading,
        (int)heading,
        memory_order_relaxed
    );
    atomic_store_explicit(
        &g_stream_heading_valid,
        1,
        memory_order_relaxed
    );

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
    if (g_set_fov)
        g_set_fov(camera, fov_from_degrees(g_ctw3d_config.fov_degrees));
    g_recalculate_matrix(camera);
}

void ctw_projection_setup_adapter_v1(void *camera) {
    CtwRecalculateMatrixFn original = (CtwRecalculateMatrixFn)
        ctw_mod_original_for_hook(CTW_HOOK_PROJECTION_SETUP);
    if (original)
        original(camera);
}

void ctw_world_stream_bias_adapter_v1(void *world) {
    CtwRenderWorldProcessFn original = (CtwRenderWorldProcessFn)
        ctw_mod_original_for_hook(CTW_HOOK_WORLD_STREAM_UPDATE);
    if (!original)
        return;

    if (!stream_bias_enabled() || g_stream_bias.active) {
        original(world);
        return;
    }

    void *camera = *g_active_camera_slot;
    if (!camera) {
        original(world);
        return;
    }

    stream_bias_begin(camera);
    original(world);
    stream_bias_end();
}

void ctw_world_visibility_bias_guard_v1(void *world) {
    CtwProcessVisibilityFn original = (CtwProcessVisibilityFn)
        ctw_mod_original_for_hook(CTW_HOOK_SECTOR_VISIBILITY);
    if (!original)
        return;

    if (!g_stream_bias.active || !g_stream_bias.camera) {
        original(world);
        return;
    }

    void *camera = g_stream_bias.camera;
    const int32_t dx = g_stream_bias.biased_x - g_stream_bias.true_x;
    const int32_t dy = g_stream_bias.biased_y - g_stream_bias.true_y;

    write_i32(camera, CTW_BASECAM_POS_X, g_stream_bias.true_x);
    write_i32(camera, CTW_BASECAM_POS_Y, g_stream_bias.true_y);

    original(world);

    g_stream_bias.true_x = read_i32(camera, CTW_BASECAM_POS_X);
    g_stream_bias.true_y = read_i32(camera, CTW_BASECAM_POS_Y);
    g_stream_bias.biased_x = g_stream_bias.true_x + dx;
    g_stream_bias.biased_y = g_stream_bias.true_y + dy;

    write_i32(camera, CTW_BASECAM_POS_X, g_stream_bias.biased_x);
    write_i32(camera, CTW_BASECAM_POS_Y, g_stream_bias.biased_y);
}

int ctw_lod_test_passthrough_v1(
    void *position,
    const void *reference
) {
    CtwFarDistanceFn original = (CtwFarDistanceFn)
        ctw_mod_original_for_hook(CTW_HOOK_LOD_TEST);
    return original ? original(position, reference) : 0;
}

void ctw_ped_sprite_render_adapter_v1(
    void *sprite,
    const void *position,
    const void *forward,
    uintptr_t arg3,
    uintptr_t arg4,
    uintptr_t arg5,
    uintptr_t arg6,
    uintptr_t arg7,
    uintptr_t arg8
) {
    CtwPedSpriteRenderFn original = (CtwPedSpriteRenderFn)
        ctw_mod_original_for_hook(CTW_HOOK_PLAYER_RENDER);
    if (!original)
        return;

    const CtwCameraInputSnapshot input = ctw_camera_snapshot();
    if (!g_ctw3d_config.character_fix ||
        input.mode == CTW_CAMERA_STOCK ||
        !g_active_camera_slot ||
        !position ||
        !forward) {
        original(
            sprite, position, forward,
            arg3, arg4, arg5, arg6, arg7, arg8
        );
        return;
    }

    void *camera = *g_active_camera_slot;
    if (!camera) {
        original(
            sprite, position, forward,
            arg3, arg4, arg5, arg6, arg7, arg8
        );
        return;
    }

    const int32_t *ped_pos = (const int32_t *)position;
    const int16_t *stock_forward = (const int16_t *)forward;
    int16_t camera_forward[3];

    int32_t camera_x = read_i32(camera, CTW_BASECAM_POS_X);
    int32_t camera_y = read_i32(camera, CTW_BASECAM_POS_Y);
    if (g_stream_bias.active && g_stream_bias.camera == camera) {
        camera_x = g_stream_bias.true_x;
        camera_y = g_stream_bias.true_y;
    }

    const void *forward_to_use = forward;
    if (ctw_character_camera_facing_forward(
            ped_pos[0],
            ped_pos[1],
            camera_x,
            camera_y,
            stock_forward,
            camera_forward
        )) {
        forward_to_use = camera_forward;
    }

    /*
     * This hook sits below cPed::Render(), so it covers the player plus every
     * world NPC that uses cPedSprite. Classic mode is a byte-for-byte
     * pass-through. FPS head/face suppression is intentionally handled later
     * at cPedBucketRenderer::Bind(), where BodyType is available.
     */
    const int previous_local = g_rendering_local_player_sprite;
    g_rendering_local_player_sprite = sprite_is_local_player(sprite);

    original(
        sprite, position, forward_to_use,
        arg3, arg4, arg5, arg6, arg7, arg8
    );

    g_rendering_local_player_sprite = previous_local;
}
