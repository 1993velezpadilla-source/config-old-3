#pragma once

#include "ctw_adapter_registry.h"

/* Exact 4.4.243 AAPCS64 adapters implemented in ctw_runtime_adapters.c. */
extern void ctw_camera_update_adapter_v1(void);
extern void ctw_projection_setup_adapter_v1(void);
extern void ctw_world_stream_bias_adapter_v1(void);
extern void ctw_world_visibility_bias_guard_v1(void);
extern void ctw_lod_test_passthrough_v1(void);
extern void ctw_ped_sprite_render_adapter_v1(void);

static const CtwAdapterBinding g_ctw_adapter_bindings_storage[] = {
    { "ctw_camera_update_adapter_v1", (void *)&ctw_camera_update_adapter_v1 },
    { "ctw_projection_setup_adapter_v1", (void *)&ctw_projection_setup_adapter_v1 },
    { "ctw_world_stream_bias_adapter_v1", (void *)&ctw_world_stream_bias_adapter_v1 },
    { "ctw_world_visibility_bias_guard_v1", (void *)&ctw_world_visibility_bias_guard_v1 },
    { "ctw_lod_test_passthrough_v1", (void *)&ctw_lod_test_passthrough_v1 },
    { "ctw_ped_sprite_render_adapter_v1", (void *)&ctw_ped_sprite_render_adapter_v1 },
};

static const size_t g_ctw_adapter_bindings_count =
    sizeof(g_ctw_adapter_bindings_storage) /
    sizeof(g_ctw_adapter_bindings_storage[0]);
