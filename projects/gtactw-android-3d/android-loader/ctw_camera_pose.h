#pragma once

#include "ctw_camera.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    float x;
    float y;
    float z;
} CtwVec3;

typedef struct {
    CtwVec3 position;
    CtwVec3 forward;
    CtwVec3 right;
    CtwVec3 up;
} CtwPlayerCameraBasis;

typedef struct {
    int override_camera;
    CtwVec3 position;
    CtwVec3 target;
    CtwVec3 forward;
    CtwVec3 up;
} CtwCameraPose;

/*
 * Builds a camera pose from generic player basis vectors.
 * No CTW axis convention is assumed here; the runtime hook supplies basis.
 */
int ctw_camera_build_pose(
    const Ctw3DConfig *config,
    CtwCameraOrbitState orbit,
    CtwCameraMode mode,
    const CtwPlayerCameraBasis *player,
    CtwCameraPose *out
);

int ctw_camera_apply_collision(
    const Ctw3DConfig *config,
    CtwCameraMode mode,
    float hit_fraction,
    CtwCameraPose *pose
);

#ifdef __cplusplus
}
#endif
