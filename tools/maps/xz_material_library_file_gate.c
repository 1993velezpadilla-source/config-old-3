#include "xz_material_library.h"

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
    XzMaterialLibraryView view;
    XzMaterialLibraryStatus status;
    uint32_t expected_materials;
    uint32_t expected_textures;

    if (argc != 4 ||
        !ParseU32(argv[2], &expected_materials) ||
        !ParseU32(argv[3], &expected_textures) ||
        expected_materials == 0u) {
        fprintf(
            stderr,
            "usage: %s <materials.xzml> <materials> <textures>\n",
            argv[0]);
        return 2;
    }

    if (!XzMaterialLibrary_SelfTest()) {
        fprintf(
            stderr,
            "XZIEL_XZML_SELFTEST_FAIL\n");
        return 3;
    }

    puts("XZIEL_XZML_SELFTEST_GREEN");

    file = fopen(argv[1], "rb");
    if (!file) {
        fprintf(
            stderr,
            "cannot open %s\n",
            argv[1]);
        return 4;
    }

    if (fseek(file, 0, SEEK_END) != 0 ||
        (length = ftell(file)) <= 0 ||
        fseek(file, 0, SEEK_SET) != 0) {
        fclose(file);
        fprintf(stderr, "invalid XZML file length\n");
        return 5;
    }

    data = (unsigned char *)malloc((size_t)length);
    if (!data) {
        fclose(file);
        fprintf(stderr, "allocation failed\n");
        return 6;
    }

    if (fread(data, 1, (size_t)length, file) !=
            (size_t)length) {
        free(data);
        fclose(file);
        fprintf(stderr, "read failed\n");
        return 7;
    }
    fclose(file);

    status =
        XzMaterialLibrary_Parse(
            &view,
            data,
            (size_t)length);

    if (status != XZ_XZML_OK) {
        fprintf(
            stderr,
            "XZIEL_XZML_FILE_GATE_FAIL status=%s\n",
            XzMaterialLibrary_StatusName(status));
        free(data);
        return 8;
    }

    if (view.material_count != expected_materials ||
        view.texture_asset_count != expected_textures) {
        fprintf(
            stderr,
            "XZIEL_XZML_FILE_GATE_FAIL counts "
            "materials=%u/%u textures=%u/%u\n",
            view.material_count,
            expected_materials,
            view.texture_asset_count,
            expected_textures);
        free(data);
        return 9;
    }

    printf(
        "XZIEL_XZML_FILE_GATE_GREEN "
        "materials=%u textures=%u bindings=%u scalars=%u "
        "colors=%u switches=%u bytes=%ld\n",
        view.material_count,
        view.texture_asset_count,
        view.texture_binding_count,
        view.scalar_count,
        view.color_count,
        view.switch_count,
        length);

    free(data);
    return 0;
}
