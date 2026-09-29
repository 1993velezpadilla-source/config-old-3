#ifndef XZ_MATERIAL_INSTANCE_BINDING_H
#define XZ_MATERIAL_INSTANCE_BINDING_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_XZMI_VERSION 1u
#define XZ_XZMI_HEADER_BYTES 48u
#define XZ_XZMI_INSTANCE_RECORD_BYTES 8u
#define XZ_XZMI_BINDING_RECORD_BYTES 4u
#define XZ_XZMI_NO_MATERIAL 0xffffffffu

typedef enum {
    XZ_XZMI_OK = 0,
    XZ_XZMI_NULL,
    XZ_XZMI_BAD_SIZE,
    XZ_XZMI_BAD_MAGIC,
    XZ_XZMI_BAD_VERSION,
    XZ_XZMI_BAD_HEADER,
    XZ_XZMI_BAD_RANGE,
    XZ_XZMI_BAD_MATERIAL_INDEX,
    XZ_XZMI_BAD_INSTANCE_INDEX,
    XZ_XZMI_BAD_SUBMESH_INDEX
} XzMaterialInstanceBindingStatus;

typedef struct {
    const unsigned char *data;
    size_t bytes;
    uint32_t instance_count;
    uint32_t material_count;
    uint32_t binding_count;
    uint32_t instance_table_offset;
    uint32_t binding_table_offset;
} XzMaterialInstanceBindingView;

typedef struct {
    uint32_t first_binding;
    uint32_t binding_count;
} XzMaterialInstanceRecord;

XzMaterialInstanceBindingStatus
XzMaterialInstanceBinding_Parse(
    XzMaterialInstanceBindingView *view,
    const unsigned char *data,
    size_t bytes);

XzMaterialInstanceBindingStatus
XzMaterialInstanceBinding_Instance(
    const XzMaterialInstanceBindingView *view,
    uint32_t instance_index,
    XzMaterialInstanceRecord *record);

XzMaterialInstanceBindingStatus
XzMaterialInstanceBinding_Material(
    const XzMaterialInstanceBindingView *view,
    uint32_t instance_index,
    uint32_t submesh_index,
    uint32_t *material_index);

const char *XzMaterialInstanceBinding_StatusName(
    XzMaterialInstanceBindingStatus status);

int XzMaterialInstanceBinding_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif
