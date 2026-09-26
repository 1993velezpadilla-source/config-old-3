#ifndef XZ_XZTEXTURE_H
#define XZ_XZTEXTURE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_XZTX_VERSION 1u
#define XZ_XZTX_HEADER_BYTES 24u
#define XZ_XZTX_FORMAT_RGBA8 1u

typedef enum {
    XZ_XZTX_OK = 0,
    XZ_XZTX_ERR_ARGUMENT,
    XZ_XZTX_ERR_TRUNCATED,
    XZ_XZTX_ERR_MAGIC,
    XZ_XZTX_ERR_VERSION,
    XZ_XZTX_ERR_DIMENSIONS,
    XZ_XZTX_ERR_FORMAT,
    XZ_XZTX_ERR_SIZE_OVERFLOW,
    XZ_XZTX_ERR_SIZE_MISMATCH
} XzXztextureStatus;

typedef struct {
    const unsigned char *data;
    size_t size;

    uint32_t width;
    uint32_t height;
    uint32_t format;
    uint32_t pixel_bytes;

    size_t pixel_offset;
    const unsigned char *pixels;
} XzXztextureView;

XzXztextureStatus XzXztexture_Parse(
    XzXztextureView *view,
    const void *data,
    size_t size);

const char *XzXztexture_StatusName(
    XzXztextureStatus status);

int XzXztexture_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif
