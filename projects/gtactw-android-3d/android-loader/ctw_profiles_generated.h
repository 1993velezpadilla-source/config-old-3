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
            .projection_setup = 0x726C6Cu,
            .world_stream_update = 0x89C494u,
            .sector_visibility = 0x89CF10u,
            .lod_test = 0x70EF54u,
            .player_render = 0x888C20u,
        },
        .target_prefixes = {
            .camera_update = {
                0xFF, 0xC3, 0x02, 0xD1, 0xE8, 0x2B, 0x00, 0xFD,
                0xFD, 0x7B, 0x06, 0xA9, 0xFA, 0x67, 0x07, 0xA9,
            },
            .projection_setup = {
                0x08, 0x40, 0x40, 0x79, 0x1F, 0x21, 0x21, 0x6B,
                0x20, 0x02, 0x00, 0x54, 0xFD, 0x7B, 0xBE, 0xA9,
            },
            .world_stream_update = {
                0xFD, 0x7B, 0xBB, 0xA9, 0xFA, 0x67, 0x01, 0xA9,
                0xF8, 0x5F, 0x02, 0xA9, 0xF6, 0x57, 0x03, 0xA9,
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
                0xFD, 0x7B, 0xBE, 0xA9, 0xF3, 0x0B, 0x00, 0xF9,
                0xFD, 0x03, 0x00, 0x91, 0xF3, 0x03, 0x00, 0xAA,
            },
        },
        .adapter_names = {
            .camera_update = "ctw_camera_update_adapter_v1",
            .projection_setup = "ctw_projection_setup_adapter_v1",
            .world_stream_update = "ctw_world_stream_update_passthrough_v1",
            .sector_visibility = "ctw_world_visibility_passthrough_v1",
            .lod_test = "ctw_lod_test_passthrough_v1",
            .player_render = "ctw_player_render_passthrough_v1",
        },
    },
};

static const size_t g_ctw_profiles_count =
    sizeof(g_ctw_profiles_storage) / sizeof(g_ctw_profiles_storage[0]);
