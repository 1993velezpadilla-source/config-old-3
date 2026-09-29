#include "xz_xztexture.h"

#include <limits.h>
#include <stdlib.h>
#include <string.h>

#define XZ_XZTX_KNOWN_FLAGS XZ_XZTX_FLAG_SRGB

static uint32_t XzReadU32Le(
    const unsigned char *p)
{
    return ((uint32_t)p[0]) |
           ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

static void XzWriteU32Le(
    unsigned char *p,
    uint32_t value)
{
    p[0] = (unsigned char)(value & 0xffu);
    p[1] = (unsigned char)((value >> 8) & 0xffu);
    p[2] = (unsigned char)((value >> 16) & 0xffu);
    p[3] = (unsigned char)((value >> 24) & 0xffu);
}

static int XzFormatNameValid(
    const unsigned char *bytes,
    uint32_t length)
{
    uint32_t i;

    if (!bytes ||
        length == 0u ||
        length >= XZ_XZTX_FORMAT_NAME_BYTES)
        return 0;

    for (i = 0u; i < length; ++i) {
        if (bytes[i] < 0x21u ||
            bytes[i] > 0x7eu)
            return 0;
    }

    if (bytes[length] != 0u)
        return 0;

    for (i = length + 1u;
         i < XZ_XZTX_FORMAT_NAME_BYTES;
         ++i) {
        if (bytes[i] != 0u)
            return 0;
    }

    return 1;
}

int XzXztexture_Mip(
    const XzXztextureView *view,
    uint32_t mip_index,
    XzXztextureMip *mip)
{
    const unsigned char *p;
    uint64_t record_offset;

    if (!view ||
        !view->data ||
        !mip ||
        mip_index >= view->mip_count)
        return 0;

    record_offset =
        (uint64_t)view->mip_table_offset +
        (uint64_t)mip_index *
            XZ_XZTX_MIP_RECORD_BYTES;

    if (record_offset >
            (uint64_t)SIZE_MAX ||
        record_offset +
            XZ_XZTX_MIP_RECORD_BYTES >
            (uint64_t)view->size)
        return 0;

    p = view->data + (size_t)record_offset;

    mip->width = XzReadU32Le(p + 0u);
    mip->height = XzReadU32Le(p + 4u);
    mip->depth = XzReadU32Le(p + 8u);
    mip->payload_offset = XzReadU32Le(p + 12u);
    mip->payload_bytes = XzReadU32Le(p + 16u);
    mip->source_mip_index = XzReadU32Le(p + 20u);
    return 1;
}

const void *XzXztexture_MipData(
    const XzXztextureView *view,
    uint32_t mip_index,
    size_t *out_bytes)
{
    XzXztextureMip mip;
    uint64_t end;

    if (out_bytes)
        *out_bytes = 0u;

    if (!XzXztexture_Mip(
            view,
            mip_index,
            &mip))
        return NULL;

    end =
        (uint64_t)mip.payload_offset +
        (uint64_t)mip.payload_bytes;

    if (end > (uint64_t)view->size)
        return NULL;

    if (out_bytes)
        *out_bytes = (size_t)mip.payload_bytes;

    return view->data + mip.payload_offset;
}

XzXztextureStatus XzXztexture_Parse(
    XzXztextureView *view,
    const void *data,
    size_t size)
{
    const unsigned char *bytes =
        (const unsigned char *)data;
    const unsigned char *format;
    uint32_t i;
    uint64_t expected_payload_offset;
    uint64_t expected_end;
    uint32_t next_payload_offset;
    uint32_t previous_width = 0u;
    uint32_t previous_height = 0u;
    uint32_t previous_depth = 0u;

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

    view->version = XzReadU32Le(bytes + 4u);
    view->width = XzReadU32Le(bytes + 8u);
    view->height = XzReadU32Le(bytes + 12u);
    view->depth = XzReadU32Le(bytes + 16u);
    view->mip_count = XzReadU32Le(bytes + 20u);
    view->flags = XzReadU32Le(bytes + 24u);
    view->format_name_bytes = XzReadU32Le(bytes + 28u);
    view->mip_record_bytes = XzReadU32Le(bytes + 32u);
    view->mip_table_offset = XzReadU32Le(bytes + 36u);
    view->payload_offset = XzReadU32Le(bytes + 40u);
    view->payload_bytes = XzReadU32Le(bytes + 44u);

    if (view->version != XZ_XZTX_VERSION)
        return XZ_XZTX_ERR_VERSION;

    if ((view->flags & ~XZ_XZTX_KNOWN_FLAGS) != 0u)
        return XZ_XZTX_ERR_FLAGS;

    if (view->width == 0u ||
        view->height == 0u ||
        view->depth == 0u ||
        view->mip_count == 0u)
        return XZ_XZTX_ERR_COUNT;

    if (view->mip_record_bytes !=
            XZ_XZTX_MIP_RECORD_BYTES ||
        view->mip_table_offset !=
            XZ_XZTX_HEADER_BYTES)
        return XZ_XZTX_ERR_HEADER;

    format = bytes + 48u;
    if (!XzFormatNameValid(
            format,
            view->format_name_bytes))
        return XZ_XZTX_ERR_FORMAT;

    memcpy(
        view->format_name,
        format,
        XZ_XZTX_FORMAT_NAME_BYTES);

    expected_payload_offset =
        (uint64_t)view->mip_table_offset +
        (uint64_t)view->mip_count *
            XZ_XZTX_MIP_RECORD_BYTES;

    if (expected_payload_offset > UINT32_MAX ||
        view->payload_offset !=
            (uint32_t)expected_payload_offset)
        return XZ_XZTX_ERR_TABLE;

    if ((uint64_t)view->payload_offset >
        (uint64_t)size)
        return XZ_XZTX_ERR_TRUNCATED;

    expected_end =
        (uint64_t)view->payload_offset +
        (uint64_t)view->payload_bytes;

    if (expected_end != (uint64_t)size)
        return expected_end > (uint64_t)size
            ? XZ_XZTX_ERR_TRUNCATED
            : XZ_XZTX_ERR_SIZE_MISMATCH;

    next_payload_offset =
        view->payload_offset;

    for (i = 0u; i < view->mip_count; ++i) {
        XzXztextureMip mip;
        uint64_t end;

        if (!XzXztexture_Mip(
                view,
                i,
                &mip))
            return XZ_XZTX_ERR_MIP;

        if (mip.width == 0u ||
            mip.height == 0u ||
            mip.depth == 0u ||
            mip.payload_bytes == 0u ||
            mip.source_mip_index != i)
            return XZ_XZTX_ERR_MIP;

        if (i == 0u) {
            if (mip.width != view->width ||
                mip.height != view->height ||
                mip.depth != view->depth)
                return XZ_XZTX_ERR_MIP;
        } else {
            if (mip.width > previous_width ||
                mip.height > previous_height ||
                mip.depth > previous_depth)
                return XZ_XZTX_ERR_MIP;
        }

        if (mip.payload_offset !=
            next_payload_offset)
            return XZ_XZTX_ERR_RANGE;

        end =
            (uint64_t)mip.payload_offset +
            (uint64_t)mip.payload_bytes;

        if (end > (uint64_t)size ||
            end > UINT32_MAX)
            return XZ_XZTX_ERR_RANGE;

        next_payload_offset = (uint32_t)end;
        previous_width = mip.width;
        previous_height = mip.height;
        previous_depth = mip.depth;
    }

    if (next_payload_offset != size)
        return XZ_XZTX_ERR_SIZE_MISMATCH;

    return XZ_XZTX_OK;
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
    case XZ_XZTX_ERR_FLAGS: return "FLAGS";
    case XZ_XZTX_ERR_HEADER: return "HEADER";
    case XZ_XZTX_ERR_FORMAT: return "FORMAT";
    case XZ_XZTX_ERR_COUNT: return "COUNT";
    case XZ_XZTX_ERR_TABLE: return "TABLE";
    case XZ_XZTX_ERR_MIP: return "MIP";
    case XZ_XZTX_ERR_RANGE: return "RANGE";
    case XZ_XZTX_ERR_SIZE_MISMATCH:
        return "SIZE_MISMATCH";
    default: return "UNKNOWN";
    }
}

