#ifndef XZ_PBR_MATERIAL_H
#define XZ_PBR_MATERIAL_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_PBR_MATERIAL_VERSION 1u
#define XZ_PBR_MATERIAL_HEADER_BYTES 20u
#define XZ_PBR_MATERIAL_RECORD_BYTES 20u

enum {
    XZ_PBR_FLAG_ROUGHNESS = 1u << 0,
    XZ_PBR_FLAG_METALLIC = 1u << 1,
    XZ_PBR_FLAG_SPECULAR = 1u << 2,
    XZ_PBR_FLAG_EMISSIVE = 1u << 3
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
