#include "xz_xztx_gpu_format.h"

#include <limits.h>
#include <stdlib.h>
#include <string.h>

static uint64_t XzCeilDivU32(
    uint32_t value,
    uint32_t divisor)
{
    return (
        (uint64_t)value +
        (uint64_t)divisor - 1u) /
        (uint64_t)divisor;
}

uint64_t XzXztxGpuFormat_ExpectedMipBytes(
    const XzXztxGpuFormat *format,
    uint32_t width,
    uint32_t height,
    uint32_t depth)
{
    uint64_t blocks_x;
    uint64_t blocks_y;
    uint64_t bytes;

    if (!format ||
        !format->compressed ||
        format->block_width == 0u ||
        format->block_height == 0u ||
        format->block_bytes == 0u ||
        width == 0u ||
        height == 0u ||
        depth == 0u)
        return 0u;

    blocks_x =
        XzCeilDivU32(
            width,
            format->block_width);
    blocks_y =
        XzCeilDivU32(
            height,
            format->block_height);

    if (blocks_x >
            UINT64_MAX / blocks_y)
        return 0u;

    bytes = blocks_x * blocks_y;

    if (bytes >
            UINT64_MAX /
                (uint64_t)format->block_bytes)
        return 0u;

    bytes *=
        (uint64_t)format->block_bytes;

    if (bytes >
            UINT64_MAX / (uint64_t)depth)
        return 0u;

    return bytes * (uint64_t)depth;
}

XzXztxGpuStatus XzXztxGpuFormat_Resolve(
    const XzXztextureView *texture,
    XzXztxGpuFormat *format)
{
    if (!texture || !format)
        return XZ_XZTX_GPU_ARGUMENT;

    memset(format, 0, sizeof(*format));

    if (texture->depth != 1u)
        return XZ_XZTX_GPU_BAD_DEPTH;

    if (strcmp(
            texture->format_name,
            "PF_ASTC_6x6") == 0) {
        format->compressed = 1u;
        format->block_width = 6u;
        format->block_height = 6u;
        format->block_bytes = 16u;
        format->srgb =
            (texture->flags &
             XZ_XZTX_FLAG_SRGB) != 0u;
        format->gl_internal_format =
            format->srgb
                ? XZ_GL_COMPRESSED_SRGB8_ALPHA8_ASTC_6X6_KHR
                : XZ_GL_COMPRESSED_RGBA_ASTC_6X6_KHR;
        return XZ_XZTX_GPU_OK;
    }

    return XZ_XZTX_GPU_UNSUPPORTED_FORMAT;
}

XzXztxGpuStatus XzXztxGpuFormat_ValidatePayload(
    const XzXztextureView *texture,
    const XzXztxGpuFormat *format,
    uint64_t *out_expected_payload_bytes)
{
    uint64_t total = 0u;
    uint32_t mip_index;

    if (out_expected_payload_bytes)
        *out_expected_payload_bytes = 0u;

    if (!texture ||
        !format ||
        !texture->data ||
        !format->compressed)
        return XZ_XZTX_GPU_ARGUMENT;

    for (mip_index = 0u;
         mip_index < texture->mip_count;
         ++mip_index) {
        XzXztextureMip mip;
        uint64_t expected;

        if (!XzXztexture_Mip(
                texture,
                mip_index,
                &mip))
            return XZ_XZTX_GPU_BAD_MIP;

        if (mip.depth != 1u)
            return XZ_XZTX_GPU_BAD_DEPTH;

        expected =
            XzXztxGpuFormat_ExpectedMipBytes(
                format,
                mip.width,
                mip.height,
                mip.depth);

        if (expected == 0u ||
            expected >
                (uint64_t)UINT32_MAX)
            return XZ_XZTX_GPU_BAD_MIP;

        if ((uint64_t)mip.payload_bytes !=
                expected)
            return XZ_XZTX_GPU_SIZE_MISMATCH;

        if (total >
            UINT64_MAX - expected)
            return XZ_XZTX_GPU_BAD_MIP;

        total += expected;
    }

    if (total !=
        (uint64_t)texture->payload_bytes)
        return XZ_XZTX_GPU_SIZE_MISMATCH;

    if (out_expected_payload_bytes)
        *out_expected_payload_bytes = total;

    return XZ_XZTX_GPU_OK;
}

