#include "ctw_hook_session.h"

#include <stdint.h>
#include <string.h>

static void values_from_targets(
    const CtwPatchTargets *targets,
    uintptr_t out[CTW_HOOK_COUNT]
) {
    out[CTW_HOOK_CAMERA_UPDATE] = targets->camera_update;
    out[CTW_HOOK_PROJECTION_SETUP] = targets->projection_setup;
    out[CTW_HOOK_WORLD_STREAM_UPDATE] = targets->world_stream_update;
    out[CTW_HOOK_SECTOR_VISIBILITY] = targets->sector_visibility;
    out[CTW_HOOK_LOD_TEST] = targets->lod_test;
    out[CTW_HOOK_PLAYER_RENDER] = targets->player_render;
}

static void values_from_replacements(
    const CtwHookReplacements *replacements,
    void *out[CTW_HOOK_COUNT]
) {
    out[CTW_HOOK_CAMERA_UPDATE] = replacements->camera_update;
    out[CTW_HOOK_PROJECTION_SETUP] = replacements->projection_setup;
    out[CTW_HOOK_WORLD_STREAM_UPDATE] = replacements->world_stream_update;
    out[CTW_HOOK_SECTOR_VISIBILITY] = replacements->sector_visibility;
    out[CTW_HOOK_LOD_TEST] = replacements->lod_test;
    out[CTW_HOOK_PLAYER_RENDER] = replacements->player_render;
}

int ctw_hook_session_uninstall_with(
    CtwHookSession *session,
    CtwBackendUninstallFn uninstall_fn
) {
    if (!session || !uninstall_fn)
        return -1;

    int first_error = 0;
    for (size_t i = CTW_HOOK_COUNT; i-- > 0;) {
        CtwHookBackendState *state = &session->states[i];
        if (!state->installed)
            continue;

        const int rc = uninstall_fn(state);
        if (rc != 0 && first_error == 0)
            first_error = rc;
    }

    size_t remaining = 0;
    for (size_t i = 0; i < CTW_HOOK_COUNT; ++i) {
        if (session->states[i].installed)
            ++remaining;
    }
    session->installed_count = remaining;
    return first_error;
}

int ctw_hook_session_install_with(
    CtwHookSession *session,
    const CtwPatchTargets *targets,
    const CtwHookReplacements *replacements,
    CtwBackendInstallFn install_fn,
    CtwBackendUninstallFn uninstall_fn
) {
    if (!session || !targets || !replacements ||
        !install_fn || !uninstall_fn) {
        return -1;
    }

    memset(session, 0, sizeof(*session));

    uintptr_t target_values[CTW_HOOK_COUNT];
    void *replacement_values[CTW_HOOK_COUNT];
    values_from_targets(targets, target_values);
    values_from_replacements(replacements, replacement_values);

    for (size_t i = 0; i < CTW_HOOK_COUNT; ++i) {
        if (!target_values[i] || !replacement_values[i]) {
            session->install_error = -2;
            break;
        }

        const int rc = install_fn(
            &session->states[i],
            (void *)target_values[i],
            replacement_values[i]
        );
        if (rc != 0) {
            session->install_error = rc;
            break;
        }
        session->installed_count = i + 1;
    }

    if (session->install_error == 0)
        return 0;

    session->rollback_error = ctw_hook_session_uninstall_with(
        session,
        uninstall_fn
    );
    return session->install_error;
}

int ctw_hook_session_install(
    CtwHookSession *session,
    const CtwPatchTargets *targets,
    const CtwHookReplacements *replacements
) {
    return ctw_hook_session_install_with(
        session,
        targets,
        replacements,
        ctw_hook_backend_install,
        ctw_hook_backend_uninstall
    );
}

int ctw_hook_session_uninstall(CtwHookSession *session) {
    return ctw_hook_session_uninstall_with(
        session,
        ctw_hook_backend_uninstall
    );
}

void *ctw_hook_session_original(
    const CtwHookSession *session,
    size_t hook_index
) {
    if (!session || hook_index >= CTW_HOOK_COUNT)
        return NULL;
    if (!session->states[hook_index].installed)
        return NULL;
    return session->states[hook_index].original;
}
