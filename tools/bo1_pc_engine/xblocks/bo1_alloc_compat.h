#pragma once
// C++ platform ABI boundary for original recovered BO1 DB_AllocXBlocks.
// All source function bodies remain unchanged; native pointers are 64-bit.
#include <cstdint>
#include <cstddef>
#ifndef __cdecl
#define __cdecl
#endif
constexpr int ERR_DROP = 1;
struct XBlock {
    unsigned char* data;
    unsigned int size;
};
static_assert(sizeof(void*)==8, "This bridge is specifically Android ARM64");
static_assert(sizeof(XBlock)==16, "64-bit host block; original Win32 block is 8 bytes");
unsigned char *__cdecl DB_MemAlloc(unsigned int size,unsigned int type,
                                 unsigned int allocType,const char *filename,int flags);
int __cdecl PMem_GetOverAllocatedSize();
void __cdecl Com_Error(int error,const char *format,...);
void __cdecl Com_Printf(int channel,const char *format,...);
void __cdecl DB_AllocXBlocks(unsigned int *blockSize,const char *filename,
                             XBlock *blocks,unsigned int allocType,int flags);
extern "C" __attribute__((visibility("default")))
int bo1_original_xblock_allocation_smoke();
