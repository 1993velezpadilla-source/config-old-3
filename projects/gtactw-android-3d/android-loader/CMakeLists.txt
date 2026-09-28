cmake_minimum_required(VERSION 3.22.1)
project(ctw3d_loader C)

add_library(Game SHARED
    ctw_loader.c
    ctw_patch.c
    ctw_camera.c
    ctw_profile.c
    ctw_config.c
)

target_compile_features(Game PRIVATE c_std_11)
target_compile_options(Game PRIVATE -Wall -Wextra -Werror -fvisibility=hidden)
target_link_libraries(Game PRIVATE dl log android)

set_target_properties(Game PROPERTIES
    OUTPUT_NAME "Game"
)
