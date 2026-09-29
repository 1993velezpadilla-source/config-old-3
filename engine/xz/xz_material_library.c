#include "xz_material_library.h"

#include <math.h>
#include <string.h>

static uint32_t XzMlReadU32Le(
    const unsigned char *p)
{
    return ((uint32_t)p[0]) |
           ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

static float XzMlReadF32Le(
    const unsigned char *p)
{
    uint32_t bits = XzMlReadU32Le(p);
    float value;
    memcpy(&value, &bits, sizeof(value));
    return value;
}

static void XzMlWriteU32Le(
    unsigned char *p,
    uint32_t value)
{
    p[0] = (unsigned char)(value & 0xffu);
    p[1] = (unsigned char)((value >> 8) & 0xffu);
    p[2] = (unsigned char)((value >> 16) & 0xffu);
    p[3] = (unsigned char)((value >> 24) & 0xffu);
}

static void XzMlWriteF32Le(
    unsigned char *p,
    float value)
{
    uint32_t bits;
    memcpy(&bits, &value, sizeof(bits));
    XzMlWriteU32Le(p, bits);
}

static int XzMlRange(
    uint32_t first,
    uint32_t count,
    uint32_t total)
{
    return (uint64_t)first +
            (uint64_t)count <=
        (uint64_t)total;
}

int XzMaterialLibrary_String(
    const XzMaterialLibraryView *view,
    uint32_t offset,
    uint32_t bytes,
    const char **text)
{
    uint64_t end;

    if (!view ||
        !view->data ||
        !text ||
        bytes == 0u)
        return 0;

    end =
        (uint64_t)offset +
        (uint64_t)bytes;

    if (end > (uint64_t)view->string_bytes)
        return 0;

    *text =
        (const char *)(
            view->data +
            view->string_table_offset +
            offset);
    return 1;
}

XzMaterialLibraryStatus XzMaterialLibrary_Material(
    const XzMaterialLibraryView *view,
    uint32_t material_index,
    XzMaterialLibraryMaterial *material)
{
    const unsigned char *p;
    uint64_t at;
    unsigned int i;
    const char *ignored;

    if (!view || !view->data || !material)
        return XZ_XZML_NULL;

    if (material_index >= view->material_count)
        return XZ_XZML_BAD_MATERIAL_INDEX;

    at =
        (uint64_t)view->material_table_offset +
        (uint64_t)material_index *
            XZ_XZML_MATERIAL_RECORD_BYTES;

    if (at + XZ_XZML_MATERIAL_RECORD_BYTES >
            (uint64_t)view->bytes)
        return XZ_XZML_BAD_RANGE;

    p = view->data + (size_t)at;

    material->path_offset = XzMlReadU32Le(p + 0u);
    material->path_bytes = XzMlReadU32Le(p + 4u);
    material->export_type_offset = XzMlReadU32Le(p + 8u);
    material->export_type_bytes = XzMlReadU32Le(p + 12u);
    material->blend_mode_offset = XzMlReadU32Le(p + 16u);
    material->blend_mode_bytes = XzMlReadU32Le(p + 20u);
    material->shading_model_offset = XzMlReadU32Le(p + 24u);
    material->shading_model_bytes = XzMlReadU32Le(p + 28u);

    material->first_texture_binding = XzMlReadU32Le(p + 32u);
    material->texture_binding_count = XzMlReadU32Le(p + 36u);
    material->first_scalar = XzMlReadU32Le(p + 40u);
    material->scalar_count = XzMlReadU32Le(p + 44u);
    material->first_color = XzMlReadU32Le(p + 48u);
    material->color_count = XzMlReadU32Le(p + 52u);
    material->first_switch = XzMlReadU32Le(p + 56u);
    material->switch_count = XzMlReadU32Le(p + 60u);

    for (i = 0u; i < 4u; ++i)
        material->canonical_texture[i] =
            XzMlReadU32Le(
                p + 64u + i * 4u);

    if (!XzMaterialLibrary_String(
            view,
            material->path_offset,
            material->path_bytes,
            &ignored) ||
        !XzMaterialLibrary_String(
            view,
            material->export_type_offset,
            material->export_type_bytes,
            &ignored) ||
        !XzMaterialLibrary_String(
            view,
            material->blend_mode_offset,
            material->blend_mode_bytes,
            &ignored) ||
        !XzMaterialLibrary_String(
            view,
            material->shading_model_offset,
            material->shading_model_bytes,
            &ignored))
        return XZ_XZML_BAD_STRING;

    if (!XzMlRange(
            material->first_texture_binding,
            material->texture_binding_count,
            view->texture_binding_count) ||
        !XzMlRange(
            material->first_scalar,
            material->scalar_count,
            view->scalar_count) ||
        !XzMlRange(
            material->first_color,
            material->color_count,
            view->color_count) ||
        !XzMlRange(
            material->first_switch,
            material->switch_count,
            view->switch_count))
        return XZ_XZML_BAD_RANGE;

    for (i = 0u; i < 4u; ++i) {
        if (material->canonical_texture[i] !=
                XZ_XZML_NO_TEXTURE &&
            material->canonical_texture[i] >=
                view->texture_asset_count)
            return XZ_XZML_BAD_TEXTURE_INDEX;
    }

    return XZ_XZML_OK;
}

XzMaterialLibraryStatus XzMaterialLibrary_TextureAsset(
    const XzMaterialLibraryView *view,
    uint32_t texture_index,
    XzMaterialLibraryTextureAsset *texture)
{
    const unsigned char *p;
    uint64_t at;
    const char *ignored;

    if (!view || !view->data || !texture)
        return XZ_XZML_NULL;

    if (texture_index >= view->texture_asset_count)
        return XZ_XZML_BAD_PARAMETER_INDEX;

    at =
        (uint64_t)view->texture_asset_table_offset +
        (uint64_t)texture_index *
            XZ_XZML_TEXTURE_ASSET_RECORD_BYTES;

    if (at + XZ_XZML_TEXTURE_ASSET_RECORD_BYTES >
            (uint64_t)view->bytes)
        return XZ_XZML_BAD_RANGE;

    p = view->data + (size_t)at;
    texture->source_path_offset =
        XzMlReadU32Le(p + 0u);
    texture->source_path_bytes =
        XzMlReadU32Le(p + 4u);
    texture->runtime_file_offset =
        XzMlReadU32Le(p + 8u);
    texture->runtime_file_bytes =
        XzMlReadU32Le(p + 12u);

    if (!XzMaterialLibrary_String(
            view,
            texture->source_path_offset,
            texture->source_path_bytes,
            &ignored) ||
        !XzMaterialLibrary_String(
            view,
            texture->runtime_file_offset,
            texture->runtime_file_bytes,
            &ignored))
        return XZ_XZML_BAD_STRING;

    return XZ_XZML_OK;
}

XzMaterialLibraryStatus XzMaterialLibrary_TextureBinding(
    const XzMaterialLibraryView *view,
    uint32_t binding_index,
    XzMaterialLibraryTextureBinding *binding)
{
    const unsigned char *p;
    uint64_t at;
    const char *ignored;

    if (!view || !view->data || !binding)
        return XZ_XZML_NULL;

    if (binding_index >= view->texture_binding_count)
        return XZ_XZML_BAD_PARAMETER_INDEX;

    at =
        (uint64_t)view->texture_binding_table_offset +
        (uint64_t)binding_index *
            XZ_XZML_TEXTURE_BINDING_RECORD_BYTES;

    if (at + XZ_XZML_TEXTURE_BINDING_RECORD_BYTES >
            (uint64_t)view->bytes)
        return XZ_XZML_BAD_RANGE;

    p = view->data + (size_t)at;
    binding->name_offset =
        XzMlReadU32Le(p + 0u);
    binding->name_bytes =
        XzMlReadU32Le(p + 4u);
    binding->texture_asset_index =
        XzMlReadU32Le(p + 8u);

    if (!XzMaterialLibrary_String(
            view,
            binding->name_offset,
            binding->name_bytes,
            &ignored))
        return XZ_XZML_BAD_STRING;

    if (binding->texture_asset_index >=
            view->texture_asset_count)
        return XZ_XZML_BAD_TEXTURE_INDEX;

    return XZ_XZML_OK;
}

XzMaterialLibraryStatus XzMaterialLibrary_Scalar(
    const XzMaterialLibraryView *view,
    uint32_t scalar_index,
    XzMaterialLibraryScalar *scalar)
{
    const unsigned char *p;
    uint64_t at;
    const char *ignored;

    if (!view || !view->data || !scalar)
        return XZ_XZML_NULL;

    if (scalar_index >= view->scalar_count)
        return XZ_XZML_BAD_PARAMETER_INDEX;

    at =
        (uint64_t)view->scalar_table_offset +
        (uint64_t)scalar_index *
            XZ_XZML_SCALAR_RECORD_BYTES;

    if (at + XZ_XZML_SCALAR_RECORD_BYTES >
            (uint64_t)view->bytes)
        return XZ_XZML_BAD_RANGE;

    p = view->data + (size_t)at;
    scalar->name_offset =
        XzMlReadU32Le(p + 0u);
    scalar->name_bytes =
        XzMlReadU32Le(p + 4u);
    scalar->value =
        XzMlReadF32Le(p + 8u);

    if (!XzMaterialLibrary_String(
            view,
            scalar->name_offset,
            scalar->name_bytes,
            &ignored))
        return XZ_XZML_BAD_STRING;

    if (!isfinite(scalar->value))
        return XZ_XZML_BAD_VALUE;

    return XZ_XZML_OK;
}

XzMaterialLibraryStatus XzMaterialLibrary_Color(
    const XzMaterialLibraryView *view,
    uint32_t color_index,
    XzMaterialLibraryColor *color)
{
    const unsigned char *p;
    uint64_t at;
    const char *ignored;
    unsigned int i;

    if (!view || !view->data || !color)
        return XZ_XZML_NULL;

    if (color_index >= view->color_count)
        return XZ_XZML_BAD_PARAMETER_INDEX;

    at =
        (uint64_t)view->color_table_offset +
        (uint64_t)color_index *
            XZ_XZML_COLOR_RECORD_BYTES;

    if (at + XZ_XZML_COLOR_RECORD_BYTES >
            (uint64_t)view->bytes)
        return XZ_XZML_BAD_RANGE;

    p = view->data + (size_t)at;
    color->name_offset =
        XzMlReadU32Le(p + 0u);
    color->name_bytes =
        XzMlReadU32Le(p + 4u);

    for (i = 0u; i < 4u; ++i) {
        color->value[i] =
            XzMlReadF32Le(
                p + 8u + i * 4u);
        if (!isfinite(color->value[i]))
            return XZ_XZML_BAD_VALUE;
    }

    if (!XzMaterialLibrary_String(
            view,
            color->name_offset,
            color->name_bytes,
            &ignored))
        return XZ_XZML_BAD_STRING;

    return XZ_XZML_OK;
}

XzMaterialLibraryStatus XzMaterialLibrary_Switch(
    const XzMaterialLibraryView *view,
    uint32_t switch_index,
    XzMaterialLibrarySwitch *value)
{
    const unsigned char *p;
    uint64_t at;
    const char *ignored;

    if (!view || !view->data || !value)
        return XZ_XZML_NULL;

    if (switch_index >= view->switch_count)
        return XZ_XZML_BAD_PARAMETER_INDEX;

    at =
        (uint64_t)view->switch_table_offset +
        (uint64_t)switch_index *
            XZ_XZML_SWITCH_RECORD_BYTES;

    if (at + XZ_XZML_SWITCH_RECORD_BYTES >
            (uint64_t)view->bytes)
        return XZ_XZML_BAD_RANGE;

    p = view->data + (size_t)at;
    value->name_offset =
        XzMlReadU32Le(p + 0u);
    value->name_bytes =
        XzMlReadU32Le(p + 4u);
    value->value =
        XzMlReadU32Le(p + 8u);

    if (!XzMaterialLibrary_String(
            view,
            value->name_offset,
            value->name_bytes,
            &ignored))
        return XZ_XZML_BAD_STRING;

    if (value->value > 1u)
        return XZ_XZML_BAD_VALUE;

    return XZ_XZML_OK;
}

XzMaterialLibraryStatus XzMaterialLibrary_Parse(
    XzMaterialLibraryView *view,
    const unsigned char *data,
    size_t bytes)
{
    uint32_t version;
    uint32_t material_count;
    uint32_t texture_asset_count;
    uint32_t texture_binding_count;
    uint32_t scalar_count;
    uint32_t color_count;
    uint32_t switch_count;
    uint32_t material_record_bytes;
    uint32_t texture_asset_record_bytes;
    uint32_t texture_binding_record_bytes;
    uint32_t scalar_record_bytes;
    uint32_t color_record_bytes;
    uint32_t switch_record_bytes;
    uint32_t material_table_offset;
    uint32_t texture_asset_table_offset;
    uint32_t texture_binding_table_offset;
    uint32_t scalar_table_offset;
    uint32_t color_table_offset;
    uint32_t switch_table_offset;
    uint32_t string_table_offset;
    uint32_t string_bytes;
    uint32_t flags;
    uint32_t reserved;
    uint64_t cursor;
    uint32_t i;

    if (!view || !data)
        return XZ_XZML_NULL;

    memset(view, 0, sizeof(*view));

    if (bytes < XZ_XZML_HEADER_BYTES)
        return XZ_XZML_BAD_SIZE;

    if (data[0] != 'X' ||
        data[1] != 'Z' ||
        data[2] != 'M' ||
        data[3] != 'L')
        return XZ_XZML_BAD_MAGIC;

    version = XzMlReadU32Le(data + 4u);
    material_count = XzMlReadU32Le(data + 8u);
    texture_asset_count = XzMlReadU32Le(data + 12u);
    texture_binding_count = XzMlReadU32Le(data + 16u);
    scalar_count = XzMlReadU32Le(data + 20u);
    color_count = XzMlReadU32Le(data + 24u);
    switch_count = XzMlReadU32Le(data + 28u);
    material_record_bytes = XzMlReadU32Le(data + 32u);
    texture_asset_record_bytes = XzMlReadU32Le(data + 36u);
    texture_binding_record_bytes = XzMlReadU32Le(data + 40u);
    scalar_record_bytes = XzMlReadU32Le(data + 44u);
    color_record_bytes = XzMlReadU32Le(data + 48u);
    switch_record_bytes = XzMlReadU32Le(data + 52u);
    material_table_offset = XzMlReadU32Le(data + 56u);
    texture_asset_table_offset = XzMlReadU32Le(data + 60u);
    texture_binding_table_offset = XzMlReadU32Le(data + 64u);
    scalar_table_offset = XzMlReadU32Le(data + 68u);
    color_table_offset = XzMlReadU32Le(data + 72u);
    switch_table_offset = XzMlReadU32Le(data + 76u);
    string_table_offset = XzMlReadU32Le(data + 80u);
    string_bytes = XzMlReadU32Le(data + 84u);
    flags = XzMlReadU32Le(data + 88u);
    reserved = XzMlReadU32Le(data + 92u);

    if (version != XZ_XZML_VERSION)
        return XZ_XZML_BAD_VERSION;

    if (material_count == 0u ||
        material_record_bytes != XZ_XZML_MATERIAL_RECORD_BYTES ||
        texture_asset_record_bytes !=
            XZ_XZML_TEXTURE_ASSET_RECORD_BYTES ||
        texture_binding_record_bytes !=
            XZ_XZML_TEXTURE_BINDING_RECORD_BYTES ||
        scalar_record_bytes !=
            XZ_XZML_SCALAR_RECORD_BYTES ||
        color_record_bytes !=
            XZ_XZML_COLOR_RECORD_BYTES ||
        switch_record_bytes !=
            XZ_XZML_SWITCH_RECORD_BYTES ||
        flags != 0u ||
        reserved != 0u ||
        material_table_offset !=
            XZ_XZML_HEADER_BYTES)
        return XZ_XZML_BAD_HEADER;

    cursor = XZ_XZML_HEADER_BYTES;
#define XZML_ADVANCE(count_, bytes_, expected_) \
    do { \
        cursor += (uint64_t)(count_) * (uint64_t)(bytes_); \
        if (cursor > UINT32_MAX || (uint32_t)cursor != (expected_)) \
            return XZ_XZML_BAD_HEADER; \
    } while (0)

    XZML_ADVANCE(
        material_count,
        XZ_XZML_MATERIAL_RECORD_BYTES,
        texture_asset_table_offset);
    XZML_ADVANCE(
        texture_asset_count,
        XZ_XZML_TEXTURE_ASSET_RECORD_BYTES,
        texture_binding_table_offset);
    XZML_ADVANCE(
        texture_binding_count,
        XZ_XZML_TEXTURE_BINDING_RECORD_BYTES,
        scalar_table_offset);
    XZML_ADVANCE(
        scalar_count,
        XZ_XZML_SCALAR_RECORD_BYTES,
        color_table_offset);
    XZML_ADVANCE(
        color_count,
        XZ_XZML_COLOR_RECORD_BYTES,
        switch_table_offset);
    XZML_ADVANCE(
        switch_count,
        XZ_XZML_SWITCH_RECORD_BYTES,
        string_table_offset);
#undef XZML_ADVANCE

    cursor += string_bytes;
    if (cursor != (uint64_t)bytes)
        return XZ_XZML_BAD_SIZE;

    view->data = data;
    view->bytes = bytes;
    view->material_count = material_count;
    view->texture_asset_count = texture_asset_count;
    view->texture_binding_count = texture_binding_count;
    view->scalar_count = scalar_count;
    view->color_count = color_count;
    view->switch_count = switch_count;
    view->material_table_offset = material_table_offset;
    view->texture_asset_table_offset = texture_asset_table_offset;
    view->texture_binding_table_offset = texture_binding_table_offset;
    view->scalar_table_offset = scalar_table_offset;
    view->color_table_offset = color_table_offset;
    view->switch_table_offset = switch_table_offset;
    view->string_table_offset = string_table_offset;
    view->string_bytes = string_bytes;

    for (i = 0u; i < material_count; ++i) {
        XzMaterialLibraryMaterial material;
        XzMaterialLibraryStatus status =
            XzMaterialLibrary_Material(
                view,
                i,
                &material);
        if (status != XZ_XZML_OK)
            return status;
    }

    for (i = 0u; i < texture_asset_count; ++i) {
        XzMaterialLibraryTextureAsset texture;
        XzMaterialLibraryStatus status =
            XzMaterialLibrary_TextureAsset(
                view,
                i,
                &texture);
        if (status != XZ_XZML_OK)
            return status;
    }

    for (i = 0u; i < texture_binding_count; ++i) {
        XzMaterialLibraryTextureBinding binding;
        XzMaterialLibraryStatus status =
            XzMaterialLibrary_TextureBinding(
                view,
                i,
                &binding);
        if (status != XZ_XZML_OK)
            return status;
    }

    for (i = 0u; i < scalar_count; ++i) {
        XzMaterialLibraryScalar scalar;
        XzMaterialLibraryStatus status =
            XzMaterialLibrary_Scalar(
                view,
                i,
                &scalar);
        if (status != XZ_XZML_OK)
            return status;
    }

    for (i = 0u; i < color_count; ++i) {
        XzMaterialLibraryColor color;
        XzMaterialLibraryStatus status =
            XzMaterialLibrary_Color(
                view,
                i,
                &color);
        if (status != XZ_XZML_OK)
            return status;
    }

    for (i = 0u; i < switch_count; ++i) {
        XzMaterialLibrarySwitch value;
        XzMaterialLibraryStatus status =
            XzMaterialLibrary_Switch(
                view,
                i,
                &value);
        if (status != XZ_XZML_OK)
            return status;
    }

    return XZ_XZML_OK;
}

const char *XzMaterialLibrary_StatusName(
    XzMaterialLibraryStatus status)
{
    switch (status) {
    case XZ_XZML_OK: return "OK";
    case XZ_XZML_NULL: return "NULL";
    case XZ_XZML_BAD_SIZE: return "BAD_SIZE";
    case XZ_XZML_BAD_MAGIC: return "BAD_MAGIC";
    case XZ_XZML_BAD_VERSION: return "BAD_VERSION";
    case XZ_XZML_BAD_HEADER: return "BAD_HEADER";
    case XZ_XZML_BAD_RANGE: return "BAD_RANGE";
    case XZ_XZML_BAD_STRING: return "BAD_STRING";
    case XZ_XZML_BAD_TEXTURE_INDEX: return "BAD_TEXTURE_INDEX";
    case XZ_XZML_BAD_MATERIAL_INDEX: return "BAD_MATERIAL_INDEX";
    case XZ_XZML_BAD_PARAMETER_INDEX: return "BAD_PARAMETER_INDEX";
    case XZ_XZML_BAD_VALUE: return "BAD_VALUE";
    default: return "UNKNOWN";
    }
}

int XzMaterialLibrary_SelfTest(void)
{
    static const char strings[] =
        "mat"
        "Material"
        "BLEND_Opaque"
        "MSM_DefaultLit"
        "/Game/T"
        "t0000.xzt"
        "PM_Diffuse"
        "Roughness"
        "Tint"
        "UseDetail";
    enum {
        MATS = 1,
        TEX = 1,
        TB = 1,
        SC = 1,
        CO = 1,
        SW = 1,
        STRING_BYTES = sizeof(strings) - 1,
        TEX_OFF =
            XZ_XZML_HEADER_BYTES +
            MATS * XZ_XZML_MATERIAL_RECORD_BYTES,
        TB_OFF =
            TEX_OFF +
            TEX * XZ_XZML_TEXTURE_ASSET_RECORD_BYTES,
        SC_OFF =
            TB_OFF +
            TB * XZ_XZML_TEXTURE_BINDING_RECORD_BYTES,
        CO_OFF =
            SC_OFF +
            SC * XZ_XZML_SCALAR_RECORD_BYTES,
        SW_OFF =
            CO_OFF +
            CO * XZ_XZML_COLOR_RECORD_BYTES,
        STR_OFF =
            SW_OFF +
            SW * XZ_XZML_SWITCH_RECORD_BYTES,
        BYTES = STR_OFF + STRING_BYTES
    };
    unsigned char data[BYTES];
    XzMaterialLibraryView view;
    XzMaterialLibraryMaterial material;
    uint32_t at = 0u;

    memset(data, 0, sizeof(data));
    memcpy(data, "XZML", 4u);
    XzMlWriteU32Le(data + 4u, XZ_XZML_VERSION);
    XzMlWriteU32Le(data + 8u, MATS);
    XzMlWriteU32Le(data + 12u, TEX);
    XzMlWriteU32Le(data + 16u, TB);
    XzMlWriteU32Le(data + 20u, SC);
    XzMlWriteU32Le(data + 24u, CO);
    XzMlWriteU32Le(data + 28u, SW);
    XzMlWriteU32Le(data + 32u, XZ_XZML_MATERIAL_RECORD_BYTES);
    XzMlWriteU32Le(data + 36u, XZ_XZML_TEXTURE_ASSET_RECORD_BYTES);
    XzMlWriteU32Le(data + 40u, XZ_XZML_TEXTURE_BINDING_RECORD_BYTES);
    XzMlWriteU32Le(data + 44u, XZ_XZML_SCALAR_RECORD_BYTES);
    XzMlWriteU32Le(data + 48u, XZ_XZML_COLOR_RECORD_BYTES);
    XzMlWriteU32Le(data + 52u, XZ_XZML_SWITCH_RECORD_BYTES);
    XzMlWriteU32Le(data + 56u, XZ_XZML_HEADER_BYTES);
    XzMlWriteU32Le(data + 60u, TEX_OFF);
    XzMlWriteU32Le(data + 64u, TB_OFF);
    XzMlWriteU32Le(data + 68u, SC_OFF);
    XzMlWriteU32Le(data + 72u, CO_OFF);
    XzMlWriteU32Le(data + 76u, SW_OFF);
    XzMlWriteU32Le(data + 80u, STR_OFF);
    XzMlWriteU32Le(data + 84u, STRING_BYTES);

#define ADD_STRING(field_off_, field_len_, literal_) \
    do { \
        XzMlWriteU32Le((field_off_), at); \
        XzMlWriteU32Le((field_len_), (uint32_t)(sizeof(literal_) - 1u)); \
        at += (uint32_t)(sizeof(literal_) - 1u); \
    } while (0)

    ADD_STRING(data + 96u + 0u, data + 96u + 4u, "mat");
    ADD_STRING(data + 96u + 8u, data + 96u + 12u, "Material");
    ADD_STRING(data + 96u + 16u, data + 96u + 20u, "BLEND_Opaque");
    ADD_STRING(data + 96u + 24u, data + 96u + 28u, "MSM_DefaultLit");
    XzMlWriteU32Le(data + 96u + 32u, 0u);
    XzMlWriteU32Le(data + 96u + 36u, 1u);
    XzMlWriteU32Le(data + 96u + 40u, 0u);
    XzMlWriteU32Le(data + 96u + 44u, 1u);
    XzMlWriteU32Le(data + 96u + 48u, 0u);
    XzMlWriteU32Le(data + 96u + 52u, 1u);
    XzMlWriteU32Le(data + 96u + 56u, 0u);
    XzMlWriteU32Le(data + 96u + 60u, 1u);
    XzMlWriteU32Le(data + 96u + 64u, 0u);
    XzMlWriteU32Le(data + 96u + 68u, XZ_XZML_NO_TEXTURE);
    XzMlWriteU32Le(data + 96u + 72u, XZ_XZML_NO_TEXTURE);
    XzMlWriteU32Le(data + 96u + 76u, XZ_XZML_NO_TEXTURE);

    ADD_STRING(data + TEX_OFF + 0u, data + TEX_OFF + 4u, "/Game/T");
    ADD_STRING(data + TEX_OFF + 8u, data + TEX_OFF + 12u, "t0000.xzt");

    ADD_STRING(data + TB_OFF + 0u, data + TB_OFF + 4u, "PM_Diffuse");
    XzMlWriteU32Le(data + TB_OFF + 8u, 0u);

    ADD_STRING(data + SC_OFF + 0u, data + SC_OFF + 4u, "Roughness");
    XzMlWriteF32Le(data + SC_OFF + 8u, 0.5f);

    ADD_STRING(data + CO_OFF + 0u, data + CO_OFF + 4u, "Tint");
    XzMlWriteF32Le(data + CO_OFF + 8u, 1.0f);
    XzMlWriteF32Le(data + CO_OFF + 12u, 0.5f);
    XzMlWriteF32Le(data + CO_OFF + 16u, 0.25f);
    XzMlWriteF32Le(data + CO_OFF + 20u, 1.0f);

    ADD_STRING(data + SW_OFF + 0u, data + SW_OFF + 4u, "UseDetail");
    XzMlWriteU32Le(data + SW_OFF + 8u, 1u);
#undef ADD_STRING

    memcpy(data + STR_OFF, strings, STRING_BYTES);

    if (at != STRING_BYTES)
        return 0;

    if (XzMaterialLibrary_Parse(
            &view,
            data,
            sizeof(data)) != XZ_XZML_OK)
        return 0;

    if (view.material_count != 1u ||
        view.texture_asset_count != 1u ||
        view.texture_binding_count != 1u)
        return 0;

    if (XzMaterialLibrary_Material(
            &view,
            0u,
            &material) != XZ_XZML_OK ||
        material.canonical_texture[0] != 0u)
        return 0;

    return 1;
}
