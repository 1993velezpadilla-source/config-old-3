#include "xz_xzmesh.h"

#include <stdio.h>

int main(void)
{
    if (!XzXzmesh_SelfTest()) {
        fprintf(stderr, "XZIEL_XZMS_LOADER_TEST_FAIL\n");
        return 1;
    }

    printf(
        "XZIEL_XZMS_LOADER_TEST_OK "
        "header=%u vertexStride=%u submeshStride=%u\n",
        (unsigned int)XZ_XZMS_HEADER_BYTES,
        (unsigned int)XZ_XZMS_VERTEX_BYTES,
        (unsigned int)XZ_XZMS_SUBMESH_BYTES);
    return 0;
}
