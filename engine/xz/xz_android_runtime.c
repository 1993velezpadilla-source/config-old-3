#include "xz_android_runtime.h"
#include "xz_phase0.h"
#include "xz_present_world.h"
#include "xz_device_caps.h"
#include "xz_scene_budget.h"
#include "xz_render_plan.h"
#include "xz_rhi.h"
#include "xz_gles3_probe.h"
#include "xz_render_graph.h"
#include "xz_gles3_shadow.h"
#include "xz_gpu_resources.h"
#include "xz_command_stream.h"
#include "xz_gles3_resource_plan.h"
#include "xz_pass_targets.h"
#include "xz_pass_inputs.h"
#include "xz_visibility.h"
#include "xz_material_lighting.h"
#include "xz_active_quality.h"
#include "xz_stream_residency.h"
#include "xz_cutover.h"
#include "xz_geometry_tap.h"
#include "xz_texture_tap.h"
#include "xz_map_runtime.h"
#include "xz_package_boot.h"
#include "xz_zone_db.h"
#include "xz_runtime_readiness.h"
#include "xz_asset_loader_registry.h"
#include "xz_bulk_store.h"
#include "xz_asset_pool.h"
#include "xz_static_scene_runtime.h"

#include <SDL.h>

#include <inttypes.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef __ANDROID__
#include <android/log.h>
#include <sys/system_properties.h>
#endif

#define XZ_MIB (1024ull * 1024ull)

typedef struct {
    XzFrameMetrics frame;
    XzMemoryBudget memory;
    XzPerformanceGovernor governor;
    XzDeviceCaps caps;
    XzSceneBudget scene_budget;
    XzRenderPlan render_plan;
    XzRhiState rhi;
    XzGles3ProbeResult gles3_probe;
    XzRenderGraph render_graph;
    XzRenderGraphCompiled render_graph_compiled;
    XzGles3ShadowState gles3_shadow;
    XzGpuResourcePool gpu_resources;
    XzGpuHandle graph_resource_handles[XZ_RG_MAX_RESOURCES];
    XzCommandStream command_stream;
    XzActiveQualityState active_quality;
    XzStreamResidency stream_residency;
    XzCutoverState cutover;
    XzMapRuntimeState map_runtime;
    XzPackageBootState package_boot;
    XzZoneDb zone_db;
    XzRuntimeReadiness runtime_readiness;
    XzAssetPoolState asset_pools;
    XzBulkStore bulk_store;
    XzAssetLoaderRegistry asset_loaders;
    XzStaticSceneRuntimeState static_scene;
    uint64_t command_encode_failures;
    uint64_t graph_rebuild_failures;
    int graph_resources_ready;
    int initialized;
    int cpu_cores;
    int system_ram_mb;
    int refresh_hz;
    int display_width;
    int display_height;
    int android_api;
    int packed_gles_version;
    size_t engine_heap_bytes;
    uint64_t last_memory_sample_frame;
    uint64_t legacy_draws_suppressed_total;
    uint64_t legacy_draws_passthrough_total;
    uint64_t legacy_world_transitions;
    int legacy_world_suppression_armed;
    unsigned int legacy_draws_suppressed_frame[XZ_LEGACY_DRAW_COUNT];
    unsigned int legacy_draws_passthrough_frame[XZ_LEGACY_DRAW_COUNT];
    double last_log_seconds;
    char board_platform[PROP_VALUE_MAX];
    char egl_driver[PROP_VALUE_MAX];
    char vulkan_driver[PROP_VALUE_MAX];
    char device_model[PROP_VALUE_MAX];
} XzAndroidRuntimeState;

static XzAndroidRuntimeState xz_runtime;

static int XzGles3MirrorBegin(
    void *user,
    uint64_t frame_index)
{
    (void)user;
    (void)frame_index;
    return 1;
}

static int XzGles3MirrorSubmit(
    void *user,
    const XzRhiSubmission *submission)
{
    if (!submission)
        return 0;

    return XzGles3Shadow_SubmitCommands(
        (XzGles3ShadowState *)user,
        submission->commands,
        submission->plan,
        submission->resources,
        submission->geometry);
}

static int XzGles3MirrorEnd(void *user)
{
    (void)user;
    return 1;
}

static void XzGles3MirrorShutdown(void *user)
{
    XzGles3Shadow_Shutdown(
        (XzGles3ShadowState *)user);
}

static uint64_t XzClampU64(uint64_t value, uint64_t lo, uint64_t hi)
{
    if (value < lo) return lo;
    if (value > hi) return hi;
    return value;
}

#ifdef __ANDROID__
static void XzAndroidLog(
    android_LogPriority priority,
    const char *format,
    ...)
{
    va_list args;
    va_start(args, format);
    __android_log_vprint(priority, "XZIEL-XZ", format, args);
    va_end(args);
}

static void XzReadProperty(
    const char *name,
    char *output,
    size_t output_size)
{
    char temp[PROP_VALUE_MAX];
    int length;

    if (!output || !output_size)
        return;

    output[0] = '\0';
    temp[0] = '\0';
    length = __system_property_get(name, temp);
    if (length <= 0)
        return;

    snprintf(output, output_size, "%s", temp);
}
#else
static void XzAndroidLog(int priority, const char *format, ...)
{
    va_list args;
    (void)priority;
    va_start(args, format);
    vfprintf(stderr, format, args);
    fputc('\n', stderr);
    va_end(args);
}

static void XzReadProperty(
    const char *name,
    char *output,
    size_t output_size)
{
    (void)name;
    if (output && output_size)
        output[0] = '\0';
}
#define ANDROID_LOG_INFO 4
#define ANDROID_LOG_WARN 5
#endif

static uint64_t XzReadProcessRssBytes(void)
{
    FILE *file;
    char line[256];
    uint64_t kb = 0;

    file = fopen("/proc/self/status", "rb");
    if (!file)
        return 0;

    while (fgets(line, sizeof(line), file)) {
        if (sscanf(line, "VmRSS: %" SCNu64 " kB", &kb) == 1) {
            fclose(file);
            return kb * 1024ull;
        }
    }

    fclose(file);
    return 0;
}

static void XzChooseMemoryBudget(
    int system_ram_mb,
    uint64_t *soft_bytes,
    uint64_t *hard_bytes)
{
    uint64_t total;
    uint64_t soft;
    uint64_t hard;

    if (system_ram_mb <= 0)
        system_ram_mb = 4096;

    total = (uint64_t)system_ram_mb * XZ_MIB;
    soft = (uint64_t)((double)total * 0.18);
    hard = (uint64_t)((double)total * 0.26);

    soft = XzClampU64(soft, 256ull * XZ_MIB, 1024ull * XZ_MIB);
    hard = XzClampU64(hard, 384ull * XZ_MIB, 1536ull * XZ_MIB);
    if (hard <= soft)
        hard = soft + 128ull * XZ_MIB;

    *soft_bytes = soft;
    *hard_bytes = hard;
}

static void XzDetectDisplay(void)
{
    SDL_DisplayMode mode;

    memset(&mode, 0, sizeof(mode));
    xz_runtime.refresh_hz = 0;
    xz_runtime.display_width = 0;
    xz_runtime.display_height = 0;

    if (SDL_GetNumVideoDisplays() > 0 &&
        SDL_GetCurrentDisplayMode(0, &mode) == 0) {
        xz_runtime.refresh_hz = mode.refresh_rate;
        xz_runtime.display_width = mode.w;
        xz_runtime.display_height = mode.h;
    }
}

static void XzDetectRuntimeGlCaps(void)
{
    int major = 0;
    int minor = 0;

    if (SDL_GL_GetCurrentContext() != NULL) {
        SDL_GL_GetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, &major);
        SDL_GL_GetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, &minor);
    }

    XzDeviceCaps_SetRuntimeGl(
        &xz_runtime.caps,
        major,
        minor,
        SDL_GL_ExtensionSupported("GL_OES_vertex_array_object"),
        SDL_GL_ExtensionSupported("GL_EXT_discard_framebuffer"),
        SDL_GL_ExtensionSupported("GL_EXT_color_buffer_half_float") ||
            SDL_GL_ExtensionSupported("GL_EXT_color_buffer_float"),
        SDL_GL_ExtensionSupported("GL_EXT_disjoint_timer_query"));
}

static int XzBuildBootstrapRenderGraph(void)
{
    XzRgResourceDesc resource;
    XzRgPassDesc pass;
    int scene_color;
    int depth;
    int lit;
    int post;
    int swapchain;
    unsigned int width =
        xz_runtime.active_quality.initialized
            ? xz_runtime.active_quality.width
            : (xz_runtime.display_width > 0
                ? (unsigned int)xz_runtime.display_width
                : 1280u);
    unsigned int height =
        xz_runtime.active_quality.initialized
            ? xz_runtime.active_quality.height
            : (xz_runtime.display_height > 0
                ? (unsigned int)xz_runtime.display_height
                : 720u);
    XzRgFormat color_format =
        xz_runtime.caps.has_half_float_color
            ? XZ_RG_FORMAT_RGBA16F
            : XZ_RG_FORMAT_RGBA8;

    XzRenderGraph_Init(&xz_runtime.render_graph);

    memset(&resource, 0, sizeof(resource));
    resource.width = width;
    resource.height = height;
    resource.samples = 1u;
    resource.format = color_format;
    resource.flags =
        XZ_RG_RESOURCE_TRANSIENT |
        XZ_RG_RESOURCE_TILE_LOCAL;
    scene_color = XzRenderGraph_AddResource(
        &xz_runtime.render_graph, &resource);

    resource.format = XZ_RG_FORMAT_DEPTH24;
    resource.flags =
        XZ_RG_RESOURCE_TRANSIENT |
        XZ_RG_RESOURCE_TILE_LOCAL |
        XZ_RG_RESOURCE_MEMORYLESS;
    depth = XzRenderGraph_AddResource(
        &xz_runtime.render_graph, &resource);

    resource.format = color_format;
    resource.flags =
        XZ_RG_RESOURCE_TRANSIENT |
        XZ_RG_RESOURCE_TILE_LOCAL;
    lit = XzRenderGraph_AddResource(
        &xz_runtime.render_graph, &resource);
    post = XzRenderGraph_AddResource(
        &xz_runtime.render_graph, &resource);

    resource.width =
        xz_runtime.display_width > 0
            ? (unsigned int)xz_runtime.display_width
            : width;
    resource.height =
        xz_runtime.display_height > 0
            ? (unsigned int)xz_runtime.display_height
            : height;
    resource.format = XZ_RG_FORMAT_RGBA8;
    resource.flags =
        XZ_RG_RESOURCE_IMPORTED |
        XZ_RG_RESOURCE_PRESERVE;
    swapchain = XzRenderGraph_AddResource(
        &xz_runtime.render_graph, &resource);

    if (scene_color < 0 || depth < 0 || lit < 0 ||
        post < 0 || swapchain < 0)
        return 0;

    memset(&pass, 0, sizeof(pass));
    pass.write_mask =
        (1u << (unsigned int)scene_color) |
        (1u << (unsigned int)depth);
    if (XzRenderGraph_AddPass(
            &xz_runtime.render_graph, &pass) < 0)
        return 0;

    memset(&pass, 0, sizeof(pass));
    pass.read_mask =
        (1u << (unsigned int)scene_color) |
        (1u << (unsigned int)depth);
    pass.write_mask = 1u << (unsigned int)lit;
    if (XzRenderGraph_AddPass(
            &xz_runtime.render_graph, &pass) < 0)
        return 0;

    memset(&pass, 0, sizeof(pass));
    pass.read_mask = 1u << (unsigned int)lit;
    pass.write_mask = 1u << (unsigned int)post;
    if (XzRenderGraph_AddPass(
            &xz_runtime.render_graph, &pass) < 0)
        return 0;

    memset(&pass, 0, sizeof(pass));
    pass.read_mask = 1u << (unsigned int)post;
    pass.write_mask = 1u << (unsigned int)swapchain;
    if (XzRenderGraph_AddPass(
            &xz_runtime.render_graph, &pass) < 0)
        return 0;

    return XzRenderGraph_Compile(
        &xz_runtime.render_graph,
        &xz_runtime.render_graph_compiled);
}

