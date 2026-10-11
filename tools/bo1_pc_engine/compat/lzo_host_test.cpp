// Uses miniLZO FROM the original BO1 engine source tree (licensed GPL).
// No alternate compressor, renderer, or game invented.
#include <minilzo/minilzo.h>
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

static bool round_trip(const std::vector<unsigned char>& input) {
    const lzo_uint original = static_cast<lzo_uint>(input.size());
    std::vector<unsigned char> compressed(input.size() + input.size()/16 + 128, 0);
    std::vector<unsigned char> restored(input.size() + 64, 0);
    std::vector<unsigned char> work(LZO1X_1_MEM_COMPRESS, 0);
    lzo_uint zipped = static_cast<lzo_uint>(compressed.size());
    const int c = lzo1x_1_compress(input.data(), original, compressed.data(), &zipped, work.data());
    if (c != LZO_E_OK) { std::fprintf(stderr, "LZO_COMPRESS_FAILED=%d\n", c); return false; }
    lzo_uint unzipped = static_cast<lzo_uint>(restored.size());
    const int d = lzo1x_decompress_safe(compressed.data(), zipped, restored.data(), &unzipped, nullptr);
    if (d != LZO_E_OK || unzipped != original
        || std::memcmp(input.data(), restored.data(), input.size()) != 0) {
        std::fprintf(stderr, "LZO_ROUNDTRIP_FAILED=%d, actual=%zu expected=%zu\n", d,
                     static_cast<size_t>(unzipped), input.size());
        return false;
    }
    if (zipped > 2) {
        lzo_uint cap = static_cast<lzo_uint>(restored.size());
        int bad = lzo1x_decompress_safe(compressed.data(), zipped - 2, restored.data(), &cap, nullptr);
        if (bad == LZO_E_OK) {
            std::fprintf(stderr, "LZO_TRUNCATED_INPUT_UNEXPECTEDLY_ACCEPTED\n");
            return false;
        }
    }
    return true;
}
int main() {
    if (lzo_init() != LZO_E_OK) return 10;
    // Test both compressible assets and high-entropy chunks.
    for (size_t n : {size_t(1),size_t(128),size_t(4096),size_t(65536),size_t(262144)}) {
        std::vector<unsigned char> data(n);
        for (size_t i = 0; i < n; ++i) data[i] = static_cast<unsigned char>((i/19) % 13);
        if (!round_trip(data)) return 11;
        uint32_t rng = 0x5ad2e512;
        for (auto& b : data) { rng ^= rng<<13; rng ^= rng>>17; rng ^= rng<<5; b = static_cast<unsigned char>(rng); }
        if (!round_trip(data)) return 12;
    }
    std::puts("BO1_BUNDLED_MINILZO_HOST_ROUNDTRIP_AND_TRUNCATION_GAUNTLET=PASS");
    return 0;
}
