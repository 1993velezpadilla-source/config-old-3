#pragma once

#include "ctw_patch.h"

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CTW_TARGET_PREFIX_BYTES 16

typedef struct {
    uint8_t camera_update[CTW_TARGET_PREFIX_BYTES];
    uint8_t projection_setup[CTW_TARGET_PREFIX_BYTES];
    uint8_t world_stream_update[CTW_TARGET_PREFIX_BYTES];
    uint8_t sector_visibility[CTW_TARGET_PREFIX_BYTES];
    uint8_t lod_test[CTW_TARGET_PREFIX_BYTES];
    uint8_t player_render[CTW_TARGET_PREFIX_BYTES];
} CtwPatchPrefixes;

typedef struct {
    const char *camera_update;
    const char *projection_setup;
    const char *world_stream_update;
    const char *sector_visibility;
    const char *lod_test;
    const char *player_render;
} CtwAdapterNames;

typedef struct {
    const char *name;
    uintptr_t expected_draw_frame_rva;
    uintptr_t expected_initial_setup_rva;
    uintptr_t expected_gamepad_axes_rva;
    CtwPatchTargets target_rvas;
    CtwPatchPrefixes target_prefixes;
    CtwAdapterNames adapter_names;
} CtwBuildProfile;

int ctw_profile_match(
    uintptr_t library_base,
    uintptr_t draw_frame_addr,
    uintptr_t initial_setup_addr,
    uintptr_t gamepad_axes_addr,
    const CtwBuildProfile *profiles,
    size_t profile_count,
    CtwPatchTargets *absolute_targets,
    const CtwBuildProfile **matched_profile
);

int ctw_profile_compare_prefix(
    const void *address,
    const uint8_t expected[CTW_TARGET_PREFIX_BYTES]
);

int ctw_profile_verify_target_prefixes(
    void *game_handle,
    const CtwBuildProfile *profile,
    const CtwPatchTargets *targets
);

int ctw_profile_resolve(
    void *game_handle,
    CtwPatchTargets *absolute_targets,
    const CtwBuildProfile **matched_profile
);

#ifdef __cplusplus
}
#endif
