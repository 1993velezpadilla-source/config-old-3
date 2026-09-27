#ifndef XZ_BO3_WEAPON_RUNTIME_H
#define XZ_BO3_WEAPON_RUNTIME_H

#include "xz_bo3_weapon_specs.h"

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum XzBo3WeaponRuntimeResult {
    XZ_BO3_WEAPON_RUNTIME_OK = 0,
    XZ_BO3_WEAPON_RUNTIME_INVALID_ARGUMENT,
    XZ_BO3_WEAPON_RUNTIME_COOLDOWN,
    XZ_BO3_WEAPON_RUNTIME_EMPTY,
    XZ_BO3_WEAPON_RUNTIME_BUSY,
    XZ_BO3_WEAPON_RUNTIME_RELOAD_UNSUPPORTED
} XzBo3WeaponRuntimeResult;

typedef struct XzBo3WeaponShotEvent {
    float scheduled_time_seconds;
    float damage_per_projectile;
    float head_multiplier;
    unsigned int projectiles_per_shot;
} XzBo3WeaponShotEvent;

typedef struct XzBo3WeaponRuntimeState {
    const XzBo3WeaponSpec *spec;

    unsigned int magazine_ammo;
    unsigned int reserve_ammo;

    unsigned int burst_remaining;
    float next_burst_shot_time;
    float trigger_ready_time;

    int reload_pending;
    float reload_complete_time;

    unsigned long long total_shots_fired;
} XzBo3WeaponRuntimeState;

void XzBo3WeaponRuntime_Reset(
    XzBo3WeaponRuntimeState *state);

XzBo3WeaponRuntimeResult XzBo3WeaponRuntime_Init(
    XzBo3WeaponRuntimeState *state,
    const XzBo3WeaponSpec *spec);

int XzBo3WeaponRuntime_IsPlayable(
    const XzBo3WeaponRuntimeState *state);

XzBo3WeaponRuntimeResult XzBo3WeaponRuntime_Trigger(
    XzBo3WeaponRuntimeState *state,
    float now_seconds,
    float target_distance_units,
    XzBo3WeaponShotEvent *event_out);

size_t XzBo3WeaponRuntime_Advance(
    XzBo3WeaponRuntimeState *state,
    float now_seconds,
    float target_distance_units,
    XzBo3WeaponShotEvent *events_out,
    size_t event_capacity);

XzBo3WeaponRuntimeResult XzBo3WeaponRuntime_TryReload(
    XzBo3WeaponRuntimeState *state,
    float now_seconds);

const char *XzBo3WeaponRuntime_ResultName(
    XzBo3WeaponRuntimeResult result);

#ifdef __cplusplus
}
#endif

#endif
