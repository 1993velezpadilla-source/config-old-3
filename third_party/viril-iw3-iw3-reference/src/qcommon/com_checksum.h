#pragma once

#include <cstdint>
#include <universal/q_shared.h>

// Shared by the original BSP loader and filesystem IWD checksum path. Keeping
// this declaration independent of com_bsp.h avoids pulling renderer headers
// into the filesystem translation unit.
int __cdecl Com_BlockChecksumKey32(
    const uint8_t *data, uint32_t length, uint32_t initialCrc);
