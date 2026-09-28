#ifndef XZ_SOURCE_ADAPTER_REGISTRY_H
#define XZ_SOURCE_ADAPTER_REGISTRY_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum XzSourceAssetKind {
    XZ_SOURCE_WORLD_GEOMETRY = 0,
    XZ_SOURCE_MATERIAL_TEXTURE_SHADER,
    XZ_SOURCE_LIGHTING_ENVIRONMENT,
    XZ_SOURCE_COLLISION_PHYSICS,
    XZ_SOURCE_NAVIGATION,
    XZ_SOURCE_ANIMATION_RIG,
    XZ_SOURCE_AUDIO,
    XZ_SOURCE_FX_PARTICLES,
    XZ_SOURCE_HUD_UI,
    XZ_SOURCE_CINEMATIC_MEDIA_CAMERA,
    XZ_SOURCE_INPUT_HAPTICS,
    XZ_SOURCE_SPAWN_GAMEPLAY,
    XZ_SOURCE_SCRIPT_GAMEPLAY,
    XZ_SOURCE_DATA_CURVES,
    XZ_SOURCE_KIND_COUNT
} XzSourceAssetKind;

typedef struct XzSourceAdapterSpec {
    uint64_t required_exports;
    uint64_t converted_exports;
    uint64_t verified_exports;
    uint8_t parser_registered;
    uint8_t converter_registered;
    uint8_t native_validator_registered;
    uint8_t failed;
} XzSourceAdapterSpec;

typedef struct XzSourceAdapterRegistry {
    XzSourceAdapterSpec kinds[XZ_SOURCE_KIND_COUNT];
    uint32_t required_kind_mask;
    uint32_t supported_kind_mask;
    uint32_t failed_kind_mask;
    uint64_t required_exports;
    uint64_t converted_exports;
    uint64_t verified_exports;
    uint32_t generation;
    int finalized;
    int ready;
} XzSourceAdapterRegistry;

void XzSourceAdapterRegistry_Init(
    XzSourceAdapterRegistry *registry);

void XzSourceAdapterRegistry_NewGeneration(
    XzSourceAdapterRegistry *registry);

int XzSourceAdapterRegistry_Require(
    XzSourceAdapterRegistry *registry,
    XzSourceAssetKind kind,
    uint64_t export_count);

int XzSourceAdapterRegistry_RegisterSupport(
    XzSourceAdapterRegistry *registry,
    XzSourceAssetKind kind,
    int parser_registered,
    int converter_registered,
    int native_validator_registered);

int XzSourceAdapterRegistry_SetProgress(
    XzSourceAdapterRegistry *registry,
    XzSourceAssetKind kind,
    uint64_t converted_exports,
    uint64_t verified_exports);

int XzSourceAdapterRegistry_SetFailed(
    XzSourceAdapterRegistry *registry,
    XzSourceAssetKind kind,
    int failed);

int XzSourceAdapterRegistry_Finalize(
    XzSourceAdapterRegistry *registry);

int XzSourceAdapterRegistry_IsReady(
    const XzSourceAdapterRegistry *registry);

const char *XzSourceAdapterRegistry_KindName(
    XzSourceAssetKind kind);

int XzSourceAdapterRegistry_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif
