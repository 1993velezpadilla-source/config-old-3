// KisakCOD IW3: Android Surface/Display mode capture and renderer-thread handoff.
//
// This reads the REAL Android Surface and Display, then feeds the ORIGINAL IW3
// display-mode builder. It is not a D3D9 implementation or a graphics backend.
// JNI capture may occur on the Activity thread; renderer state must be changed
// only on the engine's renderer initialization thread.
#if defined(__ANDROID__)
#include "r_android_display.h"
#include "r_init.h"
#include <android/native_window_jni.h>
#include <cmath>
#include <cstdint>

bool R_AndroidReadSurfaceMode(JNIEnv *env, jobject surface, jobject display,
                              IW3AndroidSurfaceMode *out)
{
    if (!env || !surface || !display || !out || env->ExceptionCheck())
        return false;

    ANativeWindow *window = ANativeWindow_fromSurface(env, surface);
    if (!window || env->ExceptionCheck())
    {
        if (window)
            ANativeWindow_release(window);
        return false;
    }
    const int width = ANativeWindow_getWidth(window);
    const int height = ANativeWindow_getHeight(window);
    ANativeWindow_release(window);

    // Display.getRefreshRate() is the OS-reported CURRENT refresh rate.
    jclass displayClass = env->GetObjectClass(display);
    if (!displayClass || env->ExceptionCheck())
    {
        if (displayClass)
            env->DeleteLocalRef(displayClass);
        return false;
    }
    jmethodID getRefreshRate = env->GetMethodID(displayClass, "getRefreshRate", "()F");
    if (!getRefreshRate || env->ExceptionCheck())
    {
        env->DeleteLocalRef(displayClass);
        return false;
    }
    const float refreshHz = env->CallFloatMethod(display, getRefreshRate);
    const bool javaFailed = env->ExceptionCheck();
    env->DeleteLocalRef(displayClass);
    if (javaFailed)
        return false;

    // Android can provide narrow portrait surfaces. The original renderer's
    // Android mode builder accepts >=320x320, unlike desktop's 640x480.
    // Do not publish partial or invalid data after a failed JNI operation.
    if (width < 320 || height < 320 || !std::isfinite(refreshHz)
        || refreshHz < 1.0f || refreshHz > 1000.0f)
        return false;

    const IW3AndroidSurfaceMode mode{
        static_cast<uint32_t>(width),
        static_cast<uint32_t>(height),
        static_cast<uint32_t>(refreshHz + 0.5f)
    };
    *out = mode;
    return true;
}

bool R_AndroidApplySurfaceMode(const IW3AndroidSurfaceMode &mode)
{
    // Must be called by the renderer initialization thread, not by an
    // Activity callback racing the original dx/dvar renderer globals.
    if (mode.width < 320 || mode.height < 320
        || mode.refreshHz < 1 || mode.refreshHz > 1000)
        return false;

    _D3DDISPLAYMODE nativeMode{};
    nativeMode.Width = mode.width;
    nativeMode.Height = mode.height;
    nativeMode.RefreshRate = mode.refreshHz;
    // Android has no D3D9 display format. The original mode builder reads
    // Width/Height/RefreshRate only; do not claim a fabricated D3D format.
    nativeMode.Format = static_cast<_D3DFORMAT>(0);
    dx.displayModes[0] = nativeMode;
    dx.displayModeCount = 1;
    R_BuildDisplayModeDvars();
    return true;
}

bool R_AndroidPopulateDisplayMode(JNIEnv *env, jobject surface, jobject display)
{
    // Convenience entry point for callers already running on the renderer
    // initialization thread. Other callers MUST capture first, then hand off
    // the plain-value mode to R_AndroidApplySurfaceMode on that thread.
    IW3AndroidSurfaceMode mode{};
    return R_AndroidReadSurfaceMode(env, surface, display, &mode)
        && R_AndroidApplySurfaceMode(mode);
}
#endif // __ANDROID__
