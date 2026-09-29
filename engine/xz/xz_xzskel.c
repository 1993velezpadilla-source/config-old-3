#include "xz_xzskel.h"

#include <math.h>
#include <string.h>

#define XZ_XZSK_REQUIRED_FLAGS \
    (XZ_XZSK_FLAG_XZIEL_BASIS | XZ_XZSK_FLAG_INDEX_U32)
#define XZ_XZSK_KNOWN_FLAGS XZ_XZSK_REQUIRED_FLAGS

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

XzXzskelStatus XzXzskel_Parse(
    XzXzskelView *view,
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
        return XZ_XZSK_ERR_ARGUMENT;

    memset(view, 0, sizeof(*view));

    if (size < XZ_XZSK_HEADER_BYTES)
        return XZ_XZSK_ERR_TRUNCATED;

    if (memcmp(p, "XZSK", 4u) != 0)
        return XZ_XZSK_ERR_MAGIC;

    if (XzReadU32Le(p + 4u) != XZ_XZSK_VERSION)
        return XZ_XZSK_ERR_VERSION;

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
            return XZ_XZSK_ERR_NONFINITE;

        if (view->bounds_min[i] >
            view->bounds_max[i])
            return XZ_XZSK_ERR_RANGE;
    }

    if ((view->flags & ~XZ_XZSK_KNOWN_FLAGS) != 0u ||
        (view->flags & XZ_XZSK_REQUIRED_FLAGS) !=
            XZ_XZSK_REQUIRED_FLAGS)
        return XZ_XZSK_ERR_FLAGS;

    if (view->bone_count == 0u ||
        view->bone_count > 65535u ||
        view->vertex_count == 0u ||
        view->index_count == 0u ||
        (view->index_count % 3u) != 0u ||
        view->section_count == 0u ||
        view->string_bytes == 0u ||
        view->skeleton_hash == 0u)
        return XZ_XZSK_ERR_COUNT;

    if (bone_stride != XZ_XZSK_BONE_BYTES ||
        vertex_stride != XZ_XZSK_VERTEX_BYTES ||
        section_stride != XZ_XZSK_SECTION_BYTES ||
        view->bone_offset != XZ_XZSK_HEADER_BYTES)
        return XZ_XZSK_ERR_HEADER;

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
        return XZ_XZSK_ERR_SIZE_OVERFLOW;

    if (view->vertex_offset != expected_vertex_offset ||
        view->index_offset != expected_index_offset ||
        view->section_offset != expected_section_offset ||
        view->string_offset != expected_string_offset)
        return XZ_XZSK_ERR_HEADER;

    if ((uint64_t)view->string_offset +
            (uint64_t)view->string_bytes !=
        (uint64_t)size)
        return ((uint64_t)view->string_offset +
                (uint64_t)view->string_bytes >
                (uint64_t)size)
            ? XZ_XZSK_ERR_TRUNCATED
            : XZ_XZSK_ERR_SIZE_MISMATCH;

    for (i = 0u; i < view->bone_count; ++i) {
        const unsigned char *b =
            p + view->bone_offset +
            (size_t)i * bone_stride;
        int32_t parent = XzReadI32Le(b + 0u);
        uint32_t name_offset = XzReadU32Le(b + 4u);
        uint32_t name_bytes = XzReadU32Le(b + 8u);

        if (XzReadU32Le(b + 12u) != 0u)
            return XZ_XZSK_ERR_HEADER;

        if (parent < -1 ||
            (parent >= 0 && (uint32_t)parent >= i))
            return XZ_XZSK_ERR_HIERARCHY;

        if (name_bytes == 0u ||
            name_offset > view->string_bytes ||
            name_bytes >
                view->string_bytes - name_offset)
            return XZ_XZSK_ERR_NAME_RANGE;

        if (!XzFiniteFloats(b + 16u, 10u))
            return XZ_XZSK_ERR_NONFINITE;
    }

    for (i = 0u; i < view->vertex_count; ++i) {
        const unsigned char *v =
            p + view->vertex_offset +
            (size_t)i * vertex_stride;
        unsigned int j;
        uint32_t weight_sum = 0u;

        if (!XzFiniteFloats(v, 26u))
            return XZ_XZSK_ERR_NONFINITE;

        for (j = 0u; j < XZ_XZSK_MAX_INFLUENCES; ++j) {
            uint16_t bone =
                XzReadU16Le(v + 104u + j * 2u);
            uint16_t weight =
                XzReadU16Le(v + 120u + j * 2u);

            if (weight != 0u) {
                if ((uint32_t)bone >= view->bone_count)
                    return XZ_XZSK_ERR_WEIGHT_RANGE;
                weight_sum += (uint32_t)weight;
            }
        }

        if (weight_sum == 0u)
            return XZ_XZSK_ERR_WEIGHT_RANGE;
    }

    for (i = 0u; i < view->index_count; ++i) {
        uint32_t index =
            XzReadU32Le(
                p + view->index_offset +
                (size_t)i * 4u);

        if (index >= view->vertex_count)
            return XZ_XZSK_ERR_INDEX_RANGE;
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
            return XZ_XZSK_ERR_INDEX_RANGE;
    }

    view->data = p;
    view->size = size;
    return XZ_XZSK_OK;
}

const char *XzXzskel_StatusName(
    XzXzskelStatus status)
{
    switch (status) {
    case XZ_XZSK_OK: return "OK";
    case XZ_XZSK_ERR_ARGUMENT: return "ARGUMENT";
    case XZ_XZSK_ERR_TRUNCATED: return "TRUNCATED";
    case XZ_XZSK_ERR_MAGIC: return "MAGIC";
    case XZ_XZSK_ERR_VERSION: return "VERSION";
    case XZ_XZSK_ERR_FLAGS: return "FLAGS";
    case XZ_XZSK_ERR_HEADER: return "HEADER";
    case XZ_XZSK_ERR_COUNT: return "COUNT";
    case XZ_XZSK_ERR_RANGE: return "RANGE";
    case XZ_XZSK_ERR_SIZE_OVERFLOW: return "SIZE_OVERFLOW";
    case XZ_XZSK_ERR_SIZE_MISMATCH: return "SIZE_MISMATCH";
    case XZ_XZSK_ERR_NONFINITE: return "NONFINITE";
    case XZ_XZSK_ERR_HIERARCHY: return "HIERARCHY";
    case XZ_XZSK_ERR_INDEX_RANGE: return "INDEX_RANGE";
    case XZ_XZSK_ERR_WEIGHT_RANGE: return "WEIGHT_RANGE";
    case XZ_XZSK_ERR_NAME_RANGE: return "NAME_RANGE";
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

int XzXzskel_SelfTest(void)
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
    XzXzskelView view;
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

    XzWriteU32Le(data + 4u, XZ_XZSK_VERSION);
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
    XzWriteF32Le(data + 84u, 1.0f);
    XzWriteF32Le(data + 88u, 1.0f);

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

    memcpy(data + string_offset, "root", NameBytes);

    return XzXzskel_Parse(
        &view,
        data,
        sizeof(data)) == XZ_XZSK_OK;
}
