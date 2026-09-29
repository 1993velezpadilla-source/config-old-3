#include "xz_xzrig.h"

#include <math.h>
#include <string.h>

#define XZ_XZRG_REQUIRED_FLAGS XZ_XZRG_FLAG_XZIEL_BASIS
#define XZ_XZRG_KNOWN_FLAGS XZ_XZRG_REQUIRED_FLAGS

static uint32_t XzReadU32Le(
    const unsigned char *p)
{
    return ((uint32_t)p[0]) |
           ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

static int32_t XzReadI32Le(
    const unsigned char *p)
{
    return (int32_t)XzReadU32Le(p);
}

static uint64_t XzReadU64Le(
    const unsigned char *p)
{
    return ((uint64_t)XzReadU32Le(p)) |
           ((uint64_t)XzReadU32Le(p + 4u) << 32);
}

static float XzReadF32Le(
    const unsigned char *p)
{
    uint32_t bits = XzReadU32Le(p);
    float value;
    memcpy(&value, &bits, sizeof(value));
    return value;
}

static int XzFiniteFloats(
    const unsigned char *p,
    unsigned int count)
{
    unsigned int i;

    for (i = 0u; i < count; ++i) {
        if (!isfinite(
                XzReadF32Le(
                    p + i * 4u)))
            return 0;
    }

    return 1;
}

XzXzrigStatus XzXzrig_Parse(
    XzXzrigView *view,
    const void *data,
    size_t size)
{
    const unsigned char *p =
        (const unsigned char *)data;
    uint32_t bone_stride;
    uint64_t expected_string_offset;
    uint32_t i;

    if (!view || !data)
        return XZ_XZRG_ERR_ARGUMENT;

    memset(view, 0, sizeof(*view));

    if (size < XZ_XZRG_HEADER_BYTES)
        return XZ_XZRG_ERR_TRUNCATED;

    if (memcmp(p, "XZRG", 4u) != 0)
        return XZ_XZRG_ERR_MAGIC;

    if (XzReadU32Le(p + 4u) !=
        XZ_XZRG_VERSION)
        return XZ_XZRG_ERR_VERSION;

    view->flags =
        XzReadU32Le(p + 8u);
    view->bone_count =
        XzReadU32Le(p + 12u);
    bone_stride =
        XzReadU32Le(p + 16u);
    view->bone_offset =
        XzReadU32Le(p + 20u);
    view->string_offset =
        XzReadU32Le(p + 24u);
    view->string_bytes =
        XzReadU32Le(p + 28u);
    view->skeleton_hash =
        XzReadU64Le(p + 32u);
    view->pose_hash =
        XzReadU64Le(p + 40u);

    if ((view->flags &
         ~XZ_XZRG_KNOWN_FLAGS) != 0u ||
        (view->flags &
         XZ_XZRG_REQUIRED_FLAGS) !=
            XZ_XZRG_REQUIRED_FLAGS)
        return XZ_XZRG_ERR_FLAGS;

    if (view->bone_count == 0u ||
        view->bone_count > 65535u ||
        view->string_bytes == 0u ||
        view->skeleton_hash == 0u ||
        view->pose_hash == 0u)
        return XZ_XZRG_ERR_COUNT;

    if (bone_stride !=
            XZ_XZRG_BONE_BYTES ||
        view->bone_offset !=
            XZ_XZRG_HEADER_BYTES)
        return XZ_XZRG_ERR_HEADER;

    expected_string_offset =
        (uint64_t)view->bone_offset +
        (uint64_t)view->bone_count *
            (uint64_t)bone_stride;

    if (expected_string_offset >
        UINT32_MAX)
        return XZ_XZRG_ERR_SIZE_OVERFLOW;

    if (view->string_offset !=
        (uint32_t)expected_string_offset)
        return XZ_XZRG_ERR_HEADER;

    if ((uint64_t)view->string_offset +
            (uint64_t)view->string_bytes !=
        (uint64_t)size)
        return
            (uint64_t)view->string_offset +
                    (uint64_t)view->string_bytes >
                (uint64_t)size
            ? XZ_XZRG_ERR_TRUNCATED
            : XZ_XZRG_ERR_SIZE_MISMATCH;

    for (i = 0u;
         i < view->bone_count;
         ++i) {
        const unsigned char *b =
            p + view->bone_offset +
            (size_t)i * bone_stride;
        int32_t parent =
            XzReadI32Le(b + 0u);
        uint32_t name_offset =
            XzReadU32Le(b + 4u);
        uint32_t name_bytes =
            XzReadU32Le(b + 8u);

        if (XzReadU32Le(b + 12u) != 0u)
            return XZ_XZRG_ERR_HEADER;

        if (parent < -1 ||
            (parent >= 0 &&
             (uint32_t)parent >= i))
            return XZ_XZRG_ERR_HIERARCHY;

        if (name_bytes == 0u ||
            name_offset >
                view->string_bytes ||
            name_bytes >
                view->string_bytes -
                    name_offset)
            return XZ_XZRG_ERR_NAME_RANGE;

        if (!XzFiniteFloats(
                b + 16u,
                10u))
            return XZ_XZRG_ERR_NONFINITE;
    }

    view->data = p;
    view->size = size;
    return XZ_XZRG_OK;
}

const char *XzXzrig_StatusName(
    XzXzrigStatus status)
{
    switch (status) {
    case XZ_XZRG_OK: return "OK";
    case XZ_XZRG_ERR_ARGUMENT:
        return "ARGUMENT";
    case XZ_XZRG_ERR_TRUNCATED:
        return "TRUNCATED";
    case XZ_XZRG_ERR_MAGIC:
        return "MAGIC";
    case XZ_XZRG_ERR_VERSION:
        return "VERSION";
    case XZ_XZRG_ERR_FLAGS:
        return "FLAGS";
    case XZ_XZRG_ERR_HEADER:
        return "HEADER";
    case XZ_XZRG_ERR_COUNT:
        return "COUNT";
    case XZ_XZRG_ERR_SIZE_OVERFLOW:
        return "SIZE_OVERFLOW";
    case XZ_XZRG_ERR_SIZE_MISMATCH:
        return "SIZE_MISMATCH";
    case XZ_XZRG_ERR_NONFINITE:
        return "NONFINITE";
    case XZ_XZRG_ERR_HIERARCHY:
        return "HIERARCHY";
    case XZ_XZRG_ERR_NAME_RANGE:
        return "NAME_RANGE";
    default:
        return "UNKNOWN";
    }
}

static void XzWriteU32Le(
    unsigned char *p,
    uint32_t value)
{
    p[0] =
        (unsigned char)(value & 0xffu);
    p[1] =
        (unsigned char)((value >> 8) & 0xffu);
    p[2] =
        (unsigned char)((value >> 16) & 0xffu);
    p[3] =
        (unsigned char)((value >> 24) & 0xffu);
}

static void XzWriteI32Le(
    unsigned char *p,
    int32_t value)
{
    XzWriteU32Le(
        p,
        (uint32_t)value);
}

static void XzWriteU64Le(
    unsigned char *p,
    uint64_t value)
{
    XzWriteU32Le(
        p,
        (uint32_t)value);
    XzWriteU32Le(
        p + 4u,
        (uint32_t)(value >> 32));
}

static void XzWriteF32Le(
    unsigned char *p,
    float value)
{
    uint32_t bits;
    memcpy(
        &bits,
        &value,
        sizeof(bits));
    XzWriteU32Le(p, bits);
}

int XzXzrig_SelfTest(void)
{
    enum {
        Bones = 2,
        NameBytes = 9
    };
    unsigned char data[
        XZ_XZRG_HEADER_BYTES +
        Bones * XZ_XZRG_BONE_BYTES +
        NameBytes];
    XzXzrigView view;
    uint32_t string_offset =
        XZ_XZRG_HEADER_BYTES +
        Bones * XZ_XZRG_BONE_BYTES;
    unsigned char *b0;
    unsigned char *b1;

    memset(data, 0, sizeof(data));
    memcpy(data, "XZRG", 4u);

    XzWriteU32Le(
        data + 4u,
        XZ_XZRG_VERSION);
    XzWriteU32Le(
        data + 8u,
        XZ_XZRG_FLAG_XZIEL_BASIS);
    XzWriteU32Le(
        data + 12u,
        Bones);
    XzWriteU32Le(
        data + 16u,
        XZ_XZRG_BONE_BYTES);
    XzWriteU32Le(
        data + 20u,
        XZ_XZRG_HEADER_BYTES);
    XzWriteU32Le(
        data + 24u,
        string_offset);
    XzWriteU32Le(
        data + 28u,
        NameBytes);
    XzWriteU64Le(
        data + 32u,
        0x1111222233334444ull);
    XzWriteU64Le(
        data + 40u,
        0x5555666677778888ull);

    b0 =
        data + XZ_XZRG_HEADER_BYTES;
    b1 =
        b0 + XZ_XZRG_BONE_BYTES;

    XzWriteI32Le(b0 + 0u, -1);
    XzWriteU32Le(b0 + 4u, 0u);
    XzWriteU32Le(b0 + 8u, 4u);
    XzWriteF32Le(b0 + 28u, 1.0f);
    XzWriteF32Le(b0 + 44u, 1.0f);
    XzWriteF32Le(b0 + 48u, 1.0f);
    XzWriteF32Le(b0 + 52u, 1.0f);

    XzWriteI32Le(b1 + 0u, 0);
    XzWriteU32Le(b1 + 4u, 4u);
    XzWriteU32Le(b1 + 8u, 5u);
    XzWriteF32Le(b1 + 28u, 1.0f);
    XzWriteF32Le(b1 + 44u, 1.0f);
    XzWriteF32Le(b1 + 48u, 1.0f);
    XzWriteF32Le(b1 + 52u, 1.0f);

    memcpy(
        data + string_offset,
        "rootchild",
        NameBytes);

    if (XzXzrig_Parse(
            &view,
            data,
            sizeof(data)) !=
        XZ_XZRG_OK)
        return 0;

    if (view.bone_count != Bones ||
        view.skeleton_hash !=
            0x1111222233334444ull ||
        view.pose_hash !=
            0x5555666677778888ull)
        return 0;

    return 1;
}
