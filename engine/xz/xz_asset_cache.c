#include "xz_asset_cache.h"

#include <string.h>

void XzAssetCache_Init(XzAssetCache *cache)
{
    if (!cache)
        return;
    memset(cache, 0, sizeof(*cache));
    cache->generation = 1u;
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
    uint32_t i;

    if (!cache || content_key == 0u)
        return 0;

    for (i = 0u; i < cache->count; ++i) {
        if (cache->entries[i].content_key == content_key &&
            cache->entries[i].asset_type == asset_type) {
            cache->hits++;
            if (out_index)
                *out_index = i + 1u;
            return 1;
        }
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
    uint32_t i;
    XzAssetCacheEntry *entry;

    if (!cache ||
        content_key == 0u ||
        (unsigned int)state > XZ_ASSET_CACHE_FAILED)
        return 0;

    for (i = 0u; i < cache->count; ++i) {
        entry = &cache->entries[i];
        if (entry->content_key == content_key &&
            entry->asset_type == asset_type) {
            if (entry->generation != cache->generation &&
                entry->state >= XZ_ASSET_CACHE_FIXED_UP &&
                state >= XZ_ASSET_CACHE_FIXED_UP) {
                cache->resumed++;
            }
            entry->state = (uint8_t)state;
            entry->generation = cache->generation;
            if (state == XZ_ASSET_CACHE_FAILED)
                cache->failed++;
            if (out_index)
                *out_index = i + 1u;
            return 1;
        }
    }

    if (cache->count >= XZ_ASSET_CACHE_MAX_ENTRIES)
        return 0;

    entry = &cache->entries[cache->count];
    memset(entry, 0, sizeof(*entry));
    entry->content_key = content_key;
    entry->asset_type = asset_type;
    entry->generation = cache->generation;
    entry->state = (uint8_t)state;

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
    uint32_t i;

    if (!cache || content_key == 0u)
        return 0;

    for (i = 0u; i < cache->count; ++i) {
        const XzAssetCacheEntry *entry = &cache->entries[i];
        if (entry->content_key == content_key &&
            entry->asset_type == asset_type)
            return entry->state == XZ_ASSET_CACHE_READY;
    }

    return 0;
}

int XzAssetCache_SelfTest(void)
{
    XzAssetCache cache;

    XzAssetCache_Init(&cache);

    if (!XzAssetCache_Upsert(
            &cache,
            0x1234ull,
            9u,
            XZ_ASSET_CACHE_READY,
            0))
        return 0;

    if (!XzAssetCache_IsReady(&cache, 0x1234ull, 9u))
        return 0;

    XzAssetCache_NewGeneration(&cache);

    if (!XzAssetCache_Upsert(
            &cache,
            0x1234ull,
            9u,
            XZ_ASSET_CACHE_READY,
            0))
        return 0;

    return cache.resumed == 1u;
}
