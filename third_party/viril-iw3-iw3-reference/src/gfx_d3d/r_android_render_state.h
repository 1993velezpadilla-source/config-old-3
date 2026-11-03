#pragma once
// Original KisakCOD IW3 state-bit boundaries on Android GLES3.
// NOT a full material/shader pipeline; alpha test enabled fails closed.
#if defined(__ANDROID__)
#include <cstdint>
bool R_AndroidGlesSetAlphaTestEnable(uint16_t originalStateBits0);
bool R_AndroidGlesSetColorMask(uint32_t originalStateBits0);
bool R_AndroidGlesSetCullFace(uint16_t originalStateBits0);
bool R_AndroidGlesSetPolygonMode(uint32_t originalStateBits0);
#endif
