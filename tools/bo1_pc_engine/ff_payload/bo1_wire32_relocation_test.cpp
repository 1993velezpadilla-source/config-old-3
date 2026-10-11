// Synthetic-only verification of the original BO1 32-bit packed offset formula.
// No retail fastfiles, no renderer, and no gameplay are involved.
#include "bo1_wire32_relocation.h"
#include <array>
#include <cstdint>
#include <cstdio>
using namespace bo1_wire32;
int main() {
    std::array<std::array<std::uint8_t, 32>, kBlockCount> memory{};
    std::array<Block, kBlockCount> blocks{};
    for (std::size_t i = 0; i < kBlockCount; ++i)
        blocks[i] = {memory[i].data(), memory[i].size()};
    Location loc{};
    for (std::uint32_t i = 0; i < kBlockCount; ++i) {
        const auto token = (i << 29u) + 6u; // byte offset 5
        if (resolve(token, blocks, 4, &loc) != Result::ok ||
            loc.block != i || loc.offset != 5 ||
            loc.address != memory[i].data() + 5) return 1;
    }
    if (resolve(0, blocks, 4, &loc) != Result::null_reference) return 2;
    if (resolve(0xffffffffu, blocks, 4, &loc) != Result::inline_sentinel) return 3;
    if (resolve(0xfffffffeu, blocks, 4, &loc) != Result::inline_sentinel) return 4;
    if (resolve(0xe0000001u, blocks, 4, &loc) != Result::invalid_block) return 5;
    if (resolve(31u, blocks, 4, &loc) != Result::out_of_bounds) return 6;
    if (resolve(33u, blocks, 4, &loc) != Result::out_of_bounds) return 7;
    if (resolve(1u, blocks, 0, &loc) != Result::invalid_argument) return 8;
    if (resolve(1u, blocks, 1, nullptr) != Result::invalid_argument) return 9;
    blocks[2].data = nullptr;
    if (resolve((2u << 29u) + 1u, blocks, 1, &loc) != Result::missing_block) return 10;
    blocks[2].data = memory[2].data();
    if (resolve((2u << 29u) + 1u, blocks, static_cast<std::size_t>(-1), &loc)
        != Result::out_of_bounds) return 11;
    memory[6][4] = 0xfe; memory[6][5] = 0xff;
    memory[6][6] = 0xff; memory[6][7] = 0xff;
    std::uint32_t wire{};
    if (read_alias_slot((6u << 29u) + 5u, blocks, &wire) != Result::ok ||
        wire != 0xfffffffeu) return 12;
    if (read_alias_slot((6u << 29u) + 31u, blocks, &wire)
        != Result::out_of_bounds) return 13;
    if (read_alias_slot(1u, blocks, nullptr) != Result::invalid_argument) return 14;
    Location address{};
    if (sizeof(void*) != 8 ||
        resolve((6u << 29u) + 5u, blocks, 4, &address) != Result::ok ||
        reinterpret_cast<std::uintptr_t>(address.address) !=
            reinterpret_cast<std::uintptr_t>(memory[6].data()) + 4u) return 15;
    std::puts("BO1_ORIGINAL_PACKED_XBLOCK_OFFSET_WIRE32_HOST64_GUARDS=PASS");
    std::puts("BO1_ORIGINAL_ALIAS_SLOT_READ_NO_POINTER_TRUNCATION=PASS");
    std::puts("NOT_AN_XASSET_LOADER_OR_KINO_RUNTIME=true");
}
