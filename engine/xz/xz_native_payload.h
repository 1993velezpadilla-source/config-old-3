#ifndef XZ_NATIVE_PAYLOAD_H
#define XZ_NATIVE_PAYLOAD_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_NATIVE_VERSION 1u

#define XZ_XZTX_HEADER_BYTES 48u
#define XZ_XZTX_MIP_BYTES 20u

#define XZ_XZAU_HEADER_BYTES 40u

#define XZ_XZSK_HEADER_BYTES 96u
#define XZ_XZSK_BONE_BYTES 56u
#define XZ_XZSK_VERTEX_BYTES 136u
#define XZ_XZSK_SECTION_BYTES 16u
#define XZ_XZSK_MAX_UVS 8u
#define XZ_XZSK_MAX_INFLUENCES 8u

#define XZ_XZAN_HEADER_BYTES 56u
#define XZ_XZAN_TRACK_BYTES 56u

enum {
    XZ_XZTX_FLAG_SRGB = 1u << 0
};

enum {
    XZ_XZSK_FLAG_XZIEL_BASIS = 1u << 0,
    XZ_XZSK_FLAG_INDEX_U32 = 1u << 1
};

enum {
    XZ_XZAN_FLAG_XZIEL_BASIS = 1u << 0,
    XZ_XZAN_FLAG_ADDITIVE = 1u << 1
};

typedef enum XzNativePayloadStatus {
    XZ_NATIVE_OK = 0,
    XZ_NATIVE_ERR_ARGUMENT,
    XZ_NATIVE_ERR_TRUNCATED,
    XZ_NATIVE_ERR_MAGIC,
    XZ_NATIVE_ERR_VERSION,
    XZ_NATIVE_ERR_FLAGS,
    XZ_NATIVE_ERR_HEADER,
    XZ_NATIVE_ERR_COUNT,
    XZ_NATIVE_ERR_RANGE,
    XZ_NATIVE_ERR_SIZE_OVERFLOW,
    XZ_NATIVE_ERR_SIZE_MISMATCH,
    XZ_NATIVE_ERR_NONFINITE,
    XZ_NATIVE_ERR_HIERARCHY,
    XZ_NATIVE_ERR_INDEX_RANGE,
    XZ_NATIVE_ERR_WEIGHT_RANGE,
    XZ_NATIVE_ERR_NAME_RANGE,
    XZ_NATIVE_ERR_TIME_RANGE
} XzNativePayloadStatus;

typedef struct XzNativeTextureMip {
    uint32_t payload_offset;
    uint32_t bytes;
    uint32_t width;
    uint32_t height;
    uint32_t depth;
} XzNativeTextureMip;

typedef struct XzNativeTextureView {
    const unsigned char *data;
    size_t size;
    uint32_t flags;
    uint32_t width;
    uint32_t height;
    uint32_t mip_count;
    uint32_t payload_offset;
    uint32_t payload_bytes;
    uint64_t format_tag;
} XzNativeTextureView;

typedef struct XzNativeAudioView {
    const unsigned char *data;
    size_t size;
    uint32_t flags;
    uint32_t channels;
    uint32_t sample_rate;
    float duration_seconds;
    uint64_t codec_tag;
    uint32_t payload_offset;
    uint32_t payload_bytes;
} XzNativeAudioView;

typedef struct XzNativeSkinnedMeshView {
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
} XzNativeSkinnedMeshView;

typedef struct XzNativeAnimationView {
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
} XzNativeAnimationView;

XzNativePayloadStatus XzNativeTexture_Parse(
    XzNativeTextureView *view,
    const void *data,
    size_t size);

int XzNativeTexture_Mip(
    const XzNativeTextureView *view,
    uint32_t mip_index,
    XzNativeTextureMip *mip);

XzNativePayloadStatus XzNativeAudio_Parse(
    XzNativeAudioView *view,
    const void *data,
    size_t size);

XzNativePayloadStatus XzNativeSkinnedMesh_Parse(
    XzNativeSkinnedMeshView *view,
    const void *data,
    size_t size);

XzNativePayloadStatus XzNativeAnimation_Parse(
    XzNativeAnimationView *view,
    const void *data,
    size_t size);

const char *XzNativePayload_StatusName(
    XzNativePayloadStatus status);

int XzNativePayload_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif
