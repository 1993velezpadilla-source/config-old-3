#pragma once

#include "ctw_profile.h"

/*
 * Generated profiles live here.
 * Keep count=0 until a real user-owned libGame.so has been fingerprinted and
 * every internal RVA has been verified. Never populate this from guesses.
 */
static const CtwBuildProfile g_ctw_profiles_storage[1] = {
    {
        .name = "placeholder-no-runtime-profile",
        .expected_draw_frame_rva = 0,
        .expected_initial_setup_rva = 0,
        .expected_gamepad_axes_rva = 0,
        .target_rvas = {0, 0, 0, 0, 0, 0},
        .adapter_names = {0, 0, 0, 0, 0, 0},
    },
};

static const size_t g_ctw_profiles_count = 0;
