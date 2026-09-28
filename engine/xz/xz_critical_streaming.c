#include "xz_critical_streaming.h"

#include <limits.h>
#include <stdlib.h>
#include <string.h>

static uint32_t XzCriticalStreaming_Hash(
    uint64_t key,
    uint32_t asset_type)
{
    uint64_t x =
        key ^
        ((uint64_t)asset_type *
         0x9E3779B97F4A7C15ull);

    x ^= x >> 33;
    x *= 0xff51afd7ed558ccdull;
    x ^= x >> 33;
    x *= 0xc4ceb9fe1a85ec53ull;
    x ^= x >> 33;

    return (uint32_t)(x ^ (x >> 32));
}

static void XzCriticalStreaming_RecomputeReady(
    XzCriticalStreamingState *state)
{
    if (!state)
        return;

    state->ready =
        state->asset_count > 0u &&
        state->failed_count == 0u &&
        state->native_ready_count ==
            state->asset_count &&
        state->resident_count ==
            state->asset_count;
}

static int XzCriticalStreaming_Reserve(
    XzCriticalStreamingState *state,
    uint32_t needed)
{
    uint32_t capacity;
    size_t bytes;
    XzCriticalStreamAsset *grown;

    if (!state)
        return 0;

    if (needed <= state->asset_capacity)
        return 1;

    capacity =
        state->asset_capacity
            ? state->asset_capacity
            : XZ_CRITICAL_STREAM_INITIAL_ENTRIES;

    while (capacity < needed) {
        if (capacity > UINT32_MAX / 2u) {
            capacity = needed;
            break;
        }
        capacity *= 2u;
    }

    bytes =
        (size_t)capacity *
        sizeof(*state->assets);

    if (capacity != 0u &&
        bytes / sizeof(*state->assets) !=
            (size_t)capacity)
        return 0;

    grown =
        (XzCriticalStreamAsset *)realloc(
            state->assets,
            bytes);

    if (!grown)
        return 0;

    memset(
        grown + state->asset_capacity,
        0,
        (size_t)(capacity -
                 state->asset_capacity) *
            sizeof(*state->assets));

    state->assets = grown;
    state->asset_capacity = capacity;
    return 1;
}

static int XzCriticalStreaming_Rehash(
    XzCriticalStreamingState *state,
    uint32_t requested)
{
    uint32_t buckets =
        XZ_CRITICAL_STREAM_INITIAL_BUCKETS;
    uint32_t *table;
    uint32_t i;

    if (!state)
        return 0;

    while (buckets < requested) {
        if (buckets > UINT32_MAX / 2u) {
            buckets = requested;
            break;
        }
        buckets *= 2u;
    }

    table =
        (uint32_t *)calloc(
            buckets,
            sizeof(*table));

    if (!table)
        return 0;

    for (i = 0u; i < state->asset_count; ++i) {
        uint32_t bucket =
            XzCriticalStreaming_Hash(
                state->assets[i].content_key,
                state->assets[i].asset_type) %
            buckets;

        state->assets[i].next_hash =
            table[bucket];
        table[bucket] = i + 1u;
    }

    free(state->buckets);
    state->buckets = table;
    state->bucket_count = buckets;
    return 1;
}

static int XzCriticalStreaming_EnsureHash(
    XzCriticalStreamingState *state,
    uint32_t needed_entries)
{
    uint64_t requested =
        (uint64_t)needed_entries * 2ull;

    if (requested <
        XZ_CRITICAL_STREAM_INITIAL_BUCKETS)
        requested =
            XZ_CRITICAL_STREAM_INITIAL_BUCKETS;

    if (requested > UINT32_MAX)
        return 0;

    if (state->bucket_count >=
        (uint32_t)requested)
        return 1;

    return XzCriticalStreaming_Rehash(
        state,
        (uint32_t)requested);
}

static int XzCriticalStreaming_FindIndex(
    const XzCriticalStreamingState *state,
    uint64_t key,
    uint32_t asset_type,
    uint32_t *out_index)
{
    uint32_t link;
    uint32_t bucket;

    if (!state ||
        !state->buckets ||
        state->bucket_count == 0u ||
        key == 0u)
        return 0;

    bucket =
        XzCriticalStreaming_Hash(
            key,
            asset_type) %
        state->bucket_count;

    link = state->buckets[bucket];

    while (link != 0u) {
        uint32_t index = link - 1u;
        const XzCriticalStreamAsset *asset;

        if (index >= state->asset_count)
            return 0;

        asset = &state->assets[index];

        if (asset->content_key == key &&
            asset->asset_type == asset_type) {
            if (out_index)
                *out_index = index + 1u;
            return 1;
        }

        link = asset->next_hash;
    }

    return 0;
}

void XzCriticalStreaming_Init(
    XzCriticalStreamingState *state)
{
    if (!state)
        return;

    memset(state, 0, sizeof(*state));
    state->generation = 1u;
}

void XzCriticalStreaming_Destroy(
    XzCriticalStreamingState *state)
{
    if (!state)
        return;

    free(state->assets);
    free(state->buckets);
    memset(state, 0, sizeof(*state));
}

void XzCriticalStreaming_NewGeneration(
    XzCriticalStreamingState *state)
{
    uint32_t i;

    if (!state)
        return;

    state->generation++;
    if (state->generation == 0u)
        state->generation = 1u;

    state->native_ready_count = 0u;
    state->resident_count = 0u;
    state->failed_count = 0u;
    state->ready = 0;

    for (i = 0u; i < state->asset_count; ++i) {
        state->assets[i].native_ready = 0u;
        state->assets[i].resident = 0u;
        state->assets[i].failed = 0u;
    }
}

