#include "xz_map_runtime.h"

#include <stddef.h>
#include <string.h>

static const char *XzMapRuntime_BaseName(const char *name)
{
    const char *base = name;
    const char *cursor;

    if (!name)
        return "";

    for (cursor = name; *cursor; ++cursor) {
        if (*cursor == '/' || *cursor == '\\')
            base = cursor + 1;
    }

    return base;
}

static void XzMapRuntime_CopyMapId(
    char *destination,
    size_t destination_size,
    const char *world_model_name)
{
    const char *base;
    size_t length;

    if (!destination || destination_size == 0u)
        return;

    destination[0] = '\0';
    base = XzMapRuntime_BaseName(world_model_name);
    length = strlen(base);

    if (length >= 6u &&
        strcmp(base + length - 6u, ".xzmap") == 0) {
        length -= 6u;
    }

    if (length >= destination_size)
        length = destination_size - 1u;

    if (length > 0u)
        memcpy(destination, base, length);

    destination[length] = '\0';
}

static XzMapRuntimeKind XzMapRuntime_Classify(
    const char *map_id,
    int verified_package_mode)
{
    if (!map_id || !map_id[0])
        return XZ_MAP_RUNTIME_NONE;

    /*
     * Nacht remains the golden-reference module even when bundled directly
     * into CI. All other map identities become XZIEL runtime maps only after
     * the Android package installer has verified and promoted their .xzp.
     */
    if (strcmp(map_id, "xziel_nacht_bo3") == 0 ||
        strcmp(map_id, "bo3_nacht_reference") == 0)
        return XZ_MAP_RUNTIME_NACHT_BO3;

    if (verified_package_mode)
        return XZ_MAP_RUNTIME_XZIEL_PACKAGE;

    return XZ_MAP_RUNTIME_NONE;
}

void XzMapRuntime_Init(XzMapRuntimeState *state)
{
    if (!state)
        return;

    memset(state, 0, sizeof(*state));
    state->kind = XZ_MAP_RUNTIME_NONE;
    XzWorldTransform_Init(&state->world_transform);
    XzNacht_Reset(&state->nacht);
}

void XzMapRuntime_SetWorldModel(
    XzMapRuntimeState *state,
    const char *world_model_name)
{
    char next_id[XZ_MAP_RUNTIME_NAME_MAX];
    XzMapRuntimeKind next_kind;

    if (!state)
        return;

    XzMapRuntime_CopyMapId(
        next_id,
        sizeof(next_id),
        world_model_name);

    next_kind = XzMapRuntime_Classify(
        next_id,
        state->verified_package_mode);

    memset(state->map_id, 0, sizeof(state->map_id));
    memcpy(
        state->map_id,
        next_id,
        strlen(next_id) + 1u);
    state->kind = next_kind;
    state->generation++;

    /*
     * BO3 reference metadata is already normalized to X,-Y,Z meters. Keep an
     * identity basis and the shared XZIEL 39.3700787402 units/m convention.
     * A future geometry package may override only the origins/basis through
     * XzMapRuntime_SetWorldTransform without touching gameplay definitions.
     */
    XzWorldTransform_Init(&state->world_transform);

    /*
     * Every invocation represents a real XZIEL world load. Reloading the same
     * map must start a fresh match too.
     */
    XzNacht_Reset(&state->nacht);
}

void XzMapRuntime_SetVerifiedPackageMode(
    XzMapRuntimeState *state,
    int enabled)
{
    if (!state)
        return;

    state->verified_package_mode = enabled ? 1 : 0;
    state->kind = XzMapRuntime_Classify(
        state->map_id,
        state->verified_package_mode);
}

int XzMapRuntime_IsVerifiedPackage(
    const XzMapRuntimeState *state)
{
    return state ? state->verified_package_mode : 0;
}

XzMapRuntimeKind XzMapRuntime_Kind(
    const XzMapRuntimeState *state)
{
    return state ? state->kind : XZ_MAP_RUNTIME_NONE;
}

const char *XzMapRuntime_KindName(
    XzMapRuntimeKind kind)
{
    switch (kind) {
    case XZ_MAP_RUNTIME_XZIEL_PACKAGE:
        return "XZIEL_PACKAGE";
    case XZ_MAP_RUNTIME_NACHT_BO3:
        return "NACHT_BO3";
    case XZ_MAP_RUNTIME_NONE:
    default:
        return "NONE";
    }
}

const char *XzMapRuntime_MapId(
    const XzMapRuntimeState *state)
{
    return state ? state->map_id : "";
}

const XzWorldTransform *XzMapRuntime_WorldTransform(
    const XzMapRuntimeState *state)
{
    return state ? &state->world_transform : NULL;
}

