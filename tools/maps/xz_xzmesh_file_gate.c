#include "xz_xzmesh.h"

#include <stdio.h>
#include <stdlib.h>

static int validate_file(const char *path)
{
    FILE *f;
    long size_long;
    size_t size;
    unsigned char *data;
    XzXzmeshView view;
    XzXzmeshStatus status;

    f = fopen(path, "rb");
    if (!f) {
        fprintf(stderr, "XZIEL_XZMS_FILE_GATE_OPEN_FAIL %s\n", path);
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

    size = (size_t) size_long;
    data = (unsigned char *) malloc(size);
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

    status = XzXzmesh_Parse(&view, data, size);
    if (status != XZ_XZMS_OK) {
        fprintf(
            stderr,
            "XZIEL_XZMS_FILE_GATE_FAIL %s status=%s\n",
            path,
            XzXzmesh_StatusName(status));
        free(data);
        return 0;
    }

    printf(
        "XZIEL_XZMS_FILE_GATE_OK %s vertices=%u indices=%u submeshes=%u flags=0x%08x\n",
        path,
        view.vertex_count,
        view.index_count,
        view.submesh_count,
        view.flags);

    free(data);
    return 1;
}

int main(int argc, char **argv)
{
    int i;

    if (argc < 2) {
        fprintf(stderr, "usage: xz_xzmesh_file_gate <mesh.xzm> [mesh.xzm ...]\n");
        return 2;
    }

    for (i = 1; i < argc; ++i) {
        if (!validate_file(argv[i]))
            return 5;
    }

    printf("XZIEL_XZMS_NATIVE_FILES_GREEN count=%d\n", argc - 1);
    return 0;
}
