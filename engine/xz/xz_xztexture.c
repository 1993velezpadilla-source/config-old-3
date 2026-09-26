#include "xz_xztexture.h"

#include <string.h>

static uint32_t XzTextureReadU32Le(
    const unsigned char *p)
{
    return ((uint32_t)p[0]) |
           ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

static void XzTextureWriteU32Le(
    unsigned char *p,
    uint32_t value)
{
    p[0] = (unsigned char)(value & 0xffu);
    p[1] = (unsigned char)((value >> 8) & 0xffu);
    p[2] = (unsigned char)((value >> 16) & 0xffu);
    p[3] = (unsigned char)((value >> 24) & 0xffu);
}

XzXztextureStatus XzXztexture_Parse(
    XzXztextureView *view,
    const void *data,
    size_t size)
{
    const unsigned char *bytes =
        (const unsigned char *)data;
    uint64_t expected_pixels;
    uint64_t expected_size;
    uint32_t version;

    if (!view || !data)
        return XZ_XZTX_ERR_ARGUMENT;

    memset(view, 0, sizeof(*view));

    if (size < XZ_XZTX_HEADER_BYTES)
        return XZ_XZTX_ERR_TRUNCATED;

    if (bytes[0] != 'X' ||
        bytes[1] != 'Z' ||
        bytes[2] != 'T' ||
        bytes[3] != 'X')
        return XZ_XZTX_ERR_MAGIC;

    version =
        XzTextureReadU32Le(bytes + 4u);
    if (version != XZ_XZTX_VERSION)
        return XZ_XZTX_ERR_VERSION;

    view->width =
        XzTextureReadU32Le(bytes + 8u);
    view->height =
        XzTextureReadU32Le(bytes + 12u);
    view->format =
        XzTextureReadU32Le(bytes + 16u);
    view->pixel_bytes =
        XzTextureReadU32Le(bytes + 20u);

    if (view->width == 0u ||
        view->height == 0u ||
        view->width > 16384u ||
        view->height > 16384u)
        goto dimensions_fail;

    if (view->format !=
            XZ_XZTX_FORMAT_RGBA8)
        goto format_fail;

    expected_pixels =
        (uint64_t)view->width *
        (uint64_t)view->height *
        4u;

    if (expected_pixels >
        (uint64_t)UINT32_MAX)
        goto overflow_fail;

    if ((uint64_t)view->pixel_bytes !=
        expected_pixels)
        goto size_fail;

    expected_size =
        (uint64_t)XZ_XZTX_HEADER_BYTES +
        expected_pixels;

    if (expected_size >
        (uint64_t)SIZE_MAX)
        goto overflow_fail;

    if ((uint64_t)size != expected_size) {
        memset(view, 0, sizeof(*view));
        return (uint64_t)size < expected_size
            ? XZ_XZTX_ERR_TRUNCATED
            : XZ_XZTX_ERR_SIZE_MISMATCH;
    }

    view->data = bytes;
    view->size = size;
    view->pixel_offset =
        XZ_XZTX_HEADER_BYTES;
    view->pixels =
        bytes + view->pixel_offset;

    return XZ_XZTX_OK;

dimensions_fail:
    memset(view, 0, sizeof(*view));
    return XZ_XZTX_ERR_DIMENSIONS;

format_fail:
    memset(view, 0, sizeof(*view));
    return XZ_XZTX_ERR_FORMAT;

overflow_fail:
    memset(view, 0, sizeof(*view));
    return XZ_XZTX_ERR_SIZE_OVERFLOW;

size_fail:
    memset(view, 0, sizeof(*view));
    return XZ_XZTX_ERR_SIZE_MISMATCH;
}

const char *XzXztexture_StatusName(
    XzXztextureStatus status)
{
    switch (status) {
    case XZ_XZTX_OK: return "OK";
    case XZ_XZTX_ERR_ARGUMENT: return "ARGUMENT";
    case XZ_XZTX_ERR_TRUNCATED: return "TRUNCATED";
    case XZ_XZTX_ERR_MAGIC: return "MAGIC";
    case XZ_XZTX_ERR_VERSION: return "VERSION";
    case XZ_XZTX_ERR_DIMENSIONS: return "DIMENSIONS";
    case XZ_XZTX_ERR_FORMAT: return "FORMAT";
    case XZ_XZTX_ERR_SIZE_OVERFLOW: return "SIZE_OVERFLOW";
    case XZ_XZTX_ERR_SIZE_MISMATCH: return "SIZE_MISMATCH";
    default: return "UNKNOWN";
    }
}

int XzXztexture_SelfTest(void)
{
    unsigned char data[
        XZ_XZTX_HEADER_BYTES + 8u * 4u];
    XzXztextureView view;

    memset(data, 0, sizeof(data));
    data[0] = 'X';
    data[1] = 'Z';
    data[2] = 'T';
    data[3] = 'X';
    XzTextureWriteU32Le(
        data + 4u,
        XZ_XZTX_VERSION);
    XzTextureWriteU32Le(
        data + 8u, 4u);
    XzTextureWriteU32Le(
        data + 12u, 2u);
    XzTextureWriteU32Le(
        data + 16u,
        XZ_XZTX_FORMAT_RGBA8);
    XzTextureWriteU32Le(
        data + 20u, 32u);

    if (XzXztexture_Parse(
            &view,
            data,
            sizeof(data)) != XZ_XZTX_OK)
        return 0;

    if (view.width != 4u ||
        view.height != 2u ||
        view.pixel_bytes != 32u ||
        view.pixels !=
            data + XZ_XZTX_HEADER_BYTES)
        return 0;

    data[0] = 'B';
    if (XzXztexture_Parse(
            &view,
            data,
            sizeof(data)) != XZ_XZTX_ERR_MAGIC)
        return 0;
    data[0] = 'X';

    XzTextureWriteU32Le(
        data + 20u, 31u);
    if (XzXztexture_Parse(
            &view,
            data,
            sizeof(data)) !=
            XZ_XZTX_ERR_SIZE_MISMATCH)
        return 0;

    return 1;
}
