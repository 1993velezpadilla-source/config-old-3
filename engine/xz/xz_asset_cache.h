#ifndef XZ_ASSET_CACHE_H
#define XZ_ASSET_CACHE_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_ASSET_CACHE_INITIAL_ENTRIES 4096u
#define XZ_ASSET_CACHE_INITIAL_BUCKETS 8192u

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
    uint32_t next_hash;
    uint8_t state;
} XzAssetCacheEntry;

typedef struct XzAssetCache {
    XzAssetCacheEntry *entries;
    uint32_t *buckets;
    uint32_t count;
    uint32_t capacity;
    uint32_t bucket_count;
    uint32_t hits;
    uint32_t misses;
    uint32_t resumed;
    uint32_t failed;
    uint32_t generation;
} XzAssetCache;

void XzAssetCache_Init(XzAssetCache *cache);

void XzAssetCache_Destroy(XzAssetCache *cache);

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
