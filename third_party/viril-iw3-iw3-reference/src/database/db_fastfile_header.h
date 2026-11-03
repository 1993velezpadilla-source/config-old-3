#ifndef KISAKCOD_DB_FASTFILE_HEADER_H
#define KISAKCOD_DB_FASTFILE_HEADER_H

#include <stddef.h>
#include <stdint.h>
#include <string.h>

// Portable, byte-aligned parser for the 12-byte header consumed by the original
// DB_LoadXFileInternal. This is not a FastFile loader: inflate, authentication
// policy, asset registration, zone allocation, and rendering remain engine work.
enum class DBFastFileHeaderStatus
{
    Ok,
    InvalidArgument,
    TruncatedMagic,
    InvalidMagic,
    TruncatedVersion,
    UnsupportedVersion
};

struct DBFastFileHeader
{
    char magic[8];
    uint32_t version;
    bool secure;
    size_t consumed;
};

static inline DBFastFileHeaderStatus DB_ParseFastFileHeader(
    const uint8_t *data, size_t available, DBFastFileHeader *out)
{
    if (!data || !out)
        return DBFastFileHeaderStatus::InvalidArgument;

    memset(out, 0, sizeof(*out));
    if (available < 8)
        return DBFastFileHeaderStatus::TruncatedMagic;

    // memcpy avoids unaligned uint32_t loads and strict-aliasing violations on
    // the zlib input buffer. Version is decoded explicitly as little-endian.
    memcpy(out->magic, data, sizeof(out->magic));
    out->consumed = 8;

    if (memcmp(out->magic, "IWff0100", 8) != 0
        && memcmp(out->magic, "IWffu100", 8) != 0)
        return DBFastFileHeaderStatus::InvalidMagic;

    if (available < 12)
        return DBFastFileHeaderStatus::TruncatedVersion;

    out->version = (uint32_t)data[8]
        | ((uint32_t)data[9] << 8)
        | ((uint32_t)data[10] << 16)
        | ((uint32_t)data[11] << 24);
    out->secure = memcmp(out->magic, "IWffu100", 8) != 0;
    out->consumed = 12;

    if (out->version != 5)
        return DBFastFileHeaderStatus::UnsupportedVersion;

    return DBFastFileHeaderStatus::Ok;
}

#endif
