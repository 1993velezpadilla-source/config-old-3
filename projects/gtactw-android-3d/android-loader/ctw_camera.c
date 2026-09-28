#include "ctw_camera.h"

#include <stdatomic.h>
#include <stdint.h>
#include <string.h>

static atomic_uint g_look_x_bits;
static atomic_uint g_look_y_bits;
static atomic_int g_mode = ATOMIC_VAR_INIT(CTW_CAMERA_THIRD_PERSON);

static uint32_t float_bits(float v) {
    uint32_t bits;
    memcpy(&bits, &v, sizeof(bits));
    return bits;
}

static float bits_float(uint32_t bits) {
    float v;
    memcpy(&v, &bits, sizeof(v));
    return v;
}

static float clamp_axis(float v) {
    if (v > 1.0f)
        v = 1.0f;
    else if (v < -1.0f)
        v = -1.0f;

    if (v > -0.08f && v < 0.08f)
        return 0.0f;
    return v;
}

void ctw_camera_set_look(float x, float y) {
    atomic_store_explicit(&g_look_x_bits, float_bits(clamp_axis(x)), memory_order_relaxed);
    atomic_store_explicit(&g_look_y_bits, float_bits(clamp_axis(y)), memory_order_relaxed);
}

void ctw_camera_set_mode(CtwCameraMode mode) {
    if (mode < CTW_CAMERA_STOCK || mode > CTW_CAMERA_FIRST_PERSON)
        mode = CTW_CAMERA_STOCK;

    atomic_store_explicit(&g_mode, (int)mode, memory_order_relaxed);
    g_ctw3d_config.mode = mode;
}

void ctw_camera_cycle_mode(void) {
    int current = atomic_load_explicit(&g_mode, memory_order_relaxed);
    int next = current + 1;
    if (next > CTW_CAMERA_FIRST_PERSON)
        next = CTW_CAMERA_STOCK;

    atomic_store_explicit(&g_mode, next, memory_order_relaxed);
    g_ctw3d_config.mode = (CtwCameraMode)next;
}

CtwCameraInputSnapshot ctw_camera_snapshot(void) {
    CtwCameraInputSnapshot out;
    out.mode = (CtwCameraMode)atomic_load_explicit(&g_mode, memory_order_relaxed);
    out.look_x = bits_float(atomic_load_explicit(&g_look_x_bits, memory_order_relaxed));
    out.look_y = bits_float(atomic_load_explicit(&g_look_y_bits, memory_order_relaxed));
    return out;
}
