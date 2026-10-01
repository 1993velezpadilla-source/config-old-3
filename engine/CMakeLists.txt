cmake_minimum_required(VERSION 3.22)
project(xziel_engine LANGUAGES CXX)

option(XZIEL_ENGINE_BUILD_TESTS "Build Xziel Engine smoke tests" ON)

add_library(xziel_engine STATIC
    src/engine.cpp
    src/movement.cpp
    src/mobile_controls.cpp
    src/fps_player.cpp
    src/weapon.cpp
    src/weapon_catalog.cpp
    src/hitscan.cpp
    src/zombie_actor.cpp
    src/player_vitals.cpp
    src/horde_director.cpp
    src/zombie_hit_regions.cpp
    src/score.cpp
    src/survival_systems.cpp
    src/interaction.cpp
    src/barricade.cpp
    src/zombie_window.cpp
    src/door.cpp
    src/map_runtime.cpp
    src/map_format.cpp
    src/gameplay_events.cpp
    src/quest_runtime.cpp
    src/environment.cpp
    src/particles.cpp
    src/performance.cpp
    src/horror.cpp
    src/render_features.cpp
    src/renderer_capabilities.cpp
    src/streaming.cpp
    src/world_streaming.cpp
    src/scene_fx.cpp
    src/audio_scene.cpp
    src/intrinsic_ads.cpp
    src/frame_graph.cpp
    src/visibility.cpp
    src/haptics.cpp
    src/frame_telemetry.cpp
    src/runtime_policy.cpp
    src/renderer_watchdog.cpp
    src/android_runtime.cpp
    src/crowd_budget.cpp
    src/camera_rig.cpp
    src/gpu_scene.cpp
    src/acoustics.cpp
    src/asset_provenance.cpp
    src/sanctum.cpp
    src/static_mesh.cpp
    src/texture_container.cpp
)

