#define _GNU_SOURCE
#include "ctw_patch.h"
#include "ctw_camera.h"
#include "ctw_config.h"

#if defined(__ANDROID__)
#include <android/log.h>
#else
#include <stdio.h>
#endif
#include <dlfcn.h>
#include <pthread.h>
#include <stdint.h>
#include <string.h>

#define EXPORT __attribute__((visibility("default")))
#define LOG_TAG "CTW3D"

#if defined(__ANDROID__)
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)
#else
#define LOGI(...) do { fprintf(stderr, LOG_TAG ": "); fprintf(stderr, __VA_ARGS__); fprintf(stderr, "\n"); } while (0)
#define LOGE(...) LOGI(__VA_ARGS__)
#endif

static pthread_once_t g_once = PTHREAD_ONCE_INIT;
static void *g_game = NULL;

static void loader_location_anchor(void) {
}

static int build_original_same_dir_path(char *out, size_t capacity) {
    if (!out || capacity == 0)
        return -1;

    Dl_info info;
    if (dladdr((void *)&loader_location_anchor, &info) == 0 ||
        !info.dli_fname || !info.dli_fname[0]) {
        return -2;
    }

    const char *slash = strrchr(info.dli_fname, '/');
    if (!slash)
        return -3;

    static const char leaf[] = "libGame_orig.so";
    const size_t dir_len = (size_t)(slash - info.dli_fname) + 1u;
    if (dir_len + sizeof(leaf) > capacity)
        return -4;

    memcpy(out, info.dli_fname, dir_len);
    memcpy(out + dir_len, leaf, sizeof(leaf));
    return 0;
}

static void load_original_once(void) {
    g_game = dlopen("libGame_orig.so", RTLD_NOW | RTLD_LOCAL);
    if (!g_game) {
        const char *first_error = dlerror();
        LOGI(
            "basename dlopen for libGame_orig.so failed: %s; "
            "trying proxy directory",
            first_error ? first_error : "(unknown)"
        );

        char path[4096];
        const int path_rc = build_original_same_dir_path(
            path,
            sizeof(path)
        );
        if (path_rc == 0) {
            g_game = dlopen(path, RTLD_NOW | RTLD_LOCAL);
            if (g_game)
                LOGI("loaded original CTW from proxy directory");
        } else {
            LOGE(
                "failed to derive proxy directory for libGame_orig.so rc=%d",
                path_rc
            );
        }
    }

    if (!g_game) {
        const char *error = dlerror();
        LOGE(
            "failed to load original libGame_orig.so: %s",
            error ? error : "(unknown)"
        );
        return;
    }

    LOGI("loaded original CTW libGame_orig.so");
    ctw_mod_init(g_game);
}

static void *game_symbol(const char *name) {
    pthread_once(&g_once, load_original_once);
    if (!g_game)
        return NULL;

    dlerror();
    void *p = dlsym(g_game, name);
    const char *err = dlerror();
    if (err) {
        LOGE("missing original symbol %s: %s", name, err);
        return NULL;
    }
    return p;
}

#define JNI_NAME2(name) Java_com_rockstargames_oswrapper_GameNative_##name
#define JNI_NAME(name) JNI_NAME2(name)
#define JNI_SYMBOL(name) "Java_com_rockstargames_oswrapper_GameNative_" #name
#define RESOLVE(sym, type) ((type)game_symbol(JNI_SYMBOL(sym)))

typedef void (*FnVV)(void *, void *);
typedef int (*FnIVV)(void *, void *);

EXPORT int JNI_OnLoad(void *vm, void *reserved) {
    pthread_once(&g_once, load_original_once);
    if (!g_game)
        return 0;

    typedef int (*Fn)(void *, void *);
    Fn original = (Fn)dlsym(g_game, "JNI_OnLoad");
    if (original)
        return original(vm, reserved);

    return 0x00010006; /* JNI_VERSION_1_6 */
}

EXPORT void JNI_OnUnload(void *vm, void *reserved) {
    if (g_game) {
        typedef void (*Fn)(void *, void *);
        Fn original = (Fn)dlsym(g_game, "JNI_OnUnload");
        if (original)
            original(vm, reserved);
    }
    ctw_mod_shutdown();
}

EXPORT void JNI_NAME(implOnActivityCreated)(void *env, void *cls, void *services, int first_run) {
    typedef void (*Fn)(void *, void *, void *, int);
    Fn fn = RESOLVE(implOnActivityCreated, Fn);
    if (fn) fn(env, cls, services, first_run);
}

