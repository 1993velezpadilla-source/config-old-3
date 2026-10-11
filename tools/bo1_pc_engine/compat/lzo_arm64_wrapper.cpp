// Thin Android JNI-compatible C ABI edge around the upstream miniLZO C code.
// This file contains no decoder, assets, zombie behavior, or game implementation.
// The original BO1 source tree includes miniLZO (GPL); preserve license.
#include <minilzo/minilzo.h>
extern "C" __attribute__((visibility("default")))
int bo1_upstream_lzo_decompress_safe(const unsigned char* src, unsigned int srcLength,
                                    unsigned char* output, unsigned int* outputCapacity) {
    if (!src || !output || !outputCapacity) return LZO_E_INVALID_ARGUMENT;
    lzo_uint capacity = static_cast<lzo_uint>(*outputCapacity);
    const int result = lzo1x_decompress_safe(src, static_cast<lzo_uint>(srcLength), output, &capacity, nullptr);
    *outputCapacity = static_cast<unsigned int>(capacity);
    return result;
}
