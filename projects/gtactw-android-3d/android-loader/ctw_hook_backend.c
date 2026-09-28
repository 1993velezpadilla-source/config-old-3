#include "ctw_hook_backend.h"
#include "ctw_patch.h"

#include <string.h>

#if defined(CTW_HAVE_SHADOWHOOK)
#include <shadowhook.h>
#endif

CtwHookBackendKind ctw_hook_backend_choose(
    const uint8_t prologue[CTW_ARM64_OVERWRITE_BYTES],
    int advanced_available
) {
    if (!prologue)
        return CTW_HOOK_BACKEND_NONE;

    if (ctw_arm64_prologue_simple_copy_safe(prologue))
        return CTW_HOOK_BACKEND_SIMPLE_COPY;

    if (advanced_available)
        return CTW_HOOK_BACKEND_SHADOWHOOK;

    return CTW_HOOK_BACKEND_NONE;
}

int ctw_hook_backend_advanced_available(void) {
#if defined(CTW_HAVE_SHADOWHOOK)
    return 1;
#else
    return 0;
#endif
}

#if defined(CTW_HAVE_SHADOWHOOK)
static int ensure_shadowhook_initialized(void) {
    static int state = 0;
    if (state == 1)
        return 0;
    if (state < 0)
        return state;

    const int rc = shadowhook_init(SHADOWHOOK_MODE_UNIQUE, false);
    if (rc != 0) {
        const int err = shadowhook_get_init_errno();
        state = err > 0 ? -1000 - err : -1000 - rc;
        return state;
    }

    state = 1;
    return 0;
}
#endif

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
        ctw_hook_backend_advanced_available()
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

#if defined(CTW_HAVE_SHADOWHOOK)
    if (state->kind == CTW_HOOK_BACKEND_SHADOWHOOK) {
        const int init_rc = ensure_shadowhook_initialized();
        if (init_rc != 0)
            return init_rc;

        void *origin = NULL;
        void *stub = shadowhook_hook_func_addr(
            target,
            replacement,
            &origin
        );
        if (!stub || !origin) {
            const int err = shadowhook_get_errno();
            return -2000 - (err > 0 ? err : 1);
        }

        state->backend_cookie = stub;
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
#if defined(CTW_HAVE_SHADOWHOOK)
    else if (state->kind == CTW_HOOK_BACKEND_SHADOWHOOK) {
        rc = shadowhook_unhook(state->backend_cookie);
    }
#endif
    else {
        return -2;
    }

    if (rc == 0) {
        state->installed = 0;
        state->original = NULL;
        state->backend_cookie = NULL;
    }
    return rc;
}
