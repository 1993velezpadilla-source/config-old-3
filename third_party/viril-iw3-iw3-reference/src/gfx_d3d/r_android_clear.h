#pragma once
// GLES3 translation of the ORIGINAL KisakCOD IW3 RC_CLEAR_SCREEN command.
// This is one render command, not a complete renderer or playable game.
#if defined(__ANDROID__)
#include <cstdint>
bool R_AndroidGlesClear(uint8_t whichToClear, const float color[4],
                        float depth, uint8_t stencil);
#endif
