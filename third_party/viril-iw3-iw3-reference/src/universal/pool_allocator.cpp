#include <universal/q_shared.h>
#include "pool_allocator.h"
#include "assertive.h"
#include <cstdint>
#include <cstddef>
#include <cstdlib>

void __cdecl Pool_Init(char *pool, pooldata_t *pooldata, uint32_t itemSize, uint32_t itemCount)
{
    // The original reconstructed IW3 used uint32_t for each free-list link
    // and truncated pointers via (uint32_t)&pool[offset]. That corrupts
    // allocations on 64-bit Android. Keep the original freelist algorithm,
    // but write actual freenode* links on both 32-bit Windows and ARM64.
    if (!pool || !pooldata ||
        itemSize < sizeof(freenode) || itemCount < 2 ||
        (reinterpret_cast<std::uintptr_t>(pool) % alignof(freenode)) != 0 ||
        (itemSize % alignof(freenode)) != 0)
    {
        MyAssertHandler(".\\universal\\pool_allocator.cpp", 18, 0,
                        "%s", "valid aligned pool and itemSize >= sizeof(freenode)");
        std::abort(); // Fail closed even if a platform assert handler returns.
    }
    pooldata->firstFree = pool;
    for (uint32_t itemIndex = 0; itemIndex < itemCount; ++itemIndex)
    {
        freenode *node = reinterpret_cast<freenode *>(
            pool + static_cast<std::size_t>(itemSize) * itemIndex);
        node->next = itemIndex + 1 < itemCount
            ? reinterpret_cast<freenode *>(
                pool + static_cast<std::size_t>(itemSize) * (itemIndex + 1))
            : nullptr;
    }
    pooldata->activeCount = 0;
}

freenode *__cdecl Pool_Alloc(pooldata_t *pooldata)
{
    freenode *item; // [esp+0h] [ebp-4h]

    if (!pooldata)
        MyAssertHandler(".\\universal\\pool_allocator.cpp", 41, 0, "%s", "pooldata");
    item = (freenode *)pooldata->firstFree;
    if (!pooldata->firstFree)
        return 0;
    pooldata->firstFree = item->next;
    ++pooldata->activeCount;
    return item;
}

void __cdecl Pool_Free(freenode *data, pooldata_t *pooldata)
{
    freenode *item; // [esp+0h] [ebp-4h]

    if (!data)
        MyAssertHandler(".\\universal\\pool_allocator.cpp", 59, 0, "%s", "data");
    if (!pooldata)
        MyAssertHandler(".\\universal\\pool_allocator.cpp", 60, 0, "%s", "pooldata");
    for (item = (freenode *)pooldata->firstFree; item; item = item->next)
    {
        if (item == data)
            MyAssertHandler(".\\universal\\pool_allocator.cpp", 63, 0, "%s", "item != data");
    }
    data->next = (freenode *)pooldata->firstFree;
    pooldata->firstFree = data;
    --pooldata->activeCount;
}

uint32_t __cdecl Pool_FreeCount(const pooldata_t *pooldata)
{
    const freenode *item; // [esp+0h] [ebp-8h]
    uint32_t count; // [esp+4h] [ebp-4h]

    if (!pooldata)
        MyAssertHandler(".\\universal\\pool_allocator.cpp", 79, 0, "%s", "pooldata");
    count = 0;
    for (item = (const freenode *)pooldata->firstFree; item; item = item->next)
        ++count;
    return count;
}