static uint64_t XzGraphResourceSizeBytes(
    const XzRgResourceDesc *resource)
{
    uint64_t bytes_per_pixel = 4u;

    if (!resource)
        return 0u;

    switch (resource->format) {
    case XZ_RG_FORMAT_RGBA16F:
        bytes_per_pixel = 8u;
        break;
    case XZ_RG_FORMAT_RG16F:
        bytes_per_pixel = 4u;
        break;
    case XZ_RG_FORMAT_DEPTH16:
        bytes_per_pixel = 2u;
        break;
    case XZ_RG_FORMAT_DEPTH24:
        bytes_per_pixel = 4u;
        break;
    case XZ_RG_FORMAT_RGBA8:
    case XZ_RG_FORMAT_UNKNOWN:
    default:
        bytes_per_pixel = 4u;
        break;
    }

    return (uint64_t)resource->width *
           (uint64_t)resource->height *
           (uint64_t)(resource->samples ?
               resource->samples : 1u) *
           bytes_per_pixel;
}

static XzGpuResourceType XzGraphResourceType(
    const XzRgResourceDesc *resource)
{
    if (!resource)
        return XZ_GPU_RESOURCE_UNKNOWN;

    if (resource->flags & XZ_RG_RESOURCE_IMPORTED)
        return XZ_GPU_RESOURCE_EXTERNAL_SURFACE;

    if (resource->format == XZ_RG_FORMAT_DEPTH16 ||
        resource->format == XZ_RG_FORMAT_DEPTH24)
        return XZ_GPU_RESOURCE_DEPTH;

    return XZ_GPU_RESOURCE_TEXTURE;
}

static int XzInitGraphResourceHandles(void)
{
    unsigned int i;

    memset(
        xz_runtime.graph_resource_handles,
        0,
        sizeof(xz_runtime.graph_resource_handles));

    for (i = 0u;
         i < xz_runtime.render_graph.resource_count;
         ++i) {
        const XzRgResourceDesc *source =
            &xz_runtime.render_graph.resources[i];
        XzGpuResourceDesc desc;
        XzGpuHandle handle;

        memset(&desc, 0, sizeof(desc));
        desc.type = XzGraphResourceType(source);
        desc.format = (uint32_t)source->format;
        desc.flags = source->flags;
        desc.width = source->width;
        desc.height = source->height;
        desc.samples = source->samples ?
            source->samples : 1u;
        desc.size_bytes =
            XzGraphResourceSizeBytes(source);

        handle = XzGpuResource_Create(
            &xz_runtime.gpu_resources,
            &desc);

        if (handle == XZ_GPU_INVALID_HANDLE)
            return 0;

        xz_runtime.graph_resource_handles[i] =
            handle;
    }

    xz_runtime.graph_resources_ready = 1;
    return 1;
}

static void XzDestroyGraphResourceHandles(void)
{
    unsigned int i;

    for (i = 0u;
         i < xz_runtime.render_graph.resource_count;
         ++i) {
        XzGpuHandle handle =
            xz_runtime.graph_resource_handles[i];

        if (handle != XZ_GPU_INVALID_HANDLE)
            XzGpuResource_Destroy(
                &xz_runtime.gpu_resources,
                handle);

        xz_runtime.graph_resource_handles[i] =
            XZ_GPU_INVALID_HANDLE;
    }

    xz_runtime.graph_resources_ready = 0;
}

static int XzRebuildGraphResources(void)
{
    XzDestroyGraphResourceHandles();

    if (!XzBuildBootstrapRenderGraph())
        return 0;

    if (!XzInitGraphResourceHandles()) {
        XzDestroyGraphResourceHandles();
        return 0;
    }

    return 1;
}

static void XzEvaluateCutover(void)
{
    XzCutoverEvidence evidence;

    memset(&evidence, 0, sizeof(evidence));

    evidence.backend_healthy =
        xz_runtime.gles3_shadow.available &&
        xz_runtime.gles3_shadow.failures == 0u &&
        xz_runtime.gles3_shadow.restore_failures == 0u &&
        xz_runtime.rhi.mirror_failures == 0u;

    evidence.commands_healthy =
        xz_runtime.rhi.rejected_plans == 0u &&
        xz_runtime.rhi.rejected_commands == 0u &&
        xz_runtime.command_encode_failures == 0u &&
        xz_runtime.gles3_shadow.command_failures == 0u;

    evidence.graph_healthy =
        xz_runtime.render_graph_compiled.valid &&
        xz_runtime.graph_resources_ready &&
        xz_runtime.gles3_shadow.physical_failures == 0u &&
        xz_runtime.gles3_shadow.framebuffer_failures == 0u &&
        xz_runtime.gles3_shadow.sampled_failures == 0u;

    evidence.residency_healthy =
        xz_runtime.render_plan.packet_count == 0u ||
        xz_runtime.stream_residency.resident_count > 0u;

    evidence.active_quality_healthy =
        xz_runtime.active_quality.initialized &&
        xz_runtime.graph_rebuild_failures == 0u;

    /*
     * Real geometry becomes a cutover capability only after the GLES3 mirror
     * has consumed the captured alias/surface/sprite batches with no geometry
     * failures or capture overflow. Textures and visible presentation remain
     * explicit blockers until their own parity work is complete.
     */
    evidence.real_geometry_ready =
        xz_runtime.gles3_shadow.real_geometry_ready &&
        xz_runtime.gles3_shadow.real_geometry_failures == 0u &&
        xz_runtime.gles3_shadow.last_geometry_drops == 0u;
    evidence.real_textures_ready =
        xz_runtime.gles3_shadow.real_textures_ready &&
        xz_runtime.gles3_shadow.real_texture_failures == 0u &&
        xz_runtime.gles3_shadow.last_texture_misses == 0u;
    evidence.visible_present_ready =
        xz_runtime.gles3_shadow.visible_context_ready &&
        xz_runtime.gles3_shadow.real_material_state_ready &&
        xz_runtime.gles3_shadow.real_raster_state_ready &&
        xz_runtime.gles3_shadow.visible_present_ready;

    evidence.healthy_frames =
        xz_runtime.frame.total_frames;

    XzCutover_Evaluate(
        &xz_runtime.cutover,
        &evidence);
}

