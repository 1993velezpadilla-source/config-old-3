#include "ctw_patch.h"

#include <assert.h>

int main(void) {
    CtwPatchTargets incomplete = {
        .camera_update = 1,
        .projection_setup = 2,
        .world_stream_update = 3,
        .sector_visibility = 4,
        .lod_test = 5,
        .player_render = 0,
    };
    assert(
        ctw_apply_profile(&incomplete) ==
        CTW_PATCH_PROFILE_INCOMPLETE
    );

    CtwPatchTargets complete = {
        .camera_update = 1,
        .projection_setup = 2,
        .world_stream_update = 3,
        .sector_visibility = 4,
        .lod_test = 5,
        .player_render = 6,
    };
    assert(
        ctw_apply_profile(&complete) ==
        CTW_PATCH_ADAPTERS_PENDING
    );

    assert(ctw_apply_profile(0) == -1);
    return 0;
}
