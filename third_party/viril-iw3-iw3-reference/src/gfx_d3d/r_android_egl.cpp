// KisakCOD IW3 Android platform EGL/GLES3 surface lifecycle.
// NOT an alternate engine or a renderer: original IW3 material/geometry/draw
// translation, R_Init integration, and real gameplay remain unimplemented.
#if defined(__ANDROID__)
#include "r_android_egl.h"
#include "r_android_gpu_fence.h"
#include <EGL/eglext.h>

static bool R_AndroidEglIsOwnerThread(const IW3AndroidEglContext *state)
{
    return state && state->ownerThreadValid
        && pthread_equal(state->ownerThread, pthread_self()) != 0;
}

// The original IW3 fence bridge owns GLsync objects. It must be released
// BEFORE unbinding or destroying its EGL context, never from the UI thread.
static bool R_AndroidEglBindOriginalFence(IW3AndroidEglContext *state)
{
    if (!state || state->gpuFenceBound
        || !R_AndroidGpuFenceBindOriginal(state->display, state->context))
        return false;
    state->gpuFenceBound = true;
    return true;
}

static bool R_AndroidEglReleaseOriginalFence(IW3AndroidEglContext *state)
{
    if (!state)
        return false;
    if (!state->gpuFenceBound)
        return true; // partial Create and detached context have no bridge
    if (!R_AndroidGpuFenceReleaseOriginal())
        return false; // pending GLsync cannot be deleted from another context
    state->gpuFenceBound = false;
    return true;
}

bool R_AndroidEglDestroy(IW3AndroidEglContext *state)
{
    if (!state)
        return false;
    // EGL resources and original IW3 GLsync belong to the render thread.
    if (state->ownerThreadValid && !R_AndroidEglIsOwnerThread(state))
        return false;
    if (!R_AndroidEglReleaseOriginalFence(state))
        return false;

    if (state->display != EGL_NO_DISPLAY)
    {
        // A failed unbind must NOT be followed by destroying a still-current
        // context. Keep ownership and handles so the render thread can retry.
        if (state->context != EGL_NO_CONTEXT
            && eglGetCurrentContext() == state->context
            && !eglMakeCurrent(state->display, EGL_NO_SURFACE, EGL_NO_SURFACE,
                               EGL_NO_CONTEXT))
            return false;

        // Tear down one resource at a time. EGL drivers can reject any step;
        // only clear handles after successful destruction, otherwise retry
        // would double-destroy already freed resources or leak a Surface.
        if (state->context != EGL_NO_CONTEXT)
        {
            if (!eglDestroyContext(state->display, state->context))
                return false;
            state->context = EGL_NO_CONTEXT;
        }
        if (state->surface != EGL_NO_SURFACE)
        {
            if (!eglDestroySurface(state->display, state->surface))
                return false;
            state->surface = EGL_NO_SURFACE;
        }
        if (!eglTerminate(state->display))
            return false;
        state->display = EGL_NO_DISPLAY;
    }
    if (state->window)
        ANativeWindow_release(state->window);
    state->display = EGL_NO_DISPLAY;
    state->surface = EGL_NO_SURFACE;
    state->context = EGL_NO_CONTEXT;
    state->config = nullptr;
    state->nativeVisualId = 0;
    state->window = nullptr;
    state->width = 0;
    state->height = 0;
    state->ownerThreadValid = false;
    state->gpuFenceBound = false;
    state->ownerThread = pthread_t{};
    return true;
}

bool R_AndroidEglRefreshSize(IW3AndroidEglContext *state)
{
    // Android can resize an existing EGL window surface without replacing
    // its EGLSurface. Query EGL (not cached ANativeWindow geometry) on the
    // engine render thread before updating the original IW3 viewport.
    if (!R_AndroidEglIsOwnerThread(state)
        || state->display == EGL_NO_DISPLAY
        || state->surface == EGL_NO_SURFACE
        || state->context == EGL_NO_CONTEXT
        || eglGetCurrentDisplay() != state->display
        || eglGetCurrentContext() != state->context
        || eglGetCurrentSurface(EGL_DRAW) != state->surface)
        return false;

    EGLint width = 0;
    EGLint height = 0;
    if (!eglQuerySurface(state->display, state->surface, EGL_WIDTH, &width)
        || !eglQuerySurface(state->display, state->surface, EGL_HEIGHT, &height)
        || width <= 0 || height <= 0)
        return false;

    // Publish both values together only after all checks pass.
    state->width = width;
    state->height = height;
    return true;
}

