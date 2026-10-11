#pragma once
// BO1 original FF header preflight, NOT a complete asset parser.
// Format and zlib path verified from original DB_LoadXFileInternal.
// Values are from the original XFile struct: 2 sizes + 7 block sizes.
#include <cstdint>
#ifdef __cplusplus
extern "C" {
#endif

struct BO1XFileHeaderInfo {
    std::uint32_t version;       // 473
    std::uint32_t size;          // remaining uncompressed FF payload size
    std::uint32_t external_size;
    std::uint32_t block_size[7];
};

enum BO1FastfileProbeResult {
    BO1_FF_HEADER_OK=0,
    BO1_FF_MISSING=1,
    BO1_FF_IO_ERROR=2,
    BO1_FF_BAD_MAGIC=3,
    BO1_FF_BAD_VERSION=4,
    BO1_FF_SECURE_NOT_SUPPORTED=5,
    BO1_FF_DEFLATE_ERROR=6,
    BO1_FF_INVALID_XFILE_LAYOUT=7
};
// Returns the preflight result. A successful preflight does NOT load
// textures, meshes, collision, audio, or any original zombie map.
int bo1_original_fastfile_header_probe(const char *zoneName, BO1XFileHeaderInfo *header);

#ifdef __cplusplus
}
#endif
