#ifndef XZ_XZMESH_H
#define XZ_XZMESH_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_XZMS_VERSION_V1 1u
#define XZ_XZMS_VERSION 2u
#define XZ_XZMS_HEADER_BYTES 56u
#define XZ_XZMS_VERTEX_BYTES_V1 32u
#define XZ_XZMS_VERTEX_BYTES_V2 56u
#define XZ_XZMS_VERTEX_BYTES XZ_XZMS_VERTEX_BYTES_V2
#define XZ_XZMS_SUBMESH_BYTES 16u
#define XZ_XZMS_NO_MATERIAL 0xffffffffu

enum {
    XZ_XZMS_FLAG_GLTF_TO_XZIEL = 1u << 0,
    XZ_XZMS_FLAG_INDEX_U32     = 1u << 1
};

enum {
    XZ_XZMS_ATTR_POSITION = 1u << 0,
    XZ_XZMS_ATTR_NORMAL   = 1u << 1,
    XZ_XZMS_ATTR_UV0      = 1u << 2,
    XZ_XZMS_ATTR_UV1      = 1u << 3,
    XZ_XZMS_ATTR_UV2      = 1u << 4,
    XZ_XZMS_ATTR_UV3      = 1u << 5
};

typedef enum {
    XZ_XZMS_OK = 0,
    XZ_XZMS_ERR_ARGUMENT,
    XZ_XZMS_ERR_TRUNCATED,
    XZ_XZMS_ERR_MAGIC,
    XZ_XZMS_ERR_VERSION,
    XZ_XZMS_ERR_FLAGS,
    XZ_XZMS_ERR_STRIDE,
    XZ_XZMS_ERR_COUNT,
    XZ_XZMS_ERR_SIZE_OVERFLOW,
    XZ_XZMS_ERR_SIZE_MISMATCH,
    XZ_XZMS_ERR_NONFINITE,
    XZ_XZMS_ERR_BOUNDS,
    XZ_XZMS_ERR_INDEX_RANGE,
    XZ_XZMS_ERR_SUBMESH_RANGE,
    XZ_XZMS_ERR_SUBMESH_ATTRIBUTES
} XzXzmeshStatus;

typedef struct {
    float position[3];
    float normal[3];
    float uv[2];
    float uv1[2];
    float uv2[2];
    float uv3[2];
} XzXzmeshVertex;

typedef struct {
    uint32_t first_index;
    uint32_t index_count;
    uint32_t material_index;
    uint32_t attribute_flags;
} XzXzmeshSubmesh;

typedef struct {
    const unsigned char *data;
    size_t size;

    uint32_t version;
    uint32_t vertex_count;
    uint32_t index_count;
    uint32_t submesh_count;
    uint32_t flags;
    uint32_t vertex_stride;
    uint32_t submesh_stride;

    size_t vertex_offset;
    size_t index_offset;
    size_t submesh_offset;

    float bounds_min[3];
    float bounds_max[3];
} XzXzmeshView;

XzXzmeshStatus XzXzmesh_Parse(
    XzXzmeshView *view,
    const void *data,
    size_t size);

int XzXzmesh_ReadVertex(
    const XzXzmeshView *view,
    uint32_t index,
    XzXzmeshVertex *vertex);

int XzXzmesh_ReadIndex(
    const XzXzmeshView *view,
    uint32_t index,
    uint32_t *value);

int XzXzmesh_ReadSubmesh(
    const XzXzmeshView *view,
    uint32_t index,
    XzXzmeshSubmesh *submesh);

const char *XzXzmesh_StatusName(
    XzXzmeshStatus status);

int XzXzmesh_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif
