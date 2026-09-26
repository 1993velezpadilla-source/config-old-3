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
    (128u * 1024u * 1024u)

#define XZ_XZMT_HEADER_BYTES 28u
#define XZ_XZMT_TEXTURE_BYTES 8u
#define XZ_XZMT_BINDING_BYTES 16u
#define XZ_XZMT_VERSION 1u
#define XZ_XZTX_HEADER_BYTES 24u
#define XZ_XZTX_VERSION 1u
#define XZ_XZTX_FORMAT_RGBA8 1u

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

static int XzSafeRuntimeTexturePath(
    const char *path,
    const char *prefix)
{
    const unsigned char *p =
        (const unsigned char *)path;

    if (!path || !path[0] ||
        !prefix || !XzHasPrefix(path, prefix))
        return 0;

    while (*p) {
        unsigned char c = *p++;
        if (!((c >= 'a' && c <= 'z') ||
              (c >= 'A' && c <= 'Z') ||
              (c >= '0' && c <= '9') ||
              c == '_' || c == '-' ||
              c == '.' || c == '/'))
            return 0;
    }

    if (strstr(path, "/../") ||
        strstr(path, "/./") ||
        strstr(path, "//"))
        return 0;

    return 1;
}

static int XzLoadMaterialTable(
    const char *map_id,
    uint32_t mesh_count,
    XzStaticTextureResource **textures_out,
    uint32_t *texture_count_out,
    XzStaticMaterialBinding **bindings_out,
    uint32_t *binding_count_out,
    uint32_t *textured_binding_count_out)
{
    unsigned char *data = NULL;
    size_t bytes = 0u;
    char table_path[256];
    char texture_prefix[192];
    XzStaticTextureResource *textures = NULL;
    XzStaticMaterialBinding *bindings = NULL;
    uint32_t version;
    uint32_t table_mesh_count;
    uint32_t texture_count;
    uint32_t binding_count;
    uint32_t string_bytes;
    uint32_t reserved;
    size_t texture_records_at;
    size_t binding_records_at;
    size_t strings_at;
    uint32_t i;
    uint32_t textured = 0u;
    int read_status;

    if (!textures_out || !texture_count_out ||
        !bindings_out || !binding_count_out ||
        !textured_binding_count_out)
        return -1;

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

    if (snprintf(
            texture_prefix, sizeof(texture_prefix),
            "xziel/maps/%s/textures/",
            map_id) <= 0 ||
        strlen(texture_prefix) >= sizeof(texture_prefix) - 1u)
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
    table_mesh_count = XzReadU32Le(data + 8u);
    texture_count = XzReadU32Le(data + 12u);
    binding_count = XzReadU32Le(data + 16u);
    string_bytes = XzReadU32Le(data + 20u);
    reserved = XzReadU32Le(data + 24u);

    if (version != XZ_XZMT_VERSION ||
        table_mesh_count != mesh_count ||
        texture_count > 4096u ||
        binding_count == 0u ||
        binding_count > 65536u ||
        reserved != 0u)
        goto invalid;

    texture_records_at = XZ_XZMT_HEADER_BYTES;
    binding_records_at =
        texture_records_at +
        (size_t)texture_count *
            XZ_XZMT_TEXTURE_BYTES;
    strings_at =
        binding_records_at +
        (size_t)binding_count *
            XZ_XZMT_BINDING_BYTES;

    if (binding_records_at < texture_records_at ||
        strings_at < binding_records_at ||
        strings_at + (size_t)string_bytes != bytes)
        goto invalid;

    if (texture_count > 0u) {
        textures =
            (XzStaticTextureResource *)calloc(
                texture_count,
                sizeof(*textures));
        if (!textures)
            goto invalid;
    }

    bindings =
        (XzStaticMaterialBinding *)calloc(
            binding_count,
            sizeof(*bindings));
    if (!bindings)
        goto invalid;

    for (i = 0u; i < texture_count; ++i) {
        const unsigned char *record =
            data + texture_records_at +
            (size_t)i * XZ_XZMT_TEXTURE_BYTES;
        uint32_t offset =
            XzReadU32Le(record);
        uint32_t length =
            XzReadU32Le(record + 4u);

        if (length == 0u ||
            length >= XZ_STATIC_TEXTURE_PATH_BYTES ||
            offset > string_bytes ||
            length > string_bytes - offset)
            goto invalid;

        memcpy(
            textures[i].path,
            data + strings_at + offset,
            length);
        textures[i].path[length] = '\0';

        if (!XzSafeRuntimeTexturePath(
                textures[i].path,
                texture_prefix))
            goto invalid;
    }

    for (i = 0u; i < binding_count; ++i) {
        const unsigned char *record =
            data + binding_records_at +
            (size_t)i * XZ_XZMT_BINDING_BYTES;
        XzStaticMaterialBinding *binding =
            &bindings[i];

        binding->mesh_index =
            XzReadU32Le(record);
        binding->material_index =
            XzReadU32Le(record + 4u);
        binding->diffuse_texture_index =
            XzReadU32Le(record + 8u);
        binding->flags =
            XzReadU32Le(record + 12u);

        if (binding->mesh_index >= mesh_count ||
            (binding->diffuse_texture_index !=
                 XZ_STATIC_MATERIAL_NO_TEXTURE &&
             binding->diffuse_texture_index >=
                 texture_count))
            goto invalid;

        if (binding->diffuse_texture_index !=
                XZ_STATIC_MATERIAL_NO_TEXTURE)
            textured++;
    }

    free(data);
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

    free(state->material_bindings);
    free(state->textures);

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
    XzStaticTextureResource *textures = NULL;
    XzStaticMaterialBinding *material_bindings = NULL;
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
        scene.mesh_count,
        &textures,
        &texture_count,
        &material_bindings,
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
    state->textures = textures;
    state->texture_count = texture_count;
    state->material_bindings =
        material_bindings;
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
    free(material_bindings);
    free(textures);
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
    uint32_t material_index)
{
    uint32_t i;

    if (!state ||
        state->status != XZ_STATIC_SCENE_READY ||
        !state->material_bindings)
        return XZ_STATIC_MATERIAL_NO_TEXTURE;

    for (i = 0u;
         i < state->material_binding_count;
         ++i) {
        const XzStaticMaterialBinding *binding =
            &state->material_bindings[i];

        if (binding->mesh_index == mesh_index &&
            binding->material_index == material_index)
            return binding->diffuse_texture_index;
    }

    return XZ_STATIC_MATERIAL_NO_TEXTURE;
}