int XzCriticalStreaming_Require(
    XzCriticalStreamingState *state,
    uint64_t content_key,
    uint32_t asset_type,
    uint32_t *out_index)
{
    uint32_t existing = 0u;
    XzCriticalStreamAsset *asset;
    uint32_t bucket;

    if (!state || content_key == 0u)
        return 0;

    if (XzCriticalStreaming_FindIndex(
            state,
            content_key,
            asset_type,
            &existing)) {
        if (out_index)
            *out_index = existing;
        return 1;
    }

    if (!XzCriticalStreaming_Reserve(
            state,
            state->asset_count + 1u))
        return 0;

    if (!XzCriticalStreaming_EnsureHash(
            state,
            state->asset_count + 1u))
        return 0;

    asset = &state->assets[state->asset_count];
    memset(asset, 0, sizeof(*asset));
    asset->content_key = content_key;
    asset->asset_type = asset_type;

    bucket =
        XzCriticalStreaming_Hash(
            content_key,
            asset_type) %
        state->bucket_count;

    asset->next_hash = state->buckets[bucket];
    state->buckets[bucket] =
        state->asset_count + 1u;

    state->asset_count++;
    state->ready = 0;

    if (out_index)
        *out_index = state->asset_count;

    return 1;
}

int XzCriticalStreaming_SetNativeReady(
    XzCriticalStreamingState *state,
    uint64_t content_key,
    uint32_t asset_type,
    int ready)
{
    uint32_t index = 0u;
    XzCriticalStreamAsset *asset;
    uint8_t value = ready ? 1u : 0u;

    if (!XzCriticalStreaming_FindIndex(
            state,
            content_key,
            asset_type,
            &index))
        return 0;

    asset = &state->assets[index - 1u];

    if (asset->native_ready != value) {
        if (value)
            state->native_ready_count++;
        else if (state->native_ready_count > 0u)
            state->native_ready_count--;

        asset->native_ready = value;
    }

    XzCriticalStreaming_RecomputeReady(state);
    return 1;
}

int XzCriticalStreaming_SetResident(
    XzCriticalStreamingState *state,
    uint64_t content_key,
    uint32_t asset_type,
    int resident)
{
    uint32_t index = 0u;
    XzCriticalStreamAsset *asset;
    uint8_t value = resident ? 1u : 0u;

    if (!XzCriticalStreaming_FindIndex(
            state,
            content_key,
            asset_type,
            &index))
        return 0;

    asset = &state->assets[index - 1u];

    if (asset->resident != value) {
        if (value)
            state->resident_count++;
        else if (state->resident_count > 0u)
            state->resident_count--;

        asset->resident = value;
    }

    XzCriticalStreaming_RecomputeReady(state);
    return 1;
}

int XzCriticalStreaming_SetFailed(
    XzCriticalStreamingState *state,
    uint64_t content_key,
    uint32_t asset_type,
    int failed)
{
    uint32_t index = 0u;
    XzCriticalStreamAsset *asset;
    uint8_t value = failed ? 1u : 0u;

    if (!XzCriticalStreaming_FindIndex(
            state,
            content_key,
            asset_type,
            &index))
        return 0;

    asset = &state->assets[index - 1u];

    if (asset->failed != value) {
        if (value)
            state->failed_count++;
        else if (state->failed_count > 0u)
            state->failed_count--;

        asset->failed = value;
    }

    XzCriticalStreaming_RecomputeReady(state);
    return 1;
}

int XzCriticalStreaming_IsReady(
    const XzCriticalStreamingState *state)
{
    return state ? state->ready : 0;
}

int XzCriticalStreaming_SelfTest(void)
{
    XzCriticalStreamingState state;
    uint32_t i;
    int ok = 0;

    XzCriticalStreaming_Init(&state);

    for (i = 0u; i < 5000u; ++i) {
        uint64_t key =
            0xABC0000000000000ull +
            (uint64_t)i + 1ull;

        if (!XzCriticalStreaming_Require(
                &state,
                key,
                9u,
                NULL) ||
            !XzCriticalStreaming_SetNativeReady(
                &state,
                key,
                9u,
                1) ||
            !XzCriticalStreaming_SetResident(
                &state,
                key,
                9u,
                1))
            goto cleanup;
    }

    if (!XzCriticalStreaming_IsReady(&state) ||
        state.asset_count != 5000u ||
        state.native_ready_count != 5000u ||
        state.resident_count != 5000u)
        goto cleanup;

    if (!XzCriticalStreaming_SetFailed(
            &state,
            0xABC0000000000001ull,
            9u,
            1) ||
        XzCriticalStreaming_IsReady(&state))
        goto cleanup;

    if (!XzCriticalStreaming_SetFailed(
            &state,
            0xABC0000000000001ull,
            9u,
            0) ||
        !XzCriticalStreaming_IsReady(&state))
        goto cleanup;

    XzCriticalStreaming_NewGeneration(&state);

    if (XzCriticalStreaming_IsReady(&state) ||
        state.native_ready_count != 0u ||
        state.resident_count != 0u)
        goto cleanup;

    ok = 1;

cleanup:
    XzCriticalStreaming_Destroy(&state);
    return ok;
}
