#pragma once

// Android bridge from the original DB_TryLoadXFileInternal path to the
// original DB_LoadXFile/DB_ReadData/DB_CancelLoadXFile descriptor contract.
// Path confinement is provided by the existing filesDir-rooted platform API;
// this helper only validates the opened regular file and adapts its descriptor.
#include "db_fastfile_posix_io.h"

#include <cerrno>
#include <cstdint>
#include <limits>
#include <sys/stat.h>
#include <unistd.h>

extern "C" int z2026_platform_open_engine_path_fd(const char *path);

static inline void *DBFastFilePosixOpenEnginePath(
    const char *path, uint32_t *fileSize, int *errorNumber)
{
    const auto invalidHandle = reinterpret_cast<void *>(static_cast<intptr_t>(-1));
    if (fileSize)
        *fileSize = 0;
    if (errorNumber)
        *errorNumber = 0;
    if (!path || !path[0] || !fileSize || !errorNumber)
    {
        if (errorNumber)
            *errorNumber = EINVAL;
        errno = EINVAL;
        return invalidHandle;
    }

    // The platform adapter rejects absolute paths outside filesDir, dot
    // traversal, symlinks and non-regular files. Clear errno first because
    // normalization failures are intentionally fail-closed without requiring
    // every rejection path to manufacture a POSIX errno value.
    errno = 0;
    const int fd = z2026_platform_open_engine_path_fd(path);
    if (fd < 0)
    {
        *errorNumber = errno ? errno : ENOENT;
        return invalidHandle;
    }

    struct stat fileStat = {};
    if (fstat(fd, &fileStat) != 0)
    {
        const int savedError = errno ? errno : EIO;
        close(fd);
        *errorNumber = savedError;
        return invalidHandle;
    }
    if (!S_ISREG(fileStat.st_mode))
    {
        close(fd);
        *errorNumber = EINVAL;
        errno = EINVAL;
        return invalidHandle;
    }
    if (fileStat.st_size < 0 ||
        static_cast<uint64_t>(fileStat.st_size) >
            static_cast<uint64_t>(std::numeric_limits<int32_t>::max()))
    {
        close(fd);
        *errorNumber = EFBIG;
        errno = EFBIG;
        return invalidHandle;
    }

    void *opaque = DBFastFilePosixOpaqueFromFd(fd);
    if (!opaque)
    {
        close(fd);
        *errorNumber = EOVERFLOW;
        errno = EOVERFLOW;
        return invalidHandle;
    }

    *fileSize = static_cast<uint32_t>(fileStat.st_size);
    return opaque;
}

// Shared implementation for the original DB_FileSize Android branch.
// Returns zero on open/stat/close failure, matching the legacy API's
// "not found" sentinel while never exposing a partially validated size.
static inline int32_t DBFastFilePosixFileSizeEnginePath(const char *path)
{
    uint32_t size = 0;
    int errorNumber = 0;
    void *opaque = DBFastFilePosixOpenEnginePath(path, &size, &errorNumber);
    const int fd = DBFastFilePosixFdFromOpaque(opaque);
    if (fd < 0)
        return 0;
    if (close(fd) != 0)
        return 0;
    return static_cast<int32_t>(size);
}
