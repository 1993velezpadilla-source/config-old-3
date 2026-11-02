#pragma once

// Shared declaration for the original engine's fast reader/writer lock.
// Kept outside win_local.h so Android can compile authentic dvar/filesystem
// translation units without importing DirectInput or other Win32 headers.
#include <stddef.h>
#include <stdint.h>

struct FastCriticalSection
{
    volatile uint32_t readCount;
    volatile uint32_t writeCount;
};

static_assert(sizeof(FastCriticalSection) == 8,
              "FastCriticalSection must retain the original 32-bit counter layout");
static_assert(offsetof(FastCriticalSection, writeCount) == 4,
              "FastCriticalSection writeCount ABI offset changed");

void Sys_LockWrite(FastCriticalSection *critSect);
void Sys_UnlockWrite(FastCriticalSection *critSect);
