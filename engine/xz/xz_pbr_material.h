#ifndef XZ_PBR_MATERIAL_H
#define XZ_PBR_MATERIAL_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_PBR_MATERIAL_VERSION 2u
#define XZ_PBR_MATERIAL_LEGACY_VERSION 1u
#define XZ_PBR_MATERIAL_HEADER_BYTES 20u
#define XZ_PBR_MATERIAL_RECORD_BYTES_V1 20u
#define XZ_PBR_MATERIAL_RECORD_BYTES 32u

enum {
    XZ_PBR_FLAG_ROUGHNESS = 1u << 0,
    XZ_PBR_FLAG_METALLIC = 1u << 1,
    XZ_PBR_FLAG_SPECULAR = 1u << 2,
    XZ_PBR_FLAG_EMISSIVE = 1u << 3
};

enum {
    XZ_PBR_BLEND_OPAQUE = 0u,
    XZ_PBR_BLEND_MASKED = 1u,
    XZ_PBR_BLEND_TRANSLUCENT = 2u,
    XZ_PBR_BLEND_ADDITIVE = 3u
};

enum {
    XZ_PBR_MATERIAL_FLAG_TWO_SIDED = 1u << 0,
    XZ_PBR_MATERIAL_FLAG_DISABLE_DEPTH_TEST = 1u << 1,
    XZ_PBR_MATERIAL_FLAG_ALPHA_TEST_ENABLED = 1u << 2
};

typedef enum {
    XZ_PBR_MATERIAL_OK = 0,
    XZ_PBR_MATERIAL_NULL,
    XZ_PBR_MATERIAL_BAD_SIZE,
    XZ_PBR_MATERIAL_BAD_MAGIC,
    XZ_PBR_MATERIAL_BAD_VERSION,
    XZ_PBR_MATERIAL_BAD_HEADER,
    XZ_PBR_MATERIAL_BAD_FLAGS,
    XZ_PBR_MATERIAL_BAD_VALUE,
    XZ_PBR_MATERIAL_BAD_INDEX
} XzPbrMaterialStatus;

typedef struct {
    const unsigned char *data;
    size_t bytes;
    uint32_t binding_count;
    uint32_t record_bytes;
} XzPbrMaterialView;

typedef struct {
    uint32_t flags;
    float roughness;
    float metallic;
    float specular;
    float emissive;
    uint32_t blend_mode;
    uint32_t material_flags;
    float opacity_mask_clip;
} XzPbrMaterialBinding;

XzPbrMaterialStatus XzPbrMaterial_Parse(
    XzPbrMaterialView *view,
    const unsigned char *data,
    size_t bytes);

XzPbrMaterialStatus XzPbrMaterial_ReadBinding(
    const XzPbrMaterialView *view,
    uint32_t binding_index,
    XzPbrMaterialBinding *binding);

const char *XzPbrMaterial_StatusName(
    XzPbrMaterialStatus status);

#ifdef __cplusplus
}
#endif

#endif
