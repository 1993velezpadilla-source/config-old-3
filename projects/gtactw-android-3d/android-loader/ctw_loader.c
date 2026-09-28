#include "ctw_patch.h"

#include <android/log.h>
#include <dlfcn.h>
#include <pthread.h>
#include <stdint.h>
#include <stdlib.h>

#define EXPORT __attribute__((visibility("default")))
#define LOG_TAG "CTW3D"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

static pthread_once_t g_once = PTHREAD_ONCE_INIT;
static void *g_game = NULL;

static void load_original_once(void) {
    g_game = dlopen("libGame_orig.so", RTLD_NOW | RTLD_LOCAL);
    if (!g_game) {
        LOGE("failed to load libGame_orig.so: %s", dlerror());
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

#define JNI_PREFIX Java_com_rockstargames_oswrapper_GameNative_
#define STR2(x) #x
#define STR(x) STR2(x)
#define RESOLVE(sym, type) ((type)game_symbol(STR(JNI_PREFIX) #sym))

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

    /* JNI_VERSION_1_6 */
    return 0x00010006;
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

EXPORT void JNI_PREFIX implOnActivityCreated(void *env, void *cls, void *services, int is_first_run) {
    typedef void (*Fn)(void *, void *, void *, int);
    Fn fn = RESOLVE(implOnActivityCreated, Fn);
    if (fn) fn(env, cls, services, is_first_run);
}

EXPORT void JNI_PREFIX implOnActivityDestroyed(void *env, void *cls) {
    FnVV fn = RESOLVE(implOnActivityDestroyed, FnVV);
    if (fn) fn(env, cls);
}

EXPORT void JNI_PREFIX implOnInitialSetup(void *env, void *cls, void *device_info, void *asset_mgr, void *paths, void *args) {
    typedef void (*Fn)(void *, void *, void *, void *, void *, void *);
    Fn fn = RESOLVE(implOnInitialSetup, Fn);
    if (fn) fn(env, cls, device_info, asset_mgr, paths, args);
}

EXPORT void JNI_PREFIX implOnSurfaceCreated(void *env, void *cls) {
    FnVV fn = RESOLVE(implOnSurfaceCreated, FnVV);
    if (fn) fn(env, cls);
}

EXPORT void JNI_PREFIX implOnSurfaceChanged(void *env, void *cls, void *surface, int w, int h) {
    typedef void (*Fn)(void *, void *, void *, int, int);
    Fn fn = RESOLVE(implOnSurfaceChanged, Fn);
    if (fn) fn(env, cls, surface, w, h);
}

EXPORT void JNI_PREFIX implOnSurfaceDestroyed(void *env, void *cls) {
    FnVV fn = RESOLVE(implOnSurfaceDestroyed, FnVV);
    if (fn) fn(env, cls);
}

EXPORT void JNI_PREFIX implOnGameResume(void *env, void *cls) {
    FnVV fn = RESOLVE(implOnGameResume, FnVV);
    if (fn) fn(env, cls);
}

EXPORT void JNI_PREFIX implOnGamePause(void *env, void *cls) {
    FnVV fn = RESOLVE(implOnGamePause, FnVV);
    if (fn) fn(env, cls);
}

EXPORT void JNI_PREFIX implOnLowMemory(void *env, void *cls) {
    FnVV fn = RESOLVE(implOnLowMemory, FnVV);
    if (fn) fn(env, cls);
}

EXPORT void JNI_PREFIX implOnBackButtonPressed(void *env, void *cls) {
    FnVV fn = RESOLVE(implOnBackButtonPressed, FnVV);
    if (fn) fn(env, cls);
}

EXPORT void JNI_PREFIX implOnDrawFrame(void *env, void *cls, float dt) {
    typedef void (*Fn)(void *, void *, float);
    Fn fn = RESOLVE(implOnDrawFrame, Fn);
    if (fn) fn(env, cls, dt);
}

EXPORT void JNI_PREFIX implOnGamepadConnected(void *env, void *cls, int id) {
    typedef void (*Fn)(void *, void *, int);
    Fn fn = RESOLVE(implOnGamepadConnected, Fn);
    if (fn) fn(env, cls, id);
}

EXPORT void JNI_PREFIX implOnGamepadDisconnected(void *env, void *cls, int id) {
    typedef void (*Fn)(void *, void *, int);
    Fn fn = RESOLVE(implOnGamepadDisconnected, Fn);
    if (fn) fn(env, cls, id);
}

EXPORT void JNI_PREFIX implOnGamepadResume(void *env, void *cls, void *ids) {
    typedef void (*Fn)(void *, void *, void *);
    Fn fn = RESOLVE(implOnGamepadResume, Fn);
    if (fn) fn(env, cls, ids);
}

EXPORT void JNI_PREFIX implOnGamepadButtonDown(void *env, void *cls, int id, int keycode) {
    typedef void (*Fn)(void *, void *, int, int);
    Fn fn = RESOLVE(implOnGamepadButtonDown, Fn);
    if (fn) fn(env, cls, id, keycode);
}

EXPORT void JNI_PREFIX implOnGamepadButtonUp(void *env, void *cls, int id, int keycode) {
    typedef void (*Fn)(void *, void *, int, int);
    Fn fn = RESOLVE(implOnGamepadButtonUp, Fn);
    if (fn) fn(env, cls, id, keycode);
}

EXPORT void JNI_PREFIX implOnGamepadAxesChanged(
    void *env, void *cls, int id,
    float lx, float ly, float rx, float ry, float lt, float rt
) {
    typedef void (*Fn)(void *, void *, int, float, float, float, float, float, float);
    Fn fn = RESOLVE(implOnGamepadAxesChanged, Fn);
    if (fn) fn(env, cls, id, lx, ly, rx, ry, lt, rt);
}

EXPORT void JNI_PREFIX implOnAccelerometerChanged(void *env, void *cls, float x, float y, float z) {
    typedef void (*Fn)(void *, void *, float, float, float);
    Fn fn = RESOLVE(implOnAccelerometerChanged, Fn);
    if (fn) fn(env, cls, x, y, z);
}

#define TOUCH_FORWARD(name) \
EXPORT void JNI_PREFIX name(void *env, void *cls, int id, float x, float y) { \
    typedef void (*Fn)(void *, void *, int, float, float); \
    Fn fn = RESOLVE(name, Fn); \
    if (fn) fn(env, cls, id, x, y); \
}

TOUCH_FORWARD(implOnTouchStart)
TOUCH_FORWARD(implOnTouchMove)
TOUCH_FORWARD(implOnTouchEnd)

EXPORT void JNI_PREFIX implOnNetworkChanged(void *env, void *cls, int type) {
    typedef void (*Fn)(void *, void *, int);
    Fn fn = RESOLVE(implOnNetworkChanged, Fn);
    if (fn) fn(env, cls, type);
}

EXPORT void JNI_PREFIX implOnPlaylistOpenComplete(void *env, void *cls, int success, int count) {
    typedef void (*Fn)(void *, void *, int, int);
    Fn fn = RESOLVE(implOnPlaylistOpenComplete, Fn);
    if (fn) fn(env, cls, success, count);
}

EXPORT void JNI_PREFIX implOnRockstarCloudDisabledComplete(void *env, void *cls) {
    FnVV fn = RESOLVE(implOnRockstarCloudDisabledComplete, FnVV);
    if (fn) fn(env, cls);
}

EXPORT void JNI_PREFIX implOnRockstarGateComplete(void *env, void *cls, int accepted) {
    typedef void (*Fn)(void *, void *, int);
    Fn fn = RESOLVE(implOnRockstarGateComplete, Fn);
    if (fn) fn(env, cls, accepted);
}

EXPORT void JNI_PREFIX implOnRockstarIdChanged(void *env, void *cls, void *id) {
    typedef void (*Fn)(void *, void *, void *);
    Fn fn = RESOLVE(implOnRockstarIdChanged, Fn);
    if (fn) fn(env, cls, id);
}

EXPORT void JNI_PREFIX implOnRockstarInitialComplete(void *env, void *cls) {
    FnVV fn = RESOLVE(implOnRockstarInitialComplete, FnVV);
    if (fn) fn(env, cls);
}

EXPORT void JNI_PREFIX implOnRockstarSetup(void *env, void *cls, void *environment, void *title_id) {
    typedef void (*Fn)(void *, void *, void *, void *);
    Fn fn = RESOLVE(implOnRockstarSetup, Fn);
    if (fn) fn(env, cls, environment, title_id);
}

EXPORT void JNI_PREFIX implOnRockstarSignInComplete(void *env, void *cls) {
    FnVV fn = RESOLVE(implOnRockstarSignInComplete, FnVV);
    if (fn) fn(env, cls);
}

EXPORT void JNI_PREFIX implOnRockstarSignOutComplete(void *env, void *cls) {
    FnVV fn = RESOLVE(implOnRockstarSignOutComplete, FnVV);
    if (fn) fn(env, cls);
}

EXPORT void JNI_PREFIX implOnRockstarStateChanged(void *env, void *cls, int signed_in) {
    typedef void (*Fn)(void *, void *, int);
    Fn fn = RESOLVE(implOnRockstarStateChanged, Fn);
    if (fn) fn(env, cls, signed_in);
}

EXPORT void JNI_PREFIX implOnRockstarTicketChanged(void *env, void *cls, void *ticket) {
    typedef void (*Fn)(void *, void *, void *);
    Fn fn = RESOLVE(implOnRockstarTicketChanged, Fn);
    if (fn) fn(env, cls, ticket);
}

EXPORT int JNI_PREFIX implIsInitialized(void *env, void *cls) {
    FnIVV fn = RESOLVE(implIsInitialized, FnIVV);
    return fn ? fn(env, cls) : 0;
}
