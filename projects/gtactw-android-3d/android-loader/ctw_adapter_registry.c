#include "ctw_adapter_registry.h"
#include "ctw_adapters_generated.h"

#include <string.h>

static void *find_adapter(const char *name) {
    if (!name || !name[0])
        return NULL;

    for (size_t i = 0; i < g_ctw_adapter_bindings_count; ++i) {
        const CtwGeneratedAdapterBinding *binding =
            &g_ctw_adapter_bindings_storage[i];
        if (binding->name && binding->replacement &&
            strcmp(binding->name, name) == 0) {
            return binding->replacement;
        }
    }
    return NULL;
}

int ctw_adapter_registry_resolve(
    const CtwBuildProfile *profile,
    CtwHookReplacements *out
) {
    if (!profile || !out)
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
        void *replacement = find_adapter(names[i]);
        if (!replacement) {
            *out = (CtwHookReplacements){0};
            return 1;
        }
        *slots[i] = replacement;
    }

    return 0;
}