int XzMapRuntime_SetWorldTransform(
    XzMapRuntimeState *state,
    const XzWorldTransform *transform)
{
    if (!state ||
        !transform ||
        !XzWorldTransform_IsValid(transform))
        return 0;

    state->world_transform = *transform;
    return 1;
}

static XzWorldVec3 XzMapRuntime_FromNachtMeters(
    XzNachtVec3 value)
{
    XzWorldVec3 result;
    result.x = value.x;
    result.y = value.y;
    result.z = value.z;
    return result;
}

static XzNachtVec3 XzMapRuntime_ToNachtMeters(
    XzWorldVec3 value)
{
    XzNachtVec3 result;
    result.x = value.x;
    result.y = value.y;
    result.z = value.z;
    return result;
}

int XzMapRuntime_NachtPurchasePositionUnits(
    const XzMapRuntimeState *state,
    size_t index,
    XzWorldVec3 *out_position_units)
{
    const XzNachtPurchase *purchase;

    if (!state ||
        state->kind != XZ_MAP_RUNTIME_NACHT_BO3 ||
        !out_position_units)
        return 0;

    purchase = XzNacht_GetPurchase(index);
    if (!purchase)
        return 0;

    *out_position_units =
        XzWorldTransform_ToRuntime(
            &state->world_transform,
            XzMapRuntime_FromNachtMeters(
                purchase->position_m));
    return 1;
}

const XzBo3WeaponSpec *XzMapRuntime_NachtPurchaseWeaponSpec(
    const XzMapRuntimeState *state,
    size_t index)
{
    const XzNachtPurchase *purchase;

    if (!state ||
        state->kind != XZ_MAP_RUNTIME_NACHT_BO3)
        return NULL;

    purchase = XzNacht_GetPurchase(index);
    if (!purchase ||
        !purchase->logical_item_id ||
        strcmp(purchase->logical_item_id, "frag_grenade") == 0)
        return NULL;

    return XzBo3WeaponSpec_FindByLogicalItemId(
        purchase->logical_item_id);
}

int XzMapRuntime_NachtDoorPositionUnits(
    const XzMapRuntimeState *state,
    size_t index,
    XzWorldVec3 *out_position_units)
{
    const XzNachtDoor *door;

    if (!state ||
        state->kind != XZ_MAP_RUNTIME_NACHT_BO3 ||
        !out_position_units)
        return 0;

    door = XzNacht_GetDoor(index);
    if (!door)
        return 0;

    *out_position_units =
        XzWorldTransform_ToRuntime(
            &state->world_transform,
            XzMapRuntime_FromNachtMeters(
                door->position_m));
    return 1;
}

int XzMapRuntime_NachtBarricadePositionUnits(
    const XzMapRuntimeState *state,
    size_t index,
    XzWorldVec3 *out_position_units)
{
    const XzNachtBarricade *barricade;

    if (!state ||
        state->kind != XZ_MAP_RUNTIME_NACHT_BO3 ||
        !out_position_units)
        return 0;

    barricade = XzNacht_GetBarricade(index);
    if (!barricade)
        return 0;

    *out_position_units =
        XzWorldTransform_ToRuntime(
            &state->world_transform,
            XzMapRuntime_FromNachtMeters(
                barricade->position_m));
    return 1;
}

int XzMapRuntime_NachtSpawnPositionUnits(
    const XzMapRuntimeState *state,
    size_t index,
    XzWorldVec3 *out_position_units)
{
    const XzNachtSpawn *spawn;

    if (!state ||
        state->kind != XZ_MAP_RUNTIME_NACHT_BO3 ||
        !out_position_units)
        return 0;

    spawn = XzNacht_GetSpawn(index);
    if (!spawn)
        return 0;

    *out_position_units =
        XzWorldTransform_ToRuntime(
            &state->world_transform,
            XzMapRuntime_FromNachtMeters(
                spawn->position_m));
    return 1;
}

int XzMapRuntime_NachtFindNearestPurchaseUnits(
    const XzMapRuntimeState *state,
    XzWorldVec3 player_position_units,
    size_t *out_index,
    float *out_distance_m)
{
    XzWorldVec3 source_m;

    if (!state ||
        state->kind != XZ_MAP_RUNTIME_NACHT_BO3)
        return 0;

    source_m = XzWorldTransform_ToSourceMeters(
        &state->world_transform,
        player_position_units);

    return XzNacht_FindNearestPurchase(
        &state->nacht,
        XzMapRuntime_ToNachtMeters(source_m),
        out_index,
        out_distance_m);
}

