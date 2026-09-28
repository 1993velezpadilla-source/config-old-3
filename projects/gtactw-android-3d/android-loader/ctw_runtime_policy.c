#include "ctw_runtime_policy.h"

#include <math.h>

static int finite_positive(float v) {
    return isfinite(v) && v > 0.0f;
}

int ctw_projection_apply_policy(
    const Ctw3DConfig *config,
    CtwCameraMode mode,
    const CtwProjectionState *original,
    CtwProjectionState *out
) {
    if (!config || !original || !out)
        return -1;
    if (!finite_positive(original->fov_degrees) ||
        !finite_positive(original->near_clip) ||
        !finite_positive(original->far_clip) ||
        original->far_clip <= original->near_clip) {
        return -2;
    }

    *out = *original;
    int changed = 0;

    if (config->camera_enabled && mode != CTW_CAMERA_STOCK) {
        if (finite_positive(config->fov_degrees)) {
            out->fov_degrees = config->fov_degrees;
            changed = 1;
        }
        if (finite_positive(config->near_clip)) {
            out->near_clip = config->near_clip;
            changed = 1;
        }
    }

    if (config->draw_distance_enabled &&
        finite_positive(config->far_clip_multiplier)) {
        out->far_clip =
            original->far_clip * config->far_clip_multiplier;
        changed = 1;
    }

    if (out->far_clip <= out->near_clip)
        out->far_clip = out->near_clip + 1.0f;

    return changed;
}

int ctw_world_distance_apply_policy(
    const Ctw3DConfig *config,
    const CtwWorldDistanceState *original,
    CtwWorldDistanceState *out
) {
    if (!config || !original || !out)
        return -1;

    if (!finite_positive(original->stream_radius) ||
        !finite_positive(original->lod_distance) ||
        !finite_positive(original->vehicle_distance) ||
        !finite_positive(original->ped_distance)) {
        return -2;
    }

    *out = *original;
    if (!config->draw_distance_enabled)
        return 0;

    if (!finite_positive(config->stream_radius_multiplier) ||
        !finite_positive(config->lod_distance_multiplier) ||
        !finite_positive(config->vehicle_distance_multiplier) ||
        !finite_positive(config->ped_distance_multiplier)) {
        return -3;
    }

    out->stream_radius =
        original->stream_radius * config->stream_radius_multiplier;
    out->lod_distance =
        original->lod_distance * config->lod_distance_multiplier;
    out->vehicle_distance =
        original->vehicle_distance * config->vehicle_distance_multiplier;
    out->ped_distance =
        original->ped_distance * config->ped_distance_multiplier;

    return 1;
}
