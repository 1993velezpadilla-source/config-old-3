LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)

LOCAL_MODULE := xziel

SDL_PATH := ../SDL
XZ_PATH := ../xz

LOCAL_C_INCLUDES := \
    $(LOCAL_PATH)/$(SDL_PATH)/include \
    $(LOCAL_PATH)/$(XZ_PATH)

XZIEL_SOURCES := $(wildcard $(LOCAL_PATH)/$(XZ_PATH)/*.c)

LOCAL_SRC_FILES := $(subst $(LOCAL_PATH)/,,$(XZIEL_SOURCES))

LOCAL_CFLAGS := \
    -O2 \
    -std=gnu99 \
    -Wall \
    -Wno-unused-variable \
    -Wno-unused-but-set-variable \
    -DXZIEL_ANDROID_STANDALONE=1

LOCAL_SHARED_LIBRARIES := SDL2

LOCAL_LDLIBS := \
    -lGLESv3 \
    -lEGL \
    -landroid \
    -llog \
    -ldl \
    -lm

include $(BUILD_SHARED_LIBRARY)
