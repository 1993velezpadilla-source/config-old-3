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

void ctw_camera_set_look(float x, float y);
void ctw_camera_set_mode(CtwCameraMode mode);
void ctw_camera_cycle_mode(void);
CtwCameraInputSnapshot ctw_camera_snapshot(void);

#ifdef __cplusplus
}
#endif
