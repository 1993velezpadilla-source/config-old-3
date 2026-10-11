#pragma once
// Original BO1 DB_ConvertOffsetToPointer packed encoding from pinned
// MisaDev4/bo1-zombies-decompiled 102f6992be332610aff587e681e3180b15f395bb:
// block = (token - 1) >> 29; offset = (token - 1) & 0x1fffffff.
// This safe ARM64 boundary does NOT load XAssets or fix up asset graphs.
#include <array>
#include <cstddef>
#include <cstdint>
namespace bo1_wire32 {
constexpr std::size_t kBlockCount = 7;
struct Block { std::uint8_t* data = nullptr; std::size_t size = 0; };
struct Location {
    std::uint8_t* address = nullptr;
    std::uint32_t block = 0;
    std::uint32_t offset = 0;
};
enum class Result : std::uint8_t {
    ok, null_reference, inline_sentinel, invalid_block, missing_block,
    out_of_bounds, invalid_argument
};
// Call only for fields that original code sends to DB_ConvertOffsetToPointer
// or DB_ConvertOffsetToAlias; XAssetList pointers have different semantics.
inline Result resolve(std::uint32_t token,
                      const std::array<Block, kBlockCount>& blocks,
                      std::size_t bytes, Location* out) noexcept {
    if (!out || !bytes) return Result::invalid_argument;
    *out = {};
    if (!token) return Result::null_reference;
    if (token >= 0xfffffffeu) return Result::inline_sentinel;
    const auto packed = token - 1u;
    const auto index = packed >> 29u;
    const auto offset = packed & 0x1fffffffu;
    if (index >= blocks.size()) return Result::invalid_block;
    const auto& b = blocks[index];
    if (!b.data) return Result::missing_block;
    if (offset > b.size || bytes > b.size - offset) return Result::out_of_bounds;
    *out = {b.data + offset, index, offset};
    return Result::ok;
}
// DB_ConvertOffsetToAlias reads a 32-bit slot. Never truncate a native
// pointer into that slot; return the serialized value for later fixups.
inline Result read_alias_slot(std::uint32_t token,
                              const std::array<Block, kBlockCount>& blocks,
                              std::uint32_t* value) noexcept {
    if (!value) return Result::invalid_argument;
    *value = 0;
    Location slot{};
    const auto status = resolve(token, blocks, 4, &slot);
    if (status != Result::ok) return status;
    const auto* p = slot.address;
    *value = std::uint32_t(p[0]) | (std::uint32_t(p[1]) << 8u) |
             (std::uint32_t(p[2]) << 16u) | (std::uint32_t(p[3]) << 24u);
    return Result::ok;
}
}
