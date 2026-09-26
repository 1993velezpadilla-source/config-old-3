#include "xz_static_scene_runtime.h"
#include "xz_xzmesh.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define XZ_STATIC_SCENE_MAX_SCENE_BYTES \
    (16u * 1024u * 1024u)

#define XZ_STATIC_SCENE_MAX_MESH_BYTES \
    (64u * 1024u * 1024u)

#define XZ_STATIC_SCENE_GAMEPLAY_UNITS_PER_METER \
    39.3700787402f

/*
 * These are Vril filesystem APIs. Keeping the declarations here lets this
 * XZIEL-owned module compile in isolation while using the exact Vril search
 * path at runtime after patch_vril_xz_phase0.py copies it into source/.
 */
extern int COM_OpenFile(
    char *filename,
    int *handle);

extern void COM_CloseFile(
    int handle);

extern int Sys_FileRead(
    int handle,
    void *dest,
    int count);

static int XzSafeMapId(
    const char *map_id)
{
    const unsigned char *p =
        (const unsigned char *)map_id;
    size_t length = 0u;

    if (!p || !p[0])
        return 0;

    while (*p) {
        unsigned char c = *p++;

        if (!((c >= 'a' && c <= 'z') ||
              (c >= 'A' && c <= 'Z') ||
              (c >= '0' && c <= '9') ||
              c == '_' ||
              c == '-'))
            return 0;

        length++;
        if (length >= 63u)
            return 0;
    }

    return 1;
}

static void XzSetError(
    XzStaticSceneRuntimeState *state,
    const char *message)
{
    if (!state)
        return;

    snprintf(
        state->error,
        sizeof(state->error),
        "%s",
        message ? message : "unknown");
}

static int XzReadVfsFile(
    const char *path,
    size_t max_bytes,
    unsigned char **output,
    size_t *output_bytes)
{
    int handle = -1;
    int length;
    size_t cursor = 0u;
    unsigned char *data;

    if (!path ||
        !output ||
        !output_bytes)
        return -1;

    *output = NULL;
    *output_bytes = 0u;

    length = COM_OpenFile(
        (char *)path,
        &handle);

    if (length < 0 || handle < 0)
        return 0;

    if (length <= 0 ||
        (size_t)length > max_bytes) {
        COM_CloseFile(handle);
        return -1;
    }

    data = (unsigned char *)malloc(
        (size_t)length);
    if (!data) {
        COM_CloseFile(handle);
        return -1;
    }

    while (cursor < (size_t)length) {
        int remaining =
            length - (int)cursor;
        int got = Sys_FileRead(
            handle,
            data + cursor,
            remaining);

        if (got <= 0 ||
            got > remaining) {
            COM_CloseFile(handle);
            free(data);
            return -1;
        }

        cursor += (size_t)got;
    }

    COM_CloseFile(handle);

    *output = data;
    *output_bytes = cursor;
    return 1;
}

static int XzHasPrefix(
    const char *value,
    const char *prefix)
{
    size_t prefix_length;

    if (!value || !prefix)
        return 0;

    prefix_length = strlen(prefix);
    return strncmp(
        value,
        prefix,
        prefix_length) == 0;
}

void XzStaticSceneRuntime_Init(
    XzStaticSceneRuntimeState *state)
{
    if (!state)
        return;

    memset(state, 0, sizeof(*state));
    state->status = XZ_STATIC_SCENE_IDLE;
}

void XzStaticSceneRuntime_Reset(
    XzStaticSceneRuntimeState *state)
{
    if (!state)
        return;

    if (state->scene_data)
        free(state->scene_data);

    memset(state, 0, sizeof(*state));
    state->status = XZ_STATIC_SCENE_IDLE;
}

