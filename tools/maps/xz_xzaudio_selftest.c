#include "xz_xzaudio.h"

#include <stdio.h>

int main(void)
{
    if (!XzXzaudio_SelfTest()) {
        fprintf(
            stderr,
            "XZIEL_XZAW_NATIVE_SELFTEST_FAILURE\n");
        return 5;
    }

    printf(
        "XZIEL_XZAW_NATIVE_SELFTEST_GREEN\n");
    return 0;
}
