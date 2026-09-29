#include "xz_xzrig.h"
#include "xz_xzskel.h"
#include "xz_xzanim.h"

#include <stdio.h>

int main(void)
{
    if (!XzXzrig_SelfTest()) {
        fprintf(stderr, "XZIEL_XZRG_SELFTEST_FAILURE\n");
        return 4;
    }

    if (!XzXzskel_SelfTest()) {
        fprintf(stderr, "XZIEL_XZSK_SELFTEST_FAILURE\n");
        return 5;
    }

    if (!XzXzanim_SelfTest()) {
        fprintf(stderr, "XZIEL_XZAN_SELFTEST_FAILURE\n");
        return 6;
    }

    printf("XZIEL_NATIVE_RIG_ANIM_SELFTEST_GREEN\n");
    return 0;
}
