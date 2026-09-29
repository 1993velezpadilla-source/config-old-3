#include "xz_material_instance_binding.h"

#include <stdlib.h>
#include <string.h>

static uint32_t XzMiReadU32Le(
    const unsigned char *p)
{
    return ((uint32_t)p[0]) |
           ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

static void XzMiWriteU32Le(
    unsigned char *p,
    uint32_t value)
{
    p[0] = (unsigned char)(value & 0xffu);
    p[1] = (unsigned char)((value >> 8) & 0xffu);
    p[2] = (unsigned char)((value >> 16) & 0xffu);
    p[3] = (unsigned char)((value >> 24) & 0xffu);
}

XzMaterialInstanceBindingStatus
XzMaterialInstanceBinding_Instance(
    const XzMaterialInstanceBindingView *view,
    uint32_t instance_index,
    XzMaterialInstanceRecord *record)
{
    const unsigned char *p;
    uint64_t at;

    if (!view || !view->data || !record)
        return XZ_XZMI_NULL;

    if (instance_index >= view->instance_count)
        return XZ_XZMI_BAD_INSTANCE_INDEX;

    at =
        (uint64_t)view->instance_table_offset +
        (uint64_t)instance_index *
            XZ_XZMI_INSTANCE_RECORD_BYTES;

    if (at + XZ_XZMI_INSTANCE_RECORD_BYTES >
            (uint64_t)view->bytes)
        return XZ_XZMI_BAD_RANGE;

    p = view->data + (size_t)at;
    record->first_binding =
        XzMiReadU32Le(p + 0u);
    record->binding_count =
        XzMiReadU32Le(p + 4u);

    if ((uint64_t)record->first_binding +
            (uint64_t)record->binding_count >
        (uint64_t)view->binding_count)
        return XZ_XZMI_BAD_RANGE;

    return XZ_XZMI_OK;
}

XzMaterialInstanceBindingStatus
XzMaterialInstanceBinding_Material(
    const XzMaterialInstanceBindingView *view,
    uint32_t instance_index,
    uint32_t submesh_index,
    uint32_t *material_index)
{
    XzMaterialInstanceRecord record;
    XzMaterialInstanceBindingStatus status;
    const unsigned char *p;
    uint64_t binding_index;
    uint64_t at;
    uint32_t material;

    if (!material_index)
        return XZ_XZMI_NULL;

    status =
        XzMaterialInstanceBinding_Instance(
            view,
            instance_index,
            &record);
    if (status != XZ_XZMI_OK)
        return status;

    if (submesh_index >= record.binding_count)
        return XZ_XZMI_BAD_SUBMESH_INDEX;

    binding_index =
        (uint64_t)record.first_binding +
        (uint64_t)submesh_index;

    at =
        (uint64_t)view->binding_table_offset +
        binding_index *
            XZ_XZMI_BINDING_RECORD_BYTES;

    if (at + XZ_XZMI_BINDING_RECORD_BYTES >
            (uint64_t)view->bytes)
        return XZ_XZMI_BAD_RANGE;

    p = view->data + (size_t)at;
    material = XzMiReadU32Le(p);

    if (material != XZ_XZMI_NO_MATERIAL &&
        material >= view->material_count)
        return XZ_XZMI_BAD_MATERIAL_INDEX;

    *material_index = material;
    return XZ_XZMI_OK;
}

XzMaterialInstanceBindingStatus
XzMaterialInstanceBinding_Parse(
    XzMaterialInstanceBindingView *view,
    const unsigned char *data,
    size_t bytes)
{
    uint32_t version;
    uint32_t instance_count;
    uint32_t material_count;
    uint32_t binding_count;
    uint32_t instance_record_bytes;
    uint32_t binding_record_bytes;
    uint32_t flags;
    uint32_t instance_table_offset;
    uint32_t binding_table_offset;
    uint32_t reserved0;
    uint32_t reserved1;
    uint64_t expected_binding_offset;
    uint64_t expected_bytes;
    uint32_t instance_index;
    uint32_t previous_end = 0u;

    if (!view || !data)
        return XZ_XZMI_NULL;

    memset(view, 0, sizeof(*view));

    if (bytes < XZ_XZMI_HEADER_BYTES)
        return XZ_XZMI_BAD_SIZE;

    if (data[0] != 'X' ||
        data[1] != 'Z' ||
        data[2] != 'M' ||
        data[3] != 'I')
        return XZ_XZMI_BAD_MAGIC;

    version =
        XzMiReadU32Le(data + 4u);
    instance_count =
        XzMiReadU32Le(data + 8u);
    material_count =
        XzMiReadU32Le(data + 12u);
    binding_count =
        XzMiReadU32Le(data + 16u);
    instance_record_bytes =
        XzMiReadU32Le(data + 20u);
    binding_record_bytes =
        XzMiReadU32Le(data + 24u);
    flags =
        XzMiReadU32Le(data + 28u);
    instance_table_offset =
        XzMiReadU32Le(data + 32u);
    binding_table_offset =
        XzMiReadU32Le(data + 36u);
    reserved0 =
        XzMiReadU32Le(data + 40u);
    reserved1 =
        XzMiReadU32Le(data + 44u);

    if (version != XZ_XZMI_VERSION)
        return XZ_XZMI_BAD_VERSION;

    if (instance_count == 0u ||
        material_count == 0u ||
        binding_count == 0u ||
        instance_record_bytes !=
            XZ_XZMI_INSTANCE_RECORD_BYTES ||
        binding_record_bytes !=
            XZ_XZMI_BINDING_RECORD_BYTES ||
        flags != 0u ||
        reserved0 != 0u ||
        reserved1 != 0u ||
        instance_table_offset !=
            XZ_XZMI_HEADER_BYTES)
        return XZ_XZMI_BAD_HEADER;

    expected_binding_offset =
        (uint64_t)instance_table_offset +
        (uint64_t)instance_count *
            XZ_XZMI_INSTANCE_RECORD_BYTES;

    if (expected_binding_offset > UINT32_MAX ||
        binding_table_offset !=
            (uint32_t)expected_binding_offset)
        return XZ_XZMI_BAD_HEADER;

    expected_bytes =
        (uint64_t)binding_table_offset +
        (uint64_t)binding_count *
            XZ_XZMI_BINDING_RECORD_BYTES;

    if (expected_bytes != (uint64_t)bytes)
        return XZ_XZMI_BAD_SIZE;

    view->data = data;
    view->bytes = bytes;
    view->instance_count = instance_count;
    view->material_count = material_count;
    view->binding_count = binding_count;
    view->instance_table_offset =
        instance_table_offset;
    view->binding_table_offset =
        binding_table_offset;

    for (instance_index = 0u;
         instance_index < instance_count;
         ++instance_index) {
        XzMaterialInstanceRecord record;
        XzMaterialInstanceBindingStatus status =
            XzMaterialInstanceBinding_Instance(
                view,
                instance_index,
                &record);
        uint32_t submesh_index;

        if (status != XZ_XZMI_OK ||
            record.binding_count == 0u ||
            record.first_binding != previous_end)
            return XZ_XZMI_BAD_RANGE;

        for (submesh_index = 0u;
             submesh_index < record.binding_count;
             ++submesh_index) {
            uint32_t material;
            status =
                XzMaterialInstanceBinding_Material(
                    view,
                    instance_index,
                    submesh_index,
                    &material);
            if (status != XZ_XZMI_OK)
                return status;
        }

        previous_end =
            record.first_binding +
            record.binding_count;
    }

    if (previous_end != binding_count)
        return XZ_XZMI_BAD_RANGE;

    return XZ_XZMI_OK;
}

const char *XzMaterialInstanceBinding_StatusName(
    XzMaterialInstanceBindingStatus status)
{
    switch (status) {
    case XZ_XZMI_OK:
        return "OK";
    case XZ_XZMI_NULL:
        return "NULL";
    case XZ_XZMI_BAD_SIZE:
        return "BAD_SIZE";
    case XZ_XZMI_BAD_MAGIC:
        return "BAD_MAGIC";
    case XZ_XZMI_BAD_VERSION:
        return "BAD_VERSION";
    case XZ_XZMI_BAD_HEADER:
        return "BAD_HEADER";
    case XZ_XZMI_BAD_RANGE:
        return "BAD_RANGE";
    case XZ_XZMI_BAD_MATERIAL_INDEX:
        return "BAD_MATERIAL_INDEX";
    case XZ_XZMI_BAD_INSTANCE_INDEX:
        return "BAD_INSTANCE_INDEX";
    case XZ_XZMI_BAD_SUBMESH_INDEX:
        return "BAD_SUBMESH_INDEX";
    default:
        return "UNKNOWN";
    }
}

int XzMaterialInstanceBinding_SelfTest(void)
{
    enum {
        INSTANCE_COUNT = 2,
        MATERIAL_COUNT = 3,
        BINDING_COUNT = 5,
        BYTES =
            XZ_XZMI_HEADER_BYTES +
            INSTANCE_COUNT *
                XZ_XZMI_INSTANCE_RECORD_BYTES +
            BINDING_COUNT *
                XZ_XZMI_BINDING_RECORD_BYTES
    };
    unsigned char data[BYTES];
    XzMaterialInstanceBindingView view;
    uint32_t material;

    memset(data, 0, sizeof(data));
    memcpy(data, "XZMI", 4u);
    XzMiWriteU32Le(data + 4u, XZ_XZMI_VERSION);
    XzMiWriteU32Le(data + 8u, INSTANCE_COUNT);
    XzMiWriteU32Le(data + 12u, MATERIAL_COUNT);
    XzMiWriteU32Le(data + 16u, BINDING_COUNT);
    XzMiWriteU32Le(
        data + 20u,
        XZ_XZMI_INSTANCE_RECORD_BYTES);
    XzMiWriteU32Le(
        data + 24u,
        XZ_XZMI_BINDING_RECORD_BYTES);
    XzMiWriteU32Le(data + 28u, 0u);
    XzMiWriteU32Le(
        data + 32u,
        XZ_XZMI_HEADER_BYTES);
    XzMiWriteU32Le(
        data + 36u,
        XZ_XZMI_HEADER_BYTES +
            INSTANCE_COUNT *
                XZ_XZMI_INSTANCE_RECORD_BYTES);

    XzMiWriteU32Le(data + 48u, 0u);
    XzMiWriteU32Le(data + 52u, 2u);
    XzMiWriteU32Le(data + 56u, 2u);
    XzMiWriteU32Le(data + 60u, 3u);

    XzMiWriteU32Le(data + 64u, 0u);
    XzMiWriteU32Le(
        data + 68u,
        XZ_XZMI_NO_MATERIAL);
    XzMiWriteU32Le(data + 72u, 2u);
    XzMiWriteU32Le(data + 76u, 1u);
    XzMiWriteU32Le(data + 80u, 0u);

    if (XzMaterialInstanceBinding_Parse(
            &view,
            data,
            sizeof(data)) != XZ_XZMI_OK)
        return 0;

    if (view.instance_count != INSTANCE_COUNT ||
        view.material_count != MATERIAL_COUNT ||
        view.binding_count != BINDING_COUNT)
        return 0;

    if (XzMaterialInstanceBinding_Material(
            &view,
            0u,
            1u,
            &material) != XZ_XZMI_OK ||
        material != XZ_XZMI_NO_MATERIAL)
        return 0;

    if (XzMaterialInstanceBinding_Material(
            &view,
            1u,
            1u,
            &material) != XZ_XZMI_OK ||
        material != 1u)
        return 0;

    XzMiWriteU32Le(data + 76u, MATERIAL_COUNT);
    if (XzMaterialInstanceBinding_Parse(
            &view,
            data,
            sizeof(data)) !=
        XZ_XZMI_BAD_MATERIAL_INDEX)
        return 0;

    return 1;
}
