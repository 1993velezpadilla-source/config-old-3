#include "xz_static_scene_runtime.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define XZ_STATIC_SCENE_MAX_SCENE_BYTES \
    (16u * 1024u * 1024u)

#define XZ_STATIC_SCENE_MAX_MESH_BYTES \
    (64u * 1024u * 1024u)

#define XZ_STATIC_SCENE_MAX_MATERIAL_BYTES \
    (4u * 1024u * 1024u)

#define XZ_STATIC_SCENE_MAX_TEXTURE_BYTES \
    (2u * 1024u * 1024u)

#define XZ_STATIC_SCENE_MAX_TEXTURE_COUNT 2048u

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

static void XzFreeMeshResources(
    XzStaticMeshResource *resources,
    uint32_t count)
{
    uint32_t i;

    if (!resources)
        return;

    for (i = 0u; i < count; ++i) {
        if (resources[i].data)
            free(resources[i].data);
    }

    free(resources);
}


static void XzFreeTextureResources(
    XzStaticTextureResource *resources,
    uint32_t count)
{
    uint32_t i;

    if (!resources)
        return;

    for (i = 0u; i < count; ++i) {
        if (resources[i].data)
            free(resources[i].data);
    }

    free(resources);
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

    XzFreeMeshResources(
        state->mesh_resources,
        state->mesh_resource_count);

    XzFreeTextureResources(
        state->texture_resources,
        state->texture_resource_count);

    if (state->material_data)
        free(state->material_data);

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
    XzStaticMeshResource *resources = NULL;
    XzStaticTextureResource *texture_resources = NULL;
    unsigned char *material_data = NULL;
    size_t material_bytes = 0u;
    XzXzmaterialView materials;
    char scene_path[256];
    char material_path[256];
    char mesh_prefix[160];
    char texture_path[256];
    char failure[128] = "";
    uint32_t mesh_index;
    uint64_t mesh_bytes_total = 0u;
    uint64_t vertex_total = 0u;
    uint64_t index_total = 0u;
    uint64_t submesh_total = 0u;
    uint64_t texture_bytes_total = 0u;
    uint32_t texture_index;
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
        snprintf(
            failure,
            sizeof(failure),
            "xzscene_%s",
            XzXzscene_StatusName(
                scene_status));
        goto invalid;
    }

    if (fabsf(
            scene.gameplay_units_per_meter -
            XZ_STATIC_SCENE_GAMEPLAY_UNITS_PER_METER) >
            0.001f) {
        snprintf(
            failure,
            sizeof(failure),
            "%s",
            "gameplay_scale_mismatch");
        goto invalid;
    }

    if (strcmp(
            map_id,
            "xziel_nacht_bo3") == 0 &&
        (scene.mesh_count != 492u ||
         scene.instance_count != 10791u)) {
        snprintf(
            failure,
            sizeof(failure),
            "%s",
            "nacht_scene_count_mismatch");
        goto invalid;
    }

    if (snprintf(
            mesh_prefix,
            sizeof(mesh_prefix),
            "xziel/maps/%s/meshes/",
            map_id) <= 0 ||
        strlen(mesh_prefix) >=
            sizeof(mesh_prefix) - 1u) {
        snprintf(
            failure,
            sizeof(failure),
            "%s",
            "mesh_prefix_overflow");
        goto invalid;
    }

    resources =
        (XzStaticMeshResource *)calloc(
            (size_t)scene.mesh_count,
            sizeof(*resources));

    if (!resources) {
        snprintf(
            failure,
            sizeof(failure),
            "%s",
            "mesh_resource_alloc_failed");
        goto invalid;
    }

    for (mesh_index = 0u;
         mesh_index < scene.mesh_count;
         ++mesh_index) {
        XzStaticMeshResource *resource =
            &resources[mesh_index];
        XzXzmeshStatus mesh_status;
        uint32_t submesh_index;

        if (!XzXzscene_ReadMeshPath(
                &scene,
                mesh_index,
                resource->path,
                sizeof(resource->path))) {
            snprintf(
                failure,
                sizeof(failure),
                "%s",
                "mesh_path_read_failed");
            goto invalid;
        }

        if (!XzHasPrefix(
                resource->path,
                mesh_prefix)) {
            snprintf(
                failure,
                sizeof(failure),
                "%s",
                "mesh_path_cross_map");
            goto invalid;
        }

        read_status = XzReadVfsFile(
            resource->path,
            XZ_STATIC_SCENE_MAX_MESH_BYTES,
            &resource->data,
            &resource->bytes);

        if (read_status <= 0) {
            snprintf(
                failure,
                sizeof(failure),
                "mesh_%u_%s",
                (unsigned int)mesh_index,
                read_status == 0
                    ? "missing"
                    : "read_failed");
            goto invalid;
        }

        mesh_status = XzXzmesh_Parse(
            &resource->mesh,
            resource->data,
            resource->bytes);

        if (mesh_status != XZ_XZMS_OK) {
            snprintf(
                failure,
                sizeof(failure),
                "mesh_%u_xzms_%s",
                (unsigned int)mesh_index,
                XzXzmesh_StatusName(
                    mesh_status));
            goto invalid;
        }

        /*
         * The source conversion proved all 492 Nacht submeshes carry normals
         * and UV0. Preserve that as a runtime requirement instead of silently
         * accepting a downgraded geometry payload.
         */
        for (submesh_index = 0u;
             submesh_index <
                 resource->mesh.submesh_count;
             ++submesh_index) {
            XzXzmeshSubmesh submesh;

            if (!XzXzmesh_ReadSubmesh(
                    &resource->mesh,
                    submesh_index,
                    &submesh) ||
                (submesh.attribute_flags &
                 (XZ_XZMS_ATTR_POSITION |
                  XZ_XZMS_ATTR_NORMAL |
                  XZ_XZMS_ATTR_UV0)) !=
                    (XZ_XZMS_ATTR_POSITION |
                     XZ_XZMS_ATTR_NORMAL |
                     XZ_XZMS_ATTR_UV0)) {
                snprintf(
                    failure,
                    sizeof(failure),
                    "%s",
                    "mesh_attributes_incomplete");
                goto invalid;
            }
        }

        mesh_bytes_total +=
            (uint64_t)resource->bytes;
        vertex_total +=
            (uint64_t)resource->mesh.vertex_count;
        index_total +=
            (uint64_t)resource->mesh.index_count;
        submesh_total +=
            (uint64_t)resource->mesh.submesh_count;
    }

    if (snprintf(
            material_path,
            sizeof(material_path),
            "xziel/maps/%s/materials.xzmt",
            map_id) <= 0 ||
        strlen(material_path) >=
            sizeof(material_path) - 1u) {
        snprintf(
            failure,
            sizeof(failure),
            "%s",
            "material_path_overflow");
        goto invalid;
    }

    read_status = XzReadVfsFile(
        material_path,
        XZ_STATIC_SCENE_MAX_MATERIAL_BYTES,
        &material_data,
        &material_bytes);

    if (read_status <= 0) {
        snprintf(
            failure,
            sizeof(failure),
            "%s",
            read_status == 0
                ? "material_table_missing"
                : "material_table_read_failed");
        goto invalid;
    }

    {
        XzXzmaterialStatus material_status =
            XzXzmaterial_Parse(
                &materials,
                material_data,
                material_bytes);

        if (material_status != XZ_XZMT_OK) {
            snprintf(
                failure,
                sizeof(failure),
                "xzmaterial_%s",
                XzXzmaterial_StatusName(
                    material_status));
            goto invalid;
        }
    }

    if (materials.mesh_count !=
            scene.mesh_count ||
        (uint64_t)materials.binding_count !=
            submesh_total ||
        materials.texture_count >
            XZ_STATIC_SCENE_MAX_TEXTURE_COUNT) {
        snprintf(
            failure,
            sizeof(failure),
            "%s",
            "material_scene_count_mismatch");
        goto invalid;
    }

    for (mesh_index = 0u;
         mesh_index < scene.mesh_count;
         ++mesh_index) {
        XzXzmaterialMeshSpan span;

        if (!XzXzmaterial_ReadMeshSpan(
                &materials,
                mesh_index,
                &span) ||
            span.binding_count !=
                resources[mesh_index].mesh.submesh_count) {
            snprintf(
                failure,
                sizeof(failure),
                "material_mesh_%u_span_mismatch",
                (unsigned int)mesh_index);
            goto invalid;
        }
    }

    if (materials.texture_count > 0u) {
        texture_resources =
            (XzStaticTextureResource *)calloc(
                (size_t)materials.texture_count,
                sizeof(*texture_resources));

        if (!texture_resources) {
            snprintf(
                failure,
                sizeof(failure),
                "%s",
                "texture_resource_alloc_failed");
            goto invalid;
        }
    }

    for (texture_index = 0u;
         texture_index < materials.texture_count;
         ++texture_index) {
        XzStaticTextureResource *texture_resource =
            &texture_resources[texture_index];
        XzXztextureStatus texture_status;

        if (snprintf(
                texture_path,
                sizeof(texture_path),
                "xziel/maps/%s/textures/t%04u.xzt",
                map_id,
                (unsigned int)texture_index) <= 0 ||
            strlen(texture_path) >=
                sizeof(texture_path) - 1u) {
            snprintf(
                failure,
                sizeof(failure),
                "%s",
                "texture_path_overflow");
            goto invalid;
        }

        snprintf(
            texture_resource->path,
            sizeof(texture_resource->path),
            "%s",
            texture_path);

        read_status = XzReadVfsFile(
            texture_path,
            XZ_STATIC_SCENE_MAX_TEXTURE_BYTES,
            &texture_resource->data,
            &texture_resource->bytes);

        if (read_status <= 0) {
            snprintf(
                failure,
                sizeof(failure),
                "texture_%u_%s",
                (unsigned int)texture_index,
                read_status == 0
                    ? "missing"
                    : "read_failed");
            goto invalid;
        }

        texture_status = XzXztexture_Parse(
            &texture_resource->texture,
            texture_resource->data,
            texture_resource->bytes);

        if (texture_status != XZ_XZTX_OK) {
            snprintf(
                failure,
                sizeof(failure),
                "texture_%u_xztx_%s",
                (unsigned int)texture_index,
                XzXztexture_StatusName(
                    texture_status));
            goto invalid;
        }

        if (strcmp(
                map_id,
                "xziel_nacht_bo3") == 0 &&
            (texture_resource->texture.width > 256u ||
             texture_resource->texture.height > 256u)) {
            snprintf(
                failure,
                sizeof(failure),
                "texture_%u_mobile_mip_exceeded",
                (unsigned int)texture_index);
            goto invalid;
        }

        texture_bytes_total +=
            (uint64_t)texture_resource->bytes;
    }

    state->scene_data = scene_data;
    state->scene_bytes = scene_bytes;
    state->scene = scene;
    state->mesh_resources = resources;
    state->mesh_resource_count =
        scene.mesh_count;
    state->material_data =
        material_data;
    state->material_bytes =
        material_bytes;
    state->materials =
        materials;
    state->texture_resources =
        texture_resources;
    state->texture_resource_count =
        materials.texture_count;
    state->mesh_files_validated =
        scene.mesh_count;
    state->mesh_bytes_validated =
        mesh_bytes_total;
    state->vertex_count =
        vertex_total;
    state->index_count =
        index_total;
    state->submesh_count =
        submesh_total;
    state->material_bindings_validated =
        materials.binding_count;
    state->texture_files_validated =
        materials.texture_count;
    state->texture_bytes_validated =
        texture_bytes_total;
    state->status =
        XZ_STATIC_SCENE_READY;
    state->error[0] = '\0';

    return state->status;