bool R_AndroidEglCreate(IW3AndroidEglContext *state, ANativeWindow *window)
{
    if (!state || !window || state->window
        || state->display != EGL_NO_DISPLAY
        || state->context != EGL_NO_CONTEXT
        || state->surface != EGL_NO_SURFACE
        || state->ownerThreadValid)
        return false;

    state->ownerThread = pthread_self();
    state->ownerThreadValid = true;
    ANativeWindow_acquire(window);
    state->window = window;
    state->display = eglGetDisplay(EGL_DEFAULT_DISPLAY);
    if (state->display == EGL_NO_DISPLAY)
        goto fail;
    if (!eglInitialize(state->display, nullptr, nullptr))
        goto fail;
    if (!eglBindAPI(EGL_OPENGL_ES_API))
        goto fail;

    {
        // Explicit ES3 is necessary for the planned real IW3 shader backend.
        // Do not silently downgrade to ES2 or claim D3D9 compatibility.
        const EGLint attrs[] = {
            EGL_SURFACE_TYPE, EGL_WINDOW_BIT,
            EGL_RENDERABLE_TYPE, EGL_OPENGL_ES3_BIT_KHR,
            EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8,
            EGL_ALPHA_SIZE, 8, EGL_DEPTH_SIZE, 24, EGL_STENCIL_SIZE, 8,
            EGL_NONE
        };
        EGLConfig config = nullptr;
        EGLint count = 0;
        if (!eglChooseConfig(state->display, attrs, &config, 1, &count)
            || count != 1 || !config)
            goto fail;

        EGLint visualId = 0;
        if (!eglGetConfigAttrib(state->display, config, EGL_NATIVE_VISUAL_ID,
                                &visualId)
            || visualId <= 0
            || ANativeWindow_setBuffersGeometry(window, 0, 0, visualId) != 0)
            goto fail;

        state->surface = eglCreateWindowSurface(state->display, config,
                                                window, nullptr);
        if (state->surface == EGL_NO_SURFACE)
            goto fail;

        const EGLint ctxAttrs[] = { EGL_CONTEXT_CLIENT_VERSION, 3, EGL_NONE };
        state->context = eglCreateContext(state->display, config,
                                           EGL_NO_CONTEXT, ctxAttrs);
        if (state->context == EGL_NO_CONTEXT)
            goto fail;
        if (!eglMakeCurrent(state->display, state->surface, state->surface,
                            state->context))
            goto fail;
        if (!R_AndroidEglRefreshSize(state))
            goto fail;
        if (!R_AndroidEglBindOriginalFence(state))
            goto fail; // never publish a usable EGL provider with unbound IW3 sync
        state->config = config;
        state->nativeVisualId = visualId;
    }
    return true;

fail:
    R_AndroidEglDestroy(state);
    return false;
}

// Pause rendering while preserving the genuine IW3 GLES3 context. Android may
// destroy its Surface before a replacement exists (Activity background/rotation).
// Only the owning render thread may detach; no IW3 draw calls are performed.
bool R_AndroidEglDetachWindow(IW3AndroidEglContext *state)
{
    if (!R_AndroidEglIsOwnerThread(state)
        || state->display == EGL_NO_DISPLAY
        || state->context == EGL_NO_CONTEXT
        || state->surface == EGL_NO_SURFACE || !state->window
        || eglGetCurrentDisplay() != state->display
        || eglGetCurrentContext() != state->context
        || eglGetCurrentSurface(EGL_DRAW) != state->surface
        || eglGetCurrentSurface(EGL_READ) != state->surface)
        return false;

    // Delete any live GLsync while the original EGL context is still current.
    // A failed unbind/surface destruction restores the original bridge only
    // if EGL successfully restores the original current context.
    if (!R_AndroidEglReleaseOriginalFence(state))
        return false;
    if (!eglMakeCurrent(state->display, EGL_NO_SURFACE, EGL_NO_SURFACE,
                        EGL_NO_CONTEXT))
    {
        R_AndroidEglBindOriginalFence(state); // best-effort on driver failure
        return false;
    }
    if (!eglDestroySurface(state->display, state->surface))
    {
        if (eglMakeCurrent(state->display, state->surface, state->surface,
                           state->context))
            R_AndroidEglBindOriginalFence(state);
        return false;
    }
    ANativeWindow_release(state->window);
    state->surface = EGL_NO_SURFACE;
    state->window = nullptr;
    state->width = 0;
    state->height = 0;
    return true;
}

