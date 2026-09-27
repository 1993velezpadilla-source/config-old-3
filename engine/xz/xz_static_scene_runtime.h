#ifndef XZ_STATIC_SCENE_RUNTIME_H
#define XZ_STATIC_SCENE_RUNTIME_H

#include "xz_xzmesh.h"
#include "xz_xzscene.h"
#include "xz_environment.h"
#include "xz_height_fog.h"

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

typedef struct {
    uint32_t width;
    uint32_t height;
    uint32_t flags;
    const unsigned char *rgba;
    size_t rgba_bytes;
} XzStaticTextureView;

typedef struct {
    XzStaticSceneStatus status;

    unsigned char *scene_data;
    size_t scene_bytes;
    XzXzsceneView scene;

    XzStaticMeshResource *mesh_resources;
    uint32_t mesh_resource_count;

    unsigned char *material_data;
    size_t material_bytes;

    uint32_t material_texture_count;
    uint32_t material_binding_count;
    size_t material_texture_table_offset;
    size_t material_binding_offset;

    unsigned char *environment_data;
    size_t environment_bytes;
    XzEnvironmentView environment;

    unsigned char *height_fog_data;
    size_t height_fog_bytes;
    XzHeightFogView height_fog;

    uint32_t mesh_files_validated;
    uint64_t mesh_bytes_validated;
    uint64_t vertex_count;
    uint64_t index_count;
    uint64_t submesh_count;

    char map_id[64];
    char scene_path[256];
    char material_path[256];
    char environment_path[256];
    char height_fog_path[256];
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

int XzStaticSceneRuntime_Texture(
    const XzStaticSceneRuntimeState *state,
    uint32_t texture_index,
    XzStaticTextureView *texture);

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

const char *XzStaticSceneRuntime_StatusName(
    XzStaticSceneStatus status);

#ifdef __cplusplus
}
#endif

#endif
