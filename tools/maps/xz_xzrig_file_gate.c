#include "xz_xzrig.h"

#include <stdio.h>
#include <stdlib.h>

static int validate_file(const char *path)
{
    FILE *f;
    long size_long;
    size_t size;
    unsigned char *data;
    XzXzrigView view;
    XzXzrigStatus status;

    f = fopen(path, "rb");
    if (!f)
        return 0;

    if (fseek(f, 0, SEEK_END) != 0) {
        fclose(f);
        return 0;
    }

    size_long = ftell(f);
    if (size_long <= 0 ||
        fseek(f, 0, SEEK_SET) != 0) {
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

    status = XzXzrig_Parse(&view, data, size);
    if (status != XZ_XZRG_OK) {
        fprintf(
            stderr,
            "XZIEL_XZRG_FILE_GATE_FAIL %s status=%s\n",
            path,
            XzXzrig_StatusName(status));
        free(data);
        return 0;
    }

    printf(
        "XZIEL_XZRG_FILE_GATE_OK %s bones=%u skeleton=%016llx pose=%016llx\n",
        path,
        view.bone_count,
        (unsigned long long)view.skeleton_hash,
        (unsigned long long)view.pose_hash);

    free(data);
    return 1;
}

int main(int argc, char **argv)
{
    int i;

    if (argc < 2) {
        fprintf(
            stderr,
            "usage: xz_xzrig_file_gate <rig.xrg> [rig.xrg ...]\n");
        return 2;
    }

    for (i = 1; i < argc; ++i) {
        if (!validate_file(argv[i]))
            return 5;
    }

    printf(
        "XZIEL_XZRG_NATIVE_FILES_GREEN count=%d\n",
        argc - 1);
    return 0;
}
