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

typedef struct {
    XzStaticSceneStatus status;

    unsigned char *scene_data;
    size_t scene_bytes;
    XzXzsceneView scene;

    XzStaticMeshResource *mesh_resources;
    uint32_t mesh_resource_count;

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

const char *XzStaticSceneRuntime_StatusName(
    XzStaticSceneStatus status);

#ifdef __cplusplus
}
#endif

#endif
