#include "xz_source_asset_pipeline.h"

int XzSourceAsset_Advance(
    XzSourceAssetState *asset,
    XzSourceAssetStage next_stage)
{
    if (!asset)
        return 0;

    if (asset->stage == XZ_SOURCE_ASSET_FAILED ||
        next_stage == XZ_SOURCE_ASSET_FAILED ||
        next_stage <= asset->stage)
        return 0;

    if ((unsigned int)next_stage >
        (unsigned int)XZ_SOURCE_ASSET_READY)
        return 0;

    if ((unsigned int)next_stage !=
        (unsigned int)asset->stage + 1u)
        return 0;

    asset->stage = (uint8_t)next_stage;
    return 1;
}

int XzSourceAsset_Fail(
    XzSourceAssetState *asset)
{
    if (!asset ||
        asset->stage == XZ_SOURCE_ASSET_READY ||
        asset->stage == XZ_SOURCE_ASSET_FAILED)
        return 0;

    asset->stage = XZ_SOURCE_ASSET_FAILED;
    return 1;
}

int XzSourceAsset_IsReady(
    const XzSourceAssetState *asset)
{
    return asset &&
           asset->stage == XZ_SOURCE_ASSET_READY;
}

int XzSourceAsset_SelfTest(void)
{
    XzSourceAssetState asset = {0};

    asset.content_key = 0x1234ull;
    asset.required = 1u;

    if (!XzSourceAsset_Advance(
            &asset,
            XZ_SOURCE_ASSET_PRESENT))
        return 0;

    if (XzSourceAsset_Advance(
            &asset,
            XZ_SOURCE_ASSET_NATIVE_BUILT))
        return 0;

    if (!XzSourceAsset_Advance(
            &asset,
            XZ_SOURCE_ASSET_PARSED) ||
        !XzSourceAsset_Advance(
            &asset,
            XZ_SOURCE_ASSET_DEPENDENCIES_RESOLVED) ||
        !XzSourceAsset_Advance(
            &asset,
            XZ_SOURCE_ASSET_NATIVE_BUILT) ||
        !XzSourceAsset_Advance(
            &asset,
            XZ_SOURCE_ASSET_NATIVE_VERIFIED) ||
        !XzSourceAsset_Advance(
            &asset,
            XZ_SOURCE_ASSET_READY))
        return 0;

    return XzSourceAsset_IsReady(&asset);
}
