cmake_minimum_required(VERSION 3.22.1)
project(ctw3d_loader C CXX ASM)

add_library(Game SHARED
    ctw_loader.c
    ctw_patch.c
    ctw_runtime_boot.c
    ctw_camera.c
    ctw_camera_pose.c
    ctw_character.c
    ctw_runtime_policy.c
    ctw_hooks.c
    ctw_trampoline.c
    ctw_hook_backend.c
    ctw_hook_session.c
    ctw_adapter_registry.c
    ctw_profile.c
    ctw_config.c
)

target_compile_features(Game PRIVATE c_std_11)
target_compile_options(Game PRIVATE -Wall -Wextra -Werror -fvisibility=hidden)
target_link_libraries(Game PRIVATE dl log android)

option(CTW_USE_SHADOWHOOK "Enable ShadowHook fallback for advanced ARM64 relocation" OFF)
set(CTW_SHADOWHOOK_DIR "" CACHE PATH "Path to pinned ShadowHook source checkout")

if(CTW_USE_SHADOWHOOK)
    if(NOT ANDROID)
        message(FATAL_ERROR "CTW_USE_SHADOWHOOK is Android-only")
    endif()
    if(NOT ANDROID_ABI STREQUAL "arm64-v8a")
        message(FATAL_ERROR "CTW_USE_SHADOWHOOK currently targets arm64-v8a only")
    endif()
    if(NOT CTW_SHADOWHOOK_DIR OR
       NOT EXISTS "${CTW_SHADOWHOOK_DIR}/shadowhook/src/main/cpp/shadowhook.c")
        message(FATAL_ERROR "CTW_USE_SHADOWHOOK requires CTW_SHADOWHOOK_DIR")
    endif()

    set(CTW_SHADOWHOOK_CPP
        "${CTW_SHADOWHOOK_DIR}/shadowhook/src/main/cpp"
    )

    file(GLOB CTW_SHADOWHOOK_SOURCES CONFIGURE_DEPENDS
        "${CTW_SHADOWHOOK_CPP}/*.c"
        "${CTW_SHADOWHOOK_CPP}/arch/arm64/*.c"
        "${CTW_SHADOWHOOK_CPP}/arch/arm64/*.S"
        "${CTW_SHADOWHOOK_CPP}/common/*.c"
        "${CTW_SHADOWHOOK_CPP}/third_party/*/*.c"
    )
    # ShadowHook's sh_jni.c exports JNI_OnLoad for its Java wrapper.
    # CTW's proxy owns JNI_OnLoad, so only embed the native hook core.
    list(
        FILTER CTW_SHADOWHOOK_SOURCES
        EXCLUDE REGEX ".*/sh_jni\\.c$"
    )

    add_library(ctw_shadowhook STATIC ${CTW_SHADOWHOOK_SOURCES})
    set_target_properties(
        ctw_shadowhook
        PROPERTIES POSITION_INDEPENDENT_CODE ON
    )
    target_compile_features(ctw_shadowhook PRIVATE c_std_11)
    target_compile_options(
        ctw_shadowhook
        PRIVATE -Os -ffunction-sections -fdata-sections
    )
    target_include_directories(
        ctw_shadowhook
        PUBLIC "${CTW_SHADOWHOOK_CPP}/include"
        PRIVATE
            "${CTW_SHADOWHOOK_CPP}"
            "${CTW_SHADOWHOOK_CPP}/arch/arm64"
            "${CTW_SHADOWHOOK_CPP}/common"
            "${CTW_SHADOWHOOK_CPP}/third_party/xdl"
            "${CTW_SHADOWHOOK_CPP}/third_party/bsd"
            "${CTW_SHADOWHOOK_CPP}/third_party/lss"
    )
    target_link_libraries(ctw_shadowhook PUBLIC log)

    target_link_libraries(Game PRIVATE ctw_shadowhook)
    target_compile_definitions(Game PRIVATE CTW_HAVE_SHADOWHOOK=1)
endif()

set_target_properties(Game PROPERTIES
    OUTPUT_NAME "Game"
)
