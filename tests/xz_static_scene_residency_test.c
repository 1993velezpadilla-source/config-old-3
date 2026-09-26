#include "xz_static_scene_runtime.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_HANDLES 8

static FILE *g_handles[MAX_HANDLES];

int COM_OpenFile(
    char *filename,
    int *handle)
{
    FILE *file;
    long length;
    int i;

    if (!filename || !handle)
        return -1;

    file = fopen(filename, "rb");
    if (!file)
        return -1;

    if (fseek(file, 0, SEEK_END) != 0) {
        fclose(file);
        return -1;
    }

    length = ftell(file);
    if (length < 0 ||
        fseek(file, 0, SEEK_SET) != 0) {
        fclose(file);
        return -1;
    }

    for (i = 1; i < MAX_HANDLES; ++i) {
        if (!g_handles[i]) {
            g_handles[i] = file;
            *handle = i;
            return (int)length;
        }
    }

    fclose(file);
    return -1;
}

void COM_CloseFile(int handle)
{
    if (handle <= 0 ||
        handle >= MAX_HANDLES ||
        !g_handles[handle])
        return;

    fclose(g_handles[handle]);
    g_handles[handle] = NULL;
}

int Sys_FileRead(
    int handle,
    void *dest,
    int count)
{
    size_t got;

    if (handle <= 0 ||
        handle >= MAX_HANDLES ||
        !g_handles[handle] ||
        !dest ||
        count < 0)
        return -1;

    got = fread(
        dest,
        1,
        (size_t)count,
        g_handles[handle]);

    return (int)got;
}

int main(void)
{
    XzStaticSceneRuntimeState state;
    const XzStaticMeshResource *mesh;
    const XzXzsceneView *scene;

    XzStaticSceneRuntime_Init(&state);

    if (XzStaticSceneRuntime_LoadMap(
            &state,
            "unit_map") !=
        XZ_STATIC_SCENE_READY) {
        fprintf(
            stderr,
            "load failed status=%s error=%s\n",
            XzStaticSceneRuntime_StatusName(
                state.status),
            state.error);
        return 1;
    }

    scene =
        XzStaticSceneRuntime_Scene(&state);

    if (!scene ||
        scene->mesh_count != 1u ||
        scene->instance_count != 1u)
        return 2;

    if (XzStaticSceneRuntime_MeshCount(
            &state) != 1u)
        return 3;

    mesh =
        XzStaticSceneRuntime_Mesh(
            &state,
            0u);

    if (!mesh ||
        !mesh->data ||
        mesh->bytes == 0u ||
        mesh->mesh.vertex_count != 3u ||
        mesh->mesh.index_count != 3u ||
        mesh->mesh.submesh_count != 1u)
        return 4;

    if (strcmp(
            mesh->path,
            "xziel/maps/unit_map/meshes/a.xzm") != 0)
        return 5;

    if (state.mesh_files_validated != 1u ||
        state.mesh_bytes_validated !=
            (uint64_t)mesh->bytes ||
        state.vertex_count != 3u ||
        state.index_count != 3u ||
        state.submesh_count != 1u)
        return 6;

    XzStaticSceneRuntime_Reset(&state);

    if (state.status !=
            XZ_STATIC_SCENE_IDLE ||
        state.scene_data != NULL ||
        state.mesh_resources != NULL ||
        state.mesh_resource_count != 0u)
        return 7;

    printf(
        "XZIEL_STATIC_SCENE_RESIDENCY_TEST_OK "
        "meshes=1 retained=1 reset=PASS\n");

    return 0;
}
