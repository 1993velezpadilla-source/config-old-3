#include "ctw_runtime_policy.h"

#include <assert.h>
#include <math.h>

static int feq(float a, float b) {
    return fabsf(a - b) < 0.0001f;
}

int main(void) {
    Ctw3DConfig cfg = {0};
    cfg.camera_enabled = 1;
    cfg.fov_degrees = 78.0f;
    cfg.near_clip = 0.05f;
    cfg.draw_distance_enabled = 1;
    cfg.far_clip_multiplier = 2.5f;
    cfg.stream_radius_multiplier = 2.5f;
    cfg.lod_distance_multiplier = 2.25f;
    cfg.vehicle_distance_multiplier = 2.0f;
    cfg.ped_distance_multiplier = 1.75f;

    const CtwProjectionState base_proj = {
        .fov_degrees = 60.0f,
        .near_clip = 0.20f,
        .far_clip = 100.0f,
    };
    CtwProjectionState proj;

    assert(
        ctw_projection_apply_policy(
            &cfg,
            CTW_CAMERA_THIRD_PERSON,
            &base_proj,
            &proj
        ) == 1
    );
    assert(feq(proj.fov_degrees, 78.0f));
    assert(feq(proj.near_clip, 0.05f));
    assert(feq(proj.far_clip, 250.0f));

    assert(
        ctw_projection_apply_policy(
            &cfg,
            CTW_CAMERA_STOCK,
            &base_proj,
            &proj
        ) == 1
    );
    assert(feq(proj.fov_degrees, 60.0f));
    assert(feq(proj.near_clip, 0.20f));
    assert(feq(proj.far_clip, 250.0f));

    cfg.draw_distance_enabled = 0;
    assert(
        ctw_projection_apply_policy(
            &cfg,
            CTW_CAMERA_STOCK,
            &base_proj,
            &proj
        ) == 0
    );
    assert(feq(proj.fov_degrees, 60.0f));
    assert(feq(proj.near_clip, 0.20f));
    assert(feq(proj.far_clip, 100.0f));

    cfg.draw_distance_enabled = 1;
    const CtwWorldDistanceState base_world = {
        .stream_radius = 80.0f,
        .lod_distance = 60.0f,
        .vehicle_distance = 50.0f,
        .ped_distance = 40.0f,
    };
    CtwWorldDistanceState world;

    assert(
        ctw_world_distance_apply_policy(
            &cfg,
            &base_world,
            &world
        ) == 1
    );
    assert(feq(world.stream_radius, 200.0f));
    assert(feq(world.lod_distance, 135.0f));
    assert(feq(world.vehicle_distance, 100.0f));
    assert(feq(world.ped_distance, 70.0f));

    cfg.draw_distance_enabled = 0;
    assert(
        ctw_world_distance_apply_policy(
            &cfg,
            &base_world,
            &world
        ) == 0
    );
    assert(feq(world.stream_radius, 80.0f));

    CtwProjectionState bad_proj = base_proj;
    bad_proj.near_clip = -1.0f;
    assert(
        ctw_projection_apply_policy(
            &cfg,
            CTW_CAMERA_THIRD_PERSON,
            &bad_proj,
            &proj
        ) == -2
    );

    return 0;
}
