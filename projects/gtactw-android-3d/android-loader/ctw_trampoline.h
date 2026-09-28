#pragma once

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CTW_ARM64_OVERWRITE_BYTES 16
#define CTW_ARM64_TRAMPOLINE_BYTES 32

typedef struct {
    void *entry;
    void *allocation;
    size_t allocation_size;
} CtwArm64Trampoline;

/* Returns 1 when a simple 16-byte prologue copy is position-independent. */
int ctw_arm64_prologue_simple_copy_safe(
    const uint8_t code[CTW_ARM64_OVERWRITE_BYTES]
);

/*
 * Build the 32-byte trampoline image:
 *   copied original 16 bytes
 *   ldr x16,#8 ; br x16 ; .quad target+16
 */
int ctw_arm64_build_trampoline_image(
    uint8_t out[CTW_ARM64_TRAMPOLINE_BYTES],
    const uint8_t original[CTW_ARM64_OVERWRITE_BYTES],
    uintptr_t resume_address
);

int ctw_arm64_create_simple_trampoline(
    void *target,
    CtwArm64Trampoline *out
);

void ctw_arm64_destroy_trampoline(CtwArm64Trampoline *trampoline);

#ifdef __cplusplus
}
#endif
