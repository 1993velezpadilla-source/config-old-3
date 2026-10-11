#pragma once
// Wire-format boundary for BO1's original Load_XAssetListCustom path.
// Source authority: MisaDev4/bo1-zombies-decompiled at
// 102f6992be332610aff587e681e3180b15f395bb
// src/database/db_registry.h (XAssetList 16, XAsset 8), and
// src/database/db_file_load.cpp (Load_XAssetListCustom,
// Load_XAssetArrayCustom). NOT a deserializer or asset loader.
//
// The serialized 32-bit fields are NOT native pointers on Android ARM64.
// In this specific loader, nonzero strings/assets fields are PRESENCE
// markers for allocations in stream 4, NOT DB_ConvertOffsetToPointer tokens.
// Do not pass these fields to bo1_wire32::resolve.
#include <cstddef>
#include <cstdint>
#include <limits>

namespace bo1_xassetlist_wire32 {
struct WireXAsset { std::uint32_t type, header; };
struct WireList {
    std::uint32_t script_count, strings_marker, asset_count, assets_marker;
};
static_assert(sizeof(WireXAsset) == 8, "original BO1 XAsset is 8 wire bytes");
static_assert(sizeof(WireList) == 16, "original BO1 XAssetList is 16 wire bytes");

enum class Result : std::uint8_t {
    ok, invalid_argument, truncated, negative_count,
    missing_presence_marker, impossible_minimum_stream
};
constexpr std::size_t kHeaderBytes = 16;

inline std::uint32_t read_le32(const std::uint8_t* p) noexcept {
    return std::uint32_t(p[0]) | (std::uint32_t(p[1]) << 8u)
         | (std::uint32_t(p[2]) << 16u) | (std::uint32_t(p[3]) << 24u);
}

// Validate only NECESSARY conditions from original loader:
//  - 16 wire bytes for XAssetList
//  - count signed int32 and nonnegative (negative would break loader)
//  - nonzero count must have a nonzero allocation marker
//  - 4 wire bytes per script-string pointer, 8 per XAsset record
// The minimum-size bound deliberately ignores string data and XAsset bodies;
// passing it does NOT establish a valid XAsset graph or usable fastfile.
// A zero count with a nonzero marker is allowed: original loader tests the
// marker independently of the count. Marker -1/-2 are NOT packed offsets here.
inline Result inspect(const std::uint8_t* bytes, std::size_t available,
                      std::uint64_t declared_payload_size,
                      WireList* output) noexcept {
    if (!output) return Result::invalid_argument;
    *output = {};
    if (!bytes) return Result::invalid_argument;
    if (available < kHeaderBytes) return Result::truncated;
    const WireList v{
        read_le32(bytes), read_le32(bytes + 4),
        read_le32(bytes + 8), read_le32(bytes + 12)
    };
    if (v.script_count > static_cast<std::uint32_t>(std::numeric_limits<std::int32_t>::max())
        || v.asset_count > static_cast<std::uint32_t>(std::numeric_limits<std::int32_t>::max()))
        return Result::negative_count;
    if ((v.script_count && !v.strings_marker) ||
        (v.asset_count && !v.assets_marker))
        return Result::missing_presence_marker;
    const std::uint64_t minimum = kHeaderBytes
        + std::uint64_t(v.script_count) * sizeof(std::uint32_t)
        + std::uint64_t(v.asset_count) * sizeof(WireXAsset);
    if (minimum > declared_payload_size)
        return Result::impossible_minimum_stream;
    *output = v;
    return Result::ok;
}
} // namespace bo1_xassetlist_wire32
