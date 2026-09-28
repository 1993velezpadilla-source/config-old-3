#include "ctw_hook_backend.h"
#include "ctw_patch.h"

#include <string.h>

#if defined(CTW_HAVE_DOBBY)
#include <dobby.h>
#endif

CtwHookBackendKind ctw_hook_backend_choose(
    const uint8_t prologue[CTW_ARM64_OVERWRITE_BYTES],
    int dobby_available
) {
    if (!prologue)
        return CTW_HOOK_BACKEND_NONE;

    if (ctw_arm64_prologue_simple_copy_safe(prologue))
        return CTW_HOOK_BACKEND_SIMPLE_COPY;

    if (dobby_available)
        return CTW_HOOK_BACKEND_DOBBY;

    return CTW_HOOK_BACKEND_NONE;
}

int ctw_hook_backend_dobby_available(void) {
#if defined(CTW_HAVE_DOBBY)
    return 1;
#else
    return 0;
#endif
}

int ctw_hook_backend_install(
    CtwHookBackendState *state,
    void *target,
    void *replacement
) {
    if (!state || !target || !replacement)
        return -1;

    memset(state, 0, sizeof(*state));
    state->target = target;
    state->replacement = replacement;

    state->kind = ctw_hook_backend_choose(
        (const uint8_t *)target,
        ctw_hook_backend_dobby_available()
    );

    if (state->kind == CTW_HOOK_BACKEND_SIMPLE_COPY) {
        int rc = ctw_arm64_create_simple_trampoline(
            target,
            &state->trampoline
        );
        if (rc != 0)
            return rc;

        rc = ctw_arm64_install_abs_jump(
            target,
            replacement,
            state->saved
        );
        if (rc != 0) {
            ctw_arm64_destroy_trampoline(&state->trampoline);
            return rc;
        }

        state->original = state->trampoline.entry;
        state->installed = 1;
        return 0;
    }

#if defined(CTW_HAVE_DOBBY)
    if (state->kind == CTW_HOOK_BACKEND_DOBBY) {
        void *origin = NULL;
        const int rc = DobbyHook(target, replacement, &origin);
        if (rc != 0 || !origin)
            return rc != 0 ? rc : -21;

        state->original = origin;
        state->installed = 1;
        return 0;
    }
#endif

    return -20;
}

int ctw_hook_backend_uninstall(CtwHookBackendState *state) {
    if (!state)
        return -1;
    if (!state->installed)
        return 0;

    int rc = 0;
    if (state->kind == CTW_HOOK_BACKEND_SIMPLE_COPY) {
        rc = ctw_arm64_restore_16(state->target, state->saved);
        if (rc == 0)
            ctw_arm64_destroy_trampoline(&state->trampoline);
    }
#if defined(CTW_HAVE_DOBBY)
    else if (state->kind == CTW_HOOK_BACKEND_DOBBY) {
        rc = DobbyDestroy(state->target);
    }
#endif
    else {
        return -2;
    }

    if (rc == 0) {
        state->installed = 0;
        state->original = NULL;
    }
    return rc;
}
