#pragma once

#include "ctw_patch.h"

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

void ctw_config_set_defaults(Ctw3DConfig *config);

/*
 * Parse the CTW Mod Hub INI format into an existing config.
 * Unknown keys are ignored. Returns the number of recognized values applied,
 * or a negative value for invalid arguments.
 */
int ctw_config_parse_text(Ctw3DConfig *config, const char *text);

/* Load and parse a local INI file. Returns applied key count or a negative error. */
int ctw_config_load_file(Ctw3DConfig *config, const char *path);

/*
 * Android only: read assets/ctw_modhub.ini through the Java AssetManager
 * passed to GameNative implOnInitialSetup. Host builds return 0.
 */
int ctw_config_load_android_asset(
    Ctw3DConfig *config,
    void *jni_env,
    void *asset_manager_object
);

#ifdef __cplusplus
}
#endif