int XzMapRuntime_NachtFindNearestDoorUnits(
    const XzMapRuntimeState *state,
    XzWorldVec3 player_position_units,
    size_t *out_index,
    float *out_distance_m)
{
    XzWorldVec3 source_m;

    if (!state ||
        state->kind != XZ_MAP_RUNTIME_NACHT_BO3)
        return 0;

    source_m = XzWorldTransform_ToSourceMeters(
        &state->world_transform,
        player_position_units);

    return XzNacht_FindNearestDoor(
        &state->nacht,
        XzMapRuntime_ToNachtMeters(source_m),
        out_index,
        out_distance_m);
}

XzNachtResult XzMapRuntime_NachtTryPurchaseUnits(
    XzMapRuntimeState *state,
    size_t index,
    XzWorldVec3 player_position_units,
    const char **out_logical_item_id)
{
    XzWorldVec3 source_m;

    if (!state ||
        state->kind != XZ_MAP_RUNTIME_NACHT_BO3)
        return XZ_NACHT_RESULT_INVALID_INDEX;

    source_m = XzWorldTransform_ToSourceMeters(
        &state->world_transform,
        player_position_units);

    return XzNacht_TryPurchase(
        &state->nacht,
        index,
        XzMapRuntime_ToNachtMeters(source_m),
        out_logical_item_id);
}

XzNachtResult XzMapRuntime_NachtTryOpenDoorUnits(
    XzMapRuntimeState *state,
    size_t index,
    XzWorldVec3 player_position_units)
{
    XzWorldVec3 source_m;

    if (!state ||
        state->kind != XZ_MAP_RUNTIME_NACHT_BO3)
        return XZ_NACHT_RESULT_INVALID_INDEX;

    source_m = XzWorldTransform_ToSourceMeters(
        &state->world_transform,
        player_position_units);

    return XzNacht_TryOpenDoor(
        &state->nacht,
        index,
        XzMapRuntime_ToNachtMeters(source_m));
}

XzNachtGameplayState *XzMapRuntime_Nacht(
    XzMapRuntimeState *state)
{
    if (!state || state->kind != XZ_MAP_RUNTIME_NACHT_BO3)
        return NULL;

    return &state->nacht;
}

const XzNachtGameplayState *XzMapRuntime_NachtConst(
    const XzMapRuntimeState *state)
{
    if (!state || state->kind != XZ_MAP_RUNTIME_NACHT_BO3)
        return NULL;

    return &state->nacht;
}

int XzMapRuntime_SelfTest(void)
{
    XzMapRuntimeState state;
    uint64_t generation;

    XzMapRuntime_Init(&state);

    if (!XzWorldTransform_IsValid(&state.world_transform))
        return 0;

    if (state.kind != XZ_MAP_RUNTIME_NONE ||
        state.generation != 0u ||
        state.nacht.points != 500u ||
        state.nacht.active_zone_mask != XZ_NACHT_ZONE_START)
        return 0;

    /*
     * Arbitrary maps do not become trusted XZIEL runtimes by filename.
     * Package verification is an explicit promotion signal.
     */
    XzMapRuntime_SetWorldModel(
        &state,
        "maps/community_test.xzmap");
    if (state.kind != XZ_MAP_RUNTIME_NONE ||
        XzMapRuntime_IsVerifiedPackage(&state) != 0)
        return 0;

    XzMapRuntime_SetVerifiedPackageMode(&state, 1);
    if (state.kind != XZ_MAP_RUNTIME_XZIEL_PACKAGE ||
        XzMapRuntime_IsVerifiedPackage(&state) != 1 ||
        strcmp(
            XzMapRuntime_KindName(state.kind),
            "XZIEL_PACKAGE") != 0 ||
        XzMapRuntime_Nacht(&state) != NULL)
        return 0;

    XzMapRuntime_SetVerifiedPackageMode(&state, 0);
    if (state.kind != XZ_MAP_RUNTIME_NONE)
        return 0;

    generation = state.generation;

    XzMapRuntime_SetWorldModel(
        &state,
        "maps/xziel_nacht_bo3.xzmap");

    if (state.kind != XZ_MAP_RUNTIME_NACHT_BO3 ||
        strcmp(state.map_id, "xziel_nacht_bo3") != 0 ||
        XzMapRuntime_Nacht(&state) == NULL ||
        state.nacht.points != 500u ||
        XzNacht_ActiveSpawnCount(&state.nacht) != 10u ||
        state.generation != generation + 1u)
        return 0;

    XzNacht_AwardPoints(&state.nacht, 250u);
    if (state.nacht.points != 750u)
        return 0;

    /* Reloading the same world starts a fresh match. */
    generation = state.generation;
    XzMapRuntime_SetWorldModel(
        &state,
        "maps/xziel_nacht_bo3.xzmap");
    if (state.generation != generation + 1u ||
        state.nacht.points != 500u ||
        XzNacht_ActiveSpawnCount(&state.nacht) != 10u)
        return 0;

    return 1;
}