target_include_directories(xziel_engine
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_compile_features(xziel_engine PUBLIC cxx_std_20)

if(CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
    target_compile_options(xziel_engine PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()

if(XZIEL_ENGINE_BUILD_TESTS)
    enable_testing()

    add_executable(xziel_engine_smoke tests/engine_smoke.cpp)
    target_link_libraries(xziel_engine_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_engine_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_engine_smoke COMMAND xziel_engine_smoke)

    add_executable(xziel_movement_smoke tests/movement_smoke.cpp)
    target_link_libraries(xziel_movement_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_movement_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_movement_smoke COMMAND xziel_movement_smoke)

    add_executable(xziel_fps_player_smoke tests/fps_player_smoke.cpp)
    target_link_libraries(xziel_fps_player_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_fps_player_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_fps_player_smoke COMMAND xziel_fps_player_smoke)

    add_executable(xziel_mobile_controls_smoke tests/mobile_controls_smoke.cpp)
    target_link_libraries(xziel_mobile_controls_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_mobile_controls_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_mobile_controls_smoke COMMAND xziel_mobile_controls_smoke)

    add_executable(xziel_fixed_tick_input_latch_smoke tests/fixed_tick_input_latch_smoke.cpp)
    target_link_libraries(xziel_fixed_tick_input_latch_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_fixed_tick_input_latch_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_fixed_tick_input_latch_smoke COMMAND xziel_fixed_tick_input_latch_smoke)

    add_executable(xziel_weapon_smoke tests/weapon_smoke.cpp)
    target_link_libraries(xziel_weapon_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_weapon_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_weapon_smoke COMMAND xziel_weapon_smoke)

    add_executable(xziel_weapon_catalog_smoke tests/weapon_catalog_smoke.cpp)
    target_link_libraries(xziel_weapon_catalog_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_weapon_catalog_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_weapon_catalog_smoke COMMAND xziel_weapon_catalog_smoke)

    add_executable(xziel_hitscan_smoke tests/hitscan_smoke.cpp)
    target_link_libraries(xziel_hitscan_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_hitscan_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_hitscan_smoke COMMAND xziel_hitscan_smoke)

    add_executable(xziel_zombie_actor_smoke tests/zombie_actor_smoke.cpp)
    target_link_libraries(xziel_zombie_actor_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_zombie_actor_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_zombie_actor_smoke COMMAND xziel_zombie_actor_smoke)

    add_executable(xziel_zombie_hit_regions_smoke tests/zombie_hit_regions_smoke.cpp)
    target_link_libraries(xziel_zombie_hit_regions_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_zombie_hit_regions_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_zombie_hit_regions_smoke COMMAND xziel_zombie_hit_regions_smoke)

    add_executable(xziel_score_smoke tests/score_smoke.cpp)
    target_link_libraries(xziel_score_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_score_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_score_smoke COMMAND xziel_score_smoke)

    add_executable(xziel_survival_systems_smoke tests/survival_systems_smoke.cpp)
    target_link_libraries(xziel_survival_systems_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_survival_systems_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_survival_systems_smoke COMMAND xziel_survival_systems_smoke)

    add_executable(xziel_player_vitals_smoke tests/player_vitals_smoke.cpp)
    target_link_libraries(xziel_player_vitals_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_player_vitals_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_player_vitals_smoke COMMAND xziel_player_vitals_smoke)

    add_executable(xziel_horde_director_smoke tests/horde_director_smoke.cpp)
    target_link_libraries(xziel_horde_director_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_horde_director_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_horde_director_smoke COMMAND xziel_horde_director_smoke)

    add_executable(xziel_interaction_smoke tests/interaction_smoke.cpp)
    target_link_libraries(xziel_interaction_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_interaction_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_interaction_smoke COMMAND xziel_interaction_smoke)

    add_executable(xziel_barricade_smoke tests/barricade_smoke.cpp)
    target_link_libraries(xziel_barricade_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_barricade_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_barricade_smoke COMMAND xziel_barricade_smoke)

    add_executable(xziel_zombie_window_smoke tests/zombie_window_smoke.cpp)
    target_link_libraries(xziel_zombie_window_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_zombie_window_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_zombie_window_smoke COMMAND xziel_zombie_window_smoke)

    add_executable(xziel_door_smoke tests/door_smoke.cpp)
    target_link_libraries(xziel_door_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_door_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_door_smoke COMMAND xziel_door_smoke)

    add_executable(xziel_map_runtime_smoke tests/map_runtime_smoke.cpp)
    target_link_libraries(xziel_map_runtime_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_map_runtime_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_map_runtime_smoke COMMAND xziel_map_runtime_smoke)

    add_executable(xziel_map_format_smoke tests/map_format_smoke.cpp)
    target_link_libraries(xziel_map_format_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_map_format_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_map_format_smoke COMMAND xziel_map_format_smoke)

    add_executable(xziel_gameplay_events_smoke tests/gameplay_events_smoke.cpp)
    target_link_libraries(xziel_gameplay_events_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_gameplay_events_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_gameplay_events_smoke COMMAND xziel_gameplay_events_smoke)

    add_executable(xziel_quest_runtime_smoke tests/quest_runtime_smoke.cpp)
    target_link_libraries(xziel_quest_runtime_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_quest_runtime_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_quest_runtime_smoke COMMAND xziel_quest_runtime_smoke)

    add_executable(xziel_environment_smoke tests/environment_smoke.cpp)
    target_link_libraries(xziel_environment_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_environment_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_environment_smoke COMMAND xziel_environment_smoke)

    add_executable(xziel_particles_smoke tests/particles_smoke.cpp)
    target_link_libraries(xziel_particles_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_particles_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_particles_smoke COMMAND xziel_particles_smoke)

    add_executable(xziel_performance_smoke tests/performance_smoke.cpp)
    target_link_libraries(xziel_performance_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_performance_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_performance_smoke COMMAND xziel_performance_smoke)

    add_executable(xziel_horror_smoke tests/horror_smoke.cpp)
    target_link_libraries(xziel_horror_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_horror_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_horror_smoke COMMAND xziel_horror_smoke)

    add_executable(xziel_render_features_smoke tests/render_features_smoke.cpp)
    target_link_libraries(xziel_render_features_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_render_features_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_render_features_smoke COMMAND xziel_render_features_smoke)

    add_executable(xziel_renderer_capabilities_smoke tests/renderer_capabilities_smoke.cpp)
    target_link_libraries(xziel_renderer_capabilities_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_renderer_capabilities_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_renderer_capabilities_smoke COMMAND xziel_renderer_capabilities_smoke)

    add_executable(xziel_streaming_smoke tests/streaming_smoke.cpp)
    target_link_libraries(xziel_streaming_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_streaming_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_streaming_smoke COMMAND xziel_streaming_smoke)

    add_executable(xziel_world_streaming_smoke tests/world_streaming_smoke.cpp)
    target_link_libraries(xziel_world_streaming_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_world_streaming_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_world_streaming_smoke COMMAND xziel_world_streaming_smoke)

    add_executable(xziel_scene_fx_smoke tests/scene_fx_smoke.cpp)
    target_link_libraries(xziel_scene_fx_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_scene_fx_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_scene_fx_smoke COMMAND xziel_scene_fx_smoke)

    add_executable(xziel_audio_scene_smoke tests/audio_scene_smoke.cpp)
    target_link_libraries(xziel_audio_scene_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_audio_scene_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_audio_scene_smoke COMMAND xziel_audio_scene_smoke)

    add_executable(xziel_intrinsic_ads_smoke tests/intrinsic_ads_smoke.cpp)
    target_link_libraries(xziel_intrinsic_ads_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_intrinsic_ads_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_intrinsic_ads_smoke COMMAND xziel_intrinsic_ads_smoke)

    add_executable(xziel_frame_graph_smoke tests/frame_graph_smoke.cpp)
    target_link_libraries(xziel_frame_graph_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_frame_graph_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_frame_graph_smoke COMMAND xziel_frame_graph_smoke)

    add_executable(xziel_visibility_smoke tests/visibility_smoke.cpp)
    target_link_libraries(xziel_visibility_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_visibility_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_visibility_smoke COMMAND xziel_visibility_smoke)

    add_executable(xziel_haptics_smoke tests/haptics_smoke.cpp)
    target_link_libraries(xziel_haptics_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_haptics_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_haptics_smoke COMMAND xziel_haptics_smoke)

    add_executable(xziel_frame_telemetry_smoke tests/frame_telemetry_smoke.cpp)
    target_link_libraries(xziel_frame_telemetry_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_frame_telemetry_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_frame_telemetry_smoke COMMAND xziel_frame_telemetry_smoke)

    add_executable(xziel_runtime_policy_smoke tests/runtime_policy_smoke.cpp)
    target_link_libraries(xziel_runtime_policy_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_runtime_policy_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_runtime_policy_smoke COMMAND xziel_runtime_policy_smoke)

    add_executable(xziel_spsc_queue_smoke tests/spsc_queue_smoke.cpp)
    target_link_libraries(xziel_spsc_queue_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_spsc_queue_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_spsc_queue_smoke COMMAND xziel_spsc_queue_smoke)

    add_executable(xziel_renderer_watchdog_smoke tests/renderer_watchdog_smoke.cpp)
    target_link_libraries(xziel_renderer_watchdog_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_renderer_watchdog_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_renderer_watchdog_smoke COMMAND xziel_renderer_watchdog_smoke)

    add_executable(xziel_android_runtime_smoke tests/android_runtime_smoke.cpp)
    target_link_libraries(xziel_android_runtime_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_android_runtime_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_android_runtime_smoke COMMAND xziel_android_runtime_smoke)

    add_executable(xziel_crowd_budget_smoke tests/crowd_budget_smoke.cpp)
    target_link_libraries(xziel_crowd_budget_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_crowd_budget_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_crowd_budget_smoke COMMAND xziel_crowd_budget_smoke)

    add_executable(xziel_camera_rig_smoke tests/camera_rig_smoke.cpp)
    target_link_libraries(xziel_camera_rig_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_camera_rig_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_camera_rig_smoke COMMAND xziel_camera_rig_smoke)

    add_executable(xziel_gpu_scene_smoke tests/gpu_scene_smoke.cpp)
    target_link_libraries(xziel_gpu_scene_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_gpu_scene_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_gpu_scene_smoke COMMAND xziel_gpu_scene_smoke)

    add_executable(xziel_acoustics_smoke tests/acoustics_smoke.cpp)
    target_link_libraries(xziel_acoustics_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_acoustics_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_acoustics_smoke COMMAND xziel_acoustics_smoke)

    add_executable(xziel_sanctum_smoke tests/sanctum_smoke.cpp)
    target_link_libraries(xziel_sanctum_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_sanctum_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_sanctum_smoke COMMAND xziel_sanctum_smoke)

    add_executable(xziel_static_mesh_smoke tests/static_mesh_smoke.cpp)
    target_link_libraries(xziel_static_mesh_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_static_mesh_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_static_mesh_smoke COMMAND xziel_static_mesh_smoke)

    add_executable(xziel_asset_provenance_smoke tests/asset_provenance_smoke.cpp)
    target_link_libraries(xziel_asset_provenance_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_asset_provenance_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_asset_provenance_smoke COMMAND xziel_asset_provenance_smoke)

    add_executable(xziel_texture_container_smoke tests/texture_container_smoke.cpp)
    target_link_libraries(xziel_texture_container_smoke PRIVATE xziel_engine)
    target_compile_features(xziel_texture_container_smoke PRIVATE cxx_std_20)
    add_test(NAME xziel_texture_container_smoke COMMAND xziel_texture_container_smoke)
endif()
