#pragma once

#include "ctw_patch.h"

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    const char *name;
    uintptr_t expected_draw_frame_rva;
    uintptr_t expected_initial_setup_rva;
    CtwPatchTargets target_rvas;
} CtwBuildProfile;

int ctw_profile_match(
    uintptr_t library_base,
    uintptr_t draw_frame_addr,
    uintptr_t initial_setup_addr,
    const CtwBuildProfile *profiles,
    size_t profile_count,
    CtwPatchTargets *absolute_targets,
    const CtwBuildProfile **matched_profile
);

int ctw_profile_resolve(
    void *game_handle,
    CtwPatchTargets *absolute_targets,
    const CtwBuildProfile **matched_profile
);

#ifdef __cplusplus
}
#endif
