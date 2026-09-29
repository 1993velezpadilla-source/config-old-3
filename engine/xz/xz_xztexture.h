#ifndef XZ_XZTEXTURE_H
#define XZ_XZTEXTURE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_XZTX_VERSION 1u
#define XZ_XZTX_HEADER_BYTES 80u
#define XZ_XZTX_MIP_RECORD_BYTES 24u
#define XZ_XZTX_FORMAT_NAME_BYTES 32u

enum {
    XZ_XZTX_FLAG_SRGB = 1u << 0
};

typedef enum XzXztextureStatus {
    XZ_XZTX_OK = 0,
    XZ_XZTX_ERR_ARGUMENT,
    XZ_XZTX_ERR_TRUNCATED,
    XZ_XZTX_ERR_MAGIC,
    XZ_XZTX_ERR_VERSION,
    XZ_XZTX_ERR_FLAGS,
    XZ_XZTX_ERR_HEADER,
    XZ_XZTX_ERR_FORMAT,
    XZ_XZTX_ERR_COUNT,
    XZ_XZTX_ERR_TABLE,
    XZ_XZTX_ERR_MIP,
    XZ_XZTX_ERR_RANGE,
    XZ_XZTX_ERR_SIZE_MISMATCH
} XzXztextureStatus;

typedef struct XzXztextureMip {
    uint32_t width;
    uint32_t height;
    uint32_t depth;
    uint32_t payload_offset;
    uint32_t payload_bytes;
    uint32_t source_mip_index;
} XzXztextureMip;

typedef struct XzXztextureView {
    const unsigned char *data;
    size_t size;

    uint32_t version;
    uint32_t width;
    uint32_t height;
    uint32_t depth;
    uint32_t mip_count;
    uint32_t flags;
    uint32_t format_name_bytes;
    uint32_t mip_record_bytes;
    uint32_t mip_table_offset;
    uint32_t payload_offset;
    uint32_t payload_bytes;

    char format_name[XZ_XZTX_FORMAT_NAME_BYTES];
} XzXztextureView;

XzXztextureStatus XzXztexture_Parse(
    XzXztextureView *view,
    const void *data,
    size_t size);

int XzXztexture_Mip(
    const XzXztextureView *view,
    uint32_t mip_index,
    XzXztextureMip *mip);

const void *XzXztexture_MipData(
    const XzXztextureView *view,
    uint32_t mip_index,
    size_t *out_bytes);

const char *XzXztexture_StatusName(
    XzXztextureStatus status);

int XzXztexture_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif
