#include "ctw_adapter_registry.h"

#include <assert.h>
#include <stdint.h>
#include <string.h>

static void a0(void) {}
static void a1(void) {}
static void a2(void) {}
static void a3(void) {}
static void a4(void) {}
static void a5(void) {}

static CtwBuildProfile profile_with_names(void) {
    CtwBuildProfile p;
    memset(&p, 0, sizeof(p));
    p.adapter_names.camera_update = "a0";
    p.adapter_names.projection_setup = "a1";
    p.adapter_names.world_stream_update = "a2";
    p.adapter_names.sector_visibility = "a3";
    p.adapter_names.lod_test = "a4";
    p.adapter_names.player_render = "a5";
    return p;
}

int main(void) {
    const CtwAdapterBinding bindings[] = {
        {"a0", (void *)&a0},
        {"a1", (void *)&a1},
        {"a2", (void *)&a2},
        {"a3", (void *)&a3},
        {"a4", (void *)&a4},
        {"a5", (void *)&a5},
    };
    CtwBuildProfile profile = profile_with_names();
    CtwHookReplacements out;

    assert(
        ctw_adapter_registry_resolve_from(
            &profile,
            &out,
            bindings,
            sizeof(bindings) / sizeof(bindings[0])
        ) == 0
    );
    assert(out.camera_update == (void *)&a0);
    assert(out.projection_setup == (void *)&a1);
    assert(out.world_stream_update == (void *)&a2);
    assert(out.sector_visibility == (void *)&a3);
    assert(out.lod_test == (void *)&a4);
    assert(out.player_render == (void *)&a5);

    CtwHookReplacements missing;
    memset(&missing, 0xA5, sizeof(missing));
    assert(
        ctw_adapter_registry_resolve_from(
            &profile,
            &missing,
            bindings,
            5
        ) == 1
    );
    assert(missing.camera_update == NULL);
    assert(missing.projection_setup == NULL);
    assert(missing.world_stream_update == NULL);
    assert(missing.sector_visibility == NULL);
    assert(missing.lod_test == NULL);
    assert(missing.player_render == NULL);

    profile.adapter_names.player_render = NULL;
    assert(
        ctw_adapter_registry_resolve_from(
            &profile,
            &missing,
            bindings,
            sizeof(bindings) / sizeof(bindings[0])
        ) == 1
    );

    assert(
        ctw_adapter_registry_resolve_from(
            NULL,
            &out,
            bindings,
            sizeof(bindings) / sizeof(bindings[0])
        ) < 0
    );

    /* Compiled default table is deliberately empty for now. */
    profile = profile_with_names();
    assert(ctw_adapter_registry_resolve(&profile, &out) == 1);

    return 0;
}
