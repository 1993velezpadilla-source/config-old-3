#include "xz_asset_cache.h"

#include <limits.h>
#include <stdlib.h>
#include <string.h>

static uint32_t XzAssetCache_Hash(
    uint64_t content_key,
    uint32_t asset_type)
{
    uint64_t x =
        content_key ^
        ((uint64_t)asset_type *
         0x9E3779B97F4A7C15ull);

    x ^= x >> 33;
    x *= 0xff51afd7ed558ccdull;
    x ^= x >> 33;
    x *= 0xc4ceb9fe1a85ec53ull;
    x ^= x >> 33;

    return (uint32_t)(x ^ (x >> 32));
}

static int XzAssetCache_ReserveEntries(
    XzAssetCache *cache,
    uint32_t needed)
{
    uint32_t new_capacity;
    XzAssetCacheEntry *grown;

    if (!cache)
        return 0;

    if (needed <= cache->capacity)
        return 1;

    new_capacity =
        cache->capacity > 0u
            ? cache->capacity
            : XZ_ASSET_CACHE_INITIAL_ENTRIES;

    while (new_capacity < needed) {
        if (new_capacity > UINT32_MAX / 2u) {
            new_capacity = needed;
            break;
        }
        new_capacity *= 2u;
    }

    if ((size_t)new_capacity >
        SIZE_MAX / sizeof(*cache->entries))
        return 0;

    grown =
        (XzAssetCacheEntry *)realloc(
            cache->entries,
            (size_t)new_capacity *
                sizeof(*cache->entries));

    if (!grown)
        return 0;

    memset(
        grown + cache->capacity,
        0,
        (size_t)(new_capacity - cache->capacity) *
            sizeof(*cache->entries));

    cache->entries = grown;
    cache->capacity = new_capacity;
    return 1;
}

static int XzAssetCache_Rehash(
    XzAssetCache *cache,
    uint32_t requested_bucket_count)
{
    uint32_t bucket_count =
        XZ_ASSET_CACHE_INITIAL_BUCKETS;
    uint32_t *buckets;
    uint32_t i;

    if (!cache)
        return 0;

    while (bucket_count < requested_bucket_count) {
        if (bucket_count > UINT32_MAX / 2u) {
            bucket_count = requested_bucket_count;
            break;
        }
        bucket_count *= 2u;
    }

    if (bucket_count == 0u)
        return 0;

    buckets =
        (uint32_t *)calloc(
            bucket_count,
            sizeof(*buckets));

    if (!buckets)
        return 0;

    for (i = 0u; i < cache->count; ++i) {
        uint32_t bucket =
            XzAssetCache_Hash(
                cache->entries[i].content_key,
                cache->entries[i].asset_type) %
            bucket_count;

        cache->entries[i].next_hash =
            buckets[bucket];
        buckets[bucket] = i + 1u;
    }

    free(cache->buckets);
    cache->buckets = buckets;
    cache->bucket_count = bucket_count;
    return 1;
}

static int XzAssetCache_EnsureHashCapacity(
    XzAssetCache *cache,
    uint32_t entry_count)
{
    uint64_t requested;

    if (!cache)
        return 0;

    requested = (uint64_t)entry_count * 2ull;
    if (requested <
        XZ_ASSET_CACHE_INITIAL_BUCKETS) {
        requested =
            XZ_ASSET_CACHE_INITIAL_BUCKETS;
    }

    if (requested > UINT32_MAX)
        return 0;

    if (cache->bucket_count >=
        (uint32_t)requested)
        return 1;

    return XzAssetCache_Rehash(
        cache,
        (uint32_t)requested);
}

static int XzAssetCache_FindIndex(
    const XzAssetCache *cache,
    uint64_t content_key,
    uint32_t asset_type,
    uint32_t *out_index)
{
    uint32_t link;
    uint32_t bucket;

    if (!cache ||
        !cache->buckets ||
        cache->bucket_count == 0u ||
        content_key == 0u)
        return 0;

    bucket =
        XzAssetCache_Hash(
            content_key,
            asset_type) %
        cache->bucket_count;

    link = cache->buckets[bucket];
    while (link != 0u) {
        uint32_t index = link - 1u;
        const XzAssetCacheEntry *entry;

        if (index >= cache->count)
            return 0;

        entry = &cache->entries[index];
        if (entry->content_key == content_key &&
            entry->asset_type == asset_type) {
            if (out_index)
                *out_index = index + 1u;
            return 1;
        }

        link = entry->next_hash;
    }

    return 0;
}

