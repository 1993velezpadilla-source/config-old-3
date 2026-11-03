// GLES3 viewport bridge for the ORIGINAL KisakCOD IW3 RC_SET_VIEWPORT.
// The engine's GfxViewport uses D3D9 top-left coordinates; GLES3 uses
// bottom-left coordinates. This is not a synthetic draw or a game renderer.
#if defined(__ANDROID__)
#include "r_android_viewport.h"
#include <EGL/egl.h>
#include <GLES3/gl3.h>
#include <cstdint>

bool R_AndroidGlesSetViewport(int x, int y, int width, int height,
                              int targetWidth, int targetHeight)
{
    if (eglGetCurrentDisplay() == EGL_NO_DISPLAY
        || eglGetCurrentContext() == EGL_NO_CONTEXT
        || x < 0 || y < 0 || width <= 0 || height <= 0
        || targetWidth <= 0 || targetHeight <= 0)
        return false;

    // Widen before adding to avoid signed overflow from untrusted command
    // buffers. The original IW3 render-target dimensions are the authority,
    // not the EGL window dimensions (which differ for offscreen targets).
    if (static_cast<int64_t>(x) + width > targetWidth
        || static_cast<int64_t>(y) + height > targetHeight)
        return false;

    // Never attribute a pre-existing GL error to this command.
    if (glGetError() != GL_NO_ERROR)
        return false;

    const GLint glY = targetHeight - y - height;
    glViewport(x, glY, width, height);
    return glGetError() == GL_NO_ERROR;
}
#endif
