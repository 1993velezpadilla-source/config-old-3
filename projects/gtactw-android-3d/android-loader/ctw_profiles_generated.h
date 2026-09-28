#pragma once

#include "ctw_profile.h"

/*
 * Exact CTW Android 4.4.243 ARM64 profile verified from the user-owned
 * libGame.so:
 *   SHA-256 c75e300a66317291c6afbeb4df6e0e0f9d8aef5d6ecd7bd43804a4e675d10936
 *   GNU build-id a4c441f4943abbcc72e8270ec18248e4358a89e2
 */
static const CtwBuildProfile g_ctw_profiles_storage[] = {
    {
        .name = "ctw-4.4.243-arm64-c75e300a6631",
        .expected_draw_frame_rva = 0xCF7F30u,
        .expected_initial_setup_rva = 0xCF7D28u,
        .expected_gamepad_axes_rva = 0xCF6398u,
        .target_rvas = {
            .camera_update = 0x72DFC0u,
            .projection_setup = 0x726CD8u,
            .world_stream_update = 0x89CA2Cu,
            .sector_visibility = 0x89CF10u,
            .lod_test = 0x70EF54u,
            .player_render = 0x89A770u,
        },
        .target_prefixes = {
            .camera_update = {
                0xFF, 0xC3, 0x02, 0xD1, 0xE8, 0x2B, 0x00, 0xFD,
                0xFD, 0x7B, 0x06, 0xA9, 0xFA, 0x67, 0x07, 0xA9,
            },
            .projection_setup = {
                0xFF, 0x43, 0x02, 0xD1, 0xFD, 0x7B, 0x07, 0xA9,
                0xF4, 0x4F, 0x08, 0xA9, 0xFD, 0xC3, 0x01, 0x91,
            },
            .world_stream_update = {
                0xFF, 0x03, 0x03, 0xD1, 0xFD, 0x7B, 0x06, 0xA9,
                0xFC, 0x6F, 0x07, 0xA9, 0xFA, 0x67, 0x08, 0xA9,
            },
            .sector_visibility = {
                0xFF, 0x83, 0x02, 0xD1, 0xE8, 0x1B, 0x00, 0xFD,
                0xFD, 0x7B, 0x04, 0xA9, 0xFC, 0x6F, 0x05, 0xA9,
            },
            .lod_test = {
                0xFF, 0x03, 0x01, 0xD1, 0xFD, 0x7B, 0x01, 0xA9,
                0xF5, 0x13, 0x00, 0xF9, 0xF4, 0x4F, 0x03, 0xA9,
            },
            .player_render = {
                0xFF, 0xC3, 0x02, 0xD1, 0xFD, 0x7B, 0x05, 0xA9,
                0xFC, 0x6F, 0x06, 0xA9, 0xFA, 0x67, 0x07, 0xA9,
            },
        },
        .adapter_names = {
            .camera_update = "ctw_camera_update_adapter_v1",
            .projection_setup = "ctw_projection_setup_adapter_v1",
            .world_stream_update = "ctw_world_stream_bias_adapter_v1",
            .sector_visibility = "ctw_world_visibility_bias_guard_v1",
            .lod_test = "ctw_lod_test_passthrough_v1",
            .player_render = "ctw_ped_sprite_render_adapter_v1",
        },
    },
};

static const size_t g_ctw_profiles_count =
    sizeof(g_ctw_profiles_storage) / sizeof(g_ctw_profiles_storage[0]);
