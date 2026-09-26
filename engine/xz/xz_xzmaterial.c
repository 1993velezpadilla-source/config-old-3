#include "xz_xzmaterial.h"

#include <string.h>

#define XZ_XZMT_KNOWN_FLAGS \
    (XZ_XZMT_ROLE_BASE_COLOR | \
     XZ_XZMT_ROLE_NORMAL | \
     XZ_XZMT_ROLE_SPECULAR | \
     XZ_XZMT_ROLE_BLEND)

static uint32_t XzMaterialReadU32Le(
    const unsigned char *p)
{
    return ((uint32_t)p[0]) |
           ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

static void XzMaterialWriteU32Le(
    unsigned char *p,
    uint32_t value)
{
    p[0] = (unsigned char)(value & 0xffu);
    p[1] = (unsigned char)((value >> 8) & 0xffu);
    p[2] = (unsigned char)((value >> 16) & 0xffu);
    p[3] = (unsigned char)((value >> 24) & 0xffu);
}

static int XzMaterialTextureValid(
    uint32_t value,
    uint32_t texture_count)
{
    return value == XZ_XZMT_NO_TEXTURE ||
           value < texture_count;
}

int XzXzmaterial_ReadMeshSpan(
    const XzXzmaterialView *view,
    uint32_t mesh_index,
    XzXzmaterialMeshSpan *span)
{
    const unsigned char *p;

    if (!view || !view->data || !span ||
        mesh_index >= view->mesh_count)
        return 0;

    p = view->data +
        view->mesh_span_offset +
        (size_t)mesh_index *
            XZ_XZMT_MESH_SPAN_BYTES;

    span->first_binding =
        XzMaterialReadU32Le(p + 0u);
    span->binding_count =
        XzMaterialReadU32Le(p + 4u);
    return 1;
}

int XzXzmaterial_ReadBinding(
    const XzXzmaterialView *view,
    uint32_t binding_index,
    XzXzmaterialBinding *binding)
{
    const unsigned char *p;

    if (!view || !view->data || !binding ||
        binding_index >= view->binding_count)
        return 0;

    p = view->data +
        view->binding_offset +
        (size_t)binding_index *
            view->binding_stride;

    binding->base_color_texture =
        XzMaterialReadU32Le(p + 0u);
    binding->normal_texture =
        XzMaterialReadU32Le(p + 4u);
    binding->specular_texture =
        XzMaterialReadU32Le(p + 8u);
    binding->blend_texture =
        XzMaterialReadU32Le(p + 12u);
    binding->flags =
        XzMaterialReadU32Le(p + 16u);
    return 1;
}

XzXzmaterialStatus XzXzmaterial_Parse(
    XzXzmaterialView *view,
    const void *data,
    size_t size)
{
    const unsigned char *bytes =
        (const unsigned char *)data;
    uint64_t span_bytes;
    uint64_t binding_bytes;
    uint64_t expected_size;
    uint32_t version;
    uint32_t mesh_index;
    uint32_t binding_index;
    uint32_t expected_first = 0u;

    if (!view || !data)
        return XZ_XZMT_ERR_ARGUMENT;

    memset(view, 0, sizeof(*view));

    if (size < XZ_XZMT_HEADER_BYTES)
        return XZ_XZMT_ERR_TRUNCATED;

    if (bytes[0] != 'X' ||
        bytes[1] != 'Z' ||
        bytes[2] != 'M' ||
        bytes[3] != 'T')
        return XZ_XZMT_ERR_MAGIC;

    version =
        XzMaterialReadU32Le(bytes + 4u);
    if (version != XZ_XZMT_VERSION)
        return XZ_XZMT_ERR_VERSION;

    view->mesh_count =
        XzMaterialReadU32Le(bytes + 8u);
    view->binding_count =
        XzMaterialReadU32Le(bytes + 12u);
    view->texture_count =
        XzMaterialReadU32Le(bytes + 16u);
    view->binding_stride =
        XzMaterialReadU32Le(bytes + 20u);

    if (view->mesh_count == 0u ||
        view->binding_count == 0u)
        goto count_fail;

    if (view->binding_stride !=
            XZ_XZMT_BINDING_BYTES)
        goto stride_fail;

    span_bytes =
        (uint64_t)view->mesh_count *
        XZ_XZMT_MESH_SPAN_BYTES;
    binding_bytes =
        (uint64_t)view->binding_count *
        view->binding_stride;

    expected_size =
        (uint64_t)XZ_XZMT_HEADER_BYTES +
        span_bytes +
        binding_bytes;

    if (expected_size >
        (uint64_t)SIZE_MAX)
        goto overflow_fail;

    if ((uint64_t)size != expected_size) {
        memset(view, 0, sizeof(*view));
        return (uint64_t)size < expected_size
            ? XZ_XZMT_ERR_TRUNCATED
            : XZ_XZMT_ERR_SIZE_MISMATCH;
    }

    view->data = bytes;
    view->size = size;
    view->mesh_span_offset =
        XZ_XZMT_HEADER_BYTES;
    view->binding_offset =
        view->mesh_span_offset +
        (size_t)span_bytes;

    for (mesh_index = 0u;
         mesh_index < view->mesh_count;
         ++mesh_index) {
        XzXzmaterialMeshSpan span;
        uint64_t end;

        if (!XzXzmaterial_ReadMeshSpan(
                view, mesh_index, &span))
            goto span_fail;

        end =
            (uint64_t)span.first_binding +
            (uint64_t)span.binding_count;

        if (span.binding_count == 0u ||
            span.first_binding != expected_first ||
            end > view->binding_count)
            goto span_fail;

        expected_first =
            (uint32_t)end;
    }

    if (expected_first != view->binding_count)
        goto span_fail;

    for (binding_index = 0u;
         binding_index < view->binding_count;
         ++binding_index) {
        XzXzmaterialBinding binding;
        uint32_t expected_flags = 0u;

        if (!XzXzmaterial_ReadBinding(
                view,
                binding_index,
                &binding))
            goto span_fail;

        if (!XzMaterialTextureValid(
                binding.base_color_texture,
                view->texture_count) ||
            !XzMaterialTextureValid(
                binding.normal_texture,
                view->texture_count) ||
            !XzMaterialTextureValid(
                binding.specular_texture,
                view->texture_count) ||
            !XzMaterialTextureValid(
                binding.blend_texture,
                view->texture_count))
            goto texture_fail;

        if (binding.base_color_texture !=
                XZ_XZMT_NO_TEXTURE)
            expected_flags |=
                XZ_XZMT_ROLE_BASE_COLOR;
        if (binding.normal_texture !=
                XZ_XZMT_NO_TEXTURE)
            expected_flags |=
                XZ_XZMT_ROLE_NORMAL;
        if (binding.specular_texture !=
                XZ_XZMT_NO_TEXTURE)
            expected_flags |=
                XZ_XZMT_ROLE_SPECULAR;
        if (binding.blend_texture !=
                XZ_XZMT_NO_TEXTURE)
            expected_flags |=
                XZ_XZMT_ROLE_BLEND;

        if ((binding.flags &
                ~XZ_XZMT_KNOWN_FLAGS) != 0u ||
            binding.flags != expected_flags)
            goto flags_fail;
    }

    return XZ_XZMT_OK;

count_fail:
    memset(view, 0, sizeof(*view));
    return XZ_XZMT_ERR_COUNT;

stride_fail:
    memset(view, 0, sizeof(*view));
    return XZ_XZMT_ERR_STRIDE;

overflow_fail:
    memset(view, 0, sizeof(*view));
    return XZ_XZMT_ERR_SIZE_OVERFLOW;

span_fail:
    memset(view, 0, sizeof(*view));
    return XZ_XZMT_ERR_MESH_SPAN;

texture_fail:
    memset(view, 0, sizeof(*view));
    return XZ_XZMT_ERR_TEXTURE_INDEX;

flags_fail:
    memset(view, 0, sizeof(*view));
    return XZ_XZMT_ERR_FLAGS;
}

const char *XzXzmaterial_StatusName(
    XzXzmaterialStatus status)
{
    switch (status) {
    case XZ_XZMT_OK: return "OK";
    case XZ_XZMT_ERR_ARGUMENT: return "ARGUMENT";
    case XZ_XZMT_ERR_TRUNCATED: return "TRUNCATED";
    case XZ_XZMT_ERR_MAGIC: return "MAGIC";
    case XZ_XZMT_ERR_VERSION: return "VERSION";
    case XZ_XZMT_ERR_COUNT: return "COUNT";
    case XZ_XZMT_ERR_STRIDE: return "STRIDE";
    case XZ_XZMT_ERR_SIZE_OVERFLOW: return "SIZE_OVERFLOW";
    case XZ_XZMT_ERR_SIZE_MISMATCH: return "SIZE_MISMATCH";
    case XZ_XZMT_ERR_MESH_SPAN: return "MESH_SPAN";
    case XZ_XZMT_ERR_TEXTURE_INDEX: return "TEXTURE_INDEX";
    case XZ_XZMT_ERR_FLAGS: return "FLAGS";
    default: return "UNKNOWN";
    }
}

int XzXzmaterial_SelfTest(void)
{
    unsigned char data[
        XZ_XZMT_HEADER_BYTES +
        XZ_XZMT_MESH_SPAN_BYTES +
        XZ_XZMT_BINDING_BYTES];
    XzXzmaterialView view;
    XzXzmaterialMeshSpan span;
    XzXzmaterialBinding binding;
    size_t bind_at =
        XZ_XZMT_HEADER_BYTES +
        XZ_XZMT_MESH_SPAN_BYTES;

    memset(data, 0, sizeof(data));
    data[0] = 'X';
    data[1] = 'Z';
    data[2] = 'M';
    data[3] = 'T';

    XzMaterialWriteU32Le(
        data + 4u,
        XZ_XZMT_VERSION);
    XzMaterialWriteU32Le(
        data + 8u, 1u);
    XzMaterialWriteU32Le(
        data + 12u, 1u);
    XzMaterialWriteU32Le(
        data + 16u, 2u);
    XzMaterialWriteU32Le(
        data + 20u,
        XZ_XZMT_BINDING_BYTES);

    XzMaterialWriteU32Le(
        data + XZ_XZMT_HEADER_BYTES,
        0u);
    XzMaterialWriteU32Le(
        data + XZ_XZMT_HEADER_BYTES + 4u,
        1u);

    XzMaterialWriteU32Le(
        data + bind_at + 0u,
        1u);
    XzMaterialWriteU32Le(
        data + bind_at + 4u,
        XZ_XZMT_NO_TEXTURE);
    XzMaterialWriteU32Le(
        data + bind_at + 8u,
        XZ_XZMT_NO_TEXTURE);
    XzMaterialWriteU32Le(
        data + bind_at + 12u,
        XZ_XZMT_NO_TEXTURE);
    XzMaterialWriteU32Le(
        data + bind_at + 16u,
        XZ_XZMT_ROLE_BASE_COLOR);

    if (XzXzmaterial_Parse(
            &view,
            data,
            sizeof(data)) != XZ_XZMT_OK)
        return 0;

    if (!XzXzmaterial_ReadMeshSpan(
            &view, 0u, &span) ||
        span.first_binding != 0u ||
        span.binding_count != 1u)
        return 0;

    if (!XzXzmaterial_ReadBinding(
            &view, 0u, &binding) ||
        binding.base_color_texture != 1u ||
        binding.flags !=
            XZ_XZMT_ROLE_BASE_COLOR)
        return 0;

    XzMaterialWriteU32Le(
        data + bind_at + 0u,
        2u);
    if (XzXzmaterial_Parse(
            &view,
            data,
            sizeof(data)) !=
            XZ_XZMT_ERR_TEXTURE_INDEX)
        return 0;

    return 1;
}
