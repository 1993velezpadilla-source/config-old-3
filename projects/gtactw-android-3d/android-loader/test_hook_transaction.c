#include "ctw_hooks.h"

#include <assert.h>
#include <stdint.h>
#include <string.h>

static int g_install_calls;
static int g_restore_calls;
static int g_fail_install_call;
static uintptr_t g_install_order[CTW_HOOK_COUNT];
static uintptr_t g_restore_order[CTW_HOOK_COUNT];

static int fake_install(
    void *target,
    void *replacement,
    uint8_t saved[16]
) {
    (void)replacement;
    const int call = g_install_calls++;
    g_install_order[call] = (uintptr_t)target;

    if (g_fail_install_call >= 0 && call == g_fail_install_call)
        return -77;

    memset(saved, call + 1, 16);
    return 0;
}

static int fake_restore(
    void *target,
    const uint8_t saved[16]
) {
    assert(saved != 0);
    g_restore_order[g_restore_calls++] = (uintptr_t)target;
    return 0;
}

static void reset_fakes(void) {
    g_install_calls = 0;
    g_restore_calls = 0;
    g_fail_install_call = -1;
    memset(g_install_order, 0, sizeof(g_install_order));
    memset(g_restore_order, 0, sizeof(g_restore_order));
}

static CtwPatchTargets make_targets(void) {
    CtwPatchTargets t = {
        .camera_update = 0x1000,
        .projection_setup = 0x2000,
        .world_stream_update = 0x3000,
        .sector_visibility = 0x4000,
        .lod_test = 0x5000,
        .player_render = 0x6000,
    };
    return t;
}

static CtwHookReplacements make_replacements(void) {
    CtwHookReplacements r = {
        .camera_update = (void *)(uintptr_t)0x11000,
        .projection_setup = (void *)(uintptr_t)0x12000,
        .world_stream_update = (void *)(uintptr_t)0x13000,
        .sector_visibility = (void *)(uintptr_t)0x14000,
        .lod_test = (void *)(uintptr_t)0x15000,
        .player_render = (void *)(uintptr_t)0x16000,
    };
    return r;
}

int main(void) {
    CtwPatchTargets targets = make_targets();
    CtwHookReplacements replacements = make_replacements();
    CtwHookTransaction tx;

    assert(ctw_hooks_prepare(&tx, &targets, &replacements) == 0);
    assert(tx.installed_count == 0);

    reset_fakes();
    g_fail_install_call = 3;
    assert(
        ctw_hooks_install_transaction(
            &tx,
            fake_install,
            fake_restore
        ) == -77
    );
    assert(g_install_calls == 4);
    assert(g_restore_calls == 3);
    assert(g_restore_order[0] == 0x3000);
    assert(g_restore_order[1] == 0x2000);
    assert(g_restore_order[2] == 0x1000);
    assert(tx.installed_count == 0);
    assert(tx.install_error == -77);
    assert(tx.rollback_error == 0);

    reset_fakes();
    assert(
        ctw_hooks_install_transaction(
            &tx,
            fake_install,
            fake_restore
        ) == 0
    );
    assert(g_install_calls == CTW_HOOK_COUNT);
    assert(tx.installed_count == CTW_HOOK_COUNT);

    assert(ctw_hooks_uninstall_all(&tx, fake_restore) == 0);
    assert(g_restore_calls == CTW_HOOK_COUNT);
    assert(g_restore_order[0] == 0x6000);
    assert(g_restore_order[5] == 0x1000);
    assert(tx.installed_count == 0);

    replacements.player_render = 0;
    assert(ctw_hooks_prepare(&tx, &targets, &replacements) == -2);

    return 0;
}
