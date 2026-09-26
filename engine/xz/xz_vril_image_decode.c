#include "xz_vril_image_decode.h"

#include "nzportable_def.h"
#include "images.h"

#include <stdlib.h>
#include <string.h>

extern int image_width;
extern int image_height;

int XzVrilImage_LoadRgba(
    const char *vfs_path_without_extension,
    unsigned char **out_pixels,
    unsigned int *out_width,
    unsigned int *out_height)
{
    byte *pixels;

    if (out_pixels)
        *out_pixels = NULL;
    if (out_width)
        *out_width = 0u;
    if (out_height)
        *out_height = 0u;

    if (!vfs_path_without_extension ||
        !vfs_path_without_extension[0] ||
        !out_pixels ||
        !out_width ||
        !out_height)
        return 0;

    /*
     * Image_LoadPixels uses Vril's COM_FOpenFile VFS and stb_image decoder.
     * It returns RGBA8 allocated by stb_image/malloc and updates these two
     * legacy dimensions synchronously.
     */
    pixels = Image_LoadPixels(
        (char *)vfs_path_without_extension,
        IMAGE_TGA | IMAGE_PNG | IMAGE_JPG);

    if (!pixels ||
        image_width <= 0 ||
        image_height <= 0) {
        free(pixels);
        return 0;
    }

    *out_pixels = (unsigned char *)pixels;
    *out_width = (unsigned int)image_width;
    *out_height = (unsigned int)image_height;
    return 1;
}

void XzVrilImage_Free(void *pixels)
{
    free(pixels);
}
