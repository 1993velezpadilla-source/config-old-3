#ifndef XZ_XZAUDIO_H
#define XZ_XZAUDIO_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_XZAW_VERSION 1u
#define XZ_XZAW_HEADER_BYTES 96u
#define XZ_XZAW_FORMAT_NAME_BYTES 64u

enum {
    XZ_XZAW_FLAG_SOURCE_STREAMING = 1u << 0
};

typedef enum XzXzaudioStatus {
    XZ_XZAW_OK = 0,
    XZ_XZAW_ERR_ARGUMENT,
    XZ_XZAW_ERR_TRUNCATED,
    XZ_XZAW_ERR_MAGIC,
    XZ_XZAW_ERR_VERSION,
    XZ_XZAW_ERR_FLAGS,
    XZ_XZAW_ERR_HEADER,
    XZ_XZAW_ERR_FORMAT,
    XZ_XZAW_ERR_RANGE,
    XZ_XZAW_ERR_SIZE_MISMATCH
} XzXzaudioStatus;

typedef struct XzXzaudioView {
    const unsigned char *data;
    size_t size;

    uint32_t version;
    uint32_t flags;
    uint32_t format_name_bytes;
    uint32_t header_bytes;
    uint32_t payload_offset;
    uint32_t payload_bytes;

    char format_name[XZ_XZAW_FORMAT_NAME_BYTES];
} XzXzaudioView;

XzXzaudioStatus XzXzaudio_Parse(
    XzXzaudioView *view,
    const void *data,
    size_t size);

const void *XzXzaudio_Payload(
    const XzXzaudioView *view,
    size_t *out_bytes);

const char *XzXzaudio_StatusName(
    XzXzaudioStatus status);

int XzXzaudio_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif
