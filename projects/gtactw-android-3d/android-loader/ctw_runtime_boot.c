#include "ctw_patch.h"
#include "ctw_profile.h"

#if defined(__ANDROID__)
#include <android/log.h>
#else
#include <stdio.h>
#endif

#define LOG_TAG "CTW3D"
#if defined(__ANDROID__)
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)
#else
#define LOGI(...) do { fprintf(stderr, LOG_TAG ": "); fprintf(stderr, __VA_ARGS__); fputc('\n', stderr); } while (0)
#define LOGE(...) LOGI(__VA_ARGS__)
#endif

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

    const int signature_rc = ctw_profile_verify_target_prefixes(
        original_game_handle,
        profile,
        &targets
    );
    if (signature_rc != 0) {
        LOGE(
            "CTW target byte signature mismatch rc=%d; game remains unmodified",
            signature_rc
        );
        return signature_rc;
    }
    LOGI("CTW target byte signatures verified");

    const int apply_rc = ctw_apply_profile(&targets);
    if (apply_rc == CTW_PATCH_ADAPTERS_PENDING) {
        LOGI(
            "CTW target profile verified; hooks intentionally not installed "
            "until ABI adapters are verified"
        );
        return 0;
    }
    if (apply_rc != CTW_PATCH_APPLIED) {
        LOGE(
            "verified profile cannot be applied rc=%d; game remains unmodified",
            apply_rc
        );
        return apply_rc;
    }

    LOGI("CTW runtime hooks installed");
    return 0;
}

void ctw_mod_shutdown(void) {
    LOGI("CTW3D loader shutdown");
}
