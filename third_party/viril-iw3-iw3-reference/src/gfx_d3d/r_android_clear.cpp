// GLES3 implementation of original KisakCOD IW3 RC_CLEAR_SCREEN semantics.
// No synthetic frame, map, shader, or substitute renderer is provided here.
#if defined(__ANDROID__)
#include "r_android_clear.h"
#include <EGL/egl.h>
#include <GLES3/gl3.h>
#include <cmath>

bool R_AndroidGlesClear(uint8_t whichToClear, const float color[4],
                        float depth, uint8_t stencil)
{
    // Original R_AddCmdClearScreen accepts only color=1, depth=2, stencil=4.
    if (!color || !(whichToClear & 7) || (whichToClear & ~7u)
        || !std::isfinite(depth) || depth < 0.0f || depth > 1.0f
        || eglGetCurrentDisplay() == EGL_NO_DISPLAY
        || eglGetCurrentContext() == EGL_NO_CONTEXT)
        return false;
    for (int i = 0; i < 4; ++i)
        if (!std::isfinite(color[i]))
            return false;

    // D3D9 Clear(0, nullptr, ...) clears the CURRENT VIEWPORT, not the
    // whole render target. GLES glClear ignores glViewport and uses scissor
    // instead. Restrict this clear to the active GL viewport and restore the
    // original scissor box/enable state so split-screen and offscreen targets
    // are not accidentally wiped outside their IW3 viewport.
    const GLboolean scissor = glIsEnabled(GL_SCISSOR_TEST);
    GLint oldScissorBox[4] = {0, 0, 0, 0};
    GLint viewport[4] = {0, 0, 0, 0};
    glGetIntegerv(GL_SCISSOR_BOX, oldScissorBox);
    glGetIntegerv(GL_VIEWPORT, viewport);
    if (viewport[2] <= 0 || viewport[3] <= 0)
        return false;
    GLboolean colorMask[4] = {GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE};
    GLboolean depthMask = GL_TRUE;
    GLint stencilFrontMask = -1, stencilBackMask = -1;
    GLfloat oldColor[4] = {0, 0, 0, 0};
    GLfloat oldDepth = 1.0f;
    GLint oldStencil = 0;
    GLbitfield bits = 0;

    if (whichToClear & 1)
    {
        glGetBooleanv(GL_COLOR_WRITEMASK, colorMask);
        glGetFloatv(GL_COLOR_CLEAR_VALUE, oldColor);
        glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);
        glClearColor(color[0], color[1], color[2], color[3]);
        bits |= GL_COLOR_BUFFER_BIT;
    }
    if (whichToClear & 2)
    {
        glGetBooleanv(GL_DEPTH_WRITEMASK, &depthMask);
        glGetFloatv(GL_DEPTH_CLEAR_VALUE, &oldDepth);
        glDepthMask(GL_TRUE);
        glClearDepthf(depth);
        bits |= GL_DEPTH_BUFFER_BIT;
    }
    if (whichToClear & 4)
    {
        glGetIntegerv(GL_STENCIL_WRITEMASK, &stencilFrontMask);
        glGetIntegerv(GL_STENCIL_BACK_WRITEMASK, &stencilBackMask);
        glGetIntegerv(GL_STENCIL_CLEAR_VALUE, &oldStencil);
        glStencilMaskSeparate(GL_FRONT, ~0u);
        glStencilMaskSeparate(GL_BACK, ~0u);
        glClearStencil(stencil);
        bits |= GL_STENCIL_BUFFER_BIT;
    }

    glEnable(GL_SCISSOR_TEST);
    glScissor(viewport[0], viewport[1], viewport[2], viewport[3]);
    glClear(bits);
    glScissor(oldScissorBox[0], oldScissorBox[1],
              oldScissorBox[2], oldScissorBox[3]);
    if (!scissor)
        glDisable(GL_SCISSOR_TEST);

    if (whichToClear & 1)
    {
        glColorMask(colorMask[0], colorMask[1], colorMask[2], colorMask[3]);
        glClearColor(oldColor[0], oldColor[1], oldColor[2], oldColor[3]);
    }
    if (whichToClear & 2)
    {
        glDepthMask(depthMask);
        glClearDepthf(oldDepth);
    }
    if (whichToClear & 4)
    {
        glStencilMaskSeparate(GL_FRONT, static_cast<GLuint>(stencilFrontMask));
        glStencilMaskSeparate(GL_BACK, static_cast<GLuint>(stencilBackMask));
        glClearStencil(oldStencil);
    }
    return glGetError() == GL_NO_ERROR;
}
#endif
