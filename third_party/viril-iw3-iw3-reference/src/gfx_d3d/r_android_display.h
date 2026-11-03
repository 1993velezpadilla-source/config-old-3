#pragma once
// Real Android Surface + Display -> original IW3 renderer display-mode dvars.
// NOT a graphics backend, not a frame, and not a playable Android game.
#if defined(__ANDROID__)
#include <jni.h>
#include <cstdint>

// Value-only snapshot: no borrowed JNI refs or native-window pointers survive
// the Activity-thread capture. The caller owns synchronization/handoff.
struct IW3AndroidSurfaceMode
{
    uint32_t width;
    uint32_t height;
    uint32_t refreshHz;
};

// May be called from the Android Activity thread. On failure, *out is unchanged.
// JNI refs are borrowed; caller retains ownership of Surface and Display.
bool R_AndroidReadSurfaceMode(JNIEnv *env, jobject surface, jobject display,
                              IW3AndroidSurfaceMode *out);

// Must be called on the original renderer initialization thread after a live
// surface exists; mutates original dx state and registers genuine renderer dvars.
bool R_AndroidApplySurfaceMode(const IW3AndroidSurfaceMode &mode);

// Convenience only when already on the renderer initialization thread.
// Do NOT invoke directly from Activity UI/lifecycle callbacks.
bool R_AndroidPopulateDisplayMode(JNIEnv *env, jobject surface, jobject display);
#endif
