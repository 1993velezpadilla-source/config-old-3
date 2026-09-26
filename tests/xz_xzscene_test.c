#include "xz_xzscene.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>

static int ParseFile(const char *path)
{
    FILE *file;
    long length;
    unsigned char *data;
    XzXzsceneView scene;
    XzXzsceneStatus status;

    file = fopen(path, "rb");
    if (!file) {
        fprintf(stderr, "cannot open %s\n", path);
        return 0;
    }

    if (fseek(file, 0, SEEK_END) != 0) {
        fclose(file);
        return 0;
    }

    length = ftell(file);
    if (length <= 0) {
        fclose(file);
        return 0;
    }

    if (fseek(file, 0, SEEK_SET) != 0) {
        fclose(file);
        return 0;
    }

    data = (unsigned char *)malloc(
        (size_t)length);
    if (!data) {
        fclose(file);
        return 0;
    }

    if (fread(
            data,
            1,
            (size_t)length,
            file) != (size_t)length) {
        free(data);
        fclose(file);
        return 0;
    }

    fclose(file);

    status = XzXzscene_Parse(
        &scene,
        data,
        (size_t)length);

    if (status != XZ_XZSC_OK) {
        fprintf(
            stderr,
            "XZSC parse failed: %s\n",
            XzXzscene_StatusName(status));
        free(data);
        return 0;
    }

    if (scene.mesh_count != 492u ||
        scene.instance_count != 10791u ||
        fabsf(
            scene.gameplay_units_per_meter -
            39.3700787402f) > 0.001f) {
        fprintf(
            stderr,
            "XZSC Nacht contract mismatch "
            "meshes=%u instances=%u scale=%f\n",
            scene.mesh_count,
            scene.instance_count,
            scene.gameplay_units_per_meter);
        free(data);
        return 0;
    }

    printf(
        "XZIEL_XZSC_FILE_OK "
        "meshes=%u instances=%u bytes=%ld scale=%.6f\n",
        scene.mesh_count,
        scene.instance_count,
        length,
        scene.gameplay_units_per_meter);

    free(data);
    return 1;
}

int main(int argc, char **argv)
{
    if (!XzXzscene_SelfTest()) {
        fprintf(
            stderr,
            "XZIEL_XZSC_SELFTEST_FAIL\n");
        return 1;
    }

    if (argc == 2 &&
        !ParseFile(argv[1]))
        return 1;

    printf(
        "XZIEL_XZSC_SELFTEST_OK "
        "header=%u meshStride=%u instanceStride=%u\n",
        (unsigned int)XZ_XZSC_HEADER_BYTES,
        (unsigned int)XZ_XZSC_MESH_RECORD_BYTES,
        (unsigned int)XZ_XZSC_INSTANCE_BYTES);

    return 0;
}
