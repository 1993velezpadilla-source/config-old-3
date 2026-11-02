#pragma once
// Genuine GLES3 GPU fence provider for KisakCOD IW3 on Android.
// This is NOT a renderer, and no original IW3 draw command is wired here yet.
#if defined(__ANDROID__)
#include <EGL/egl.h>
#include <GLES3/gl3.h>
#include <pthread.h>
#include <stdint.h>

enum class IW3AndroidGpuFenceResult
{
    Invalid,  // wrong thread/context, unbound state or GLES wait failure
    Idle,     // no fence was issued
    Pending,  // GPU has not completed the submitted work
    Complete  // real GLES3 sync object signaled and was retired
};

struct IW3AndroidGpuFence
{
    EGLDisplay display = EGL_NO_DISPLAY;
    EGLContext context = EGL_NO_CONTEXT;
    pthread_t ownerThread{};
    bool ownerThreadValid = false;
    GLsync sync = nullptr;

    IW3AndroidGpuFence() = default;
    IW3AndroidGpuFence(const IW3AndroidGpuFence &) = delete;
    IW3AndroidGpuFence &operator=(const IW3AndroidGpuFence &) = delete;
};

// All methods are render-thread-only. Bind requires an actual current ES3
// context; no fabricated completion is ever returned on invalid state.
bool R_AndroidGpuFenceBind(IW3AndroidGpuFence *state, EGLDisplay display, EGLContext context);
bool R_AndroidGpuFenceInsert(IW3AndroidGpuFence *state);
IW3AndroidGpuFenceResult R_AndroidGpuFencePoll(IW3AndroidGpuFence *state);
// Bounded wait: never block the engine indefinitely in a driver call.
IW3AndroidGpuFenceResult R_AndroidGpuFenceWait(IW3AndroidGpuFence *state, uint64_t timeoutNs);
bool R_AndroidGpuFenceAbandon(IW3AndroidGpuFence *state);
// Must be called before EGL context destruction. Refuses unsafe deletion if
// a fence exists but its original context is no longer current.
bool R_AndroidGpuFenceRelease(IW3AndroidGpuFence *state);
#endif

// Explicit render-thread bridge for original IW3 GPU-fence call sites.
// Not automatically bound by the standalone EGL provider yet.
bool R_AndroidGpuFenceBindOriginal(EGLDisplay display, EGLContext context);
bool R_AndroidGpuFenceReleaseOriginal();
bool R_AndroidGpuFenceOriginalInsert();
IW3AndroidGpuFenceResult R_AndroidGpuFenceOriginalPoll();
IW3AndroidGpuFenceResult R_AndroidGpuFenceOriginalWait(uint64_t timeoutNs);
bool R_AndroidGpuFenceOriginalAbandon();
