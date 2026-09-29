#include "xz_static_scene_runtime.h"

#include <limits.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define XZ_STATIC_SCENE_MAX_SCENE_BYTES \
    (16u * 1024u * 1024u)

#define XZ_STATIC_SCENE_MAX_MESH_BYTES \
    (64u * 1024u * 1024u)

#define XZ_STATIC_SCENE_MAX_MATERIAL_BYTES \
    (384u * 1024u * 1024u)

#define XZ_STATIC_SCENE_MAX_MATERIAL_INSTANCE_BYTES \
    (16u * 1024u * 1024u)

#define XZ_STATIC_SCENE_MAX_MATERIAL_LIBRARY_BYTES \
    (64u * 1024u * 1024u)

#define XZ_STATIC_SCENE_MAX_NATIVE_TEXTURE_BYTES \
    (128u * 1024u * 1024u)

#define XZ_STATIC_SCENE_MAX_PBR_MATERIAL_BYTES \
    (64u * 1024u)

#define XZ_STATIC_SCENE_MAX_NORMAL_MATERIAL_BYTES \
    (256u * 1024u * 1024u)

#define XZ_STATIC_SCENE_MAX_ENVIRONMENT_BYTES \
    (256u * 1024u)

#define XZ_STATIC_SCENE_MAX_HEIGHT_FOG_BYTES \
    (4u * 1024u)

#define XZ_STATIC_SCENE_MAX_REFLECTION_BYTES \
    (2u * 1024u * 1024u)

#define XZ_XZRC_V1_HEADER_BYTES 64u
#define XZ_XZRC_V2_HEADER_BYTES 96u
#define XZ_XZRC_VERSION_MIN 1u
#define XZ_XZRC_VERSION_MAX 2u
#define XZ_XZRC_FACE_COUNT 6u
#define XZ_XZRC_FORMAT_RGBA16F 1u
#define XZ_XZRC_RGBA16F_BYTES_PER_TEXEL 8u

#define XZ_XZMT_HEADER_BYTES 24u
#define XZ_XZMT_TEXTURE_BYTES 20u
#define XZ_XZMT_VERSION 1u
#define XZ_XZMT_HEADER_FLAG_RGBA8 1u
#define XZ_XZMN_HEADER_BYTES 24u
#define XZ_XZMN_TEXTURE_BYTES 20u
#define XZ_XZMN_VERSION 1u
#define XZ_XZMN_FLAG_RGBA8_NORMAL 2u

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

extern void Sys_FileSeek(
    int handle,
    int position);

