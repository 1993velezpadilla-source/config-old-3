#ifndef XZ_VRIL_IMAGE_DECODE_H
#define XZ_VRIL_IMAGE_DECODE_H

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Vril-facing image decode bridge.
 *
 * Paths are VFS-relative and omit the extension. The decoder probes the
 * formats already supported by Vril (TGA/PNG/JPG) and returns malloc-owned
 * RGBA8 pixels. Call XzVrilImage_Free() after the GLES upload completes.
 */
int XzVrilImage_LoadRgba(
    const char *vfs_path_without_extension,
    unsigned char **out_pixels,
    unsigned int *out_width,
    unsigned int *out_height);

void XzVrilImage_Free(void *pixels);

#ifdef __cplusplus
}
#endif

#endif