static void XzLogSnapshot(double now_seconds)
{
    const XzGovernorRecommendation *rec =
        &xz_runtime.governor.recommendation;
    const XzPresentFrame *present =
        XzPresentWorld_GetReadFrame();
    const XzSceneBudget *scene =
        &xz_runtime.scene_budget;
    const XzRenderPlan *plan =
        &xz_runtime.render_plan;
    const XzRhiState *rhi =
        &xz_runtime.rhi;
    const XzGles3ShadowState *g3 =
        &xz_runtime.gles3_shadow;
    const XzGpuResourcePool *gpu =
        &xz_runtime.gpu_resources;
    const XzCommandStream *commands =
        &xz_runtime.command_stream;
    const uint64_t present_generation =
        present ? present->generation : 0u;
    const unsigned int present_entities =
        present ? present->entity_count : 0u;
    const unsigned int present_alias =
        present ? present->alias_count : 0u;
    const unsigned int present_brush =
        present ? present->brush_count : 0u;
    const unsigned int present_sprite =
        present ? present->sprite_count : 0u;
    const unsigned int present_static =
        present ? present->static_brush_count : 0u;
    const unsigned int present_lights =
        present ? present->active_light_count : 0u;
    const unsigned int present_dropped =
        present ? present->dropped_entities : 0u;

    XzAndroidLog(
        ANDROID_LOG_INFO,
        "perf processed_frames=%" PRIu64
        " last=%.2fms avg=%.2f p50=%.2f p95=%.2f p99=%.2f max=%.2f"
        " rss=%.1fMiB high=%.1fMiB state=%s passive=%d"
        " present_gen=%" PRIu64
        " present=%u alias=%u brush=%u sprite=%u static=%u lights=%u dropped=%u"
        " budget(near=%u mid=%u far=%u crit=%u imp=%u bg=%u"
        " anim=%u shadow=%u vfx=%u light=%u/%u)"
        " plan(gen=%" PRIu64 " src=%u packets=%u culled=%u vis=%u/%u/%u"
        " lod=%u/%u/%u anim=%u shadow=%u vfx=%u"
        " mat=%u/%u/%u/%u lit=%u lights=%u/%u dark=%u hash=%08x)"
        " rhi(active=%s shadow=%d submitted=%" PRIu64
        " cmdStreams=%" PRIu64 " rejected=%" PRIu64
        " rejectedCmd=%" PRIu64 " cmdHash=%08x)"
        " mirror(backend=%s attached=%d attempts=%" PRIu64
        " submitted=%" PRIu64 " fail=%" PRIu64
        " beginFail=%" PRIu64 " endFail=%" PRIu64 ")"
        " g3shadow(submitted=%" PRIu64 " packets=%" PRIu64
        " draws=%" PRIu64 " fail=%" PRIu64 " readback=%" PRIu64
        " restoreFail=%" PRIu64 " restore=%d glerr=0x%x hash=%08x)"
        " g3diag(stage=%u preerr=%" PRIu64 ")"
        " g3cmd(streams=%" PRIu64 " commands=%" PRIu64
        " passes=%" PRIu64 " reads=%" PRIu64 " writes=%" PRIu64
        " draws=%" PRIu64 " fail=%" PRIu64 " hash=%08x)"
        " advice(render=%.2f anim=%.2f shadow=%.2f vfx=%.2f light=%.2f stream=%.2f)",
        xz_runtime.frame.total_frames,
        xz_runtime.frame.last_ms,
        xz_runtime.frame.average_ms,
        xz_runtime.frame.p50_ms,
        xz_runtime.frame.p95_ms,
        xz_runtime.frame.p99_ms,
        xz_runtime.frame.max_ms,
        (double)xz_runtime.memory.current_bytes / (double)XZ_MIB,
        (double)xz_runtime.memory.high_water_bytes / (double)XZ_MIB,
        XzGovernorState_Name(xz_runtime.governor.state),
        xz_runtime.governor.passive,
        present_generation,
        present_entities,
        present_alias,
        present_brush,
        present_sprite,
        present_static,
        present_lights,
        present_dropped,
        scene->near_entities,
        scene->mid_entities,
        scene->far_entities,
        scene->critical_entities,
        scene->important_entities,
        scene->background_entities,
        scene->full_animation_budget,
        scene->shadowed_entity_budget,
        scene->premium_vfx_budget,
        scene->admitted_lights,
        scene->dynamic_light_budget,
        plan->generation,
        plan->source_packet_count,
        plan->packet_count,
        plan->culled_packets,
        plan->visibility_front_count,
        plan->visibility_edge_count,
        plan->visibility_behind_count,
        plan->near_count,
        plan->mid_count,
        plan->far_count,
        plan->full_animation_count,
        plan->shadow_count,
        plan->premium_vfx_count,
        plan->material_color_count,
        plan->material_translucent_count,
        plan->material_glow_count,
        plan->material_additive_count,
        plan->lit_packet_count,
        plan->admitted_lights,
        plan->requested_lights,
        plan->dark_lights,
        plan->content_hash,
        XzRhiBackend_Name(rhi->active_backend),
        rhi->shadow_mode,
        rhi->submitted_frames,
        rhi->submitted_command_streams,
        rhi->rejected_plans,
        rhi->rejected_commands,
        rhi->last_command_hash,
        XzRhiBackend_Name(rhi->mirror_backend),
        rhi->mirror_attached,
        rhi->mirror_submit_attempts,
        rhi->mirror_submitted_frames,
        rhi->mirror_failures,
        rhi->mirror_begin_failures,
        rhi->mirror_end_failures,
        g3->submitted_frames,
        g3->submitted_packets,
        g3->draw_calls,
        g3->failures,
        g3->readback_failures,
        g3->restore_failures,
        g3->restore_ok,
        g3->last_gl_error,
        g3->last_plan_hash,
        g3->last_error_stage,
        g3->preexisting_errors,
        g3->command_stream_submissions,
        g3->commands_executed,
        g3->passes_executed,
        g3->resource_read_commands,
        g3->resource_write_commands,
        g3->draw_commands,
        g3->command_failures,
        g3->last_command_hash,
        rec->render_scale,
        rec->animation_rate_scale,
        rec->shadow_budget_scale,
        rec->vfx_budget_scale,
        rec->light_budget_scale,
        rec->streaming_aggression);

    /*
     * Keep graph/resource telemetry on a dedicated short logcat record.
     * Android truncates oversized records; splitting this preserves stable
     * machine-readable gates as Xz telemetry grows.
     */
    XzAndroidLog(
        ANDROID_LOG_INFO,
        "phase13 heartbeat init=%d graph=%d resources=%u mirror=%d"
        " gles3=%d sampled=%" PRIu64 " sampleFail=%" PRIu64
        " source=%u draw=%u culled=%u front=%u edge=%u behind=%u",
        xz_runtime.initialized,
        xz_runtime.render_graph_compiled.valid,
        xz_runtime.gpu_resources.alive_count,
        xz_runtime.rhi.mirror_attached,
        xz_runtime.gles3_shadow.available,
        xz_runtime.gles3_shadow.sampled_passes,
        xz_runtime.gles3_shadow.sampled_failures,
        plan->source_packet_count,
        plan->packet_count,
        plan->culled_packets,
        plan->visibility_front_count,
        plan->visibility_edge_count,
        plan->visibility_behind_count);

    XzAndroidLog(
        ANDROID_LOG_INFO,
        "phase15 heartbeat active=%d scale=%.2f requested=%.2f size=%ux%u"
        " proxy=%u qUpdates=%" PRIu64
        " changes=%" PRIu64 " suppressed=%" PRIu64
        " rebuildFail=%" PRIu64
        " streamCap=%u resident=%u high=%u"
        " loads=%" PRIu64 " hits=%" PRIu64
        " evict=%" PRIu64 " miss=%" PRIu64
        " unique=%u/%u aggression=%.2f",
        xz_runtime.governor.passive ? 0 : 1,
        xz_runtime.active_quality.applied_render_scale,
        xz_runtime.active_quality.requested_render_scale,
        xz_runtime.active_quality.width,
        xz_runtime.active_quality.height,
        xz_runtime.gles3_shadow.resource_proxy_max,
        xz_runtime.gles3_shadow.quality_scale_updates,
        xz_runtime.active_quality.changes,
        xz_runtime.active_quality.suppressed_changes,
        xz_runtime.graph_rebuild_failures,
        xz_runtime.stream_residency.capacity,
        xz_runtime.stream_residency.resident_count,
        xz_runtime.stream_residency.high_water_count,
        xz_runtime.stream_residency.loads,
        xz_runtime.stream_residency.hits,
        xz_runtime.stream_residency.evictions,
        xz_runtime.stream_residency.misses,
        xz_runtime.stream_residency.last_admitted_unique,
        xz_runtime.stream_residency.last_requested_unique,
        xz_runtime.stream_residency.last_aggression);

    {
        const XzGeometryFrame *geometry =
            XzGeometryTap_GetReadFrame();

        XzAndroidLog(
            ANDROID_LOG_INFO,
            "parity geometry generation=%" PRIu64
            " batches=%u vertices=%u indices=%u"
            " kinds=%u/%u/%u/%u/%u drops=%u/%u/%u"
            " g3sub=%" PRIu64 " g3draw=%" PRIu64
            " g3verts=%" PRIu64 " g3indices=%" PRIu64
            " g3fail=%" PRIu64 " kindMask=0x%x ready=%d",
            geometry ? geometry->generation : 0u,
            geometry ? geometry->batch_count : 0u,
            geometry ? geometry->vertex_count : 0u,
            geometry ? geometry->index_count : 0u,
            geometry ? geometry->alias_batches : 0u,
            geometry ? geometry->surface_batches : 0u,
            geometry ? geometry->sprite_batches : 0u,
            geometry ? geometry->effect_batches : 0u,
            geometry ? geometry->special_batches : 0u,
            geometry ? geometry->dropped_batches : 0u,
            geometry ? geometry->dropped_vertices : 0u,
            geometry ? geometry->dropped_indices : 0u,
            g3->real_geometry_submissions,
            g3->real_geometry_draw_calls,
            g3->real_geometry_vertices,
            g3->real_geometry_indices,
            g3->real_geometry_failures,
            g3->real_geometry_kind_mask,
            g3->real_geometry_ready);
    }

    {
        XzTextureTapStats texture_stats;

        XzTextureTap_GetStats(&texture_stats);
        XzAndroidLog(
            ANDROID_LOG_INFO,
            "parity texture captured=%" PRIu64
            " updates=%" PRIu64
            " resident=%u bytes=%zu high=%zu dropped=%" PRIu64
            " resolve=%" PRIu64 "/%" PRIu64
            " g3uploads=%" PRIu64 " g3binds=%" PRIu64
            " g3bytes=%" PRIu64 " g3miss=%" PRIu64
            " g3fail=%" PRIu64 " kindMask=0x%x"
            " lastBatches=%u lastMiss=%u ready=%d",
            texture_stats.captures,
            texture_stats.updates,
            texture_stats.resident_count,
            texture_stats.resident_bytes,
            texture_stats.high_water_bytes,
            texture_stats.dropped,
            texture_stats.resolve_hits,
            texture_stats.resolve_misses,
            g3->real_texture_uploads,
            g3->real_texture_binds,
            g3->real_texture_bytes,
            g3->real_texture_misses,
            g3->real_texture_failures,
            g3->real_texture_kind_mask,
            g3->last_texture_batches,
            g3->last_texture_misses,
            g3->real_textures_ready);
    }

    {
        const XzGeometryFrame *geometry =
            XzGeometryTap_GetReadFrame();

        XzAndroidLog(
            ANDROID_LOG_INFO,
            "parity shadows current=%u",
            geometry ? geometry->shadow_batches : 0u);
    }

    XzAndroidLog(
        ANDROID_LOG_INFO,
        "legacy3d suppress total=%" PRIu64 " pass=%" PRIu64
        " armed=%d transitions=%" PRIu64
        " frame(alias=%u surface=%u sprite=%u effect=%u special=%u shadow=%u)"
        " passFrame(alias=%u surface=%u sprite=%u effect=%u special=%u shadow=%u)",
        xz_runtime.legacy_draws_suppressed_total,
        xz_runtime.legacy_draws_passthrough_total,
        xz_runtime.legacy_world_suppression_armed,
        xz_runtime.legacy_world_transitions,
        xz_runtime.legacy_draws_suppressed_frame[XZ_LEGACY_DRAW_ALIAS],
        xz_runtime.legacy_draws_suppressed_frame[XZ_LEGACY_DRAW_SURFACE],
        xz_runtime.legacy_draws_suppressed_frame[XZ_LEGACY_DRAW_SPRITE],
        xz_runtime.legacy_draws_suppressed_frame[XZ_LEGACY_DRAW_EFFECT],
        xz_runtime.legacy_draws_suppressed_frame[XZ_LEGACY_DRAW_SPECIAL],
        xz_runtime.legacy_draws_suppressed_frame[XZ_LEGACY_DRAW_SHADOW],
        xz_runtime.legacy_draws_passthrough_frame[XZ_LEGACY_DRAW_ALIAS],
        xz_runtime.legacy_draws_passthrough_frame[XZ_LEGACY_DRAW_SURFACE],
        xz_runtime.legacy_draws_passthrough_frame[XZ_LEGACY_DRAW_SPRITE],
        xz_runtime.legacy_draws_passthrough_frame[XZ_LEGACY_DRAW_EFFECT],
        xz_runtime.legacy_draws_passthrough_frame[XZ_LEGACY_DRAW_SPECIAL],
        xz_runtime.legacy_draws_passthrough_frame[XZ_LEGACY_DRAW_SHADOW]);

    XzAndroidLog(
        ANDROID_LOG_INFO,
        "parity effects current=%u seen=%d",
        g3->last_effect_batches,
        g3->real_effects_ready);

    XzAndroidLog(
        ANDROID_LOG_INFO,
        "parity specials current=%u sky=%u water=%u skySeen=%d waterSeen=%d",
        g3->last_special_batches,
        g3->last_sky_batches,
        g3->last_water_batches,
        g3->real_sky_ready,
        g3->real_water_ready);

    XzAndroidLog(
        ANDROID_LOG_INFO,
        "parity material state=%u blend=%u lightmap=%u alpha=%u"
        " modulate=%u ready=%d",
        g3->last_material_state_batches,
        g3->last_blended_batches,
        g3->last_lightmap_batches,
        g3->last_alpha_test_batches,
        g3->last_modulate_batches,
        g3->real_material_state_ready);

    XzAndroidLog(
        ANDROID_LOG_INFO,
        "parity raster fog=%u cull=%u depthRange=%u offset=%u ready=%d",
        g3->last_fog_batches,
        g3->last_cull_batches,
        g3->last_depth_range_batches,
        g3->last_polygon_offset_batches,
        g3->real_raster_state_ready);

    XzAndroidLog(
        ANDROID_LOG_INFO,
        "parity present context=%d attempts=%" PRIu64
        " success=%" PRIu64 " fail=%" PRIu64
        " draws=%" PRIu64 " streak=%u"
        " render=%ux%u surface=%ux%u ready=%d",
        g3->visible_context_ready,
        g3->visible_present_attempts,
        g3->visible_present_successes,
        g3->visible_present_failures,
        g3->visible_present_draw_calls,
        g3->visible_present_streak,
        g3->visible_render_width,
        g3->visible_render_height,
        g3->visible_surface_width,
        g3->visible_surface_height,
        g3->visible_present_ready);

    XzAndroidLog(
        ANDROID_LOG_INFO,
        "phase16 heartbeat requested=%s active=%s candidate=%d allowed=%d"
        " caps=0x%x blockers=0x%x eval=%" PRIu64
        " blocked=%" PRIu64 " legacyVisible=%d",
        XzCutoverMode_Name(
            xz_runtime.cutover.requested_mode),
        XzCutoverMode_Name(
            xz_runtime.cutover.active_mode),
        xz_runtime.cutover.candidate_ready,
        xz_runtime.cutover.cutover_allowed,
        xz_runtime.cutover.capability_mask,
        xz_runtime.cutover.blocker_mask,
        xz_runtime.cutover.evaluations,
        xz_runtime.cutover.blocked_modern_evaluations,
        xz_runtime.cutover.active_mode !=
            XZ_CUTOVER_MODE_MODERN);

    XzAndroidLog(
        ANDROID_LOG_INFO,
        "graphio g3res(mapped=%u objects=%u create=%" PRIu64
        " reuse=%" PRIu64 " destroy=%" PRIu64
        " read=%" PRIu64 " write=%" PRIu64
        " fail=%" PRIu64 " bytes=%" PRIu64 ")"
        " g3fbo(bind=%" PRIu64 " check=%" PRIu64
        " fail=%" PRIu64 " external=%" PRIu64
        " color=%" PRIu64 " depth=%" PRIu64
        " targetFail=%" PRIu64 ")"
        " g3sample(passes=%" PRIu64 " draws=%" PRIu64
        " inputs=%" PRIu64 " fail=%" PRIu64 " max=%u)"
        " g3material(packets=%" PRIu64 " lit=%" PRIu64
        " vertices=%" PRIu64 " flags=0x%x)"
        " cmd(count=%u hash=%08x overflow=%u resources=%u high=%u"
        " stale=%" PRIu64 " encodeFail=%" PRIu64 ")",
        g3->physical_alive,
        g3->physical_gl_objects,
        g3->physical_creates,
        g3->physical_reuses,
        g3->physical_destroys,
        g3->physical_read_binds,
        g3->physical_write_binds,
        g3->physical_failures,
        g3->physical_bytes,
        g3->framebuffer_binds,
        g3->framebuffer_checks,
        g3->framebuffer_failures,
        g3->framebuffer_external_passes,
        g3->framebuffer_color_attachments,
        g3->framebuffer_depth_attachments,
        g3->target_plan_failures,
        g3->sampled_passes,
        g3->sampled_draws,
        g3->sampled_input_binds,
        g3->sampled_failures,
        g3->sampled_max_inputs,
        g3->material_packets,
        g3->material_lit_packets,
        g3->material_vertices,
        g3->last_material_flags,
        commands->count,
        commands->content_hash,
        commands->overflow_count,
        gpu->alive_count,
        gpu->high_water_count,
        gpu->stale_resolves,
        xz_runtime.command_encode_failures);

    xz_runtime.last_log_seconds = now_seconds;
}

