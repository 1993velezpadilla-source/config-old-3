#ifndef XZ_STATIC_SCENE_RUNTIME_H
#define XZ_STATIC_SCENE_RUNTIME_H

#include "xz_xzmesh.h"
#include "xz_xzscene.h"
#include "xz_xztexture.h"
#include "xz_environment.h"
#include "xz_height_fog.h"
#include "xz_pbr_material.h"
#include "xz_material_instance_binding.h"
#include "xz_material_library.h"
#include "xz_lightmap_texture.h"
#include "xz_lightmap_binding.h"

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    XZ_STATIC_SCENE_IDLE = 0,
    XZ_STATIC_SCENE_NOT_PRESENT,
    XZ_STATIC_SCENE_READY,
    XZ_STATIC_SCENE_INVALID
} XzStaticSceneStatus;

typedef struct {
    unsigned char *data;
    size_t bytes;
    XzXzmeshView mesh;
    char path[XZ_XZSC_MAX_PATH_BYTES + 1u];
} XzStaticMeshResource;

#define XZ_STATIC_MATERIAL_NO_TEXTURE 0xffffffffu
#define XZ_STATIC_TEXTURE_FLAG_RGBA8 1u
#define XZ_STATIC_TEXTURE_FLAG_SRGB 2u

typedef struct {
    uint32_t width;
    uint32_t height;
    uint32_t flags;
    const unsigned char *rgba;
    size_t rgba_bytes;
} XzStaticTextureView;

typedef struct {
    unsigned char *data;
    size_t bytes;
    XzXztextureView texture;
    char path[256];
} XzStaticNativeTextureResource;

#define XZ_REFLECTION_FORMAT_RGBA16F 1u
#define XZ_REFLECTION_SHAPE_NONE 0u
#define XZ_REFLECTION_SHAPE_SPHERE 1u

typedef struct {
    const unsigned char *payload;
    size_t payload_bytes;
    uint32_t cubemap_size;
    uint32_t mip_count;
    uint32_t face_count;
    uint32_t pixel_format;
    uint32_t bytes_per_texel;
    float average_brightness;
    float brightness;
    unsigned char map_build_data_id[16];
    uint32_t asset_version;
    uint32_t shape;
    float capture_position_meters[3];
    float influence_radius_meters;
    float capture_offset_meters[3];
} XzReflectionCaptureView;

typedef struct {
    XzStaticSceneStatus status;

    unsigned char *scene_data;
    size_t scene_bytes;
    XzXzsceneView scene;

    XzStaticMeshResource *mesh_resources;
    uint32_t mesh_resource_count;

    unsigned char *material_data;
    size_t material_bytes;
    int material_file_handle;

    unsigned char *material_instance_data;
    size_t material_instance_bytes;
    XzMaterialInstanceBindingView material_instances;

    unsigned char *material_library_data;
    size_t material_library_bytes;
    XzMaterialLibraryView material_library;

    uint32_t material_texture_count;
    uint32_t material_binding_count;
    size_t material_texture_table_offset;
    size_t material_binding_offset;

    unsigned char *pbr_material_data;
    size_t pbr_material_bytes;
    XzPbrMaterialView pbr_material;

    unsigned char *normal_material_data;
    size_t normal_material_bytes;
    int normal_material_file_handle;
    uint32_t normal_texture_count;
    uint32_t normal_binding_count;
    size_t normal_texture_table_offset;
    size_t normal_binding_offset;

    unsigned char *environment_data;
    size_t environment_bytes;
    XzEnvironmentView environment;

    unsigned char *height_fog_data;
    size_t height_fog_bytes;
    XzHeightFogView height_fog;

    unsigned char *reflection_data;
    size_t reflection_bytes;
    XzReflectionCaptureView reflection;

    XzLightmapTextureView lightmaps;
    XzLightmapBindingView lightmap_bindings;

    uint32_t mesh_files_validated;
    uint64_t mesh_bytes_validated;
    uint64_t vertex_count;
    uint64_t index_count;
    uint64_t submesh_count;

    char map_id[64];
    char scene_path[256];
    char material_path[256];
    char material_instance_path[256];
    char material_library_path[256];
    char pbr_material_path[256];
    char normal_material_path[256];
    char environment_path[256];
    char height_fog_path[256];
    char reflection_path[256];
    char lightmap_path[256];
    char lightmap_binding_path[256];
    char error[128];
} XzStaticSceneRuntimeState;

