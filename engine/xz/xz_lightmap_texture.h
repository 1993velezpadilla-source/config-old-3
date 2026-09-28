#ifndef XZ_LIGHTMAP_TEXTURE_H
#define XZ_LIGHTMAP_TEXTURE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_XZLT_VERSION_V1 1u
#define XZ_XZLT_VERSION 2u
#define XZ_XZLT_HEADER_BYTES 32u
#define XZ_XZLT_TEXTURE_RECORD_BYTES 24u
#define XZ_XZLT_MIP_RECORD_BYTES 16u

enum {
    XZ_XZLT_FORMAT_BC1 = 1u,
    XZ_XZLT_FORMAT_BC3 = 2u,
    XZ_XZLT_FORMAT_ETC2_RGBA8 = 3u
};

typedef enum {
    XZ_XZLT_OK = 0,
    XZ_XZLT_ERR_ARGUMENT,
    XZ_XZLT_ERR_OPEN,
    XZ_XZLT_ERR_READ,
    XZ_XZLT_ERR_MAGIC,
    XZ_XZLT_ERR_VERSION,
    XZ_XZLT_ERR_HEADER,
    XZ_XZLT_ERR_COUNT,
    XZ_XZLT_ERR_TABLE,
    XZ_XZLT_ERR_TEXTURE,
    XZ_XZLT_ERR_MIP,
    XZ_XZLT_ERR_RANGE,
    XZ_XZLT_ERR_MEMORY
} XzLightmapTextureStatus;

typedef struct {
    uint32_t format;
    uint32_t width;
    uint32_t height;
    uint32_t first_mip;
    uint32_t mip_count;
    uint32_t srgb;
} XzLightmapTextureRecord;

typedef struct {
    uint32_t payload_offset;
    uint32_t bytes;
    uint32_t width;
    uint32_t height;
} XzLightmapMipRecord;

typedef struct {
    int file_handle;
    int file_open;
    uint32_t file_bytes;

    unsigned char *table_data;
    size_t table_bytes;

    uint32_t version;
    uint32_t texture_count;
    uint32_t mip_count;
    uint32_t texture_table_offset;
    uint32_t mip_table_offset;
    uint32_t payload_offset;
    uint32_t payload_bytes;

    uint32_t bc1_texture_count;
    uint32_t bc3_texture_count;
    uint32_t etc2_rgba8_texture_count;
    uint32_t srgb_texture_count;
    uint32_t linear_texture_count;
} XzLightmapTextureView;

void XzLightmapTexture_Init(
    XzLightmapTextureView *view);

XzLightmapTextureStatus XzLightmapTexture_Open(
    XzLightmapTextureView *view,
    const char *path);

void XzLightmapTexture_Close(
    XzLightmapTextureView *view);

int XzLightmapTexture_Texture(
    const XzLightmapTextureView *view,
    uint32_t texture_index,
    XzLightmapTextureRecord *record);

int XzLightmapTexture_Mip(
    const XzLightmapTextureView *view,
    uint32_t mip_index,
    XzLightmapMipRecord *record);

XzLightmapTextureStatus XzLightmapTexture_ReadMip(
    XzLightmapTextureView *view,
    uint32_t texture_index,
    uint32_t relative_mip,
    void *destination,
    size_t destination_bytes,
    XzLightmapMipRecord *record);

const char *XzLightmapTexture_StatusName(
    XzLightmapTextureStatus status);

#ifdef __cplusplus
}
#endif

#endif
