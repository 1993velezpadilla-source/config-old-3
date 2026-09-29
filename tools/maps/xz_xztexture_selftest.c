#include "xz_xztexture.h"

#include <stdio.h>

int main(void)
{
    if (!XzXztexture_SelfTest()) {
        fprintf(
            stderr,
            "XZIEL_XZTX_NATIVE_SELFTEST_FAILURE\n");
        return 5;
    }

    printf(
        "XZIEL_XZTX_NATIVE_SELFTEST_GREEN\n");
    return 0;
}