invalid:
    XzFreeTextureResources(
        texture_resources,
        materials.texture_count);
    free(material_data);
    XzFreeMeshResources(
        resources,
        scene.mesh_count);
    free(scene_data);

    state->status =
        XZ_STATIC_SCENE_INVALID;
    XzSetError(
        state,
        failure[0]
            ? failure
            : "unknown_static_scene_failure");
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

const XzStaticMeshResource *
XzStaticSceneRuntime_Mesh(
    const XzStaticSceneRuntimeState *state,
    uint32_t mesh_index)
{
    if (!state ||
        state->status !=
            XZ_STATIC_SCENE_READY ||
        !state->mesh_resources ||
        mesh_index >=
            state->mesh_resource_count)
        return NULL;

    return &state->mesh_resources[mesh_index];
}

uint32_t XzStaticSceneRuntime_MeshCount(
    const XzStaticSceneRuntimeState *state)
{
    if (!state ||
        state->status !=
            XZ_STATIC_SCENE_READY ||
        !state->mesh_resources)
        return 0u;

    return state->mesh_resource_count;
}

const XzXzmaterialView *
XzStaticSceneRuntime_Materials(
    const XzStaticSceneRuntimeState *state)
{
    if (!state ||
        state->status !=
            XZ_STATIC_SCENE_READY ||
        !state->material_data)
        return NULL;

    return &state->materials;
}

const XzStaticTextureResource *
XzStaticSceneRuntime_Texture(
    const XzStaticSceneRuntimeState *state,
    uint32_t texture_index)
{
    if (!state ||
        state->status !=
            XZ_STATIC_SCENE_READY ||
        !state->texture_resources ||
        texture_index >=
            state->texture_resource_count)
        return NULL;

    return &state->texture_resources[
        texture_index];
}

uint32_t XzStaticSceneRuntime_TextureCount(
    const XzStaticSceneRuntimeState *state)
{
    if (!state ||
        state->status !=
            XZ_STATIC_SCENE_READY)
        return 0u;

    return state->texture_resource_count;
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
