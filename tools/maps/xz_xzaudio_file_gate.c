#include "xz_xzaudio.h"

#include <stdio.h>
#include <stdlib.h>

static int validate_file(
    const char *path)
{
    FILE *f;
    long size_long;
    size_t size;
    unsigned char *data;
    XzXzaudioView view;
    XzXzaudioStatus status;
    size_t payload_bytes = 0u;
    const void *payload;

    f = fopen(path, "rb");
    if (!f) {
        fprintf(
            stderr,
            "XZIEL_XZAW_FILE_GATE_OPEN_FAIL %s\n",
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
        XzXzaudio_Parse(
            &view,
            data,
            size);

    if (status != XZ_XZAW_OK) {
        fprintf(
            stderr,
            "XZIEL_XZAW_FILE_GATE_FAIL %s status=%s\n",
            path,
            XzXzaudio_StatusName(status));
        free(data);
        return 0;
    }

    payload =
        XzXzaudio_Payload(
            &view,
            &payload_bytes);

    if (!payload ||
        payload_bytes != view.payload_bytes) {
        free(data);
        return 0;
    }

    printf(
        "XZIEL_XZAW_FILE_GATE_OK %s format=%s streaming=%u payload=%u\n",
        path,
        view.format_name,
        (view.flags &
         XZ_XZAW_FLAG_SOURCE_STREAMING) != 0u,
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
            "usage: xz_xzaudio_file_gate <audio.xaw> [audio.xaw ...]\n");
        return 2;
    }

    for (i = 1; i < argc; ++i) {
        if (!validate_file(argv[i]))
            return 5;
    }

    printf(
        "XZIEL_XZAW_NATIVE_FILES_GREEN count=%d\n",
        argc - 1);
    return 0;
}
