// Android GLES3 synchronization for the genuine KisakCOD IW3 render path.
// No fake D3D9 query, no software renderer and no gameplay claim.
#if defined(__ANDROID__)
#include "r_android_gpu_fence.h"

static bool R_AndroidGpuFenceIsOwner(const IW3AndroidGpuFence *state)
{
    return state && state->ownerThreadValid
        && pthread_equal(state->ownerThread, pthread_self()) != 0;
}

static bool R_AndroidGpuFenceIsCurrent(const IW3AndroidGpuFence *state)
{
    return R_AndroidGpuFenceIsOwner(state)
        && state->display != EGL_NO_DISPLAY
        && state->context != EGL_NO_CONTEXT
        && eglGetCurrentDisplay() == state->display
        && eglGetCurrentContext() == state->context;
}

bool R_AndroidGpuFenceBind(IW3AndroidGpuFence *state, EGLDisplay display, EGLContext context)
{
    if (!state || state->ownerThreadValid || state->sync
        || display == EGL_NO_DISPLAY || context == EGL_NO_CONTEXT
        || eglGetCurrentDisplay() != display
        || eglGetCurrentContext() != context)
        return false;
    state->display = display;
    state->context = context;
    state->ownerThread = pthread_self();
    state->ownerThreadValid = true;
    return true;
}

bool R_AndroidGpuFenceInsert(IW3AndroidGpuFence *state)
{
    if (!R_AndroidGpuFenceIsCurrent(state) || state->sync)
        return false; // never silently replace a pending fence
    GLsync fence = glFenceSync(GL_SYNC_GPU_COMMANDS_COMPLETE, 0);
    if (!fence)
        return false;
    state->sync = fence;
    // Ensure commands, including the fence, reach the GPU on this context.
    glFlush();
    return true;
}

static IW3AndroidGpuFenceResult R_AndroidGpuFenceCheck(IW3AndroidGpuFence *state,
                                                        GLbitfield flags, GLuint64 timeout)
{
    if (!R_AndroidGpuFenceIsCurrent(state))
        return IW3AndroidGpuFenceResult::Invalid;
    if (!state->sync)
        return IW3AndroidGpuFenceResult::Idle;
    const GLenum result = glClientWaitSync(state->sync, flags, timeout);
    if (result == GL_TIMEOUT_EXPIRED)
        return IW3AndroidGpuFenceResult::Pending;
    if (result != GL_ALREADY_SIGNALED && result != GL_CONDITION_SATISFIED)
        return IW3AndroidGpuFenceResult::Invalid; // GL_WAIT_FAILED: preserve fence for cleanup
    glDeleteSync(state->sync);
    state->sync = nullptr;
    return IW3AndroidGpuFenceResult::Complete;
}

IW3AndroidGpuFenceResult R_AndroidGpuFencePoll(IW3AndroidGpuFence *state)
{
    return R_AndroidGpuFenceCheck(state, 0, 0);
}

IW3AndroidGpuFenceResult R_AndroidGpuFenceWait(IW3AndroidGpuFence *state, uint64_t timeoutNs)
{
    // GLES3 implementations can have problematic long waits. One call is
    // bounded to 50 ms; callers may poll again after handling Pending.
    constexpr uint64_t maxWaitNs = 50000000ULL;
    if (timeoutNs > maxWaitNs)
        timeoutNs = maxWaitNs;
    return R_AndroidGpuFenceCheck(state, GL_SYNC_FLUSH_COMMANDS_BIT,
                                  static_cast<GLuint64>(timeoutNs));
}

bool R_AndroidGpuFenceAbandon(IW3AndroidGpuFence *state)
{
    if (!R_AndroidGpuFenceIsCurrent(state))
        return false;
    if (state->sync)
    {
        glDeleteSync(state->sync);
        state->sync = nullptr;
    }
    return true;
}

bool R_AndroidGpuFenceRelease(IW3AndroidGpuFence *state)
{
    if (!R_AndroidGpuFenceIsOwner(state))
        return false;
    // A detached EGL surface can leave the context non-current. It is safe
    // to release only if no live GLsync object remains.
    if (state->sync && !R_AndroidGpuFenceAbandon(state))
        return false;
    state->display = EGL_NO_DISPLAY;
    state->context = EGL_NO_CONTEXT;
    state->ownerThread = pthread_t{};
    state->ownerThreadValid = false;
    return true;
}
// Original IW3 render-thread bridge: one owned GLsync, never a synthetic query.
static IW3AndroidGpuFence s_iw3OriginalGpuFence;
bool R_AndroidGpuFenceBindOriginal(EGLDisplay display, EGLContext context)
{
    return R_AndroidGpuFenceBind(&s_iw3OriginalGpuFence, display, context);
}
bool R_AndroidGpuFenceReleaseOriginal()
{
    return R_AndroidGpuFenceRelease(&s_iw3OriginalGpuFence);
}
bool R_AndroidGpuFenceOriginalInsert()
{
    return R_AndroidGpuFenceInsert(&s_iw3OriginalGpuFence);
}
IW3AndroidGpuFenceResult R_AndroidGpuFenceOriginalPoll()
{
    return R_AndroidGpuFencePoll(&s_iw3OriginalGpuFence);
}
IW3AndroidGpuFenceResult R_AndroidGpuFenceOriginalWait(uint64_t timeoutNs)
{
    return R_AndroidGpuFenceWait(&s_iw3OriginalGpuFence, timeoutNs);
}
bool R_AndroidGpuFenceOriginalAbandon()
{
    if (!s_iw3OriginalGpuFence.sync)
        return false;
    return R_AndroidGpuFenceAbandon(&s_iw3OriginalGpuFence);
}
#endif // __ANDROID__
