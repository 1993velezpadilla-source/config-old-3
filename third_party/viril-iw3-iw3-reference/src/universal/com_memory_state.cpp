#include "com_memory_state.h"
// One engine-owned definition shared by the original memory module and the
// Android ARM64 dependency audit. These globals were zero-initialized in
// com_memory.cpp; moving their storage does not create a second allocator state.
hunkUsed_t hunk_high{};
hunkUsed_t hunk_low{};
unsigned char *s_hunkData = nullptr;
uint8_t *s_origHunkData = nullptr;
int32_t s_hunkTotal = 0;
