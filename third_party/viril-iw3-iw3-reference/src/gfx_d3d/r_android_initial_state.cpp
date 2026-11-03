// GLES3 equivalent of the three initial D3D9 render-state settings used
// by original KisakCOD IW3 R_SetInitialContextState.
// D3DRS_SEPARATEALPHABLENDENABLE and D3DRS_TWOSIDEDSTENCILMODE enable
// capabilities that are always available in GLES3 via the separate
// blend/stencil functions; there is no corresponding GLES3 enable switch.
// D3DRS_ZENABLE=FALSE maps to disabling the depth test.
#if defined(__ANDROID__)
#include "r_android_initial_state.h"
#include <EGL/egl.h>
#include <GLES3/gl3.h>

bool R_AndroidGlesSetInitialContextState()
{
    if (eglGetCurrentDisplay() == EGL_NO_DISPLAY
        || eglGetCurrentContext() == EGL_NO_CONTEXT
        || glGetError() != GL_NO_ERROR)
        return false;

    glDisable(GL_DEPTH_TEST);
    return glGetError() == GL_NO_ERROR;
}
#endif