EXPORT void JNI_NAME(implOnActivityDestroyed)(void *env, void *cls) {
    FnVV fn = RESOLVE(implOnActivityDestroyed, FnVV);
    if (fn) fn(env, cls);
}

EXPORT void JNI_NAME(implOnInitialSetup)(void *env, void *cls, void *device_info, void *asset_mgr, void *paths, void *args) {
    const int config_rc = ctw_config_load_android_asset(
        &g_ctw3d_config,
        env,
        asset_mgr
    );
    if (config_rc > 0) {
        ctw_camera_set_mode(g_ctw3d_config.mode);
        LOGI("loaded CTW Mod Hub asset config values=%d", config_rc);
    } else if (config_rc < 0) {
        LOGE("failed to load CTW Mod Hub asset config rc=%d", config_rc);
    }
    ctw_camera_runtime_reset(&g_ctw3d_config);

    typedef void (*Fn)(void *, void *, void *, void *, void *, void *);
    Fn fn = RESOLVE(implOnInitialSetup, Fn);
    if (fn) fn(env, cls, device_info, asset_mgr, paths, args);
}

EXPORT void JNI_NAME(implOnSurfaceCreated)(void *env, void *cls) {
    FnVV fn = RESOLVE(implOnSurfaceCreated, FnVV);
    if (fn) fn(env, cls);
}

EXPORT void JNI_NAME(implOnSurfaceChanged)(void *env, void *cls, void *surface, int w, int h) {
    typedef void (*Fn)(void *, void *, void *, int, int);
    Fn fn = RESOLVE(implOnSurfaceChanged, Fn);
    if (fn) fn(env, cls, surface, w, h);
}

EXPORT void JNI_NAME(implOnSurfaceDestroyed)(void *env, void *cls) {
    FnVV fn = RESOLVE(implOnSurfaceDestroyed, FnVV);
    if (fn) fn(env, cls);
}

EXPORT void JNI_NAME(implOnGameResume)(void *env, void *cls) {
    FnVV fn = RESOLVE(implOnGameResume, FnVV);
    if (fn) fn(env, cls);
}

EXPORT void JNI_NAME(implOnGamePause)(void *env, void *cls) {
    FnVV fn = RESOLVE(implOnGamePause, FnVV);
    if (fn) fn(env, cls);
}

EXPORT void JNI_NAME(implOnLowMemory)(void *env, void *cls) {
    FnVV fn = RESOLVE(implOnLowMemory, FnVV);
    if (fn) fn(env, cls);
}

EXPORT void JNI_NAME(implOnBackButtonPressed)(void *env, void *cls) {
    FnVV fn = RESOLVE(implOnBackButtonPressed, FnVV);
    if (fn) fn(env, cls);
}

EXPORT void JNI_NAME(implOnDrawFrame)(void *env, void *cls, float dt) {
    ctw_camera_runtime_step(&g_ctw3d_config, dt);

    typedef void (*Fn)(void *, void *, float);
    Fn fn = RESOLVE(implOnDrawFrame, Fn);
    if (fn) fn(env, cls, dt);
}

#define GAMEPAD_ID_FORWARD(name) \
EXPORT void JNI_NAME(name)(void *env, void *cls, int id) { \
    typedef void (*Fn)(void *, void *, int); \
    Fn fn = RESOLVE(name, Fn); \
    if (fn) fn(env, cls, id); \
}

GAMEPAD_ID_FORWARD(implOnGamepadConnected)
GAMEPAD_ID_FORWARD(implOnGamepadDisconnected)

EXPORT void JNI_NAME(implOnGamepadResume)(void *env, void *cls, void *ids) {
    typedef void (*Fn)(void *, void *, void *);
    Fn fn = RESOLVE(implOnGamepadResume, Fn);
    if (fn) fn(env, cls, ids);
}

EXPORT void JNI_NAME(implOnGamepadButtonDown)(void *env, void *cls, int id, int keycode) {
    typedef void (*Fn)(void *, void *, int, int);

    const CtwCameraButtonAction camera_action =
        ctw_camera_handle_gamepad_button_down(
            keycode,
            &g_ctw3d_config
        );
    if (camera_action == CTW_CAMERA_BUTTON_MODE_CYCLED) {
        const CtwCameraInputSnapshot s = ctw_camera_snapshot();
        LOGI("camera mode -> %d", (int)s.mode);
    } else if (camera_action == CTW_CAMERA_BUTTON_ORBIT_RESET) {
        LOGI("camera orbit reset");
    }

    Fn fn = RESOLVE(implOnGamepadButtonDown, Fn);
    if (fn) fn(env, cls, id, keycode);
}

