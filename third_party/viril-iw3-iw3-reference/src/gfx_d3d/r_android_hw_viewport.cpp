// GLES3 implementation for the ORIGINAL IW3 R_HW_SetViewport state path.
// Does not draw geometry, allocate images, or fabricate a game frame.
#if defined(__ANDROID__)
#include "r_android_hw_viewport.h"
#include "r_android_target.h"
#include "r_android_viewport.h"
#include <GLES3/gl3.h>
#include <cmath>

bool R_AndroidGlesHardwareViewport(int x, int y, int width, int height,
                                   float nearValue, float farValue)
{
    int targetWidth = 0, targetHeight = 0;
    if (!R_AndroidGlesGetBoundTargetDimensions(&targetWidth, &targetHeight)
        || !std::isfinite(nearValue) || !std::isfinite(farValue)
        || nearValue < 0.0f || farValue > 1.0f || nearValue >= farValue
        || glGetError() != GL_NO_ERROR)
        return false;

    // Save both pieces of state: a failed depth-range operation must not
    // leave a changed viewport behind in the original command buffer.
    GLint oldViewport[4] = {};
    GLfloat oldDepthRange[2] = {};
    glGetIntegerv(GL_VIEWPORT, oldViewport);
    glGetFloatv(GL_DEPTH_RANGE, oldDepthRange);
    if (glGetError() != GL_NO_ERROR)
        return false;

    if (!R_AndroidGlesSetViewport(x, y, width, height, targetWidth, targetHeight))
        return false;
    glDepthRangef(nearValue, farValue);
    if (glGetError() == GL_NO_ERROR)
        return true;

    glViewport(oldViewport[0], oldViewport[1], oldViewport[2], oldViewport[3]);
    glDepthRangef(oldDepthRange[0], oldDepthRange[1]);
    glGetError(); // Caller treats the operation as fatal regardless of rollback.
    return false;
}
#endif
