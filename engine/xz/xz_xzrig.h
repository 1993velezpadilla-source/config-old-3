#ifndef XZ_XZRIG_H
#define XZ_XZRIG_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_XZRG_VERSION 1u
#define XZ_XZRG_HEADER_BYTES 48u
#define XZ_XZRG_BONE_BYTES 56u

enum {
    XZ_XZRG_FLAG_XZIEL_BASIS = 1u << 0
};

typedef enum XzXzrigStatus {
    XZ_XZRG_OK = 0,
    XZ_XZRG_ERR_ARGUMENT,
    XZ_XZRG_ERR_TRUNCATED,
    XZ_XZRG_ERR_MAGIC,
    XZ_XZRG_ERR_VERSION,
    XZ_XZRG_ERR_FLAGS,
    XZ_XZRG_ERR_HEADER,
    XZ_XZRG_ERR_COUNT,
    XZ_XZRG_ERR_SIZE_OVERFLOW,
    XZ_XZRG_ERR_SIZE_MISMATCH,
    XZ_XZRG_ERR_NONFINITE,
    XZ_XZRG_ERR_HIERARCHY,
    XZ_XZRG_ERR_NAME_RANGE
} XzXzrigStatus;

typedef struct XzXzrigView {
    const unsigned char *data;
    size_t size;
    uint32_t flags;
    uint32_t bone_count;
    uint32_t bone_offset;
    uint32_t string_offset;
    uint32_t string_bytes;
    uint64_t skeleton_hash;
    uint64_t pose_hash;
} XzXzrigView;

XzXzrigStatus XzXzrig_Parse(
    XzXzrigView *view,
    const void *data,
    size_t size);

const char *XzXzrig_StatusName(
    XzXzrigStatus status);

int XzXzrig_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif
