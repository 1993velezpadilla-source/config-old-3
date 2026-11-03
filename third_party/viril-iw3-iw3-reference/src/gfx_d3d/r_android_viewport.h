#pragma once
// Translation of IW3's original top-left GfxViewport to GLES3 coordinates.
// Not a render target allocator or a complete renderer.
#if defined(__ANDROID__)
bool R_AndroidGlesSetViewport(int x, int y, int width, int height,
                              int targetWidth, int targetHeight);
#endif