// Surface replacement is necessary after Android destroys/recreates a Surface
// while the engine's render thread keeps the same ES3 context alive.
// Do not mutate IW3 renderer state here: this only replaces the EGL drawable.
bool R_AndroidEglReplaceWindow(IW3AndroidEglContext *state, ANativeWindow *newWindow)
{
    const bool detached = state && state->surface == EGL_NO_SURFACE
        && state->window == nullptr;
    if (!state || !newWindow || newWindow == state->window
        || !R_AndroidEglIsOwnerThread(state)
        || state->display == EGL_NO_DISPLAY
        || state->context == EGL_NO_CONTEXT
        || !state->config || state->nativeVisualId <= 0
        || (!detached && (!state->gpuFenceBound
            || state->surface == EGL_NO_SURFACE || !state->window
            || eglGetCurrentDisplay() != state->display
            || eglGetCurrentContext() != state->context
            || eglGetCurrentSurface(EGL_DRAW) != state->surface
            || eglGetCurrentSurface(EGL_READ) != state->surface))
        || (detached && (eglGetCurrentDisplay() != EGL_NO_DISPLAY
            || eglGetCurrentContext() != EGL_NO_CONTEXT
            || eglGetCurrentSurface(EGL_DRAW) != EGL_NO_SURFACE
            || eglGetCurrentSurface(EGL_READ) != EGL_NO_SURFACE)))
        return false;

    ANativeWindow_acquire(newWindow);
    if (ANativeWindow_setBuffersGeometry(newWindow, 0, 0,
                                         state->nativeVisualId) != 0)
    {
        ANativeWindow_release(newWindow);
        return false;
    }
    EGLSurface replacement = eglCreateWindowSurface(state->display,
                                                      state->config,
                                                      newWindow, nullptr);
    if (replacement == EGL_NO_SURFACE)
    {
        ANativeWindow_release(newWindow);
        return false;
    }
    EGLint width = 0;
    EGLint height = 0;
    // Query before making it current, so all failures leave the old surface
    // current and its cached size untouched.
    if (!eglQuerySurface(state->display, replacement, EGL_WIDTH, &width)
        || !eglQuerySurface(state->display, replacement, EGL_HEIGHT, &height)
        || width <= 0 || height <= 0)
    {
        eglDestroySurface(state->display, replacement);
        ANativeWindow_release(newWindow);
        return false;
    }
    if (!eglMakeCurrent(state->display, replacement, replacement,
                        state->context))
    {
        // A failed eglMakeCurrent is not guaranteed to preserve the previous
        // thread binding on every driver. Attempt to restore the original
        // drawable before releasing the candidate. Never publish candidate
        // dimensions or release the previous ANativeWindow on failure.
        if (!detached)
            eglMakeCurrent(state->display, state->surface, state->surface,
                           state->context);
        eglDestroySurface(state->display, replacement);
        ANativeWindow_release(newWindow);
        return false;
    }
    if (detached && !R_AndroidEglBindOriginalFence(state))
    {
        // Never publish a resumed Surface with unbound original IW3 GLsync.
        eglMakeCurrent(state->display, EGL_NO_SURFACE, EGL_NO_SURFACE,
                       EGL_NO_CONTEXT);
        eglDestroySurface(state->display, replacement);
        ANativeWindow_release(newWindow);
        return false;
    }
    EGLSurface oldSurface = state->surface;
    ANativeWindow *oldWindow = state->window;
    state->surface = replacement;
    state->window = newWindow;
    state->width = width;
    state->height = height;
    if (oldSurface != EGL_NO_SURFACE)
        eglDestroySurface(state->display, oldSurface);
    if (oldWindow)
        ANativeWindow_release(oldWindow);
    return true;
}

bool R_AndroidEglPresent(const IW3AndroidEglContext *state)
{
    // A successful swap only proves an EGL surface, NOT an IW3 rendered frame.
    if (!state || !state->gpuFenceBound || !R_AndroidEglIsOwnerThread(state)
        || state->display == EGL_NO_DISPLAY
        || state->surface == EGL_NO_SURFACE
        || state->context == EGL_NO_CONTEXT
        || eglGetCurrentDisplay() != state->display
        || eglGetCurrentContext() != state->context
        || eglGetCurrentSurface(EGL_DRAW) != state->surface)
        return false;
    return eglSwapBuffers(state->display, state->surface) == EGL_TRUE;
}
#endif // __ANDROID__
