#include "xz_environment.h"

#include <stdio.h>
#include <stdlib.h>

static unsigned char *ReadAll(
    const char *path,
    size_t *bytes_out)
{
    FILE *f;
    long length;
    unsigned char *data;

    if (!path || !bytes_out)
        return NULL;

    *bytes_out = 0u;
    f = fopen(path, "rb");
    if (!f)
        return NULL;

    if (fseek(f, 0, SEEK_END) != 0) {
        fclose(f);
        return NULL;
    }

    length = ftell(f);
    if (length <= 0 ||
        fseek(f, 0, SEEK_SET) != 0) {
        fclose(f);
        return NULL;
    }

    data = (unsigned char *)malloc((size_t)length);
    if (!data) {
        fclose(f);
        return NULL;
    }

    if (fread(data, 1u, (size_t)length, f) !=
        (size_t)length) {
        free(data);
        fclose(f);
        return NULL;
    }

    fclose(f);
    *bytes_out = (size_t)length;
    return data;
}

int main(int argc, char **argv)
{
    XzEnvironmentView view;
    XzEnvironmentStatus status;
    unsigned char *data;
    size_t bytes;
    unsigned long expected_total;
    unsigned long expected_point;
    unsigned long expected_spot;
    unsigned long expected_directional;
    unsigned long expected_sky;
    uint32_t i;

    if (argc != 7) {
        fprintf(stderr,
            "usage: xz_environment_file_gate <file> <total> <point> <spot> <directional> <sky>\n");
        return 2;
    }

    expected_total = strtoul(argv[2], NULL, 10);
    expected_point = strtoul(argv[3], NULL, 10);
    expected_spot = strtoul(argv[4], NULL, 10);
    expected_directional = strtoul(argv[5], NULL, 10);
    expected_sky = strtoul(argv[6], NULL, 10);

    data = ReadAll(argv[1], &bytes);
    if (!data)
        return 3;

    status = XzEnvironment_Parse(&view, data, bytes);
    if (status != XZ_ENV_OK) {
        fprintf(stderr,
            "XZIEL_XZEN_FILE_GATE_FAIL status=%s\n",
            XzEnvironment_StatusName(status));
        free(data);
        return 4;
    }

    if (view.light_count != expected_total ||
        view.point_count != expected_point ||
        view.spot_count != expected_spot ||
        view.directional_count != expected_directional ||
        view.sky_count != expected_sky) {
        fprintf(stderr,
            "XZIEL_XZEN_FILE_GATE_FAIL counts=%u,%u,%u,%u,%u expected=%lu,%lu,%lu,%lu,%lu\n",
            view.light_count,
            view.point_count,
            view.spot_count,
            view.directional_count,
            view.sky_count,
            expected_total,
            expected_point,
            expected_spot,
            expected_directional,
            expected_sky);
        free(data);
        return 5;
    }

    for (i = 0u; i < view.light_count; ++i) {
        XzEnvironmentLight light;
        if (!XzEnvironment_ReadLight(&view, i, &light)) {
            fprintf(stderr,
                "XZIEL_XZEN_FILE_GATE_FAIL light=%u\n",
                i);
            free(data);
            return 6;
        }
    }

    printf(
        "XZIEL_XZEN_FILE_GATE_GREEN lights=%u point=%u spot=%u directional=%u sky=%u bytes=%zu\n",
        view.light_count,
        view.point_count,
        view.spot_count,
        view.directional_count,
        view.sky_count,
        bytes);

    free(data);
    return 0;
}
