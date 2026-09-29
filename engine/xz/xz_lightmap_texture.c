#include "xz_lightmap_texture.h"
#include "xz_file_io.h"

#include <limits.h>
#include <stdlib.h>
#include <string.h>

static uint32_t XzReadU32Le(
    const unsigned char *p)
{
    return ((uint32_t)p[0]) |
           ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
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
        size_t remaining = bytes - done;
        int request;
        int got;

        if (remaining > (size_t)INT_MAX)
            request = INT_MAX;
        else
            request = (int)remaining;

        got = XzFile_Read(
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

static int XzTextureRecordAt(
    const XzLightmapTextureView *view,
    uint32_t texture_index,
    XzLightmapTextureRecord *record)
{
    const unsigned char *p;

    if (!view ||
        !view->table_data ||
        !record ||
        texture_index >= view->texture_count)
        return 0;

    p =
        view->table_data +
        (size_t)texture_index *
            XZ_XZLT_TEXTURE_RECORD_BYTES;

    record->format = XzReadU32Le(p + 0u);
    record->width = XzReadU32Le(p + 4u);
    record->height = XzReadU32Le(p + 8u);
    record->first_mip = XzReadU32Le(p + 12u);
    record->mip_count = XzReadU32Le(p + 16u);
    record->srgb = XzReadU32Le(p + 20u);
    return 1;
}

static int XzMipRecordAt(
    const XzLightmapTextureView *view,
    uint32_t mip_index,
    XzLightmapMipRecord *record)
{
    const unsigned char *p;
    size_t mip_table_relative;

    if (!view ||
        !view->table_data ||
        !record ||
        mip_index >= view->mip_count ||
        view->mip_table_offset <
            view->texture_table_offset)
        return 0;

    mip_table_relative =
        (size_t)(
            view->mip_table_offset -
            view->texture_table_offset);

    p =
        view->table_data +
        mip_table_relative +
        (size_t)mip_index *
            XZ_XZLT_MIP_RECORD_BYTES;

    record->payload_offset =
        XzReadU32Le(p + 0u);
    record->bytes =
        XzReadU32Le(p + 4u);
    record->width =
        XzReadU32Le(p + 8u);
    record->height =
        XzReadU32Le(p + 12u);
    return 1;
}

static int XzExpectedCompressedBytes(
    uint32_t format,
    uint32_t width,
    uint32_t height,
    uint32_t *bytes)
{
    uint64_t blocks_x;
    uint64_t blocks_y;
    uint64_t block_bytes;
    uint64_t total;

    if (!bytes ||
        width == 0u ||
        height == 0u)
        return 0;

    if (format == XZ_XZLT_FORMAT_BC1)
        block_bytes = 8u;
    else if (format == XZ_XZLT_FORMAT_BC3)
        block_bytes = 16u;
    else
        return 0;

    blocks_x =
        ((uint64_t)width + 3u) / 4u;
    blocks_y =
        ((uint64_t)height + 3u) / 4u;
    total =
        blocks_x *
        blocks_y *
        block_bytes;

    if (total == 0u ||
        total > UINT32_MAX)
        return 0;

    *bytes = (uint32_t)total;
    return 1;
}

void XzLightmapTexture_Init(
    XzLightmapTextureView *view)
{
    if (!view)
        return;

    memset(view, 0, sizeof(*view));
    view->file_handle = -1;
}

void XzLightmapTexture_Close(
    XzLightmapTextureView *view)
{
    if (!view)
        return;

    if (view->file_open &&
        view->file_handle >= 0)
        XzFile_Close(
            view->file_handle);

    free(view->table_data);

    memset(view, 0, sizeof(*view));
    view->file_handle = -1;
}

XzLightmapTextureStatus XzLightmapTexture_Open(
    XzLightmapTextureView *view,
    const char *path)
{
    unsigned char header[
        XZ_XZLT_HEADER_BYTES];
    unsigned char *tables = NULL;
    unsigned char *seen_mips = NULL;
    int handle = -1;
    int file_bytes;
    uint32_t version;
    uint32_t texture_count;
    uint32_t mip_count;
    uint32_t texture_record_bytes;
    uint32_t mip_record_bytes;
    uint32_t texture_table_offset;
    uint32_t mip_table_offset;
    uint64_t expected_mip_table;
    uint64_t payload_offset64;
    uint32_t payload_offset;
    uint32_t payload_bytes;
    size_t table_bytes;
    uint32_t texture_index;
    uint32_t mip_index;
    uint32_t bc1_count = 0u;
    uint32_t bc3_count = 0u;
    uint32_t srgb_count = 0u;
    uint32_t linear_count = 0u;
    XzLightmapTextureStatus status =
        XZ_XZLT_OK;

    if (!view ||
        !path ||
        !path[0])
        return XZ_XZLT_ERR_ARGUMENT;

    XzLightmapTexture_Close(view);

    file_bytes =
        XzFile_Open(
            (char *)path,
            &handle);

    if (handle < 0 ||
        file_bytes < (int)XZ_XZLT_HEADER_BYTES) {
        if (handle >= 0)
            XzFile_Close(handle);
        return XZ_XZLT_ERR_OPEN;
    }

    if (!XzReadExact(
            handle,
            header,
            sizeof(header))) {
        status = XZ_XZLT_ERR_READ;
        goto fail;
    }

    if (header[0] != 'X' ||
        header[1] != 'Z' ||
        header[2] != 'L' ||
        header[3] != 'T') {
        status = XZ_XZLT_ERR_MAGIC;
        goto fail;
    }

    version =
        XzReadU32Le(header + 4u);
    texture_count =
        XzReadU32Le(header + 8u);
    mip_count =
        XzReadU32Le(header + 12u);
    texture_record_bytes =
        XzReadU32Le(header + 16u);
    mip_record_bytes =
        XzReadU32Le(header + 20u);
    texture_table_offset =
        XzReadU32Le(header + 24u);
    mip_table_offset =
        XzReadU32Le(header + 28u);

    if (version != XZ_XZLT_VERSION) {
        status = XZ_XZLT_ERR_VERSION;
        goto fail;
    }

    if (texture_record_bytes !=
            XZ_XZLT_TEXTURE_RECORD_BYTES ||
        mip_record_bytes !=
            XZ_XZLT_MIP_RECORD_BYTES ||
        texture_table_offset !=
            XZ_XZLT_HEADER_BYTES) {
        status = XZ_XZLT_ERR_HEADER;
        goto fail;
    }

    if (texture_count == 0u ||
        mip_count == 0u) {
        status = XZ_XZLT_ERR_COUNT;
        goto fail;
    }

    expected_mip_table =
        (uint64_t)texture_table_offset +
        (uint64_t)texture_count *
            XZ_XZLT_TEXTURE_RECORD_BYTES;

    if (expected_mip_table !=
            (uint64_t)mip_table_offset) {
        status = XZ_XZLT_ERR_TABLE;
        goto fail;
    }

    payload_offset64 =
        (uint64_t)mip_table_offset +
        (uint64_t)mip_count *
            XZ_XZLT_MIP_RECORD_BYTES;

    if (payload_offset64 >
            (uint64_t)file_bytes ||
        payload_offset64 >
            UINT32_MAX) {
        status = XZ_XZLT_ERR_RANGE;
        goto fail;
    }

    payload_offset =
        (uint32_t)payload_offset64;
    payload_bytes =
        (uint32_t)(
            (uint64_t)file_bytes -
            payload_offset64);

    table_bytes =
        (size_t)(
            payload_offset -
            texture_table_offset);

    if (table_bytes == 0u ||
        table_bytes > (size_t)INT_MAX) {
        status = XZ_XZLT_ERR_TABLE;
        goto fail;
    }

    tables =
        (unsigned char *)malloc(
            table_bytes);
    seen_mips =
        (unsigned char *)calloc(
            (size_t)mip_count,
            1u);

    if (!tables ||
        !seen_mips) {
        status = XZ_XZLT_ERR_MEMORY;
        goto fail;
    }

    XzFile_Seek(
        handle,
        (int)texture_table_offset);

    if (!XzReadExact(
            handle,
            tables,
            table_bytes)) {
        status = XZ_XZLT_ERR_READ;
        goto fail;
    }

    view->file_handle = handle;
    view->file_open = 1;
    view->file_bytes =
        (uint32_t)file_bytes;
    view->table_data = tables;
    view->table_bytes = table_bytes;
    view->texture_count = texture_count;
    view->mip_count = mip_count;
    view->texture_table_offset =
        texture_table_offset;
    view->mip_table_offset =
        mip_table_offset;
    view->payload_offset =
        payload_offset;
    view->payload_bytes =
        payload_bytes;

    for (texture_index = 0u;
         texture_index < texture_count;
         ++texture_index) {
        XzLightmapTextureRecord texture;
        uint64_t mip_end;

        if (!XzTextureRecordAt(
                view,
                texture_index,
                &texture)) {
            status = XZ_XZLT_ERR_TEXTURE;
            goto fail_view;
        }

        if (texture.format ==
                XZ_XZLT_FORMAT_BC1)
            bc1_count++;
        else if (texture.format ==
                 XZ_XZLT_FORMAT_BC3)
            bc3_count++;
        else {
            status = XZ_XZLT_ERR_TEXTURE;
            goto fail_view;
        }

        if (texture.width == 0u ||
            texture.height == 0u ||
            texture.mip_count == 0u ||
            texture.srgb > 1u) {
            status = XZ_XZLT_ERR_TEXTURE;
            goto fail_view;
        }

        if (texture.srgb)
            srgb_count++;
        else
            linear_count++;

        mip_end =
            (uint64_t)texture.first_mip +
            (uint64_t)texture.mip_count;

        if (mip_end >
                (uint64_t)mip_count) {
            status = XZ_XZLT_ERR_RANGE;
            goto fail_view;
        }

        for (mip_index = 0u;
             mip_index <
                texture.mip_count;
             ++mip_index) {
            const uint32_t absolute_mip =
                texture.first_mip +
                mip_index;
            XzLightmapMipRecord mip;
            uint32_t expected_bytes;
            uint64_t payload_end;

            if (seen_mips[absolute_mip]) {
                status = XZ_XZLT_ERR_MIP;
                goto fail_view;
            }
            seen_mips[absolute_mip] = 1u;

            if (!XzMipRecordAt(
                    view,
                    absolute_mip,
                    &mip)) {
                status = XZ_XZLT_ERR_MIP;
                goto fail_view;
            }

            if (!XzExpectedCompressedBytes(
                    texture.format,
                    mip.width,
                    mip.height,
                    &expected_bytes) ||
                mip.bytes !=
                    expected_bytes) {
                status = XZ_XZLT_ERR_MIP;
                goto fail_view;
            }

            if (mip_index == 0u &&
                (mip.width != texture.width ||
                 mip.height != texture.height)) {
                status = XZ_XZLT_ERR_MIP;
                goto fail_view;
            }

            payload_end =
                (uint64_t)mip.payload_offset +
                (uint64_t)mip.bytes;

            if (payload_end >
                    (uint64_t)payload_bytes) {
                status = XZ_XZLT_ERR_RANGE;
                goto fail_view;
            }
        }
    }

    for (mip_index = 0u;
         mip_index < mip_count;
         ++mip_index) {
        if (!seen_mips[mip_index]) {
            status = XZ_XZLT_ERR_MIP;
            goto fail_view;
        }
    }

    view->bc1_texture_count =
        bc1_count;
    view->bc3_texture_count =
        bc3_count;
    view->srgb_texture_count =
        srgb_count;
    view->linear_texture_count =
        linear_count;

    free(seen_mips);
    return XZ_XZLT_OK;

fail_view:
    free(seen_mips);
    XzLightmapTexture_Close(view);
    return status;

fail:
    free(seen_mips);
    free(tables);
    if (handle >= 0)
        XzFile_Close(handle);
    XzLightmapTexture_Init(view);
    return status;
}

int XzLightmapTexture_Texture(
    const XzLightmapTextureView *view,
    uint32_t texture_index,
    XzLightmapTextureRecord *record)
{
    return XzTextureRecordAt(
        view,
        texture_index,
        record);
}

int XzLightmapTexture_Mip(
    const XzLightmapTextureView *view,
    uint32_t mip_index,
    XzLightmapMipRecord *record)
{
    return XzMipRecordAt(
        view,
        mip_index,
        record);
}

XzLightmapTextureStatus XzLightmapTexture_ReadMip(
    XzLightmapTextureView *view,
    uint32_t texture_index,
    uint32_t relative_mip,
    void *destination,
    size_t destination_bytes,
    XzLightmapMipRecord *record)
{
    XzLightmapTextureRecord texture;
    XzLightmapMipRecord mip;
    uint32_t absolute_mip;
    uint64_t file_offset;

    if (!view ||
        !view->file_open ||
        view->file_handle < 0 ||
        !destination)
        return XZ_XZLT_ERR_ARGUMENT;

    if (!XzTextureRecordAt(
            view,
            texture_index,
            &texture) ||
        relative_mip >=
            texture.mip_count)
        return XZ_XZLT_ERR_RANGE;

    absolute_mip =
        texture.first_mip +
        relative_mip;

    if (!XzMipRecordAt(
            view,
            absolute_mip,
            &mip))
        return XZ_XZLT_ERR_MIP;

    if ((size_t)mip.bytes >
            destination_bytes)
        return XZ_XZLT_ERR_RANGE;

    file_offset =
        (uint64_t)view->payload_offset +
        (uint64_t)mip.payload_offset;

    if (file_offset >
            INT_MAX ||
        file_offset +
            (uint64_t)mip.bytes >
            (uint64_t)view->file_bytes)
        return XZ_XZLT_ERR_RANGE;

    XzFile_Seek(
        view->file_handle,
        (int)file_offset);

    if (!XzReadExact(
            view->file_handle,
            destination,
            (size_t)mip.bytes))
        return XZ_XZLT_ERR_READ;

    if (record)
        *record = mip;

    return XZ_XZLT_OK;
}

const char *XzLightmapTexture_StatusName(
    XzLightmapTextureStatus status)
{
    switch (status) {
    case XZ_XZLT_OK:
        return "OK";
    case XZ_XZLT_ERR_ARGUMENT:
        return "ARGUMENT";
    case XZ_XZLT_ERR_OPEN:
        return "OPEN";
    case XZ_XZLT_ERR_READ:
        return "READ";
    case XZ_XZLT_ERR_MAGIC:
        return "MAGIC";
    case XZ_XZLT_ERR_VERSION:
        return "VERSION";
    case XZ_XZLT_ERR_HEADER:
        return "HEADER";
    case XZ_XZLT_ERR_COUNT:
        return "COUNT";
    case XZ_XZLT_ERR_TABLE:
        return "TABLE";
    case XZ_XZLT_ERR_TEXTURE:
        return "TEXTURE";
    case XZ_XZLT_ERR_MIP:
        return "MIP";
    case XZ_XZLT_ERR_RANGE:
        return "RANGE";
    case XZ_XZLT_ERR_MEMORY:
        return "MEMORY";
    default:
        return "UNKNOWN";
    }
}