void XzAndroidRuntime_Init(size_t engine_heap_bytes)
{
    uint64_t soft_bytes;
    uint64_t hard_bytes;
    char api[PROP_VALUE_MAX];
    char gles[PROP_VALUE_MAX];

    memset(&xz_runtime, 0, sizeof(xz_runtime));

    xz_runtime.cpu_cores = SDL_GetCPUCount();
    xz_runtime.system_ram_mb = SDL_GetSystemRAM();
    xz_runtime.engine_heap_bytes = engine_heap_bytes;

    XzDetectDisplay();

    XzReadProperty(
        "ro.board.platform",
        xz_runtime.board_platform,
        sizeof(xz_runtime.board_platform));
    XzReadProperty(
        "ro.hardware.egl",
        xz_runtime.egl_driver,
        sizeof(xz_runtime.egl_driver));
    XzReadProperty(
        "ro.hardware.vulkan",
        xz_runtime.vulkan_driver,
        sizeof(xz_runtime.vulkan_driver));
    XzReadProperty(
        "ro.product.model",
        xz_runtime.device_model,
        sizeof(xz_runtime.device_model));
    XzReadProperty("ro.build.version.sdk", api, sizeof(api));
    XzReadProperty("ro.opengles.version", gles, sizeof(gles));
    xz_runtime.android_api = api[0] ? atoi(api) : 0;
    xz_runtime.packed_gles_version = gles[0] ? atoi(gles) : 0;

    XzDeviceCaps_Init(&xz_runtime.caps);
    XzDeviceCaps_SetPlatform(
        &xz_runtime.caps,
        xz_runtime.cpu_cores,
        xz_runtime.system_ram_mb,
        xz_runtime.refresh_hz,
        xz_runtime.android_api,
        xz_runtime.packed_gles_version,
        xz_runtime.vulkan_driver[0] != '\0');
    XzDetectRuntimeGlCaps();

    XzFrameMetrics_Init(&xz_runtime.frame);
    XzChooseMemoryBudget(
        xz_runtime.system_ram_mb, &soft_bytes, &hard_bytes);
    XzMemoryBudget_Init(&xz_runtime.memory, soft_bytes, hard_bytes);

    /*
     * Phase 15 activates the governor for the modern shadow path. Legacy GL4ES
     * remains the visible renderer until Phase 16, but Xz render scale, scene
     * budgets and asset residency now follow measured recommendations.
     */
    XzPerformanceGovernor_Init(
        &xz_runtime.governor, 1000.0 / 60.0, 0);

    XzActiveQuality_Init(
        &xz_runtime.active_quality,
        xz_runtime.display_width > 0
            ? (unsigned int)xz_runtime.display_width
            : 1280u,
        xz_runtime.display_height > 0
            ? (unsigned int)xz_runtime.display_height
            : 720u);

    XzStreamResidency_Init(
        &xz_runtime.stream_residency);

    XzCutover_Init(
        &xz_runtime.cutover);
    XzCutover_RequestMode(
        &xz_runtime.cutover,
        XZ_CUTOVER_MODE_MODERN);

    XzGpuResourcePool_Init(
        &xz_runtime.gpu_resources);

    XzMapRuntime_Init(&xz_runtime.map_runtime);
    XzPackageBoot_Init(&xz_runtime.package_boot);
    XzZoneDb_Init(&xz_runtime.zone_db);
    XzRuntimeReadiness_Init(&xz_runtime.runtime_readiness);
    XzAssetPool_Init(&xz_runtime.asset_pools);
    XzBulkStore_Init(&xz_runtime.bulk_store);
    XzAssetLoaderRegistry_Init(&xz_runtime.asset_loaders);
    XzStaticSceneRuntime_Init(&xz_runtime.static_scene);

    xz_runtime.initialized = 1;

    XzAndroidLog(
        ANDROID_LOG_INFO,
        "phase0 init passive=0 selftest=%s model='%s' board='%s'"
        " egl='%s' vk='%s' sdk=%d cores=%d ram=%dMiB refresh=%dHz"
        " engine_heap=%.1fMiB mem_soft=%.1fMiB mem_hard=%.1fMiB",
        XzPhase0_SelfTest() ? "PASS" : "FAIL",
        xz_runtime.device_model[0] ? xz_runtime.device_model : "unknown",
        xz_runtime.board_platform[0] ? xz_runtime.board_platform : "unknown",
        xz_runtime.egl_driver[0] ? xz_runtime.egl_driver : "unknown",
        xz_runtime.vulkan_driver[0] ? xz_runtime.vulkan_driver : "unknown",
        xz_runtime.android_api,
        xz_runtime.cpu_cores,
        xz_runtime.system_ram_mb,
        xz_runtime.refresh_hz,
        (double)xz_runtime.engine_heap_bytes / (double)XZ_MIB,
        (double)soft_bytes / (double)XZ_MIB,
        (double)hard_bytes / (double)XZ_MIB);

    XzAndroidLog(
        ANDROID_LOG_INFO,
        "phase2 caps selftest=%s tier=%s platform_gles=%d.%d runtime_gl=%d.%d"
        " vulkan_hint=%d allow(gles3=%d vk=%d gpuDriven=%d temporal=%d highHz=%d rt=%d)"
        " ext(vao=%d discard=%d halfFloat=%d timer=%d)",
        XzDeviceCaps_SelfTest() ? "PASS" : "FAIL",
        XzDeviceTier_Name(xz_runtime.caps.tier),
        xz_runtime.caps.platform_gles_major,
        xz_runtime.caps.platform_gles_minor,
        xz_runtime.caps.runtime_gl_major,
        xz_runtime.caps.runtime_gl_minor,
        xz_runtime.caps.vulkan_hint,
        xz_runtime.caps.allow_gles3,
        xz_runtime.caps.allow_vulkan,
        xz_runtime.caps.allow_gpu_driven,
        xz_runtime.caps.allow_temporal_upscale,
        xz_runtime.caps.allow_high_refresh,
        xz_runtime.caps.allow_ray_query,
        xz_runtime.caps.has_vao,
        xz_runtime.caps.has_discard_framebuffer,
        xz_runtime.caps.has_half_float_color,
        xz_runtime.caps.has_timer_query);

    XzRhi_Init(
        &xz_runtime.rhi,
        XZ_RHI_BACKEND_GLES3,
        &xz_runtime.caps,
        1);

    XzAndroidLog(
        ANDROID_LOG_INFO,
        "phase3 renderplan=%s rhi=%s requested=%s active=%s shadow=%d",
        XzRenderPlan_SelfTest() ? "PASS" : "FAIL",
        XzRhi_SelfTest() ? "PASS" : "FAIL",
        XzRhiBackend_Name(xz_runtime.rhi.requested_backend),
        XzRhiBackend_Name(xz_runtime.rhi.active_backend),
        xz_runtime.rhi.shadow_mode);

    XzGles3Probe_InitResult(&xz_runtime.gles3_probe);
    if (xz_runtime.caps.allow_gles3) {
        int probe_ok =
            XzGles3Probe_Run(&xz_runtime.gles3_probe);
        XzAndroidLog(
            probe_ok ? ANDROID_LOG_INFO : ANDROID_LOG_WARN,
            "phase4 gles3_probe=%s status=%s egl=%d.%d gl=%d.%d"
            " shader_compile=%d shader_link=%d restore=%d err=0x%x"
            " vendor='%s' renderer='%s' version='%s'",
            probe_ok ? "PASS" : "FAIL",
            XzGles3ProbeStatus_Name(
                xz_runtime.gles3_probe.status),
            xz_runtime.gles3_probe.egl_major,
            xz_runtime.gles3_probe.egl_minor,
            xz_runtime.gles3_probe.gl_major,
            xz_runtime.gles3_probe.gl_minor,
            xz_runtime.gles3_probe.shader_compile_ok,
            xz_runtime.gles3_probe.shader_link_ok,
            xz_runtime.gles3_probe.restore_ok,
            xz_runtime.gles3_probe.gl_error,
            xz_runtime.gles3_probe.vendor,
            xz_runtime.gles3_probe.renderer,
            xz_runtime.gles3_probe.version);
    } else {
        XzAndroidLog(
            ANDROID_LOG_INFO,
            "phase4 gles3_probe=SKIP status=UNAVAILABLE restore=1");
    }

    {
        int graph_ok = XzBuildBootstrapRenderGraph();
        const XzRenderGraphCompiled *compiled =
            &xz_runtime.render_graph_compiled;
        int resources_ok = 0;

        XzAndroidLog(
            graph_ok ? ANDROID_LOG_INFO : ANDROID_LOG_WARN,
            "phase5 rendergraph selftest=%s compile=%s error=%s"
            " resources=%u passes=%u alias=%u peak=%u tile=%u"
            " memoryless=%u fusion_groups=%u fused=%u size=%dx%d",
            XzRenderGraph_SelfTest() ? "PASS" : "FAIL",
            graph_ok ? "PASS" : "FAIL",
            XzRgError_Name(compiled->error),
            compiled->resource_count,
            compiled->pass_count,
            compiled->alias_slot_count,
            compiled->peak_live_transient_slots,
            compiled->tile_local_resource_count,
            compiled->memoryless_resource_count,
            compiled->fusion_group_count,
            compiled->fused_pass_count,
            xz_runtime.display_width,
            xz_runtime.display_height);

        if (graph_ok)
            resources_ok =
                XzInitGraphResourceHandles();

        XzAndroidLog(
            resources_ok ? ANDROID_LOG_INFO : ANDROID_LOG_WARN,
            "phase8 resource_cmd resources_selftest=%s commands_selftest=%s"
            " init=%s alive=%u high=%u",
            XzGpuResourcePool_SelfTest() ? "PASS" : "FAIL",
            XzCommandStream_SelfTest() ? "PASS" : "FAIL",
            resources_ok ? "PASS" : "FAIL",
            xz_runtime.gpu_resources.alive_count,
            xz_runtime.gpu_resources.high_water_count);
    }

    XzGles3Shadow_InitState(&xz_runtime.gles3_shadow);
    if (xz_runtime.caps.allow_gles3 &&
        xz_runtime.gles3_probe.status ==
            XZ_GLES3_PROBE_SHADER_OK) {
        int shadow_ok = XzGles3Shadow_Init(
            &xz_runtime.gles3_shadow,
            8u);

        XzAndroidLog(
            shadow_ok ? ANDROID_LOG_INFO : ANDROID_LOG_WARN,
            "phase6 gles3shadow init=%s available=%d shader=%d"
            " restore=%d stride=%u",
            shadow_ok ? "PASS" : "FAIL",
            xz_runtime.gles3_shadow.available,
            xz_runtime.gles3_shadow.shader_ok,
            xz_runtime.gles3_shadow.restore_ok,
            xz_runtime.gles3_shadow.submit_stride);

        if (shadow_ok) {
            XzRhiMirrorDriver mirror;
            int attach_ok;

            memset(&mirror, 0, sizeof(mirror));
            mirror.user = &xz_runtime.gles3_shadow;
            mirror.begin_frame = XzGles3MirrorBegin;
            mirror.submit_plan = XzGles3MirrorSubmit;
            mirror.end_frame = XzGles3MirrorEnd;
            mirror.shutdown = XzGles3MirrorShutdown;

            attach_ok = XzRhi_AttachMirror(
                &xz_runtime.rhi,
                XZ_RHI_BACKEND_GLES3,
                &mirror);

            XzAndroidLog(
                attach_ok ? ANDROID_LOG_INFO : ANDROID_LOG_WARN,
                "phase7 rhi_mirror attach=%s backend=%s",
                attach_ok ? "PASS" : "FAIL",
                XzRhiBackend_Name(
                    xz_runtime.rhi.mirror_backend));

            XzAndroidLog(
                (attach_ok &&
                 xz_runtime.graph_resources_ready)
                    ? ANDROID_LOG_INFO
                    : ANDROID_LOG_WARN,
                "phase9 command_executor init=%s submit=COMMAND_STREAM"
                " backend=%s resources=%d",
                (attach_ok &&
                 xz_runtime.graph_resources_ready)
                    ? "PASS" : "FAIL",
                XzRhiBackend_Name(
                    xz_runtime.rhi.mirror_backend),
                xz_runtime.graph_resources_ready);

            XzAndroidLog(
                XzGles3ResourcePlan_SelfTest()
                    ? ANDROID_LOG_INFO
                    : ANDROID_LOG_WARN,
                "phase10 gles3_resources planner=%s proxyMax=%u",
                XzGles3ResourcePlan_SelfTest()
                    ? "PASS" : "FAIL",
                128u);

            XzAndroidLog(
                XzPassTargetPlan_SelfTest()
                    ? ANDROID_LOG_INFO
                    : ANDROID_LOG_WARN,
                "phase11 pass_targets planner=%s",
                XzPassTargetPlan_SelfTest()
                    ? "PASS" : "FAIL");

            XzAndroidLog(
                XzPassInputPlan_SelfTest()
                    ? ANDROID_LOG_INFO
                    : ANDROID_LOG_WARN,
                "phase12 pass_inputs planner=%s sampledDepth=TEXTURE",
                XzPassInputPlan_SelfTest()
                    ? "PASS" : "FAIL");

            XzAndroidLog(
                XzVisibility_SelfTest()
                    ? ANDROID_LOG_INFO
                    : ANDROID_LOG_WARN,
                "phase13 visibility selftest=%s source=VRIL_PVS camera=VPN_FOV"
                " conservative=1",
                XzVisibility_SelfTest()
                    ? "PASS" : "FAIL");

            XzAndroidLog(
                XzMaterialLighting_SelfTest()
                    ? ANDROID_LOG_INFO
                    : ANDROID_LOG_WARN,
                "phase14 materials_lighting selftest=%s source=VRIL"
                " modes=COLOR/TEXTURE/GLOW/SOLID/ADDITIVE/LMPOINT lights=DLIGHT",
                XzMaterialLighting_SelfTest()
                    ? "PASS" : "FAIL");

            XzAndroidLog(
                (XzActiveQuality_SelfTest() &&
                 XzStreamResidency_SelfTest())
                    ? ANDROID_LOG_INFO
                    : ANDROID_LOG_WARN,
                "phase15 active_scaling=%s residency=%s governor=ACTIVE"
                " initialScale=%.2f size=%ux%u",
                XzActiveQuality_SelfTest()
                    ? "PASS" : "FAIL",
                XzStreamResidency_SelfTest()
                    ? "PASS" : "FAIL",
                xz_runtime.active_quality.applied_render_scale,
                xz_runtime.active_quality.width,
                xz_runtime.active_quality.height);

            XzAndroidLog(
                XzCutover_SelfTest()
                    ? ANDROID_LOG_INFO
                    : ANDROID_LOG_WARN,
                "phase16 cutover selftest=%s requested=MODERN safety=STRICT"
                " geometry=REAL textures=RGBA_TAP visible=GLES3_PREHUD_GL4ES_UI",
                XzCutover_SelfTest()
                    ? "PASS" : "FAIL");

            if (!attach_ok)
                XzGles3Shadow_Shutdown(
                    &xz_runtime.gles3_shadow);
        }
    } else {
        XzAndroidLog(
            ANDROID_LOG_INFO,
            "phase6 gles3shadow init=SKIP available=0 shader=0"
            " restore=1 stride=0");
    }
}