void XzAssetCache_Init(XzAssetCache *cache)
{
    if (!cache)
        return;

    memset(cache, 0, sizeof(*cache));
    cache->generation = 1u;
}

void XzAssetCache_Destroy(XzAssetCache *cache)
{
    if (!cache)
        return;

    free(cache->entries);
    free(cache->buckets);
    memset(cache, 0, sizeof(*cache));
}

void XzAssetCache_NewGeneration(XzAssetCache *cache)
{
    if (!cache)
        return;

    cache->generation++;
    if (cache->generation == 0u)
        cache->generation = 1u;
}

int XzAssetCache_Find(
    XzAssetCache *cache,
    uint64_t content_key,
    uint32_t asset_type,
    uint32_t *out_index)
{
    if (!cache || content_key == 0u)
        return 0;

    if (XzAssetCache_FindIndex(
            cache,
            content_key,
            asset_type,
            out_index)) {
        cache->hits++;
        return 1;
    }

    cache->misses++;
    return 0;
}

int XzAssetCache_Upsert(
    XzAssetCache *cache,
    uint64_t content_key,
    uint32_t asset_type,
    XzAssetCacheState state,
    uint32_t *out_index)
{
    uint32_t existing_index = 0u;
    XzAssetCacheEntry *entry;
    uint32_t bucket;

    if (!cache ||
        content_key == 0u ||
        (unsigned int)state >
            XZ_ASSET_CACHE_FAILED)
        return 0;

    if (XzAssetCache_FindIndex(
            cache,
            content_key,
            asset_type,
            &existing_index)) {
        entry =
            &cache->entries[existing_index - 1u];

        if (entry->generation !=
                cache->generation &&
            entry->state >=
                XZ_ASSET_CACHE_FIXED_UP &&
            state >=
                XZ_ASSET_CACHE_FIXED_UP) {
            cache->resumed++;
        }

        entry->state = (uint8_t)state;
        entry->generation = cache->generation;

        if (state == XZ_ASSET_CACHE_FAILED)
            cache->failed++;

        if (out_index)
            *out_index = existing_index;

        return 1;
    }

    if (!XzAssetCache_ReserveEntries(
            cache,
            cache->count + 1u))
        return 0;

    if (!XzAssetCache_EnsureHashCapacity(
            cache,
            cache->count + 1u))
        return 0;

    entry = &cache->entries[cache->count];
    memset(entry, 0, sizeof(*entry));
    entry->content_key = content_key;
    entry->asset_type = asset_type;
    entry->generation = cache->generation;
    entry->state = (uint8_t)state;

    bucket =
        XzAssetCache_Hash(
            content_key,
            asset_type) %
        cache->bucket_count;

    entry->next_hash = cache->buckets[bucket];
    cache->buckets[bucket] = cache->count + 1u;

    if (state == XZ_ASSET_CACHE_FAILED)
        cache->failed++;

    cache->count++;

    if (out_index)
        *out_index = cache->count;

    return 1;
}

int XzAssetCache_IsReady(
    const XzAssetCache *cache,
    uint64_t content_key,
    uint32_t asset_type)
{
    uint32_t index = 0u;

    if (!XzAssetCache_FindIndex(
            cache,
            content_key,
            asset_type,
            &index))
        return 0;

    return cache->entries[index - 1u].state ==
        XZ_ASSET_CACHE_READY;
}

int XzAssetCache_SelfTest(void)
{
    XzAssetCache cache;
    uint32_t i;
    int ok = 0;

    XzAssetCache_Init(&cache);

    if (!XzAssetCache_Upsert(
            &cache,
            0x1234ull,
            9u,
            XZ_ASSET_CACHE_READY,
            NULL))
        goto cleanup;

    if (!XzAssetCache_IsReady(
            &cache,
            0x1234ull,
            9u))
        goto cleanup;

    for (i = 0u; i < 40000u; ++i) {
        if (!XzAssetCache_Upsert(
                &cache,
                0x100000ull + i,
                9u,
                XZ_ASSET_CACHE_VERIFIED,
                NULL))
            goto cleanup;
    }

    if (cache.count < 40001u ||
        cache.capacity < cache.count ||
        cache.bucket_count <
            XZ_ASSET_CACHE_INITIAL_BUCKETS)
        goto cleanup;

    XzAssetCache_NewGeneration(&cache);

    if (!XzAssetCache_Upsert(
            &cache,
            0x1234ull,
            9u,
            XZ_ASSET_CACHE_READY,
            NULL))
        goto cleanup;

    if (cache.resumed != 1u)
        goto cleanup;

    ok = 1;

cleanup:
    XzAssetCache_Destroy(&cache);
    return ok;
}
