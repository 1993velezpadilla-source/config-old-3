#include "xz_xzskel.h"

#include <stdio.h>
#include <stdlib.h>

static int validate_file(
    const char *path)
{
    FILE *f;
    long size_long;
    size_t size;
    unsigned char *data;
    XzXzskelView view;
    XzXzskelStatus status;

    f = fopen(path, "rb");
    if (!f) {
        fprintf(
            stderr,
            "XZIEL_XZSK_FILE_GATE_OPEN_FAIL %s\n",
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
        XzXzskel_Parse(
            &view,
            data,
            size);

    if (status != XZ_XZSK_OK) {
        fprintf(
            stderr,
            "XZIEL_XZSK_FILE_GATE_FAIL %s status=%s\n",
            path,
            XzXzskel_StatusName(status));
        free(data);
        return 0;
    }

    printf(
        "XZIEL_XZSK_FILE_GATE_OK %s bones=%u skeletonBones=%u vertices=%u indices=%u sections=%u skeleton=%016llx meshLayout=%016llx\n",
        path,
        view.bone_count,
        view.skeleton_bone_count,
        view.vertex_count,
        view.index_count,
        view.section_count,
        (unsigned long long)view.skeleton_hash,
        (unsigned long long)view.mesh_layout_hash);

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
            "usage: xz_xzskel_file_gate <mesh.xsk> [mesh.xsk ...]\n");
        return 2;
    }

    for (i = 1; i < argc; ++i) {
        if (!validate_file(argv[i]))
            return 5;
    }

    printf(
        "XZIEL_XZSK_NATIVE_FILES_GREEN count=%d\n",
        argc - 1);
    return 0;
}
