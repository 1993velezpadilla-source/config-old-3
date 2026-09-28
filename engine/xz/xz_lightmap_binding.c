#include "xz_lightmap_binding.h"

#include <limits.h>
#include <stdlib.h>
#include <string.h>

extern int COM_OpenFile(
    char *filename,
    int *handle);

extern void COM_CloseFile(
    int handle);

extern int Sys_FileRead(
    int handle,
    void *dest,
    int count);

static uint32_t XzReadU32Le(
    const unsigned char *p)
{
    return ((uint32_t)p[0]) |
           ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

static float XzReadF32Le(
    const unsigned char *p)
{
    const uint32_t bits = XzReadU32Le(p);
    float value;
    memcpy(&value, &bits, sizeof(value));
    return value;
}

static int XzReadExact(
    int handle,
    void *destination,
    size_t bytes)
{
    unsigned char *out =
        (unsigned char *)destination;
    size_t done = 0u;

    while (done < bytes) {
        const size_t remaining = bytes - done;
        const int request =
            remaining > (size_t)INT_MAX
                ? INT_MAX
                : (int)remaining;
        const int got =
            Sys_FileRead(
                handle,
                out + done,
                request);

        if (got <= 0 ||
            got > request)
            return 0;

        done += (size_t)got;
    }

    return 1;
}

static int XzGuidIsZero(
    const unsigned char guid[16])
{
    unsigned int i;

    for (i = 0u; i < 16u; ++i) {
        if (guid[i] != 0u)
            return 0;
    }
    return 1;
}

static int XzBindingRecordAt(
    const XzLightmapBindingView *view,
    uint32_t instance_index,
    XzLightmapBindingRecord *record)
{
    const unsigned char *p;
    unsigned int i;

    if (!view ||
        !view->data ||
        !record ||
        view->record_bytes != XZ_XZLB_RECORD_BYTES ||
        instance_index >= view->instance_count)
        return 0;

    p =
        view->data +
        XZ_XZLB_HEADER_BYTES +
        (size_t)instance_index *
            XZ_XZLB_RECORD_BYTES;

    memset(record, 0, sizeof(*record));

    record->flags = XzReadU32Le(p + 0u);
    record->uv_channel = XzReadU32Le(p + 4u);
    record->light_texture[0] = XzReadU32Le(p + 8u);
    record->light_texture[1] = XzReadU32Le(p + 12u);
    record->shadow_texture = XzReadU32Le(p + 16u);
    record->sky_occlusion_texture = XzReadU32Le(p + 20u);
    record->ao_mask_texture = XzReadU32Le(p + 24u);
    record->component_export_index = XzReadU32Le(p + 28u);

    for (i = 0u; i < 2u; ++i)
        record->lightmap_coordinate_scale[i] =
            XzReadF32Le(p + 32u + i * 4u);
    for (i = 0u; i < 2u; ++i)
        record->lightmap_coordinate_bias[i] =
            XzReadF32Le(p + 40u + i * 4u);
    for (i = 0u; i < 16u; ++i)
        record->lightmap_scale_vectors[i] =
            XzReadF32Le(p + 48u + i * 4u);
    for (i = 0u; i < 16u; ++i)
        record->lightmap_add_vectors[i] =
            XzReadF32Le(p + 112u + i * 4u);

    record->light_shadow_channel_mask =
        XzReadU32Le(p + 176u);
    record->resolution_code =
        XzReadU32Le(p + 180u);

    for (i = 0u; i < 4u; ++i)
        record->light_inv_uniform_penumbra_size[i] =
            XzReadF32Le(p + 184u + i * 4u);
    for (i = 0u; i < 2u; ++i)
        record->shadow_coordinate_scale[i] =
            XzReadF32Le(p + 200u + i * 4u);
    for (i = 0u; i < 2u; ++i)
        record->shadow_coordinate_bias[i] =
            XzReadF32Le(p + 208u + i * 4u);

    record->shadow_channel_mask =
        XzReadU32Le(p + 216u);

    for (i = 0u; i < 4u; ++i)
        record->shadow_inv_uniform_penumbra_size[i] =
            XzReadF32Le(p + 224u + i * 4u);

    memcpy(
        record->map_build_data_id,
        p + 240u,
        16u);

    return 1;
}

void XzLightmapBinding_Init(
    XzLightmapBindingView *view)
{
    if (!view)
        return;

    memset(view, 0, sizeof(*view));
}

void XzLightmapBinding_Close(
    XzLightmapBindingView *view)
{
    if (!view)
        return;

    free(view->data);
    memset(view, 0, sizeof(*view));
}

XzLightmapBindingStatus XzLightmapBinding_Open(
    XzLightmapBindingView *view,
    const char *path)
{
    unsigned char *data = NULL;
    int handle = -1;
    int file_bytes;
    uint32_t version;
    uint32_t instance_count;
    uint32_t record_bytes;
    uint32_t mapped_count;
    uint32_t texture_count;
    uint32_t header_flags;
    uint32_t reserved;
    uint64_t expected_bytes;
    uint32_t instance_index;
    uint32_t observed_mapped = 0u;
    uint32_t observed_missing = 0u;
    uint32_t observed_ready = 0u;
    uint32_t uv_counts[4] = {0u, 0u, 0u, 0u};
    XzLightmapBindingStatus status =
        XZ_XZLB_OK;

    if (!view ||
        !path ||
        !path[0])
        return XZ_XZLB_ERR_ARGUMENT;

    XzLightmapBinding_Close(view);

    file_bytes =
        COM_OpenFile(
            (char *)path,
            &handle);

    if (handle < 0 ||
        file_bytes < (int)XZ_XZLB_HEADER_BYTES) {
        if (handle >= 0)
            COM_CloseFile(handle);
        return XZ_XZLB_ERR_OPEN;
    }

    data =
        (unsigned char *)malloc(
            (size_t)file_bytes);
    if (!data) {
        COM_CloseFile(handle);
        return XZ_XZLB_ERR_MEMORY;
    }

    if (!XzReadExact(
            handle,
            data,
            (size_t)file_bytes)) {
        status = XZ_XZLB_ERR_READ;
        goto fail;
    }

    COM_CloseFile(handle);
    handle = -1;

    if (data[0] != 'X' ||
        data[1] != 'Z' ||
        data[2] != 'L' ||
        data[3] != 'B') {
        status = XZ_XZLB_ERR_MAGIC;
        goto fail;
    }

    version = XzReadU32Le(data + 4u);
    instance_count = XzReadU32Le(data + 8u);
    record_bytes = XzReadU32Le(data + 12u);
    mapped_count = XzReadU32Le(data + 16u);
    texture_count = XzReadU32Le(data + 20u);
    header_flags = XzReadU32Le(data + 24u);
    reserved = XzReadU32Le(data + 28u);

    if (version != XZ_XZLB_VERSION) {
        status = XZ_XZLB_ERR_VERSION;
        goto fail;
    }

    if (record_bytes != XZ_XZLB_RECORD_BYTES ||
        header_flags != 1u ||
        reserved != 0u) {
        status = XZ_XZLB_ERR_HEADER;
        goto fail;
    }

    if (instance_count == 0u ||
        mapped_count > instance_count ||
        texture_count == 0u) {
        status = XZ_XZLB_ERR_COUNT;
        goto fail;
    }

    expected_bytes =
        (uint64_t)XZ_XZLB_HEADER_BYTES +
        (uint64_t)instance_count *
            (uint64_t)XZ_XZLB_RECORD_BYTES;

    if (expected_bytes !=
        (uint64_t)(uint32_t)file_bytes) {
        status = XZ_XZLB_ERR_RANGE;
        goto fail;
    }

    view->data = data;
    view->bytes = (size_t)file_bytes;
    view->instance_count = instance_count;
    view->record_bytes = record_bytes;
    view->mapped_count = mapped_count;
    view->texture_count = texture_count;
    view->header_flags = header_flags;
    data = NULL;

    for (instance_index = 0u;
         instance_index < instance_count;
         ++instance_index) {
        XzLightmapBindingRecord record;
        const uint32_t known_flags =
            XZ_XZLB_FLAG_MAPPED |
            XZ_XZLB_FLAG_RUNTIME_READY |
            XZ_XZLB_FLAG_SHADOW_TEXTURE |
            XZ_XZLB_FLAG_SKY_OCCLUSION |
            XZ_XZLB_FLAG_AO_MASK |
            XZ_XZLB_FLAG_SHADOW_PARAMS |
            XZ_XZLB_FLAG_MESH_CONSENSUS;
        int mapped;

        if (!XzBindingRecordAt(
                view,
                instance_index,
                &record)) {
            status = XZ_XZLB_ERR_RECORD;
            goto fail_view;
        }

        mapped =
            (record.flags & XZ_XZLB_FLAG_MAPPED) != 0u;

        if ((record.flags & ~known_flags) != 0u) {
            status = XZ_XZLB_ERR_RECORD;
            goto fail_view;
        }

        if ((record.shadow_texture != XZ_XZLB_NO_TEXTURE &&
             record.shadow_texture >= texture_count) ||
            (record.sky_occlusion_texture != XZ_XZLB_NO_TEXTURE &&
             record.sky_occlusion_texture >= texture_count) ||
            (record.ao_mask_texture != XZ_XZLB_NO_TEXTURE &&
             record.ao_mask_texture >= texture_count)) {
            status = XZ_XZLB_ERR_RANGE;
            goto fail_view;
        }

        if (mapped) {
            int consensus;

            observed_mapped++;

            if ((record.flags &
                 XZ_XZLB_FLAG_RUNTIME_READY) == 0u) {
                status = XZ_XZLB_ERR_RECORD;
                goto fail_view;
            }
            observed_ready++;

            if (record.uv_channel > 3u ||
                record.light_texture[0] >= texture_count ||
                record.light_texture[1] >= texture_count) {
                status = XZ_XZLB_ERR_RANGE;
                goto fail_view;
            }
            uv_counts[record.uv_channel]++;

            if (record.resolution_code !=
                    XZ_XZLB_RESOLUTION_AUTHORED &&
                record.resolution_code !=
                    XZ_XZLB_RESOLUTION_MESH_CONSENSUS) {
                status = XZ_XZLB_ERR_RECORD;
                goto fail_view;
            }

            consensus =
                record.resolution_code ==
                XZ_XZLB_RESOLUTION_MESH_CONSENSUS;
            if (consensus !=
                ((record.flags &
                  XZ_XZLB_FLAG_MESH_CONSENSUS) != 0u)) {
                status = XZ_XZLB_ERR_RECORD;
                goto fail_view;
            }

            if (XzGuidIsZero(
                    record.map_build_data_id)) {
                status = XZ_XZLB_ERR_RECORD;
                goto fail_view;
            }
        } else {
            observed_missing++;

            if (record.flags != 0u ||
                record.uv_channel != XZ_XZLB_NO_TEXTURE ||
                record.light_texture[0] != XZ_XZLB_NO_TEXTURE ||
                record.light_texture[1] != XZ_XZLB_NO_TEXTURE ||
                record.resolution_code != XZ_XZLB_RESOLUTION_NONE ||
                !XzGuidIsZero(record.map_build_data_id)) {
                status = XZ_XZLB_ERR_RECORD;
                goto fail_view;
            }
        }
    }

    if (observed_mapped != mapped_count ||
        observed_ready != mapped_count ||
        observed_missing !=
            instance_count - mapped_count) {
        status = XZ_XZLB_ERR_COUNT;
        goto fail_view;
    }

    view->missing_count = observed_missing;
    view->runtime_ready_count = observed_ready;
    memcpy(
        view->uv_channel_count,
        uv_counts,
        sizeof(uv_counts));

    return XZ_XZLB_OK;

fail_view:
    XzLightmapBinding_Close(view);
    return status;

fail:
    if (handle >= 0)
        COM_CloseFile(handle);
    free(data);
    XzLightmapBinding_Init(view);
    return status;
}

int XzLightmapBinding_Record(
    const XzLightmapBindingView *view,
    uint32_t instance_index,
    XzLightmapBindingRecord *record)
{
    return XzBindingRecordAt(
        view,
        instance_index,
        record);
}

const char *XzLightmapBinding_StatusName(
    XzLightmapBindingStatus status)
{
    switch (status) {
    case XZ_XZLB_OK:
        return "OK";
    case XZ_XZLB_ERR_ARGUMENT:
        return "ARGUMENT";
    case XZ_XZLB_ERR_OPEN:
        return "OPEN";
    case XZ_XZLB_ERR_READ:
        return "READ";
    case XZ_XZLB_ERR_MAGIC:
        return "MAGIC";
    case XZ_XZLB_ERR_VERSION:
        return "VERSION";
    case XZ_XZLB_ERR_HEADER:
        return "HEADER";
    case XZ_XZLB_ERR_COUNT:
        return "COUNT";
    case XZ_XZLB_ERR_RECORD:
        return "RECORD";
    case XZ_XZLB_ERR_RANGE:
        return "RANGE";
    case XZ_XZLB_ERR_MEMORY:
        return "MEMORY";
    default:
        return "UNKNOWN";
    }
}
