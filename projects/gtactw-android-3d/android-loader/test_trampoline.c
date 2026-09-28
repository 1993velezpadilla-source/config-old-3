#include "ctw_trampoline.h"

#include <assert.h>
#include <stdint.h>
#include <string.h>

static void put_u32(uint8_t *p, uint32_t v) {
    memcpy(p, &v, sizeof(v));
}

static uint64_t get_u64(const uint8_t *p) {
    uint64_t v = 0;
    memcpy(&v, p, sizeof(v));
    return v;
}

int main(void) {
    uint8_t safe[16];
    put_u32(safe + 0,  0xA9BF7BFDu); /* stp x29,x30,[sp,#-16]! */
    put_u32(safe + 4,  0x910003FDu); /* mov x29,sp */
    put_u32(safe + 8,  0xD10083FFu); /* sub sp,sp,#0x20 */
    put_u32(safe + 12, 0xF9000BF3u); /* str x19,[sp,#0x10] */

    assert(ctw_arm64_prologue_simple_copy_safe(safe) == 1);

    uint8_t image[CTW_ARM64_TRAMPOLINE_BYTES];
    const uintptr_t resume = (uintptr_t)0x123456789ABCDEF0ull;
    assert(
        ctw_arm64_build_trampoline_image(image, safe, resume) == 0
    );
    assert(memcmp(image, safe, 16) == 0);

    uint32_t word = 0;
    memcpy(&word, image + 16, sizeof(word));
    assert(word == 0x58000050u);
    memcpy(&word, image + 20, sizeof(word));
    assert(word == 0xD61F0200u);
    assert(get_u64(image + 24) == (uint64_t)resume);

    uint8_t unsafe[16];
    memcpy(unsafe, safe, sizeof(unsafe));
    put_u32(unsafe + 4, 0x90000000u); /* adrp */
    assert(ctw_arm64_prologue_simple_copy_safe(unsafe) == 0);
    assert(
        ctw_arm64_build_trampoline_image(image, unsafe, resume) == -2
    );

    memcpy(unsafe, safe, sizeof(unsafe));
    put_u32(unsafe + 8, 0x94000000u); /* bl */
    assert(ctw_arm64_prologue_simple_copy_safe(unsafe) == 0);

    memcpy(unsafe, safe, sizeof(unsafe));
    put_u32(unsafe + 12, 0x58000000u); /* ldr literal */
    assert(ctw_arm64_prologue_simple_copy_safe(unsafe) == 0);

    return 0;
}
