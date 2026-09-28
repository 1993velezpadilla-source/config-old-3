#include "ctw_profile.h"

#include <assert.h>
#include <stdint.h>

int main(void) {
    const uintptr_t base = 0x10000000u;

    const CtwBuildProfile profiles[] = {
        {
            .name = "fixture-build",
            .expected_draw_frame_rva = 0x1000,
            .expected_initial_setup_rva = 0x2000,
            .target_rvas = {
                .camera_update = 0x3000,
                .projection_setup = 0x4000,
                .world_stream_update = 0x5000,
                .sector_visibility = 0x6000,
                .lod_test = 0x7000,
                .player_render = 0x8000,
            },
        },
    };

    CtwPatchTargets out = {0};
    const CtwBuildProfile *matched = 0;

    int rc = ctw_profile_match(
        base,
        base + 0x1000,
        base + 0x2000,
        profiles,
        1,
        &out,
        &matched
    );
    assert(rc == 0);
    assert(matched == &profiles[0]);
    assert(out.camera_update == base + 0x3000);
    assert(out.player_render == base + 0x8000);

    out.camera_update = 123;
    matched = (const CtwBuildProfile *)1;
    rc = ctw_profile_match(
        base,
        base + 0x1111,
        base + 0x2000,
        profiles,
        1,
        &out,
        &matched
    );
    assert(rc == 1);
    assert(out.camera_update == 0);
    assert(matched == 0);

    return 0;
}
