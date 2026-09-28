#define _GNU_SOURCE
#include "ctw_profile.h"
#include "ctw_profiles_generated.h"

#include <dlfcn.h>
#include <stdint.h>
#include <string.h>

#define DRAW_FRAME_SYMBOL "Java_com_rockstargames_oswrapper_GameNative_implOnDrawFrame"
#define INITIAL_SETUP_SYMBOL "Java_com_rockstargames_oswrapper_GameNative_implOnInitialSetup"

static uintptr_t absolute_from_rva(uintptr_t base, uintptr_t rva) {
    return rva ? base + rva : 0;
}

int ctw_profile_match(
    uintptr_t library_base,
    uintptr_t draw_frame_addr,
    uintptr_t initial_setup_addr,
    const CtwBuildProfile *profiles,
    size_t profile_count,
    CtwPatchTargets *absolute_targets,
    const CtwBuildProfile **matched_profile
) {
    if (!library_base || !draw_frame_addr || !initial_setup_addr ||
        !absolute_targets || (!profiles && profile_count != 0)) {
        return -1;
    }

    memset(absolute_targets, 0, sizeof(*absolute_targets));
    if (matched_profile)
        *matched_profile = NULL;

    const uintptr_t draw_rva = draw_frame_addr - library_base;
    const uintptr_t setup_rva = initial_setup_addr - library_base;

    for (size_t i = 0; i < profile_count; ++i) {
        const CtwBuildProfile *p = &profiles[i];
        if (!p->expected_draw_frame_rva || !p->expected_initial_setup_rva)
            continue;
        if (p->expected_draw_frame_rva != draw_rva ||
            p->expected_initial_setup_rva != setup_rva) {
            continue;
        }

        absolute_targets->camera_update =
            absolute_from_rva(library_base, p->target_rvas.camera_update);
        absolute_targets->projection_setup =
            absolute_from_rva(library_base, p->target_rvas.projection_setup);
        absolute_targets->world_stream_update =
            absolute_from_rva(library_base, p->target_rvas.world_stream_update);
        absolute_targets->sector_visibility =
            absolute_from_rva(library_base, p->target_rvas.sector_visibility);
        absolute_targets->lod_test =
            absolute_from_rva(library_base, p->target_rvas.lod_test);
        absolute_targets->player_render =
            absolute_from_rva(library_base, p->target_rvas.player_render);

        if (matched_profile)
            *matched_profile = p;
        return 0;
    }

    return 1;
}

int ctw_profile_resolve(
    void *game_handle,
    CtwPatchTargets *absolute_targets,
    const CtwBuildProfile **matched_profile
) {
    if (!game_handle || !absolute_targets)
        return -1;

    void *draw = dlsym(game_handle, DRAW_FRAME_SYMBOL);
    void *setup = dlsym(game_handle, INITIAL_SETUP_SYMBOL);
    if (!draw || !setup)
        return -2;

    Dl_info info;
    if (dladdr(draw, &info) == 0 || !info.dli_fbase)
        return -3;

    return ctw_profile_match(
        (uintptr_t)info.dli_fbase,
        (uintptr_t)draw,
        (uintptr_t)setup,
        g_ctw_profiles_storage,
        g_ctw_profiles_count,
        absolute_targets,
        matched_profile
    );
}
