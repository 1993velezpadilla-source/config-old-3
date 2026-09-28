#include "ctw_camera.h"

#include <stdatomic.h>
#include <stdint.h>
#include <string.h>

static atomic_uint g_look_x_bits;
static atomic_uint g_look_y_bits;
static atomic_int g_mode = ATOMIC_VAR_INIT(CTW_CAMERA_THIRD_PERSON);
static CtwCameraOrbitState g_runtime_orbit;

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


static float clampf_camera(float v, float lo, float hi) {
    if (v < lo)
        return lo;
    if (v > hi)
        return hi;
    return v;
}

static float wrap_degrees(float v) {
    while (v > 180.0f)
        v -= 360.0f;
    while (v < -180.0f)
        v += 360.0f;
    return v;
}

void ctw_camera_orbit_reset(
    CtwCameraOrbitState *state,
    const Ctw3DConfig *config
) {
    if (!state)
        return;

    state->yaw_degrees = 0.0f;
    state->pitch_degrees = config
        ? clampf_camera(
            config->camera_pitch_degrees,
            config->camera_min_pitch_degrees,
            config->camera_max_pitch_degrees
        )
        : 0.0f;
}

void ctw_camera_orbit_step(
    CtwCameraOrbitState *state,
    const Ctw3DConfig *config,
    CtwCameraInputSnapshot input,
    float dt_seconds
) {
    if (!state || !config || !config->camera_enabled)
        return;
    if (input.mode == CTW_CAMERA_STOCK)
        return;
    if (dt_seconds <= 0.0f)
        return;

    /* Clamp giant resume/frame-hitch deltas so one frame cannot spin camera. */
    if (dt_seconds > 0.1f)
        dt_seconds = 0.1f;

    state->yaw_degrees +=
        input.look_x * config->camera_look_sensitivity_x * dt_seconds;
    state->yaw_degrees = wrap_degrees(state->yaw_degrees);

    float look_y = input.look_y;
    if (config->camera_invert_y)
        look_y = -look_y;

    state->pitch_degrees +=
        look_y * config->camera_look_sensitivity_y * dt_seconds;
    state->pitch_degrees = clampf_camera(
        state->pitch_degrees,
        config->camera_min_pitch_degrees,
        config->camera_max_pitch_degrees
    );
}


void ctw_camera_runtime_reset(const Ctw3DConfig *config) {
    ctw_camera_orbit_reset(&g_runtime_orbit, config);
}

void ctw_camera_runtime_step(const Ctw3DConfig *config, float dt_seconds) {
    ctw_camera_orbit_step(
        &g_runtime_orbit,
        config,
        ctw_camera_snapshot(),
        dt_seconds
    );
}

CtwCameraOrbitState ctw_camera_orbit_snapshot(void) {
    return g_runtime_orbit;
}
