#include "xz_xzanim.h"

#include <math.h>
#include <string.h>

#define XZ_XZAN_KNOWN_FLAGS \
    (XZ_XZAN_FLAG_XZIEL_BASIS | XZ_XZAN_FLAG_ADDITIVE)
#define XZ_XZAN_REQUIRED_FLAGS XZ_XZAN_FLAG_XZIEL_BASIS

static uint32_t XzReadU32Le(const unsigned char *p)
{
    return ((uint32_t)p[0]) |
           ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

static uint64_t XzReadU64Le(const unsigned char *p)
{
    return ((uint64_t)XzReadU32Le(p)) |
           ((uint64_t)XzReadU32Le(p + 4u) << 32);
}

static float XzReadF32Le(const unsigned char *p)
{
    uint32_t bits = XzReadU32Le(p);
    float value;
    memcpy(&value, &bits, sizeof(value));
    return value;
}

static int XzMulAddU32(
    uint32_t base,
    uint32_t count,
    uint32_t stride,
    uint32_t *out)
{
    uint64_t value;

    if (!out)
        return 0;

    value =
        (uint64_t)base +
        (uint64_t)count *
            (uint64_t)stride;

    if (value > UINT32_MAX)
        return 0;

    *out = (uint32_t)value;
    return 1;
}

static int XzArrayRange(
    uint32_t payload_bytes,
    uint32_t offset,
    uint32_t count,
    uint32_t stride)
{
    uint64_t bytes =
        (uint64_t)count *
        (uint64_t)stride;

    return (uint64_t)offset <= payload_bytes &&
           bytes <=
               (uint64_t)payload_bytes -
               (uint64_t)offset;
}

static int XzFiniteArray(
    const unsigned char *payload,
    uint32_t offset,
    uint32_t count,
    uint32_t components)
{
    uint64_t values =
        (uint64_t)count *
        (uint64_t)components;
    uint64_t i;

    for (i = 0u; i < values; ++i) {
        if (!isfinite(
                XzReadF32Le(
                    payload +
                    offset +
                    (size_t)i * 4u)))
            return 0;
    }

    return 1;
}

static int XzTimesValid(
    const unsigned char *payload,
    uint32_t offset,
    uint32_t count,
    uint32_t frame_count)
{
    uint32_t i;
    float previous = -1.0f;

    for (i = 0u; i < count; ++i) {
        float value =
            XzReadF32Le(
                payload +
                offset +
                (size_t)i * 4u);

        if (!isfinite(value) ||
            value < 0.0f ||
            value > (float)frame_count ||
            (i > 0u && value < previous))
            return 0;

        previous = value;
    }

    return 1;
}

XzXzanimStatus XzXzanim_Parse(
    XzXzanimView *view,
    const void *data,
    size_t size)
{
    const unsigned char *p =
        (const unsigned char *)data;
    uint32_t track_stride;
    uint32_t expected_payload_offset;
    uint32_t i;

    if (!view || !data)
        return XZ_XZAN_ERR_ARGUMENT;

    memset(view, 0, sizeof(*view));

    if (size < XZ_XZAN_HEADER_BYTES)
        return XZ_XZAN_ERR_TRUNCATED;

    if (memcmp(p, "XZAN", 4u) != 0)
        return XZ_XZAN_ERR_MAGIC;

    if (XzReadU32Le(p + 4u) != XZ_XZAN_VERSION)
        return XZ_XZAN_ERR_VERSION;

    view->flags = XzReadU32Le(p + 8u);
    view->frame_count = XzReadU32Le(p + 12u);
    view->frames_per_second = XzReadF32Le(p + 16u);
    view->duration_seconds = XzReadF32Le(p + 20u);
    view->track_count = XzReadU32Le(p + 24u);
    track_stride = XzReadU32Le(p + 28u);
    view->track_offset = XzReadU32Le(p + 32u);
    view->payload_offset = XzReadU32Le(p + 36u);
    view->payload_bytes = XzReadU32Le(p + 40u);

    if (XzReadU32Le(p + 44u) != 0u)
        return XZ_XZAN_ERR_HEADER;

    view->skeleton_hash = XzReadU64Le(p + 48u);

    if ((view->flags & ~XZ_XZAN_KNOWN_FLAGS) != 0u ||
        (view->flags & XZ_XZAN_REQUIRED_FLAGS) !=
            XZ_XZAN_REQUIRED_FLAGS)
        return XZ_XZAN_ERR_FLAGS;

    if (view->frame_count == 0u ||
        !isfinite(view->frames_per_second) ||
        view->frames_per_second <= 0.0f ||
        !isfinite(view->duration_seconds) ||
        view->duration_seconds <= 0.0f ||
        view->track_count == 0u ||
        view->skeleton_hash == 0u)
        return XZ_XZAN_ERR_COUNT;

    if (track_stride != XZ_XZAN_TRACK_BYTES ||
        view->track_offset != XZ_XZAN_HEADER_BYTES)
        return XZ_XZAN_ERR_HEADER;

    if (!XzMulAddU32(
            view->track_offset,
            view->track_count,
            track_stride,
            &expected_payload_offset))
        return XZ_XZAN_ERR_SIZE_OVERFLOW;

    if (view->payload_offset != expected_payload_offset)
        return XZ_XZAN_ERR_HEADER;

    if ((uint64_t)view->payload_offset +
            (uint64_t)view->payload_bytes !=
        (uint64_t)size)
        return ((uint64_t)view->payload_offset +
                (uint64_t)view->payload_bytes >
                (uint64_t)size)
            ? XZ_XZAN_ERR_TRUNCATED
            : XZ_XZAN_ERR_SIZE_MISMATCH;

    for (i = 0u; i < view->track_count; ++i) {
        const unsigned char *t =
            p + view->track_offset +
            (size_t)i * track_stride;
        const unsigned char *payload =
            p + view->payload_offset;
        uint32_t pos_count = XzReadU32Le(t + 0u);
        uint32_t rot_count = XzReadU32Le(t + 4u);
        uint32_t scale_count = XzReadU32Le(t + 8u);
        uint32_t shared_time_count = XzReadU32Le(t + 12u);
        uint32_t pos_time_count = XzReadU32Le(t + 16u);
        uint32_t rot_time_count = XzReadU32Le(t + 20u);
        uint32_t scale_time_count = XzReadU32Le(t + 24u);
        uint32_t pos_offset = XzReadU32Le(t + 28u);
        uint32_t rot_offset = XzReadU32Le(t + 32u);
        uint32_t scale_offset = XzReadU32Le(t + 36u);
        uint32_t shared_time_offset = XzReadU32Le(t + 40u);
        uint32_t pos_time_offset = XzReadU32Le(t + 44u);
        uint32_t rot_time_offset = XzReadU32Le(t + 48u);
        uint32_t scale_time_offset = XzReadU32Le(t + 52u);

        /*
         * Zero-key tracks are valid: Unreal evaluates those bones from the
         * linked skeleton reference pose. Keep the record so track index
         * remains identical to skeleton bone index.
         */
        if (!XzArrayRange(
                view->payload_bytes,
                pos_offset,
                pos_count,
                12u) ||
            !XzArrayRange(
                view->payload_bytes,
                rot_offset,
                rot_count,
                16u) ||
            !XzArrayRange(
                view->payload_bytes,
                scale_offset,
                scale_count,
                12u) ||
            !XzArrayRange(
                view->payload_bytes,
                shared_time_offset,
                shared_time_count,
                4u) ||
            !XzArrayRange(
                view->payload_bytes,
                pos_time_offset,
                pos_time_count,
                4u) ||
            !XzArrayRange(
                view->payload_bytes,
                rot_time_offset,
                rot_time_count,
                4u) ||
            !XzArrayRange(
                view->payload_bytes,
                scale_time_offset,
                scale_time_count,
                4u))
            return XZ_XZAN_ERR_RANGE;

        if (!XzFiniteArray(
                payload,
                pos_offset,
                pos_count,
                3u) ||
            !XzFiniteArray(
                payload,
                rot_offset,
                rot_count,
                4u) ||
            !XzFiniteArray(
                payload,
                scale_offset,
                scale_count,
                3u))
            return XZ_XZAN_ERR_NONFINITE;

        if ((shared_time_count > 0u &&
             !XzTimesValid(
                 payload,
                 shared_time_offset,
                 shared_time_count,
                 view->frame_count)) ||
            (pos_time_count > 0u &&
             !XzTimesValid(
                 payload,
                 pos_time_offset,
                 pos_time_count,
                 view->frame_count)) ||
            (rot_time_count > 0u &&
             !XzTimesValid(
                 payload,
                 rot_time_offset,
                 rot_time_count,
                 view->frame_count)) ||
            (scale_time_count > 0u &&
             !XzTimesValid(
                 payload,
                 scale_time_offset,
                 scale_time_count,
                 view->frame_count)))
            return XZ_XZAN_ERR_TIME_RANGE;
    }

    view->data = p;
    view->size = size;
    return XZ_XZAN_OK;
}

const char *XzXzanim_StatusName(
    XzXzanimStatus status)
{
    switch (status) {
    case XZ_XZAN_OK: return "OK";
    case XZ_XZAN_ERR_ARGUMENT: return "ARGUMENT";
    case XZ_XZAN_ERR_TRUNCATED: return "TRUNCATED";
    case XZ_XZAN_ERR_MAGIC: return "MAGIC";
    case XZ_XZAN_ERR_VERSION: return "VERSION";
    case XZ_XZAN_ERR_FLAGS: return "FLAGS";
    case XZ_XZAN_ERR_HEADER: return "HEADER";
    case XZ_XZAN_ERR_COUNT: return "COUNT";
    case XZ_XZAN_ERR_RANGE: return "RANGE";
    case XZ_XZAN_ERR_SIZE_OVERFLOW: return "SIZE_OVERFLOW";
    case XZ_XZAN_ERR_SIZE_MISMATCH: return "SIZE_MISMATCH";
    case XZ_XZAN_ERR_NONFINITE: return "NONFINITE";
    case XZ_XZAN_ERR_TIME_RANGE: return "TIME_RANGE";
    default: return "UNKNOWN";
    }
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

static void XzWriteU64Le(
    unsigned char *p,
    uint64_t value)
{
    XzWriteU32Le(p, (uint32_t)value);
    XzWriteU32Le(p + 4u, (uint32_t)(value >> 32));
}

static void XzWriteF32Le(
    unsigned char *p,
    float value)
{
    uint32_t bits;
    memcpy(&bits, &value, sizeof(bits));
    XzWriteU32Le(p, bits);
}

int XzXzanim_SelfTest(void)
{
    enum {
        Tracks = 2,
        PayloadBytes = 40
    };
    unsigned char data[
        XZ_XZAN_HEADER_BYTES +
        Tracks * XZ_XZAN_TRACK_BYTES +
        PayloadBytes];
    XzXzanimView view;
    uint32_t payload_offset =
        XZ_XZAN_HEADER_BYTES +
        Tracks * XZ_XZAN_TRACK_BYTES;
    unsigned char *t =
        data + XZ_XZAN_HEADER_BYTES;
    unsigned char *payload =
        data + payload_offset;

    memset(data, 0, sizeof(data));
    memcpy(data, "XZAN", 4u);

    XzWriteU32Le(data + 4u, XZ_XZAN_VERSION);
    XzWriteU32Le(data + 8u, XZ_XZAN_FLAG_XZIEL_BASIS);
    XzWriteU32Le(data + 12u, 30u);
    XzWriteF32Le(data + 16u, 30.0f);
    XzWriteF32Le(data + 20u, 1.0f);
    XzWriteU32Le(data + 24u, Tracks);
    XzWriteU32Le(data + 28u, XZ_XZAN_TRACK_BYTES);
    XzWriteU32Le(data + 32u, XZ_XZAN_HEADER_BYTES);
    XzWriteU32Le(data + 36u, payload_offset);
    XzWriteU32Le(data + 40u, PayloadBytes);
    XzWriteU64Le(data + 48u, 0x1111222233334444ull);

    XzWriteU32Le(t + 0u, 1u);
    XzWriteU32Le(t + 4u, 1u);
    XzWriteU32Le(t + 8u, 1u);
    XzWriteU32Le(t + 28u, 0u);
    XzWriteU32Le(t + 32u, 12u);
    XzWriteU32Le(t + 36u, 28u);
    XzWriteU32Le(t + 40u, 40u);
    XzWriteU32Le(t + 44u, 40u);
    XzWriteU32Le(t + 48u, 40u);
    XzWriteU32Le(t + 52u, 40u);

    /*
     * Track 1 stays all-zero by design. It represents a valid bone that has
     * no authored transform keys and must evaluate from the reference pose.
     */

    XzWriteF32Le(payload + 24u, 1.0f);
    XzWriteF32Le(payload + 28u, 1.0f);
    XzWriteF32Le(payload + 32u, 1.0f);
    XzWriteF32Le(payload + 36u, 1.0f);

    return XzXzanim_Parse(
        &view,
        data,
        sizeof(data)) == XZ_XZAN_OK;
}