void XzStaticSceneRuntime_Init(
    XzStaticSceneRuntimeState *state);

void XzStaticSceneRuntime_Reset(
    XzStaticSceneRuntimeState *state);

XzStaticSceneStatus XzStaticSceneRuntime_LoadMap(
    XzStaticSceneRuntimeState *state,
    const char *map_id);

void XzStaticSceneRuntime_Shutdown(
    XzStaticSceneRuntimeState *state);

const XzXzsceneView *XzStaticSceneRuntime_Scene(
    const XzStaticSceneRuntimeState *state);

const XzStaticMeshResource *
XzStaticSceneRuntime_Mesh(
    const XzStaticSceneRuntimeState *state,
    uint32_t mesh_index);

uint32_t XzStaticSceneRuntime_MeshCount(
    const XzStaticSceneRuntimeState *state);

int XzStaticSceneRuntime_MaterialBinding(
    const XzStaticSceneRuntimeState *state,
    uint32_t binding_index,
    uint32_t *texture_index);

const XzMaterialInstanceBindingView *
XzStaticSceneRuntime_MaterialInstances(
    const XzStaticSceneRuntimeState *state);

int XzStaticSceneRuntime_InstanceMaterial(
    const XzStaticSceneRuntimeState *state,
    uint32_t instance_index,
    uint32_t submesh_index,
    uint32_t *material_index);

const XzMaterialLibraryView *
XzStaticSceneRuntime_MaterialLibrary(
    const XzStaticSceneRuntimeState *state);

int XzStaticSceneRuntime_Material(
    const XzStaticSceneRuntimeState *state,
    uint32_t material_index,
    XzMaterialLibraryMaterial *material);

int XzStaticSceneRuntime_LoadMaterialTexture(
    const XzStaticSceneRuntimeState *state,
    uint32_t texture_index,
    XzStaticNativeTextureResource *resource);

void XzStaticSceneRuntime_ReleaseMaterialTexture(
    XzStaticNativeTextureResource *resource);

int XzStaticSceneRuntime_Texture(
    const XzStaticSceneRuntimeState *state,
    uint32_t texture_index,
    XzStaticTextureView *texture);

int XzStaticSceneRuntime_ReadTexture(
    const XzStaticSceneRuntimeState *state,
    uint32_t texture_index,
    void *destination,
    size_t destination_bytes);

int XzStaticSceneRuntime_PbrBinding(
    const XzStaticSceneRuntimeState *state,
    uint32_t binding_index,
    XzPbrMaterialBinding *binding);

int XzStaticSceneRuntime_NormalBinding(
    const XzStaticSceneRuntimeState *state,
    uint32_t binding_index,
    uint32_t *texture_index);

int XzStaticSceneRuntime_NormalTexture(
    const XzStaticSceneRuntimeState *state,
    uint32_t texture_index,
    XzStaticTextureView *texture);

int XzStaticSceneRuntime_ReadNormalTexture(
    const XzStaticSceneRuntimeState *state,
    uint32_t texture_index,
    void *destination,
    size_t destination_bytes);

const XzEnvironmentView *
XzStaticSceneRuntime_Environment(
    const XzStaticSceneRuntimeState *state);

int XzStaticSceneRuntime_EnvironmentLight(
    const XzStaticSceneRuntimeState *state,
    uint32_t light_index,
    XzEnvironmentLight *light);

const XzHeightFogView *
XzStaticSceneRuntime_HeightFog(
    const XzStaticSceneRuntimeState *state);

const XzReflectionCaptureView *
XzStaticSceneRuntime_ReflectionCapture(
    const XzStaticSceneRuntimeState *state);

const XzLightmapTextureView *
XzStaticSceneRuntime_Lightmaps(
    const XzStaticSceneRuntimeState *state);

const XzLightmapBindingView *
XzStaticSceneRuntime_LightmapBindings(
    const XzStaticSceneRuntimeState *state);

const char *XzStaticSceneRuntime_StatusName(
    XzStaticSceneStatus status);

#ifdef __cplusplus
}
#endif

#endif
