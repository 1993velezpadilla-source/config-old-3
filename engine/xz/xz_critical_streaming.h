#ifndef XZ_CRITICAL_STREAMING_H
#define XZ_CRITICAL_STREAMING_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_CRITICAL_STREAM_INITIAL_ENTRIES 1024u
#define XZ_CRITICAL_STREAM_INITIAL_BUCKETS 2048u

typedef struct XzCriticalStreamAsset {
    uint64_t content_key;
    uint32_t asset_type;
    uint32_t next_hash;
    uint8_t native_ready;
    uint8_t resident;
    uint8_t failed;
} XzCriticalStreamAsset;

typedef struct XzCriticalStreamingState {
    XzCriticalStreamAsset *assets;
    uint32_t *buckets;
    uint32_t asset_count;
    uint32_t asset_capacity;
    uint32_t bucket_count;
    uint32_t native_ready_count;
    uint32_t resident_count;
    uint32_t failed_count;
    uint32_t generation;
    int ready;
} XzCriticalStreamingState;

void XzCriticalStreaming_Init(
    XzCriticalStreamingState *state);

void XzCriticalStreaming_Destroy(
    XzCriticalStreamingState *state);

void XzCriticalStreaming_NewGeneration(
    XzCriticalStreamingState *state);

int XzCriticalStreaming_Require(
    XzCriticalStreamingState *state,
    uint64_t content_key,
    uint32_t asset_type,
    uint32_t *out_index);

int XzCriticalStreaming_SetNativeReady(
    XzCriticalStreamingState *state,
    uint64_t content_key,
    uint32_t asset_type,
    int ready);

int XzCriticalStreaming_SetResident(
    XzCriticalStreamingState *state,
    uint64_t content_key,
    uint32_t asset_type,
    int resident);

int XzCriticalStreaming_SetFailed(
    XzCriticalStreamingState *state,
    uint64_t content_key,
    uint32_t asset_type,
    int failed);

int XzCriticalStreaming_IsReady(
    const XzCriticalStreamingState *state);

int XzCriticalStreaming_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif
