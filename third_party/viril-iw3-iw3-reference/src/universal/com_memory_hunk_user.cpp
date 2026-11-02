// Original IW3 HunkUser allocator, shared by Windows and Android.
#include <qcommon/qcommon.h>
#include <universal/assertive.h>
#include <universal/com_memory.h>
#include <cstddef>
#include <cstdint>
#include <cstring>

HunkUser* __cdecl Hunk_UserCreate(int32_t maxSize, const char* name, bool fixed, bool tempMem, int32_t type)
{
    HunkUser* user; // [esp+0h] [ebp-4h]

    if (maxSize % 4096)
        MyAssertHandler(".\\universal\\com_memory.cpp", 2834, 0, "%s\n\t(maxSize) = %i", "(!(maxSize % (4*1024)))", maxSize);
    user = (HunkUser*)Z_VirtualReserve(maxSize);
    Z_VirtualCommit(user, static_cast<int32_t>(offsetof(HunkUser, buf)));
    user->end = reinterpret_cast<uintptr_t>(user) + static_cast<uintptr_t>(maxSize);
    user->pos = reinterpret_cast<uintptr_t>(user->buf);
    if ((user->pos & 0x1F) != 0)
        MyAssertHandler(".\\universal\\com_memory.cpp", 2848, 0, "%s\n\t(user->pos) = %p", "(!(user->pos & 31))", reinterpret_cast<void *>(user->pos));
    user->maxSize = maxSize;
    user->current = user;
    user->fixed = fixed;
    user->name = name;
    user->tempMem = tempMem;
    user->type = type;
    if (user->next)
        MyAssertHandler(".\\universal\\com_memory.cpp", 2855, 0, "%s", "!user->next");
    return user;
}

void* Hunk_UserAlloc(HunkUser* user, uint32_t size, int32_t alignment)
{
    uintptr_t pos; // [esp+4h] [ebp-10h]
    uintptr_t result; // [esp+8h] [ebp-Ch]
    HunkUser* current; // [esp+Ch] [ebp-8h]
    HunkUser* newCurrent; // [esp+10h] [ebp-4h]

    iassert(user);
    iassert(static_cast<uint>(size) <= user->maxSize - offsetof(HunkUser, buf));
    iassert(!(alignment & (alignment - 1)));
    iassert(alignment <= HUNK_MAX_ALIGNEMT);

    alignment = alignment - 1;

    for (current = user->current; ; current = newCurrent)
    {
        pos = current->pos;
        result = ~static_cast<uintptr_t>(alignment) & (static_cast<uintptr_t>(alignment) + pos);
        if (static_cast<uintptr_t>(size) + result <= current->end)
            break;
        if (user->fixed)
            Com_Error(ERR_FATAL, "Hunk_UserAlloc: out of memory");
        newCurrent = Hunk_UserCreate(user->maxSize, user->name, 0, user->tempMem, user->type);
        user->current = newCurrent;
        current->next = newCurrent;
    }

    current->pos = static_cast<uintptr_t>(size) + (~static_cast<uintptr_t>(alignment) & (static_cast<uintptr_t>(alignment) + pos));
    pos = (pos + 4095u) & ~static_cast<uintptr_t>(4095u);

    if (pos != ((current->pos + 4095u) & ~static_cast<uintptr_t>(4095u)))
    {
        iassert(current->pos - pos > 0);
        Z_VirtualCommit(reinterpret_cast<void *>(pos), static_cast<int32_t>(current->pos - pos));
    }

    return reinterpret_cast<void *>(result);
}

void* Hunk_UserAllocAlignStrict(HunkUser* user, uint32_t size)
{
    return Hunk_UserAlloc(user, size, 1);
}

void __cdecl Hunk_UserSetPos(HunkUser* user, uint8_t* pos)
{
    iassert(user->fixed);
    iassert(pos >= user->buf);
    iassert((uintptr_t)pos <= user->pos); // (psize_int)pos <= user->pos

    user->pos = reinterpret_cast<uintptr_t>(pos);
}

void __cdecl Hunk_UserReset(HunkUser* user)
{
    uintptr_t pos; // [esp+0h] [ebp-4h]

    if (user->next)
    {
        Hunk_UserDestroy(user->next);
        user->current = user;
        user->next = 0;
    }
    pos = reinterpret_cast<uintptr_t>(user) + 4096u;
    if (pos != ((user->pos + 4095u) & ~static_cast<uintptr_t>(4095u)))
    {
        if (user->pos <= pos)
            MyAssertHandler(".\\universal\\com_memory.cpp", 3019, 0, "%s", "user->pos - pos > 0");
        Z_VirtualDecommit(reinterpret_cast<void *>(pos), static_cast<int32_t>(user->pos - pos));
    }
    user->pos = reinterpret_cast<uintptr_t>(user->buf);
    memset(user->buf, 0, 4096u - offsetof(HunkUser, buf));
}

void __cdecl Hunk_UserDestroy(HunkUser* user)
{
    HunkUser* current; // [esp+0h] [ebp-8h]
    HunkUser* newCurrent; // [esp+4h] [ebp-4h]

    for (current = user->next; current; current = newCurrent)
    {
        newCurrent = current->next;
        Z_VirtualFree(current);
    }
    Z_VirtualFree(user);
}

char* __cdecl Hunk_CopyString(HunkUser* user, const char* in)
{
    char v3; // [esp+3h] [ebp-21h]
    char* v4; // [esp+8h] [ebp-1Ch]
    const char* v5; // [esp+Ch] [ebp-18h]
    char* out; // [esp+20h] [ebp-4h]

    out = (char*)Hunk_UserAlloc(user, strlen(in) + 1, 1);
    v5 = in;
    v4 = out;
    do
    {
        v3 = *v5;
        *v4++ = *v5++;
    } while (v3);
    return out;
}
