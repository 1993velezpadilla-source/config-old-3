#include "xz_runtime_readiness.h"

#include <string.h>

static const char *const gate_names[XZ_GATE_COUNT] = {
    "package_visible",
    "zone_db",
    "zone_dependencies",
    "world",
    "material_shader",
    "collision",
    "navigation",
    "physics",
    "rig_db",
    "animation_db",
    "ai_behavior",
    "script_module_db",
    "precache",
    "weapon_gameplay_db",
    "audio",
    "fx",
    "hud_ui",
    "replication",
    "render_frame"
};

static uint32_t XzRuntimeReadiness_AllMask(void)
{
    return (1u << XZ_GATE_COUNT) - 1u;
}

static void XzRuntimeReadiness_Recompute(
    XzRuntimeReadiness *state)
{
    if (!state)
        return;

    state->match_ready =
        state->failed_mask == 0u &&
        (state->ready_mask & state->required_mask) ==
            state->required_mask;

    state->round_start_allowed = state->match_ready;
}

void XzRuntimeReadiness_Init(XzRuntimeReadiness *state)
{
    if (!state)
        return;

    memset(state, 0, sizeof(*state));
    state->required_mask = XzRuntimeReadiness_AllMask();
}

void XzRuntimeReadiness_Reset(
    XzRuntimeReadiness *state)
{
    uint32_t next_generation;

    if (!state)
        return;

    next_generation = state->generation + 1u;
    XzRuntimeReadiness_Init(state);
    state->generation = next_generation;
}

int XzRuntimeReadiness_SetGate(
    XzRuntimeReadiness *state,
    XzRuntimeGate gate,
    int ready,
    int failed)
{
    uint32_t bit;

    if (!state ||
        (unsigned int)gate >= XZ_GATE_COUNT ||
        (ready && failed))
        return 0;

    bit = 1u << (unsigned int)gate;

    if (ready)
        state->ready_mask |= bit;
    else
        state->ready_mask &= ~bit;

    if (failed)
        state->failed_mask |= bit;
    else
        state->failed_mask &= ~bit;

    XzRuntimeReadiness_Recompute(state);
    return 1;
}

int XzRuntimeReadiness_IsGateReady(
    const XzRuntimeReadiness *state,
    XzRuntimeGate gate)
{
    uint32_t bit;

    if (!state || (unsigned int)gate >= XZ_GATE_COUNT)
        return 0;

    bit = 1u << (unsigned int)gate;
    return (state->ready_mask & bit) != 0u &&
           (state->failed_mask & bit) == 0u;
}

int XzRuntimeReadiness_MatchReady(
    const XzRuntimeReadiness *state)
{
    return state ? state->match_ready : 0;
}

const char *XzRuntimeReadiness_GateName(
    XzRuntimeGate gate)
{
    if ((unsigned int)gate >= XZ_GATE_COUNT)
        return "unknown";

    return gate_names[(unsigned int)gate];
}

int XzRuntimeReadiness_SelfTest(void)
{
    XzRuntimeReadiness state;
    unsigned int gate;

    XzRuntimeReadiness_Init(&state);

    if (state.match_ready ||
        state.round_start_allowed)
        return 0;

    for (gate = 0u; gate < XZ_GATE_COUNT; ++gate) {
        if (!XzRuntimeReadiness_SetGate(
                &state,
                (XzRuntimeGate)gate,
                1,
                0))
            return 0;
    }

    if (!state.match_ready ||
        !state.round_start_allowed)
        return 0;

    if (!XzRuntimeReadiness_SetGate(
            &state,
            XZ_GATE_AUDIO,
            0,
            1))
        return 0;

    if (state.match_ready ||
        state.round_start_allowed)
        return 0;

    XzRuntimeReadiness_Reset(&state);
    return state.generation == 1u &&
           !state.match_ready &&
           !state.round_start_allowed;
}