void XzAndroidRuntime_SetVerifiedMapPackageMode(int enabled)
{
    int preflight_ok = 1;

    if (!xz_runtime.initialized)
        return;

    XzPackageBoot_Init(&xz_runtime.package_boot);

    if (enabled) {
        preflight_ok =
            XzPackageBoot_LoadAndPreflightVfs(
                &xz_runtime.package_boot,
                ".xziel-boot.plan");

        XzAndroidLog(
            preflight_ok ? ANDROID_LOG_INFO : ANDROID_LOG_ERROR,
            "package boot preflight ready=%d plan=%d"
            " familiesVisible=%u/%u artifactsVisible=%u/%u"
            " missing=%u failedMask=0x%08x error='%s'",
            XzPackageBoot_IsReady(&xz_runtime.package_boot),
            xz_runtime.package_boot.plan_present,
            (unsigned int)__builtin_popcount(
                xz_runtime.package_boot.visible_family_mask),
            XZ_PACKAGE_BOOT_FAMILY_COUNT,
            xz_runtime.package_boot.visible_artifacts,
            xz_runtime.package_boot.declared_artifacts,
            xz_runtime.package_boot.missing_artifacts,
            xz_runtime.package_boot.failed_family_mask,
            xz_runtime.package_boot.error);

        XzAndroidLog(
            XzPackageBoot_SelfTest()
                ? ANDROID_LOG_INFO
                : ANDROID_LOG_WARN,
            "package boot selftest=%s contractFamilies=%u",
            XzPackageBoot_SelfTest() ? "PASS" : "FAIL",
            XZ_PACKAGE_BOOT_FAMILY_COUNT);
    }

    /*
     * A package is promoted only after both the installer verification and
     * the mounted VFS preflight succeed. This mirrors BO3's zone/database
     * principle: resolve the complete declared asset set before activating
     * the runtime map.
     */
    XzRuntimeReadiness_SetGate(
        &xz_runtime.runtime_readiness,
        XZ_GATE_PACKAGE_VISIBLE,
        enabled && preflight_ok,
        enabled && !preflight_ok);

    XzMapRuntime_SetVerifiedPackageMode(
        &xz_runtime.map_runtime,
        enabled && preflight_ok);

    XzAndroidLog(
        (enabled && !preflight_ok)
            ? ANDROID_LOG_ERROR
            : ANDROID_LOG_INFO,
        "map package promotion requested=%d verified=%d kind=%s map='%s'",
        enabled ? 1 : 0,
        XzMapRuntime_IsVerifiedPackage(&xz_runtime.map_runtime),
        XzMapRuntime_KindName(
            XzMapRuntime_Kind(&xz_runtime.map_runtime)),
        XzMapRuntime_MapId(&xz_runtime.map_runtime));

    XzAndroidLog(
        ANDROID_LOG_INFO,
        "runtime readiness matchReady=%d roundStartAllowed=%d"
        " readyMask=0x%08x failedMask=0x%08x requiredMask=0x%08x",
        XzRuntimeReadiness_MatchReady(
            &xz_runtime.runtime_readiness),
        xz_runtime.runtime_readiness.round_start_allowed,
        xz_runtime.runtime_readiness.ready_mask,
        xz_runtime.runtime_readiness.failed_mask,
        xz_runtime.runtime_readiness.required_mask);

    XzAndroidLog(
        ANDROID_LOG_INFO,
        "asset database poolsReady=%d poolCapacity=%u poolUsed=%u"
        " bulkReady=%d bulkPackages=%u bulkEntries=%u"
        " loaderRegistryReady=%d loaders=%u fixups=%u"
        " missingLoaders=%u missingFixups=%u",
        XzAssetPool_IsReady(&xz_runtime.asset_pools),
        xz_runtime.asset_pools.total_capacity,
        xz_runtime.asset_pools.total_used,
        XzBulkStore_IsReady(&xz_runtime.bulk_store),
        xz_runtime.bulk_store.package_count,
        xz_runtime.bulk_store.entry_count,
        XzAssetLoaderRegistry_IsReady(
            &xz_runtime.asset_loaders),
        xz_runtime.asset_loaders.registered_loaders,
        xz_runtime.asset_loaders.registered_fixups,
        xz_runtime.asset_loaders.missing_loaders,
        xz_runtime.asset_loaders.missing_fixups);
}

void XzAndroidRuntime_BeginFrame(double now_seconds)
{
    if (!xz_runtime.initialized)
        return;

    memset(
        xz_runtime.legacy_draws_suppressed_frame,
        0,
        sizeof(xz_runtime.legacy_draws_suppressed_frame));
    memset(
        xz_runtime.legacy_draws_passthrough_frame,
        0,
        sizeof(xz_runtime.legacy_draws_passthrough_frame));

    XzFrameMetrics_Begin(&xz_runtime.frame, now_seconds);
}

