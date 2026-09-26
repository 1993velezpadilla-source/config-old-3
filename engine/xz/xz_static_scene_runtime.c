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
    (256u * 1024u * 1024u)

#define XZ_XZMT_HEADER_BYTES 24u
#define XZ_XZMT_TEXTURE_BYTES 20u
#define XZ_XZMT_BINDING_BYTES 4u
#define XZ_XZMT_VERSION 1u
#define XZ_XZMT_FORMAT_RGBA8_BASECOLOR 1u

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

static uint32_t XzReadU32Le(
    const unsigned char *p)
{
    return
        (uint32_t)p[0] |
        ((uint32_t)p[1] << 8) |
        ((uint32_t)p[2] << 16) |
        ((uint32_t)p[3] << 24);
}

static int XzLoadMaterialTable(
    const char *map_id,
    uint64_t expected_binding_count,
    unsigned char **material_data_out,
    size_t *material_bytes_out,
    XzStaticTextureResource **textures_out,
    uint32_t *texture_count_out,
    uint32_t **bindings_out,
    uint32_t *binding_count_out,
    uint32_t *textured_binding_count_out)
{
    unsigned char *data = NULL;
    size_t bytes = 0u;
    char table_path[256];
    XzStaticTextureResource *textures = NULL;
    uint32_t *bindings = NULL;
    uint32_t version;
    uint32_t texture_count;
    uint32_t binding_count;
    uint32_t texture_record_bytes;
    uint32_t residency_format;
    size_t texture_records_at;
    size_t binding_records_at;
    size_t texture_data_at;
    uint32_t i;
    uint32_t textured = 0u;
    int read_status;

    if (!material_data_out ||
        !material_bytes_out ||
        !textures_out ||
        !texture_count_out ||
        !bindings_out ||
        !binding_count_out ||
        !textured_binding_count_out)
        return -1;

    *material_data_out = NULL;
    *material_bytes_out = 0u;
    *textures_out = NULL;
    *texture_count_out = 0u;
    *bindings_out = NULL;
    *binding_count_out = 0u;
    *textured_binding_count_out = 0u;

    if (snprintf(
            table_path, sizeof(table_path),
            "xziel/maps/%s/materials.xzmt",
            map_id) <= 0 ||
        strlen(table_path) >= sizeof(table_path) - 1u)
        return -1;

    read_status = XzReadVfsFile(
        table_path,
        XZ_STATIC_SCENE_MAX_MATERIAL_BYTES,
        &data,
        &bytes);

    if (read_status <= 0)
        return read_status;

    if (bytes < XZ_XZMT_HEADER_BYTES ||
        memcmp(data, "XZMT", 4u) != 0)
        goto invalid;

    version = XzReadU32Le(data + 4u);
    texture_count = XzReadU32Le(data + 8u);
    binding_count = XzReadU32Le(data + 12u);
    texture_record_bytes = XzReadU32Le(data + 16u);
    residency_format = XzReadU32Le(data + 20u);

    if (version != XZ_XZMT_VERSION ||
        texture_record_bytes != XZ_XZMT_TEXTURE_BYTES ||
        residency_format != XZ_XZMT_FORMAT_RGBA8_BASECOLOR ||
        texture_count == 0u ||
        texture_count > 4096u ||
        binding_count == 0u ||
        binding_count > 65536u ||
        expected_binding_count > UINT32_MAX ||
        binding_count != (uint32_t)expected_binding_count)
        goto invalid;

    texture_records_at = XZ_XZMT_HEADER_BYTES;
    binding_records_at =
        texture_records_at +
        (size_t)texture_count *
            XZ_XZMT_TEXTURE_BYTES;
    texture_data_at =
        binding_records_at +
        (size_t)binding_count *
            XZ_XZMT_BINDING_BYTES;

    if (binding_records_at < texture_records_at ||
        texture_data_at < binding_records_at ||
        texture_data_at > bytes)
        goto invalid;

    textures =
        (XzStaticTextureResource *)calloc(
            texture_count,
            sizeof(*textures));
    bindings =
        (uint32_t *)calloc(
            binding_count,
            sizeof(*bindings));

    if (!textures || !bindings)
        goto invalid;

    for (i = 0u; i < texture_count; ++i) {
        const unsigned char *record =
            data + texture_records_at +
            (size_t)i * XZ_XZMT_TEXTURE_BYTES;
        XzStaticTextureResource *texture =
            &textures[i];
        uint64_t expected_bytes;
        uint64_t end_offset;

        texture->width =
            XzReadU32Le(record);
        texture->height =
            XzReadU32Le(record + 4u);
        texture->data_offset =
            XzReadU32Le(record + 8u);
        texture->data_bytes =
            XzReadU32Le(record + 12u);
        texture->format =
            XzReadU32Le(record + 16u);

        expected_bytes =
            (uint64_t)texture->width *
            (uint64_t)texture->height * 4u;
        end_offset =
            (uint64_t)texture->data_offset +
            (uint64_t)texture->data_bytes;

        if (texture->width == 0u ||
            texture->height == 0u ||
            texture->width > 4096u ||
            texture->height > 4096u ||
            texture->format !=
                XZ_XZMT_FORMAT_RGBA8_BASECOLOR ||
            expected_bytes > UINT32_MAX ||
            texture->data_bytes !=
                (uint32_t)expected_bytes ||
            texture->data_offset < texture_data_at ||
            end_offset > bytes)
            goto invalid;
    }

    for (i = 0u; i < binding_count; ++i) {
        uint32_t texture_index =
            XzReadU32Le(
                data + binding_records_at +
                (size_t)i *
                    XZ_XZMT_BINDING_BYTES);

        if (texture_index !=
                XZ_STATIC_MATERIAL_NO_TEXTURE &&
            texture_index >= texture_count)
            goto invalid;

        bindings[i] = texture_index;
        if (texture_index !=
                XZ_STATIC_MATERIAL_NO_TEXTURE)
            textured++;
    }

    *material_data_out = data;
    *material_bytes_out = bytes;
    *textures_out = textures;
    *texture_count_out = texture_count;
    *bindings_out = bindings;
    *binding_count_out = binding_count;
    *textured_binding_count_out = textured;
    return 1;

invalid:
    free(bindings);
    free(textures);
    free(data);
    return -1;
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

    if (state->scene_data)
        free(state->scene_data);

    free(state->submesh_texture_indices);
    free(state->textures);
    free(state->material_data);

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
    unsigned char *material_data = NULL;
    size_t material_bytes = 0u;
    XzStaticTextureResource *textures = NULL;
    uint32_t *submesh_texture_indices = NULL;
    uint32_t texture_count = 0u;
    uint32_t material_binding_count = 0u;
    uint32_t textured_material_bindings = 0u;
    char scene_path[256];
    char mesh_prefix[160];
    char failure[128] = "";
    uint32_t mesh_index;
    uint64_t mesh_bytes_total = 0u;
    uint64_t vertex_total = 0u;
    uint64_t index_total = 0u;
    uint64_t submesh_total = 0u;
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

    read_status = XzLoadMaterialTable(
        map_id,
        submesh_total,
        &material_data,
        &material_bytes,
        &textures,
        &texture_count,
        &submesh_texture_indices,
        &material_binding_count,
        &textured_material_bindings);

    if (read_status < 0 ||
        (strcmp(map_id, "xziel_nacht_bo3") == 0 &&
         read_status != 1)) {
        snprintf(
            failure,
            sizeof(failure),
            "%s",
            read_status == 0
                ? "materials_not_present"
                : "materials_invalid");
        goto invalid;
    }

    state->scene_data = scene_data;
    state->scene_bytes = scene_bytes;
    state->scene = scene;
    state->mesh_resources = resources;
    state->mesh_resource_count =
        scene.mesh_count;
    state->material_data = material_data;
    state->material_bytes = material_bytes;
    state->textures = textures;
    state->texture_count = texture_count;
    state->submesh_texture_indices =
        submesh_texture_indices;
    state->material_binding_count =
        material_binding_count;
    state->textured_material_bindings =
        textured_material_bindings;
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
    state->status =
        XZ_STATIC_SCENE_READY;
    state->error[0] = '\0';

    return state->status;

invalid:
    XzFreeMeshResources(
        resources,
        scene.mesh_count);
    free(submesh_texture_indices);
    free(textures);
    free(material_data);
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

uint32_t XzStaticSceneRuntime_TextureCount(
    const XzStaticSceneRuntimeState *state)
{
    if (!state ||
        state->status != XZ_STATIC_SCENE_READY)
        return 0u;
    return state->texture_count;
}

uint32_t XzStaticSceneRuntime_MaterialBindingCount(
    const XzStaticSceneRuntimeState *state)
{
    if (!state ||
        state->status != XZ_STATIC_SCENE_READY)
        return 0u;
    return state->material_binding_count;
}

uint32_t XzStaticSceneRuntime_DiffuseTextureIndex(
    const XzStaticSceneRuntimeState *state,
    uint32_t mesh_index,
    uint32_t submesh_index)
{
    uint64_t ordinal = 0u;
    uint32_t i;

    if (!state ||
        state->status != XZ_STATIC_SCENE_READY ||
        !state->mesh_resources ||
        !state->submesh_texture_indices ||
        mesh_index >= state->mesh_resource_count ||
        submesh_index >=
            state->mesh_resources[
                mesh_index].mesh.submesh_count)
        return XZ_STATIC_MATERIAL_NO_TEXTURE;

    for (i = 0u; i < mesh_index; ++i)
        ordinal +=
            state->mesh_resources[i].mesh.submesh_count;

    ordinal += submesh_index;

    if (ordinal >= state->material_binding_count)
        return XZ_STATIC_MATERIAL_NO_TEXTURE;

    return state->submesh_texture_indices[
        (uint32_t)ordinal];
}

int XzStaticSceneRuntime_LoadTextureRgba(
    const XzStaticSceneRuntimeState *state,
    uint32_t texture_index,
    unsigned char **out_pixels,
    uint32_t *out_width,
    uint32_t *out_height)
{
    const XzStaticTextureResource *texture;
    unsigned char *pixels;
    uint64_t end_offset;

    if (out_pixels)
        *out_pixels = NULL;
    if (out_width)
        *out_width = 0u;
    if (out_height)
        *out_height = 0u;

    if (!state ||
        state->status != XZ_STATIC_SCENE_READY ||
        !out_pixels || !out_width || !out_height ||
        !state->material_data ||
        !state->textures ||
        texture_index >= state->texture_count)
        return 0;

    texture =
        &state->textures[texture_index];

    end_offset =
        (uint64_t)texture->data_offset +
        (uint64_t)texture->data_bytes;

    if (texture->format !=
            XZ_XZMT_FORMAT_RGBA8_BASECOLOR ||
        texture->data_bytes == 0u ||
        end_offset > state->material_bytes)
        return 0;

    pixels =
        (unsigned char *)malloc(
            texture->data_bytes);
    if (!pixels)
        return 0;

    memcpy(
        pixels,
        state->material_data +
            texture->data_offset,
        texture->data_bytes);

    *out_pixels = pixels;
    *out_width = texture->width;
    *out_height = texture->height;
    return 1;
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
