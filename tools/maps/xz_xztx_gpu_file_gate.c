#include "xz_xztexture.h"
#include "xz_xztx_gpu_format.h"

#include <stdio.h>
#include <stdlib.h>

static int CheckFile(
    const char *path,
    uint64_t *out_payload,
    uint64_t *out_mips,
    uint64_t *out_srgb)
{
    FILE *file;
    long length;
    unsigned char *data;
    XzXztextureView texture;
    XzXztxGpuFormat format;
    XzXztextureStatus texture_status;
    XzXztxGpuStatus gpu_status;
    uint64_t expected_payload = 0u;

    if (!path ||
        !out_payload ||
        !out_mips ||
        !out_srgb)
        return 0;

    file = fopen(path, "rb");
    if (!file) {
        fprintf(stderr, "cannot open %s\n", path);
        return 0;
    }

    if (fseek(file, 0, SEEK_END) != 0 ||
        (length = ftell(file)) <= 0 ||
        fseek(file, 0, SEEK_SET) != 0) {
        fclose(file);
        fprintf(stderr, "bad file length %s\n", path);
        return 0;
    }

    data = (unsigned char *)malloc((size_t)length);
    if (!data) {
        fclose(file);
        fprintf(stderr, "allocation failed %s\n", path);
        return 0;
    }

    if (fread(data, 1, (size_t)length, file) !=
            (size_t)length) {
        free(data);
        fclose(file);
        fprintf(stderr, "read failed %s\n", path);
        return 0;
    }

    fclose(file);

    texture_status =
        XzXztexture_Parse(
            &texture,
            data,
            (size_t)length);

    if (texture_status != XZ_XZTX_OK) {
        fprintf(
            stderr,
            "XZIEL_XZTX_GPU_FILE_FAIL path=%s parse=%s\n",
            path,
            XzXztexture_StatusName(texture_status));
        free(data);
        return 0;
    }

    gpu_status =
        XzXztxGpuFormat_Resolve(
            &texture,
            &format);

    if (gpu_status != XZ_XZTX_GPU_OK) {
        fprintf(
            stderr,
            "XZIEL_XZTX_GPU_FILE_FAIL path=%s resolve=%s format=%s\n",
            path,
            XzXztxGpuFormat_StatusName(gpu_status),
            texture.format_name);
        free(data);
        return 0;
    }

    gpu_status =
        XzXztxGpuFormat_ValidatePayload(
            &texture,
            &format,
            &expected_payload);

    if (gpu_status != XZ_XZTX_GPU_OK) {
        fprintf(
            stderr,
            "XZIEL_XZTX_GPU_FILE_FAIL path=%s payload=%s format=%s\n",
            path,
            XzXztxGpuFormat_StatusName(gpu_status),
            texture.format_name);
        free(data);
        return 0;
    }

    *out_payload += expected_payload;
    *out_mips += texture.mip_count;
    if (format.srgb)
        (*out_srgb)++;

    printf(
        "XZIEL_XZTX_GPU_FILE_GREEN path=%s "
        "format=%s srgb=%u mips=%u payload=%llu gl=0x%04X\n",
        path,
        texture.format_name,
        format.srgb,
        texture.mip_count,
        (unsigned long long)expected_payload,
        format.gl_internal_format);

    free(data);
    return 1;
}

int main(int argc, char **argv)
{
    uint64_t payload = 0u;
    uint64_t mips = 0u;
    uint64_t srgb = 0u;
    int i;

    if (argc < 2) {
        fprintf(
            stderr,
            "usage: %s <texture.xzt> [texture.xzt ...]\n",
            argv[0]);
        return 2;
    }

    if (!XzXztexture_SelfTest() ||
        !XzXztxGpuFormat_SelfTest()) {
        fprintf(
            stderr,
            "XZIEL_XZTX_GPU_SELFTEST_FAIL\n");
        return 3;
    }

    puts("XZIEL_XZTX_GPU_SELFTEST_GREEN");

    for (i = 1; i < argc; ++i) {
        if (!CheckFile(
                argv[i],
                &payload,
                &mips,
                &srgb))
            return 4;
    }

    printf(
        "XZIEL_XZTX_GPU_BATCH_GREEN "
        "files=%d mips=%llu payload=%llu srgb=%llu linear=%llu\n",
        argc - 1,
        (unsigned long long)mips,
        (unsigned long long)payload,
        (unsigned long long)srgb,
        (unsigned long long)((uint64_t)(argc - 1) - srgb));

    return 0;
}
