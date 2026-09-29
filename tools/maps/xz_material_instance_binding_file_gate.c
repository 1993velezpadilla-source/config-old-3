#include "xz_material_instance_binding.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>

static int ParseU32(
    const char *text,
    uint32_t *value)
{
    char *end = NULL;
    unsigned long parsed;

    if (!text || !value || text[0] == '\0')
        return 0;

    errno = 0;
    parsed = strtoul(text, &end, 10);
    if (errno != 0 ||
        !end ||
        *end != '\0' ||
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
    XzMaterialInstanceBindingView view;
    XzMaterialInstanceBindingStatus status;
    uint32_t expected_instances;
    uint32_t expected_materials;
    uint32_t expected_bindings;

    if (argc != 5 ||
        !ParseU32(argv[2], &expected_instances) ||
        !ParseU32(argv[3], &expected_materials) ||
        !ParseU32(argv[4], &expected_bindings) ||
        expected_instances == 0u ||
        expected_materials == 0u ||
        expected_bindings == 0u) {
        fprintf(
            stderr,
            "usage: %s <materials.xzmi> <instances> <materials> <bindings>\n",
            argv[0]);
        return 2;
    }

    if (!XzMaterialInstanceBinding_SelfTest()) {
        fprintf(
            stderr,
            "XZIEL_XZMI_SELFTEST_FAIL\n");
        return 9;
    }

    printf("XZIEL_XZMI_SELFTEST_GREEN\n");

    file = fopen(argv[1], "rb");
    if (!file) {
        fprintf(
            stderr,
            "cannot open %s\n",
            argv[1]);
        return 3;
    }

    if (fseek(file, 0, SEEK_END) != 0 ||
        (length = ftell(file)) <= 0 ||
        fseek(file, 0, SEEK_SET) != 0) {
        fclose(file);
        fprintf(stderr, "invalid XZMI file length\n");
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

    status =
        XzMaterialInstanceBinding_Parse(
            &view,
            data,
            (size_t)length);

    if (status != XZ_XZMI_OK) {
        fprintf(
            stderr,
            "XZIEL_XZMI_FILE_GATE_FAIL status=%s\n",
            XzMaterialInstanceBinding_StatusName(
                status));
        free(data);
        return 7;
    }

    if (view.instance_count != expected_instances ||
        view.material_count != expected_materials ||
        view.binding_count != expected_bindings) {
        fprintf(
            stderr,
            "XZIEL_XZMI_FILE_GATE_FAIL counts "
            "instances=%u/%u materials=%u/%u bindings=%u/%u\n",
            view.instance_count,
            expected_instances,
            view.material_count,
            expected_materials,
            view.binding_count,
            expected_bindings);
        free(data);
        return 8;
    }

    printf(
        "XZIEL_XZMI_FILE_GATE_GREEN "
        "instances=%u materials=%u bindings=%u bytes=%ld\n",
        view.instance_count,
        view.material_count,
        view.binding_count,
        length);

    free(data);
    return 0;
}