const char *XzXztxGpuFormat_StatusName(
    XzXztxGpuStatus status)
{
    switch (status) {
    case XZ_XZTX_GPU_OK:
        return "OK";
    case XZ_XZTX_GPU_ARGUMENT:
        return "ARGUMENT";
    case XZ_XZTX_GPU_UNSUPPORTED_FORMAT:
        return "UNSUPPORTED_FORMAT";
    case XZ_XZTX_GPU_BAD_DEPTH:
        return "BAD_DEPTH";
    case XZ_XZTX_GPU_BAD_MIP:
        return "BAD_MIP";
    case XZ_XZTX_GPU_SIZE_MISMATCH:
        return "SIZE_MISMATCH";
    default:
        return "UNKNOWN";
    }
}

int XzXztxGpuFormat_SelfTest(void)
{
    XzXztextureView texture;
    XzXztxGpuFormat format;
    unsigned char data[
        XZ_XZTX_HEADER_BYTES +
        3u * XZ_XZTX_MIP_RECORD_BYTES +
        96u];
    uint64_t expected = 0u;

    memset(&texture, 0, sizeof(texture));
    snprintf(
        texture.format_name,
        sizeof(texture.format_name),
        "%s",
        "PF_ASTC_6x6");
    texture.depth = 1u;
    texture.flags = XZ_XZTX_FLAG_SRGB;

    if (XzXztxGpuFormat_Resolve(
            &texture,
            &format) != XZ_XZTX_GPU_OK ||
        !format.compressed ||
        !format.srgb ||
        format.gl_internal_format !=
            XZ_GL_COMPRESSED_SRGB8_ALPHA8_ASTC_6X6_KHR ||
        XzXztxGpuFormat_ExpectedMipBytes(
            &format,
            12u,
            12u,
            1u) != 64u ||
        XzXztxGpuFormat_ExpectedMipBytes(
            &format,
            7u,
            7u,
            1u) != 64u ||
        XzXztxGpuFormat_ExpectedMipBytes(
            &format,
            1u,
            1u,
            1u) != 16u)
        return 0;

    memset(data, 0, sizeof(data));
    /*
     * Build only the fields consumed by ValidatePayload. XZTX parsing itself
     * has an independent self-test and production callers resolve after parse.
     */
    texture.data = data;
    texture.size = sizeof(data);
    texture.width = 12u;
    texture.height = 12u;
    texture.depth = 1u;
    texture.mip_count = 3u;
    texture.mip_table_offset = XZ_XZTX_HEADER_BYTES;
    texture.payload_offset =
        XZ_XZTX_HEADER_BYTES +
        3u * XZ_XZTX_MIP_RECORD_BYTES;
    texture.payload_bytes = 96u;

#define WRITE32(at_, value_) \
    do { \
        uint32_t v_ = (uint32_t)(value_); \
        data[(at_) + 0u] = (unsigned char)(v_ & 0xffu); \
        data[(at_) + 1u] = (unsigned char)((v_ >> 8) & 0xffu); \
        data[(at_) + 2u] = (unsigned char)((v_ >> 16) & 0xffu); \
        data[(at_) + 3u] = (unsigned char)((v_ >> 24) & 0xffu); \
    } while (0)

    /* 12x12 => 2x2 blocks => 64 bytes. */
    WRITE32(80u + 0u, 12u);
    WRITE32(80u + 4u, 12u);
    WRITE32(80u + 8u, 1u);
    WRITE32(80u + 12u, texture.payload_offset);
    WRITE32(80u + 16u, 64u);
    WRITE32(80u + 20u, 0u);

    /* 6x6 => 1 block => 16 bytes. */
    WRITE32(104u + 0u, 6u);
    WRITE32(104u + 4u, 6u);
    WRITE32(104u + 8u, 1u);
    WRITE32(104u + 12u, texture.payload_offset + 64u);
    WRITE32(104u + 16u, 16u);
    WRITE32(104u + 20u, 1u);

    /* 3x3 => 1 block => 16 bytes. */
    WRITE32(128u + 0u, 3u);
    WRITE32(128u + 4u, 3u);
    WRITE32(128u + 8u, 1u);
    WRITE32(128u + 12u, texture.payload_offset + 80u);
    WRITE32(128u + 16u, 16u);
    WRITE32(128u + 20u, 2u);
#undef WRITE32

    if (XzXztxGpuFormat_ValidatePayload(
            &texture,
            &format,
            &expected) != XZ_XZTX_GPU_OK ||
        expected != 96u)
        return 0;

    /* Corrupt one mip length; must fail closed. */
    data[104u + 16u] = 15u;
    if (XzXztxGpuFormat_ValidatePayload(
            &texture,
            &format,
            NULL) !=
        XZ_XZTX_GPU_SIZE_MISMATCH)
        return 0;

    return 1;
}
