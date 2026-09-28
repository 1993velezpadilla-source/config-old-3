#include "ctw_adapter_registry.h"
#include <ctw_adapters_generated.h>

#include <string.h>

static void *find_adapter(
    const char *name,
    const CtwAdapterBinding *bindings,
    size_t binding_count
) {
    if (!name || !name[0] || (!bindings && binding_count != 0))
        return NULL;

    for (size_t i = 0; i < binding_count; ++i) {
        const CtwAdapterBinding *binding = &bindings[i];
        if (binding->name && binding->replacement &&
            strcmp(binding->name, name) == 0) {
            return binding->replacement;
        }
    }
    return NULL;
}

int ctw_adapter_registry_resolve_from(
    const CtwBuildProfile *profile,
    CtwHookReplacements *out,
    const CtwAdapterBinding *bindings,
    size_t binding_count
) {
    if (!profile || !out || (!bindings && binding_count != 0))
        return -1;

    *out = (CtwHookReplacements){0};

    const char *names[CTW_HOOK_COUNT] = {
        profile->adapter_names.camera_update,
        profile->adapter_names.projection_setup,
        profile->adapter_names.world_stream_update,
        profile->adapter_names.sector_visibility,
        profile->adapter_names.lod_test,
        profile->adapter_names.player_render,
    };
    void **slots[CTW_HOOK_COUNT] = {
        &out->camera_update,
        &out->projection_setup,
        &out->world_stream_update,
        &out->sector_visibility,
        &out->lod_test,
        &out->player_render,
    };

    for (size_t i = 0; i < CTW_HOOK_COUNT; ++i) {
        void *replacement = find_adapter(
            names[i],
            bindings,
            binding_count
        );
        if (!replacement) {
            *out = (CtwHookReplacements){0};
            return 1;
        }
        *slots[i] = replacement;
    }

    return 0;
}

int ctw_adapter_registry_resolve(
    const CtwBuildProfile *profile,
    CtwHookReplacements *out
) {
    return ctw_adapter_registry_resolve_from(
        profile,
        out,
        g_ctw_adapter_bindings_storage,
        g_ctw_adapter_bindings_count
    );
}
