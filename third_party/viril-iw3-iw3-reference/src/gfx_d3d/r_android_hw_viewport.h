#pragma once
// Original IW3 R_HW_SetViewport -> GLES3 viewport/depth-range bridge.
// Requires a successfully bound genuine IW3 render target.
#if defined(__ANDROID__)
bool R_AndroidGlesHardwareViewport(int x, int y, int width, int height,
                                   float nearValue, float farValue);
#endif
