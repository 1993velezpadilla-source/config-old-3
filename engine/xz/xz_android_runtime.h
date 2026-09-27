#ifndef XZ_ANDROID_RUNTIME_H
#define XZ_ANDROID_RUNTIME_H

#include "xz_nacht_reference.h"

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

void XzAndroidRuntime_Init(size_t engine_heap_bytes);
void XzAndroidRuntime_SetVerifiedMapPackageMode(int enabled);
typedef enum {
    XZ_LEGACY_DRAW_ALIAS = 0,
    XZ_LEGACY_DRAW_SURFACE,
    XZ_LEGACY_DRAW_SPRITE,
    XZ_LEGACY_DRAW_EFFECT,
    XZ_LEGACY_DRAW_SPECIAL,
    XZ_LEGACY_DRAW_SHADOW,
    XZ_LEGACY_DRAW_COUNT
} XzLegacyWorldDrawKind;

void XzAndroidRuntime_BeginFrame(double now_seconds);
void XzAndroidRuntime_NotifyWorldTransition(void);
void XzAndroidRuntime_NotifyWorldTransitionNamed(
    const char *world_model_name);
int XzAndroidRuntime_ActiveMapIsVerifiedPackage(void);
int XzAndroidRuntime_StaticSceneReady(void);
int XzAndroidRuntime_ActiveMapIsNachtBo3(void);
const XzNachtGameplayState *XzAndroidRuntime_NachtState(void);
int XzAndroidRuntime_ShouldSuppressLegacyWorldDraw(
    XzLegacyWorldDrawKind kind);
int XzAndroidRuntime_CompositeVisibleWorld(void);
void XzAndroidRuntime_AuditLegacyPresentBeforeSwap(
    unsigned int width,
    unsigned int height);
void XzAndroidRuntime_EndFrame(double now_seconds);
void XzAndroidRuntime_Shutdown(void);

#ifdef __cplusplus
}
#endif

#endif
