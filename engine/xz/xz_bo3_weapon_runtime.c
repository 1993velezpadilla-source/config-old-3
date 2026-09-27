#include "xz_bo3_weapon_runtime.h"

#include <math.h>
#include <string.h>

#define XZ_BO3_WEAPON_RUNTIME_TIME_EPSILON 0.000001f

static int XzBo3WeaponRuntime_IsFiniteNonNegative(
    float value)
{
    return isfinite(value) && value >= 0.0f;
}

static void XzBo3WeaponRuntime_CompleteReloadIfDue(
    XzBo3WeaponRuntimeState *state,
    float now_seconds)
{
    unsigned int needed;
    unsigned int moved;

    if (!state ||
        !state->spec ||
        !state->reload_pending ||
        now_seconds + XZ_BO3_WEAPON_RUNTIME_TIME_EPSILON <
            state->reload_complete_time)
        return;

    needed =
        state->spec->magazine > state->magazine_ammo
            ? state->spec->magazine - state->magazine_ammo
            : 0u;

    moved =
        needed < state->reserve_ammo
            ? needed
            : state->reserve_ammo;

    state->magazine_ammo += moved;
    state->reserve_ammo -= moved;
    state->reload_pending = 0;
    state->reload_complete_time = 0.0f;
}

static void XzBo3WeaponRuntime_FillShotEvent(
    const XzBo3WeaponRuntimeState *state,
    float scheduled_time_seconds,
    float target_distance_units,
    XzBo3WeaponShotEvent *event_out)
{
    event_out->scheduled_time_seconds =
        scheduled_time_seconds;
    event_out->damage_per_projectile =
        XzBo3WeaponSpec_DamageAtDistanceUnits(
            state->spec,
            target_distance_units);
    event_out->head_multiplier =
        state->spec->head_multiplier;
    event_out->projectiles_per_shot =
        state->spec->projectiles_per_shot;
}

static int XzBo3WeaponRuntime_ConsumeShot(
    XzBo3WeaponRuntimeState *state,
    float scheduled_time_seconds,
    float target_distance_units,
    XzBo3WeaponShotEvent *event_out)
{
    if (!state ||
        !state->spec ||
        !event_out ||
        state->magazine_ammo == 0u)
        return 0;

    XzBo3WeaponRuntime_FillShotEvent(
        state,
        scheduled_time_seconds,
        target_distance_units,
        event_out);

    state->magazine_ammo--;
    state->total_shots_fired++;
    return 1;
}

void XzBo3WeaponRuntime_Reset(
    XzBo3WeaponRuntimeState *state)
{
    if (!state)
        return;

    memset(state, 0, sizeof(*state));
}

XzBo3WeaponRuntimeResult XzBo3WeaponRuntime_Init(
    XzBo3WeaponRuntimeState *state,
    const XzBo3WeaponSpec *spec)
{
    if (!state ||
        !spec ||
        spec->magazine == 0u ||
        spec->burst_size == 0u ||
        !isfinite(spec->cyclic_rpm) ||
        spec->cyclic_rpm <= 0.0f ||
        !isfinite(spec->overall_rpm) ||
        spec->overall_rpm <= 0.0f)
        return XZ_BO3_WEAPON_RUNTIME_INVALID_ARGUMENT;

    XzBo3WeaponRuntime_Reset(state);
    state->spec = spec;
    state->magazine_ammo = spec->magazine;
    state->reserve_ammo = spec->reserve;

    return XZ_BO3_WEAPON_RUNTIME_OK;
}

int XzBo3WeaponRuntime_IsPlayable(
    const XzBo3WeaponRuntimeState *state)
{
    if (!state || !state->spec)
        return 0;

    return XzBo3WeaponSpec_IsNativeReady(
        state->spec);
}

XzBo3WeaponRuntimeResult XzBo3WeaponRuntime_Trigger(
    XzBo3WeaponRuntimeState *state,
    float now_seconds,
    float target_distance_units,
    XzBo3WeaponShotEvent *event_out)
{
    float interval;

    if (!state ||
        !state->spec ||
        !event_out ||
        !XzBo3WeaponRuntime_IsFiniteNonNegative(
            now_seconds) ||
        !XzBo3WeaponRuntime_IsFiniteNonNegative(
            target_distance_units))
        return XZ_BO3_WEAPON_RUNTIME_INVALID_ARGUMENT;

    XzBo3WeaponRuntime_CompleteReloadIfDue(
        state,
        now_seconds);

    if (state->reload_pending ||
        state->burst_remaining > 0u)
        return XZ_BO3_WEAPON_RUNTIME_BUSY;

    if (now_seconds + XZ_BO3_WEAPON_RUNTIME_TIME_EPSILON <
        state->trigger_ready_time)
        return XZ_BO3_WEAPON_RUNTIME_COOLDOWN;

    if (state->magazine_ammo == 0u)
        return XZ_BO3_WEAPON_RUNTIME_EMPTY;

    if (!XzBo3WeaponRuntime_ConsumeShot(
            state,
            now_seconds,
            target_distance_units,
            event_out))
        return XZ_BO3_WEAPON_RUNTIME_EMPTY;

    if (state->spec->burst_size > 1u) {
        interval =
            XzBo3WeaponSpec_SecondsPerBurstShot(
                state->spec);

        state->burst_remaining =
            state->spec->burst_size - 1u;
        state->next_burst_shot_time =
            now_seconds + interval;
        state->trigger_ready_time =
            now_seconds +
            XzBo3WeaponSpec_BurstCycleSeconds(
                state->spec);
    } else {
        state->trigger_ready_time =
            now_seconds +
            XzBo3WeaponSpec_SecondsPerShot(
                state->spec);
    }

    return XZ_BO3_WEAPON_RUNTIME_OK;
}

