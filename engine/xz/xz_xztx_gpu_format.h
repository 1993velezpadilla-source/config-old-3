#ifndef XZ_XZTX_GPU_FORMAT_H
#define XZ_XZTX_GPU_FORMAT_H

#include "xz_xztexture.h"

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_GL_COMPRESSED_RGBA_ASTC_6X6_KHR 0x93B4u
#define XZ_GL_COMPRESSED_SRGB8_ALPHA8_ASTC_6X6_KHR 0x93D4u

typedef enum {
    XZ_XZTX_GPU_OK = 0,
    XZ_XZTX_GPU_ARGUMENT,
    XZ_XZTX_GPU_UNSUPPORTED_FORMAT,
    XZ_XZTX_GPU_BAD_DEPTH,
    XZ_XZTX_GPU_BAD_MIP,
    XZ_XZTX_GPU_SIZE_MISMATCH
} XzXztxGpuStatus;

typedef struct {
    uint32_t gl_internal_format;
    uint32_t block_width;
    uint32_t block_height;
    uint32_t block_bytes;
    uint32_t compressed;
    uint32_t srgb;
} XzXztxGpuFormat;

XzXztxGpuStatus XzXztxGpuFormat_Resolve(
    const XzXztextureView *texture,
    XzXztxGpuFormat *format);

XzXztxGpuStatus XzXztxGpuFormat_ValidatePayload(
    const XzXztextureView *texture,
    const XzXztxGpuFormat *format,
    uint64_t *out_expected_payload_bytes);

uint64_t XzXztxGpuFormat_ExpectedMipBytes(
    const XzXztxGpuFormat *format,
    uint32_t width,
    uint32_t height,
    uint32_t depth);

const char *XzXztxGpuFormat_StatusName(
    XzXztxGpuStatus status);

int XzXztxGpuFormat_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif
