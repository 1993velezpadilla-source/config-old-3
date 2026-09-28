#include "ctw_hook_backend.h"

#include <assert.h>
#include <stdint.h>
#include <string.h>

static void put_u32(uint8_t *p, uint32_t v) {
    memcpy(p, &v, sizeof(v));
}

int main(void) {
    uint8_t safe[CTW_ARM64_OVERWRITE_BYTES];
    put_u32(safe + 0, 0xA9BF7BFDu);
    put_u32(safe + 4, 0x910003FDu);
    put_u32(safe + 8, 0xD10083FFu);
    put_u32(safe + 12, 0xF9000BF3u);

    assert(
        ctw_hook_backend_choose(safe, 0)
        == CTW_HOOK_BACKEND_SIMPLE_COPY
    );
    assert(
        ctw_hook_backend_choose(safe, 1)
        == CTW_HOOK_BACKEND_SIMPLE_COPY
    );

    uint8_t unsafe[CTW_ARM64_OVERWRITE_BYTES];
    memcpy(unsafe, safe, sizeof(unsafe));
    put_u32(unsafe + 4, 0x90000000u); /* adrp */

    assert(
        ctw_hook_backend_choose(unsafe, 0)
        == CTW_HOOK_BACKEND_NONE
    );
    assert(
        ctw_hook_backend_choose(unsafe, 1)
        == CTW_HOOK_BACKEND_DOBBY
    );

    assert(ctw_hook_backend_choose(NULL, 1) == CTW_HOOK_BACKEND_NONE);

#if !defined(CTW_HAVE_DOBBY)
    assert(ctw_hook_backend_dobby_available() == 0);
#endif

    CtwHookBackendState state;
    memset(&state, 0, sizeof(state));
    assert(ctw_hook_backend_uninstall(&state) == 0);

    return 0;
}
