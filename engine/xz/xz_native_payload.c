#include "xz_native_payload.h"

#include <math.h>
#include <string.h>

#define XZ_XZTX_KNOWN_FLAGS XZ_XZTX_FLAG_SRGB
#define XZ_XZSK_REQUIRED_FLAGS \
    (XZ_XZSK_FLAG_XZIEL_BASIS | XZ_XZSK_FLAG_INDEX_U32)
#define XZ_XZSK_KNOWN_FLAGS XZ_XZSK_REQUIRED_FLAGS
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

static int32_t XzReadI32Le(const unsigned char *p)
{
    return (int32_t)XzReadU32Le(p);
}

static uint64_t XzReadU64Le(const unsigned char *p)
{
    return ((uint64_t)XzReadU32Le(p)) |
           ((uint64_t)XzReadU32Le(p + 4u) << 32);
}

static uint16_t XzReadU16Le(const unsigned char *p)
{
    return (uint16_t)(
        (uint16_t)p[0] |
        (uint16_t)((uint16_t)p[1] << 8));
}

static float XzReadF32Le(const unsigned char *p)
{
    uint32_t bits = XzReadU32Le(p);
    float value;
    memcpy(&value, &bits, sizeof(value));
    return value;
}

static int XzRangeFits(
    size_t size,
    uint64_t offset,
    uint64_t bytes)
{
    return offset <= (uint64_t)size &&
           bytes <= (uint64_t)size - offset;
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

static int XzFiniteFloats(
    const unsigned char *p,
    unsigned int count)
{
    unsigned int i;

    for (i = 0u; i < count; ++i) {
        if (!isfinite(XzReadF32Le(p + i * 4u)))
            return 0;
    }
    return 1;
}

int XzNativeTexture_Mip(
    const XzNativeTextureView *view,
    uint32_t mip_index,
    XzNativeTextureMip *mip)
{
    const unsigned char *p;

    if (!view || !view->data || !mip ||
        mip_index >= view->mip_count)
        return 0;

    p = view->data +
        XZ_XZTX_HEADER_BYTES +
        (size_t)mip_index *
            XZ_XZTX_MIP_BYTES;

    mip->payload_offset = XzReadU32Le(p + 0u);
    mip->bytes = XzReadU32Le(p + 4u);
    mip->width = XzReadU32Le(p + 8u);
    mip->height = XzReadU32Le(p + 12u);
    mip->depth = XzReadU32Le(p + 16u);
    return 1;
}

XzNativePayloadStatus XzNativeTexture_Parse(
    XzNativeTextureView *view,
    const void *data,
    size_t size)
{
    const unsigned char *p =
        (const unsigned char *)data;
    uint32_t mip_record_bytes;
    uint32_t mip_table_offset;
    uint32_t expected_payload_offset;
    uint32_t previous_end = 0u;
    uint32_t previous_width = 0u;
    uint32_t previous_height = 0u;
    uint32_t i;

    if (!view || !data)
        return XZ_NATIVE_ERR_ARGUMENT;
    memset(view, 0, sizeof(*view));

    if (size < XZ_XZTX_HEADER_BYTES)
        return XZ_NATIVE_ERR_TRUNCATED;
    if (memcmp(p, "XZTX", 4u) != 0)
        return XZ_NATIVE_ERR_MAGIC;
    if (XzReadU32Le(p + 4u) != XZ_NATIVE_VERSION)
        return XZ_NATIVE_ERR_VERSION;

    view->flags = XzReadU32Le(p + 8u);
    view->width = XzReadU32Le(p + 12u);
    view->height = XzReadU32Le(p + 16u);
    view->mip_count = XzReadU32Le(p + 20u);
    mip_record_bytes = XzReadU32Le(p + 24u);
    mip_table_offset = XzReadU32Le(p + 28u);
    view->payload_offset = XzReadU32Le(p + 32u);
    view->payload_bytes = XzReadU32Le(p + 36u);
    view->format_tag = XzReadU64Le(p + 40u);

    if ((view->flags & ~XZ_XZTX_KNOWN_FLAGS) != 0u)
        return XZ_NATIVE_ERR_FLAGS;
    if (view->width == 0u ||
        view->height == 0u ||
        view->mip_count == 0u ||
        view->format_tag == 0u)
        return XZ_NATIVE_ERR_COUNT;
    if (mip_record_bytes != XZ_XZTX_MIP_BYTES ||
        mip_table_offset != XZ_XZTX_HEADER_BYTES)
        return XZ_NATIVE_ERR_HEADER;
    if (!XzMulAddU32(
            mip_table_offset,
            view->mip_count,
            mip_record_bytes,
            &expected_payload_offset))
        return XZ_NATIVE_ERR_SIZE_OVERFLOW;
    if (view->payload_offset != expected_payload_offset)
        return XZ_NATIVE_ERR_HEADER;
    if (!XzRangeFits(
            size,
            view->payload_offset,
            view->payload_bytes))
        return XZ_NATIVE_ERR_RANGE;
    if ((uint64_t)view->payload_offset +
            (uint64_t)view->payload_bytes !=
        (uint64_t)size)
        return XZ_NATIVE_ERR_SIZE_MISMATCH;

    view->data = p;
    view->size = size;

    for (i = 0u; i < view->mip_count; ++i) {
        XzNativeTextureMip mip;
        uint64_t end;

        if (!XzNativeTexture_Mip(view, i, &mip))
            return XZ_NATIVE_ERR_RANGE;
        if (mip.bytes == 0u ||
            mip.width == 0u ||
            mip.height == 0u ||
            mip.depth == 0u)
            return XZ_NATIVE_ERR_COUNT;
        if (i == 0u &&
            (mip.width != view->width ||
             mip.height != view->height))
            return XZ_NATIVE_ERR_HEADER;
        if (i > 0u &&
            (mip.width > previous_width ||
             mip.height > previous_height))
            return XZ_NATIVE_ERR_RANGE;
        if (mip.payload_offset != previous_end)
            return XZ_NATIVE_ERR_RANGE;

        end =
            (uint64_t)mip.payload_offset +
            (uint64_t)mip.bytes;
        if (end > view->payload_bytes ||
            end > UINT32_MAX)
            return XZ_NATIVE_ERR_RANGE;

        previous_end = (uint32_t)end;
        previous_width = mip.width;
        previous_height = mip.height;
    }

    if (previous_end != view->payload_bytes)
        return XZ_NATIVE_ERR_SIZE_MISMATCH;

    return XZ_NATIVE_OK;
}

XzNativePayloadStatus XzNativeAudio_Parse(
    XzNativeAudioView *view,
    const void *data,
    size_t size)
{
    const unsigned char *p =
        (const unsigned char *)data;

    if (!view || !data)
        return XZ_NATIVE_ERR_ARGUMENT;
    memset(view, 0, sizeof(*view));

    if (size < XZ_XZAU_HEADER_BYTES)
        return XZ_NATIVE_ERR_TRUNCATED;
    if (memcmp(p, "XZAU", 4u) != 0)
        return XZ_NATIVE_ERR_MAGIC;
    if (XzReadU32Le(p + 4u) != XZ_NATIVE_VERSION)
        return XZ_NATIVE_ERR_VERSION;

    view->flags = XzReadU32Le(p + 8u);
    view->channels = XzReadU32Le(p + 12u);
    view->sample_rate = XzReadU32Le(p + 16u);
    view->duration_seconds = XzReadF32Le(p + 20u);
    view->codec_tag = XzReadU64Le(p + 24u);
    view->payload_offset = XzReadU32Le(p + 32u);
    view->payload_bytes = XzReadU32Le(p + 36u);

    if (view->flags != 0u)
        return XZ_NATIVE_ERR_FLAGS;
    if (view->channels == 0u ||
        view->channels > 32u ||
        view->sample_rate == 0u ||
        !isfinite(view->duration_seconds) ||
        view->duration_seconds <= 0.0f ||
        view->codec_tag == 0u ||
        view->payload_bytes == 0u)
        return XZ_NATIVE_ERR_COUNT;
    if (view->payload_offset != XZ_XZAU_HEADER_BYTES)
        return XZ_NATIVE_ERR_HEADER;
    if (!XzRangeFits(
            size,
            view->payload_offset,
            view->payload_bytes))
        return XZ_NATIVE_ERR_RANGE;
    if ((uint64_t)view->payload_offset +
            (uint64_t)view->payload_bytes !=
        (uint64_t)size)
        return XZ_NATIVE_ERR_SIZE_MISMATCH;

    view->data = p;
    view->size = size;
    return XZ_NATIVE_OK;
}

XzNativePayloadStatus XzNativeSkinnedMesh_Parse(
    XzNativeSkinnedMeshView *view,
    const void *data,
    size_t size)
{
    const unsigned char *p =
        (const unsigned char *)data;
    uint32_t bone_stride;
    uint32_t vertex_stride;
    uint32_t section_stride;
    uint32_t expected_vertex_offset;
    uint32_t expected_index_offset;
    uint32_t expected_section_offset;
    uint32_t expected_string_offset;
    uint32_t i;

    if (!view || !data)
        return XZ_NATIVE_ERR_ARGUMENT;
    memset(view, 0, sizeof(*view));

    if (size < XZ_XZSK_HEADER_BYTES)
        return XZ_NATIVE_ERR_TRUNCATED;
    if (memcmp(p, "XZSK", 4u) != 0)
        return XZ_NATIVE_ERR_MAGIC;
    if (XzReadU32Le(p + 4u) != XZ_NATIVE_VERSION)
        return XZ_NATIVE_ERR_VERSION;

    view->flags = XzReadU32Le(p + 8u);
    view->bone_count = XzReadU32Le(p + 12u);
    view->vertex_count = XzReadU32Le(p + 16u);
    view->index_count = XzReadU32Le(p + 20u);
    view->section_count = XzReadU32Le(p + 24u);
    bone_stride = XzReadU32Le(p + 28u);
    vertex_stride = XzReadU32Le(p + 32u);
    section_stride = XzReadU32Le(p + 36u);
    view->bone_offset = XzReadU32Le(p + 40u);
    view->vertex_offset = XzReadU32Le(p + 44u);
    view->index_offset = XzReadU32Le(p + 48u);
    view->section_offset = XzReadU32Le(p + 52u);
    view->string_offset = XzReadU32Le(p + 56u);
    view->string_bytes = XzReadU32Le(p + 60u);
    view->skeleton_hash = XzReadU64Le(p + 64u);

    for (i = 0u; i < 3u; ++i) {
        view->bounds_min[i] =
            XzReadF32Le(p + 72u + i * 4u);
        view->bounds_max[i] =
            XzReadF32Le(p + 84u + i * 4u);
        if (!isfinite(view->bounds_min[i]) ||
            !isfinite(view->bounds_max[i]))
            return XZ_NATIVE_ERR_NONFINITE;
        if (view->bounds_min[i] > view->bounds_max[i])
            return XZ_NATIVE_ERR_RANGE;
    }

    if ((view->flags & ~XZ_XZSK_KNOWN_FLAGS) != 0u ||
        (view->flags & XZ_XZSK_REQUIRED_FLAGS) !=
            XZ_XZSK_REQUIRED_FLAGS)
        return XZ_NATIVE_ERR_FLAGS;
    if (view->bone_count == 0u ||
        view->bone_count > 65535u ||
        view->vertex_count == 0u ||
        view->index_count == 0u ||
        (view->index_count % 3u) != 0u ||
        view->section_count == 0u ||
        view->string_bytes == 0u ||
        view->skeleton_hash == 0u)
        return XZ_NATIVE_ERR_COUNT;
    if (bone_stride != XZ_XZSK_BONE_BYTES ||
        vertex_stride != XZ_XZSK_VERTEX_BYTES ||
        section_stride != XZ_XZSK_SECTION_BYTES ||
        view->bone_offset != XZ_XZSK_HEADER_BYTES)
        return XZ_NATIVE_ERR_HEADER;

    if (!XzMulAddU32(
            view->bone_offset,
            view->bone_count,
            bone_stride,
            &expected_vertex_offset) ||
        !XzMulAddU32(
            expected_vertex_offset,
            view->vertex_count,
            vertex_stride,
            &expected_index_offset) ||
        !XzMulAddU32(
            expected_index_offset,
            view->index_count,
            4u,
            &expected_section_offset) ||
        !XzMulAddU32(
            expected_section_offset,
            view->section_count,
            section_stride,
            &expected_string_offset))
        return XZ_NATIVE_ERR_SIZE_OVERFLOW;

    if (view->vertex_offset != expected_vertex_offset ||
        view->index_offset != expected_index_offset ||
        view->section_offset != expected_section_offset ||
        view->string_offset != expected_string_offset)
        return XZ_NATIVE_ERR_HEADER;
    if (!XzRangeFits(size, view->string_offset, view->string_bytes))
        return XZ_NATIVE_ERR_RANGE;
    if ((uint64_t)view->string_offset +
            (uint64_t)view->string_bytes !=
        (uint64_t)size)
        return XZ_NATIVE_ERR_SIZE_MISMATCH;

    for (i = 0u; i < view->bone_count; ++i) {
        const unsigned char *b =
            p + view->bone_offset +
            (size_t)i * bone_stride;
        int32_t parent = XzReadI32Le(b + 0u);
        uint32_t name_offset = XzReadU32Le(b + 4u);
        uint32_t name_bytes = XzReadU32Le(b + 8u);

        if (parent < -1 ||
            (parent >= 0 && (uint32_t)parent >= i))
            return XZ_NATIVE_ERR_HIERARCHY;
        if (name_bytes == 0u ||
            !XzRangeFits(
                view->string_bytes,
                name_offset,
                name_bytes))
            return XZ_NATIVE_ERR_NAME_RANGE;
        if (!XzFiniteFloats(b + 16u, 10u))
            return XZ_NATIVE_ERR_NONFINITE;
    }

    for (i = 0u; i < view->vertex_count; ++i) {
        const unsigned char *v =
            p + view->vertex_offset +
            (size_t)i * vertex_stride;
        unsigned int j;
        uint32_t weight_sum = 0u;

        if (!XzFiniteFloats(v, 26u))
            return XZ_NATIVE_ERR_NONFINITE;

        for (j = 0u; j < XZ_XZSK_MAX_INFLUENCES; ++j) {
            uint16_t bone =
                XzReadU16Le(v + 104u + j * 2u);
            uint16_t weight =
                XzReadU16Le(v + 120u + j * 2u);

            if (weight != 0u) {
                if ((uint32_t)bone >= view->bone_count)
                    return XZ_NATIVE_ERR_WEIGHT_RANGE;
                weight_sum += (uint32_t)weight;
            }
        }

        if (weight_sum == 0u)
            return XZ_NATIVE_ERR_WEIGHT_RANGE;
    }

    for (i = 0u; i < view->index_count; ++i) {
        uint32_t index =
            XzReadU32Le(
                p + view->index_offset +
                (size_t)i * 4u);
        if (index >= view->vertex_count)
            return XZ_NATIVE_ERR_INDEX_RANGE;
    }

    for (i = 0u; i < view->section_count; ++i) {
        const unsigned char *s =
            p + view->section_offset +
            (size_t)i * section_stride;
        uint32_t first = XzReadU32Le(s + 0u);
        uint32_t count = XzReadU32Le(s + 4u);
        uint64_t end =
            (uint64_t)first +
            (uint64_t)count;

        if (count == 0u ||
            (count % 3u) != 0u ||
            end > view->index_count)
            return XZ_NATIVE_ERR_INDEX_RANGE;
    }

    view->data = p;
    view->size = size;
    return XZ_NATIVE_OK;
}

static int XzAnimArrayRange(
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

static int XzAnimFiniteArray(
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

static int XzAnimTimesValid(
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

XzNativePayloadStatus XzNativeAnimation_Parse(
    XzNativeAnimationView *view,
    const void *data,
    size_t size)
{
    const unsigned char *p =
        (const unsigned char *)data;
    uint32_t track_stride;
    uint32_t expected_payload_offset;
    uint32_t i;

    if (!view || !data)
        return XZ_NATIVE_ERR_ARGUMENT;
    memset(view, 0, sizeof(*view));

    if (size < XZ_XZAN_HEADER_BYTES)
        return XZ_NATIVE_ERR_TRUNCATED;
    if (memcmp(p, "XZAN", 4u) != 0)
        return XZ_NATIVE_ERR_MAGIC;
    if (XzReadU32Le(p + 4u) != XZ_NATIVE_VERSION)
        return XZ_NATIVE_ERR_VERSION;

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
        return XZ_NATIVE_ERR_HEADER;
    view->skeleton_hash = XzReadU64Le(p + 48u);

    if ((view->flags & ~XZ_XZAN_KNOWN_FLAGS) != 0u ||
        (view->flags & XZ_XZAN_REQUIRED_FLAGS) !=
            XZ_XZAN_REQUIRED_FLAGS)
        return XZ_NATIVE_ERR_FLAGS;
    if (view->frame_count == 0u ||
        !isfinite(view->frames_per_second) ||
        view->frames_per_second <= 0.0f ||
        !isfinite(view->duration_seconds) ||
        view->duration_seconds <= 0.0f ||
        view->track_count == 0u ||
        view->skeleton_hash == 0u)
        return XZ_NATIVE_ERR_COUNT;
    if (track_stride != XZ_XZAN_TRACK_BYTES ||
        view->track_offset != XZ_XZAN_HEADER_BYTES)
        return XZ_NATIVE_ERR_HEADER;
    if (!XzMulAddU32(
            view->track_offset,
            view->track_count,
            track_stride,
            &expected_payload_offset))
        return XZ_NATIVE_ERR_SIZE_OVERFLOW;
    if (view->payload_offset != expected_payload_offset)
        return XZ_NATIVE_ERR_HEADER;
    if (!XzRangeFits(
            size,
            view->payload_offset,
            view->payload_bytes))
        return XZ_NATIVE_ERR_RANGE;
    if ((uint64_t)view->payload_offset +
            (uint64_t)view->payload_bytes !=
        (uint64_t)size)
        return XZ_NATIVE_ERR_SIZE_MISMATCH;

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

        if (pos_count + rot_count + scale_count == 0u)
            return XZ_NATIVE_ERR_COUNT;

        if (!XzAnimArrayRange(
                view->payload_bytes,
                pos_offset,
                pos_count,
                12u) ||
            !XzAnimArrayRange(
                view->payload_bytes,
                rot_offset,
                rot_count,
                16u) ||
            !XzAnimArrayRange(
                view->payload_bytes,
                scale_offset,
                scale_count,
                12u) ||
            !XzAnimArrayRange(
                view->payload_bytes,
                shared_time_offset,
                shared_time_count,
                4u) ||
            !XzAnimArrayRange(
                view->payload_bytes,
                pos_time_offset,
                pos_time_count,
                4u) ||
            !XzAnimArrayRange(
                view->payload_bytes,
                rot_time_offset,
                rot_time_count,
                4u) ||
            !XzAnimArrayRange(
                view->payload_bytes,
                scale_time_offset,
                scale_time_count,
                4u))
            return XZ_NATIVE_ERR_RANGE;

        if (!XzAnimFiniteArray(
                payload,
                pos_offset,
                pos_count,
                3u) ||
            !XzAnimFiniteArray(
                payload,
                rot_offset,
                rot_count,
                4u) ||
            !XzAnimFiniteArray(
                payload,
                scale_offset,
                scale_count,
                3u))
            return XZ_NATIVE_ERR_NONFINITE;

        if ((shared_time_count > 0u &&
             !XzAnimTimesValid(
                 payload,
                 shared_time_offset,
                 shared_time_count,
                 view->frame_count)) ||
            (pos_time_count > 0u &&
             !XzAnimTimesValid(
                 payload,
                 pos_time_offset,
                 pos_time_count,
                 view->frame_count)) ||
            (rot_time_count > 0u &&
             !XzAnimTimesValid(
                 payload,
                 rot_time_offset,
                 rot_time_count,
                 view->frame_count)) ||
            (scale_time_count > 0u &&
             !XzAnimTimesValid(
                 payload,
                 scale_time_offset,
                 scale_time_count,
                 view->frame_count)))
            return XZ_NATIVE_ERR_TIME_RANGE;
    }

    view->data = p;
    view->size = size;
    return XZ_NATIVE_OK;
}

const char *XzNativePayload_StatusName(
    XzNativePayloadStatus status)
{
    switch (status) {
    case XZ_NATIVE_OK: return "OK";
    case XZ_NATIVE_ERR_ARGUMENT: return "ARGUMENT";
    case XZ_NATIVE_ERR_TRUNCATED: return "TRUNCATED";
    case XZ_NATIVE_ERR_MAGIC: return "MAGIC";
    case XZ_NATIVE_ERR_VERSION: return "VERSION";
    case XZ_NATIVE_ERR_FLAGS: return "FLAGS";
    case XZ_NATIVE_ERR_HEADER: return "HEADER";
    case XZ_NATIVE_ERR_COUNT: return "COUNT";
    case XZ_NATIVE_ERR_RANGE: return "RANGE";
    case XZ_NATIVE_ERR_SIZE_OVERFLOW: return "SIZE_OVERFLOW";
    case XZ_NATIVE_ERR_SIZE_MISMATCH: return "SIZE_MISMATCH";
    case XZ_NATIVE_ERR_NONFINITE: return "NONFINITE";
    case XZ_NATIVE_ERR_HIERARCHY: return "HIERARCHY";
    case XZ_NATIVE_ERR_INDEX_RANGE: return "INDEX_RANGE";
    case XZ_NATIVE_ERR_WEIGHT_RANGE: return "WEIGHT_RANGE";
    case XZ_NATIVE_ERR_NAME_RANGE: return "NAME_RANGE";
    case XZ_NATIVE_ERR_TIME_RANGE: return "TIME_RANGE";
    default: return "UNKNOWN";
    }
}

static void XzWriteU16Le(
    unsigned char *p,
    uint16_t value)
{
    p[0] = (unsigned char)(value & 0xffu);
    p[1] = (unsigned char)((value >> 8) & 0xffu);
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

static void XzWriteI32Le(
    unsigned char *p,
    int32_t value)
{
    XzWriteU32Le(p, (uint32_t)value);
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

static int XzNativeTexture_SelfTest(void)
{
    unsigned char data[
        XZ_XZTX_HEADER_BYTES +
        XZ_XZTX_MIP_BYTES +
        8u];
    XzNativeTextureView view;

    memset(data, 0, sizeof(data));
    memcpy(data, "XZTX", 4u);
    XzWriteU32Le(data + 4u, XZ_NATIVE_VERSION);
    XzWriteU32Le(data + 8u, XZ_XZTX_FLAG_SRGB);
    XzWriteU32Le(data + 12u, 4u);
    XzWriteU32Le(data + 16u, 4u);
    XzWriteU32Le(data + 20u, 1u);
    XzWriteU32Le(data + 24u, XZ_XZTX_MIP_BYTES);
    XzWriteU32Le(data + 28u, XZ_XZTX_HEADER_BYTES);
    XzWriteU32Le(
        data + 32u,
        XZ_XZTX_HEADER_BYTES + XZ_XZTX_MIP_BYTES);
    XzWriteU32Le(data + 36u, 8u);
    XzWriteU64Le(data + 40u, 0x12345678ull);
    XzWriteU32Le(data + 48u, 0u);
    XzWriteU32Le(data + 52u, 8u);
    XzWriteU32Le(data + 56u, 4u);
    XzWriteU32Le(data + 60u, 4u);
    XzWriteU32Le(data + 64u, 1u);

    return XzNativeTexture_Parse(
        &view,
        data,
        sizeof(data)) == XZ_NATIVE_OK;
}

static int XzNativeAudio_SelfTest(void)
{
    unsigned char data[XZ_XZAU_HEADER_BYTES + 4u];
    XzNativeAudioView view;

    memset(data, 0, sizeof(data));
    memcpy(data, "XZAU", 4u);
    XzWriteU32Le(data + 4u, XZ_NATIVE_VERSION);
    XzWriteU32Le(data + 12u, 2u);
    XzWriteU32Le(data + 16u, 48000u);
    XzWriteF32Le(data + 20u, 1.0f);
    XzWriteU64Le(data + 24u, 0x98765432ull);
    XzWriteU32Le(data + 32u, XZ_XZAU_HEADER_BYTES);
    XzWriteU32Le(data + 36u, 4u);

    return XzNativeAudio_Parse(
        &view,
        data,
        sizeof(data)) == XZ_NATIVE_OK;
}

static int XzNativeSkinnedMesh_SelfTest(void)
{
    enum {
        Bones = 1,
        Vertices = 3,
        Indices = 3,
        Sections = 1,
        NameBytes = 4
    };
    unsigned char data[
        XZ_XZSK_HEADER_BYTES +
        Bones * XZ_XZSK_BONE_BYTES +
        Vertices * XZ_XZSK_VERTEX_BYTES +
        Indices * 4u +
        Sections * XZ_XZSK_SECTION_BYTES +
        NameBytes];
    XzNativeSkinnedMeshView view;
    uint32_t bone_offset = XZ_XZSK_HEADER_BYTES;
    uint32_t vertex_offset =
        bone_offset + Bones * XZ_XZSK_BONE_BYTES;
    uint32_t index_offset =
        vertex_offset + Vertices * XZ_XZSK_VERTEX_BYTES;
    uint32_t section_offset =
        index_offset + Indices * 4u;
    uint32_t string_offset =
        section_offset + Sections * XZ_XZSK_SECTION_BYTES;
    unsigned int i;

    memset(data, 0, sizeof(data));
    memcpy(data, "XZSK", 4u);
    XzWriteU32Le(data + 4u, XZ_NATIVE_VERSION);
    XzWriteU32Le(
        data + 8u,
        XZ_XZSK_FLAG_XZIEL_BASIS |
        XZ_XZSK_FLAG_INDEX_U32);
    XzWriteU32Le(data + 12u, Bones);
    XzWriteU32Le(data + 16u, Vertices);
    XzWriteU32Le(data + 20u, Indices);
    XzWriteU32Le(data + 24u, Sections);
    XzWriteU32Le(data + 28u, XZ_XZSK_BONE_BYTES);
    XzWriteU32Le(data + 32u, XZ_XZSK_VERTEX_BYTES);
    XzWriteU32Le(data + 36u, XZ_XZSK_SECTION_BYTES);
    XzWriteU32Le(data + 40u, bone_offset);
    XzWriteU32Le(data + 44u, vertex_offset);
    XzWriteU32Le(data + 48u, index_offset);
    XzWriteU32Le(data + 52u, section_offset);
    XzWriteU32Le(data + 56u, string_offset);
    XzWriteU32Le(data + 60u, NameBytes);
    XzWriteU64Le(data + 64u, 0x1111222233334444ull);
    XzWriteF32Le(data + 72u, 0.0f);
    XzWriteF32Le(data + 76u, 0.0f);
    XzWriteF32Le(data + 80u, 0.0f);
    XzWriteF32Le(data + 84u, 1.0f);
    XzWriteF32Le(data + 88u, 1.0f);
    XzWriteF32Le(data + 92u, 0.0f);

    XzWriteI32Le(data + bone_offset + 0u, -1);
    XzWriteU32Le(data + bone_offset + 4u, 0u);
    XzWriteU32Le(data + bone_offset + 8u, NameBytes);
    XzWriteF32Le(data + bone_offset + 28u, 1.0f);
    XzWriteF32Le(data + bone_offset + 44u, 1.0f);
    XzWriteF32Le(data + bone_offset + 48u, 1.0f);
    XzWriteF32Le(data + bone_offset + 52u, 1.0f);

    for (i = 0u; i < Vertices; ++i) {
        unsigned char *v =
            data + vertex_offset +
            i * XZ_XZSK_VERTEX_BYTES;
        XzWriteF32Le(v + 20u, 1.0f);
        XzWriteF32Le(v + 24u, 1.0f);
        XzWriteF32Le(v + 36u, 1.0f);
        XzWriteU16Le(v + 104u, 0u);
        XzWriteU16Le(v + 120u, 65535u);
    }

    XzWriteF32Le(
        data + vertex_offset +
        XZ_XZSK_VERTEX_BYTES + 0u,
        1.0f);
    XzWriteF32Le(
        data + vertex_offset +
        2u * XZ_XZSK_VERTEX_BYTES + 4u,
        1.0f);

    XzWriteU32Le(data + index_offset + 0u, 0u);
    XzWriteU32Le(data + index_offset + 4u, 1u);
    XzWriteU32Le(data + index_offset + 8u, 2u);

    XzWriteU32Le(data + section_offset + 0u, 0u);
    XzWriteU32Le(data + section_offset + 4u, 3u);
    XzWriteU32Le(data + section_offset + 8u, 0u);
    XzWriteU32Le(data + section_offset + 12u, 0u);

    memcpy(data + string_offset, "root", NameBytes);

    return XzNativeSkinnedMesh_Parse(
        &view,
        data,
        sizeof(data)) == XZ_NATIVE_OK;
}

static int XzNativeAnimation_SelfTest(void)
{
    enum {
        Tracks = 1,
        PayloadBytes = 40
    };
    unsigned char data[
        XZ_XZAN_HEADER_BYTES +
        Tracks * XZ_XZAN_TRACK_BYTES +
        PayloadBytes];
    XzNativeAnimationView view;
    uint32_t payload_offset =
        XZ_XZAN_HEADER_BYTES +
        Tracks * XZ_XZAN_TRACK_BYTES;
    unsigned char *t =
        data + XZ_XZAN_HEADER_BYTES;
    unsigned char *payload =
        data + payload_offset;

    memset(data, 0, sizeof(data));
    memcpy(data, "XZAN", 4u);
    XzWriteU32Le(data + 4u, XZ_NATIVE_VERSION);
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

    XzWriteF32Le(payload + 12u + 12u, 1.0f);
    XzWriteF32Le(payload + 28u + 0u, 1.0f);
    XzWriteF32Le(payload + 28u + 4u, 1.0f);
    XzWriteF32Le(payload + 28u + 8u, 1.0f);

    return XzNativeAnimation_Parse(
        &view,
        data,
        sizeof(data)) == XZ_NATIVE_OK;
}

int XzNativePayload_SelfTest(void)
{
    return
        XzNativeTexture_SelfTest() &&
        XzNativeAudio_SelfTest() &&
        XzNativeSkinnedMesh_SelfTest() &&
        XzNativeAnimation_SelfTest();
}
