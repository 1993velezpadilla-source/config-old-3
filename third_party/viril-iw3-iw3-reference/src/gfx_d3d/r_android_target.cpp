// Original KisakCOD IW3 render-target selection -> GLES3 FBO bridge.
// Not a replacement renderer. Never invents textures or pretends to draw.
#if defined(__ANDROID__)
#include "r_android_target.h"
#include <EGL/egl.h>
#include <GLES3/gl3.h>

namespace {
constexpr int kTargetCount = 15;
constexpr int kFrameBufferId = 1; // Original R_RENDERTARGET_FRAME_BUFFER
struct Target {
    GLuint fbo = 0;
    int width = 0;
    int height = 0;
};
Target targets[kTargetCount] = {};
EGLDisplay ownerDisplay = EGL_NO_DISPLAY;
EGLContext ownerContext = EGL_NO_CONTEXT;
int boundWidth = 0;
int boundHeight = 0;

bool CurrentContext()
{
    const EGLDisplay display = eglGetCurrentDisplay();
    const EGLContext context = eglGetCurrentContext();
    if (display == EGL_NO_DISPLAY || context == EGL_NO_CONTEXT)
        return false;
    return ownerContext == EGL_NO_CONTEXT
        || (display == ownerDisplay && context == ownerContext);
}

bool AdoptContext()
{
    if (!CurrentContext())
        return false;
    if (ownerContext == EGL_NO_CONTEXT) {
        ownerDisplay = eglGetCurrentDisplay();
        ownerContext = eglGetCurrentContext();
    }
    return true;
}
}

bool R_AndroidGlesRegisterTarget(int id, unsigned int colorTexture,
                                 unsigned int depthStencilRenderbuffer,
                                 int width, int height)
{
    // Attachments must already have been created by the genuine IW3 image
    // backend. No synthetic image, texture allocation or map is performed.
    if (id < 0 || id >= kTargetCount || id == kFrameBufferId
        || width <= 0 || height <= 0
        || (!colorTexture && !depthStencilRenderbuffer)
        || !AdoptContext() || targets[id].fbo
        || glGetError() != GL_NO_ERROR)
        return false;

    GLint previous = 0;
    glGetIntegerv(GL_FRAMEBUFFER_BINDING, &previous);
    GLuint fbo = 0;
    glGenFramebuffers(1, &fbo);
    if (!fbo || glGetError() != GL_NO_ERROR) {
        if (fbo)
            glDeleteFramebuffers(1, &fbo);
        return false;
    }
    glBindFramebuffer(GL_FRAMEBUFFER, fbo);
    if (colorTexture)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                               GL_TEXTURE_2D, colorTexture, 0);
    else {
        const GLenum none = GL_NONE;
        glDrawBuffers(1, &none);
        glReadBuffer(GL_NONE);
    }
    if (depthStencilRenderbuffer)
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_STENCIL_ATTACHMENT,
                                  GL_RENDERBUFFER, depthStencilRenderbuffer);
    const bool complete = glCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE;
    const bool noError = glGetError() == GL_NO_ERROR;
    glBindFramebuffer(GL_FRAMEBUFFER, static_cast<GLuint>(previous));
    const bool restored = glGetError() == GL_NO_ERROR;
    if (!complete || !noError || !restored) {
        glDeleteFramebuffers(1, &fbo);
        return false;
    }
    targets[id] = {fbo, width, height};
    return true;
}

bool R_AndroidGlesBindTarget(int id, int width, int height)
{
    if (id < 0 || id >= kTargetCount || width <= 0 || height <= 0
        || !AdoptContext() || glGetError() != GL_NO_ERROR)
        return false;
    GLuint fbo = 0;
    if (id == kFrameBufferId) {
        const EGLSurface surface = eglGetCurrentSurface(EGL_DRAW);
        EGLint w = 0, h = 0;
        if (surface == EGL_NO_SURFACE
            || !eglQuerySurface(ownerDisplay, surface, EGL_WIDTH, &w)
            || !eglQuerySurface(ownerDisplay, surface, EGL_HEIGHT, &h)
            || w != width || h != height)
            return false;
    } else {
        const Target &target = targets[id];
        if (!target.fbo || target.width != width || target.height != height)
            return false; // original offscreen image has not been registered
        fbo = target.fbo;
    }
    GLint previousFbo = 0, previousViewport[4] = {0, 0, 0, 0};
    glGetIntegerv(GL_FRAMEBUFFER_BINDING, &previousFbo);
    glGetIntegerv(GL_VIEWPORT, previousViewport);
    glBindFramebuffer(GL_FRAMEBUFFER, fbo);
    const bool complete = id == kFrameBufferId
        || glCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE;
    if (complete)
        glViewport(0, 0, width, height);
    if (!complete || glGetError() != GL_NO_ERROR) {
        glBindFramebuffer(GL_FRAMEBUFFER, static_cast<GLuint>(previousFbo));
        glViewport(previousViewport[0], previousViewport[1],
                   previousViewport[2], previousViewport[3]);
        glGetError();
        return false;
    }
    boundWidth = width;
    boundHeight = height;
    return true;
}

bool R_AndroidGlesGetBoundTargetDimensions(int *width, int *height)
{
    if (!width || !height || !CurrentContext()
        || boundWidth <= 0 || boundHeight <= 0)
        return false;
    *width = boundWidth;
    *height = boundHeight;
    return true;
}

bool R_AndroidGlesReleaseTargets()
{
    if (ownerContext == EGL_NO_CONTEXT)
        return true;
    // Must run before EGL context destruction on the original render thread.
    if (!CurrentContext() || glGetError() != GL_NO_ERROR)
        return false;
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
    if (glGetError() != GL_NO_ERROR)
        return false;
    for (Target &target : targets) {
        if (target.fbo) {
            glDeleteFramebuffers(1, &target.fbo);
            target = {};
        }
    }
    if (glGetError() != GL_NO_ERROR)
        return false;
    boundWidth = 0;
    boundHeight = 0;
    ownerDisplay = EGL_NO_DISPLAY;
    ownerContext = EGL_NO_CONTEXT;
    return true;
}
#endif
