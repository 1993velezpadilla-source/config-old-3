#pragma once

#include "ctw_patch.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    CtwCameraMode mode;
    float look_x;
    float look_y;
} CtwCameraInputSnapshot;

typedef struct {
    float yaw_degrees;
    float pitch_degrees;
} CtwCameraOrbitState;

typedef enum {
    CTW_CAMERA_BUTTON_NONE = 0,
    CTW_CAMERA_BUTTON_MODE_CYCLED = 1,
    CTW_CAMERA_BUTTON_ORBIT_RESET = 2,
} CtwCameraButtonAction;

void ctw_camera_set_look(float x, float y);
void ctw_camera_set_mode(CtwCameraMode mode);
void ctw_camera_cycle_mode(void);
CtwCameraInputSnapshot ctw_camera_snapshot(void);
CtwCameraButtonAction ctw_camera_handle_gamepad_button_down(
    int keycode,
    const Ctw3DConfig *config
);
void ctw_camera_orbit_reset(
    CtwCameraOrbitState *state,
    const Ctw3DConfig *config
);
void ctw_camera_orbit_step(
    CtwCameraOrbitState *state,
    const Ctw3DConfig *config,
    CtwCameraInputSnapshot input,
    float dt_seconds
);
void ctw_camera_runtime_reset(const Ctw3DConfig *config);
void ctw_camera_runtime_step(const Ctw3DConfig *config, float dt_seconds);
CtwCameraOrbitState ctw_camera_orbit_snapshot(void);

#ifdef __cplusplus
}
#endif
