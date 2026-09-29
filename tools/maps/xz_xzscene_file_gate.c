#include "xz_xzscene.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>

static int ParseU32(const char *text, uint32_t *value)
{
    char *end = NULL;
    unsigned long parsed;

    if (!text || !value || text[0] == '\0')
        return 0;

    errno = 0;
    parsed = strtoul(text, &end, 10);
    if (errno != 0 || !end || *end != '\0' ||
        parsed > 0xfffffffful)
        return 0;

    *value = (uint32_t)parsed;
    return 1;
}

int main(int argc, char **argv)
{
    FILE *file;
    long length;
    unsigned char *data;
    XzXzsceneView scene;
    XzXzsceneStatus status;
    uint32_t expected_meshes;
    uint32_t expected_instances;

    if (argc != 4 ||
        !ParseU32(argv[2], &expected_meshes) ||
        !ParseU32(argv[3], &expected_instances) ||
        expected_meshes == 0u ||
        expected_instances == 0u) {
        fprintf(
            stderr,
            "usage: %s <scene.xzsc> <expected-meshes> <expected-instances>\n",
            argv[0]);
        return 2;
    }

    file = fopen(argv[1], "rb");
    if (!file) {
        fprintf(stderr, "cannot open %s\n", argv[1]);
        return 3;
    }

    if (fseek(file, 0, SEEK_END) != 0 ||
        (length = ftell(file)) <= 0 ||
        fseek(file, 0, SEEK_SET) != 0) {
        fclose(file);
        fprintf(stderr, "invalid XZSC file length\n");
        return 4;
    }

    data = (unsigned char *)malloc((size_t)length);
    if (!data) {
        fclose(file);
        fprintf(stderr, "allocation failed\n");
        return 5;
    }

    if (fread(data, 1, (size_t)length, file) !=
            (size_t)length) {
        free(data);
        fclose(file);
        fprintf(stderr, "read failed\n");
        return 6;
    }
    fclose(file);

    status = XzXzscene_Parse(
        &scene,
        data,
        (size_t)length);
    if (status != XZ_XZSC_OK) {
        fprintf(
            stderr,
            "XZIEL_XZSC_FILE_GATE_FAIL status=%s\n",
            XzXzscene_StatusName(status));
        free(data);
        return 7;
    }

    if (scene.mesh_count != expected_meshes ||
        scene.instance_count != expected_instances) {
        fprintf(
            stderr,
            "XZIEL_XZSC_FILE_GATE_FAIL counts meshes=%u/%u instances=%u/%u\n",
            scene.mesh_count,
            expected_meshes,
            scene.instance_count,
            expected_instances);
        free(data);
        return 8;
    }

    printf(
        "XZIEL_XZSC_FILE_GATE_GREEN meshes=%u instances=%u bytes=%ld scale=%.6f\n",
        scene.mesh_count,
        scene.instance_count,
        length,
        scene.gameplay_units_per_meter);

    free(data);
    return 0;
}