size_t XzBo3WeaponRuntime_Advance(
    XzBo3WeaponRuntimeState *state,
    float now_seconds,
    float target_distance_units,
    XzBo3WeaponShotEvent *events_out,
    size_t event_capacity)
{
    size_t emitted = 0u;
    float interval;

    if (!state ||
        !state->spec ||
        !XzBo3WeaponRuntime_IsFiniteNonNegative(
            now_seconds) ||
        !XzBo3WeaponRuntime_IsFiniteNonNegative(
            target_distance_units) ||
        (event_capacity > 0u && !events_out))
        return 0u;

    XzBo3WeaponRuntime_CompleteReloadIfDue(
        state,
        now_seconds);

    if (state->reload_pending ||
        state->burst_remaining == 0u ||
        event_capacity == 0u)
        return 0u;

    interval =
        XzBo3WeaponSpec_SecondsPerBurstShot(
            state->spec);

    if (!isfinite(interval) || interval <= 0.0f) {
        state->burst_remaining = 0u;
        return 0u;
    }

    while (state->burst_remaining > 0u &&
           emitted < event_capacity &&
           state->next_burst_shot_time <=
               now_seconds +
                   XZ_BO3_WEAPON_RUNTIME_TIME_EPSILON) {
        if (state->magazine_ammo == 0u) {
            state->burst_remaining = 0u;
            break;
        }

        if (!XzBo3WeaponRuntime_ConsumeShot(
                state,
                state->next_burst_shot_time,
                target_distance_units,
                &events_out[emitted])) {
            state->burst_remaining = 0u;
            break;
        }

        emitted++;
        state->burst_remaining--;

        if (state->burst_remaining > 0u)
            state->next_burst_shot_time +=
                interval;
    }

    if (state->burst_remaining == 0u)
        state->next_burst_shot_time = 0.0f;

    return emitted;
}

XzBo3WeaponRuntimeResult XzBo3WeaponRuntime_TryReload(
    XzBo3WeaponRuntimeState *state,
    float now_seconds)
{
    float duration;

    if (!state ||
        !state->spec ||
        !XzBo3WeaponRuntime_IsFiniteNonNegative(
            now_seconds))
        return XZ_BO3_WEAPON_RUNTIME_INVALID_ARGUMENT;

    XzBo3WeaponRuntime_CompleteReloadIfDue(
        state,
        now_seconds);

    if (state->reload_pending ||
        state->burst_remaining > 0u)
        return XZ_BO3_WEAPON_RUNTIME_BUSY;

    if (state->magazine_ammo >=
            state->spec->magazine ||
        state->reserve_ammo == 0u)
        return XZ_BO3_WEAPON_RUNTIME_OK;

    duration =
        state->magazine_ammo == 0u
            ? state->spec->reload_empty_seconds
            : state->spec->reload_loaded_seconds;

    if (!isfinite(duration) ||
        duration <= 0.0f)
        return XZ_BO3_WEAPON_RUNTIME_RELOAD_UNSUPPORTED;

    state->reload_pending = 1;
    state->reload_complete_time =
        now_seconds + duration;

    return XZ_BO3_WEAPON_RUNTIME_OK;
}

const char *XzBo3WeaponRuntime_ResultName(
    XzBo3WeaponRuntimeResult result)
{
    switch (result) {
    case XZ_BO3_WEAPON_RUNTIME_OK:
        return "OK";
    case XZ_BO3_WEAPON_RUNTIME_INVALID_ARGUMENT:
        return "INVALID_ARGUMENT";
    case XZ_BO3_WEAPON_RUNTIME_COOLDOWN:
        return "COOLDOWN";
    case XZ_BO3_WEAPON_RUNTIME_EMPTY:
        return "EMPTY";
    case XZ_BO3_WEAPON_RUNTIME_BUSY:
        return "BUSY";
    case XZ_BO3_WEAPON_RUNTIME_RELOAD_UNSUPPORTED:
        return "RELOAD_UNSUPPORTED";
    default:
        return "UNKNOWN";
    }
}
