#ifndef XZ_ASSET_POOL_H
#define XZ_ASSET_POOL_H

#include <stdint.h>
#include "xz_t7_asset_types.h"

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_ASSET_POOL_TYPE_COUNT XZ_T7_RUNTIME_TYPE_COUNT

typedef struct XzAssetPoolTypeState {
    uint32_t capacity;
    uint32_t used;
    uint32_t high_watermark;
    uint32_t rejected;
} XzAssetPoolTypeState;

typedef struct XzAssetPoolState {
    XzAssetPoolTypeState type[XZ_ASSET_POOL_TYPE_COUNT];
    uint32_t total_capacity;
    uint32_t total_used;
    int ready;
} XzAssetPoolState;

void XzAssetPool_Init(
    XzAssetPoolState *state);

int XzAssetPool_SetCapacity(
    XzAssetPoolState *state,
    XzT7AssetType type,
    uint32_t capacity);

int XzAssetPool_Acquire(
    XzAssetPoolState *state,
    XzT7AssetType type,
    uint32_t count);

int XzAssetPool_Release(
    XzAssetPoolState *state,
    XzT7AssetType type,
    uint32_t count);

int XzAssetPool_IsReady(
    const XzAssetPoolState *state);

int XzAssetPool_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif
