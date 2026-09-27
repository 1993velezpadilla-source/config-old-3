LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)

LOCAL_MODULE := main

SDL_PATH := ../SDL
MIXER_PATH := ../SDL2_mixer
GL4ES_PATH := ../gl4es
VRIL_PATH := ../vril

LOCAL_C_INCLUDES :=     $(LOCAL_PATH)/$(SDL_PATH)/include     $(LOCAL_PATH)/$(MIXER_PATH)/include     $(LOCAL_PATH)/$(GL4ES_PATH)/include     $(LOCAL_PATH)/$(VRIL_PATH)/source

VRIL_ENGINE_SOURCES :=     $(wildcard $(LOCAL_PATH)/$(VRIL_PATH)/source/*.c)     $(wildcard $(LOCAL_PATH)/$(VRIL_PATH)/source/menu/*.c)     $(wildcard $(LOCAL_PATH)/$(VRIL_PATH)/source/qcvm/*.c)     $(wildcard $(LOCAL_PATH)/$(VRIL_PATH)/source/render/*.c)     $(wildcard $(LOCAL_PATH)/$(VRIL_PATH)/source/tests/*.c)

VRIL_SDL_SOURCES :=     $(wildcard $(LOCAL_PATH)/$(VRIL_PATH)/source/platform/sdl/*.c)     $(wildcard $(LOCAL_PATH)/$(VRIL_PATH)/source/platform/sdl/gl/*.c)

LOCAL_SRC_FILES :=     $(subst $(LOCAL_PATH)/,,$(VRIL_ENGINE_SOURCES))     $(subst $(LOCAL_PATH)/,,$(VRIL_SDL_SOURCES))     xziel_android_bridge.c

# Normal builds keep NZ:P's classic 24-AI ceiling. Benchmark builds can
# override this at prepare/build time without changing release behavior.
XZIEL_MAX_AI_COUNT ?= 24

LOCAL_CFLAGS :=     -O2     -std=gnu99     -Wall     -Wno-unused-variable     -Wno-unused-but-set-variable     -DGLQUAKE     -DPLATFORM_SDL     -DPLATFORM_CONFIRM_IS_ENTER     -DPLATFORM_DIRECTORY=sdl     -DPLATFORM_RENDERER=gl     -DMAX_AI_COUNT=$(XZIEL_MAX_AI_COUNT)     -DPLATFORM_USES_GENERIC_GLYPHS     -DPLATFORM_SUPPORTS_HIGH_FRAMERATES     -DPLATFORM_SUPPORTS_VIDEO_OPTIONS     -DPLATFORM_SUPPORTS_GYRO     -DPLATFORM_SUPPORTS_RUMBLE

LOCAL_SHARED_LIBRARIES := SDL2 SDL2_mixer
LOCAL_STATIC_LIBRARIES := GL

LOCAL_LDLIBS :=     -lGLESv2     -lEGL     -lOpenSLES     -landroid     -llog     -ldl     -lm

include $(BUILD_SHARED_LIBRARY)
