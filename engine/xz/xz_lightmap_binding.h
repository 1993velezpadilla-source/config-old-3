#ifndef XZ_LIGHTMAP_BINDING_H
#define XZ_LIGHTMAP_BINDING_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_XZLB_VERSION 1u
#define XZ_XZLB_HEADER_BYTES 32u
#define XZ_XZLB_RECORD_BYTES 256u
#define XZ_XZLB_NO_TEXTURE 0xffffffffu

enum {
    XZ_XZLB_FLAG_MAPPED = 1u << 0,
    XZ_XZLB_FLAG_RUNTIME_READY = 1u << 1,
    XZ_XZLB_FLAG_SHADOW_TEXTURE = 1u << 2,
    XZ_XZLB_FLAG_SKY_OCCLUSION = 1u << 3,
    XZ_XZLB_FLAG_AO_MASK = 1u << 4,
    XZ_XZLB_FLAG_SHADOW_PARAMS = 1u << 5,
    XZ_XZLB_FLAG_MESH_CONSENSUS = 1u << 6
};

enum {
    XZ_XZLB_RESOLUTION_NONE = 0u,
    XZ_XZLB_RESOLUTION_AUTHORED = 1u,
    XZ_XZLB_RESOLUTION_MESH_CONSENSUS = 2u
};

typedef enum {
    XZ_XZLB_OK = 0,
    XZ_XZLB_ERR_ARGUMENT,
    XZ_XZLB_ERR_OPEN,
    XZ_XZLB_ERR_READ,
    XZ_XZLB_ERR_MAGIC,
    XZ_XZLB_ERR_VERSION,
    XZ_XZLB_ERR_HEADER,
    XZ_XZLB_ERR_COUNT,
    XZ_XZLB_ERR_RECORD,
    XZ_XZLB_ERR_RANGE,
    XZ_XZLB_ERR_MEMORY
} XzLightmapBindingStatus;

typedef struct {
    uint32_t flags;
    uint32_t uv_channel;
    uint32_t light_texture[2];
    uint32_t shadow_texture;
    uint32_t sky_occlusion_texture;
    uint32_t ao_mask_texture;
    uint32_t component_export_index;
    float lightmap_coordinate_scale[2];
    float lightmap_coordinate_bias[2];
    float lightmap_scale_vectors[16];
    float lightmap_add_vectors[16];
    uint32_t light_shadow_channel_mask;
    uint32_t resolution_code;
    float light_inv_uniform_penumbra_size[4];
    float shadow_coordinate_scale[2];
    float shadow_coordinate_bias[2];
    uint32_t shadow_channel_mask;
    float shadow_inv_uniform_penumbra_size[4];
    unsigned char map_build_data_id[16];
} XzLightmapBindingRecord;

typedef struct {
    unsigned char *data;
    size_t bytes;
    uint32_t instance_count;
    uint32_t record_bytes;
    uint32_t mapped_count;
    uint32_t missing_count;
    uint32_t runtime_ready_count;
    uint32_t texture_count;
    uint32_t header_flags;
    uint32_t uv_channel_count[4];
} XzLightmapBindingView;

void XzLightmapBinding_Init(
    XzLightmapBindingView *view);

XzLightmapBindingStatus XzLightmapBinding_Open(
    XzLightmapBindingView *view,
    const char *path);

void XzLightmapBinding_Close(
    XzLightmapBindingView *view);

int XzLightmapBinding_Record(
    const XzLightmapBindingView *view,
    uint32_t instance_index,
    XzLightmapBindingRecord *record);

const char *XzLightmapBinding_StatusName(
    XzLightmapBindingStatus status);

#ifdef __cplusplus
}
#endif

#endif
