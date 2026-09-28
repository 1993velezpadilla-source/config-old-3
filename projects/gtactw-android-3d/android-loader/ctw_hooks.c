#include "ctw_hooks.h"

#include <string.h>

static void clear_runtime_state(CtwHookTransaction *tx) {
    if (!tx)
        return;
    tx->installed_count = 0;
    tx->install_error = 0;
    tx->rollback_error = 0;
    for (size_t i = 0; i < CTW_HOOK_COUNT; ++i) {
        tx->slots[i].installed = 0;
        memset(tx->slots[i].saved, 0, sizeof(tx->slots[i].saved));
    }
}

int ctw_hooks_prepare(
    CtwHookTransaction *tx,
    const CtwPatchTargets *targets,
    const CtwHookReplacements *replacements
) {
    if (!tx || !targets || !replacements)
        return -1;

    memset(tx, 0, sizeof(*tx));

    const uintptr_t target_values[CTW_HOOK_COUNT] = {
        targets->camera_update,
        targets->projection_setup,
        targets->world_stream_update,
        targets->sector_visibility,
        targets->lod_test,
        targets->player_render,
    };
    void *replacement_values[CTW_HOOK_COUNT] = {
        replacements->camera_update,
        replacements->projection_setup,
        replacements->world_stream_update,
        replacements->sector_visibility,
        replacements->lod_test,
        replacements->player_render,
    };

    for (size_t i = 0; i < CTW_HOOK_COUNT; ++i) {
        if (!target_values[i] || !replacement_values[i])
            return -2;
        tx->slots[i].target = (void *)target_values[i];
        tx->slots[i].replacement = replacement_values[i];
    }

    return 0;
}

int ctw_hooks_uninstall_all(
    CtwHookTransaction *tx,
    CtwHookRestoreFn restore_fn
) {
    if (!tx || !restore_fn)
        return -1;

    int first_error = 0;
    for (size_t i = CTW_HOOK_COUNT; i-- > 0;) {
        CtwHookSlot *slot = &tx->slots[i];
        if (!slot->installed)
            continue;

        const int rc = restore_fn(slot->target, slot->saved);
        if (rc != 0 && first_error == 0)
            first_error = rc;
        if (rc == 0)
            slot->installed = 0;
    }

    size_t remaining = 0;
    for (size_t i = 0; i < CTW_HOOK_COUNT; ++i) {
        if (tx->slots[i].installed)
            ++remaining;
    }
    tx->installed_count = remaining;
    return first_error;
}

int ctw_hooks_install_transaction(
    CtwHookTransaction *tx,
    CtwHookInstallFn install_fn,
    CtwHookRestoreFn restore_fn
) {
    if (!tx || !install_fn || !restore_fn)
        return -1;

    clear_runtime_state(tx);

    for (size_t i = 0; i < CTW_HOOK_COUNT; ++i) {
        CtwHookSlot *slot = &tx->slots[i];
        if (!slot->target || !slot->replacement) {
            tx->install_error = -2;
            break;
        }

        const int rc = install_fn(
            slot->target,
            slot->replacement,
            slot->saved
        );
        if (rc != 0) {
            tx->install_error = rc;
            break;
        }

        slot->installed = 1;
        tx->installed_count = i + 1;
    }

    if (tx->install_error == 0)
        return 0;

    tx->rollback_error = ctw_hooks_uninstall_all(tx, restore_fn);
    return tx->install_error;
}
