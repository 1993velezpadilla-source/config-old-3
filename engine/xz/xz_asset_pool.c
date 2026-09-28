#include "xz_asset_pool.h"

#include <string.h>

void XzAssetPool_Init(
    XzAssetPoolState *state)
{
    if (!state)
        return;

    memset(state, 0, sizeof(*state));
}

int XzAssetPool_SetCapacity(
    XzAssetPoolState *state,
    XzT7AssetType type,
    uint32_t capacity)
{
    unsigned int index = (unsigned int)type;
    uint32_t old_capacity;

    if (!state ||
        index >= XZ_ASSET_POOL_TYPE_COUNT ||
        capacity < state->type[index].used)
        return 0;

    old_capacity = state->type[index].capacity;
    state->type[index].capacity = capacity;

    if (state->total_capacity >= old_capacity)
        state->total_capacity -= old_capacity;
    state->total_capacity += capacity;

    state->ready = state->total_capacity > 0u;
    return 1;
}

int XzAssetPool_Acquire(
    XzAssetPoolState *state,
    XzT7AssetType type,
    uint32_t count)
{
    unsigned int index = (unsigned int)type;
    XzAssetPoolTypeState *pool;

    if (!state || index >= XZ_ASSET_POOL_TYPE_COUNT)
        return 0;

    pool = &state->type[index];
    if (count > pool->capacity - pool->used) {
        pool->rejected += count;
        return 0;
    }

    pool->used += count;
    state->total_used += count;
    if (pool->used > pool->high_watermark)
        pool->high_watermark = pool->used;

    return 1;
}

int XzAssetPool_Release(
    XzAssetPoolState *state,
    XzT7AssetType type,
    uint32_t count)
{
    unsigned int index = (unsigned int)type;
    XzAssetPoolTypeState *pool;

    if (!state || index >= XZ_ASSET_POOL_TYPE_COUNT)
        return 0;

    pool = &state->type[index];
    if (count > pool->used)
        return 0;

    pool->used -= count;
    state->total_used -= count;
    return 1;
}

int XzAssetPool_IsReady(
    const XzAssetPoolState *state)
{
    return state ? state->ready : 0;
}

int XzAssetPool_SelfTest(void)
{
    XzAssetPoolState state;

    XzAssetPool_Init(&state);

    if (!XzAssetPool_SetCapacity(&state, XZ_T7_IMAGE, 2u))
        return 0;

    if (!XzAssetPool_Acquire(&state, XZ_T7_IMAGE, 2u))
        return 0;

    if (XzAssetPool_Acquire(&state, XZ_T7_IMAGE, 1u))
        return 0;

    if (state.type[XZ_T7_IMAGE].rejected != 1u)
        return 0;

    if (!XzAssetPool_Release(&state, XZ_T7_IMAGE, 1u))
        return 0;

    return XzAssetPool_IsReady(&state) &&
           state.total_used == 1u &&
           state.type[XZ_T7_IMAGE].high_watermark == 2u;
}
