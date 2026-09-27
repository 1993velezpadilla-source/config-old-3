#include "xz_bo3_weapon_runtime.h"

#include <assert.h>
#include <math.h>
#include <string.h>

static int Near(float a, float b, float epsilon)
{
    return fabsf(a - b) <= epsilon;
}

int main(void)
{
    const XzBo3WeaponSpec *rk5;
    const XzBo3WeaponSpec *kn44;
    const XzBo3WeaponSpec *argus;
    XzBo3WeaponRuntimeState state;
    XzBo3WeaponShotEvent event;
    XzBo3WeaponShotEvent events[4];
    size_t emitted;

    rk5 = XzBo3WeaponSpec_FindByLogicalItemId(
        "pistol_burst");
    kn44 = XzBo3WeaponSpec_FindByLogicalItemId(
        "ar_standard");
    argus = XzBo3WeaponSpec_FindByLogicalItemId(
        "shotgun_precision");

    assert(rk5 && kn44 && argus);

    assert(
        XzBo3WeaponRuntime_Init(&state, rk5) ==
        XZ_BO3_WEAPON_RUNTIME_OK);
    assert(state.magazine_ammo == 15u);
    assert(state.reserve_ammo == 120u);
    assert(state.total_shots_fired == 0u);
    assert(!XzBo3WeaponRuntime_IsPlayable(&state));

    assert(
        XzBo3WeaponRuntime_Trigger(
            &state,
            0.0f,
            475.5f,
            &event) ==
        XZ_BO3_WEAPON_RUNTIME_OK);
    assert(state.magazine_ammo == 14u);
    assert(state.burst_remaining == 2u);
    assert(state.total_shots_fired == 1u);
    assert(Near(event.scheduled_time_seconds, 0.0f, 0.000001f));
    assert(Near(event.damage_per_projectile, 62.5f, 0.0001f));
    assert(event.projectiles_per_shot == 1u);
    assert(Near(event.head_multiplier, 2.0f, 0.0001f));

    assert(
        XzBo3WeaponRuntime_Trigger(
            &state,
            0.01f,
            475.5f,
            &event) ==
        XZ_BO3_WEAPON_RUNTIME_BUSY);

    emitted =
        XzBo3WeaponRuntime_Advance(
            &state,
            0.065f,
            475.5f,
            events,
            4u);
    assert(emitted == 0u);
    assert(state.magazine_ammo == 14u);

    emitted =
        XzBo3WeaponRuntime_Advance(
            &state,
            0.067f,
            475.5f,
            events,
            4u);
    assert(emitted == 1u);
    assert(state.magazine_ammo == 13u);
    assert(state.burst_remaining == 1u);
    assert(Near(
        events[0].scheduled_time_seconds,
        60.0f / 909.0f,
        0.00001f));

    emitted =
        XzBo3WeaponRuntime_Advance(
            &state,
            0.133f,
            475.5f,
            events,
            4u);
    assert(emitted == 1u);
    assert(state.magazine_ammo == 12u);
    assert(state.burst_remaining == 0u);
    assert(state.total_shots_fired == 3u);
    assert(Near(
        events[0].scheduled_time_seconds,
        2.0f * 60.0f / 909.0f,
        0.00001f));

    assert(
        XzBo3WeaponRuntime_Trigger(
            &state,
            0.20f,
            475.5f,
            &event) ==
        XZ_BO3_WEAPON_RUNTIME_COOLDOWN);

    assert(
        XzBo3WeaponRuntime_TryReload(
            &state,
            0.30f) ==
        XZ_BO3_WEAPON_RUNTIME_OK);
    assert(state.reload_pending == 1);
    assert(Near(
        state.reload_complete_time,
        1.80f,
        0.0001f));

    assert(
        XzBo3WeaponRuntime_Trigger(
            &state,
            1.0f,
            475.5f,
            &event) ==
        XZ_BO3_WEAPON_RUNTIME_BUSY);

    emitted =
        XzBo3WeaponRuntime_Advance(
            &state,
            1.799f,
            475.5f,
            events,
            4u);
    assert(emitted == 0u);
    assert(state.reload_pending == 1);
    assert(state.magazine_ammo == 12u);

    emitted =
        XzBo3WeaponRuntime_Advance(
            &state,
            1.80f,
            475.5f,
            events,
            4u);
    assert(emitted == 0u);
    assert(state.reload_pending == 0);
    assert(state.magazine_ammo == 15u);
    assert(state.reserve_ammo == 117u);

    assert(
        XzBo3WeaponRuntime_Init(&state, rk5) ==
        XZ_BO3_WEAPON_RUNTIME_OK);
    assert(
        XzBo3WeaponRuntime_Trigger(
            &state,
            0.0f,
            200.0f,
            &event) ==
        XZ_BO3_WEAPON_RUNTIME_OK);

    emitted =
        XzBo3WeaponRuntime_Advance(
            &state,
            1.0f,
            200.0f,
            events,
            2u);
    assert(emitted == 2u);
    assert(state.burst_remaining == 0u);
    assert(state.magazine_ammo == 12u);
    assert(Near(events[0].damage_per_projectile, 100.0f, 0.0001f));
    assert(Near(events[1].damage_per_projectile, 100.0f, 0.0001f));

    assert(
        XzBo3WeaponRuntime_Init(&state, kn44) ==
        XZ_BO3_WEAPON_RUNTIME_OK);
    assert(
        XzBo3WeaponRuntime_Trigger(
            &state,
            0.0f,
            1350.5f,
            &event) ==
        XZ_BO3_WEAPON_RUNTIME_OK);
    assert(Near(event.damage_per_projectile, 95.0f, 0.0001f));
    assert(
        XzBo3WeaponRuntime_Trigger(
            &state,
            0.05f,
            1350.5f,
            &event) ==
        XZ_BO3_WEAPON_RUNTIME_COOLDOWN);
    assert(
        XzBo3WeaponRuntime_Trigger(
            &state,
            0.096f,
            1350.5f,
            &event) ==
        XZ_BO3_WEAPON_RUNTIME_OK);
    assert(state.magazine_ammo == 28u);

    assert(
        XzBo3WeaponRuntime_Init(&state, argus) ==
        XZ_BO3_WEAPON_RUNTIME_OK);
    assert(
        XzBo3WeaponRuntime_Trigger(
            &state,
            0.0f,
            300.0f,
            &event) ==
        XZ_BO3_WEAPON_RUNTIME_OK);
    assert(event.damage_per_projectile == 0.0f);
    assert(
        XzBo3WeaponRuntime_TryReload(
            &state,
            2.0f) ==
        XZ_BO3_WEAPON_RUNTIME_RELOAD_UNSUPPORTED);

    assert(
        XzBo3WeaponRuntime_Trigger(
            &state,
            -1.0f,
            0.0f,
            &event) ==
        XZ_BO3_WEAPON_RUNTIME_INVALID_ARGUMENT);

    assert(strcmp(
        XzBo3WeaponRuntime_ResultName(
            XZ_BO3_WEAPON_RUNTIME_COOLDOWN),
        "COOLDOWN") == 0);

    XzBo3WeaponRuntime_Reset(&state);
    assert(state.spec == 0);
    assert(state.magazine_ammo == 0u);
    assert(state.reserve_ammo == 0u);

    return 0;
}
