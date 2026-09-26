#ifndef XZ_XZMATERIAL_H
#define XZ_XZMATERIAL_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_XZMT_VERSION 1u
#define XZ_XZMT_HEADER_BYTES 24u
#define XZ_XZMT_MESH_SPAN_BYTES 8u
#define XZ_XZMT_BINDING_BYTES 20u
#define XZ_XZMT_NO_TEXTURE 0xffffffffu

enum {
    XZ_XZMT_ROLE_BASE_COLOR = 1u << 0,
    XZ_XZMT_ROLE_NORMAL     = 1u << 1,
    XZ_XZMT_ROLE_SPECULAR   = 1u << 2,
    XZ_XZMT_ROLE_BLEND      = 1u << 3
};

typedef enum {
    XZ_XZMT_OK = 0,
    XZ_XZMT_ERR_ARGUMENT,
    XZ_XZMT_ERR_TRUNCATED,
    XZ_XZMT_ERR_MAGIC,
    XZ_XZMT_ERR_VERSION,
    XZ_XZMT_ERR_COUNT,
    XZ_XZMT_ERR_STRIDE,
    XZ_XZMT_ERR_SIZE_OVERFLOW,
    XZ_XZMT_ERR_SIZE_MISMATCH,
    XZ_XZMT_ERR_MESH_SPAN,
    XZ_XZMT_ERR_TEXTURE_INDEX,
    XZ_XZMT_ERR_FLAGS
} XzXzmaterialStatus;

typedef struct {
    uint32_t first_binding;
    uint32_t binding_count;
} XzXzmaterialMeshSpan;

typedef struct {
    uint32_t base_color_texture;
    uint32_t normal_texture;
    uint32_t specular_texture;
    uint32_t blend_texture;
    uint32_t flags;
} XzXzmaterialBinding;

typedef struct {
    const unsigned char *data;
    size_t size;

    uint32_t mesh_count;
    uint32_t binding_count;
    uint32_t texture_count;
    uint32_t binding_stride;

    size_t mesh_span_offset;
    size_t binding_offset;
} XzXzmaterialView;

XzXzmaterialStatus XzXzmaterial_Parse(
    XzXzmaterialView *view,
    const void *data,
    size_t size);

int XzXzmaterial_ReadMeshSpan(
    const XzXzmaterialView *view,
    uint32_t mesh_index,
    XzXzmaterialMeshSpan *span);

int XzXzmaterial_ReadBinding(
    const XzXzmaterialView *view,
    uint32_t binding_index,
    XzXzmaterialBinding *binding);

const char *XzXzmaterial_StatusName(
    XzXzmaterialStatus status);

int XzXzmaterial_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif
