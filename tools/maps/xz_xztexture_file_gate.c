#include "xz_xztexture.h"

#include <stdio.h>
#include <stdlib.h>

static int validate_file(
    const char *path)
{
    FILE *f;
    long size_long;
    size_t size;
    unsigned char *data;
    XzXztextureView view;
    XzXztextureStatus status;
    uint32_t i;
    uint64_t payload_total = 0u;

    f = fopen(path, "rb");
    if (!f) {
        fprintf(
            stderr,
            "XZIEL_XZTX_FILE_GATE_OPEN_FAIL %s\n",
            path);
        return 0;
    }

    if (fseek(f, 0, SEEK_END) != 0) {
        fclose(f);
        return 0;
    }

    size_long = ftell(f);
    if (size_long <= 0) {
        fclose(f);
        return 0;
    }

    if (fseek(f, 0, SEEK_SET) != 0) {
        fclose(f);
        return 0;
    }

    size = (size_t)size_long;
    data = (unsigned char *)malloc(size);
    if (!data) {
        fclose(f);
        return 0;
    }

    if (fread(data, 1u, size, f) != size) {
        free(data);
        fclose(f);
        return 0;
    }

    fclose(f);

    status =
        XzXztexture_Parse(
            &view,
            data,
            size);

    if (status != XZ_XZTX_OK) {
        fprintf(
            stderr,
            "XZIEL_XZTX_FILE_GATE_FAIL %s status=%s\n",
            path,
            XzXztexture_StatusName(status));
        free(data);
        return 0;
    }

    for (i = 0u; i < view.mip_count; ++i) {
        XzXztextureMip mip;
        if (!XzXztexture_Mip(
                &view,
                i,
                &mip)) {
            free(data);
            return 0;
        }
        payload_total += mip.payload_bytes;
    }

    if (payload_total !=
        (uint64_t)view.payload_bytes) {
        free(data);
        return 0;
    }

    printf(
        "XZIEL_XZTX_FILE_GATE_OK %s format=%s size=%ux%ux%u mips=%u srgb=%u payload=%u\n",
        path,
        view.format_name,
        view.width,
        view.height,
        view.depth,
        view.mip_count,
        (view.flags & XZ_XZTX_FLAG_SRGB) != 0u,
        view.payload_bytes);

    free(data);
    return 1;
}

int main(
    int argc,
    char **argv)
{
    int i;

    if (argc < 2) {
        fprintf(
            stderr,
            "usage: xz_xztexture_file_gate <texture.xzt> [texture.xzt ...]\n");
        return 2;
    }

    for (i = 1; i < argc; ++i) {
        if (!validate_file(argv[i]))
            return 5;
    }

    printf(
        "XZIEL_XZTX_NATIVE_FILES_GREEN count=%d\n",
        argc - 1);
    return 0;
}
