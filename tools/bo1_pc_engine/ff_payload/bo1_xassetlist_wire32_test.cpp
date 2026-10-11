// Synthetic-only BO1 original XAssetList wire32 structural guard tests.
// No retail assets, no asset loading, no Kino rendering/gameplay.
#include "bo1_xassetlist_wire32.h"
#include <array>
#include <cstdint>
#include <cstdio>
using namespace bo1_xassetlist_wire32;
static void put(std::array<std::uint8_t,16>& b, unsigned off, std::uint32_t v) {
    for (unsigned i=0;i<4;++i) b[off+i]=static_cast<std::uint8_t>(v>>(8*i));
}
int main() {
    static_assert(sizeof(void*)==8, "test requires 64-bit host or ARM64");
    std::array<std::uint8_t,16> b{};
    WireList out{};
    put(b,0,185); put(b,4,0xffffffffu);
    put(b,8,1485); put(b,12,0xfffffffeu);
    constexpr std::uint64_t min=16+185*4+1485*8;
    if (inspect(b.data(),b.size(),min,&out)!=Result::ok) return 1;
    if (out.script_count!=185 || out.asset_count!=1485 ||
        out.strings_marker!=0xffffffffu || out.assets_marker!=0xfffffffeu) return 2;
    if (inspect(b.data(),b.size(),min-1,&out)!=Result::impossible_minimum_stream) return 3;
    if (out.asset_count!=0) return 4; // fail closed, no stale metadata
    if (inspect(b.data(),15,min,&out)!=Result::truncated) return 5;
    if (inspect(nullptr,16,min,&out)!=Result::invalid_argument) return 6;
    if (inspect(b.data(),16,min,nullptr)!=Result::invalid_argument) return 7;
    put(b,0,0x80000000u);
    if (inspect(b.data(),16,UINT64_MAX,&out)!=Result::negative_count) return 8;
    put(b,0,185); put(b,8,0xffffffffu);
    if (inspect(b.data(),16,UINT64_MAX,&out)!=Result::negative_count) return 9;
    put(b,8,1485); put(b,4,0);
    if (inspect(b.data(),16,min,&out)!=Result::missing_presence_marker) return 10;
    put(b,4,1); put(b,12,0);
    if (inspect(b.data(),16,min,&out)!=Result::missing_presence_marker) return 11;
    put(b,0,0); put(b,8,0);
    if (inspect(b.data(),16,16,&out)!=Result::ok) return 12;
    // Nonzero markers with zero counts are not packed offset references.
    put(b,4,0xffffffffu); put(b,12,0xfffffffeu);
    if (inspect(b.data(),16,16,&out)!=Result::ok) return 13;
    if (inspect(b.data(),16,15,&out)!=Result::impossible_minimum_stream) return 14;
    std::puts("BO1_ORIGINAL_XASSETLIST_WIRE32_MINIMUM_STREAM_GUARDS=PASS");
    std::puts("BO1_ORIGINAL_XASSETLIST_PRESENCE_NOT_PACKED_OFFSETS=PASS");
    std::puts("NO_XASSET_GRAPH_OR_RETAIL_KINO_RUNTIME=true");
}
