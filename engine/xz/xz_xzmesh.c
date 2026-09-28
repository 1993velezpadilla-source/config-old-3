#include "xz_xzmesh.h"

#include <math.h>
#include <string.h>

#define XZ_XZMS_KNOWN_FLAGS \
    (XZ_XZMS_FLAG_GLTF_TO_XZIEL | XZ_XZMS_FLAG_INDEX_U32)
#define XZ_XZMS_REQUIRED_FLAGS XZ_XZMS_KNOWN_FLAGS
#define XZ_XZMS_KNOWN_ATTRS \
    (XZ_XZMS_ATTR_POSITION | XZ_XZMS_ATTR_NORMAL | XZ_XZMS_ATTR_UV0 | \
     XZ_XZMS_ATTR_UV1 | XZ_XZMS_ATTR_UV2 | XZ_XZMS_ATTR_UV3 | \
     XZ_XZMS_ATTR_TANGENT)

static uint32_t XzReadU32Le(const unsigned char *p)
{
    return ((uint32_t)p[0]) |
           ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

static float XzReadF32Le(const unsigned char *p)
{
    uint32_t bits = XzReadU32Le(p);
    float value;
    memcpy(&value, &bits, sizeof(value));
    return value;
}

static int XzMulAddSize(
    size_t base,
    uint32_t count,
    uint32_t stride,
    size_t *out)
{
    size_t product;

    if (!out)
        return 0;

    if (count != 0u &&
        (size_t)stride > (SIZE_MAX - base) / (size_t)count)
        return 0;

    product = (size_t)count * (size_t)stride;
    *out = base + product;
    return 1;
}

static int XzFiniteVertex(
    const XzXzmeshVertex *vertex)
{
    unsigned int i;

    if (!vertex)
        return 0;

    for (i = 0u; i < 3u; ++i) {
        if (!isfinite(vertex->position[i]) ||
            !isfinite(vertex->normal[i]))
            return 0;
    }

    for (i = 0u; i < 4u; ++i) {
        if (!isfinite(vertex->tangent[i]))
            return 0;
    }

    return isfinite(vertex->uv[0]) &&
           isfinite(vertex->uv[1]) &&
           isfinite(vertex->uv1[0]) &&
           isfinite(vertex->uv1[1]) &&
           isfinite(vertex->uv2[0]) &&
           isfinite(vertex->uv2[1]) &&
           isfinite(vertex->uv3[0]) &&
           isfinite(vertex->uv3[1]);
}

int XzXzmesh_ReadVertex(
    const XzXzmeshView *view,
    uint32_t index,
    XzXzmeshVertex *vertex)
{
    const unsigned char *p;
    unsigned int i;

    if (!view || !view->data || !vertex ||
        index >= view->vertex_count)
        return 0;

    p = view->data +
        view->vertex_offset +
        (size_t)index * view->vertex_stride;

    for (i = 0u; i < 3u; ++i)
        vertex->position[i] =
            XzReadF32Le(p + i * 4u);

    for (i = 0u; i < 3u; ++i)
        vertex->normal[i] =
            XzReadF32Le(p + 12u + i * 4u);

    vertex->tangent[0] = 0.0f;
    vertex->tangent[1] = 0.0f;
    vertex->tangent[2] = 0.0f;
    vertex->tangent[3] = 1.0f;
    vertex->uv[0] = 0.0f;
    vertex->uv[1] = 0.0f;
    vertex->uv1[0] = 0.0f;
    vertex->uv1[1] = 0.0f;
    vertex->uv2[0] = 0.0f;
    vertex->uv2[1] = 0.0f;
    vertex->uv3[0] = 0.0f;
    vertex->uv3[1] = 0.0f;

    if (view->version >= XZ_XZMS_VERSION) {
        for (i = 0u; i < 4u; ++i)
            vertex->tangent[i] =
                XzReadF32Le(p + 24u + i * 4u);
        vertex->uv[0] = XzReadF32Le(p + 40u);
        vertex->uv[1] = XzReadF32Le(p + 44u);
        vertex->uv1[0] = XzReadF32Le(p + 48u);
        vertex->uv1[1] = XzReadF32Le(p + 52u);
        vertex->uv2[0] = XzReadF32Le(p + 56u);
        vertex->uv2[1] = XzReadF32Le(p + 60u);
        vertex->uv3[0] = XzReadF32Le(p + 64u);
        vertex->uv3[1] = XzReadF32Le(p + 68u);
    } else {
        vertex->uv[0] = XzReadF32Le(p + 24u);
        vertex->uv[1] = XzReadF32Le(p + 28u);
        if (view->version >= XZ_XZMS_VERSION_V2) {
            vertex->uv1[0] = XzReadF32Le(p + 32u);
            vertex->uv1[1] = XzReadF32Le(p + 36u);
            vertex->uv2[0] = XzReadF32Le(p + 40u);
            vertex->uv2[1] = XzReadF32Le(p + 44u);
            vertex->uv3[0] = XzReadF32Le(p + 48u);
            vertex->uv3[1] = XzReadF32Le(p + 52u);
        }
    }

    return 1;
}

int XzXzmesh_ReadIndex(
    const XzXzmeshView *view,
    uint32_t index,
    uint32_t *value)
{
    const unsigned char *p;

    if (!view || !view->data || !value ||
        index >= view->index_count)
        return 0;

    p = view->data +
        view->index_offset +
        (size_t)index * 4u;
    *value = XzReadU32Le(p);
    return 1;
}

int XzXzmesh_ReadSubmesh(
    const XzXzmeshView *view,
    uint32_t index,
    XzXzmeshSubmesh *submesh)
{
    const unsigned char *p;

    if (!view || !view->data || !submesh ||
        index >= view->submesh_count)
        return 0;

    p = view->data +
        view->submesh_offset +
        (size_t)index * view->submesh_stride;

    submesh->first_index = XzReadU32Le(p + 0u);
    submesh->index_count = XzReadU32Le(p + 4u);
    submesh->material_index = XzReadU32Le(p + 8u);
    submesh->attribute_flags = XzReadU32Le(p + 12u);
    return 1;
}

XzXzmeshStatus XzXzmesh_Parse(
    XzXzmeshView *view,
    const void *data,
    size_t size)
{
    const unsigned char *bytes =
        (const unsigned char *)data;
    size_t after_vertices;
    size_t after_indices;
    size_t expected_end;
    uint32_t version;
    uint32_t i;
    float actual_min[3] = {0.0f, 0.0f, 0.0f};
    float actual_max[3] = {0.0f, 0.0f, 0.0f};

    if (!view || !data)
        return XZ_XZMS_ERR_ARGUMENT;

    memset(view, 0, sizeof(*view));

    if (size < XZ_XZMS_HEADER_BYTES)
        return XZ_XZMS_ERR_TRUNCATED;

    if (bytes[0] != 'X' ||
        bytes[1] != 'Z' ||
        bytes[2] != 'M' ||
        bytes[3] != 'S')
        return XZ_XZMS_ERR_MAGIC;

    version = XzReadU32Le(bytes + 4u);
    if (version != XZ_XZMS_VERSION_V1 &&
        version != XZ_XZMS_VERSION_V2 &&
        version != XZ_XZMS_VERSION)
        return XZ_XZMS_ERR_VERSION;

    view->version = version;
    view->vertex_count = XzReadU32Le(bytes + 8u);
    view->index_count = XzReadU32Le(bytes + 12u);
    view->submesh_count = XzReadU32Le(bytes + 16u);
    view->flags = XzReadU32Le(bytes + 20u);
    view->vertex_stride = XzReadU32Le(bytes + 24u);
    view->submesh_stride = XzReadU32Le(bytes + 28u);

    if ((view->flags & ~XZ_XZMS_KNOWN_FLAGS) != 0u ||
        (view->flags & XZ_XZMS_REQUIRED_FLAGS) !=
            XZ_XZMS_REQUIRED_FLAGS)
        return XZ_XZMS_ERR_FLAGS;

    if (((version == XZ_XZMS_VERSION_V1) &&
         view->vertex_stride != XZ_XZMS_VERTEX_BYTES_V1) ||
        ((version == XZ_XZMS_VERSION_V2) &&
         view->vertex_stride != XZ_XZMS_VERTEX_BYTES_V2) ||
        ((version == XZ_XZMS_VERSION) &&
         view->vertex_stride != XZ_XZMS_VERTEX_BYTES_V3) ||
        view->submesh_stride != XZ_XZMS_SUBMESH_BYTES)
        return XZ_XZMS_ERR_STRIDE;

    if (view->vertex_count == 0u ||
        view->index_count == 0u ||
        view->submesh_count == 0u ||
        (view->index_count % 3u) != 0u)
        return XZ_XZMS_ERR_COUNT;

    for (i = 0u; i < 3u; ++i) {
        view->bounds_min[i] =
            XzReadF32Le(bytes + 32u + i * 4u);
        view->bounds_max[i] =
            XzReadF32Le(bytes + 44u + i * 4u);

        if (!isfinite(view->bounds_min[i]) ||
            !isfinite(view->bounds_max[i]))
            return XZ_XZMS_ERR_NONFINITE;

        if (view->bounds_min[i] >
            view->bounds_max[i])
            return XZ_XZMS_ERR_BOUNDS;
    }

    view->data = bytes;
    view->size = size;
    view->vertex_offset = XZ_XZMS_HEADER_BYTES;

    if (!XzMulAddSize(
            view->vertex_offset,
            view->vertex_count,
            view->vertex_stride,
            &after_vertices))
        return XZ_XZMS_ERR_SIZE_OVERFLOW;

    view->index_offset = after_vertices;
    if (!XzMulAddSize(
            view->index_offset,
            view->index_count,
            4u,
            &after_indices))
        return XZ_XZMS_ERR_SIZE_OVERFLOW;

    view->submesh_offset = after_indices;
    if (!XzMulAddSize(
            view->submesh_offset,
            view->submesh_count,
            view->submesh_stride,
            &expected_end))
        return XZ_XZMS_ERR_SIZE_OVERFLOW;

    if (expected_end != size) {
        memset(view, 0, sizeof(*view));
        return expected_end > size
            ? XZ_XZMS_ERR_TRUNCATED
            : XZ_XZMS_ERR_SIZE_MISMATCH;
    }

    for (i = 0u; i < view->vertex_count; ++i) {
        XzXzmeshVertex vertex;
        unsigned int axis;

        if (!XzXzmesh_ReadVertex(view, i, &vertex) ||
            !XzFiniteVertex(&vertex)) {
            memset(view, 0, sizeof(*view));
            return XZ_XZMS_ERR_NONFINITE;
        }

        if (i == 0u) {
            for (axis = 0u; axis < 3u; ++axis) {
                actual_min[axis] = vertex.position[axis];
                actual_max[axis] = vertex.position[axis];
            }
        } else {
            for (axis = 0u; axis < 3u; ++axis) {
                if (vertex.position[axis] < actual_min[axis])
                    actual_min[axis] = vertex.position[axis];
                if (vertex.position[axis] > actual_max[axis])
                    actual_max[axis] = vertex.position[axis];
            }
        }
    }

    for (i = 0u; i < 3u; ++i) {
        const float scale =
            fmaxf(
                1.0f,
                fmaxf(
                    fabsf(actual_min[i]),
                    fabsf(actual_max[i])));
        const float tolerance = scale * 1.0e-5f;

        if (fabsf(actual_min[i] - view->bounds_min[i]) > tolerance ||
            fabsf(actual_max[i] - view->bounds_max[i]) > tolerance) {
            memset(view, 0, sizeof(*view));
            return XZ_XZMS_ERR_BOUNDS;
        }
    }

    for (i = 0u; i < view->index_count; ++i) {
        uint32_t value;

        if (!XzXzmesh_ReadIndex(view, i, &value) ||
            value >= view->vertex_count) {
            memset(view, 0, sizeof(*view));
            return XZ_XZMS_ERR_INDEX_RANGE;
        }
    }

    for (i = 0u; i < view->submesh_count; ++i) {
        XzXzmeshSubmesh submesh;
        uint64_t end;

        if (!XzXzmesh_ReadSubmesh(view, i, &submesh)) {
            memset(view, 0, sizeof(*view));
            return XZ_XZMS_ERR_SUBMESH_RANGE;
        }

        end =
            (uint64_t)submesh.first_index +
            (uint64_t)submesh.index_count;

        if (submesh.index_count == 0u ||
            (submesh.index_count % 3u) != 0u ||
            end > (uint64_t)view->index_count) {
            memset(view, 0, sizeof(*view));
            return XZ_XZMS_ERR_SUBMESH_RANGE;
        }

        if ((submesh.attribute_flags & ~XZ_XZMS_KNOWN_ATTRS) != 0u ||
            (submesh.attribute_flags & XZ_XZMS_ATTR_POSITION) == 0u) {
            memset(view, 0, sizeof(*view));
            return XZ_XZMS_ERR_SUBMESH_ATTRIBUTES;
        }
    }

    return XZ_XZMS_OK;
}

const char *XzXzmesh_StatusName(
    XzXzmeshStatus status)
{
    switch (status) {
    case XZ_XZMS_OK: return "OK";
    case XZ_XZMS_ERR_ARGUMENT: return "ARGUMENT";
    case XZ_XZMS_ERR_TRUNCATED: return "TRUNCATED";
    case XZ_XZMS_ERR_MAGIC: return "MAGIC";
    case XZ_XZMS_ERR_VERSION: return "VERSION";
    case XZ_XZMS_ERR_FLAGS: return "FLAGS";
    case XZ_XZMS_ERR_STRIDE: return "STRIDE";
    case XZ_XZMS_ERR_COUNT: return "COUNT";
    case XZ_XZMS_ERR_SIZE_OVERFLOW: return "SIZE_OVERFLOW";
    case XZ_XZMS_ERR_SIZE_MISMATCH: return "SIZE_MISMATCH";
    case XZ_XZMS_ERR_NONFINITE: return "NONFINITE";
    case XZ_XZMS_ERR_BOUNDS: return "BOUNDS";
    case XZ_XZMS_ERR_INDEX_RANGE: return "INDEX_RANGE";
    case XZ_XZMS_ERR_SUBMESH_RANGE: return "SUBMESH_RANGE";
    case XZ_XZMS_ERR_SUBMESH_ATTRIBUTES:
        return "SUBMESH_ATTRIBUTES";
    default:
        return "UNKNOWN";
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

static void XzWriteF32Le(
    unsigned char *p,
    float value)
{
    uint32_t bits;
    memcpy(&bits, &value, sizeof(bits));
    XzWriteU32Le(p, bits);
}

int XzXzmesh_SelfTest(void)
{
    unsigned char data[
        XZ_XZMS_HEADER_BYTES +
        3u * XZ_XZMS_VERTEX_BYTES +
        3u * 4u +
        XZ_XZMS_SUBMESH_BYTES];
    XzXzmeshView view;
    XzXzmeshVertex vertex;
    XzXzmeshSubmesh submesh;
    XzXzmeshStatus status;
    unsigned int i;
    size_t indices_at =
        XZ_XZMS_HEADER_BYTES +
        3u * XZ_XZMS_VERTEX_BYTES;
    size_t submesh_at =
        indices_at + 3u * 4u;

    memset(data, 0, sizeof(data));
    data[0] = 'X';
    data[1] = 'Z';
    data[2] = 'M';
    data[3] = 'S';

    XzWriteU32Le(data + 4u, XZ_XZMS_VERSION);
    XzWriteU32Le(data + 8u, 3u);
    XzWriteU32Le(data + 12u, 3u);
    XzWriteU32Le(data + 16u, 1u);
    XzWriteU32Le(
        data + 20u,
        XZ_XZMS_FLAG_GLTF_TO_XZIEL |
        XZ_XZMS_FLAG_INDEX_U32);
    XzWriteU32Le(data + 24u, XZ_XZMS_VERTEX_BYTES);
    XzWriteU32Le(data + 28u, XZ_XZMS_SUBMESH_BYTES);

    /* Bounds: (0,0,0) to (1,1,0). */
    for (i = 0u; i < 3u; ++i)
        XzWriteF32Le(data + 32u + i * 4u, 0.0f);
    XzWriteF32Le(data + 44u, 1.0f);
    XzWriteF32Le(data + 48u, 1.0f);
    XzWriteF32Le(data + 52u, 0.0f);

    /* Vertex 0: normal z=1, tangent x=1, handedness=1. */
    XzWriteF32Le(
        data + XZ_XZMS_HEADER_BYTES + 20u,
        1.0f);
    XzWriteF32Le(
        data + XZ_XZMS_HEADER_BYTES + 24u,
        1.0f);
    XzWriteF32Le(
        data + XZ_XZMS_HEADER_BYTES + 36u,
        1.0f);

    /* Vertex 1: position x=1, normal z=1, tangent x=1, uv0=(1,0). */
    XzWriteF32Le(
        data + XZ_XZMS_HEADER_BYTES +
            XZ_XZMS_VERTEX_BYTES + 0u,
        1.0f);
    XzWriteF32Le(
        data + XZ_XZMS_HEADER_BYTES +
            XZ_XZMS_VERTEX_BYTES + 20u,
        1.0f);
    XzWriteF32Le(
        data + XZ_XZMS_HEADER_BYTES +
            XZ_XZMS_VERTEX_BYTES + 24u,
        1.0f);
    XzWriteF32Le(
        data + XZ_XZMS_HEADER_BYTES +
            XZ_XZMS_VERTEX_BYTES + 36u,
        1.0f);
    XzWriteF32Le(
        data + XZ_XZMS_HEADER_BYTES +
            XZ_XZMS_VERTEX_BYTES + 40u,
        1.0f);

    /* Vertex 2: position y=1, normal z=1, tangent x=1, uv0=(0,1). */
    XzWriteF32Le(
        data + XZ_XZMS_HEADER_BYTES +
            2u * XZ_XZMS_VERTEX_BYTES + 4u,
        1.0f);
    XzWriteF32Le(
        data + XZ_XZMS_HEADER_BYTES +
            2u * XZ_XZMS_VERTEX_BYTES + 20u,
        1.0f);
    XzWriteF32Le(
        data + XZ_XZMS_HEADER_BYTES +
            2u * XZ_XZMS_VERTEX_BYTES + 24u,
        1.0f);
    XzWriteF32Le(
        data + XZ_XZMS_HEADER_BYTES +
            2u * XZ_XZMS_VERTEX_BYTES + 36u,
        1.0f);
    XzWriteF32Le(
        data + XZ_XZMS_HEADER_BYTES +
            2u * XZ_XZMS_VERTEX_BYTES + 44u,
        1.0f);

    XzWriteU32Le(data + indices_at + 0u, 0u);
    XzWriteU32Le(data + indices_at + 4u, 1u);
    XzWriteU32Le(data + indices_at + 8u, 2u);

    XzWriteU32Le(data + submesh_at + 0u, 0u);
    XzWriteU32Le(data + submesh_at + 4u, 3u);
    XzWriteU32Le(data + submesh_at + 8u, 7u);
    XzWriteU32Le(
        data + submesh_at + 12u,
        XZ_XZMS_ATTR_POSITION |
        XZ_XZMS_ATTR_NORMAL |
        XZ_XZMS_ATTR_UV0 |
        XZ_XZMS_ATTR_TANGENT);

    status = XzXzmesh_Parse(
        &view, data, sizeof(data));
    if (status != XZ_XZMS_OK)
        return 0;

    if (view.vertex_count != 3u ||
        view.index_count != 3u ||
        view.submesh_count != 1u)
        return 0;

    if (!XzXzmesh_ReadVertex(
            &view, 1u, &vertex) ||
        vertex.position[0] != 1.0f ||
        vertex.normal[2] != 1.0f ||
        vertex.tangent[0] != 1.0f ||
        vertex.tangent[3] != 1.0f ||
        vertex.uv[0] != 1.0f ||
        vertex.uv1[0] != 0.0f)
        return 0;

    if (!XzXzmesh_ReadSubmesh(
            &view, 0u, &submesh) ||
        submesh.material_index != 7u ||
        submesh.index_count != 3u)
        return 0;

    /* Index outside the vertex array must fail closed. */
    XzWriteU32Le(data + indices_at + 8u, 3u);
    if (XzXzmesh_Parse(
            &view, data, sizeof(data)) !=
        XZ_XZMS_ERR_INDEX_RANGE)
        return 0;
    XzWriteU32Le(data + indices_at + 8u, 2u);

    /* Unknown submesh attribute bit must fail closed. */
    XzWriteU32Le(
        data + submesh_at + 12u,
        XZ_XZMS_ATTR_POSITION | (1u << 7));
    if (XzXzmesh_Parse(
            &view, data, sizeof(data)) !=
        XZ_XZMS_ERR_SUBMESH_ATTRIBUTES)
        return 0;

    return 1;
}
