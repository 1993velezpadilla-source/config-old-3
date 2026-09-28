#include "ctw_patch.h"
#include "ctw_profile.h"

#if defined(__ANDROID__)
#include <android/log.h>
#else
#include <stdio.h>
#endif
#include <errno.h>
#include <stdint.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#define LOG_TAG "CTW3D"
#if defined(__ANDROID__)
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)
#else
#define LOGI(...) do { fprintf(stderr, LOG_TAG ": "); fprintf(stderr, __VA_ARGS__); fputc('\n', stderr); } while (0)
#define LOGE(...) LOGI(__VA_ARGS__)
#endif

Ctw3DConfig g_ctw3d_config = {
    .mode = CTW_CAMERA_THIRD_PERSON,

    .camera_enabled = 1,
    .camera_height = 1.35f,
    .camera_distance = 5.8f,
    .camera_pitch_degrees = -7.0f,
    .fov_degrees = 72.0f,
    .near_clip = 0.05f,
    .disable_cinematic_camera = 1,

    .draw_distance_enabled = 1,
    .far_clip_multiplier = 2.5f,
    .stream_radius_multiplier = 2.5f,
    .lod_distance_multiplier = 2.0f,
    .vehicle_distance_multiplier = 2.0f,
    .ped_distance_multiplier = 2.0f,

    .character_fix = 1,
    .extended_character_lod = 1,
    .keep_full_player_body = 1,
    .hide_head_in_first_person = 1,
};

#if defined(__aarch64__)
static size_t page_size(void) {
    static size_t size = 0;
    if (!size) {
        const long v = sysconf(_SC_PAGESIZE);
        size = v > 0 ? (size_t)v : 4096u;
    }
    return size;
}

static int make_writable(void *address, size_t length, int prot) {
    const size_t page = page_size();
    const uintptr_t start = (uintptr_t)address & ~(uintptr_t)(page - 1u);
    const uintptr_t end =
        ((uintptr_t)address + length + page - 1u) & ~(uintptr_t)(page - 1u);
    return mprotect((void *)start, end - start, prot);
}
#endif

int ctw_arm64_install_abs_jump(void *target, void *replacement, uint8_t saved[16]) {
#if defined(__aarch64__)
    if (!target || !replacement || !saved)
        return -1;

    memcpy(saved, target, 16);

    /* ldr x16, #8 ; br x16 ; .quad replacement */
    uint32_t patch[4];
    patch[0] = 0x58000050u;
    patch[1] = 0xD61F0200u;
    const uint64_t dst = (uint64_t)(uintptr_t)replacement;
    memcpy(&patch[2], &dst, sizeof(dst));

    if (make_writable(target, 16, PROT_READ | PROT_WRITE | PROT_EXEC) != 0) {
        LOGE("mprotect RWX failed errno=%d", errno);
        return -2;
    }

    memcpy(target, patch, sizeof(patch));
    __builtin___clear_cache((char *)target, (char *)target + 16);

    if (make_writable(target, 16, PROT_READ | PROT_EXEC) != 0) {
        LOGE("mprotect RX restore failed errno=%d", errno);
        return -3;
    }
    return 0;
#else
    (void)target;
    (void)replacement;
    (void)saved;
    return -100;
#endif
}

int ctw_arm64_restore_16(void *target, const uint8_t saved[16]) {
#if defined(__aarch64__)
    if (!target || !saved)
        return -1;

    if (make_writable(target, 16, PROT_READ | PROT_WRITE | PROT_EXEC) != 0)
        return -2;

    memcpy(target, saved, 16);
    __builtin___clear_cache((char *)target, (char *)target + 16);
    return make_writable(target, 16, PROT_READ | PROT_EXEC) == 0 ? 0 : -3;
#else
    (void)target;
    (void)saved;
    return -100;
#endif
}

int ctw_apply_profile(const CtwPatchTargets *targets) {
    if (!targets)
        return -1;

    if (!targets->camera_update ||
        !targets->projection_setup ||
        !targets->world_stream_update ||
        !targets->sector_visibility ||
        !targets->lod_test ||
        !targets->player_render) {
        LOGI("profile incomplete; CTW remains unmodified");
        return 1;
    }

    LOGI("complete CTW patch target profile present");
    return 0;
}

int ctw_mod_init(void *original_game_handle) {
    if (!original_game_handle)
        return -1;

    LOGI("CTW3D loader active; camera mode=%d", (int)g_ctw3d_config.mode);

    CtwPatchTargets targets = {0};
    const CtwBuildProfile *profile = NULL;
    const int match_rc = ctw_profile_resolve(
        original_game_handle,
        &targets,
        &profile
    );

    if (match_rc == 1) {
        LOGI("no verified CTW build profile matched; game remains unmodified");
        return 0;
    }
    if (match_rc != 0) {
        LOGE("failed to fingerprint CTW runtime build rc=%d", match_rc);
        return match_rc;
    }

    LOGI("matched verified CTW build profile: %s", profile->name);
    const int apply_rc = ctw_apply_profile(&targets);
    if (apply_rc != 0) {
        LOGE("verified profile is incomplete rc=%d; game remains unmodified", apply_rc);
        return apply_rc;
    }

    LOGI("CTW patch target set verified and ready");
    return 0;
}

void ctw_mod_shutdown(void) {
    LOGI("CTW3D loader shutdown");
}
