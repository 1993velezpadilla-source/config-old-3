cmake_minimum_required(VERSION 3.22.1)
project(ctw3d_loader C CXX)

add_library(Game SHARED
    ctw_loader.c
    ctw_patch.c
    ctw_camera.c
    ctw_camera_pose.c
    ctw_character.c
    ctw_runtime_policy.c
    ctw_hooks.c
    ctw_trampoline.c
    ctw_hook_backend.c
    ctw_profile.c
    ctw_config.c
)

target_compile_features(Game PRIVATE c_std_11)
target_compile_options(Game PRIVATE -Wall -Wextra -Werror -fvisibility=hidden)
target_link_libraries(Game PRIVATE dl log android)

option(CTW_USE_DOBBY "Enable Dobby fallback for advanced ARM64 relocation" OFF)
set(CTW_DOBBY_DIR "" CACHE PATH "Path to pinned Dobby source checkout")

if(CTW_USE_DOBBY)
    if(NOT CTW_DOBBY_DIR OR NOT EXISTS "${CTW_DOBBY_DIR}/CMakeLists.txt")
        message(FATAL_ERROR "CTW_USE_DOBBY requires CTW_DOBBY_DIR")
    endif()

    set(DOBBY_GENERATE_SHARED OFF CACHE BOOL "" FORCE)
    set(DOBBY_DEBUG OFF CACHE BOOL "" FORCE)
    set(DOBBY_BUILD_EXAMPLE OFF CACHE BOOL "" FORCE)
    set(DOBBY_BUILD_TEST OFF CACHE BOOL "" FORCE)
    set(Plugin.SymbolResolver OFF CACHE BOOL "" FORCE)
    set(Plugin.ImportTableReplace OFF CACHE BOOL "" FORCE)
    set(Plugin.Android.BionicLinkerUtil OFF CACHE BOOL "" FORCE)

    add_subdirectory("${CTW_DOBBY_DIR}" "${CMAKE_BINARY_DIR}/dobby")
    target_include_directories(Game PRIVATE "${CTW_DOBBY_DIR}/include")
    target_link_libraries(Game PRIVATE dobby)
    target_compile_definitions(Game PRIVATE CTW_HAVE_DOBBY=1)
endif()

set_target_properties(Game PROPERTIES
    OUTPUT_NAME "Game"
)
