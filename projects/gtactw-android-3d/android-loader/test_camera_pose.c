#include "ctw_camera_pose.h"

#include <assert.h>
#include <math.h>

static int feq(float a, float b) {
    return fabsf(a - b) < 0.0001f;
}

int main(void) {
    Ctw3DConfig cfg = {0};
    cfg.camera_enabled = 1;
    cfg.camera_height = 1.5f;
    cfg.camera_distance = 5.0f;

    CtwPlayerCameraBasis p = {
        .position = {10.0f, 20.0f, 3.0f},
        .forward = {0.0f, 1.0f, 0.0f},
        .right = {1.0f, 0.0f, 0.0f},
        .up = {0.0f, 0.0f, 1.0f},
    };

    CtwCameraOrbitState orbit = {
        .yaw_degrees = 0.0f,
        .pitch_degrees = 0.0f,
    };
    CtwCameraPose pose;

    assert(
        ctw_camera_build_pose(
            &cfg,
            orbit,
            CTW_CAMERA_THIRD_PERSON,
            &p,
            &pose
        ) == 1
    );
    assert(pose.override_camera == 1);
    assert(feq(pose.target.x, 10.0f));
    assert(feq(pose.target.y, 20.0f));
    assert(feq(pose.target.z, 4.5f));
    assert(feq(pose.position.x, 10.0f));
    assert(feq(pose.position.y, 15.0f));
    assert(feq(pose.position.z, 4.5f));

    assert(
        ctw_camera_build_pose(
            &cfg,
            orbit,
            CTW_CAMERA_FIRST_PERSON,
            &p,
            &pose
        ) == 1
    );
    assert(feq(pose.position.x, 10.0f));
    assert(feq(pose.position.y, 20.0f));
    assert(feq(pose.position.z, 4.5f));
    assert(feq(pose.target.x, 10.0f));
    assert(feq(pose.target.y, 21.0f));
    assert(feq(pose.target.z, 4.5f));

    orbit.yaw_degrees = 90.0f;
    orbit.pitch_degrees = 0.0f;
    assert(
        ctw_camera_build_pose(
            &cfg,
            orbit,
            CTW_CAMERA_FIRST_PERSON,
            &p,
            &pose
        ) == 1
    );
    assert(fabsf(pose.forward.x - 1.0f) < 0.0001f);
    assert(fabsf(pose.forward.y) < 0.0001f);
    assert(fabsf(pose.forward.z) < 0.0001f);

    orbit.yaw_degrees = 0.0f;
    orbit.pitch_degrees = 30.0f;
    assert(
        ctw_camera_build_pose(
            &cfg,
            orbit,
            CTW_CAMERA_FIRST_PERSON,
            &p,
            &pose
        ) == 1
    );
    assert(pose.forward.y > 0.8f);
    assert(pose.forward.z > 0.49f);

    cfg.camera_enabled = 0;
    assert(
        ctw_camera_build_pose(
            &cfg,
            orbit,
            CTW_CAMERA_THIRD_PERSON,
            &p,
            &pose
        ) == 0
    );
    assert(pose.override_camera == 0);

    cfg.camera_enabled = 1;
    CtwPlayerCameraBasis bad = p;
    bad.right = bad.forward;
    assert(
        ctw_camera_build_pose(
            &cfg,
            orbit,
            CTW_CAMERA_THIRD_PERSON,
            &bad,
            &pose
        ) == -2
    );

    return 0;
}
