#ifndef XZ_ASSET_CACHE_H
#define XZ_ASSET_CACHE_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_ASSET_CACHE_MAX_ENTRIES 32768u

typedef enum XzAssetCacheState {
    XZ_ASSET_CACHE_EMPTY = 0,
    XZ_ASSET_CACHE_VERIFIED = 1,
    XZ_ASSET_CACHE_LOADED = 2,
    XZ_ASSET_CACHE_FIXED_UP = 3,
    XZ_ASSET_CACHE_READY = 4,
    XZ_ASSET_CACHE_FAILED = 5
} XzAssetCacheState;

typedef struct XzAssetCacheEntry {
    uint64_t content_key;
    uint32_t asset_type;
    uint32_t generation;
    uint8_t state;
} XzAssetCacheEntry;

typedef struct XzAssetCache {
    XzAssetCacheEntry entries[XZ_ASSET_CACHE_MAX_ENTRIES];
    uint32_t count;
    uint32_t hits;
    uint32_t misses;
    uint32_t resumed;
    uint32_t failed;
    uint32_t generation;
} XzAssetCache;

void XzAssetCache_Init(XzAssetCache *cache);

void XzAssetCache_NewGeneration(XzAssetCache *cache);

int XzAssetCache_Find(
    XzAssetCache *cache,
    uint64_t content_key,
    uint32_t asset_type,
    uint32_t *out_index);

int XzAssetCache_Upsert(
    XzAssetCache *cache,
    uint64_t content_key,
    uint32_t asset_type,
    XzAssetCacheState state,
    uint32_t *out_index);

int XzAssetCache_IsReady(
    const XzAssetCache *cache,
    uint64_t content_key,
    uint32_t asset_type);

int XzAssetCache_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif
