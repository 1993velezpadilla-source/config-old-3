#include "xz_xzaudio.h"

#include <string.h>

#define XZ_XZAW_KNOWN_FLAGS XZ_XZAW_FLAG_SOURCE_STREAMING

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
        length >= XZ_XZAW_FORMAT_NAME_BYTES)
        return 0;

    for (i = 0u; i < length; ++i) {
        if (bytes[i] < 0x21u ||
            bytes[i] > 0x7eu)
            return 0;
    }

    if (bytes[length] != 0u)
        return 0;

    for (i = length + 1u;
         i < XZ_XZAW_FORMAT_NAME_BYTES;
         ++i) {
        if (bytes[i] != 0u)
            return 0;
    }

    return 1;
}

XzXzaudioStatus XzXzaudio_Parse(
    XzXzaudioView *view,
    const void *data,
    size_t size)
{
    const unsigned char *bytes =
        (const unsigned char *)data;
    const unsigned char *format;
    uint64_t end;

    if (!view || !data)
        return XZ_XZAW_ERR_ARGUMENT;

    memset(view, 0, sizeof(*view));

    if (size < XZ_XZAW_HEADER_BYTES)
        return XZ_XZAW_ERR_TRUNCATED;

    if (bytes[0] != 'X' ||
        bytes[1] != 'Z' ||
        bytes[2] != 'A' ||
        bytes[3] != 'W')
        return XZ_XZAW_ERR_MAGIC;

    view->data = bytes;
    view->size = size;
    view->version = XzReadU32Le(bytes + 4u);
    view->flags = XzReadU32Le(bytes + 8u);
    view->format_name_bytes = XzReadU32Le(bytes + 12u);
    view->header_bytes = XzReadU32Le(bytes + 16u);
    view->payload_offset = XzReadU32Le(bytes + 20u);
    view->payload_bytes = XzReadU32Le(bytes + 24u);

    if (view->version != XZ_XZAW_VERSION)
        return XZ_XZAW_ERR_VERSION;

    if ((view->flags & ~XZ_XZAW_KNOWN_FLAGS) != 0u)
        return XZ_XZAW_ERR_FLAGS;

    if (view->header_bytes != XZ_XZAW_HEADER_BYTES ||
        view->payload_offset != XZ_XZAW_HEADER_BYTES)
        return XZ_XZAW_ERR_HEADER;

    format = bytes + 32u;
    if (!XzFormatNameValid(
            format,
            view->format_name_bytes))
        return XZ_XZAW_ERR_FORMAT;

    memcpy(
        view->format_name,
        format,
        XZ_XZAW_FORMAT_NAME_BYTES);

    if (view->payload_bytes == 0u)
        return XZ_XZAW_ERR_RANGE;

    end =
        (uint64_t)view->payload_offset +
        (uint64_t)view->payload_bytes;

    if (end != (uint64_t)size)
        return end > (uint64_t)size
            ? XZ_XZAW_ERR_TRUNCATED
            : XZ_XZAW_ERR_SIZE_MISMATCH;

    return XZ_XZAW_OK;
}

const void *XzXzaudio_Payload(
    const XzXzaudioView *view,
    size_t *out_bytes)
{
    uint64_t end;

    if (out_bytes)
        *out_bytes = 0u;

    if (!view ||
        !view->data ||
        view->payload_bytes == 0u)
        return NULL;

    end =
        (uint64_t)view->payload_offset +
        (uint64_t)view->payload_bytes;

    if (end > (uint64_t)view->size)
        return NULL;

    if (out_bytes)
        *out_bytes = (size_t)view->payload_bytes;

    return view->data + view->payload_offset;
}

const char *XzXzaudio_StatusName(
    XzXzaudioStatus status)
{
    switch (status) {
    case XZ_XZAW_OK: return "OK";
    case XZ_XZAW_ERR_ARGUMENT: return "ARGUMENT";
    case XZ_XZAW_ERR_TRUNCATED: return "TRUNCATED";
    case XZ_XZAW_ERR_MAGIC: return "MAGIC";
    case XZ_XZAW_ERR_VERSION: return "VERSION";
    case XZ_XZAW_ERR_FLAGS: return "FLAGS";
    case XZ_XZAW_ERR_HEADER: return "HEADER";
    case XZ_XZAW_ERR_FORMAT: return "FORMAT";
    case XZ_XZAW_ERR_RANGE: return "RANGE";
    case XZ_XZAW_ERR_SIZE_MISMATCH:
        return "SIZE_MISMATCH";
    default: return "UNKNOWN";
    }
}

int XzXzaudio_SelfTest(void)
{
    unsigned char data[
        XZ_XZAW_HEADER_BYTES + 12u];
    XzXzaudioView view;
    size_t payload_bytes = 0u;
    const unsigned char *payload;

    memset(data, 0, sizeof(data));

    data[0] = 'X';
    data[1] = 'Z';
    data[2] = 'A';
    data[3] = 'W';

    XzWriteU32Le(data + 4u, XZ_XZAW_VERSION);
    XzWriteU32Le(
        data + 8u,
        XZ_XZAW_FLAG_SOURCE_STREAMING);
    XzWriteU32Le(data + 12u, 3u);
    XzWriteU32Le(
        data + 16u,
        XZ_XZAW_HEADER_BYTES);
    XzWriteU32Le(
        data + 20u,
        XZ_XZAW_HEADER_BYTES);
    XzWriteU32Le(data + 24u, 12u);
    memcpy(data + 32u, "OGG", 3u);
    memset(
        data + XZ_XZAW_HEADER_BYTES,
        0x6bu,
        12u);

    if (XzXzaudio_Parse(
            &view,
            data,
            sizeof(data)) != XZ_XZAW_OK)
        return 0;

    if (strcmp(view.format_name, "OGG") != 0 ||
        (view.flags &
         XZ_XZAW_FLAG_SOURCE_STREAMING) == 0u)
        return 0;

    payload =
        (const unsigned char *)XzXzaudio_Payload(
            &view,
            &payload_bytes);

    if (!payload ||
        payload_bytes != 12u ||
        payload[0] != 0x6bu)
        return 0;

    XzWriteU32Le(
        data + 8u,
        XZ_XZAW_FLAG_SOURCE_STREAMING |
        (1u << 7));

    if (XzXzaudio_Parse(
            &view,
            data,
            sizeof(data)) !=
        XZ_XZAW_ERR_FLAGS)
        return 0;

    return 1;
}