void XzAndroidRuntime_NotifyWorldTransition(void)
{
    XzAndroidRuntime_NotifyWorldTransitionNamed(NULL);
}

void XzAndroidRuntime_NotifyWorldTransitionNamed(
    const char *world_model_name)
{
    if (!xz_runtime.initialized)
        return;

    xz_runtime.legacy_world_suppression_armed = 0;
    xz_runtime.legacy_world_transitions++;

    XzMapRuntime_SetWorldModel(
        &xz_runtime.map_runtime,
        world_model_name);

    XzGles3Shadow_ReleaseStaticScene(
        &xz_runtime.gles3_shadow);

    {
        XzStaticSceneStatus static_status =
            XzStaticSceneRuntime_LoadMap(
                &xz_runtime.static_scene,
                XzMapRuntime_MapId(
                    &xz_runtime.map_runtime));
        const XzXzsceneView *static_scene =
            XzStaticSceneRuntime_Scene(
                &xz_runtime.static_scene);
        const XzEnvironmentView *environment =
            XzStaticSceneRuntime_Environment(
                &xz_runtime.static_scene);
        int static_gpu_ready = 0;

        if (static_status ==
                XZ_STATIC_SCENE_READY) {
            static_gpu_ready =
                XzGles3Shadow_UploadStaticScene(
                    &xz_runtime.gles3_shadow,
                    &xz_runtime.static_scene);
        }

        XzAndroidLog(
            static_status == XZ_STATIC_SCENE_INVALID
                ? ANDROID_LOG_WARN
                : ANDROID_LOG_INFO,
            "static_scene status=%s map='%s' scene='%s'"
            " meshes=%u instances=%u xzms=%u"
            " vertices=%" PRIu64 " indices=%" PRIu64
            " submeshes=%" PRIu64
            " meshBytes=%" PRIu64 " sceneBytes=%zu"
            " gpuReady=%d gpuMeshes=%u"
            " gpuVertices=%" PRIu64
            " gpuIndices=%" PRIu64
            " gpuBytes=%" PRIu64
            " materialReady=%d gpuTextures=%u"
            " gpuTextureBytes=%" PRIu64
            " materialBindings=%u mappedBindings=%u"
            " normalBindings=%u normalMapped=%u"
            " normalTextures=%u normalBytes=%zu normalGpuReady=%d"
            " pbrBindings=%u pbrBytes=%zu"
            " pbrGpuReady=%d pbrAuthored=%u"
            " specularReady=%d"
            " envLights=%u envPoint=%u envSpot=%u"
            " envDirectional=%u envSky=%u envBytes=%zu"
            " localLights=%u localActive=%u"
            " localCameraAffecting=%u localDropped=%u"
            " localReady=%d"
            " heightFogReady=%d directionalFog=%d"
            " fogDensity=%.6f fogFalloff=%.6f"
            " fogMaxOpacity=%.6f fogStartMeters=%.6f"
            " fogBytes=%zu"
            " error='%s'",
            XzStaticSceneRuntime_StatusName(
                static_status),
            XzMapRuntime_MapId(
                &xz_runtime.map_runtime),
            xz_runtime.static_scene.scene_path,
            static_scene
                ? static_scene->mesh_count
                : 0u,
            static_scene
                ? static_scene->instance_count
                : 0u,
            xz_runtime.static_scene.mesh_files_validated,
            xz_runtime.static_scene.vertex_count,
            xz_runtime.static_scene.index_count,
            xz_runtime.static_scene.submesh_count,
            xz_runtime.static_scene.mesh_bytes_validated,
            xz_runtime.static_scene.scene_bytes,
            static_gpu_ready,
            xz_runtime.gles3_shadow.static_scene_gpu_meshes,
            xz_runtime.gles3_shadow.static_scene_gpu_vertices,
            xz_runtime.gles3_shadow.static_scene_gpu_indices,
            xz_runtime.gles3_shadow.static_scene_gpu_bytes,
            xz_runtime.gles3_shadow.static_scene_material_ready,
            xz_runtime.gles3_shadow.static_scene_gpu_textures,
            xz_runtime.gles3_shadow.static_scene_gpu_texture_bytes,
            xz_runtime.gles3_shadow.static_scene_material_bindings,
            xz_runtime.gles3_shadow.static_scene_material_mapped_bindings,
            xz_runtime.gles3_shadow.static_scene_normal_bindings,
            xz_runtime.gles3_shadow.static_scene_normal_mapped_bindings,
            xz_runtime.gles3_shadow.static_scene_gpu_normal_textures,
            xz_runtime.static_scene.normal_material_bytes,
            xz_runtime.gles3_shadow.static_scene_normal_ready,
            xz_runtime.static_scene.pbr_material_data
                ? xz_runtime.static_scene.pbr_material.binding_count
                : 0u,
            xz_runtime.static_scene.pbr_material_bytes,
            xz_runtime.gles3_shadow.static_scene_pbr_ready,
            xz_runtime.gles3_shadow.static_scene_pbr_authored_bindings,
            xz_runtime.gles3_shadow.static_scene_specular_response_ready,
            environment
                ? environment->light_count
                : 0u,
            environment
                ? environment->point_count
                : 0u,
            environment
                ? environment->spot_count
                : 0u,
            environment
                ? environment->directional_count
                : 0u,
            environment
                ? environment->sky_count
                : 0u,
            xz_runtime.static_scene.environment_bytes,
            xz_runtime.gles3_shadow.static_scene_local_light_count,
            xz_runtime.gles3_shadow.static_scene_local_light_active,
            xz_runtime.gles3_shadow.static_scene_local_light_camera_affecting,
            xz_runtime.gles3_shadow.static_scene_local_light_dropped_affecting,
            xz_runtime.gles3_shadow.static_scene_local_lighting_ready,
            xz_runtime.gles3_shadow.static_scene_height_fog_ready,
            xz_runtime.gles3_shadow.static_scene_directional_fog_enabled,
            xz_runtime.gles3_shadow.static_scene_fog_density,
            xz_runtime.gles3_shadow.static_scene_fog_height_falloff,
            xz_runtime.gles3_shadow.static_scene_fog_max_opacity,
            xz_runtime.gles3_shadow.static_scene_fog_start_meters,
            xz_runtime.static_scene.height_fog_bytes,
            xz_runtime.static_scene.error);

        XzAndroidLog(
            ANDROID_LOG_INFO,
            "static_scene_reflection map='%s'"
            " ready=%d iblReady=%d sphereReady=%d"
            " size=%u mips=%u"
            " assetBytes=%zu gpuBytes=%" PRIu64
            " averageBrightness=%.8f brightness=%.6f"
            " positionMeters=(%.8f,%.8f,%.8f)"
            " radiusMeters=%.6f"
            " offsetMeters=(%.6f,%.6f,%.6f)",
            XzMapRuntime_MapId(
                &xz_runtime.map_runtime),
            xz_runtime.gles3_shadow.static_scene_reflection_ready,
            xz_runtime.gles3_shadow.static_scene_reflection_ibl_ready,
            xz_runtime.gles3_shadow.static_scene_reflection_sphere_ready,
            xz_runtime.gles3_shadow.static_scene_reflection_size,
            xz_runtime.gles3_shadow.static_scene_reflection_mips,
            xz_runtime.static_scene.reflection_bytes,
            xz_runtime.gles3_shadow.static_scene_reflection_gpu_bytes,
            xz_runtime.gles3_shadow.static_scene_reflection_average_brightness,
            xz_runtime.gles3_shadow.static_scene_reflection_brightness,
            xz_runtime.gles3_shadow.static_scene_reflection_position_meters[0],
            xz_runtime.gles3_shadow.static_scene_reflection_position_meters[1],
            xz_runtime.gles3_shadow.static_scene_reflection_position_meters[2],
            xz_runtime.gles3_shadow.static_scene_reflection_radius_meters,
            xz_runtime.gles3_shadow.static_scene_reflection_offset_meters[0],
            xz_runtime.gles3_shadow.static_scene_reflection_offset_meters[1],
            xz_runtime.gles3_shadow.static_scene_reflection_offset_meters[2]);

        XzAndroidLog(
            ANDROID_LOG_INFO,
            "static_scene_lightmaps map='%s'"
            " ready=%d textures=%u mips=%u"
            " tableBytes=%zu payloadBytes=%u fileBytes=%u"
            " bc1=%u bc3=%u srgb=%u linear=%u",
            XzMapRuntime_MapId(
                &xz_runtime.map_runtime),
            xz_runtime.static_scene.lightmaps.file_open,
            xz_runtime.static_scene.lightmaps.texture_count,
            xz_runtime.static_scene.lightmaps.mip_count,
            xz_runtime.static_scene.lightmaps.table_bytes,
            xz_runtime.static_scene.lightmaps.payload_bytes,
            xz_runtime.static_scene.lightmaps.file_bytes,
            xz_runtime.static_scene.lightmaps.bc1_texture_count,
            xz_runtime.static_scene.lightmaps.bc3_texture_count,
            xz_runtime.static_scene.lightmaps.srgb_texture_count,
            xz_runtime.static_scene.lightmaps.linear_texture_count);

        XzAndroidLog(
            ANDROID_LOG_INFO,
            "static_scene_lightmap_bindings map='%s'"
            " ready=%d instances=%u mapped=%u missing=%u"
            " runtimeReady=%u textures=%u bytes=%zu"
            " uv0=%u uv1=%u uv2=%u uv3=%u",
            XzMapRuntime_MapId(
                &xz_runtime.map_runtime),
            xz_runtime.static_scene.lightmap_bindings.data != NULL,
            xz_runtime.static_scene.lightmap_bindings.instance_count,
            xz_runtime.static_scene.lightmap_bindings.mapped_count,
            xz_runtime.static_scene.lightmap_bindings.missing_count,
            xz_runtime.static_scene.lightmap_bindings.runtime_ready_count,
            xz_runtime.static_scene.lightmap_bindings.texture_count,
            xz_runtime.static_scene.lightmap_bindings.bytes,
            xz_runtime.static_scene.lightmap_bindings.uv_channel_count[0],
            xz_runtime.static_scene.lightmap_bindings.uv_channel_count[1],
            xz_runtime.static_scene.lightmap_bindings.uv_channel_count[2],
            xz_runtime.static_scene.lightmap_bindings.uv_channel_count[3]);

        XzAndroidLog(
            ANDROID_LOG_INFO,
            "static_scene_multi_uv map='%s'"
            " ready=%d meshes=%u"
            " uv01Loc=1 normalLoc=2 uv23Loc=3 tangentLoc=4 modelLoc=5",
            XzMapRuntime_MapId(
                &xz_runtime.map_runtime),
            xz_runtime.gles3_shadow.static_scene_multi_uv_ready,
            xz_runtime.gles3_shadow.static_scene_gpu_multi_uv_meshes);

        XzAndroidLog(
            ANDROID_LOG_INFO,
            "static_scene_lightmap_batches map='%s'"
            " ready=%d batches=%u mappedBatches=%u missingBatches=%u"
            " mappedInstances=10787 missingInstances=4",
            XzMapRuntime_MapId(
                &xz_runtime.map_runtime),
            xz_runtime.gles3_shadow.static_scene_lightmap_batch_ready,
            xz_runtime.gles3_shadow.static_scene_lightmap_batch_count,
            xz_runtime.gles3_shadow.static_scene_lightmap_mapped_batches,
            xz_runtime.gles3_shadow.static_scene_lightmap_missing_batches);

        XzAndroidLog(
            ANDROID_LOG_INFO,
            "static_scene_baked_lightmaps map='%s'"
            " ready=%d textures=%u gpuBytes=%" PRIu64
            " batches=%u mappedBatches=%u"
            " uploadMode=bc3_rgba8_authored_mip512"
            " uploadStage=%u textureIndex=%u mip=%u"
            " size=%ux%u glError=0x%x"
            " reason=%u readStatus=%u mipBytes=%u decodedBytes=%" PRIu64,
            XzMapRuntime_MapId(
                &xz_runtime.map_runtime),
            xz_runtime.gles3_shadow.static_scene_lightmap_shader_ready,
            xz_runtime.gles3_shadow.static_scene_gpu_lightmap_textures,
            xz_runtime.gles3_shadow.static_scene_gpu_lightmap_bytes,
            xz_runtime.gles3_shadow.static_scene_lightmap_batch_count,
            xz_runtime.gles3_shadow.static_scene_lightmap_mapped_batches,
            xz_runtime.gles3_shadow.static_scene_lightmap_upload_stage,
            xz_runtime.gles3_shadow.static_scene_lightmap_upload_texture_index,
            xz_runtime.gles3_shadow.static_scene_lightmap_upload_mip,
            xz_runtime.gles3_shadow.static_scene_lightmap_upload_width,
            xz_runtime.gles3_shadow.static_scene_lightmap_upload_height,
            xz_runtime.gles3_shadow.static_scene_lightmap_upload_gl_error,
            xz_runtime.gles3_shadow.static_scene_lightmap_upload_reason,
            xz_runtime.gles3_shadow.static_scene_lightmap_upload_read_status,
            xz_runtime.gles3_shadow.static_scene_lightmap_upload_mip_bytes,
            xz_runtime.gles3_shadow.static_scene_lightmap_upload_decoded_bytes);

        XzAndroidLog(
            ANDROID_LOG_INFO,
            "static_scene_tonemap map='%s'"
            " ready=%d tonemapMode=pavlov_legacy"
            " autoExposure=%d tonemapperFilm=%d"
            " contrast=%.6f dynamicRange=%.6f"
            " toeAmount=%.6f healAmount=%.6f"
            " exposure=%.6f exposureMode=fixed",
            XzMapRuntime_MapId(
                &xz_runtime.map_runtime),
            xz_runtime.gles3_shadow.static_scene_tonemap_ready,
            xz_runtime.gles3_shadow.static_scene_auto_exposure_enabled,
            xz_runtime.gles3_shadow.static_scene_tonemapper_film_enabled,
            xz_runtime.gles3_shadow.static_scene_legacy_film_contrast,
            xz_runtime.gles3_shadow.static_scene_legacy_film_dynamic_range,
            xz_runtime.gles3_shadow.static_scene_legacy_film_toe_amount,
            xz_runtime.gles3_shadow.static_scene_legacy_film_heal_amount,
            xz_runtime.gles3_shadow.static_scene_exposure_multiplier);
    }

    XzAndroidLog(
        ANDROID_LOG_INFO,
        "legacy3d worldTransition count=%" PRIu64
        " armed=0 map='%s' mapRuntime=%s generation=%" PRIu64,
        xz_runtime.legacy_world_transitions,
        XzMapRuntime_MapId(&xz_runtime.map_runtime),
        XzMapRuntime_KindName(
            XzMapRuntime_Kind(&xz_runtime.map_runtime)),
        xz_runtime.map_runtime.generation);

    if (XzMapRuntime_Kind(&xz_runtime.map_runtime) ==
            XZ_MAP_RUNTIME_NACHT_BO3) {
        const XzNachtGameplayState *nacht =
            XzMapRuntime_NachtConst(
                &xz_runtime.map_runtime);

        XzAndroidLog(
            ANDROID_LOG_INFO,
            "nacht runtime active points=%u zones=0x%x spawns=%u"
            " purchases=%u doors=%u barricades=%u",
            nacht ? nacht->points : 0u,
            nacht ? nacht->active_zone_mask : 0u,
            nacht
                ? (unsigned int)XzNacht_ActiveSpawnCount(nacht)
                : 0u,
            (unsigned int)XZ_NACHT_PURCHASE_COUNT,
            (unsigned int)XZ_NACHT_DOOR_COUNT,
            (unsigned int)XZ_NACHT_BARRICADE_COUNT);
    }
}