const char *XzStaticSceneRuntime_TexturePath(
    const XzStaticSceneRuntimeState *state,
    uint32_t texture_index)
{
    if (!state ||
        state->status != XZ_STATIC_SCENE_READY ||
        !state->textures ||
        texture_index >= state->texture_count)
        return NULL;

    return state->textures[texture_index].path;
}

int XzStaticSceneRuntime_LoadTextureRgba(
    const XzStaticSceneRuntimeState *state,
    uint32_t texture_index,
    unsigned char **out_pixels,
    uint32_t *out_width,
    uint32_t *out_height)
{
    unsigned char *file_data = NULL;
    unsigned char *pixels = NULL;
    size_t file_bytes = 0u;
    uint32_t version;
    uint32_t width;
    uint32_t height;
    uint32_t format;
    uint32_t rgba_bytes;
    uint64_t expected_bytes;
    int read_status;

    if (out_pixels)
        *out_pixels = NULL;
    if (out_width)
        *out_width = 0u;
    if (out_height)
        *out_height = 0u;

    if (!state ||
        state->status != XZ_STATIC_SCENE_READY ||
        !out_pixels || !out_width || !out_height ||
        !state->textures ||
        texture_index >= state->texture_count)
        return 0;

    read_status = XzReadVfsFile(
        state->textures[texture_index].path,
        XZ_STATIC_SCENE_MAX_TEXTURE_BYTES,
        &file_data,
        &file_bytes);

    if (read_status != 1 ||
        file_bytes < XZ_XZTX_HEADER_BYTES ||
        memcmp(file_data, "XZTX", 4u) != 0) {
        free(file_data);
        return 0;
    }

    version = XzReadU32Le(file_data + 4u);
    width = XzReadU32Le(file_data + 8u);
    height = XzReadU32Le(file_data + 12u);
    format = XzReadU32Le(file_data + 16u);
    rgba_bytes = XzReadU32Le(file_data + 20u);

    expected_bytes =
        (uint64_t)width *
        (uint64_t)height * 4u;

    if (version != XZ_XZTX_VERSION ||
        format != XZ_XZTX_FORMAT_RGBA8 ||
        width == 0u || height == 0u ||
        width > 8192u || height > 8192u ||
        expected_bytes > UINT32_MAX ||
        rgba_bytes != (uint32_t)expected_bytes ||
        file_bytes !=
            XZ_XZTX_HEADER_BYTES +
            (size_t)rgba_bytes) {
        free(file_data);
        return 0;
    }

    pixels =
        (unsigned char *)malloc(
            (size_t)rgba_bytes);
    if (!pixels) {
        free(file_data);
        return 0;
    }

    memcpy(
        pixels,
        file_data + XZ_XZTX_HEADER_BYTES,
        rgba_bytes);
    free(file_data);

    *out_pixels = pixels;
    *out_width = width;
    *out_height = height;
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
