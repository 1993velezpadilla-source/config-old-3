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

    return 0;
}