int XzXztexture_SelfTest(void)
{
    unsigned char data[
        XZ_XZTX_HEADER_BYTES +
        2u * XZ_XZTX_MIP_RECORD_BYTES +
        20u];
    XzXztextureView view;
    XzXztextureMip mip;
    size_t payload_bytes = 0u;
    const unsigned char *payload;
    size_t payload_offset =
        XZ_XZTX_HEADER_BYTES +
        2u * XZ_XZTX_MIP_RECORD_BYTES;

    memset(data, 0, sizeof(data));

    data[0] = 'X';
    data[1] = 'Z';
    data[2] = 'T';
    data[3] = 'X';

    XzWriteU32Le(data + 4u, XZ_XZTX_VERSION);
    XzWriteU32Le(data + 8u, 4u);
    XzWriteU32Le(data + 12u, 4u);
    XzWriteU32Le(data + 16u, 1u);
    XzWriteU32Le(data + 20u, 2u);
    XzWriteU32Le(data + 24u, XZ_XZTX_FLAG_SRGB);
    XzWriteU32Le(data + 28u, 7u);
    XzWriteU32Le(
        data + 32u,
        XZ_XZTX_MIP_RECORD_BYTES);
    XzWriteU32Le(
        data + 36u,
        XZ_XZTX_HEADER_BYTES);
    XzWriteU32Le(
        data + 40u,
        (uint32_t)payload_offset);
    XzWriteU32Le(data + 44u, 20u);
    memcpy(data + 48u, "PF_DXT1", 7u);

    /* mip 0: 4x4, 16 bytes */
    XzWriteU32Le(data + 80u + 0u, 4u);
    XzWriteU32Le(data + 80u + 4u, 4u);
    XzWriteU32Le(data + 80u + 8u, 1u);
    XzWriteU32Le(
        data + 80u + 12u,
        (uint32_t)payload_offset);
    XzWriteU32Le(data + 80u + 16u, 16u);
    XzWriteU32Le(data + 80u + 20u, 0u);

    /* mip 1: 2x2, 4 bytes */
    XzWriteU32Le(data + 104u + 0u, 2u);
    XzWriteU32Le(data + 104u + 4u, 2u);
    XzWriteU32Le(data + 104u + 8u, 1u);
    XzWriteU32Le(
        data + 104u + 12u,
        (uint32_t)payload_offset + 16u);
    XzWriteU32Le(data + 104u + 16u, 4u);
    XzWriteU32Le(data + 104u + 20u, 1u);

    memset(data + payload_offset, 0x5a, 20u);

    if (XzXztexture_Parse(
            &view,
            data,
            sizeof(data)) != XZ_XZTX_OK)
        return 0;

    if (strcmp(view.format_name, "PF_DXT1") != 0 ||
        view.mip_count != 2u ||
        (view.flags & XZ_XZTX_FLAG_SRGB) == 0u)
        return 0;

    if (!XzXztexture_Mip(
            &view,
            1u,
            &mip) ||
        mip.width != 2u ||
        mip.height != 2u ||
        mip.payload_bytes != 4u)
        return 0;

    payload =
        (const unsigned char *)XzXztexture_MipData(
            &view,
            1u,
            &payload_bytes);

    if (!payload ||
        payload_bytes != 4u ||
        payload[0] != 0x5au)
        return 0;

    /* Unknown flag must fail closed. */
    XzWriteU32Le(
        data + 24u,
        XZ_XZTX_FLAG_SRGB | (1u << 7));
    if (XzXztexture_Parse(
            &view,
            data,
            sizeof(data)) !=
        XZ_XZTX_ERR_FLAGS)
        return 0;

    return 1;
}
