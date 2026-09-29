#ifndef XZ_SOURCE_ASSET_PIPELINE_H
#define XZ_SOURCE_ASSET_PIPELINE_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum XzSourceAssetStage {
    XZ_SOURCE_ASSET_NONE = 0,
    XZ_SOURCE_ASSET_PRESENT,
    XZ_SOURCE_ASSET_PARSED,
    XZ_SOURCE_ASSET_DEPENDENCIES_RESOLVED,
    XZ_SOURCE_ASSET_NATIVE_BUILT,
    XZ_SOURCE_ASSET_NATIVE_VERIFIED,
    XZ_SOURCE_ASSET_READY,
    XZ_SOURCE_ASSET_FAILED
} XzSourceAssetStage;

typedef struct XzSourceAssetState {
    uint64_t content_key;
    uint32_t source_type;
    uint32_t native_type;
    uint8_t stage;
    uint8_t required;
} XzSourceAssetState;

int XzSourceAsset_BindNativeAdapter(
    XzSourceAssetState *asset,
    const char *source_class);

int XzSourceAsset_Advance(
    XzSourceAssetState *asset,
    XzSourceAssetStage next_stage);

int XzSourceAsset_Fail(
    XzSourceAssetState *asset);

int XzSourceAsset_IsReady(
    const XzSourceAssetState *asset);

int XzSourceAsset_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif
