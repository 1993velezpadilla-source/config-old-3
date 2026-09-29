#ifndef XZ_MATERIAL_LIBRARY_H
#define XZ_MATERIAL_LIBRARY_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_XZML_VERSION 1u
#define XZ_XZML_HEADER_BYTES 96u
#define XZ_XZML_MATERIAL_RECORD_BYTES 80u
#define XZ_XZML_TEXTURE_ASSET_RECORD_BYTES 16u
#define XZ_XZML_TEXTURE_BINDING_RECORD_BYTES 12u
#define XZ_XZML_SCALAR_RECORD_BYTES 12u
#define XZ_XZML_COLOR_RECORD_BYTES 24u
#define XZ_XZML_SWITCH_RECORD_BYTES 12u
#define XZ_XZML_NO_TEXTURE 0xffffffffu

typedef enum {
    XZ_XZML_OK = 0,
    XZ_XZML_NULL,
    XZ_XZML_BAD_SIZE,
    XZ_XZML_BAD_MAGIC,
    XZ_XZML_BAD_VERSION,
    XZ_XZML_BAD_HEADER,
    XZ_XZML_BAD_RANGE,
    XZ_XZML_BAD_STRING,
    XZ_XZML_BAD_TEXTURE_INDEX,
    XZ_XZML_BAD_MATERIAL_INDEX,
    XZ_XZML_BAD_PARAMETER_INDEX,
    XZ_XZML_BAD_VALUE
} XzMaterialLibraryStatus;

typedef struct {
    const unsigned char *data;
    size_t bytes;

    uint32_t material_count;
    uint32_t texture_asset_count;
    uint32_t texture_binding_count;
    uint32_t scalar_count;
    uint32_t color_count;
    uint32_t switch_count;

    uint32_t material_table_offset;
    uint32_t texture_asset_table_offset;
    uint32_t texture_binding_table_offset;
    uint32_t scalar_table_offset;
    uint32_t color_table_offset;
    uint32_t switch_table_offset;
    uint32_t string_table_offset;
    uint32_t string_bytes;
} XzMaterialLibraryView;

typedef struct {
    uint32_t path_offset;
    uint32_t path_bytes;
    uint32_t export_type_offset;
    uint32_t export_type_bytes;
    uint32_t blend_mode_offset;
    uint32_t blend_mode_bytes;
    uint32_t shading_model_offset;
    uint32_t shading_model_bytes;

    uint32_t first_texture_binding;
    uint32_t texture_binding_count;
    uint32_t first_scalar;
    uint32_t scalar_count;
    uint32_t first_color;
    uint32_t color_count;
    uint32_t first_switch;
    uint32_t switch_count;

    uint32_t canonical_texture[4];
} XzMaterialLibraryMaterial;

typedef struct {
    uint32_t source_path_offset;
    uint32_t source_path_bytes;
    uint32_t runtime_file_offset;
    uint32_t runtime_file_bytes;
} XzMaterialLibraryTextureAsset;

typedef struct {
    uint32_t name_offset;
    uint32_t name_bytes;
    uint32_t texture_asset_index;
} XzMaterialLibraryTextureBinding;

typedef struct {
    uint32_t name_offset;
    uint32_t name_bytes;
    float value;
} XzMaterialLibraryScalar;

typedef struct {
    uint32_t name_offset;
    uint32_t name_bytes;
    float value[4];
} XzMaterialLibraryColor;

typedef struct {
    uint32_t name_offset;
    uint32_t name_bytes;
    uint32_t value;
} XzMaterialLibrarySwitch;

XzMaterialLibraryStatus XzMaterialLibrary_Parse(
    XzMaterialLibraryView *view,
    const unsigned char *data,
    size_t bytes);

XzMaterialLibraryStatus XzMaterialLibrary_Material(
    const XzMaterialLibraryView *view,
    uint32_t material_index,
    XzMaterialLibraryMaterial *material);

XzMaterialLibraryStatus XzMaterialLibrary_TextureAsset(
    const XzMaterialLibraryView *view,
    uint32_t texture_index,
    XzMaterialLibraryTextureAsset *texture);

XzMaterialLibraryStatus XzMaterialLibrary_TextureBinding(
    const XzMaterialLibraryView *view,
    uint32_t binding_index,
    XzMaterialLibraryTextureBinding *binding);

XzMaterialLibraryStatus XzMaterialLibrary_Scalar(
    const XzMaterialLibraryView *view,
    uint32_t scalar_index,
    XzMaterialLibraryScalar *scalar);

XzMaterialLibraryStatus XzMaterialLibrary_Color(
    const XzMaterialLibraryView *view,
    uint32_t color_index,
    XzMaterialLibraryColor *color);

XzMaterialLibraryStatus XzMaterialLibrary_Switch(
    const XzMaterialLibraryView *view,
    uint32_t switch_index,
    XzMaterialLibrarySwitch *value);

int XzMaterialLibrary_String(
    const XzMaterialLibraryView *view,
    uint32_t offset,
    uint32_t bytes,
    const char **text);

const char *XzMaterialLibrary_StatusName(
    XzMaterialLibraryStatus status);

int XzMaterialLibrary_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif
