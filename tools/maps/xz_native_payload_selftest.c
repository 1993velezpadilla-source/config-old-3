#include "xz_native_payload.h"

#include <stdio.h>

int main(void)
{
    if (!XzNativePayload_SelfTest()) {
        fprintf(
            stderr,
            "XZIEL_NATIVE_RIG_ANIM_SELFTEST_FAILURE\n");
        return 5;
    }

    printf(
        "XZIEL_NATIVE_RIG_ANIM_SELFTEST_GREEN\n");
    return 0;
}
