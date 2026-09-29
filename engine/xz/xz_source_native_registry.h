#ifndef XZ_SOURCE_NATIVE_REGISTRY_H
#define XZ_SOURCE_NATIVE_REGISTRY_H

#include <stddef.h>
#include <stdint.h>

#include "xz_source_adapter_registry.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum XzNativePayloadType {
    XZ_NATIVE_PAYLOAD_NONE = 0,
    XZ_NATIVE_PAYLOAD_XZMS,
    XZ_NATIVE_PAYLOAD_XZTX,
    XZ_NATIVE_PAYLOAD_XZAW,
    XZ_NATIVE_PAYLOAD_XZSK,
    XZ_NATIVE_PAYLOAD_XZAN,
    XZ_NATIVE_PAYLOAD_TYPE_COUNT
} XzNativePayloadType;

typedef struct XzSourceNativeAdapter {
    const char *source_class;
    XzSourceAssetKind source_kind;
    XzNativePayloadType native_type;
    const char *magic;
    const char *extension;
} XzSourceNativeAdapter;

const XzSourceNativeAdapter *XzSourceNativeRegistry_Find(
    const char *source_class);

const char *XzSourceNativeRegistry_TypeName(
    XzNativePayloadType type);

int XzSourceNativeRegistry_ValidatePayload(
    const XzSourceNativeAdapter *adapter,
    const void *data,
    size_t size);

int XzSourceNativeRegistry_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif
