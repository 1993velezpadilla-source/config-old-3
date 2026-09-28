#include "ctw_camera.h"

#include <assert.h>
#include <math.h>

int main(void) {
    CtwCameraInputSnapshot s = ctw_camera_snapshot();
    assert(s.mode == CTW_CAMERA_THIRD_PERSON);

    ctw_camera_set_look(0.02f, -2.0f);
    s = ctw_camera_snapshot();
    assert(s.look_x == 0.0f);
    assert(fabsf(s.look_y + 1.0f) < 0.0001f);

    ctw_camera_cycle_mode();
    s = ctw_camera_snapshot();
    assert(s.mode == CTW_CAMERA_FIRST_PERSON);

    ctw_camera_cycle_mode();
    s = ctw_camera_snapshot();
    assert(s.mode == CTW_CAMERA_STOCK);

    ctw_camera_cycle_mode();
    s = ctw_camera_snapshot();
    assert(s.mode == CTW_CAMERA_THIRD_PERSON);

    Ctw3DConfig cfg = {0};
    cfg.camera_enabled = 1;
    cfg.camera_pitch_degrees = -7.0f;
    cfg.camera_look_sensitivity_x = 110.0f;
    cfg.camera_look_sensitivity_y = 90.0f;
    cfg.camera_min_pitch_degrees = -70.0f;
    cfg.camera_max_pitch_degrees = 35.0f;

    CtwCameraOrbitState orbit;
    ctw_camera_orbit_reset(&orbit, &cfg);
    assert(fabsf(orbit.yaw_degrees) < 0.0001f);
    assert(fabsf(orbit.pitch_degrees + 7.0f) < 0.0001f);

    CtwCameraInputSnapshot input = {
        .mode = CTW_CAMERA_THIRD_PERSON,
        .look_x = 1.0f,
        .look_y = 1.0f,
    };
    ctw_camera_orbit_step(&orbit, &cfg, input, 0.05f);
    assert(fabsf(orbit.yaw_degrees - 5.5f) < 0.0001f);
    assert(fabsf(orbit.pitch_degrees + 2.5f) < 0.0001f);

    cfg.camera_invert_y = 1;
    input.look_y = 10.0f;
    ctw_camera_orbit_step(&orbit, &cfg, input, 1.0f);
    assert(orbit.pitch_degrees == -70.0f); /* dt and pitch clamp */

    const float frozen_yaw = orbit.yaw_degrees;
    input.mode = CTW_CAMERA_STOCK;
    ctw_camera_orbit_step(&orbit, &cfg, input, 0.05f);
    assert(orbit.yaw_degrees == frozen_yaw);

    ctw_camera_set_mode(CTW_CAMERA_THIRD_PERSON);
    ctw_camera_set_look(1.0f, 0.0f);
    ctw_camera_runtime_reset(&cfg);
    ctw_camera_runtime_step(&cfg, 0.05f);
    CtwCameraOrbitState runtime = ctw_camera_orbit_snapshot();
    assert(fabsf(runtime.yaw_degrees - 5.5f) < 0.0001f);
    assert(fabsf(runtime.pitch_degrees + 7.0f) < 0.0001f);

    assert(
        ctw_camera_handle_gamepad_button_down(8, &cfg)
        == CTW_CAMERA_BUTTON_ORBIT_RESET
    );
    runtime = ctw_camera_orbit_snapshot();
    assert(fabsf(runtime.yaw_degrees) < 0.0001f);
    assert(fabsf(runtime.pitch_degrees + 7.0f) < 0.0001f);

    assert(
        ctw_camera_handle_gamepad_button_down(13, &cfg)
        == CTW_CAMERA_BUTTON_MODE_CYCLED
    );
    assert(ctw_camera_snapshot().mode == CTW_CAMERA_FIRST_PERSON);

    ctw_camera_set_mode(CTW_CAMERA_STOCK);
    assert(
        ctw_camera_handle_gamepad_button_down(8, &cfg)
        == CTW_CAMERA_BUTTON_NONE
    );

    return 0;
}
