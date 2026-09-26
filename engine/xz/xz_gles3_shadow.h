#ifndef XZ_GLES3_SHADOW_H
#define XZ_GLES3_SHADOW_H

#include "xz_render_plan.h"
#include "xz_command_stream.h"
#include "xz_geometry_tap.h"
#include "xz_static_scene_runtime.h"

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    int initialized;
    int available;
    int shader_ok;
    int restore_ok;

    unsigned int submit_stride;
    float quality_scale;
    unsigned int resource_proxy_max;
    uint64_t quality_scale_updates;

    uint64_t submit_attempts;
    uint64_t submitted_frames;
    uint64_t skipped_frames;
    uint64_t submitted_packets;
    uint64_t draw_calls;
    uint64_t failures;
    uint64_t restore_failures;
    uint64_t readback_failures;

    uint64_t command_stream_submissions;
    uint64_t commands_executed;
    uint64_t passes_executed;
    uint64_t resource_read_commands;
    uint64_t resource_write_commands;
    uint64_t draw_commands;
    uint64_t command_failures;

    unsigned int physical_alive;
    unsigned int physical_gl_objects;
    uint64_t physical_creates;
    uint64_t physical_reuses;
    uint64_t physical_destroys;
    uint64_t physical_read_binds;
    uint64_t physical_write_binds;
    uint64_t physical_failures;
    uint64_t physical_bytes;

    uint64_t framebuffer_binds;
    uint64_t framebuffer_checks;
    uint64_t framebuffer_failures;
    uint64_t framebuffer_external_passes;
    uint64_t framebuffer_color_attachments;
    uint64_t framebuffer_depth_attachments;
    uint64_t target_plan_failures;

    uint64_t sampled_passes;
    uint64_t sampled_draws;
    uint64_t sampled_input_binds;
    uint64_t sampled_failures;
    unsigned int sampled_max_inputs;

    uint64_t material_packets;
    uint64_t material_lit_packets;
    uint64_t material_vertices;
    unsigned int last_material_flags;

    uint64_t real_geometry_submissions;
    uint64_t real_geometry_draw_calls;
    uint64_t real_geometry_vertices;
    uint64_t real_geometry_indices;
    uint64_t real_geometry_failures;
    unsigned int real_geometry_kind_mask;
    unsigned int last_geometry_batches;
    unsigned int last_geometry_vertices;
    unsigned int last_geometry_indices;
    unsigned int last_geometry_drops;
    unsigned int last_effect_batches;
    unsigned int last_special_batches;
    unsigned int last_sky_batches;
    unsigned int last_water_batches;
    int real_geometry_ready;
    unsigned int real_scene_ready_streak;
    int real_effects_ready;
    int real_sky_ready;
    int real_water_ready;

    uint64_t static_scene_upload_attempts;
    uint64_t static_scene_upload_successes;
    uint64_t static_scene_upload_failures;
    uint64_t static_scene_gpu_bytes;
    uint64_t static_scene_gpu_vertices;
    uint64_t static_scene_gpu_indices;
    unsigned int static_scene_gpu_meshes;
    unsigned int static_scene_gpu_submeshes;
    int static_scene_gpu_ready;

    uint64_t static_scene_draw_attempts;
    uint64_t static_scene_draw_successes;
    uint64_t static_scene_draw_failures;
    unsigned int static_scene_last_draw_calls;
    unsigned int static_scene_last_instances;
    unsigned int static_scene_fbo_nonblack_pixels;
    unsigned int static_scene_surface_nonblack_pixels;
    unsigned int static_scene_postrestore_nonblack_pixels;
    unsigned int static_scene_readback_width;
    unsigned int static_scene_readback_height;
    int static_scene_frame_ready;

    uint64_t real_texture_uploads;
    uint64_t real_texture_binds;
    uint64_t real_texture_bytes;
    uint64_t real_texture_misses;
    uint64_t real_texture_failures;
    unsigned int real_texture_kind_mask;
    unsigned int last_texture_batches;
    unsigned int last_texture_misses;
    int real_textures_ready;

    unsigned int last_material_state_batches;
    unsigned int last_blended_batches;
    unsigned int last_lightmap_batches;
    unsigned int last_alpha_test_batches;
    unsigned int last_modulate_batches;
    int real_material_state_ready;

    unsigned int last_fog_batches;
    unsigned int last_cull_batches;
    unsigned int last_depth_range_batches;
    unsigned int last_polygon_offset_batches;
    int real_raster_state_ready;

    uint64_t visible_present_attempts;
    uint64_t visible_present_successes;
    uint64_t visible_present_failures;
    uint64_t visible_present_draw_calls;
    unsigned int visible_render_width;
    unsigned int visible_render_height;
    unsigned int visible_surface_width;
    unsigned int visible_surface_height;
    unsigned int visible_present_streak;
    int visible_context_ready;
    int visible_present_ready;

    unsigned int last_packet_count;
    uint32_t last_plan_hash;
    uint32_t last_command_hash;
    unsigned int last_gl_error;
    unsigned int last_error_stage;
    uint64_t preexisting_errors;

    unsigned char last_expected_rgba[4];
    unsigned char last_readback_rgba[4];
} XzGles3ShadowState;

void XzGles3Shadow_InitState(
    XzGles3ShadowState *state);

int XzGles3Shadow_Init(
    XzGles3ShadowState *state,
    unsigned int submit_stride);

int XzGles3Shadow_SetQualityScale(
    XzGles3ShadowState *state,
    float scale);

int XzGles3Shadow_Submit(
    XzGles3ShadowState *state,
    const XzRenderPlan *plan);

int XzGles3Shadow_SubmitCommands(
    XzGles3ShadowState *state,
    const XzCommandStream *commands,
    const XzRenderPlan *plan,
    XzGpuResourcePool *resources,
    const XzGeometryFrame *geometry);

int XzGles3Shadow_UploadStaticScene(
    XzGles3ShadowState *state,
    const XzStaticSceneRuntimeState *scene);

void XzGles3Shadow_ReleaseStaticScene(
    XzGles3ShadowState *state);

int XzGles3Shadow_CompositeVisibleWorld(
    XzGles3ShadowState *state,
    const XzGeometryFrame *geometry,
    unsigned int render_width,
    unsigned int render_height);

void XzGles3Shadow_Shutdown(
    XzGles3ShadowState *state);

#ifdef __cplusplus
}
#endif

#endif
