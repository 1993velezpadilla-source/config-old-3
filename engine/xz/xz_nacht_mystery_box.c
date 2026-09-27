#include "xz_nacht_mystery_box.h"

#include <string.h>

/*
 * BO3 source authority used for this clean-room runtime contract:
 *
 * ate47/bo3-source @ fe040b1187b4850fe8da3c78b703c986c87d1028
 *   scripts/shared/array_shared.gsc
 *     array::randomize swaps every i with randomint(array.size).
 *   scripts/zm/_zm_magicbox.gsc
 *     selection randomizes level.zombie_weapons, then returns the first
 *     receiveable weapon; if none pass, it returns the first randomized key.
 *     default chest cost is 950.
 *   scripts/zm/_zm_weapons.gsc
 *     limited quotas count other holders / PAP / active boxes / custom sources.
 *   scripts/zm/zm_prototype.gsc
 *     sets magic_chest_movable to 0 for Nacht.
 *
 * Pool membership itself is generated from the repository's validated
 * zm_prototype in_box catalog and never duplicated by hand.
 */

static const XzNachtMysteryBoxEntry
    kNachtMysteryBoxPool[XZ_NACHT_MYSTERY_BOX_POOL_COUNT] = {
#include "xz_nacht_mystery_box_pool.generated.inc"
};

static int XzNachtMysteryBox_Owns(
    const XzNachtMysteryBoxSelectionContext *context,
    const char *weapon_id)
{
    if (!context ||
        !context->owns_weapon_or_upgrade ||
        !weapon_id)
        return 0;

    return context->owns_weapon_or_upgrade(
        context->user_context,
        weapon_id) != 0;
}

static int XzNachtMysteryBox_PredicateAllows(
    XzNachtMysteryBoxWeaponPredicateFn predicate,
    const XzNachtMysteryBoxSelectionContext *context,
    const char *weapon_id)
{
    if (!predicate)
        return 1;

    return predicate(
        context->user_context,
        weapon_id) != 0;
}

size_t XzNachtMysteryBox_Count(void)
{
    return XZ_NACHT_MYSTERY_BOX_POOL_COUNT;
}

const XzNachtMysteryBoxEntry *XzNachtMysteryBox_Get(
    size_t index)
{
    if (index >= XZ_NACHT_MYSTERY_BOX_POOL_COUNT)
        return NULL;

    return &kNachtMysteryBoxPool[index];
}

int XzNachtMysteryBox_IsEligible(
    const XzNachtMysteryBoxEntry *entry,
    const XzNachtMysteryBoxSelectionContext *context)
{
    uint32_t occupied = 0u;

    if (!entry || !context)
        return 0;

    if (XzNachtMysteryBox_Owns(
            context,
            entry->weapon_id))
        return 0;

    if (entry->upgrade_id &&
        XzNachtMysteryBox_Owns(
            context,
            entry->upgrade_id))
        return 0;

    /*
     * Stock BO3 explicitly makes Ray Gun and Ray Gun Mark II mutually
     * exclusive for the receiving player.
     */
    if (strcmp(entry->weapon_id, "ray_gun") == 0 &&
        (XzNachtMysteryBox_Owns(
             context,
             "raygun_mark2") ||
         XzNachtMysteryBox_Owns(
             context,
             "raygun_mark2_upgraded")))
        return 0;

    if (strcmp(entry->weapon_id, "raygun_mark2") == 0 &&
        (XzNachtMysteryBox_Owns(
             context,
             "ray_gun") ||
         XzNachtMysteryBox_Owns(
             context,
             "ray_gun_upgraded")))
        return 0;

    if (entry->quota_defined) {
        if (context->limited_occupancy)
            occupied =
                context->limited_occupancy(
                    context->user_context,
                    entry->weapon_id);

        if (occupied >= entry->quota)
            return 0;
    }

    if (!XzNachtMysteryBox_PredicateAllows(
            context->content_allowed,
            context,
            entry->weapon_id))
        return 0;

    if (!XzNachtMysteryBox_PredicateAllows(
            context->special_allowed,
            context,
            entry->weapon_id))
        return 0;

    if (context->require_native_ready) {
        if (!context->native_ready ||
            !context->native_ready(
                context->user_context,
                entry->weapon_id))
            return 0;
    }

    return 1;
}

XzNachtMysteryBoxResult XzNachtMysteryBox_Select(
    const XzNachtMysteryBoxSelectionContext *context,
    XzNachtMysteryBoxSelection *selection_out)
{
    uint8_t order[XZ_NACHT_MYSTERY_BOX_POOL_COUNT];
    size_t i;

    if (!context ||
        !selection_out ||
        !context->random_below)
        return XZ_NACHT_MYSTERY_BOX_INVALID_ARGUMENT;

    selection_out->entry = NULL;
    selection_out->used_unfiltered_fallback = 0u;

    for (i = 0u;
         i < XZ_NACHT_MYSTERY_BOX_POOL_COUNT;
         ++i)
        order[i] = (uint8_t)i;

    /*
     * Mirror BO3 array::randomize exactly at the algorithm level:
     * every index i swaps against randomint(full_array_size), not the
     * Fisher-Yates shrinking range.
     */
    for (i = 0u;
         i < XZ_NACHT_MYSTERY_BOX_POOL_COUNT;
         ++i) {
        const uint32_t j =
            context->random_below(
                context->user_context,
                XZ_NACHT_MYSTERY_BOX_POOL_COUNT);
        uint8_t temp;

        if (j >= XZ_NACHT_MYSTERY_BOX_POOL_COUNT)
            return XZ_NACHT_MYSTERY_BOX_RNG_OUT_OF_RANGE;

        temp = order[i];
        order[i] = order[j];
        order[j] = temp;
    }

    for (i = 0u;
         i < XZ_NACHT_MYSTERY_BOX_POOL_COUNT;
         ++i) {
        const XzNachtMysteryBoxEntry *entry =
            &kNachtMysteryBoxPool[order[i]];

        if (XzNachtMysteryBox_IsEligible(
                entry,
                context)) {
            selection_out->entry = entry;
            return XZ_NACHT_MYSTERY_BOX_OK;
        }
    }

    /*
     * Stock BO3 falls back to keys[0] if every receiveability check fails.
     * Preserve that behavior for reference-mode parity. In native-safe mode
     * we intentionally refuse to bypass native readiness.
     */
    if (context->require_native_ready)
        return XZ_NACHT_MYSTERY_BOX_NO_ELIGIBLE_NATIVE_WEAPON;

    selection_out->entry =
        &kNachtMysteryBoxPool[order[0]];
    selection_out->used_unfiltered_fallback = 1u;
    return XZ_NACHT_MYSTERY_BOX_OK;
}