int XzAndroidRuntime_ActiveMapIsVerifiedPackage(void)
{
    return xz_runtime.initialized &&
        XzMapRuntime_IsVerifiedPackage(
            &xz_runtime.map_runtime);
}

int XzAndroidRuntime_StaticSceneReady(void)
{
    return xz_runtime.initialized &&
        xz_runtime.static_scene.status ==
            XZ_STATIC_SCENE_READY &&
        XzStaticSceneRuntime_Scene(
            &xz_runtime.static_scene) != NULL;
}

int XzAndroidRuntime_ActiveMapIsNachtBo3(void)
{
    return xz_runtime.initialized &&
        XzMapRuntime_Kind(&xz_runtime.map_runtime) ==
            XZ_MAP_RUNTIME_NACHT_BO3;
}

const XzNachtGameplayState *XzAndroidRuntime_NachtState(void)
{
    if (!xz_runtime.initialized)
        return NULL;

    return XzMapRuntime_NachtConst(
        &xz_runtime.map_runtime);
}

int XzAndroidRuntime_ShouldSuppressLegacyWorldDraw(
    XzLegacyWorldDrawKind kind)
{
    const XzGeometryFrame *current;
    int suppress = 0;

    if (!xz_runtime.initialized ||
        kind < XZ_LEGACY_DRAW_ALIAS ||
        kind >= XZ_LEGACY_DRAW_COUNT)
        return 0;

    current = XzGeometryTap_GetWriteFrame();

    /*
     * Once a world has completed a clean MODERN takeover, suppression stays
     * armed across subsequent frames of that same map. R_NewMap explicitly
     * disarms it before any geometry from the next world can be submitted.
     * This removes the old early-frame legacy guard-band while preserving
     * immediate GL4ES fallback across map transitions.
     */
    if (xz_runtime.legacy_world_suppression_armed) {
        suppress =
            xz_runtime.cutover.active_mode ==
                XZ_CUTOVER_MODE_MODERN &&
            xz_runtime.gles3_shadow.visible_present_ready &&
            xz_runtime.gles3_shadow.real_scene_ready_streak >= 4u;
    } else if (kind == XZ_LEGACY_DRAW_SURFACE ||
               kind == XZ_LEGACY_DRAW_SPECIAL) {
        suppress =
            xz_runtime.cutover.active_mode ==
                XZ_CUTOVER_MODE_MODERN &&
            xz_runtime.gles3_shadow.visible_present_ready &&
            xz_runtime.gles3_shadow.real_scene_ready_streak >= 4u &&
            current &&
            current->surface_batches >= 32u &&
            current->batch_count >= 32u &&
            current->dropped_batches == 0u &&
            current->dropped_vertices == 0u &&
            current->dropped_indices == 0u;
    } else if (kind == XZ_LEGACY_DRAW_ALIAS ||
               kind == XZ_LEGACY_DRAW_SPRITE ||
               kind == XZ_LEGACY_DRAW_EFFECT ||
               kind == XZ_LEGACY_DRAW_SHADOW) {
        suppress =
            xz_runtime.cutover.active_mode ==
                XZ_CUTOVER_MODE_MODERN &&
            xz_runtime.gles3_shadow.visible_present_ready &&
            xz_runtime.gles3_shadow.real_scene_ready_streak >= 4u &&
            current &&
            current->surface_batches >= 32u &&
            current->alias_batches >= 1u &&
            current->batch_count >= 48u &&
            current->dropped_batches == 0u &&
            current->dropped_vertices == 0u &&
            current->dropped_indices == 0u;
    }

    if (suppress) {
        xz_runtime.legacy_draws_suppressed_total++;
        xz_runtime.legacy_draws_suppressed_frame[kind]++;
        return 1;
    }

    xz_runtime.legacy_draws_passthrough_total++;
    xz_runtime.legacy_draws_passthrough_frame[kind]++;
    return 0;
}