XzStaticSceneStatus XzStaticSceneRuntime_LoadMap(
    XzStaticSceneRuntimeState *state,
    const char *map_id)
{
    unsigned char *scene_data = NULL;
    size_t scene_bytes = 0u;
    XzXzsceneView scene;
    XzXzsceneStatus scene_status;
    char scene_path[256];
    char mesh_prefix[160];
    uint32_t mesh_index;
    int read_status;

    if (!state)
        return XZ_STATIC_SCENE_INVALID;

    XzStaticSceneRuntime_Reset(state);

    if (!XzSafeMapId(map_id)) {
        state->status =
            XZ_STATIC_SCENE_INVALID;
        XzSetError(
            state,
            "unsafe_map_id");
        return state->status;
    }

    snprintf(
        state->map_id,
        sizeof(state->map_id),
        "%s",
        map_id);

    if (snprintf(
            scene_path,
            sizeof(scene_path),
            "xziel/maps/%s/scene.xzsc",
            map_id) <= 0 ||
        strlen(scene_path) >=
            sizeof(scene_path) - 1u) {
        state->status =
            XZ_STATIC_SCENE_INVALID;
        XzSetError(
            state,
            "scene_path_overflow");
        return state->status;
    }

    snprintf(
        state->scene_path,
        sizeof(state->scene_path),
        "%s",
        scene_path);

    read_status = XzReadVfsFile(
        scene_path,
        XZ_STATIC_SCENE_MAX_SCENE_BYTES,
        &scene_data,
        &scene_bytes);

    if (read_status == 0) {
        state->status =
            XZ_STATIC_SCENE_NOT_PRESENT;
        XzSetError(
            state,
            "scene_not_present");
        return state->status;
    }

    if (read_status < 0) {
        state->status =
            XZ_STATIC_SCENE_INVALID;
        XzSetError(
            state,
            "scene_read_failed");
        return state->status;
    }

    scene_status = XzXzscene_Parse(
        &scene,
        scene_data,
        scene_bytes);

    if (scene_status != XZ_XZSC_OK) {
        char error[128];

        snprintf(
            error,
            sizeof(error),
            "xzscene_%s",
            XzXzscene_StatusName(
                scene_status));
        free(scene_data);

        state->status =
            XZ_STATIC_SCENE_INVALID;
        XzSetError(state, error);
        return state->status;
    }

    if (fabsf(
            scene.gameplay_units_per_meter -
            XZ_STATIC_SCENE_GAMEPLAY_UNITS_PER_METER) >
            0.001f) {
        free(scene_data);
        state->status =
            XZ_STATIC_SCENE_INVALID;
        XzSetError(
            state,
            "gameplay_scale_mismatch");
        return state->status;
    }

    if (strcmp(
            map_id,
            "xziel_nacht_bo3") == 0 &&
        (scene.mesh_count != 492u ||
         scene.instance_count != 10791u)) {
        free(scene_data);
        state->status =
            XZ_STATIC_SCENE_INVALID;
        XzSetError(
            state,
            "nacht_scene_count_mismatch");
        return state->status;
    }

    if (snprintf(
            mesh_prefix,
            sizeof(mesh_prefix),
            "xziel/maps/%s/meshes/",
            map_id) <= 0 ||
        strlen(mesh_prefix) >=
            sizeof(mesh_prefix) - 1u) {
        free(scene_data);
        state->status =
            XZ_STATIC_SCENE_INVALID;
        XzSetError(
            state,
            "mesh_prefix_overflow");
        return state->status;
    }

    for (mesh_index = 0u;
         mesh_index < scene.mesh_count;
         ++mesh_index) {
        char mesh_path[
            XZ_XZSC_MAX_PATH_BYTES + 1u];
        unsigned char *mesh_data = NULL;
        size_t mesh_bytes = 0u;
        XzXzmeshView mesh;
        XzXzmeshStatus mesh_status;
        uint32_t submesh_index;

        if (!XzXzscene_ReadMeshPath(
                &scene,
                mesh_index,
                mesh_path,
                sizeof(mesh_path))) {
            free(scene_data);
            state->status =
                XZ_STATIC_SCENE_INVALID;
            XzSetError(
                state,
                "mesh_path_read_failed");
            return state->status;
        }

        if (!XzHasPrefix(
                mesh_path,
                mesh_prefix)) {
            free(scene_data);
            state->status =
                XZ_STATIC_SCENE_INVALID;
            XzSetError(
                state,
                "mesh_path_cross_map");
            return state->status;
        }

        read_status = XzReadVfsFile(
            mesh_path,
            XZ_STATIC_SCENE_MAX_MESH_BYTES,
            &mesh_data,
            &mesh_bytes);

        if (read_status <= 0) {
            char error[128];

            snprintf(
                error,
                sizeof(error),
                "mesh_%u_%s",
                (unsigned int)mesh_index,
                read_status == 0
                    ? "missing"
                    : "read_failed");
            free(scene_data);
            state->status =
                XZ_STATIC_SCENE_INVALID;
            XzSetError(state, error);
            return state->status;
        }

        mesh_status = XzXzmesh_Parse(
            &mesh,
            mesh_data,
            mesh_bytes);

        if (mesh_status != XZ_XZMS_OK) {
            char error[128];

            snprintf(
                error,
                sizeof(error),
                "mesh_%u_xzms_%s",
                (unsigned int)mesh_index,
                XzXzmesh_StatusName(
                    mesh_status));
            free(mesh_data);
            free(scene_data);
            state->status =
                XZ_STATIC_SCENE_INVALID;
            XzSetError(state, error);
            return state->status;
        }

        /*
         * The source conversion proved all 492 Nacht submeshes carry normals
         * and UV0. Preserve that as a runtime requirement instead of silently
         * accepting a downgraded geometry payload.
         */
        for (submesh_index = 0u;
             submesh_index <
                 mesh.submesh_count;
             ++submesh_index) {
            XzXzmeshSubmesh submesh;

            if (!XzXzmesh_ReadSubmesh(
                    &mesh,
                    submesh_index,
                    &submesh) ||
                (submesh.attribute_flags &
                 (XZ_XZMS_ATTR_POSITION |
                  XZ_XZMS_ATTR_NORMAL |
                  XZ_XZMS_ATTR_UV0)) !=
                    (XZ_XZMS_ATTR_POSITION |
                     XZ_XZMS_ATTR_NORMAL |
                     XZ_XZMS_ATTR_UV0)) {
                free(mesh_data);
                free(scene_data);
                state->status =
                    XZ_STATIC_SCENE_INVALID;
                XzSetError(
                    state,
                    "mesh_attributes_incomplete");
                return state->status;
            }
        }

        state->mesh_files_validated++;
        state->mesh_bytes_validated +=
            (uint64_t)mesh_bytes;
        state->vertex_count +=
            (uint64_t)mesh.vertex_count;
        state->index_count +=
            (uint64_t)mesh.index_count;
        state->submesh_count +=
            (uint64_t)mesh.submesh_count;

        free(mesh_data);
    }

    state->scene_data = scene_data;
    state->scene_bytes = scene_bytes;
    state->scene = scene;
    state->status =
        XZ_STATIC_SCENE_READY;
    state->error[0] = '\0';

    return state->status;
}

void XzStaticSceneRuntime_Shutdown(
    XzStaticSceneRuntimeState *state)
{
    XzStaticSceneRuntime_Reset(state);
}

const XzXzsceneView *XzStaticSceneRuntime_Scene(
    const XzStaticSceneRuntimeState *state)
{
    if (!state ||
        state->status !=
            XZ_STATIC_SCENE_READY ||
        !state->scene_data)
        return NULL;

    return &state->scene;
}

const char *XzStaticSceneRuntime_StatusName(
    XzStaticSceneStatus status)
{
    switch (status) {
    case XZ_STATIC_SCENE_IDLE:
        return "IDLE";
    case XZ_STATIC_SCENE_NOT_PRESENT:
        return "NOT_PRESENT";
    case XZ_STATIC_SCENE_READY:
        return "READY";
    case XZ_STATIC_SCENE_INVALID:
        return "INVALID";
    default:
        return "UNKNOWN";
    }
}
