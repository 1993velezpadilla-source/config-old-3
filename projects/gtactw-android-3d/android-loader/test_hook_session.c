#include "ctw_hook_session.h"

#include <assert.h>
#include <stdint.h>
#include <string.h>

static int g_install_calls;
static int g_uninstall_calls;
static int g_fail_install_call;
static uintptr_t g_uninstall_targets[CTW_HOOK_COUNT];

static int fake_install(
    CtwHookBackendState *state,
    void *target,
    void *replacement
) {
    const int call = g_install_calls++;
    if (g_fail_install_call >= 0 && call == g_fail_install_call)
        return -55;

    memset(state, 0, sizeof(*state));
    state->kind = CTW_HOOK_BACKEND_SIMPLE_COPY;
    state->target = target;
    state->replacement = replacement;
    state->original = (void *)((uintptr_t)target + 0x100000u);
    state->installed = 1;
    return 0;
}

static int fake_uninstall(CtwHookBackendState *state) {
    assert(state != NULL);
    assert(state->installed);
    g_uninstall_targets[g_uninstall_calls++] = (uintptr_t)state->target;
    state->installed = 0;
    state->original = NULL;
    return 0;
}

static void reset_fakes(void) {
    g_install_calls = 0;
    g_uninstall_calls = 0;
    g_fail_install_call = -1;
    memset(g_uninstall_targets, 0, sizeof(g_uninstall_targets));
}

static CtwPatchTargets make_targets(void) {
    CtwPatchTargets targets = {
        .camera_update = 0x1000,
        .projection_setup = 0x2000,
        .world_stream_update = 0x3000,
        .sector_visibility = 0x4000,
        .lod_test = 0x5000,
        .player_render = 0x6000,
    };
    return targets;
}

static CtwHookReplacements make_replacements(void) {
    CtwHookReplacements replacements = {
        .camera_update = (void *)(uintptr_t)0x11000,
        .projection_setup = (void *)(uintptr_t)0x12000,
        .world_stream_update = (void *)(uintptr_t)0x13000,
        .sector_visibility = (void *)(uintptr_t)0x14000,
        .lod_test = (void *)(uintptr_t)0x15000,
        .player_render = (void *)(uintptr_t)0x16000,
    };
    return replacements;
}

int main(void) {
    CtwPatchTargets targets = make_targets();
    CtwHookReplacements replacements = make_replacements();
    CtwHookSession session;

    reset_fakes();
    assert(
        ctw_hook_session_install_with(
            &session,
            &targets,
            &replacements,
            fake_install,
            fake_uninstall
        ) == 0
    );
    assert(session.installed_count == CTW_HOOK_COUNT);
    assert(
        ctw_hook_session_original(
            &session,
            CTW_HOOK_CAMERA_UPDATE
        ) == (void *)(uintptr_t)0x101000
    );
    assert(
        ctw_hook_session_original(
            &session,
            CTW_HOOK_PLAYER_RENDER
        ) == (void *)(uintptr_t)0x106000
    );

    assert(ctw_hook_session_uninstall_with(&session, fake_uninstall) == 0);
    assert(g_uninstall_calls == CTW_HOOK_COUNT);
    assert(g_uninstall_targets[0] == 0x6000);
    assert(g_uninstall_targets[5] == 0x1000);
    assert(session.installed_count == 0);
    assert(
        ctw_hook_session_original(
            &session,
            CTW_HOOK_CAMERA_UPDATE
        ) == NULL
    );

    reset_fakes();
    g_fail_install_call = 3;
    assert(
        ctw_hook_session_install_with(
            &session,
            &targets,
            &replacements,
            fake_install,
            fake_uninstall
        ) == -55
    );
    assert(g_install_calls == 4);
    assert(g_uninstall_calls == 3);
    assert(g_uninstall_targets[0] == 0x3000);
    assert(g_uninstall_targets[1] == 0x2000);
    assert(g_uninstall_targets[2] == 0x1000);
    assert(session.installed_count == 0);
    assert(session.install_error == -55);
    assert(session.rollback_error == 0);

    replacements.lod_test = NULL;
    assert(
        ctw_hook_session_install_with(
            &session,
            &targets,
            &replacements,
            fake_install,
            fake_uninstall
        ) == -2
    );
    assert(session.installed_count == 0);

    assert(ctw_hook_session_original(NULL, 0) == NULL);
    assert(ctw_hook_session_original(&session, CTW_HOOK_COUNT) == NULL);

    return 0;
}
