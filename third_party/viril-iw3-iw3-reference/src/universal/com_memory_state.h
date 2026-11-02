#pragma once
#include <stdint.h>
#include <stddef.h>

struct hunkUsed_t { int32_t permanent; int32_t temp; };
struct hunkHeader_t {
    uint32_t magic;
    int32_t size;
    const char *name;
#if UINTPTR_MAX == UINT32_MAX
    int32_t dummy;
#endif
};
static_assert(sizeof(hunkUsed_t) == 8, "Unexpected IW3 Hunk counter layout");
static_assert(sizeof(hunkHeader_t) == 16, "IW3 temporary Hunk header must remain 16 bytes");
extern hunkUsed_t hunk_high;
extern hunkUsed_t hunk_low;
extern unsigned char *s_hunkData;
extern uint8_t *s_origHunkData;
extern int32_t s_hunkTotal;
inline uint8_t *Hunk_PageBase(const void *address) noexcept {
    return reinterpret_cast<uint8_t *>(
        reinterpret_cast<uintptr_t>(address) & ~static_cast<uintptr_t>(0xFFFu));
}
