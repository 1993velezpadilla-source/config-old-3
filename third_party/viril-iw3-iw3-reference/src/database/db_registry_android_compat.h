#pragma once

// Android-only declarations for genuine platform services consumed by the
// original database registry. These are implemented with POSIX/app-private
// primitives; this header does not provide renderer or database stubs.
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string.h>
#include <string>
#include <unistd.h>

#include <qcommon/fast_critical_section.h>
#include "iw3_android_platform.h"
#include "db_fastfile_posix_open.h"

constexpr int CRITSECT_MISSING_ASSET = 0x17; // KisakCOD SP win_local.h ABI value

static inline int InterlockedIncrement(volatile uint32_t *value)
{
    return static_cast<int>(__atomic_add_fetch(value, 1u, __ATOMIC_SEQ_CST));
}

static inline int InterlockedDecrement(volatile uint32_t *value)
{
    return static_cast<int>(__atomic_sub_fetch(value, 1u, __ATOMIC_SEQ_CST));
}

// db_registry.cpp uses _itoa only for decimal FastFile size diagnostics.
static inline char *_itoa(int value, char *buffer, int radix)
{
    if (!buffer)
        return nullptr;
    if (radix == 10)
        std::snprintf(buffer, 16, "%d", value);
    else if (radix == 16)
        std::snprintf(buffer, 16, "%x", static_cast<unsigned int>(value));
    else
        buffer[0] = '\0';
    return buffer;
}

#ifndef _strdup
#define _strdup ::strdup
#endif

#ifndef _stricmp
#define _stricmp I_stricmp
#endif
#ifndef _strnicmp
#define _strnicmp I_strnicmp
#endif

// The registry only uses CRITSECT_MISSING_ASSET in this TU. Map that exact SP
// lock index to a real FastCriticalSection rather than a no-op Win32 shim.
static inline FastCriticalSection &DB_AndroidMissingAssetCriticalSection()
{
    static FastCriticalSection section{};
    return section;
}
static inline void Sys_EnterCriticalSection(int section)
{
    if (section == CRITSECT_MISSING_ASSET)
        Sys_LockWrite(&DB_AndroidMissingAssetCriticalSection());
}
static inline void Sys_LeaveCriticalSection(int section)
{
    if (section == CRITSECT_MISSING_ASSET)
        Sys_UnlockWrite(&DB_AndroidMissingAssetCriticalSection());
}

// Read an optional zone_source CSV through the same app-private rooted
// descriptor boundary as FastFiles. No path outside filesDir is accepted.
static inline bool DB_ReadAndroidZoneSourceCsv(
    const char *path, char **contents, uint32_t *length)
{
    if (!contents || !length)
        return false;
    *contents = nullptr;
    *length = 0;
    uint32_t fileSize = 0;
    int openError = 0;
    void *opaque = DBFastFilePosixOpenEnginePath(path, &fileSize, &openError);
    const int fd = DBFastFilePosixFdFromOpaque(opaque);
    if (fd < 0)
        return false;
    char *buffer = static_cast<char *>(std::malloc(static_cast<std::size_t>(fileSize) + 1));
    if (!buffer)
    {
        close(fd);
        return false;
    }
    uint32_t transferred = 0;
    while (transferred < fileSize)
    {
        const ssize_t count = read(fd, buffer + transferred, fileSize - transferred);
        if (count < 0 && errno == EINTR)
            continue;
        if (count <= 0)
        {
            std::free(buffer);
            close(fd);
            return false;
        }
        transferred += static_cast<uint32_t>(count);
    }
    if (close(fd) != 0)
    {
        std::free(buffer);
        return false;
    }
    buffer[fileSize] = '\0';
    *contents = buffer;
    *length = fileSize;
    return true;
}

// Original Android fatal system errors are still routed to the real system
// error service when that service is linked into the engine runtime.
void Sys_Error(const char *error, ...);

// Android implementation returns the configured app-private filesDir. The
// original DB_BuildOSPath_Mod path is subsequently normalized and confined by
// DBFastFilePosixOpenEnginePath.
char *Sys_DefaultInstallPath();
