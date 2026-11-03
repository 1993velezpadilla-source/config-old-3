#pragma once
// GLES3 render-target binding for original IW3 R_HW_SetRenderTarget.
// Image/texture creation remains owned by the original image backend.
#if defined(__ANDROID__)
bool R_AndroidGlesRegisterTarget(int targetId, unsigned int colorTexture,
                                 unsigned int depthStencilRenderbuffer,
                                 int width, int height);
bool R_AndroidGlesBindTarget(int targetId, int width, int height);
// Reports only the dimensions of a successfully bound ORIGINAL IW3 target.
// No fallback to window size when no target is active.
bool R_AndroidGlesGetBoundTargetDimensions(int *width, int *height);
bool R_AndroidGlesReleaseTargets();
#endif
