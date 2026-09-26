#include "xz_xzscene.h"

#include <math.h>
#include <string.h>

#define XZ_XZSC_KNOWN_FLAGS \
    (XZ_XZSC_FLAG_XZIEL_Z_UP | \
     XZ_XZSC_FLAG_METERS | \
     XZ_XZSC_FLAG_ROW_MAJOR_COLUMN_VECTOR | \
     XZ_XZSC_FLAG_XZMS_MESHES)

#define XZ_XZSC_REQUIRED_FLAGS \
    XZ_XZSC_KNOWN_FLAGS

#define XZ_XZSC_MAX_MESHES 65535u
#define XZ_XZSC_MAX_INSTANCES 4000000u

static uint32_t XzReadU32Le(
    const unsigned char *p)
{
    return ((uint32_t)p[0]) |
           ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

static float XzReadF32Le(
    const unsigned char *p)
{
    uint32_t bits = XzReadU32Le(p);
    float value;

    memcpy(&value, &bits, sizeof(value));
    return value;
}

static int XzAddMulSize(
    size_t base,
    uint32_t count,
    uint32_t stride,
    size_t *output)
{
    if (!output)
        return 0;

    if (count != 0u &&
        (size_t)stride >
            (SIZE_MAX - base) / (size_t)count)
        return 0;

    *output =
        base + (size_t)count * (size_t)stride;
    return 1;
}

static int XzSafePathBytes(
    const unsigned char *path,
    uint32_t length)
{
    uint32_t i = 0u;
    uint32_t segment_length = 0u;

    if (!path ||
        length == 0u ||
        length > XZ_XZSC_MAX_PATH_BYTES ||
        path[0] == '/')
        return 0;

    while (i < length) {
        unsigned char c = path[i];

        if (c == '\\' || c == ':' || c == 0u)
            return 0;

        if (c == '/') {
            if (segment_length == 0u)
                return 0;

            if (segment_length == 1u &&
                path[i - 1u] == '.')
                return 0;

            if (segment_length == 2u &&
                path[i - 1u] == '.' &&
                path[i - 2u] == '.')
                return 0;

            segment_length = 0u;
            i++;
            continue;
        }

        if (!((c >= 'a' && c <= 'z') ||
              (c >= 'A' && c <= 'Z') ||
              (c >= '0' && c <= '9') ||
              c == '_' ||
              c == '-' ||
              c == '.'))
            return 0;

        segment_length++;
        i++;
    }

    if (segment_length == 0u)
        return 0;

    if (segment_length == 1u &&
        path[length - 1u] == '.')
        return 0;

    if (segment_length == 2u &&
        path[length - 1u] == '.' &&
        path[length - 2u] == '.')
        return 0;

    if (length < 4u ||
        path[length - 4u] != '.' ||
        (path[length - 3u] != 'x' &&
         path[length - 3u] != 'X') ||
        (path[length - 2u] != 'z' &&
         path[length - 2u] != 'Z') ||
        (path[length - 1u] != 'm' &&
         path[length - 1u] != 'M'))
        return 0;

    return 1;
}

int XzXzscene_ReadMeshPath(
    const XzXzsceneView *view,
    uint32_t index,
    char *output,
    size_t output_size)
{
    const unsigned char *record;
    const unsigned char *source;
    uint32_t offset;
    uint32_t length;

    if (!view ||
        !view->data ||
        !output ||
        index >= view->mesh_count)
        return 0;

    record =
        view->data +
        view->mesh_offset +
        (size_t)index * view->mesh_stride;

    offset = XzReadU32Le(record);
    length = XzReadU32Le(record + 4u);

    if ((uint64_t)offset + (uint64_t)length >
            (uint64_t)view->string_bytes ||
        (size_t)length + 1u > output_size)
        return 0;

    source =
        view->data +
        view->string_offset +
        offset;

    memcpy(output, source, length);
    output[length] = '\0';
    return 1;
}

int XzXzscene_ReadInstance(
    const XzXzsceneView *view,
    uint32_t index,
    XzXzsceneInstance *instance)
{
    const unsigned char *p;
    unsigned int i;

    if (!view ||
        !view->data ||
        !instance ||
        index >= view->instance_count)
        return 0;

    p =
        view->data +
        view->instance_offset +
        (size_t)index * view->instance_stride;

    instance->mesh_index = XzReadU32Le(p);

    for (i = 0u; i < 16u; ++i)
        instance->matrix[i] =
            XzReadF32Le(p + 4u + i * 4u);

    return 1;
}

XzXzsceneStatus XzXzscene_Parse(
    XzXzsceneView *view,
    const void *data,
    size_t size)
{
    const unsigned char *bytes =
        (const unsigned char *)data;
    uint32_t version;
    uint32_t reserved;
    uint32_t i;
    uint32_t j;
    size_t after_meshes;
    size_t after_instances;
    size_t expected_end;
    char left[XZ_XZSC_MAX_PATH_BYTES + 1u];
    char right[XZ_XZSC_MAX_PATH_BYTES + 1u];

    if (!view || !data)
        return XZ_XZSC_ERR_ARGUMENT;

    memset(view, 0, sizeof(*view));

    if (size < XZ_XZSC_HEADER_BYTES)
        return XZ_XZSC_ERR_TRUNCATED;

    if (bytes[0] != 'X' ||
        bytes[1] != 'Z' ||
        bytes[2] != 'S' ||
        bytes[3] != 'C')
        return XZ_XZSC_ERR_MAGIC;

    version = XzReadU32Le(bytes + 4u);
    if (version != XZ_XZSC_VERSION)
        return XZ_XZSC_ERR_VERSION;

    view->flags =
        XzReadU32Le(bytes + 8u);
    view->mesh_count =
        XzReadU32Le(bytes + 12u);
    view->instance_count =
        XzReadU32Le(bytes + 16u);
    view->mesh_stride =
        XzReadU32Le(bytes + 20u);
    view->instance_stride =
        XzReadU32Le(bytes + 24u);
    view->string_bytes =
        XzReadU32Le(bytes + 28u);
    view->gameplay_units_per_meter =
        XzReadF32Le(bytes + 32u);
    reserved =
        XzReadU32Le(bytes + 36u);

    if ((view->flags & ~XZ_XZSC_KNOWN_FLAGS) != 0u ||
        (view->flags & XZ_XZSC_REQUIRED_FLAGS) !=
            XZ_XZSC_REQUIRED_FLAGS)
        return XZ_XZSC_ERR_FLAGS;

    if (view->mesh_stride !=
            XZ_XZSC_MESH_RECORD_BYTES ||
        view->instance_stride !=
            XZ_XZSC_INSTANCE_BYTES)
        return XZ_XZSC_ERR_STRIDE;

    if (view->mesh_count == 0u ||
        view->mesh_count > XZ_XZSC_MAX_MESHES ||
        view->instance_count == 0u ||
        view->instance_count >
            XZ_XZSC_MAX_INSTANCES ||
        view->string_bytes == 0u)
        return XZ_XZSC_ERR_COUNT;

    if (!isfinite(
            view->gameplay_units_per_meter) ||
        view->gameplay_units_per_meter <= 0.0f ||
        view->gameplay_units_per_meter > 10000.0f)
        return XZ_XZSC_ERR_SCALE;

    if (reserved != 0u)
        return XZ_XZSC_ERR_RESERVED;

    view->data = bytes;
    view->size = size;
    view->mesh_offset =
        XZ_XZSC_HEADER_BYTES;

    if (!XzAddMulSize(
            view->mesh_offset,
            view->mesh_count,
            view->mesh_stride,
            &after_meshes))
        goto overflow;

    view->instance_offset =
        after_meshes;

    if (!XzAddMulSize(
            view->instance_offset,
            view->instance_count,
            view->instance_stride,
            &after_instances))
        goto overflow;

    view->string_offset =
        after_instances;

    if (view->string_bytes >
        SIZE_MAX - view->string_offset)
        goto overflow;

    expected_end =
        view->string_offset +
        view->string_bytes;

    if (expected_end != size) {
        memset(view, 0, sizeof(*view));
        return expected_end > size
            ? XZ_XZSC_ERR_TRUNCATED
            : XZ_XZSC_ERR_SIZE;
    }

    for (i = 0u;
         i < view->mesh_count;
         ++i) {
        const unsigned char *record =
            bytes +
            view->mesh_offset +
            (size_t)i * view->mesh_stride;
        uint32_t offset =
            XzReadU32Le(record);
        uint32_t length =
            XzReadU32Le(record + 4u);

        if ((uint64_t)offset +
                (uint64_t)length >
            (uint64_t)view->string_bytes) {
            memset(view, 0, sizeof(*view));
            return XZ_XZSC_ERR_PATH_RANGE;
        }

        if (!XzSafePathBytes(
                bytes +
                    view->string_offset +
                    offset,
                length)) {
            memset(view, 0, sizeof(*view));
            return XZ_XZSC_ERR_PATH_SYNTAX;
        }

        if (!XzXzscene_ReadMeshPath(
                view,
                i,
                left,
                sizeof(left))) {
            memset(view, 0, sizeof(*view));
            return XZ_XZSC_ERR_PATH_RANGE;
        }

        for (j = 0u; j < i; ++j) {
            if (!XzXzscene_ReadMeshPath(
                    view,
                    j,
                    right,
                    sizeof(right))) {
                memset(view, 0, sizeof(*view));
                return XZ_XZSC_ERR_PATH_RANGE;
            }

            if (strcmp(left, right) == 0) {
                memset(view, 0, sizeof(*view));
                return XZ_XZSC_ERR_DUPLICATE_PATH;
            }
        }
    }

    for (i = 0u;
         i < view->instance_count;
         ++i) {
        XzXzsceneInstance instance;
        unsigned int matrix_index;

        if (!XzXzscene_ReadInstance(
                view, i, &instance) ||
            instance.mesh_index >=
                view->mesh_count) {
            memset(view, 0, sizeof(*view));
            return XZ_XZSC_ERR_INSTANCE_MESH;
        }

        for (matrix_index = 0u;
             matrix_index < 16u;
             ++matrix_index) {
            if (!isfinite(
                    instance.matrix[
                        matrix_index])) {
                memset(view, 0, sizeof(*view));
                return XZ_XZSC_ERR_INSTANCE_MATRIX;
            }
        }

        if (fabsf(instance.matrix[12]) >
                1.0e-5f ||
            fabsf(instance.matrix[13]) >
                1.0e-5f ||
            fabsf(instance.matrix[14]) >
                1.0e-5f ||
            fabsf(
                instance.matrix[15] - 1.0f) >
                1.0e-5f) {
            memset(view, 0, sizeof(*view));
            return XZ_XZSC_ERR_INSTANCE_MATRIX;
        }
    }

    /*
     * A scene may not hide unreferenced mesh rows. This is an O(M*I)
     * validation by design: it runs only on map load, requires no temporary
     * allocation and is bounded by the explicit scene count caps.
     */
    for (i = 0u;
         i < view->mesh_count;
         ++i) {
        int found = 0;

        for (j = 0u;
             j < view->instance_count;
             ++j) {
            XzXzsceneInstance instance;

            if (!XzXzscene_ReadInstance(
                    view,
                    j,
                    &instance)) {
                memset(view, 0, sizeof(*view));
                return XZ_XZSC_ERR_INSTANCE_MATRIX;
            }

            if (instance.mesh_index == i) {
                found = 1;
                break;
            }
        }

        if (!found) {
            memset(view, 0, sizeof(*view));
            return XZ_XZSC_ERR_UNREFERENCED_MESH;
        }
    }

    return XZ_XZSC_OK;

overflow:
    memset(view, 0, sizeof(*view));
    return XZ_XZSC_ERR_OVERFLOW;
}

const char *XzXzscene_StatusName(
    XzXzsceneStatus status)
{
    switch (status) {
    case XZ_XZSC_OK:
        return "OK";
    case XZ_XZSC_ERR_ARGUMENT:
        return "ARGUMENT";
    case XZ_XZSC_ERR_TRUNCATED:
        return "TRUNCATED";
    case XZ_XZSC_ERR_MAGIC:
        return "MAGIC";
    case XZ_XZSC_ERR_VERSION:
        return "VERSION";
    case XZ_XZSC_ERR_FLAGS:
        return "FLAGS";
    case XZ_XZSC_ERR_STRIDE:
        return "STRIDE";
    case XZ_XZSC_ERR_COUNT:
        return "COUNT";
    case XZ_XZSC_ERR_SCALE:
        return "SCALE";
    case XZ_XZSC_ERR_RESERVED:
        return "RESERVED";
    case XZ_XZSC_ERR_OVERFLOW:
        return "OVERFLOW";
    case XZ_XZSC_ERR_SIZE:
        return "SIZE";
    case XZ_XZSC_ERR_PATH_RANGE:
        return "PATH_RANGE";
    case XZ_XZSC_ERR_PATH_SYNTAX:
        return "PATH_SYNTAX";
    case XZ_XZSC_ERR_DUPLICATE_PATH:
        return "DUPLICATE_PATH";
    case XZ_XZSC_ERR_INSTANCE_MESH:
        return "INSTANCE_MESH";
    case XZ_XZSC_ERR_INSTANCE_MATRIX:
        return "INSTANCE_MATRIX";
    case XZ_XZSC_ERR_UNREFERENCED_MESH:
        return "UNREFERENCED_MESH";
    default:
        return "UNKNOWN";
    }
}

static void XzWriteU32Le(
    unsigned char *p,
    uint32_t value)
{
    p[0] = (unsigned char)(
        value & 0xffu);
    p[1] = (unsigned char)(
        (value >> 8) & 0xffu);
    p[2] = (unsigned char)(
        (value >> 16) & 0xffu);
    p[3] = (unsigned char)(
        (value >> 24) & 0xffu);
}

static void XzWriteF32Le(
    unsigned char *p,
    float value)
{
    uint32_t bits;

    memcpy(&bits, &value, sizeof(bits));
    XzWriteU32Le(p, bits);
}

int XzXzscene_SelfTest(void)
{
    static const char path[] =
        "xziel/maps/test/meshes/a.xzm";

    enum {
        PATH_BYTES = sizeof(path) - 1u,
        TEST_BYTES =
            XZ_XZSC_HEADER_BYTES +
            XZ_XZSC_MESH_RECORD_BYTES +
            XZ_XZSC_INSTANCE_BYTES +
            PATH_BYTES
    };

    unsigned char data[TEST_BYTES];
    XzXzsceneView view;
    XzXzsceneInstance instance;
    char output[64];
    unsigned int i;

    memset(data, 0, sizeof(data));

    memcpy(data, "XZSC", 4u);
    XzWriteU32Le(
        data + 4u,
        XZ_XZSC_VERSION);
    XzWriteU32Le(
        data + 8u,
        XZ_XZSC_REQUIRED_FLAGS);
    XzWriteU32Le(data + 12u, 1u);
    XzWriteU32Le(data + 16u, 1u);
    XzWriteU32Le(
        data + 20u,
        XZ_XZSC_MESH_RECORD_BYTES);
    XzWriteU32Le(
        data + 24u,
        XZ_XZSC_INSTANCE_BYTES);
    XzWriteU32Le(
        data + 28u,
        PATH_BYTES);
    XzWriteF32Le(
        data + 32u,
        39.37007874f);
    XzWriteU32Le(data + 36u, 0u);

    /* mesh record */
    XzWriteU32Le(data + 40u, 0u);
    XzWriteU32Le(
        data + 44u,
        PATH_BYTES);

    /* instance record */
    XzWriteU32Le(data + 48u, 0u);
    for (i = 0u; i < 16u; ++i) {
        XzWriteF32Le(
            data + 52u + i * 4u,
            (i == 0u ||
             i == 5u ||
             i == 10u ||
             i == 15u)
                ? 1.0f
                : 0.0f);
    }

    memcpy(
        data + 116u,
        path,
        PATH_BYTES);

    if (XzXzscene_Parse(
            &view,
            data,
            sizeof(data)) != XZ_XZSC_OK)
        return 0;

    if (!XzXzscene_ReadMeshPath(
            &view,
            0u,
            output,
            sizeof(output)) ||
        strcmp(output, path) != 0)
        return 0;

    if (!XzXzscene_ReadInstance(
            &view,
            0u,
            &instance) ||
        instance.mesh_index != 0u)
        return 0;

    /* Invalid mesh index must fail closed. */
    XzWriteU32Le(data + 48u, 1u);
    if (XzXzscene_Parse(
            &view,
            data,
            sizeof(data)) !=
        XZ_XZSC_ERR_INSTANCE_MESH)
        return 0;
    XzWriteU32Le(data + 48u, 0u);

    /* Traversal syntax must fail closed. */
    memcpy(
        data + 116u,
        "../x.xzm",
        8u);
    XzWriteU32Le(data + 44u, 8u);
    XzWriteU32Le(data + 28u, 8u);

    if (XzXzscene_Parse(
            &view,
            data,
            124u) !=
        XZ_XZSC_ERR_PATH_SYNTAX)
        return 0;

    return 1;
}
