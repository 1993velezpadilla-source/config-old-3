#pragma once

#include "ctw_patch.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    float fov_degrees;
    float near_clip;
    float far_clip;
} CtwProjectionState;

typedef struct {
    float stream_radius;
    float lod_distance;
    float vehicle_distance;
    float ped_distance;
} CtwWorldDistanceState;

/*
 * Applies CTW3D camera/projection policy to engine-provided values.
 * Returns 1 when at least one value is overridden, 0 when preserved, <0 on
 * invalid input.
 */
int ctw_projection_apply_policy(
    const Ctw3DConfig *config,
    CtwCameraMode mode,
    const CtwProjectionState *original,
    CtwProjectionState *out
);

/*
 * Applies coordinated world/population distance multipliers.
 * Returns 1 when enabled, 0 when preserved, <0 on invalid input.
 */
int ctw_world_distance_apply_policy(
    const Ctw3DConfig *config,
    const CtwWorldDistanceState *original,
    CtwWorldDistanceState *out
);

#ifdef __cplusplus
}
#endif
