#ifndef XZ_XZSCENE_H
#define XZ_XZSCENE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_XZSC_VERSION 1u
#define XZ_XZSC_HEADER_BYTES 40u
#define XZ_XZSC_MESH_RECORD_BYTES 8u
#define XZ_XZSC_INSTANCE_BYTES 68u
#define XZ_XZSC_MAX_PATH_BYTES 255u

enum {
    XZ_XZSC_FLAG_XZIEL_Z_UP =
        1u << 0,
    XZ_XZSC_FLAG_METERS =
        1u << 1,
    XZ_XZSC_FLAG_ROW_MAJOR_COLUMN_VECTOR =
        1u << 2,
    XZ_XZSC_FLAG_XZMS_MESHES =
        1u << 3
};

typedef enum {
    XZ_XZSC_OK = 0,
    XZ_XZSC_ERR_ARGUMENT,
    XZ_XZSC_ERR_TRUNCATED,
    XZ_XZSC_ERR_MAGIC,
    XZ_XZSC_ERR_VERSION,
    XZ_XZSC_ERR_FLAGS,
    XZ_XZSC_ERR_STRIDE,
    XZ_XZSC_ERR_COUNT,
    XZ_XZSC_ERR_SCALE,
    XZ_XZSC_ERR_RESERVED,
    XZ_XZSC_ERR_OVERFLOW,
    XZ_XZSC_ERR_SIZE,
    XZ_XZSC_ERR_PATH_RANGE,
    XZ_XZSC_ERR_PATH_SYNTAX,
    XZ_XZSC_ERR_DUPLICATE_PATH,
    XZ_XZSC_ERR_INSTANCE_MESH,
    XZ_XZSC_ERR_INSTANCE_MATRIX,
    XZ_XZSC_ERR_UNREFERENCED_MESH
} XzXzsceneStatus;

typedef struct {
    const unsigned char *data;
    size_t size;

    uint32_t mesh_count;
    uint32_t instance_count;
    uint32_t flags;
    uint32_t mesh_stride;
    uint32_t instance_stride;
    uint32_t string_bytes;
    float gameplay_units_per_meter;

    size_t mesh_offset;
    size_t instance_offset;
    size_t string_offset;
} XzXzsceneView;

typedef struct {
    uint32_t mesh_index;
    float matrix[16];
} XzXzsceneInstance;

XzXzsceneStatus XzXzscene_Parse(
    XzXzsceneView *view,
    const void *data,
    size_t size);

int XzXzscene_ReadMeshPath(
    const XzXzsceneView *view,
    uint32_t index,
    char *output,
    size_t output_size);

int XzXzscene_ReadInstance(
    const XzXzsceneView *view,
    uint32_t index,
    XzXzsceneInstance *instance);

const char *XzXzscene_StatusName(
    XzXzsceneStatus status);

int XzXzscene_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif
