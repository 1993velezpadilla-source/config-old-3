#pragma once

#include "ctw_hook_backend.h"
#include "ctw_hooks.h"

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    CtwHookBackendState states[CTW_HOOK_COUNT];
    size_t installed_count;
    int install_error;
    int rollback_error;
} CtwHookSession;

typedef int (*CtwBackendInstallFn)(
    CtwHookBackendState *state,
    void *target,
    void *replacement
);

typedef int (*CtwBackendUninstallFn)(CtwHookBackendState *state);

int ctw_hook_session_install_with(
    CtwHookSession *session,
    const CtwPatchTargets *targets,
    const CtwHookReplacements *replacements,
    CtwBackendInstallFn install_fn,
    CtwBackendUninstallFn uninstall_fn
);

int ctw_hook_session_install(
    CtwHookSession *session,
    const CtwPatchTargets *targets,
    const CtwHookReplacements *replacements
);

int ctw_hook_session_uninstall_with(
    CtwHookSession *session,
    CtwBackendUninstallFn uninstall_fn
);

int ctw_hook_session_uninstall(CtwHookSession *session);

void *ctw_hook_session_original(
    const CtwHookSession *session,
    size_t hook_index
);

#ifdef __cplusplus
}
#endif
