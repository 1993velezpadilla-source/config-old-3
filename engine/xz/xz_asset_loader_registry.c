#include "xz_asset_loader_registry.h"

#include <string.h>

void XzAssetLoaderRegistry_Init(
    XzAssetLoaderRegistry *registry)
{
    unsigned int i;

    if (!registry)
        return;

    memset(registry, 0, sizeof(*registry));

    for (i = 0u; i < XZ_T7_RUNTIME_TYPE_COUNT; ++i) {
        registry->specs[i].type = (XzT7AssetType)i;
        registry->specs[i].load_policy = XZ_ASSET_LOAD_DELAY;
        registry->specs[i].fixup_policy = XZ_ASSET_FIXUP_REFERENCES;
        registry->specs[i].contributes_to_readiness = 1u;
    }
}

int XzAssetLoaderRegistry_Register(
    XzAssetLoaderRegistry *registry,
    XzT7AssetType type,
    XzAssetLoadPolicy load_policy,
    XzAssetFixupPolicy fixup_policy,
    int loader_registered,
    int fixup_registered,
    int contributes_to_readiness)
{
    unsigned int index = (unsigned int)type;
    XzAssetLoaderSpec *spec;

    if (!registry ||
        index >= XZ_T7_RUNTIME_TYPE_COUNT ||
        (unsigned int)load_policy > XZ_ASSET_LOAD_MEMMAPPED ||
        (unsigned int)fixup_policy > XZ_ASSET_FIXUP_UI)
        return 0;

    spec = &registry->specs[index];
    spec->type = type;
    spec->load_policy = load_policy;
    spec->fixup_policy = fixup_policy;
    spec->loader_registered = loader_registered ? 1u : 0u;
    spec->fixup_registered =
        (fixup_policy == XZ_ASSET_FIXUP_NONE)
            ? 1u
            : (fixup_registered ? 1u : 0u);
    spec->contributes_to_readiness =
        contributes_to_readiness ? 1u : 0u;

    return 1;
}

int XzAssetLoaderRegistry_Finalize(
    XzAssetLoaderRegistry *registry)
{
    unsigned int i;

    if (!registry)
        return 0;

    registry->registered_loaders = 0u;
    registry->registered_fixups = 0u;
    registry->missing_loaders = 0u;
    registry->missing_fixups = 0u;

    for (i = 0u; i < XZ_T7_RUNTIME_TYPE_COUNT; ++i) {
        const XzAssetLoaderSpec *spec = &registry->specs[i];

        if (!spec->contributes_to_readiness)
            continue;

        if (spec->loader_registered)
            registry->registered_loaders++;
        else
            registry->missing_loaders++;

        if (spec->fixup_registered)
            registry->registered_fixups++;
        else
            registry->missing_fixups++;
    }

    registry->ready =
        registry->missing_loaders == 0u &&
        registry->missing_fixups == 0u;

    return registry->ready;
}

int XzAssetLoaderRegistry_IsReady(
    const XzAssetLoaderRegistry *registry)
{
    return registry ? registry->ready : 0;
}

int XzAssetLoaderRegistry_SelfTest(void)
{
    XzAssetLoaderRegistry registry;
    unsigned int i;

    XzAssetLoaderRegistry_Init(&registry);

    if (XzAssetLoaderRegistry_Finalize(&registry))
        return 0;

    for (i = 0u; i < XZ_T7_RUNTIME_TYPE_COUNT; ++i) {
        if (!XzAssetLoaderRegistry_Register(
                &registry,
                (XzT7AssetType)i,
                XZ_ASSET_LOAD_RESIDENT,
                XZ_ASSET_FIXUP_NONE,
                1,
                1,
                1))
            return 0;
    }

    if (!XzAssetLoaderRegistry_Finalize(&registry))
        return 0;

    if (!XzAssetLoaderRegistry_Register(
            &registry,
            XZ_T7_SOUND,
            XZ_ASSET_LOAD_STREAM,
            XZ_ASSET_FIXUP_AUDIO,
            1,
            0,
            1))
        return 0;

    if (XzAssetLoaderRegistry_Finalize(&registry))
        return 0;

    return registry.missing_fixups == 1u;
}
