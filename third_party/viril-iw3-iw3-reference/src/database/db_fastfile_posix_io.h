#pragma once

// POSIX file-I/O primitive for the original IW3 FastFile loader's Android
// path. This helper performs positioned reads only; it does not parse,
// decompress, mount, or otherwise replace the original FastFile loader.
#include <cerrno>
#include <cstddef>
#include <cstdint>
#include <climits>
#include <limits>
#include <sys/types.h>
#include <unistd.h>

static inline void *DBFastFilePosixOpaqueFromFd(int fd)
{
    // DB_LoadXFile currently accepts an opaque HANDLE-shaped value. Encode
    // fd+1 so descriptor 0 is representable without becoming a null handle.
    if (fd < 0 || fd == INT_MAX)
        return nullptr;
    return reinterpret_cast<void *>(static_cast<intptr_t>(fd) + 1);
}

static inline int DBFastFilePosixFdFromOpaque(const void *opaque)
{
    const intptr_t encoded = reinterpret_cast<intptr_t>(opaque);
    if (encoded <= 0 || encoded - 1 > INT_MAX)
        return -1;
    return static_cast<int>(encoded - 1);
}

// Fill up to capacity bytes from a fixed file offset. Retry EINTR and
// accumulate short positive reads so callers see either a full chunk or the
// true final short chunk/EOF. Returns 0 for success (including EOF), -1 for
// an I/O/argument/offset error. Output values are initialized when possible.
static inline int DBFastFilePosixReadAt(
    int fd, void *destination, size_t capacity, uint64_t offset,
    size_t *bytesRead, int *errorNumber)
{
    if (bytesRead)
        *bytesRead = 0;
    if (errorNumber)
        *errorNumber = 0;

    if (!bytesRead || !errorNumber || fd < 0 || (!destination && capacity != 0))
    {
        if (errorNumber)
            *errorNumber = EINVAL;
        errno = EINVAL;
        return -1;
    }

    const uint64_t maxOffset = static_cast<uint64_t>(std::numeric_limits<off_t>::max());
    if (offset > maxOffset || static_cast<uint64_t>(capacity) > maxOffset - offset)
    {
        *errorNumber = EOVERFLOW;
        errno = EOVERFLOW;
        return -1;
    }

    auto *out = static_cast<unsigned char *>(destination);
    while (*bytesRead < capacity)
    {
        const uint64_t currentOffset = offset + static_cast<uint64_t>(*bytesRead);
        const ssize_t count = pread(fd, out + *bytesRead, capacity - *bytesRead,
                                    static_cast<off_t>(currentOffset));
        if (count > 0)
        {
            *bytesRead += static_cast<size_t>(count);
            continue;
        }
        if (count == 0)
            return 0;

        const int savedError = errno;
        if (savedError == EINTR)
            continue;

        *errorNumber = savedError;
        return -1;
    }
    return 0;
}