static uint32_t XzStaticReadU32Le(
    const unsigned char *p)
{
    return ((uint32_t)p[0]) |
           ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

static float XzStaticReadF32Le(
    const unsigned char *p)
{
    uint32_t bits = XzStaticReadU32Le(p);
    float value = 0.0f;
    memcpy(&value, &bits, sizeof(value));
    return value;
}

static int XzValidateReflectionPack(
    const unsigned char *data,
    size_t size,
    XzReflectionCaptureView *view)
{
    uint32_t version;
    uint32_t cubemap_size;
    uint32_t mip_count;
    uint32_t face_count;
    uint32_t pixel_format;
    uint32_t bytes_per_texel;
    uint32_t payload_offset;
    uint32_t payload_bytes;
    uint32_t expected_mips = 0u;
    uint32_t mip_size;
    uint64_t expected_payload = 0u;
    uint32_t mip;

    if (!data || !view ||
        size < XZ_XZRC_V1_HEADER_BYTES)
        return 0;

    if (data[0] != 'X' ||
        data[1] != 'Z' ||
        data[2] != 'R' ||
        data[3] != 'C')
        return 0;

    version = XzStaticReadU32Le(data + 4u);
    if (version < XZ_XZRC_VERSION_MIN ||
        version > XZ_XZRC_VERSION_MAX)
        return 0;

    cubemap_size = XzStaticReadU32Le(data + 8u);
    mip_count = XzStaticReadU32Le(data + 12u);
    face_count = XzStaticReadU32Le(data + 16u);
    pixel_format = XzStaticReadU32Le(data + 20u);
    bytes_per_texel = XzStaticReadU32Le(data + 24u);
    payload_offset = XzStaticReadU32Le(data + 28u);
    payload_bytes = XzStaticReadU32Le(data + 32u);

    if (cubemap_size == 0u ||
        (cubemap_size & (cubemap_size - 1u)) != 0u ||
        face_count != XZ_XZRC_FACE_COUNT ||
        pixel_format != XZ_XZRC_FORMAT_RGBA16F ||
        bytes_per_texel !=
            XZ_XZRC_RGBA16F_BYTES_PER_TEXEL ||
        payload_offset !=
            (version >= 2u
                ? XZ_XZRC_V2_HEADER_BYTES
                : XZ_XZRC_V1_HEADER_BYTES) ||
        payload_offset > size ||
        payload_bytes > size - payload_offset ||
        (size_t)payload_offset +
            (size_t)payload_bytes != size)
        return 0;

    mip_size = cubemap_size;
    while (mip_size > 0u) {
        expected_mips++;
        mip_size >>= 1u;
    }

    if (mip_count != expected_mips)
        return 0;

    for (mip = 0u; mip < mip_count; ++mip) {
        uint32_t edge = cubemap_size >> mip;
        expected_payload +=
            (uint64_t)edge *
            (uint64_t)edge *
            (uint64_t)face_count *
            (uint64_t)bytes_per_texel;
    }

    if (expected_payload !=
            (uint64_t)payload_bytes)
        return 0;

    memset(view, 0, sizeof(*view));
    view->payload = data + payload_offset;
    view->payload_bytes = payload_bytes;
    view->cubemap_size = cubemap_size;
    view->mip_count = mip_count;
    view->face_count = face_count;
    view->pixel_format = pixel_format;
    view->bytes_per_texel = bytes_per_texel;
    view->asset_version = version;
    view->average_brightness =
        XzStaticReadF32Le(data + 36u);
    view->brightness =
        XzStaticReadF32Le(data + 40u);
    memcpy(
        view->map_build_data_id,
        data + 44u,
        sizeof(view->map_build_data_id));

    if (version >= 2u) {
        view->capture_position_meters[0] =
            XzStaticReadF32Le(data + 64u);
        view->capture_position_meters[1] =
            XzStaticReadF32Le(data + 68u);
        view->capture_position_meters[2] =
            XzStaticReadF32Le(data + 72u);
        view->influence_radius_meters =
            XzStaticReadF32Le(data + 76u);
        view->capture_offset_meters[0] =
            XzStaticReadF32Le(data + 80u);
        view->capture_offset_meters[1] =
            XzStaticReadF32Le(data + 84u);
        view->capture_offset_meters[2] =
            XzStaticReadF32Le(data + 88u);
        view->shape =
            XzStaticReadU32Le(data + 92u);
    }

    if (!isfinite(view->average_brightness) ||
        view->average_brightness <= 0.0f ||
        !isfinite(view->brightness) ||
        view->brightness <= 0.0f)
        return 0;

    if (version >= 2u) {
        uint32_t axis;
        if (view->shape !=
                XZ_REFLECTION_SHAPE_SPHERE ||
            !isfinite(
                view->influence_radius_meters) ||
            view->influence_radius_meters <= 0.0f)
            return 0;

        for (axis = 0u; axis < 3u; ++axis) {
            if (!isfinite(
                    view->capture_position_meters[axis]) ||
                !isfinite(
                    view->capture_offset_meters[axis]))
                return 0;
        }
    }

    return 1;
}

static int XzReadExactHandle(
    int handle,
    void *destination,
    size_t bytes)
{
    unsigned char *out =
        (unsigned char *)destination;
    size_t cursor = 0u;

    while (cursor < bytes) {
        size_t remaining = bytes - cursor;
        int request =
            remaining > (size_t)INT_MAX
                ? INT_MAX
                : (int)remaining;
        int got = Sys_FileRead(
            handle,
            out + cursor,
            request);

        if (got <= 0 || got > request)
            return 0;

        cursor += (size_t)got;
    }

    return 1;
}

static int XzOpenStreamedTexturePack(
    const char *path,
    const char magic[4],
    uint32_t expected_header_flags,
    uint32_t expected_texture_flags,
    uint32_t expected_bindings,
    int *out_handle,
    unsigned char **out_table_data,
    size_t *out_file_bytes,
    uint32_t *out_texture_count,
    uint32_t *out_binding_count,
    size_t *out_texture_table_offset,
    size_t *out_binding_offset)
{
    unsigned char header[24];
    int handle = -1;
    int length;
    uint32_t textures;
    uint32_t bindings;
    uint32_t entry_bytes;
    uint32_t flags;
    uint64_t table_end;
    uint64_t bindings_end;
    unsigned char *table_data = NULL;
    uint32_t i;

    if (!path || !magic ||
        !out_handle || !out_table_data ||
        !out_file_bytes ||
        !out_texture_count ||
        !out_binding_count ||
        !out_texture_table_offset ||
        !out_binding_offset)
        return -1;

    *out_handle = -1;
    *out_table_data = NULL;
    *out_file_bytes = 0u;

    length = COM_OpenFile(
        (char *)path,
        &handle);

    if (length < 0 || handle < 0)
        return 0;

    if (length < (int)sizeof(header) ||
        !XzReadExactHandle(
            handle,
            header,
            sizeof(header))) {
        COM_CloseFile(handle);
        return -1;
    }

    if (memcmp(header, magic, 4u) != 0 ||
        XzStaticReadU32Le(header + 4u) != 1u) {
        COM_CloseFile(handle);
        return -1;
    }

    textures = XzStaticReadU32Le(header + 8u);
    bindings = XzStaticReadU32Le(header + 12u);
    entry_bytes = XzStaticReadU32Le(header + 16u);
    flags = XzStaticReadU32Le(header + 20u);

    if (textures == 0u ||
        bindings == 0u ||
        bindings != expected_bindings ||
        entry_bytes != 20u ||
        flags != expected_header_flags) {
        COM_CloseFile(handle);
        return -1;
    }

    table_end =
        24u +
        (uint64_t)textures * 20u;
    bindings_end =
        table_end +
        (uint64_t)bindings * 4u;

    if (bindings_end > (uint64_t)length ||
        bindings_end > (uint64_t)SIZE_MAX) {
        COM_CloseFile(handle);
        return -1;
    }

    table_data =
        (unsigned char *)malloc(
            (size_t)bindings_end);
    if (!table_data) {
        COM_CloseFile(handle);
        return -1;
    }

    memcpy(table_data, header, sizeof(header));

    if (!XzReadExactHandle(
            handle,
            table_data + sizeof(header),
            (size_t)bindings_end -
                sizeof(header))) {
        free(table_data);
        COM_CloseFile(handle);
        return -1;
    }

    for (i = 0u; i < textures; ++i) {
        const unsigned char *entry =
            table_data + 24u +
            (size_t)i * 20u;
        uint32_t width =
            XzStaticReadU32Le(entry + 0u);
        uint32_t height =
            XzStaticReadU32Le(entry + 4u);
        uint32_t offset =
            XzStaticReadU32Le(entry + 8u);
        uint32_t bytes =
            XzStaticReadU32Le(entry + 12u);
        uint32_t texture_flags =
            XzStaticReadU32Le(entry + 16u);
        uint64_t expected_bytes =
            (uint64_t)width *
            (uint64_t)height * 4u;
        uint64_t end =
            (uint64_t)offset +
            (uint64_t)bytes;

        if (width == 0u ||
            height == 0u ||
            width > 4096u ||
            height > 4096u ||
            expected_bytes != (uint64_t)bytes ||
            (texture_flags &
                expected_texture_flags) !=
                expected_texture_flags ||
            (expected_header_flags == 2u &&
                texture_flags !=
                    expected_texture_flags) ||
            (expected_header_flags == 1u &&
                (texture_flags & ~3u) != 0u) ||
            (uint64_t)offset < bindings_end ||
            end > (uint64_t)length ||
            offset > (uint32_t)INT_MAX) {
            free(table_data);
            COM_CloseFile(handle);
            return -1;
        }
    }

    for (i = 0u; i < bindings; ++i) {
        uint32_t value =
            XzStaticReadU32Le(
                table_data +
                (size_t)table_end +
                (size_t)i * 4u);

        if (value !=
                XZ_STATIC_MATERIAL_NO_TEXTURE &&
            value >= textures) {
            free(table_data);
            COM_CloseFile(handle);
            return -1;
        }
    }

    *out_handle = handle;
    *out_table_data = table_data;
    *out_file_bytes = (size_t)length;
    *out_texture_count = textures;
    *out_binding_count = bindings;
    *out_texture_table_offset = 24u;
    *out_binding_offset = (size_t)table_end;
    return 1;
}

static int XzReadStreamedTexture(
    int handle,
    const unsigned char *table_data,
    size_t texture_table_offset,
    uint32_t texture_count,
    uint32_t texture_index,
    void *destination,
    size_t destination_bytes)
{
    const unsigned char *entry;
    uint32_t offset;
    uint32_t bytes;

    if (handle < 0 ||
        !table_data ||
        !destination ||
        texture_index >= texture_count)
        return 0;

    entry =
        table_data +
        texture_table_offset +
        (size_t)texture_index * 20u;
    offset =
        XzStaticReadU32Le(entry + 8u);
    bytes =
        XzStaticReadU32Le(entry + 12u);

    if (destination_bytes < (size_t)bytes ||
        offset > (uint32_t)INT_MAX)
        return 0;

    Sys_FileSeek(handle, (int)offset);
    return XzReadExactHandle(
        handle,
        destination,
        (size_t)bytes);
}

static int XzSafeAssetLeaf(
    const char *name,
    size_t length)
{
    size_t i;

    if (!name ||
        length == 0u ||
        length >= 128u)
        return 0;

    for (i = 0u; i < length; ++i) {
        const unsigned char c =
            (unsigned char)name[i];

        if (!((c >= 'a' && c <= 'z') ||
              (c >= 'A' && c <= 'Z') ||
              (c >= '0' && c <= '9') ||
              c == '_' ||
              c == '-' ||
              c == '.'))
            return 0;
    }

    return 1;
}

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

void XzStaticSceneRuntime_Init(
    XzStaticSceneRuntimeState *state)
{
    if (!state)
        return;

    memset(state, 0, sizeof(*state));
    state->material_file_handle = -1;
    state->normal_material_file_handle = -1;
    XzLightmapTexture_Init(
        &state->lightmaps);
    XzLightmapBinding_Init(
        &state->lightmap_bindings);
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

    if (state->material_file_handle >= 0)
        COM_CloseFile(
            state->material_file_handle);
    if (state->material_data)
        free(state->material_data);

    if (state->material_instance_data)
        free(state->material_instance_data);

    if (state->material_library_data)
        free(state->material_library_data);

    if (state->pbr_material_data)
        free(state->pbr_material_data);

    if (state->normal_material_file_handle >= 0)
        COM_CloseFile(
            state->normal_material_file_handle);
    if (state->normal_material_data)
        free(state->normal_material_data);

    if (state->environment_data)
        free(state->environment_data);

    if (state->height_fog_data)
        free(state->height_fog_data);

    if (state->reflection_data)
        free(state->reflection_data);

    XzLightmapTexture_Close(
        &state->lightmaps);
    XzLightmapBinding_Close(
        &state->lightmap_bindings);

    memset(state, 0, sizeof(*state));
    state->material_file_handle = -1;
    state->normal_material_file_handle = -1;
    XzLightmapTexture_Init(
        &state->lightmaps);
    XzLightmapBinding_Init(
        &state->lightmap_bindings);
    state->status = XZ_STATIC_SCENE_IDLE;
}

XzStaticSceneStatus XzStaticSceneRuntime_LoadMap(
    XzStaticSceneRuntimeState *state,
    const char *map_id)
{
    unsigned char *scene_data = NULL;
    size_t scene_bytes = 0u;
    unsigned char *material_data = NULL;
    size_t material_bytes = 0u;
    int material_file_handle = -1;
    unsigned char *material_instance_data = NULL;
    size_t material_instance_bytes = 0u;
    XzMaterialInstanceBindingView material_instances;
    unsigned char *material_library_data = NULL;
    size_t material_library_bytes = 0u;
    XzMaterialLibraryView material_library;
    unsigned char *pbr_material_data = NULL;
    size_t pbr_material_bytes = 0u;
    XzPbrMaterialView pbr_material;
    XzPbrMaterialStatus pbr_material_status;
    unsigned char *normal_material_data = NULL;
    size_t normal_material_bytes = 0u;
    int normal_material_file_handle = -1;
    unsigned char *environment_data = NULL;
    size_t environment_bytes = 0u;
    XzEnvironmentView environment;
    XzEnvironmentStatus environment_status;
    unsigned char *height_fog_data = NULL;
    size_t height_fog_bytes = 0u;
    XzHeightFogView height_fog;
    XzHeightFogStatus height_fog_status;
    unsigned char *reflection_data = NULL;
    size_t reflection_bytes = 0u;
    XzReflectionCaptureView reflection;
    XzLightmapTextureView lightmaps;
    XzLightmapTextureStatus lightmap_status;
    XzLightmapBindingView lightmap_bindings;
    XzLightmapBindingStatus lightmap_binding_status;
    XzXzsceneView scene;
    XzXzsceneStatus scene_status;
    XzStaticMeshResource *resources = NULL;
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
    char mesh_prefix[160];
    char failure[128] = "";
    uint32_t material_texture_count = 0u;
    uint32_t material_binding_count = 0u;
    size_t material_texture_table_offset = 0u;
    size_t material_binding_offset = 0u;
    uint32_t normal_texture_count = 0u;
    uint32_t normal_binding_count = 0u;
    size_t normal_texture_table_offset = 0u;
    size_t normal_binding_offset = 0u;
    uint32_t mesh_index;
    uint64_t mesh_bytes_total = 0u;
    uint64_t vertex_total = 0u;
    uint64_t index_total = 0u;
    uint64_t submesh_total = 0u;
    int read_status;

    XzLightmapTexture_Init(
        &lightmaps);
    XzLightmapBinding_Init(
        &lightmap_bindings);

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
         * Static-scene geometry has one source-agnostic baseline: positions,
         * normals, tangents and UV0. Additional UV channels are capabilities,
         * not a map-wide requirement. Systems that consume an authored extra
         * UV set (for example baked lightmaps) must validate that requirement
         * at their own binding boundary instead of rejecting otherwise valid
         * meshes during generic scene load.
         */
        for (submesh_index = 0u;
             submesh_index <
                 resource->mesh.submesh_count;
             ++submesh_index) {
            XzXzmeshSubmesh submesh;
            const uint32_t required_attributes =
                XZ_XZMS_ATTR_POSITION |
                XZ_XZMS_ATTR_NORMAL |
                XZ_XZMS_ATTR_TANGENT |
                XZ_XZMS_ATTR_UV0;

            if (!XzXzmesh_ReadSubmesh(
                    &resource->mesh,
                    submesh_index,
                    &submesh) ||
                (submesh.attribute_flags &
                 required_attributes) !=
                    required_attributes) {
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
            material_instance_path,
            sizeof(material_instance_path),
            "xziel/maps/%s/materials.xzmi",
            map_id) <= 0 ||
        strlen(material_instance_path) >=
            sizeof(material_instance_path) - 1u) {
        snprintf(
            failure,
            sizeof(failure),
            "%s",
            "material_instance_path_overflow");
        goto invalid;
    }

    read_status = XzReadVfsFile(
        material_instance_path,
        XZ_STATIC_SCENE_MAX_MATERIAL_INSTANCE_BYTES,
        &material_instance_data,
        &material_instance_bytes);

    if (read_status < 0) {
        snprintf(
            failure,
            sizeof(failure),
            "%s",
            "material_instance_read_failed");
        goto invalid;
    }

    if (read_status > 0) {
        XzMaterialInstanceBindingStatus material_instance_status;
        uint32_t instance_index;

        material_instance_status =
            XzMaterialInstanceBinding_Parse(
                &material_instances,
                material_instance_data,
                material_instance_bytes);

        if (material_instance_status != XZ_XZMI_OK) {
            snprintf(
                failure,
                sizeof(failure),
                "material_instance_%s",
                XzMaterialInstanceBinding_StatusName(
                    material_instance_status));
            goto invalid;
        }

        if (material_instances.instance_count !=
                scene.instance_count) {
            snprintf(
                failure,
                sizeof(failure),
                "%s",
                "material_instance_count_mismatch");
            goto invalid;
        }

        for (instance_index = 0u;
             instance_index < scene.instance_count;
             ++instance_index) {
            XzXzsceneInstance instance;
            XzMaterialInstanceRecord binding_record;

            if (!XzXzscene_ReadInstance(
                    &scene,
                    instance_index,
                    &instance) ||
                instance.mesh_index >= scene.mesh_count ||
                XzMaterialInstanceBinding_Instance(
                    &material_instances,
                    instance_index,
                    &binding_record) != XZ_XZMI_OK ||
                binding_record.binding_count !=
                    resources[instance.mesh_index]
                        .mesh.submesh_count) {
                snprintf(
                    failure,
                    sizeof(failure),
                    "%s",
                    "material_instance_submesh_mismatch");
                goto invalid;
            }
        }
    }

    if (snprintf(
            material_library_path,
            sizeof(material_library_path),
            "xziel/maps/%s/materials.xzml",
            map_id) <= 0 ||
        strlen(material_library_path) >=
            sizeof(material_library_path) - 1u) {
        snprintf(
            failure,
            sizeof(failure),
            "%s",
            "material_library_path_overflow");
        goto invalid;
    }

    read_status = XzReadVfsFile(
        material_library_path,
        XZ_STATIC_SCENE_MAX_MATERIAL_LIBRARY_BYTES,
        &material_library_data,
        &material_library_bytes);

    if (read_status < 0) {
        snprintf(
            failure,
            sizeof(failure),
            "%s",
            "material_library_read_failed");
        goto invalid;
    }

    if (read_status > 0) {
        XzMaterialLibraryStatus material_library_status =
            XzMaterialLibrary_Parse(
                &material_library,
                material_library_data,
                material_library_bytes);

        if (material_library_status != XZ_XZML_OK) {
            snprintf(
                failure,
                sizeof(failure),
                "material_library_%s",
                XzMaterialLibrary_StatusName(
                    material_library_status));
            goto invalid;
        }

        if (!material_instance_data) {
            snprintf(
                failure,
                sizeof(failure),
                "%s",
                "material_library_without_instances");
            goto invalid;
        }

        if (material_library.material_count !=
                material_instances.material_count) {
            snprintf(
                failure,
                sizeof(failure),
                "%s",
                "material_library_count_mismatch");
            goto invalid;
        }
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

    read_status =
        XzOpenStreamedTexturePack(
            material_path,
            "XZMT",
            XZ_XZMT_HEADER_FLAG_RGBA8,
            XZ_STATIC_TEXTURE_FLAG_RGBA8,
            (uint32_t)submesh_total,
            &material_file_handle,
            &material_data,
            &material_bytes,
            &material_texture_count,
            &material_binding_count,
            &material_texture_table_offset,
            &material_binding_offset);

    if (read_status < 0 ||
        (read_status == 0 &&
         strcmp(
             map_id,
             "xziel_nacht_bo3") == 0)) {
        snprintf(
            failure,
            sizeof(failure),
            "%s",
            read_status == 0
                ? "material_pack_missing"
                : "material_pack_stream_open_failed");
        goto invalid;
    }

    if (snprintf(
            pbr_material_path,
            sizeof(pbr_material_path),
            "xziel/maps/%s/materials.xzpb",
            map_id) <= 0 ||
        strlen(pbr_material_path) >=
            sizeof(pbr_material_path) - 1u) {
        snprintf(
            failure,
            sizeof(failure),
            "%s",
            "pbr_material_path_overflow");
        goto invalid;
    }

    read_status = XzReadVfsFile(
        pbr_material_path,
        XZ_STATIC_SCENE_MAX_PBR_MATERIAL_BYTES,
        &pbr_material_data,
        &pbr_material_bytes);

    if (read_status < 0 ||
        (read_status == 0 &&
         strcmp(map_id, "xziel_nacht_bo3") == 0)) {
        snprintf(
            failure,
            sizeof(failure),
            "%s",
            read_status == 0
                ? "pbr_material_pack_missing"
                : "pbr_material_pack_read_failed");
        goto invalid;
    }

    if (read_status > 0) {
        pbr_material_status =
            XzPbrMaterial_Parse(
                &pbr_material,
                pbr_material_data,
                pbr_material_bytes);

        if (pbr_material_status !=
                XZ_PBR_MATERIAL_OK) {
            snprintf(
                failure,
                sizeof(failure),
                "pbr_material_%s",
                XzPbrMaterial_StatusName(
                    pbr_material_status));
            goto invalid;
        }

        if (pbr_material.binding_count !=
                (uint32_t)submesh_total) {
            snprintf(
                failure,
                sizeof(failure),
                "%s",
                "pbr_material_binding_mismatch");
            goto invalid;
        }
    }

    if (snprintf(
            normal_material_path,
            sizeof(normal_material_path),
            "xziel/maps/%s/materials.xzmn",
            map_id) <= 0 ||
        strlen(normal_material_path) >=
            sizeof(normal_material_path) - 1u) {
        snprintf(
            failure,
            sizeof(failure),
            "%s",
            "normal_material_path_overflow");
        goto invalid;
    }

    read_status =
        XzOpenStreamedTexturePack(
            normal_material_path,
            "XZMN",
            XZ_XZMN_FLAG_RGBA8_NORMAL,
            XZ_XZMN_FLAG_RGBA8_NORMAL,
            (uint32_t)submesh_total,
            &normal_material_file_handle,
            &normal_material_data,
            &normal_material_bytes,
            &normal_texture_count,
            &normal_binding_count,
            &normal_texture_table_offset,
            &normal_binding_offset);

    if (read_status < 0 ||
        (read_status == 0 &&
         strcmp(
             map_id,
             "xziel_nacht_bo3") == 0)) {
        snprintf(
            failure,
            sizeof(failure),
            "%s",
            read_status == 0
                ? "normal_material_pack_missing"
                : "normal_material_pack_stream_open_failed");
        goto invalid;
    }

    if (snprintf(
            environment_path,
            sizeof(environment_path),
            "xziel/maps/%s/environment.xzen",
            map_id) <= 0 ||
        strlen(environment_path) >=
            sizeof(environment_path) - 1u) {
        snprintf(
            failure,
            sizeof(failure),
            "%s",
            "environment_path_overflow");
        goto invalid;
    }

    read_status = XzReadVfsFile(
        environment_path,
        XZ_STATIC_SCENE_MAX_ENVIRONMENT_BYTES,
        &environment_data,
        &environment_bytes);

    if (read_status < 0 ||
        (read_status == 0 &&
         strcmp(map_id, "xziel_nacht_bo3") == 0)) {
        snprintf(
            failure,
            sizeof(failure),
            "%s",
            read_status == 0
                ? "environment_pack_missing"
                : "environment_pack_read_failed");
        goto invalid;
    }

    if (read_status > 0) {
        environment_status =
            XzEnvironment_Parse(
                &environment,
                environment_data,
                environment_bytes);

        if (environment_status != XZ_ENV_OK) {
            snprintf(
                failure,
                sizeof(failure),
                "environment_%s",
                XzEnvironment_StatusName(
                    environment_status));
            goto invalid;
        }

        if (strcmp(
                map_id,
                "xziel_nacht_bo3") == 0 &&
            (environment.light_count != 166u ||
             environment.point_count != 144u ||
             environment.spot_count != 19u ||
             environment.directional_count != 2u ||
             environment.sky_count != 1u)) {
            snprintf(
                failure,
                sizeof(failure),
                "%s",
                "nacht_environment_count_mismatch");
            goto invalid;
        }
    }

    if (snprintf(
            height_fog_path,
            sizeof(height_fog_path),
            "xziel/maps/%s/fog.xzfg",
            map_id) <= 0 ||
        strlen(height_fog_path) >=
            sizeof(height_fog_path) - 1u) {
        snprintf(
            failure,
            sizeof(failure),
            "%s",
            "height_fog_path_overflow");
        goto invalid;
    }

    read_status = XzReadVfsFile(
        height_fog_path,
        XZ_STATIC_SCENE_MAX_HEIGHT_FOG_BYTES,
        &height_fog_data,
        &height_fog_bytes);

    if (read_status < 0 ||
        (read_status == 0 &&
         strcmp(map_id, "xziel_nacht_bo3") == 0)) {
        snprintf(
            failure,
            sizeof(failure),
            "%s",
            read_status == 0
                ? "height_fog_pack_missing"
                : "height_fog_pack_read_failed");
        goto invalid;
    }

    if (read_status > 0) {
        height_fog_status =
            XzHeightFog_Parse(
                &height_fog,
                height_fog_data,
                height_fog_bytes);

        if (height_fog_status !=
            XZ_HEIGHT_FOG_OK) {
            snprintf(
                failure,
                sizeof(failure),
                "height_fog_%s",
                XzHeightFog_StatusName(
                    height_fog_status));
            goto invalid;
        }

        if (strcmp(
                map_id,
                "xziel_nacht_bo3") == 0 &&
            (height_fog_bytes !=
                 XZ_HEIGHT_FOG_BYTES ||
             fabsf(height_fog.density - 0.1f) >
                 0.000001f ||
             fabsf(height_fog.height_falloff - 2.0f) >
                 0.000001f ||
             fabsf(height_fog.max_opacity - 0.2f) >
                 0.000001f ||
             fabsf(height_fog.start_distance_meters - 3.0f) >
                 0.000001f ||
             height_fog.flags != 0u)) {
            snprintf(
                failure,
                sizeof(failure),
                "%s",
                "nacht_height_fog_mismatch");
            goto invalid;
        }
    }

    if (snprintf(
            reflection_path,
            sizeof(reflection_path),
            "xziel/maps/%s/reflection.xzrc",
            map_id) <= 0 ||
        strlen(reflection_path) >=
            sizeof(reflection_path) - 1u) {
        snprintf(
            failure,
            sizeof(failure),
            "%s",
            "reflection_path_overflow");
        goto invalid;
    }

    read_status = XzReadVfsFile(
        reflection_path,
        XZ_STATIC_SCENE_MAX_REFLECTION_BYTES,
        &reflection_data,
        &reflection_bytes);

    if (read_status < 0 ||
        (read_status == 0 &&
         strcmp(map_id, "xziel_nacht_bo3") == 0)) {
        snprintf(
            failure,
            sizeof(failure),
            "%s",
            read_status == 0
                ? "reflection_pack_missing"
                : "reflection_pack_read_failed");
        goto invalid;
    }

    if (read_status > 0) {
        static const unsigned char nacht_guid[16] = {
            0x26, 0xae, 0xb6, 0xb5,
            0x44, 0xe0, 0xc5, 0x52,
            0xb1, 0xf0, 0x51, 0x92,
            0x79, 0xa3, 0xbf, 0x2d
        };

        if (!XzValidateReflectionPack(
                reflection_data,
                reflection_bytes,
                &reflection)) {
            snprintf(
                failure,
                sizeof(failure),
                "%s",
                "reflection_pack_invalid");
            goto invalid;
        }

        if (strcmp(
                map_id,
                "xziel_nacht_bo3") == 0 &&
            (reflection.asset_version != 2u ||
             reflection.shape !=
                 XZ_REFLECTION_SHAPE_SPHERE ||
             reflection.cubemap_size != 128u ||
             reflection.mip_count != 8u ||
             reflection.face_count != 6u ||
             reflection.pixel_format !=
                 XZ_REFLECTION_FORMAT_RGBA16F ||
             reflection.bytes_per_texel != 8u ||
             reflection.payload_bytes != 1048560u ||
             fabsf(
                 reflection.average_brightness -
                 0.04043579f) > 0.000001f ||
             fabsf(
                 reflection.brightness -
                 1.0f) > 0.000001f ||
             fabsf(
                 reflection.capture_position_meters[0] -
                 (-0.1090765381f)) > 0.000001f ||
             fabsf(
                 reflection.capture_position_meters[1] -
                 0.0932865906f) > 0.000001f ||
             fabsf(
                 reflection.capture_position_meters[2] -
                 2.6686132813f) > 0.000001f ||
             fabsf(
                 reflection.influence_radius_meters -
                 30.0f) > 0.000001f ||
             fabsf(
                 reflection.capture_offset_meters[0]) >
                 0.000001f ||
             fabsf(
                 reflection.capture_offset_meters[1]) >
                 0.000001f ||
             fabsf(
                 reflection.capture_offset_meters[2]) >
                 0.000001f ||
             memcmp(
                 reflection.map_build_data_id,
                 nacht_guid,
                 sizeof(nacht_guid)) != 0)) {
            snprintf(
                failure,
                sizeof(failure),
                "%s",
                "nacht_reflection_mismatch");
            goto invalid;
        }
    }

    if (snprintf(
            lightmap_path,
            sizeof(lightmap_path),
            "xziel/maps/%s/lightmaps.xzlt",
            map_id) <= 0 ||
        strlen(lightmap_path) >=
            sizeof(lightmap_path) - 1u) {
        snprintf(
            failure,
            sizeof(failure),
            "%s",
            "lightmap_path_overflow");
        goto invalid;
    }

    if (strcmp(
            map_id,
            "xziel_nacht_bo3") == 0) {
        lightmap_status =
            XzLightmapTexture_Open(
                &lightmaps,
                lightmap_path);

        if (lightmap_status !=
                XZ_XZLT_OK) {
            snprintf(
                failure,
                sizeof(failure),
                "lightmap_pack_%s",
                XzLightmapTexture_StatusName(
                    lightmap_status));
            goto invalid;
        }

        if (lightmaps.texture_count != 188u ||
            lightmaps.mip_count != 2066u ||
            lightmaps.bc1_texture_count != 94u ||
            lightmaps.bc3_texture_count != 94u ||
            lightmaps.srgb_texture_count != 0u ||
            lightmaps.linear_texture_count != 188u ||
            lightmaps.payload_offset != 37600u ||
            lightmaps.payload_bytes != 235450032u ||
            lightmaps.file_bytes != 235487632u) {
            snprintf(
                failure,
                sizeof(failure),
                "%s",
                "nacht_lightmap_pack_mismatch");
            goto invalid;
        }
    }

    if (snprintf(
            lightmap_binding_path,
            sizeof(lightmap_binding_path),
            "xziel/maps/%s/lightmap-bindings.xzlb",
            map_id) <= 0 ||
        strlen(lightmap_binding_path) >=
            sizeof(lightmap_binding_path) - 1u) {
        snprintf(
            failure,
            sizeof(failure),
            "%s",
            "lightmap_binding_path_overflow");
        goto invalid;
    }

    if (strcmp(
            map_id,
            "xziel_nacht_bo3") == 0) {
        lightmap_binding_status =
            XzLightmapBinding_Open(
                &lightmap_bindings,
                lightmap_binding_path);

        if (lightmap_binding_status !=
                XZ_XZLB_OK) {
            snprintf(
                failure,
                sizeof(failure),
                "lightmap_binding_%s",
                XzLightmapBinding_StatusName(
                    lightmap_binding_status));
            goto invalid;
        }

        if (lightmap_bindings.instance_count != 10791u ||
            lightmap_bindings.record_bytes != 256u ||
            lightmap_bindings.mapped_count != 10787u ||
            lightmap_bindings.missing_count != 4u ||
            lightmap_bindings.runtime_ready_count != 10787u ||
            lightmap_bindings.texture_count !=
                lightmaps.texture_count ||
            lightmap_bindings.header_flags != 1u ||
            lightmap_bindings.bytes != 2762528u ||
            lightmap_bindings.uv_channel_count[0] != 0u ||
            lightmap_bindings.uv_channel_count[1] != 10399u ||
            lightmap_bindings.uv_channel_count[2] != 1u ||
            lightmap_bindings.uv_channel_count[3] != 387u) {
            snprintf(
                failure,
                sizeof(failure),
                "%s",
                "nacht_lightmap_binding_mismatch");
            goto invalid;
        }
    }

    state->scene_data = scene_data;
    state->scene_bytes = scene_bytes;
    state->scene = scene;
    state->mesh_resources = resources;
    state->mesh_resource_count =
        scene.mesh_count;
    state->material_data = material_data;
    state->material_bytes = material_bytes;
    state->material_file_handle =
        material_file_handle;
    state->material_instance_data =
        material_instance_data;
    state->material_instance_bytes =
        material_instance_bytes;
    if (material_instance_data)
        state->material_instances =
            material_instances;

    state->material_library_data =
        material_library_data;
    state->material_library_bytes =
        material_library_bytes;
    if (material_library_data)
        state->material_library =
            material_library;

    material_file_handle = -1;
    state->material_texture_count =
        material_texture_count;
    state->material_binding_count =
        material_binding_count;
    state->material_texture_table_offset =
        material_texture_table_offset;
    state->material_binding_offset =
        material_binding_offset;
    state->pbr_material_data =
        pbr_material_data;
    state->pbr_material_bytes =
        pbr_material_bytes;
    if (pbr_material_data)
        state->pbr_material = pbr_material;
    state->normal_material_data =
        normal_material_data;
    state->normal_material_bytes =
        normal_material_bytes;
    state->normal_material_file_handle =
        normal_material_file_handle;
    normal_material_file_handle = -1;
    state->normal_texture_count =
        normal_texture_count;
    state->normal_binding_count =
        normal_binding_count;
    state->normal_texture_table_offset =
        normal_texture_table_offset;
    state->normal_binding_offset =
        normal_binding_offset;
    state->environment_data =
        environment_data;
    state->environment_bytes =
        environment_bytes;
    if (environment_data)
        state->environment = environment;

    state->height_fog_data =
        height_fog_data;
    state->height_fog_bytes =
        height_fog_bytes;
    if (height_fog_data)
        state->height_fog = height_fog;

    state->reflection_data =
        reflection_data;
    state->reflection_bytes =
        reflection_bytes;
    if (reflection_data)
        state->reflection = reflection;

    if (lightmaps.file_open) {
        state->lightmaps = lightmaps;
        XzLightmapTexture_Init(
            &lightmaps);
    }
    if (lightmap_bindings.data) {
        state->lightmap_bindings =
            lightmap_bindings;
        XzLightmapBinding_Init(
            &lightmap_bindings);
    }
    if (material_data) {
        snprintf(
            state->material_path,
            sizeof(state->material_path),
            "%s",
            material_path);
    }
    if (material_instance_data) {
        snprintf(
            state->material_instance_path,
            sizeof(state->material_instance_path),
            "%s",
            material_instance_path);
    }
    if (material_library_data) {
        snprintf(
            state->material_library_path,
            sizeof(state->material_library_path),
            "%s",
            material_library_path);
    }
    if (pbr_material_data) {
        snprintf(
            state->pbr_material_path,
            sizeof(state->pbr_material_path),
            "%s",
            pbr_material_path);
    }
    if (normal_material_data) {
        snprintf(
            state->normal_material_path,
            sizeof(state->normal_material_path),
            "%s",
            normal_material_path);
    }
    if (environment_data) {
        snprintf(
            state->environment_path,
            sizeof(state->environment_path),
            "%s",
            environment_path);
    }
    if (height_fog_data) {
        snprintf(
            state->height_fog_path,
            sizeof(state->height_fog_path),
            "%s",
            height_fog_path);
    }
    if (reflection_data) {
        snprintf(
            state->reflection_path,
            sizeof(state->reflection_path),
            "%s",
            reflection_path);
    }
    if (state->lightmaps.file_open) {
        snprintf(
            state->lightmap_path,
            sizeof(state->lightmap_path),
            "%s",
            lightmap_path);
    }
    if (state->lightmap_bindings.data) {
        snprintf(
            state->lightmap_binding_path,
            sizeof(state->lightmap_binding_path),
            "%s",
            lightmap_binding_path);
    }
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
    free(scene_data);
    if (material_file_handle >= 0)
        COM_CloseFile(material_file_handle);
    free(material_data);
    free(material_instance_data);
    free(material_library_data);
    free(pbr_material_data);
    if (normal_material_file_handle >= 0)
        COM_CloseFile(normal_material_file_handle);
    free(normal_material_data);
    free(environment_data);
    free(height_fog_data);
    free(reflection_data);
    XzLightmapTexture_Close(
        &lightmaps);
    XzLightmapBinding_Close(
        &lightmap_bindings);

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

int XzStaticSceneRuntime_MaterialBinding(
    const XzStaticSceneRuntimeState *state,
    uint32_t binding_index,
    uint32_t *texture_index)
{
    if (!state ||
        state->status !=
            XZ_STATIC_SCENE_READY ||
        !state->material_data ||
        !texture_index ||
        binding_index >=
            state->material_binding_count)
        return 0;

    *texture_index =
        XzStaticReadU32Le(
            state->material_data +
            state->material_binding_offset +
            (size_t)binding_index *
                sizeof(uint32_t));
    return 1;
}

const XzMaterialInstanceBindingView *
XzStaticSceneRuntime_MaterialInstances(
    const XzStaticSceneRuntimeState *state)
{
    if (!state ||
        state->status !=
            XZ_STATIC_SCENE_READY ||
        !state->material_instance_data)
        return NULL;

    return &state->material_instances;
}

int XzStaticSceneRuntime_InstanceMaterial(
    const XzStaticSceneRuntimeState *state,
    uint32_t instance_index,
    uint32_t submesh_index,
    uint32_t *material_index)
{
    if (!state ||
        state->status !=
            XZ_STATIC_SCENE_READY ||
        !state->material_instance_data ||
        !material_index)
        return 0;

    return XzMaterialInstanceBinding_Material(
        &state->material_instances,
        instance_index,
        submesh_index,
        material_index) == XZ_XZMI_OK;
}

const XzMaterialLibraryView *
XzStaticSceneRuntime_MaterialLibrary(
    const XzStaticSceneRuntimeState *state)
{
    if (!state ||
        state->status !=
            XZ_STATIC_SCENE_READY ||
        !state->material_library_data)
        return NULL;

    return &state->material_library;
}

int XzStaticSceneRuntime_Material(
    const XzStaticSceneRuntimeState *state,
    uint32_t material_index,
    XzMaterialLibraryMaterial *material)
{
    if (!state ||
        state->status !=
            XZ_STATIC_SCENE_READY ||
        !state->material_library_data ||
        !material)
        return 0;

    return XzMaterialLibrary_Material(
        &state->material_library,
        material_index,
        material) == XZ_XZML_OK;
}

int XzStaticSceneRuntime_LoadMaterialTexture(
    const XzStaticSceneRuntimeState *state,
    uint32_t texture_index,
    XzStaticNativeTextureResource *resource)
{
    XzMaterialLibraryTextureAsset asset;
    const char *runtime_file;
    unsigned char *data = NULL;
    size_t bytes = 0u;
    size_t runtime_file_bytes;
    char leaf[128];
    char path[256];
    int read_status;
    XzXztextureStatus texture_status;

    if (!state ||
        state->status != XZ_STATIC_SCENE_READY ||
        !state->material_library_data ||
        !resource)
        return 0;

    memset(resource, 0, sizeof(*resource));

    if (XzMaterialLibrary_TextureAsset(
            &state->material_library,
            texture_index,
            &asset) != XZ_XZML_OK ||
        !XzMaterialLibrary_String(
            &state->material_library,
            asset.runtime_file_offset,
            asset.runtime_file_bytes,
            &runtime_file))
        return 0;

    runtime_file_bytes =
        (size_t)asset.runtime_file_bytes;

    if (!XzSafeAssetLeaf(
            runtime_file,
            runtime_file_bytes) ||
        runtime_file_bytes >= sizeof(leaf))
        return 0;

    memcpy(
        leaf,
        runtime_file,
        runtime_file_bytes);
    leaf[runtime_file_bytes] = '\0';

    if (snprintf(
            path,
            sizeof(path),
            "xziel/maps/%s/textures/%s",
            state->map_id,
            leaf) <= 0 ||
        strlen(path) >= sizeof(path) - 1u)
        return 0;

    read_status =
        XzReadVfsFile(
            path,
            XZ_STATIC_SCENE_MAX_NATIVE_TEXTURE_BYTES,
            &data,
            &bytes);

    if (read_status <= 0)
        return 0;

    texture_status =
        XzXztexture_Parse(
            &resource->texture,
            data,
            bytes);

    if (texture_status != XZ_XZTX_OK) {
        free(data);
        memset(resource, 0, sizeof(*resource));
        return 0;
    }

    resource->data = data;
    resource->bytes = bytes;
    snprintf(
        resource->path,
        sizeof(resource->path),
        "%s",
        path);
    return 1;
}

void XzStaticSceneRuntime_ReleaseMaterialTexture(
    XzStaticNativeTextureResource *resource)
{
    if (!resource)
        return;

    free(resource->data);
    memset(resource, 0, sizeof(*resource));
}

int XzStaticSceneRuntime_Texture(
    const XzStaticSceneRuntimeState *state,
    uint32_t texture_index,
    XzStaticTextureView *texture)
{
    const unsigned char *entry;
    uint32_t bytes;

    if (!state ||
        state->status !=
            XZ_STATIC_SCENE_READY ||
        !state->material_data ||
        state->material_file_handle < 0 ||
        !texture ||
        texture_index >=
            state->material_texture_count)
        return 0;

    entry =
        state->material_data +
        state->material_texture_table_offset +
        (size_t)texture_index *
            XZ_XZMT_TEXTURE_BYTES;

    texture->width =
        XzStaticReadU32Le(entry + 0u);
    texture->height =
        XzStaticReadU32Le(entry + 4u);
    bytes =
        XzStaticReadU32Le(entry + 12u);
    texture->flags =
        XzStaticReadU32Le(entry + 16u);
    texture->rgba = NULL;
    texture->rgba_bytes = (size_t)bytes;
    return 1;
}

int XzStaticSceneRuntime_ReadTexture(
    const XzStaticSceneRuntimeState *state,
    uint32_t texture_index,
    void *destination,
    size_t destination_bytes)
{
    if (!state ||
        state->status !=
            XZ_STATIC_SCENE_READY)
        return 0;

    return XzReadStreamedTexture(
        state->material_file_handle,
        state->material_data,
        state->material_texture_table_offset,
        state->material_texture_count,
        texture_index,
        destination,
        destination_bytes);
}

int XzStaticSceneRuntime_PbrBinding(
    const XzStaticSceneRuntimeState *state,
    uint32_t binding_index,
    XzPbrMaterialBinding *binding)
{
    if (!state ||
        state->status !=
            XZ_STATIC_SCENE_READY ||
        !state->pbr_material_data ||
        !binding)
        return 0;

    return XzPbrMaterial_ReadBinding(
        &state->pbr_material,
        binding_index,
        binding) == XZ_PBR_MATERIAL_OK;
}


int XzStaticSceneRuntime_NormalBinding(
    const XzStaticSceneRuntimeState *state,
    uint32_t binding_index,
    uint32_t *texture_index)
{
    if (!state ||
        state->status !=
            XZ_STATIC_SCENE_READY ||
        !state->normal_material_data ||
        !texture_index ||
        binding_index >=
            state->normal_binding_count)
        return 0;

    *texture_index =
        XzStaticReadU32Le(
            state->normal_material_data +
            state->normal_binding_offset +
            (size_t)binding_index *
                sizeof(uint32_t));
    return 1;
}

int XzStaticSceneRuntime_NormalTexture(
    const XzStaticSceneRuntimeState *state,
    uint32_t texture_index,
    XzStaticTextureView *texture)
{
    const unsigned char *entry;
    uint32_t bytes;

    if (!state ||
        state->status !=
            XZ_STATIC_SCENE_READY ||
        !state->normal_material_data ||
        state->normal_material_file_handle < 0 ||
        !texture ||
        texture_index >=
            state->normal_texture_count)
        return 0;

    entry =
        state->normal_material_data +
        state->normal_texture_table_offset +
        (size_t)texture_index *
            XZ_XZMN_TEXTURE_BYTES;

    texture->width =
        XzStaticReadU32Le(entry + 0u);
    texture->height =
        XzStaticReadU32Le(entry + 4u);
    bytes =
        XzStaticReadU32Le(entry + 12u);
    texture->flags =
        XzStaticReadU32Le(entry + 16u);
    texture->rgba = NULL;
    texture->rgba_bytes = (size_t)bytes;
    return 1;
}

int XzStaticSceneRuntime_ReadNormalTexture(
    const XzStaticSceneRuntimeState *state,
    uint32_t texture_index,
    void *destination,
    size_t destination_bytes)
{
    if (!state ||
        state->status !=
            XZ_STATIC_SCENE_READY)
        return 0;

    return XzReadStreamedTexture(
        state->normal_material_file_handle,
        state->normal_material_data,
        state->normal_texture_table_offset,
        state->normal_texture_count,
        texture_index,
        destination,
        destination_bytes);
}

const XzEnvironmentView *
XzStaticSceneRuntime_Environment(
    const XzStaticSceneRuntimeState *state)
{
    if (!state ||
        state->status !=
            XZ_STATIC_SCENE_READY ||
        !state->environment_data)
        return NULL;

    return &state->environment;
}

int XzStaticSceneRuntime_EnvironmentLight(
    const XzStaticSceneRuntimeState *state,
    uint32_t light_index,
    XzEnvironmentLight *light)
{
    if (!state ||
        state->status !=
            XZ_STATIC_SCENE_READY ||
        !state->environment_data)
        return 0;

    return XzEnvironment_ReadLight(
        &state->environment,
        light_index,
        light);
}

const XzHeightFogView *
XzStaticSceneRuntime_HeightFog(
    const XzStaticSceneRuntimeState *state)
{
    if (!state ||
        state->status !=
            XZ_STATIC_SCENE_READY ||
        !state->height_fog_data)
        return NULL;

    return &state->height_fog;
}

const XzReflectionCaptureView *
XzStaticSceneRuntime_ReflectionCapture(
    const XzStaticSceneRuntimeState *state)
{
    if (!state ||
        state->status !=
            XZ_STATIC_SCENE_READY ||
        !state->reflection_data)
        return NULL;

    return &state->reflection;
}

const XzLightmapTextureView *
XzStaticSceneRuntime_Lightmaps(
    const XzStaticSceneRuntimeState *state)
{
    if (!state ||
        state->status !=
            XZ_STATIC_SCENE_READY ||
        !state->lightmaps.file_open)
        return NULL;

    return &state->lightmaps;
}

const XzLightmapBindingView *
XzStaticSceneRuntime_LightmapBindings(
    const XzStaticSceneRuntimeState *state)
{
    if (!state ||
        state->status !=
            XZ_STATIC_SCENE_READY ||
        !state->lightmap_bindings.data)
        return NULL;

    return &state->lightmap_bindings;
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
