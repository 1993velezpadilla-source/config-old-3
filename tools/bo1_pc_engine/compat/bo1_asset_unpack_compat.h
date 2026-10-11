#pragma once
// Minimal compile compatibility for BO1 original sprite/texture unpack translation unit.
// Only declarations and Windows aliases; no original pixel math is reimplemented.
#include <cstdint>
#include <cstring>
#include <cmath>
#ifndef __cdecl
#define __cdecl
#endif
#ifndef __int8
#define __int8 char
#endif
#ifndef __int16
#define __int16 short
#endif
#ifndef _BYTE
#define _BYTE unsigned char
#endif
#ifndef iassert
#define iassert(condition) ((void)0)
#endif
#ifndef __debugbreak
#define __debugbreak() __builtin_trap()
#endif
template <typename T> inline std::uint32_t BO1_UnpackRawBits(const T& value) {
    static_assert(sizeof(T)==4);
    std::uint32_t bits{};
    std::memcpy(&bits,&value,sizeof bits);
    return bits;
}
#ifndef LOWORD
#define LOWORD(x) (BO1_UnpackRawBits(x) & 0xffffu)
#endif
#ifndef HIWORD
#define HIWORD(x) ((BO1_UnpackRawBits(x)>>16) & 0xffffu)
#endif
float __cdecl Vec3NormalizeTo(const float* v, float* out);
float __cdecl Vec3Normalize(float* v);
float __cdecl Vec3Dot(const float* a, const float* b);
float __cdecl Vec4Normalize(float* v);
bool Assert_MyHandler(const char *filename, int line, int type, const char *fmt, ...);
