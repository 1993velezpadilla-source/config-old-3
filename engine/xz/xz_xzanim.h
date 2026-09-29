#ifndef XZ_XZANIM_H
#define XZ_XZANIM_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_XZAN_VERSION 1u
#define XZ_XZAN_HEADER_BYTES 56u
#define XZ_XZAN_TRACK_BYTES 56u

enum {
    XZ_XZAN_FLAG_XZIEL_BASIS = 1u << 0,
    XZ_XZAN_FLAG_ADDITIVE = 1u << 1
};

typedef enum XzXzanimStatus {
    XZ_XZAN_OK = 0,
    XZ_XZAN_ERR_ARGUMENT,
    XZ_XZAN_ERR_TRUNCATED,
    XZ_XZAN_ERR_MAGIC,
    XZ_XZAN_ERR_VERSION,
    XZ_XZAN_ERR_FLAGS,
    XZ_XZAN_ERR_HEADER,
    XZ_XZAN_ERR_COUNT,
    XZ_XZAN_ERR_RANGE,
    XZ_XZAN_ERR_SIZE_OVERFLOW,
    XZ_XZAN_ERR_SIZE_MISMATCH,
    XZ_XZAN_ERR_NONFINITE,
    XZ_XZAN_ERR_TIME_RANGE
} XzXzanimStatus;

typedef struct XzXzanimView {
    const unsigned char *data;
    size_t size;
    uint32_t flags;
    uint32_t frame_count;
    float frames_per_second;
    float duration_seconds;
    uint32_t track_count;
    uint32_t track_offset;
    uint32_t payload_offset;
    uint32_t payload_bytes;
    uint64_t skeleton_hash;
} XzXzanimView;

XzXzanimStatus XzXzanim_Parse(
    XzXzanimView *view,
    const void *data,
    size_t size);

const char *XzXzanim_StatusName(
    XzXzanimStatus status);

int XzXzanim_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif
