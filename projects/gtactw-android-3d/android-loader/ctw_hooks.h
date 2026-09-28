#pragma once

#include "ctw_patch.h"

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
    CTW_HOOK_CAMERA_UPDATE = 0,
    CTW_HOOK_PROJECTION_SETUP = 1,
    CTW_HOOK_WORLD_STREAM_UPDATE = 2,
    CTW_HOOK_SECTOR_VISIBILITY = 3,
    CTW_HOOK_LOD_TEST = 4,
    CTW_HOOK_PLAYER_RENDER = 5,
    CTW_HOOK_COUNT = 6,
};

typedef struct {
    void *camera_update;
    void *projection_setup;
    void *world_stream_update;
    void *sector_visibility;
    void *lod_test;
    void *player_render;
} CtwHookReplacements;

typedef struct {
    void *target;
    void *replacement;
    uint8_t saved[16];
    int installed;
} CtwHookSlot;

typedef struct {
    CtwHookSlot slots[CTW_HOOK_COUNT];
    size_t installed_count;
    int install_error;
    int rollback_error;
} CtwHookTransaction;

typedef int (*CtwHookInstallFn)(
    void *target,
    void *replacement,
    uint8_t saved[16]
);

typedef int (*CtwHookRestoreFn)(
    void *target,
    const uint8_t saved[16]
);

int ctw_hooks_prepare(
    CtwHookTransaction *tx,
    const CtwPatchTargets *targets,
    const CtwHookReplacements *replacements
);

int ctw_hooks_install_transaction(
    CtwHookTransaction *tx,
    CtwHookInstallFn install_fn,
    CtwHookRestoreFn restore_fn
);

int ctw_hooks_uninstall_all(
    CtwHookTransaction *tx,
    CtwHookRestoreFn restore_fn
);

#ifdef __cplusplus
}
#endif