void XzNachtMysteryBox_Reset(
    XzNachtMysteryBoxState *state)
{
    if (!state)
        return;

    state->completed_uses = 0u;
    state->busy = 0u;
}

XzNachtMysteryBoxResult XzNachtMysteryBox_TryRoll(
    XzNachtMysteryBoxState *state,
    uint32_t *player_points,
    const XzNachtMysteryBoxSelectionContext *context,
    XzNachtMysteryBoxSelection *selection_out)
{
    XzNachtMysteryBoxResult result;

    if (!state ||
        !player_points ||
        !context ||
        !selection_out)
        return XZ_NACHT_MYSTERY_BOX_INVALID_ARGUMENT;

    if (state->busy)
        return XZ_NACHT_MYSTERY_BOX_BUSY;

    if (*player_points < XZ_NACHT_MYSTERY_BOX_COST)
        return XZ_NACHT_MYSTERY_BOX_INSUFFICIENT_POINTS;

    result =
        XzNachtMysteryBox_Select(
            context,
            selection_out);

    if (result != XZ_NACHT_MYSTERY_BOX_OK)
        return result;

    *player_points -= XZ_NACHT_MYSTERY_BOX_COST;
    state->busy = 1u;
    return XZ_NACHT_MYSTERY_BOX_OK;
}

void XzNachtMysteryBox_CompleteRoll(
    XzNachtMysteryBoxState *state)
{
    if (!state || !state->busy)
        return;

    state->busy = 0u;
    state->completed_uses++;
}

static uint32_t XzNachtMysteryBox_SelfTestRandom(
    void *context,
    uint32_t upper_exclusive)
{
    (void)context;
    return upper_exclusive > 0u
        ? 0u
        : 0u;
}

int XzNachtMysteryBox_SelfTest(void)
{
    XzNachtMysteryBoxSelectionContext context;
    XzNachtMysteryBoxSelection selection;
    XzNachtMysteryBoxState state;
    uint32_t points = 1000u;

    if (XzNachtMysteryBox_Count() !=
        XZ_NACHT_MYSTERY_BOX_POOL_COUNT)
        return 0;

    if (!XzNachtMysteryBox_Get(0u) ||
        strcmp(
            XzNachtMysteryBox_Get(0u)->weapon_id,
            "ar_accurate") != 0)
        return 0;

    if (!XzNachtMysteryBox_Get(33u) ||
        strcmp(
            XzNachtMysteryBox_Get(33u)->weapon_id,
            "thundergun") != 0 ||
        XzNachtMysteryBox_Get(33u)->quota_defined != 1u ||
        XzNachtMysteryBox_Get(33u)->quota != 1u)
        return 0;

    if (XzNachtMysteryBox_Get(
            XZ_NACHT_MYSTERY_BOX_POOL_COUNT) != NULL)
        return 0;

    memset(&context, 0, sizeof(context));
    context.random_below =
        XzNachtMysteryBox_SelfTestRandom;

    if (XzNachtMysteryBox_Select(
            &context,
            &selection) != XZ_NACHT_MYSTERY_BOX_OK ||
        !selection.entry ||
        strcmp(
            selection.entry->weapon_id,
            "thundergun") != 0)
        return 0;

    XzNachtMysteryBox_Reset(&state);

    if (XzNachtMysteryBox_TryRoll(
            &state,
            &points,
            &context,
            &selection) != XZ_NACHT_MYSTERY_BOX_OK ||
        points != 50u ||
        !state.busy ||
        state.completed_uses != 0u)
        return 0;

    XzNachtMysteryBox_CompleteRoll(&state);

    return !state.busy &&
        state.completed_uses == 1u;
}

const char *XzNachtMysteryBox_ResultName(
    XzNachtMysteryBoxResult result)
{
    switch (result) {
    case XZ_NACHT_MYSTERY_BOX_OK:
        return "OK";
    case XZ_NACHT_MYSTERY_BOX_INVALID_ARGUMENT:
        return "INVALID_ARGUMENT";
    case XZ_NACHT_MYSTERY_BOX_RNG_OUT_OF_RANGE:
        return "RNG_OUT_OF_RANGE";
    case XZ_NACHT_MYSTERY_BOX_INSUFFICIENT_POINTS:
        return "INSUFFICIENT_POINTS";
    case XZ_NACHT_MYSTERY_BOX_BUSY:
        return "BUSY";
    case XZ_NACHT_MYSTERY_BOX_NO_ELIGIBLE_NATIVE_WEAPON:
        return "NO_ELIGIBLE_NATIVE_WEAPON";
    default:
        return "UNKNOWN";
    }
}