int XzAndroidRuntime_CompositeVisibleWorld(void)
{
    int presented;

    if (!xz_runtime.initialized ||
        !xz_runtime.cutover.candidate_ready ||
        !xz_runtime.gles3_shadow.real_geometry_ready ||
        !xz_runtime.gles3_shadow.real_textures_ready ||
        !xz_runtime.gles3_shadow.visible_context_ready)
        return 0;

    presented =
        XzGles3Shadow_CompositeVisibleWorld(
            &xz_runtime.gles3_shadow,
            XzGeometryTap_GetWriteFrame(),
            xz_runtime.active_quality.width,
            xz_runtime.active_quality.height);

    if (presented &&
        xz_runtime.gles3_shadow.static_scene_frame_ready &&
        xz_runtime.gles3_shadow.static_scene_draw_successes == 1u) {
        XzAndroidLog(
            ANDROID_LOG_INFO,
            "static_scene_draw ready=1 meshes=%u"
            " instances=%u drawCalls=%u"
            " attempts=%" PRIu64
            " failures=%" PRIu64
            " fboPixels=%u surfacePixels=%u"
            " postRestorePixels=%u"
            " readback=%ux%u"
            " localLights=%u active=%u affecting=%u dropped=%u"
            " normalReady=%d normalApplied=%u normalMapped=%u"
            " pbrReady=%d pbrApplied=%u pbrAuthored=%u"
            " specularReady=%d specularLocal=%u"
            " reflectionReady=%d reflectionIblReady=%d"
            " reflectionSphereReady=%d"
            " reflectionSize=%u reflectionMips=%u"
            " reflectionGpuBytes=%" PRIu64
            " heightFogReady=%d directionalFog=%d"
            " fogDensity=%.6f fogFalloff=%.6f"
            " fogMaxOpacity=%.6f fogStartMeters=%.6f"
            " lightmapReady=%d bakedLightmapDraws=%u",
            xz_runtime.gles3_shadow.static_scene_gpu_meshes,
            xz_runtime.gles3_shadow.static_scene_last_instances,
            xz_runtime.gles3_shadow.static_scene_last_draw_calls,
            xz_runtime.gles3_shadow.static_scene_draw_attempts,
            xz_runtime.gles3_shadow.static_scene_draw_failures,
            xz_runtime.gles3_shadow.static_scene_fbo_nonblack_pixels,
            xz_runtime.gles3_shadow.static_scene_surface_nonblack_pixels,
            xz_runtime.gles3_shadow.static_scene_postrestore_nonblack_pixels,
            xz_runtime.gles3_shadow.static_scene_readback_width,
            xz_runtime.gles3_shadow.static_scene_readback_height,
            xz_runtime.gles3_shadow.static_scene_local_light_count,
            xz_runtime.gles3_shadow.static_scene_local_light_active,
            xz_runtime.gles3_shadow.static_scene_local_light_camera_affecting,
            xz_runtime.gles3_shadow.static_scene_local_light_dropped_affecting,
            xz_runtime.gles3_shadow.static_scene_normal_ready,
            xz_runtime.gles3_shadow.static_scene_last_normal_bindings,
            xz_runtime.gles3_shadow.static_scene_normal_mapped_bindings,
            xz_runtime.gles3_shadow.static_scene_pbr_ready,
            xz_runtime.gles3_shadow.static_scene_last_pbr_bindings,
            xz_runtime.gles3_shadow.static_scene_pbr_authored_bindings,
            xz_runtime.gles3_shadow.static_scene_specular_response_ready,
            xz_runtime.gles3_shadow.static_scene_last_specular_local_lights,
            xz_runtime.gles3_shadow.static_scene_reflection_ready,
            xz_runtime.gles3_shadow.static_scene_reflection_ibl_ready,
            xz_runtime.gles3_shadow.static_scene_reflection_sphere_ready,
            xz_runtime.gles3_shadow.static_scene_reflection_size,
            xz_runtime.gles3_shadow.static_scene_reflection_mips,
            xz_runtime.gles3_shadow.static_scene_reflection_gpu_bytes,
            xz_runtime.gles3_shadow.static_scene_height_fog_ready,
            xz_runtime.gles3_shadow.static_scene_directional_fog_enabled,
            xz_runtime.gles3_shadow.static_scene_fog_density,
            xz_runtime.gles3_shadow.static_scene_fog_height_falloff,
            xz_runtime.gles3_shadow.static_scene_fog_max_opacity,
            xz_runtime.gles3_shadow.static_scene_fog_start_meters,
            xz_runtime.gles3_shadow.static_scene_lightmap_shader_ready,
            xz_runtime.gles3_shadow.static_scene_last_baked_lightmap_draw_calls);

        {
            unsigned int probe_index;

            for (probe_index = 0u;
                 probe_index <
                    xz_runtime.gles3_shadow.
                        static_scene_camera_probe_count;
                 ++probe_index) {
                const unsigned int mesh_index =
                    xz_runtime.gles3_shadow.
                        static_scene_camera_probe_mesh[probe_index];
                const XzStaticMeshResource *mesh =
                    XzStaticSceneRuntime_Mesh(
                        &xz_runtime.static_scene,
                        mesh_index);

                XzAndroidLog(
                    ANDROID_LOG_INFO,
                    "static_scene_camera_probe rank=%u"
                    " camera=(%.3f,%.3f,%.3f)"
                    " insideCount=%u"
                    " mesh=%u instance=%u"
                    " distance=%.3f inside=%u"
                    " boundsMin=(%.3f,%.3f,%.3f)"
                    " boundsMax=(%.3f,%.3f,%.3f)"
                    " path='%s'",
                    probe_index,
                    xz_runtime.gles3_shadow.
                        static_scene_camera_origin[0],
                    xz_runtime.gles3_shadow.
                        static_scene_camera_origin[1],
                    xz_runtime.gles3_shadow.
                        static_scene_camera_origin[2],
                    xz_runtime.gles3_shadow.
                        static_scene_camera_probe_inside_count,
                    mesh_index,
                    xz_runtime.gles3_shadow.
                        static_scene_camera_probe_instance[probe_index],
                    xz_runtime.gles3_shadow.
                        static_scene_camera_probe_distance[probe_index],
                    xz_runtime.gles3_shadow.
                        static_scene_camera_probe_inside[probe_index],
                    xz_runtime.gles3_shadow.
                        static_scene_camera_probe_bounds_min[probe_index][0],
                    xz_runtime.gles3_shadow.
                        static_scene_camera_probe_bounds_min[probe_index][1],
                    xz_runtime.gles3_shadow.
                        static_scene_camera_probe_bounds_min[probe_index][2],
                    xz_runtime.gles3_shadow.
                        static_scene_camera_probe_bounds_max[probe_index][0],
                    xz_runtime.gles3_shadow.
                        static_scene_camera_probe_bounds_max[probe_index][1],
                    xz_runtime.gles3_shadow.
                        static_scene_camera_probe_bounds_max[probe_index][2],
                    mesh ? mesh->path : "");
            }
        }
    }

    return presented;
}

void XzAndroidRuntime_AuditLegacyPresentBeforeSwap(
    unsigned int width,
    unsigned int height,
    int screenflash_color,
    int screenflash_type,
    double screenflash_duration,
    double screenflash_starttime,
    double screenflash_worktime,
    double server_time)
{
    XzGles3ShadowState *shadow;
    int screenflash_active;

    if (!xz_runtime.initialized ||
        !xz_runtime.gles3_shadow.static_scene_frame_ready)
        return;

    shadow = &xz_runtime.gles3_shadow;
    screenflash_active =
        screenflash_duration > server_time;

    if (!shadow->static_scene_preswap_intro_sampled) {
        unsigned int *rgba =
            shadow->static_scene_preswap_mean_rgba;

        if (!XzGles3Shadow_AuditCurrentFramebuffer(
                shadow,
                width,
                height,
                rgba))
            return;

        shadow->static_scene_preswap_intro_sampled = 1;

        XzAndroidLog(
            ANDROID_LOG_INFO,
            "present_luma"
            " postRestoreRGBA=%u,%u,%u,%u"
            " preSwapRGBA=%u,%u,%u,%u"
            " screenflashColor=%d"
            " screenflashType=%d"
            " screenflashDuration=%.6f"
            " screenflashStart=%.6f"
            " screenflashWork=%.6f"
            " serverTime=%.6f"
            " screenflashActive=%d",
            shadow->static_scene_postrestore_mean_rgba[0],
            shadow->static_scene_postrestore_mean_rgba[1],
            shadow->static_scene_postrestore_mean_rgba[2],
            shadow->static_scene_postrestore_mean_rgba[3],
            rgba[0],
            rgba[1],
            rgba[2],
            rgba[3],
            screenflash_color,
            screenflash_type,
            screenflash_duration,
            screenflash_starttime,
            screenflash_worktime,
            server_time,
            screenflash_active);
    }

    if (!screenflash_active &&
        !shadow->static_scene_preswap_clear_sampled) {
        unsigned int *rgba =
            shadow->static_scene_preswap_clear_mean_rgba;

        if (!XzGles3Shadow_AuditCurrentFramebuffer(
                shadow,
                width,
                height,
                rgba))
            return;

        shadow->static_scene_preswap_clear_sampled = 1;

        XzAndroidLog(
            ANDROID_LOG_INFO,
            "present_luma_clear"
            " preSwapRGBA=%u,%u,%u,%u"
            " serverTime=%.6f"
            " screenflashDuration=%.6f"
            " screenflashActive=0",
            rgba[0],
            rgba[1],
            rgba[2],
            rgba[3],
            server_time,
            screenflash_duration);
    }
}

void XzAndroidRuntime_EndFrame(double now_seconds)
{
    uint64_t rss;

    if (!xz_runtime.initialized)
        return;

    XzFrameMetrics_End(&xz_runtime.frame, now_seconds);

    if (xz_runtime.frame.total_frames -
            xz_runtime.last_memory_sample_frame >= 60u) {
        rss = XzReadProcessRssBytes();
        if (rss)
            XzMemoryBudget_Sample(&xz_runtime.memory, rss);
        xz_runtime.last_memory_sample_frame =
            xz_runtime.frame.total_frames;
    }

    XzPerformanceGovernor_Update(
        &xz_runtime.governor,
        &xz_runtime.frame,
        &xz_runtime.memory,
        -1);

    if (XzActiveQuality_Update(
            &xz_runtime.active_quality,
            &xz_runtime.governor.recommendation,
            xz_runtime.frame.total_frames,
            xz_runtime.display_width > 0
                ? (unsigned int)xz_runtime.display_width
                : 1280u,
            xz_runtime.display_height > 0
                ? (unsigned int)xz_runtime.display_height
                : 720u)) {
        XzGles3Shadow_SetQualityScale(
            &xz_runtime.gles3_shadow,
            xz_runtime.active_quality.applied_render_scale);

        if (!XzRebuildGraphResources())
            xz_runtime.graph_rebuild_failures++;
    }

    XzSceneBudget_Build(
        &xz_runtime.scene_budget,
        XzPresentWorld_GetReadFrame(),
        xz_runtime.caps.tier,
        &xz_runtime.governor.recommendation);

    XzRenderPlan_Build(
        &xz_runtime.render_plan,
        XzPresentWorld_GetReadFrame(),
        &xz_runtime.scene_budget,
        xz_runtime.caps.tier);

    XzStreamResidency_Update(
        &xz_runtime.stream_residency,
        &xz_runtime.render_plan,
        xz_runtime.caps.tier,
        &xz_runtime.governor.recommendation);

    if (xz_runtime.graph_resources_ready) {
        if (!XzCommandStream_EncodeFrame(
                &xz_runtime.command_stream,
                &xz_runtime.render_graph,
                &xz_runtime.render_graph_compiled,
                &xz_runtime.gpu_resources,
                xz_runtime.graph_resource_handles,
                &xz_runtime.render_plan))
            xz_runtime.command_encode_failures++;
    }

    XzRhi_BeginFrame(&xz_runtime.rhi);
    XzRhi_SubmitFrame(
        &xz_runtime.rhi,
        &xz_runtime.render_plan,
        &xz_runtime.command_stream,
        &xz_runtime.gpu_resources,
        XzGeometryTap_GetReadFrame());
    XzRhi_EndFrame(&xz_runtime.rhi);

    XzEvaluateCutover();

    {
        const XzGeometryFrame *completed =
            XzGeometryTap_GetReadFrame();
        const int can_arm =
            xz_runtime.cutover.active_mode ==
                XZ_CUTOVER_MODE_MODERN &&
            xz_runtime.gles3_shadow.visible_present_ready &&
            xz_runtime.gles3_shadow.real_scene_ready_streak >= 4u &&
            completed &&
            completed->surface_batches >= 32u &&
            completed->batch_count >= 32u &&
            completed->dropped_batches == 0u &&
            completed->dropped_vertices == 0u &&
            completed->dropped_indices == 0u;

        if (can_arm)
            xz_runtime.legacy_world_suppression_armed = 1;
        else if (xz_runtime.cutover.active_mode !=
                     XZ_CUTOVER_MODE_MODERN ||
                 !xz_runtime.gles3_shadow.visible_present_ready)
            xz_runtime.legacy_world_suppression_armed = 0;
    }

    if (xz_runtime.last_log_seconds == 0.0 ||
        now_seconds - xz_runtime.last_log_seconds >= 5.0)
        XzLogSnapshot(now_seconds);
}

void XzAndroidRuntime_Shutdown(void)
{
    if (!xz_runtime.initialized)
        return;

    XzLogSnapshot(xz_runtime.last_log_seconds + 5.0);
    XzRhi_Shutdown(&xz_runtime.rhi);
    XzDestroyGraphResourceHandles();
    XzStaticSceneRuntime_Shutdown(
        &xz_runtime.static_scene);
    XzTextureTap_Shutdown();
    XzAndroidLog(
        ANDROID_LOG_INFO,
        "phase0 shutdown processed_frames=%" PRIu64
        " spikes25=%" PRIu64 " spikes33=%" PRIu64
        " spikes50=%" PRIu64,
        xz_runtime.frame.total_frames,
        xz_runtime.frame.spikes_over_25ms,
        xz_runtime.frame.spikes_over_33ms,
        xz_runtime.frame.spikes_over_50ms);

    xz_runtime.initialized = 0;
}
