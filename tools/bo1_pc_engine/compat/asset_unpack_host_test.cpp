// Runtime tests of exact BO1 original com_pack.cpp functions.
#include <universal/com_pack.h>
#include <cmath>
#include <cstdio>
static bool nearto(float actual, float expected) {
    return std::fabs(actual-expected) < 0.00002f;
}
int main() {
    const unsigned char src[4]={0,128,255,64};
    float result[4]{};
    Byte4UnpackRgba(src,result);
    if (!nearto(result[0],0)||!nearto(result[1],128.0f/255.0f)
        ||!nearto(result[2],1)||!nearto(result[3],64.0f/255.0f)) return 11;
    PackedUnitVec packed{};
    packed.array[0]=127;
    packed.array[1]=127;
    packed.array[2]=127;
    packed.array[3]=0;
    float vec[3]={1,1,1};
    Vec3UnpackUnitVec(packed,vec);
    if (!nearto(vec[0],0)||!nearto(vec[1],0)||!nearto(vec[2],0)) return 12;
    PackedTexCoords uv(0);
    float out[2]={123,456};
    Vec2UnpackTexCoords(uv,out);
    if (!nearto(out[0],0)||!nearto(out[1],0)) return 13;
    std::puts("BO1_ORIGINAL_TEXTURE_RGBA_NORMAL_UV_UNPACK_TESTS=PASS");
    return 0;
}
