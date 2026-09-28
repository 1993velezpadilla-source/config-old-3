#pragma once

#include "ctw_trampoline.h"

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    CTW_HOOK_BACKEND_NONE = 0,
    CTW_HOOK_BACKEND_SIMPLE_COPY = 1,
    CTW_HOOK_BACKEND_SHADOWHOOK = 2,
} CtwHookBackendKind;

typedef struct {
    CtwHookBackendKind kind;
    void *target;
    void *replacement;
    void *original;
    uint8_t saved[CTW_ARM64_OVERWRITE_BYTES];
    CtwArm64Trampoline trampoline;
    void *backend_cookie;
    int installed;
} CtwHookBackendState;

CtwHookBackendKind ctw_hook_backend_choose(
    const uint8_t prologue[CTW_ARM64_OVERWRITE_BYTES],
    int advanced_available
);

int ctw_hook_backend_advanced_available(void);

int ctw_hook_backend_install(
    CtwHookBackendState *state,
    void *target,
    void *replacement
);

int ctw_hook_backend_uninstall(CtwHookBackendState *state);

#ifdef __cplusplus
}
#endif
