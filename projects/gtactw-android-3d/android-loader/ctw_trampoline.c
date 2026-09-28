#include "ctw_trampoline.h"

#include <string.h>

#if defined(__aarch64__)
#include <sys/mman.h>
#include <unistd.h>
#endif

static uint32_t read_u32_le(const uint8_t *p) {
    uint32_t v = 0;
    memcpy(&v, p, sizeof(v));
    return v;
}

static int instruction_is_simple_copy_safe(uint32_t insn) {
    /* ADR / ADRP. */
    if ((insn & 0x9F000000u) == 0x10000000u)
        return 0;
    if ((insn & 0x9F000000u) == 0x90000000u)
        return 0;

    /* B / BL. */
    if ((insn & 0xFC000000u) == 0x14000000u)
        return 0;
    if ((insn & 0xFC000000u) == 0x94000000u)
        return 0;

    /* B.cond. */
    if ((insn & 0xFF000010u) == 0x54000000u)
        return 0;

    /* CBZ / CBNZ. */
    if ((insn & 0x7E000000u) == 0x34000000u)
        return 0;

    /* TBZ / TBNZ. */
    if ((insn & 0x7E000000u) == 0x36000000u)
        return 0;

    /* Literal load/prefetch family. */
    if ((insn & 0x3B000000u) == 0x18000000u)
        return 0;

    /* RET / BR / BLR. */
    if ((insn & 0xFFFFFC1Fu) == 0xD65F0000u)
        return 0;
    if ((insn & 0xFFFFFC1Fu) == 0xD61F0000u)
        return 0;
    if ((insn & 0xFFFFFC1Fu) == 0xD63F0000u)
        return 0;

    return 1;
}

int ctw_arm64_prologue_simple_copy_safe(
    const uint8_t code[CTW_ARM64_OVERWRITE_BYTES]
) {
    if (!code)
        return 0;

    for (size_t i = 0; i < CTW_ARM64_OVERWRITE_BYTES; i += 4) {
        if (!instruction_is_simple_copy_safe(read_u32_le(code + i)))
            return 0;
    }
    return 1;
}

int ctw_arm64_build_trampoline_image(
    uint8_t out[CTW_ARM64_TRAMPOLINE_BYTES],
    const uint8_t original[CTW_ARM64_OVERWRITE_BYTES],
    uintptr_t resume_address
) {
    if (!out || !original || !resume_address)
        return -1;
    if (!ctw_arm64_prologue_simple_copy_safe(original))
        return -2;

    memcpy(out, original, CTW_ARM64_OVERWRITE_BYTES);

    /* ldr x16, #8 ; br x16 ; .quad resume_address */
    const uint32_t ldr_x16_literal = 0x58000050u;
    const uint32_t br_x16 = 0xD61F0200u;
    memcpy(out + 16, &ldr_x16_literal, sizeof(ldr_x16_literal));
    memcpy(out + 20, &br_x16, sizeof(br_x16));
    const uint64_t resume = (uint64_t)resume_address;
    memcpy(out + 24, &resume, sizeof(resume));

    return 0;
}

int ctw_arm64_create_simple_trampoline(
    void *target,
    CtwArm64Trampoline *out
) {
#if defined(__aarch64__)
    if (!target || !out)
        return -1;

    memset(out, 0, sizeof(*out));

    uint8_t image[CTW_ARM64_TRAMPOLINE_BYTES];
    const int build_rc = ctw_arm64_build_trampoline_image(
        image,
        (const uint8_t *)target,
        (uintptr_t)target + CTW_ARM64_OVERWRITE_BYTES
    );
    if (build_rc != 0)
        return build_rc;

    long page = sysconf(_SC_PAGESIZE);
    if (page <= 0)
        page = 4096;

    void *mem = mmap(
        NULL,
        (size_t)page,
        PROT_READ | PROT_WRITE,
        MAP_PRIVATE | MAP_ANONYMOUS,
        -1,
        0
    );
    if (mem == MAP_FAILED)
        return -3;

    memcpy(mem, image, sizeof(image));
    __builtin___clear_cache(
        (char *)mem,
        (char *)mem + sizeof(image)
    );

    if (mprotect(mem, (size_t)page, PROT_READ | PROT_EXEC) != 0) {
        munmap(mem, (size_t)page);
        return -4;
    }

    out->entry = mem;
    out->allocation = mem;
    out->allocation_size = (size_t)page;
    return 0;
#else
    (void)target;
    (void)out;
    return -100;
#endif
}

void ctw_arm64_destroy_trampoline(CtwArm64Trampoline *trampoline) {
    if (!trampoline)
        return;

#if defined(__aarch64__)
    if (trampoline->allocation && trampoline->allocation_size)
        munmap(trampoline->allocation, trampoline->allocation_size);
#endif

    trampoline->entry = NULL;
    trampoline->allocation = NULL;
    trampoline->allocation_size = 0;
}