EXPORT void JNI_NAME(implOnGamepadButtonUp)(void *env, void *cls, int id, int keycode) {
    typedef void (*Fn)(void *, void *, int, int);
    Fn fn = RESOLVE(implOnGamepadButtonUp, Fn);
    if (fn) fn(env, cls, id, keycode);
}

EXPORT void JNI_NAME(implOnGamepadAxesChanged)(
    void *env, void *cls, int id,
    float lx, float ly, float rx, float ry, float lt, float rt
) {
    ctw_camera_set_look(rx, ry);

    typedef void (*Fn)(void *, void *, int, float, float, float, float, float, float);
    Fn fn = RESOLVE(implOnGamepadAxesChanged, Fn);
    if (fn) fn(env, cls, id, lx, ly, rx, ry, lt, rt);
}

EXPORT void JNI_NAME(implOnAccelerometerChanged)(void *env, void *cls, float x, float y, float z) {
    typedef void (*Fn)(void *, void *, float, float, float);
    Fn fn = RESOLVE(implOnAccelerometerChanged, Fn);
    if (fn) fn(env, cls, x, y, z);
}

#define TOUCH_FORWARD(name) \
EXPORT void JNI_NAME(name)(void *env, void *cls, int id, float x, float y) { \
    typedef void (*Fn)(void *, void *, int, float, float); \
    Fn fn = RESOLVE(name, Fn); \
    if (fn) fn(env, cls, id, x, y); \
}

TOUCH_FORWARD(implOnTouchStart)
TOUCH_FORWARD(implOnTouchMove)
TOUCH_FORWARD(implOnTouchEnd)

EXPORT void JNI_NAME(implOnNetworkChanged)(void *env, void *cls, int type) {
    typedef void (*Fn)(void *, void *, int);
    Fn fn = RESOLVE(implOnNetworkChanged, Fn);
    if (fn) fn(env, cls, type);
}

EXPORT void JNI_NAME(implOnPlaylistOpenComplete)(void *env, void *cls, int success, int count) {
    typedef void (*Fn)(void *, void *, int, int);
    Fn fn = RESOLVE(implOnPlaylistOpenComplete, Fn);
    if (fn) fn(env, cls, success, count);
}

EXPORT void JNI_NAME(implOnRockstarCloudDisabledComplete)(void *env, void *cls) {
    FnVV fn = RESOLVE(implOnRockstarCloudDisabledComplete, FnVV);
    if (fn) fn(env, cls);
}

EXPORT void JNI_NAME(implOnRockstarGateComplete)(void *env, void *cls, int accepted) {
    typedef void (*Fn)(void *, void *, int);
    Fn fn = RESOLVE(implOnRockstarGateComplete, Fn);
    if (fn) fn(env, cls, accepted);
}

#define PTR_FORWARD(name) \
EXPORT void JNI_NAME(name)(void *env, void *cls, void *value) { \
    typedef void (*Fn)(void *, void *, void *); \
    Fn fn = RESOLVE(name, Fn); \
    if (fn) fn(env, cls, value); \
}

PTR_FORWARD(implOnRockstarIdChanged)

EXPORT void JNI_NAME(implOnRockstarInitialComplete)(void *env, void *cls) {
    FnVV fn = RESOLVE(implOnRockstarInitialComplete, FnVV);
    if (fn) fn(env, cls);
}

EXPORT void JNI_NAME(implOnRockstarSetup)(void *env, void *cls, void *environment, void *title_id) {
    typedef void (*Fn)(void *, void *, void *, void *);
    Fn fn = RESOLVE(implOnRockstarSetup, Fn);
    if (fn) fn(env, cls, environment, title_id);
}

EXPORT void JNI_NAME(implOnRockstarSignInComplete)(void *env, void *cls) {
    FnVV fn = RESOLVE(implOnRockstarSignInComplete, FnVV);
    if (fn) fn(env, cls);
}

EXPORT void JNI_NAME(implOnRockstarSignOutComplete)(void *env, void *cls) {
    FnVV fn = RESOLVE(implOnRockstarSignOutComplete, FnVV);
    if (fn) fn(env, cls);
}

EXPORT void JNI_NAME(implOnRockstarStateChanged)(void *env, void *cls, int signed_in) {
    typedef void (*Fn)(void *, void *, int);
    Fn fn = RESOLVE(implOnRockstarStateChanged, Fn);
    if (fn) fn(env, cls, signed_in);
}

PTR_FORWARD(implOnRockstarTicketChanged)

EXPORT int JNI_NAME(implIsInitialized)(void *env, void *cls) {
    FnIVV fn = RESOLVE(implIsInitialized, FnIVV);
    return fn ? fn(env, cls) : 0;
}
