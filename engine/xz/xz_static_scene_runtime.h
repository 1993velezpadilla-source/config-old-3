#ifndef XZ_STATIC_SCENE_RUNTIME_H
#define XZ_STATIC_SCENE_RUNTIME_H

#include "xz_xzmesh.h"
#include "xz_xzscene.h"

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
#define XZ_STATIC_TEXTURE_PATH_BYTES 128u

typedef struct {
    char path[XZ_STATIC_TEXTURE_PATH_BYTES];
} XzStaticTextureResource;

typedef struct {
    uint32_t mesh_index;
    uint32_t material_index;
    uint32_t diffuse_texture_index;
    uint32_t flags;
} XzStaticMaterialBinding;

typedef struct {
    XzStaticSceneStatus status;

    unsigned char *scene_data;
    size_t scene_bytes;
    XzXzsceneView scene;

    XzStaticMeshResource *mesh_resources;
    uint32_t mesh_resource_count;

    XzStaticTextureResource *textures;
    uint32_t texture_count;
    XzStaticMaterialBinding *material_bindings;
    uint32_t material_binding_count;
    uint32_t textured_material_bindings;

    uint32_t mesh_files_validated;
    uint64_t mesh_bytes_validated;
    uint64_t vertex_count;
    uint64_t index_count;
    uint64_t submesh_count;

    char map_id[64];
    char scene_path[256];
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

uint32_t XzStaticSceneRuntime_TextureCount(
    const XzStaticSceneRuntimeState *state);

uint32_t XzStaticSceneRuntime_MaterialBindingCount(
    const XzStaticSceneRuntimeState *state);

uint32_t XzStaticSceneRuntime_DiffuseTextureIndex(
    const XzStaticSceneRuntimeState *state,
    uint32_t mesh_index,
    uint32_t material_index);

const char *XzStaticSceneRuntime_TexturePath(
    const XzStaticSceneRuntimeState *state,
    uint32_t texture_index);

int XzStaticSceneRuntime_LoadTextureRgba(
    const XzStaticSceneRuntimeState *state,
    uint32_t texture_index,
    unsigned char **out_pixels,
    uint32_t *out_width,
    uint32_t *out_height);

const char *XzStaticSceneRuntime_StatusName(
    XzStaticSceneStatus status);

#ifdef __cplusplus
}
#endif

#endif
