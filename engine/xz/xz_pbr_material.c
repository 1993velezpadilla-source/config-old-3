#include "xz_pbr_material.h"

#include <math.h>
#include <string.h>

static uint32_t XzPbrMaterial_ReadU32Le(
    const unsigned char *p)
{
    return ((uint32_t)p[0]) |
           ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

static float XzPbrMaterial_ReadF32Le(
    const unsigned char *p)
{
    uint32_t bits =
        XzPbrMaterial_ReadU32Le(p);
    float value;

    memcpy(&value, &bits, sizeof(value));
    return value;
}

static XzPbrMaterialStatus XzPbrMaterial_DecodeBinding(
    const unsigned char *record,
    XzPbrMaterialBinding *binding)
{
    const uint32_t known_flags =
        XZ_PBR_FLAG_ROUGHNESS |
        XZ_PBR_FLAG_METALLIC |
        XZ_PBR_FLAG_SPECULAR |
        XZ_PBR_FLAG_EMISSIVE;

    if (!record || !binding)
        return XZ_PBR_MATERIAL_NULL;

    memset(binding, 0, sizeof(*binding));
    binding->flags =
        XzPbrMaterial_ReadU32Le(record + 0u);
    binding->roughness =
        XzPbrMaterial_ReadF32Le(record + 4u);
    binding->metallic =
        XzPbrMaterial_ReadF32Le(record + 8u);
    binding->specular =
        XzPbrMaterial_ReadF32Le(record + 12u);
    binding->emissive =
        XzPbrMaterial_ReadF32Le(record + 16u);

    if ((binding->flags & ~known_flags) != 0u)
        return XZ_PBR_MATERIAL_BAD_FLAGS;

    if (!isfinite(binding->roughness) ||
        !isfinite(binding->metallic) ||
        !isfinite(binding->specular) ||
        !isfinite(binding->emissive) ||
        binding->roughness < 0.0f ||
        binding->roughness > 1.0f ||
        binding->metallic < 0.0f ||
        binding->metallic > 1.0f ||
        binding->specular < 0.0f ||
        binding->specular > 1.0f ||
        binding->emissive < 0.0f ||
        binding->emissive > 16.0f)
        return XZ_PBR_MATERIAL_BAD_VALUE;

    return XZ_PBR_MATERIAL_OK;
}

XzPbrMaterialStatus XzPbrMaterial_Parse(
    XzPbrMaterialView *view,
    const unsigned char *data,
    size_t bytes)
{
    uint32_t binding_count;
    uint32_t record_bytes;
    uint32_t header_flags;
    uint64_t expected_bytes;
    uint32_t i;

    if (!view || !data)
        return XZ_PBR_MATERIAL_NULL;

    memset(view, 0, sizeof(*view));

    if (bytes < XZ_PBR_MATERIAL_HEADER_BYTES)
        return XZ_PBR_MATERIAL_BAD_SIZE;

    if (data[0] != 'X' ||
        data[1] != 'Z' ||
        data[2] != 'P' ||
        data[3] != 'B')
        return XZ_PBR_MATERIAL_BAD_MAGIC;

    if (XzPbrMaterial_ReadU32Le(data + 4u) !=
            XZ_PBR_MATERIAL_VERSION)
        return XZ_PBR_MATERIAL_BAD_VERSION;

    binding_count =
        XzPbrMaterial_ReadU32Le(data + 8u);
    record_bytes =
        XzPbrMaterial_ReadU32Le(data + 12u);
    header_flags =
        XzPbrMaterial_ReadU32Le(data + 16u);

    if (binding_count == 0u ||
        binding_count > 65536u ||
        record_bytes != XZ_PBR_MATERIAL_RECORD_BYTES ||
        header_flags != 0u)
        return XZ_PBR_MATERIAL_BAD_HEADER;

    expected_bytes =
        (uint64_t)XZ_PBR_MATERIAL_HEADER_BYTES +
        (uint64_t)binding_count *
            (uint64_t)record_bytes;

    if (expected_bytes != (uint64_t)bytes)
        return XZ_PBR_MATERIAL_BAD_SIZE;

    for (i = 0u; i < binding_count; ++i) {
        XzPbrMaterialBinding binding;
        XzPbrMaterialStatus status =
            XzPbrMaterial_DecodeBinding(
                data +
                    XZ_PBR_MATERIAL_HEADER_BYTES +
                    (size_t)i * record_bytes,
                &binding);

        if (status != XZ_PBR_MATERIAL_OK)
            return status;
    }

    view->data = data;
    view->bytes = bytes;
    view->binding_count = binding_count;
    view->record_bytes = record_bytes;
    return XZ_PBR_MATERIAL_OK;
}

XzPbrMaterialStatus XzPbrMaterial_ReadBinding(
    const XzPbrMaterialView *view,
    uint32_t binding_index,
    XzPbrMaterialBinding *binding)
{
    if (!view || !binding || !view->data)
        return XZ_PBR_MATERIAL_NULL;

    if (binding_index >= view->binding_count)
        return XZ_PBR_MATERIAL_BAD_INDEX;

    return XzPbrMaterial_DecodeBinding(
        view->data +
            XZ_PBR_MATERIAL_HEADER_BYTES +
            (size_t)binding_index *
                view->record_bytes,
        binding);
}

const char *XzPbrMaterial_StatusName(
    XzPbrMaterialStatus status)
{
    switch (status) {
    case XZ_PBR_MATERIAL_OK:
        return "OK";
    case XZ_PBR_MATERIAL_NULL:
        return "NULL";
    case XZ_PBR_MATERIAL_BAD_SIZE:
        return "BAD_SIZE";
    case XZ_PBR_MATERIAL_BAD_MAGIC:
        return "BAD_MAGIC";
    case XZ_PBR_MATERIAL_BAD_VERSION:
        return "BAD_VERSION";
    case XZ_PBR_MATERIAL_BAD_HEADER:
        return "BAD_HEADER";
    case XZ_PBR_MATERIAL_BAD_FLAGS:
        return "BAD_FLAGS";
    case XZ_PBR_MATERIAL_BAD_VALUE:
        return "BAD_VALUE";
    case XZ_PBR_MATERIAL_BAD_INDEX:
        return "BAD_INDEX";
    default:
        return "UNKNOWN";
    }
}
