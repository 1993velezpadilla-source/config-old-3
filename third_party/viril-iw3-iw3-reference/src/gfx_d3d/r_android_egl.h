#pragma once
// Android EGL/GLES3 context lifecycle for the authentic KisakCOD IW3 renderer.
// This is a platform surface provider ONLY: it does not translate IW3 D3D9
// draw commands, load maps, or constitute a playable Android build.
#if defined(__ANDROID__)
#include <android/native_window.h>
#include <pthread.h>
#include <EGL/egl.h>

struct IW3AndroidEglContext
{
    EGLDisplay display = EGL_NO_DISPLAY;
    EGLSurface surface = EGL_NO_SURFACE;
    EGLContext context = EGL_NO_CONTEXT;
    EGLConfig config = nullptr; // EGLConfig selected by Create, reused on Surface replacement
    EGLint nativeVisualId = 0;
    ANativeWindow *window = nullptr; // acquired reference owned by this object
    EGLint width = 0;
    EGLint height = 0;
    pthread_t ownerThread{};
    bool ownerThreadValid = false;
    // Original IW3 GLsync bridge is bound only while this EGL context is current.
    bool gpuFenceBound = false;

    IW3AndroidEglContext() = default;
    IW3AndroidEglContext(const IW3AndroidEglContext &) = delete;
    IW3AndroidEglContext &operator=(const IW3AndroidEglContext &) = delete;
};

// All operations are restricted to the thread that successfully began Create.
// In particular, Destroy rejects a foreign thread WITHOUT releasing any state;
// the Android lifecycle must dispatch cleanup to the owning render thread.
// The caller must serialize Surface destruction/recreation and keep the Java Surface alive.
// No JNI references are retained; window is acquired/released explicitly.
bool R_AndroidEglCreate(IW3AndroidEglContext *state, ANativeWindow *window);
// Refresh actual EGL surface dimensions after Android Surface resize/rotation.
// Requires the provider's context and draw surface current on the render thread.
// Failed queries preserve the last valid dimensions; no viewport is changed.
bool R_AndroidEglRefreshSize(IW3AndroidEglContext *state);
// Transactionally attach a newly created Android Surface on the owning render thread.
// Keeps the original ES3 context; the previous surface remains usable on failure.
// Does NOT connect the genuine IW3 draw-command backend or prove rendering.
// Release the current Android Surface while retaining the ES3 context.
// Used for Activity pause/surfaceDestroyed; requires owner thread and current
// EGL context. ReplaceWindow can later attach a new Surface from this state.
// No draw/present calls are valid between detach and reattach.
bool R_AndroidEglDetachWindow(IW3AndroidEglContext *state);
bool R_AndroidEglReplaceWindow(IW3AndroidEglContext *state, ANativeWindow *newWindow);
bool R_AndroidEglPresent(const IW3AndroidEglContext *state);
// Returns false on null state or a foreign thread (state left intact).
// Idempotent on the owning thread, including after failed partial Create.
bool R_AndroidEglDestroy(IW3AndroidEglContext *state);
#endif
