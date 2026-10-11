// Android ABI bridge to actual upstream unpacking functions.
// Functions defined in upstream src/universal/com_pack.cpp, not here.
#include <universal/com_pack.h>
extern "C" __attribute__((visibility("default")))
void bo1_original_unpack_rgba(const unsigned char src[4], float dst[4]) {
    Byte4UnpackRgba(src,dst);
}
extern "C" __attribute__((visibility("default")))
void bo1_original_unpack_normal(unsigned int bits,float dst[3]) {
    PackedUnitVec packed; packed.packed=bits; Vec3UnpackUnitVec(packed,dst);
}
extern "C" __attribute__((visibility("default")))
void bo1_original_unpack_uv(unsigned int bits,float dst[2]) {
    Vec2UnpackTexCoords(PackedTexCoords(bits),dst);
}
