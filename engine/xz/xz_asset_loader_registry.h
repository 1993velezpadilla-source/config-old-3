#ifndef XZ_ASSET_LOADER_REGISTRY_H
#define XZ_ASSET_LOADER_REGISTRY_H

#include <stdint.h>
#include "xz_t7_asset_types.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum XzAssetLoadPolicy {
    XZ_ASSET_LOAD_BOOT = 0,
    XZ_ASSET_LOAD_RESIDENT = 1,
    XZ_ASSET_LOAD_STREAM = 2,
    XZ_ASSET_LOAD_DELAY = 3,
    XZ_ASSET_LOAD_MEMMAPPED = 4
} XzAssetLoadPolicy;

typedef enum XzAssetFixupPolicy {
    XZ_ASSET_FIXUP_NONE = 0,
    XZ_ASSET_FIXUP_REFERENCES = 1,
    XZ_ASSET_FIXUP_GPU = 2,
    XZ_ASSET_FIXUP_AUDIO = 3,
    XZ_ASSET_FIXUP_SCRIPT = 4,
    XZ_ASSET_FIXUP_PHYSICS = 5,
    XZ_ASSET_FIXUP_NAV = 6,
    XZ_ASSET_FIXUP_ANIMATION = 7,
    XZ_ASSET_FIXUP_UI = 8
} XzAssetFixupPolicy;

typedef struct XzAssetLoaderSpec {
    XzT7AssetType type;
    XzAssetLoadPolicy load_policy;
    XzAssetFixupPolicy fixup_policy;
    uint8_t loader_registered;
    uint8_t fixup_registered;
    uint8_t contributes_to_readiness;
} XzAssetLoaderSpec;

typedef struct XzAssetLoaderRegistry {
    XzAssetLoaderSpec specs[XZ_T7_RUNTIME_TYPE_COUNT];
    uint32_t registered_loaders;
    uint32_t registered_fixups;
    uint32_t missing_loaders;
    uint32_t missing_fixups;
    int ready;
} XzAssetLoaderRegistry;

void XzAssetLoaderRegistry_Init(
    XzAssetLoaderRegistry *registry);

int XzAssetLoaderRegistry_Register(
    XzAssetLoaderRegistry *registry,
    XzT7AssetType type,
    XzAssetLoadPolicy load_policy,
    XzAssetFixupPolicy fixup_policy,
    int loader_registered,
    int fixup_registered,
    int contributes_to_readiness);

int XzAssetLoaderRegistry_Finalize(
    XzAssetLoaderRegistry *registry);

int XzAssetLoaderRegistry_IsReady(
    const XzAssetLoaderRegistry *registry);

int XzAssetLoaderRegistry_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif
