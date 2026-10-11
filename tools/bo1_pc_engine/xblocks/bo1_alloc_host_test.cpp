// Host-side execution of authentic BO1 memory allocator body with safe POSIX
// backing storage. No map or proprietary game data.
#include "bo1_alloc_compat.h"
#include <cstdio>
int main() {
    if(bo1_original_xblock_allocation_smoke()!=0) return 1;
    for(int i=0;i<10;++i)
        if(bo1_original_xblock_allocation_smoke()!=0) return 2;
    std::puts("ORIGINAL_BO1_DB_ALLOCXBLOCKS_SEVEN_BLOCKS_HOST=PASS");
    std::puts("ORIGINAL_BO1_DB_ALLOCXBLOCKS_ARM64_BOUNDARY=READY_FOR_CROSS_COMPILE");
    std::puts("XASSET_POINTER_RELOCATION=NOT_IMPLEMENTED");
    return 0;
}
