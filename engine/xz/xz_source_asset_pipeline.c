#include "xz_source_asset_pipeline.h"
#include "xz_source_native_registry.h"

int XzSourceAsset_BindNativeAdapter(
    XzSourceAssetState *asset,
    const char *source_class)
{
    const XzSourceNativeAdapter *adapter;

    if (!asset ||
        !source_class ||
        !source_class[0] ||
        asset->stage >= XZ_SOURCE_ASSET_NATIVE_BUILT)
        return 0;

    adapter =
        XzSourceNativeRegistry_Find(
            source_class);

    if (!adapter)
        return 0;

    asset->native_type =
        (uint32_t)adapter->native_type;

    return 1;
}

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

    if (!XzSourceAsset_BindNativeAdapter(
            &asset,
            "Texture2D") ||
        asset.native_type !=
            (uint32_t)XZ_NATIVE_PAYLOAD_XZTX)
        return 0;

    if (XzSourceAsset_BindNativeAdapter(
            &asset,
            "Material"))
        return 0;

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
