#ifndef XZ_RUNTIME_READINESS_H
#define XZ_RUNTIME_READINESS_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum XzRuntimeGate {
    XZ_GATE_PACKAGE_VISIBLE = 0,
    XZ_GATE_ZONE_DB,
    XZ_GATE_ZONE_DEPENDENCIES,
    XZ_GATE_WORLD,
    XZ_GATE_MATERIAL_SHADER,
    XZ_GATE_COLLISION,
    XZ_GATE_NAVIGATION,
    XZ_GATE_PHYSICS,
    XZ_GATE_RIG_DB,
    XZ_GATE_ANIMATION_DB,
    XZ_GATE_AI_BEHAVIOR,
    XZ_GATE_SCRIPT_MODULE_DB,
    XZ_GATE_PRECACHE,
    XZ_GATE_GAME_SYSTEMS,
    XZ_GATE_WEAPON_GAMEPLAY_DB,
    XZ_GATE_AUDIO,
    XZ_GATE_FX,
    XZ_GATE_HUD_UI,
    XZ_GATE_REPLICATION,
    XZ_GATE_CRITICAL_STREAMING,
    XZ_GATE_RENDER_FRAME,
    XZ_GATE_COUNT
} XzRuntimeGate;

typedef struct XzRuntimeReadiness {
    uint32_t ready_mask;
    uint32_t failed_mask;
    uint32_t required_mask;
    uint32_t generation;
    int match_ready;
    int round_start_allowed;
} XzRuntimeReadiness;

void XzRuntimeReadiness_Init(XzRuntimeReadiness *state);

void XzRuntimeReadiness_Reset(
    XzRuntimeReadiness *state);

int XzRuntimeReadiness_SetGate(
    XzRuntimeReadiness *state,
    XzRuntimeGate gate,
    int ready,
    int failed);

int XzRuntimeReadiness_IsGateReady(
    const XzRuntimeReadiness *state,
    XzRuntimeGate gate);

int XzRuntimeReadiness_MatchReady(
    const XzRuntimeReadiness *state);

const char *XzRuntimeReadiness_GateName(
    XzRuntimeGate gate);

int XzRuntimeReadiness_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif
