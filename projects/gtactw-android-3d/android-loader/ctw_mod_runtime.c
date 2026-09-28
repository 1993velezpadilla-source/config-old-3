#define _GNU_SOURCE
#include "ctw_patch.h"
#include "ctw_mod_runtime.h"

#include "ctw_adapter_registry.h"
#include "ctw_hook_session.h"
#include "ctw_profile.h"

#if defined(__ANDROID__)
#include <android/log.h>
#else
#include <stdio.h>
#endif

#include <string.h>

#define LOG_TAG "CTW3D"
#if defined(__ANDROID__)
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)
#else
#define LOGI(...) do { fprintf(stderr, LOG_TAG ": "); fprintf(stderr, __VA_ARGS__); fputc('\n', stderr); } while (0)
#define LOGE(...) LOGI(__VA_ARGS__)
#endif

static CtwHookSession g_ctw_hook_session;
static int g_ctw_hook_session_active = 0;

static int targets_complete(const CtwPatchTargets *targets) {
    return targets &&
        targets->camera_update &&
        targets->projection_setup &&
        targets->world_stream_update &&
        targets->sector_visibility &&
        targets->lod_test &&
        targets->player_render;
}

int ctw_mod_init(void *original_game_handle) {
    if (!original_game_handle)
        return -1;

    if (g_ctw_hook_session_active) {
        LOGI("CTW runtime hooks already active");
        return CTW_PATCH_APPLIED;
    }

    CtwPatchTargets targets;
    memset(&targets, 0, sizeof(targets));
    const CtwBuildProfile *profile = NULL;

    const int resolve_rc = ctw_profile_resolve(
        original_game_handle,
        &targets,
        &profile
    );
    if (resolve_rc == 1) {
        LOGI("no verified CTW runtime profile matched; game remains unmodified");
        return CTW_PATCH_PROFILE_NOT_FOUND;
    }
    if (resolve_rc != 0 || !profile) {
        LOGE("failed to resolve CTW runtime profile rc=%d", resolve_rc);
        return CTW_PATCH_PROFILE_RESOLVE_FAILED;
    }

    if (!targets_complete(&targets)) {
        LOGE("matched CTW profile has incomplete target set");
        return CTW_PATCH_PROFILE_INCOMPLETE;
    }

    const int signature_rc = ctw_profile_verify_target_prefixes(
        original_game_handle,
        profile,
        &targets
    );
    if (signature_rc != 0) {
        LOGE(
            "CTW target signature verification failed rc=%d; "
            "game remains unmodified",
            signature_rc
        );
        return CTW_PATCH_SIGNATURE_MISMATCH;
    }

    CtwHookReplacements replacements;
    memset(&replacements, 0, sizeof(replacements));
    const int adapters_rc = ctw_adapter_registry_resolve(
        profile,
        &replacements
    );
    if (adapters_rc != 0) {
        LOGI(
            "verified profile matched but compiled adapters are incomplete "
            "rc=%d; game remains unmodified",
            adapters_rc
        );
        return CTW_PATCH_ADAPTERS_PENDING;
    }

    memset(&g_ctw_hook_session, 0, sizeof(g_ctw_hook_session));
    const int hook_rc = ctw_hook_session_install(
        &g_ctw_hook_session,
        &targets,
        &replacements
    );
    if (hook_rc != 0) {
        LOGE(
            "CTW hook transaction failed rc=%d rollback_rc=%d",
            hook_rc,
            g_ctw_hook_session.rollback_error
        );
        return CTW_PATCH_HOOK_INSTALL_FAILED;
    }

    if (g_ctw_hook_session.installed_count != CTW_HOOK_COUNT) {
        LOGE(
            "CTW hook session incomplete count=%zu; rolling back",
            g_ctw_hook_session.installed_count
        );
        (void)ctw_hook_session_uninstall(&g_ctw_hook_session);
        return CTW_PATCH_HOOK_INSTALL_FAILED;
    }

    g_ctw_hook_session_active = 1;
    LOGI("CTW 3D runtime hooks installed atomically: %d/%d", CTW_HOOK_COUNT, CTW_HOOK_COUNT);
    return CTW_PATCH_APPLIED;
}

void ctw_mod_shutdown(void) {
    if (!g_ctw_hook_session_active)
        return;

    const int rc = ctw_hook_session_uninstall(&g_ctw_hook_session);
    if (rc != 0 || g_ctw_hook_session.installed_count != 0) {
        LOGE(
            "CTW runtime hook shutdown incomplete rc=%d remaining=%zu",
            rc,
            g_ctw_hook_session.installed_count
        );
        return;
    }

    g_ctw_hook_session_active = 0;
    LOGI("CTW runtime hooks removed");
}


void *ctw_mod_original_for_hook(size_t hook_index) {
    if (!g_ctw_hook_session_active)
        return NULL;
    return ctw_hook_session_original(
        &g_ctw_hook_session,
        hook_index
    );
}

int ctw_mod_hooks_active(void) {
    return g_ctw_hook_session_active &&
        g_ctw_hook_session.installed_count == CTW_HOOK_COUNT;
}
