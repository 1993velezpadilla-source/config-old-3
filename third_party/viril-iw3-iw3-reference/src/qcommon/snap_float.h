#pragma once

#include <cfenv>
#include <cmath>
#include <cstdint>
#include <limits>
#include "../universal/assertive.h"

#if defined(_M_IX86) || defined(_M_X64) || defined(__i386__) || defined(__x86_64__)
#include <xmmintrin.h>
#if defined(_MSC_VER)
#include <intrin.h>
#endif
#endif

namespace kisak_detail
{
// ARM64 has no x86 CVTSS2SI intrinsic. Preserve its current-rounding-mode
// conversion, including ties-to-even at the engine's default FE_TONEAREST.
// Never replace ordinary integer casts with this: those truncate instead.
inline int SnapFloatToIntPortable(float value)
{
    static_assert(sizeof(int) == sizeof(std::int32_t));
    const double rounded = std::rint(static_cast<double>(value));
    // CVTSS2SI returns the integer-indefinite value for NaN and overflow.
    // Check in double precision before converting, avoiding undefined C++
    // float-to-int behavior at +2^31 (INT_MAX rounds up when stored as float).
    if (!std::isfinite(rounded) ||
        rounded < static_cast<double>((std::numeric_limits<int>::min)()) ||
        rounded > static_cast<double>((std::numeric_limits<int>::max)()))
    {
        std::feraiseexcept(FE_INVALID);
        return (std::numeric_limits<int>::min)();
    }
    return static_cast<int>(rounded);
}
}

// (https://github.com/SwagSoftware/KisakCOD/issues/52)
// The original x86 engine uses fistp/CVTSS2SI, not truncation or round-away.
inline int SnapFloatToInt(float x)
{
#if defined(_MSC_VER) && defined(_M_IX86) && defined(KISAK_PURE)
    int i;
    __asm fld x;
    __asm fistp i;
    return i;
#elif defined(_M_IX86) || defined(_M_X64) || defined(__i386__) || defined(__x86_64__)
    int retval = _mm_cvtss_si32(_mm_set_ss(x));
#if defined(_DEBUG) && defined(_MSC_VER) && defined(_M_IX86)
    const float input = x;
    int32_t output{};
    __asm fld input
    __asm fistp output
    iassert(retval == output);
#endif
    return retval;
#else
    return kisak_detail::SnapFloatToIntPortable(x);
#endif
}

inline float SnapFloat(float x)
{
    return static_cast<float>(SnapFloatToInt(x));
}
