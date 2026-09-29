#ifndef XZ_XZSKEL_H
#define XZ_XZSKEL_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_XZSK_VERSION 2u
#define XZ_XZSK_HEADER_BYTES 112u
#define XZ_XZSK_BONE_BYTES 56u
#define XZ_XZSK_VERTEX_BYTES 136u
#define XZ_XZSK_SECTION_BYTES 16u
#define XZ_XZSK_MAX_UVS 8u
#define XZ_XZSK_MAX_INFLUENCES 8u

enum {
    XZ_XZSK_FLAG_XZIEL_BASIS = 1u << 0,
    XZ_XZSK_FLAG_INDEX_U32 = 1u << 1,
    XZ_XZSK_FLAG_SKELETON_REMAP = 1u << 2
};

typedef enum XzXzskelStatus {
    XZ_XZSK_OK = 0,
    XZ_XZSK_ERR_ARGUMENT,
    XZ_XZSK_ERR_TRUNCATED,
    XZ_XZSK_ERR_MAGIC,
    XZ_XZSK_ERR_VERSION,
    XZ_XZSK_ERR_FLAGS,
    XZ_XZSK_ERR_HEADER,
    XZ_XZSK_ERR_COUNT,
    XZ_XZSK_ERR_RANGE,
    XZ_XZSK_ERR_SIZE_OVERFLOW,
    XZ_XZSK_ERR_SIZE_MISMATCH,
    XZ_XZSK_ERR_NONFINITE,
    XZ_XZSK_ERR_HIERARCHY,
    XZ_XZSK_ERR_INDEX_RANGE,
    XZ_XZSK_ERR_WEIGHT_RANGE,
    XZ_XZSK_ERR_NAME_RANGE
} XzXzskelStatus;

typedef struct XzXzskelView {
    const unsigned char *data;
    size_t size;
    uint32_t flags;
    uint32_t bone_count;
    uint32_t vertex_count;
    uint32_t index_count;
    uint32_t section_count;
    uint32_t bone_offset;
    uint32_t vertex_offset;
    uint32_t index_offset;
    uint32_t section_offset;
    uint32_t string_offset;
    uint32_t string_bytes;
    uint64_t skeleton_hash;
    float bounds_min[3];
    float bounds_max[3];
    uint32_t skeleton_bone_count;
    uint64_t mesh_layout_hash;
} XzXzskelView;

XzXzskelStatus XzXzskel_Parse(
    XzXzskelView *view,
    const void *data,
    size_t size);

const char *XzXzskel_StatusName(
    XzXzskelStatus status);

int XzXzskel_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif
