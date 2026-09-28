#!/usr/bin/env python3
"""Inject Xziel Phase-0 runtime telemetry into the freshly cloned Vril tree.

The Android build intentionally clones upstream Vril on every run. Xziel-owned
modules live in engine/xz/ and are copied into Vril's source root here so the
existing Android.mk wildcard compiles them without vendoring/forking Vril.

Phase 0 established telemetry and recommendations. By Phase 15 the modern
shadow renderer actively applies those recommendations to render scale,
quality budgets and asset residency while legacy GL4ES remains visible.
"""

from pathlib import Path
import re
import shutil
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_vril_xz_phase0.py <vril-root>")

vril = Path(sys.argv[1]).resolve()
source = vril / "source"
repo = Path(__file__).resolve().parents[1]
modules = repo / "engine" / "xz"

if not source.is_dir():
    raise SystemExit(f"Vril source directory not found: {source}")
if not modules.is_dir():
    raise SystemExit(f"Xz module directory not found: {modules}")

for name in (
    "xz_phase0.h",
    "xz_phase0.c",
    "xz_android_runtime.h",
    "xz_android_runtime.c",
    "xz_present_world.h",
    "xz_present_world.c",
    "xz_vril_bridge.h",
    "xz_vril_bridge.c",
    "xz_device_caps.h",
    "xz_device_caps.c",
    "xz_scene_budget.h",
    "xz_scene_budget.c",
    "xz_render_plan.h",
    "xz_render_plan.c",
    "xz_rhi.h",
    "xz_rhi.c",
    "xz_gles3_probe.h",
    "xz_gles3_probe.c",
    "xz_render_graph.h",
    "xz_render_graph.c",
    "xz_gles3_shadow.h",
    "xz_gles3_shadow.c",
    "xz_gpu_resources.h",
    "xz_gpu_resources.c",
    "xz_command_stream.h",
    "xz_command_stream.c",
    "xz_gles3_resource_plan.h",
    "xz_gles3_resource_plan.c",
    "xz_pass_targets.h",
    "xz_pass_targets.c",
    "xz_pass_inputs.h",
    "xz_pass_inputs.c",
    "xz_visibility.h",
    "xz_visibility.c",
    "xz_material_lighting.h",
    "xz_material_lighting.c",
    "xz_active_quality.h",
    "xz_active_quality.c",
    "xz_stream_residency.h",
    "xz_stream_residency.c",
    "xz_cutover.h",
    "xz_cutover.c",
    "xz_geometry_tap.h",
    "xz_geometry_tap.c",
    "xz_texture_tap.h",
    "xz_texture_tap.c",
    "xz_nacht_reference.h",
    "xz_nacht_reference.c",
    "xz_map_runtime.h",
    "xz_map_runtime.c",
    "xz_package_boot.h",
    "xz_package_boot.c",
    "xz_zone_db.h",
    "xz_zone_db.c",
    "xz_runtime_readiness.h",
    "xz_runtime_readiness.c",
    "xz_t7_asset_types.h",
    "xz_t7_asset_types.c",
    "xz_asset_pool.h",
    "xz_asset_pool.c",
    "xz_bulk_store.h",
    "xz_bulk_store.c",
    "xz_asset_loader_registry.h",
    "xz_asset_loader_registry.c",
    "xz_xzmesh.h",
    "xz_xzmesh.c",
    "xz_xzscene.h",
    "xz_xzscene.c",
    "xz_static_scene_runtime.h",
    "xz_static_scene_runtime.c",
    "xz_static_scene_draw_plan.h",
    "xz_static_scene_draw_plan.c",
    "xz_static_scene_lightmap_draw_plan.h",
    "xz_static_scene_lightmap_draw_plan.c",
    "xz_environment.h",
    "xz_environment.c",
    "xz_height_fog.h",
    "xz_height_fog.c",
    "xz_pbr_material.h",
    "xz_pbr_material.c",
    "xz_lightmap_texture.h",
    "xz_lightmap_texture.c",
    "xz_lightmap_binding.h",
    "xz_lightmap_binding.c",
    "xz_world_transform.h",
    "xz_world_transform.c",
    "xz_bo3_weapon_specs.h",
    "xz_bo3_weapon_specs.c",
):
    src = modules / name
    if not src.is_file():
        raise SystemExit(f"Missing Xz source: {src}")
    shutil.copy2(src, source / name)

sys_sdl = source / "platform" / "sdl" / "sys_sdl.c"
text = sys_sdl.read_text(encoding="utf-8")

include_anchor = '#include "sdl_local.h"\n'
include_block = (
    '#include "sdl_local.h"\n'
    '#ifdef __ANDROID__\n'
    '#include "xz_android_runtime.h"\n'
    '#include "xz_vril_bridge.h"\n'
    '#include "xz_texture_tap.h"\n'
    '#endif\n'
)
if '#include "xz_android_runtime.h"' not in text:
    if include_anchor not in text:
        raise SystemExit("Missing sys_sdl include anchor")
    text = text.replace(include_anchor, include_block, 1)

if '#include "xz_geometry_tap.h"' not in text:
    anchor = '#include "xz_vril_bridge.h"\n'
    if anchor not in text:
        raise SystemExit("Missing geometry-tap include anchor")
    text = text.replace(
        anchor,
        anchor + '#include "xz_geometry_tap.h"\n',
        1,
    )

init_anchor = '\tHost_Init(&parms);\n'
init_block = (
    '#ifdef __ANDROID__\n'
    '\t/* Capture renderer uploads performed during Host_Init. */\n'
    '\tXzTextureTap_Init();\n'
    '#endif\n'
    '\tHost_Init(&parms);\n'
    '#ifdef __ANDROID__\n'
    '\tXzAndroidRuntime_Init(heap_size);\n'
    '\tXzAndroidRuntime_SetVerifiedMapPackageMode(\n'
    '\t\tCOM_CheckParm("-xzielstrictassets") != 0);\n'
    '\tXzVrilBridge_Init();\n'
    '#endif\n'
)
if 'XzAndroidRuntime_Init(heap_size);' not in text:
    if init_anchor not in text:
        raise SystemExit("Missing Host_Init Phase-0 anchor")
    text = text.replace(init_anchor, init_block, 1)

if "XzGeometryTap_Init();" not in text:
    anchor = "\tXzVrilBridge_Init();\n"
    if anchor not in text:
        raise SystemExit("Missing geometry-tap init anchor")
    text = text.replace(
        anchor,
        anchor + "\tXzGeometryTap_Init();\n",
        1,
    )

loop_anchor = (
    '\t\tdouble now = Sys_FloatTime();\n'
    '\t\tHost_Frame(now - oldtime);\n'
    '\t\tmusic_update();\n'
    '\t\toldtime = now;\n'
)
loop_block = (
    '\t\tdouble now = Sys_FloatTime();\n'
    '#ifdef __ANDROID__\n'
    '\t\tint xz_frame_before = host_framecount;\n'
    '\t\tXzAndroidRuntime_BeginFrame(now);\n'
    '#endif\n'
    '\t\tHost_Frame(now - oldtime);\n'
    '\t\tmusic_update();\n'
    '#ifdef __ANDROID__\n'
    '\t\t/* Host_FilterTime can reject a loop iteration. Only publish a\n'
    '\t\t * metric when Vril actually processed a frame. */\n'
    '\t\tif (host_framecount != xz_frame_before) {\n'
    '\t\t\tXzVrilBridge_CapturePresentation(host_framecount);\n'
    '\t\t\tXzAndroidRuntime_EndFrame(Sys_FloatTime());\n'
    '\t\t}\n'
    '#endif\n'
    '\t\toldtime = now;\n'
)
if 'XzAndroidRuntime_BeginFrame(now);' not in text:
    if loop_anchor not in text:
        raise SystemExit("Missing SDL frame-loop Phase-0 anchor")
    text = text.replace(loop_anchor, loop_block, 1)

if "XzGeometryTap_BeginFrame" not in text:
    begin_anchor = "\t\tXzAndroidRuntime_BeginFrame(now);\n"
    if begin_anchor not in text:
        raise SystemExit("Missing geometry-tap begin anchor")
    text = text.replace(
        begin_anchor,
        begin_anchor +
        "\t\tXzGeometryTap_BeginFrame((uint64_t)(xz_frame_before + 1));\n",
        1,
    )

if "XzGeometryTap_CommitFrame();" not in text:
    commit_anchor = "\t\t\tXzVrilBridge_CapturePresentation(host_framecount);\n"
    if commit_anchor not in text:
        raise SystemExit("Missing geometry-tap commit anchor")
    text = text.replace(
        commit_anchor,
        "\t\t\tXzGeometryTap_CommitFrame();\n" + commit_anchor,
        1,
    )

first_frame_old = (
    '#ifdef __ANDROID__\n'
    '\t\tif (xziel_first_frame) {\n'
    '\t\t\tXziel_WriteStage("FIRST_FRAME_OK");\n'
    '\t\t\txziel_first_frame = 0;\n'
    '\t\t}\n'
    '#endif\n'
)
first_frame_new = (
    '#ifdef __ANDROID__\n'
    '\t\tif (xziel_first_frame && host_framecount != xz_frame_before) {\n'
    '\t\t\tXziel_WriteStage("FIRST_FRAME_OK");\n'
    '\t\t\txziel_first_frame = 0;\n'
    '\t\t}\n'
    '#endif\n'
)
if 'xziel_first_frame && host_framecount != xz_frame_before' not in text:
    if first_frame_old not in text:
        raise SystemExit("Missing FIRST_FRAME_OK hardening anchor")
    text = text.replace(first_frame_old, first_frame_new, 1)

shutdown_anchor = '\tif (host_initialized)\n\t\tHost_Shutdown();\n'
shutdown_block = (
    '#ifdef __ANDROID__\n'
    '\tXzVrilBridge_Shutdown();\n'
    '\tXzAndroidRuntime_Shutdown();\n'
    '#endif\n'
    '\tif (host_initialized)\n'
    '\t\tHost_Shutdown();\n'
)
if 'XzAndroidRuntime_Shutdown();' not in text:
    if shutdown_anchor not in text:
        raise SystemExit("Missing shutdown Phase-0 anchor")
    text = text.replace(shutdown_anchor, shutdown_block, 1)

sys_sdl.write_text(text, encoding="utf-8")


# Capture the actual SDL/GL geometry batches that legacy Vril submits. Xz uses
# these only for parity validation; the legacy GL4ES draw calls remain intact.
gl_hyena = source / "platform" / "sdl" / "gl" / "gl_hyena.c"
hyena = gl_hyena.read_text(encoding="utf-8")

if '#include "xz_geometry_tap.h"' not in hyena:
    anchor = '#include "../../../nzportable_def.h"\n'
    if anchor not in hyena:
        raise SystemExit("Missing gl_hyena include anchor")
    hyena = hyena.replace(
        anchor,
        anchor +
        '#ifdef __ANDROID__\n'
        '#include "xz_geometry_tap.h"\n'
        '#include "xz_android_runtime.h"\n'
        '#include <stddef.h>\n'
        '#include <string.h>\n'
        '#include <stdlib.h>\n'
        '#endif\n',
        1,
    )

# Snapshot the fixed-function state at the exact legacy draw boundary. This
# preserves Vril lightmap blending (DST_COLOR/SRC_COLOR + depth EQUAL), water
# alpha, sprites and cutout alpha semantics for the native GLES3 replay.
if "xz_hyena_special_kind" not in hyena:
    static_anchor = "static vec3_t hyena_scale;\n"
    if static_anchor not in hyena:
        raise SystemExit("Missing Hyena special-kind static anchor")
    hyena = hyena.replace(
        static_anchor,
        static_anchor +
        "#ifdef __ANDROID__\n"
        "static XzGeometrySpecialKind xz_hyena_special_kind = XZ_GEOMETRY_SPECIAL_NONE;\n"
        "#endif\n",
        1,
    )

state_helper = (
    '#ifdef __ANDROID__\n'
    'static void XzCaptureLegacyRenderState(XzGeometryRenderState *state)\n'
    '{\n'
    '    GLboolean depth_write = GL_TRUE;\n'
    '    GLint value = 0;\n'
    '    memset(state, 0, sizeof(*state));\n'
    '    glGetFloatv(GL_CURRENT_COLOR, state->color);\n'
    '    state->blend_enabled = glIsEnabled(GL_BLEND) ? 1u : 0u;\n'
    '    state->alpha_test_enabled = glIsEnabled(GL_ALPHA_TEST) ? 1u : 0u;\n'
    '    state->depth_test_enabled = glIsEnabled(GL_DEPTH_TEST) ? 1u : 0u;\n'
    '    glGetBooleanv(GL_DEPTH_WRITEMASK, &depth_write);\n'
    '    state->depth_write = depth_write ? 1u : 0u;\n'
    '    glGetIntegerv(GL_BLEND_SRC, &value);\n'
    '    state->blend_src = (unsigned int)value;\n'
    '    glGetIntegerv(GL_BLEND_DST, &value);\n'
    '    state->blend_dst = (unsigned int)value;\n'
    '    glGetIntegerv(GL_DEPTH_FUNC, &value);\n'
    '    state->depth_func = (unsigned int)value;\n'
    '    glGetIntegerv(GL_ALPHA_TEST_FUNC, &value);\n'
    '    state->alpha_func = (unsigned int)value;\n'
    '    glGetFloatv(GL_ALPHA_TEST_REF, &state->alpha_ref);\n'
    '    glGetTexEnviv(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, &value);\n'
    '    state->texture_env_mode = (unsigned int)value;\n'
    '    state->texture_enabled = glIsEnabled(GL_TEXTURE_2D) ? 1u : 0u;\n'
    '    state->fog_enabled = glIsEnabled(GL_FOG) ? 1u : 0u;\n'
    '    glGetFloatv(GL_FOG_START, &state->fog_start);\n'
    '    glGetFloatv(GL_FOG_END, &state->fog_end);\n'
    '    glGetFloatv(GL_FOG_COLOR, state->fog_color);\n'
    '    glGetFloatv(GL_DEPTH_RANGE, state->depth_range);\n'
    '    state->cull_enabled = glIsEnabled(GL_CULL_FACE) ? 1u : 0u;\n'
    '    glGetIntegerv(GL_CULL_FACE_MODE, &value);\n'
    '    state->cull_face = (unsigned int)value;\n'
    '    glGetIntegerv(GL_FRONT_FACE, &value);\n'
    '    state->front_face = (unsigned int)value;\n'
    '    state->polygon_offset_enabled = glIsEnabled(GL_POLYGON_OFFSET_FILL) ? 1u : 0u;\n'
    '    glGetFloatv(GL_POLYGON_OFFSET_FACTOR, &state->polygon_offset_factor);\n'
    '    glGetFloatv(GL_POLYGON_OFFSET_UNITS, &state->polygon_offset_units);\n'
    '}\n'
    '#endif\n'
)
if 'static void XzCaptureLegacyRenderState' not in hyena:
    include_end = '#endif\n'
    include_pos = hyena.find(include_end, hyena.find('#include "xz_geometry_tap.h"'))
    if include_pos < 0:
        raise SystemExit("Missing geometry state helper insertion point")
    include_pos += len(include_end)
    hyena = hyena[:include_pos] + '\n' + state_helper + hyena[include_pos:]

alias_anchor = (
    "void Hyena_DrawAliasBatch(const alias_batch_t *batch)\n"
    "{\n"
    "    if (!batch->num_indices) return;\n"
)
if "XzGeometryTap_CaptureAlias(" not in hyena:
    if alias_anchor not in hyena:
        raise SystemExit("Missing alias geometry capture anchor")
    alias_capture = alias_anchor + (
        "#ifdef __ANDROID__\n"
        "    {\n"
        "        float xz_mv[16], xz_pr[16];\n"
        "        GLint xz_tex = 0;\n"
        "        XzGeometryRenderState xz_state;\n"
        "        XzCaptureLegacyRenderState(&xz_state);\n"
        "        glGetFloatv(GL_MODELVIEW_MATRIX, xz_mv);\n"
        "        glGetFloatv(GL_PROJECTION_MATRIX, xz_pr);\n"
        "        glGetIntegerv(GL_TEXTURE_BINDING_2D, &xz_tex);\n"
        "        XzGeometryTap_CaptureAlias(\n"
        "            batch->vertices,\n"
        "            (unsigned int)batch->num_vertices,\n"
        "            (unsigned int)sizeof(alias_vertex_t),\n"
        "            (unsigned int)offsetof(alias_vertex_t, xyz),\n"
        "            (unsigned int)offsetof(alias_vertex_t, uv),\n"
        "            batch->indices,\n"
        "            (unsigned int)batch->num_indices,\n"
        "            (int)xz_tex,\n"
        "            &xz_state,\n"
        "            xz_mv,\n"
        "            xz_pr);\n"
        "    }\n"
        "    if (XzAndroidRuntime_ShouldSuppressLegacyWorldDraw(XZ_LEGACY_DRAW_ALIAS))\n"
        "        return;\n"
        "#endif\n"
    )
    hyena = hyena.replace(alias_anchor, alias_capture, 1)

# Warped surface fans flow through Hyena_DrawVertices and are captured by the
# generic effects path below; do not duplicate them here.

surface_anchor = (
    "    glEnableClientState(GL_VERTEX_ARRAY); glEnableClientState(GL_TEXTURE_COORD_ARRAY);\n"
    "    glVertexPointer(3, GL_FLOAT, stride * sizeof(float), source);\n"
)
if "XZ_GEOMETRY_SURFACE_CAPTURE" not in hyena:
    if surface_anchor not in hyena:
        raise SystemExit("Missing surface geometry capture anchor")
    surface_capture = (
        "#ifdef __ANDROID__\n"
        "    /* XZ_GEOMETRY_SURFACE_CAPTURE */\n"
        "    {\n"
        "        float xz_mv[16], xz_pr[16];\n"
        "        GLint xz_tex = 0;\n"
        "        XzGeometryRenderState xz_state;\n"
        "        XzCaptureLegacyRenderState(&xz_state);\n"
        "        glGetFloatv(GL_MODELVIEW_MATRIX, xz_mv);\n"
        "        glGetFloatv(GL_PROJECTION_MATRIX, xz_pr);\n"
        "        glGetIntegerv(GL_TEXTURE_BINDING_2D, &xz_tex);\n"
        "        XzGeometryTap_CaptureSurfaceFan(\n"
        "            source,\n"
        "            (unsigned int)count,\n"
        "            (unsigned int)stride,\n"
        "            0u,\n"
        "            (unsigned int)texture_offset,\n"
        "            (int)xz_tex,\n"
        "            &xz_state,\n"
        "            xz_mv,\n"
        "            xz_pr);\n"
        "    }\n"
        "    if (XzAndroidRuntime_ShouldSuppressLegacyWorldDraw(XZ_LEGACY_DRAW_SURFACE))\n"
        "        return;\n"
        "#endif\n"
    ) + surface_anchor
    hyena = hyena.replace(surface_anchor, surface_capture, 1)


generic_anchor = (
    "    for (i = 0; i < count; ++i) { vertices[i].xyz.x = vertices[i].xyz.x * hyena_scale[0] + hyena_translation[0]; vertices[i].xyz.y = vertices[i].xyz.y * hyena_scale[1] + hyena_translation[1]; vertices[i].xyz.z = vertices[i].xyz.z * hyena_scale[2] + hyena_translation[2]; }\n"
    "    glEnableClientState(GL_VERTEX_ARRAY); glVertexPointer(3, GL_FLOAT, sizeof(*vertices), &vertices[0].xyz);\n"
)
if "XZ_GEOMETRY_EFFECT_CAPTURE" not in hyena:
    if generic_anchor not in hyena:
        raise SystemExit("Missing generic Hyena geometry capture anchor")
    generic_capture = (
        "    for (i = 0; i < count; ++i) { vertices[i].xyz.x = vertices[i].xyz.x * hyena_scale[0] + hyena_translation[0]; vertices[i].xyz.y = vertices[i].xyz.y * hyena_scale[1] + hyena_translation[1]; vertices[i].xyz.z = vertices[i].xyz.z * hyena_scale[2] + hyena_translation[2]; }\n"
        "#ifdef __ANDROID__\n"
        "    /* XZ_GEOMETRY_EFFECT_CAPTURE: particles, decals, beams and warped fans. */\n"
        "    {\n"
        "        float xz_mv[16], xz_pr[16];\n"
        "        GLint xz_tex = 0;\n"
        "        XzGeometryRenderState xz_state;\n"
        "        XzGeometryPrimitive xz_primitive = XZ_GEOMETRY_TRIANGLE_FAN;\n"
        "        XzCaptureLegacyRenderState(&xz_state);\n"
        "        if (hyena_vertex_mode == HYE_TRIANGLES)\n"
        "            xz_primitive = XZ_GEOMETRY_TRIANGLES;\n"
        "        else if (hyena_vertex_mode == HYE_TRIANGLE_STRIP)\n"
        "            xz_primitive = XZ_GEOMETRY_TRIANGLE_STRIP;\n"
        "        glGetFloatv(GL_MODELVIEW_MATRIX, xz_mv);\n"
        "        glGetFloatv(GL_PROJECTION_MATRIX, xz_pr);\n"
        "        glGetIntegerv(GL_TEXTURE_BINDING_2D, &xz_tex);\n"
        "        if (xz_hyena_special_kind != XZ_GEOMETRY_SPECIAL_NONE) {\n"
        "            XzGeometryTap_CaptureSpecialFan(\n"
        "                (const float *)vertices,\n"
        "                (unsigned int)count,\n"
        "                (unsigned int)(sizeof(vertex_t) / sizeof(float)),\n"
        "                (unsigned int)(offsetof(vertex_t, xyz) / sizeof(float)),\n"
        "                (unsigned int)(offsetof(vertex_t, uv) / sizeof(float)),\n"
        "                (int)xz_tex,\n"
        "                xz_hyena_special_kind,\n"
        "                &xz_state, xz_mv, xz_pr);\n"
        "        } else {\n"
        "            XzGeometryTap_CapturePrimitive(\n"
        "                (const float *)vertices,\n"
        "                (unsigned int)count,\n"
        "                (unsigned int)(sizeof(vertex_t) / sizeof(float)),\n"
        "                (unsigned int)(offsetof(vertex_t, xyz) / sizeof(float)),\n"
        "                (unsigned int)(offsetof(vertex_t, uv) / sizeof(float)),\n"
        "                xz_primitive,\n"
        "                (int)xz_tex,\n"
        "                &xz_state,\n"
        "                xz_mv,\n"
        "                xz_pr);\n"
        "        }\n"
        "    }\n"
        "    if (xz_hyena_special_kind != XZ_GEOMETRY_SPECIAL_NONE &&\n"
        "        XzAndroidRuntime_ShouldSuppressLegacyWorldDraw(XZ_LEGACY_DRAW_SPECIAL)) {\n"
        "        free(vertices);\n"
        "        return;\n"
        "    }\n"
        "    if (xz_hyena_special_kind == XZ_GEOMETRY_SPECIAL_NONE &&\n"
        "        XzAndroidRuntime_ShouldSuppressLegacyWorldDraw(XZ_LEGACY_DRAW_EFFECT)) {\n"
        "        free(vertices);\n"
        "        return;\n"
        "    }\n"
        "#endif\n"
        "    glEnableClientState(GL_VERTEX_ARRAY); glVertexPointer(3, GL_FLOAT, sizeof(*vertices), &vertices[0].xyz);\n"
    )
    hyena = hyena.replace(generic_anchor, generic_capture, 1)


warp_special_anchor = (
    "        Hyena_BeginVertices(HYE_TRIANGLE_FAN);\n"
    "        Hyena_DrawVertices(vertices, count, HYE_TEXTURE_32BITFLOAT, HYE_VERTEX_32BITFLOAT);\n"
    "        Hyena_EndVertices(); return;\n"
)
if "XZ_HYENA_WATER_SPECIAL" not in hyena:
    if warp_special_anchor not in hyena:
        raise SystemExit("Missing Hyena warped-water special anchor")
    warp_special = (
        "        Hyena_BeginVertices(HYE_TRIANGLE_FAN);\n"
        "#ifdef __ANDROID__\n"
        "        /* XZ_HYENA_WATER_SPECIAL */\n"
        "        xz_hyena_special_kind = XZ_GEOMETRY_SPECIAL_WATER;\n"
        "#endif\n"
        "        Hyena_DrawVertices(vertices, count, HYE_TEXTURE_32BITFLOAT, HYE_VERTEX_32BITFLOAT);\n"
        "#ifdef __ANDROID__\n"
        "        xz_hyena_special_kind = XZ_GEOMETRY_SPECIAL_NONE;\n"
        "#endif\n"
        "        Hyena_EndVertices(); return;\n"
    )
    hyena = hyena.replace(warp_special_anchor, warp_special, 1)

gl_hyena.write_text(hyena, encoding="utf-8")


# Capture the exact level-0 RGBA texels that Vril uploads to legacy GL4ES.
# GL_Upload32 mutates its scratch buffer while generating mip levels, so the
# tap must run immediately after the level-0 upload and before that loop.
gl_draw = source / "platform" / "sdl" / "gl" / "gl_draw.c"
draw = gl_draw.read_text(encoding="utf-8")

if '#include "xz_texture_tap.h"' not in draw:
    anchor = '#include "../../../nzportable_def.h"\n'
    if anchor not in draw:
        raise SystemExit("Missing gl_draw texture-tap include anchor")
    draw = draw.replace(
        anchor,
        anchor +
        '#ifdef __ANDROID__\n'
        '#include "xz_texture_tap.h"\n'
        '#endif\n',
        1,
    )

texture_upload_anchor = (
    "    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, scaled_width, "
    "scaled_height, 0, GL_RGBA, GL_UNSIGNED_BYTE, scaled);\n"
)
if "XZ_TEXTURE_RGBA_CAPTURE" not in draw:
    if texture_upload_anchor not in draw:
        raise SystemExit("Missing GL_Upload32 level-0 texture anchor")
    texture_capture = texture_upload_anchor + (
        "#ifdef __ANDROID__\n"
        "    /* XZ_TEXTURE_RGBA_CAPTURE: before scaled is mip-mutated. */\n"
        "    XzTextureTap_CaptureRgba(\n"
        "        (unsigned int)gl_id,\n"
        "        scaled,\n"
        "        (unsigned int)scaled_width,\n"
        "        (unsigned int)scaled_height);\n"
        "#endif\n"
    )
    draw = draw.replace(
        texture_upload_anchor,
        texture_capture,
        1,
    )

gl_draw.write_text(draw, encoding="utf-8")

if draw.count('#include "xz_texture_tap.h"') != 1:
    raise SystemExit("Texture tap header injection count mismatch")
if draw.count("XZ_TEXTURE_RGBA_CAPTURE") != 1:
    raise SystemExit("Texture RGBA capture injection count mismatch")


gl_rmain = source / "platform" / "sdl" / "gl" / "gl_rmain.c"
rmain = gl_rmain.read_text(encoding="utf-8")

if '#include "xz_geometry_tap.h"' not in rmain:
    anchor = '#include "../../../nzportable_def.h"\n'
    if anchor not in rmain:
        raise SystemExit("Missing gl_rmain include anchor")
    rmain = rmain.replace(
        anchor,
        anchor +
        '#ifdef __ANDROID__\n'
        '#include "xz_geometry_tap.h"\n'
        '#include "xz_android_runtime.h"\n'
        '#include <string.h>\n'
        '#include <stdlib.h>\n'
        '#endif\n',
        1,
    )

sprite_state_helper = (
    '#ifdef __ANDROID__\n'
    'static void XzCaptureLegacySpriteState(XzGeometryRenderState *state)\n'
    '{\n'
    '    GLboolean depth_write = GL_TRUE;\n'
    '    GLint value = 0;\n'
    '    memset(state, 0, sizeof(*state));\n'
    '    glGetFloatv(GL_CURRENT_COLOR, state->color);\n'
    '    state->blend_enabled = glIsEnabled(GL_BLEND) ? 1u : 0u;\n'
    '    state->alpha_test_enabled = glIsEnabled(GL_ALPHA_TEST) ? 1u : 0u;\n'
    '    state->depth_test_enabled = glIsEnabled(GL_DEPTH_TEST) ? 1u : 0u;\n'
    '    glGetBooleanv(GL_DEPTH_WRITEMASK, &depth_write);\n'
    '    state->depth_write = depth_write ? 1u : 0u;\n'
    '    glGetIntegerv(GL_BLEND_SRC, &value);\n'
    '    state->blend_src = (unsigned int)value;\n'
    '    glGetIntegerv(GL_BLEND_DST, &value);\n'
    '    state->blend_dst = (unsigned int)value;\n'
    '    glGetIntegerv(GL_DEPTH_FUNC, &value);\n'
    '    state->depth_func = (unsigned int)value;\n'
    '    glGetIntegerv(GL_ALPHA_TEST_FUNC, &value);\n'
    '    state->alpha_func = (unsigned int)value;\n'
    '    glGetFloatv(GL_ALPHA_TEST_REF, &state->alpha_ref);\n'
    '    glGetTexEnviv(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, &value);\n'
    '    state->texture_env_mode = (unsigned int)value;\n'
    '    state->texture_enabled = glIsEnabled(GL_TEXTURE_2D) ? 1u : 0u;\n'
    '    state->fog_enabled = glIsEnabled(GL_FOG) ? 1u : 0u;\n'
    '    glGetFloatv(GL_FOG_START, &state->fog_start);\n'
    '    glGetFloatv(GL_FOG_END, &state->fog_end);\n'
    '    glGetFloatv(GL_FOG_COLOR, state->fog_color);\n'
    '    glGetFloatv(GL_DEPTH_RANGE, state->depth_range);\n'
    '    state->cull_enabled = glIsEnabled(GL_CULL_FACE) ? 1u : 0u;\n'
    '    glGetIntegerv(GL_CULL_FACE_MODE, &value);\n'
    '    state->cull_face = (unsigned int)value;\n'
    '    glGetIntegerv(GL_FRONT_FACE, &value);\n'
    '    state->front_face = (unsigned int)value;\n'
    '    state->polygon_offset_enabled = glIsEnabled(GL_POLYGON_OFFSET_FILL) ? 1u : 0u;\n'
    '    glGetFloatv(GL_POLYGON_OFFSET_FACTOR, &state->polygon_offset_factor);\n'
    '    glGetFloatv(GL_POLYGON_OFFSET_UNITS, &state->polygon_offset_units);\n'
    '}\n'
    '#endif\n'
)
if 'static void XzCaptureLegacySpriteState' not in rmain:
    include_end = '#endif\n'
    include_pos = rmain.find(include_end, rmain.find('#include "xz_geometry_tap.h"'))
    if include_pos < 0:
        raise SystemExit("Missing sprite state helper insertion point")
    include_pos += len(include_end)
    rmain = rmain[:include_pos] + '\n' + sprite_state_helper + rmain[include_pos:]

sprite_anchor = (
    "\tglBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);\n"
    "\tglBegin (GL_QUADS);\n"
)
if "XZ_GEOMETRY_SPRITE_CAPTURE" not in rmain:
    if sprite_anchor not in rmain:
        raise SystemExit("Missing post-state sprite geometry capture anchor")
    sprite_capture = (
        "\tglBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);\n"
        "#ifdef __ANDROID__\n"
        "\t/* XZ_GEOMETRY_SPRITE_CAPTURE: after sprite blend/depth setup. */\n"
        "\t{\n"
        "\t\tfloat xz_positions[12];\n"
        "\t\tconst float xz_uvs[8] = {0,1, 0,0, 1,0, 1,1};\n"
        "\t\tfloat xz_mv[16], xz_pr[16];\n"
        "\t\tGLint xz_tex = 0;\n"
        "\t\tXzGeometryRenderState xz_state;\n"
        "\t\tvec3_t xz_point;\n"
        "\t\tXzCaptureLegacySpriteState(&xz_state);\n"
        "\t\tVectorMA (e->origin, frame->down * scale, up, xz_point);\n"
        "\t\tVectorMA (xz_point, frame->left * scale, right, xz_point);\n"
        "\t\tmemcpy(&xz_positions[0], xz_point, sizeof(vec3_t));\n"
        "\t\tVectorMA (e->origin, frame->up * scale, up, xz_point);\n"
        "\t\tVectorMA (xz_point, frame->left * scale, right, xz_point);\n"
        "\t\tmemcpy(&xz_positions[3], xz_point, sizeof(vec3_t));\n"
        "\t\tVectorMA (e->origin, frame->up * scale, up, xz_point);\n"
        "\t\tVectorMA (xz_point, frame->right * scale, right, xz_point);\n"
        "\t\tmemcpy(&xz_positions[6], xz_point, sizeof(vec3_t));\n"
        "\t\tVectorMA (e->origin, frame->down * scale, up, xz_point);\n"
        "\t\tVectorMA (xz_point, frame->right * scale, right, xz_point);\n"
        "\t\tmemcpy(&xz_positions[9], xz_point, sizeof(vec3_t));\n"
        "\t\tglGetFloatv(GL_MODELVIEW_MATRIX, xz_mv);\n"
        "\t\tglGetFloatv(GL_PROJECTION_MATRIX, xz_pr);\n"
        "\t\tglGetIntegerv(GL_TEXTURE_BINDING_2D, &xz_tex);\n"
        "\t\tXzGeometryTap_CaptureSpriteQuad(\n"
        "\t\t\txz_positions,\n"
        "\t\t\txz_uvs,\n"
        "\t\t\t(int)xz_tex,\n"
        "\t\t\t&xz_state,\n"
        "\t\t\txz_mv,\n"
        "\t\t\txz_pr);\n"
        "\t}\n"
        "\tif (!XzAndroidRuntime_ShouldSuppressLegacyWorldDraw(XZ_LEGACY_DRAW_SPRITE)) {\n"
        "#endif\n"
        "\tglBegin (GL_QUADS);\n"
    )
    rmain = rmain.replace(sprite_anchor, sprite_capture, 1)



if "XZ_LEGACY_SPRITE_SUPPRESS_END" not in rmain:
    sprite_begin = rmain.find("void R_DrawSpriteModel (entity_t *e)")
    sprite_end = rmain.find("/*\n=============================================================\n\n  ALIAS MODELS", sprite_begin)
    if sprite_begin < 0 or sprite_end < 0:
        raise SystemExit("Missing sprite function bounds for suppression")
    sprite_chunk = rmain[sprite_begin:sprite_end]
    sprite_end_anchor = "\tglEnd ();\n\tglDepthMask(GL_TRUE);\n"
    if sprite_end_anchor not in sprite_chunk:
        raise SystemExit("Missing sprite suppression end anchor")
    sprite_chunk = sprite_chunk.replace(
        sprite_end_anchor,
        "\tglEnd ();\n"
        "#ifdef __ANDROID__\n"
        "\t} /* XZ_LEGACY_SPRITE_SUPPRESS_END */\n"
        "#endif\n"
        "\tglDepthMask(GL_TRUE);\n",
        1,
    )
    rmain = rmain[:sprite_begin] + sprite_chunk + rmain[sprite_end:]

# Alias/model blob shadows bypass Hyena and are emitted as immediate-mode
# triangle fans/strips. Capture the projected vertices and the exact untextured
# blend state so the GLES3 world remains complete before legacy 3D retirement.
if "XZ_ALIAS_SHADOW_CAPTURE" not in rmain:
    shadow_begin = rmain.find("void GL_DrawAliasShadow (aliashdr_t *paliashdr, int posenum)")
    shadow_end = rmain.find("/*\n=================\nR_SetupAliasFrame", shadow_begin)
    if shadow_begin < 0 or shadow_end < 0:
        raise SystemExit("Missing alias-shadow function bounds")
    shadow = rmain[shadow_begin:shadow_end]

    shadow_local_anchor = "\tint\t\tcount;\n"
    if shadow_local_anchor not in shadow:
        raise SystemExit("Missing alias-shadow local anchor")
    shadow = shadow.replace(
        shadow_local_anchor,
        shadow_local_anchor +
        "#ifdef __ANDROID__\n"
        "\tfloat\t\t*xz_shadow_capture = NULL;\n"
        "\tint\t\txz_shadow_capture_count = 0;\n"
        "\tint\t\txz_shadow_capture_index = 0;\n"
        "\tint\t\txz_shadow_suppress = 0;\n"
        "\tXzGeometryPrimitive xz_shadow_primitive = XZ_GEOMETRY_TRIANGLE_STRIP;\n"
        "#endif\n",
        1,
    )

    fan_anchor = (
        "\t\tif (count < 0)\n"
        "\t\t{\n"
        "\t\t\tcount = -count;\n"
        "\t\t\tglBegin (GL_TRIANGLE_FAN);\n"
        "\t\t}\n"
        "\t\telse\n"
        "\t\t\tglBegin (GL_TRIANGLE_STRIP);\n"
    )
    if fan_anchor not in shadow:
        raise SystemExit("Missing alias-shadow primitive anchor")
    fan_block = (
        "\t\tif (count < 0)\n"
        "\t\t{\n"
        "\t\t\tcount = -count;\n"
        "#ifdef __ANDROID__\n"
        "\t\t\txz_shadow_primitive = XZ_GEOMETRY_TRIANGLE_FAN;\n"
        "#endif\n"
        "#ifdef __ANDROID__\n"
        "\t\t\tif (!xz_shadow_suppress)\n"
        "#endif\n"
        "\t\t\tglBegin (GL_TRIANGLE_FAN);\n"
        "\t\t}\n"
        "\t\telse\n"
        "\t\t{\n"
        "#ifdef __ANDROID__\n"
        "\t\t\txz_shadow_primitive = XZ_GEOMETRY_TRIANGLE_STRIP;\n"
        "\t\t\tif (!xz_shadow_suppress)\n"
        "#endif\n"
        "\t\t\tglBegin (GL_TRIANGLE_STRIP);\n"
        "\t\t}\n"
        "#ifdef __ANDROID__\n"
        "\t\txz_shadow_capture_count = (xz_shadow_capture && count <= paliashdr->poseverts) ? count : 0;\n"
        "\t\txz_shadow_capture_index = 0;\n"
        "#endif\n"
    )
    shadow = shadow.replace(fan_anchor, fan_block, 1)

    shadow_height_anchor = "\theight = -lheight + 1.0f;\n"
    if shadow_height_anchor not in shadow:
        raise SystemExit("Missing alias-shadow scratch allocation anchor")
    shadow = shadow.replace(
        shadow_height_anchor,
        shadow_height_anchor +
        "#ifdef __ANDROID__\n"
        "\t/* One scratch allocation per shadowed model, reused by every strip/fan. */\n"
        "\tif (paliashdr->poseverts > 0)\n"
        "\t\txz_shadow_capture = (float *)malloc((size_t)paliashdr->poseverts * 5u * sizeof(float));\n"
        "\txz_shadow_suppress = XzAndroidRuntime_ShouldSuppressLegacyWorldDraw(XZ_LEGACY_DRAW_SHADOW);\n"
        "#endif\n",
        1,
    )

    vertex_anchor = (
        "\t\t\tpoint[2] = height;\n"
        "//\t\t\theight -= 0.001;\n"
        "\t\t\tglVertex3fv (point);\n"
    )
    if vertex_anchor not in shadow:
        raise SystemExit("Missing alias-shadow vertex anchor")
    vertex_block = (
        "\t\t\tpoint[2] = height;\n"
        "//\t\t\theight -= 0.001;\n"
        "#ifdef __ANDROID__\n"
        "\t\t\tif (xz_shadow_capture && xz_shadow_capture_index < xz_shadow_capture_count) {\n"
        "\t\t\t\tfloat *xz_out = xz_shadow_capture + xz_shadow_capture_index * 5;\n"
        "\t\t\t\txz_out[0] = point[0];\n"
        "\t\t\t\txz_out[1] = point[1];\n"
        "\t\t\t\txz_out[2] = point[2];\n"
        "\t\t\t\txz_out[3] = 0.0f;\n"
        "\t\t\t\txz_out[4] = 0.0f;\n"
        "\t\t\t\txz_shadow_capture_index++;\n"
        "\t\t\t}\n"
        "#endif\n"
        "#ifdef __ANDROID__\n"
        "\t\t\tif (!xz_shadow_suppress)\n"
        "#endif\n"
        "\t\t\tglVertex3fv (point);\n"
    )
    shadow = shadow.replace(vertex_anchor, vertex_block, 1)

    end_anchor = "\t\tglEnd ();\n"
    if end_anchor not in shadow:
        raise SystemExit("Missing alias-shadow end anchor")
    end_block = (
        "#ifdef __ANDROID__\n"
        "\t\tif (!xz_shadow_suppress)\n"
        "#endif\n"
        "\t\tglEnd ();\n"
        "#ifdef __ANDROID__\n"
        "\t\tif (xz_shadow_capture && xz_shadow_capture_index == xz_shadow_capture_count) {\n"
        "\t\t\tfloat xz_mv[16], xz_pr[16];\n"
        "\t\t\tXzGeometryRenderState xz_state;\n"
        "\t\t\tXzCaptureLegacySpriteState(&xz_state);\n"
        "\t\t\txz_state.texture_enabled = 0u;\n"
        "\t\t\tglGetFloatv(GL_MODELVIEW_MATRIX, xz_mv);\n"
        "\t\t\tglGetFloatv(GL_PROJECTION_MATRIX, xz_pr);\n"
        "\t\t\t/* XZ_ALIAS_SHADOW_CAPTURE */\n"
        "\t\t\tXzGeometryTap_CaptureShadowPrimitive(\n"
        "\t\t\t\txz_shadow_capture,\n"
        "\t\t\t\t(unsigned int)xz_shadow_capture_count,\n"
        "\t\t\t\t5u, 0u, 5u,\n"
        "\t\t\t\txz_shadow_primitive,\n"
        "\t\t\t\t&xz_state, xz_mv, xz_pr);\n"
        "\t\t}\n"
        "#endif\n"
    )
    shadow = shadow.replace(end_anchor, end_block, 1)

    shadow_tail_anchor = "\t}\t\n}\n"
    if shadow_tail_anchor not in shadow:
        raise SystemExit("Missing alias-shadow scratch free anchor")
    shadow = shadow.replace(
        shadow_tail_anchor,
        "\t}\t\n"
        "#ifdef __ANDROID__\n"
        "\tif (xz_shadow_capture) free(xz_shadow_capture);\n"
        "#endif\n"
        "}\n",
        1,
    )

    rmain = rmain[:shadow_begin] + shadow + rmain[shadow_end:]

if rmain.count("XZ_ALIAS_SHADOW_CAPTURE") != 1:
    raise SystemExit("Alias-shadow geometry capture injection count mismatch")

gl_rmain.write_text(rmain, encoding="utf-8")


# Capture legacy immediate-mode sky/water paths that bypass Hyena. The capture
# is side-band only: Vril/GL4ES still executes its original draw during parity
# validation, while Xz records the exact post-warp vertices/UVs and GL state.
gl_warp = source / "platform" / "sdl" / "gl" / "gl_warp.c"
warp = gl_warp.read_text(encoding="utf-8")

if '#include "xz_geometry_tap.h"' not in warp:
    anchor = '#include "../../../nzportable_def.h"\n'
    if anchor not in warp:
        raise SystemExit("Missing gl_warp include anchor")
    warp = warp.replace(
        anchor,
        anchor +
        '#ifdef __ANDROID__\n'
        '#include "xz_geometry_tap.h"\n'
        '#include "xz_android_runtime.h"\n'
        '#include <stddef.h>\n'
        '#include <string.h>\n'
        '#endif\n',
        1,
    )

if 'static void XzCaptureLegacyRenderState' not in warp:
    include_end = '#endif\n'
    include_pos = warp.find(include_end, warp.find('#include "xz_geometry_tap.h"'))
    if include_pos < 0:
        raise SystemExit("Missing gl_warp state-helper insertion point")
    include_pos += len(include_end)
    warp = warp[:include_pos] + '\n' + state_helper + warp[include_pos:]


def replace_scoped(text, begin, end, old, new, label):
    b = text.find(begin)
    e = text.find(end, b + len(begin))
    if b < 0 or e < 0:
        raise SystemExit("Missing " + label + " function bounds")
    chunk = text[b:e]
    if old not in chunk:
        raise SystemExit("Missing " + label + " capture anchor")
    chunk = chunk.replace(old, new, 1)
    return text[:b] + chunk + text[e:]


if "XZ_SPECIAL_WATER_CAPTURE" not in warp:
    warp = replace_scoped(
        warp,
        "void EmitWaterPolys (msurface_t *fa)",
        "/*\n=============\nEmitSkyPolys",
        "\t{\n\t\tglBegin (GL_POLYGON);\n",
        "\t{\n"
        "#ifdef __ANDROID__\n"
        "\t\tfloat xz_capture[64 * 5];\n"
        "\t\tint xz_capture_count = p->numverts <= 64 ? p->numverts : 0;\n"
        "\t\tint xz_suppress_special = XzAndroidRuntime_ShouldSuppressLegacyWorldDraw(XZ_LEGACY_DRAW_SPECIAL);\n"
        "\t\tif (!xz_suppress_special)\n"
        "#endif\n"
        "\t\tglBegin (GL_POLYGON);\n",
        "water begin",
    )
    warp = replace_scoped(
        warp,
        "void EmitWaterPolys (msurface_t *fa)",
        "/*\n=============\nEmitSkyPolys",
        "\t\t\tt *= (1.0f/64);\n\n\t\t\tglTexCoord2f (s, t);\n",
        "\t\t\tt *= (1.0f/64);\n"
        "#ifdef __ANDROID__\n"
        "\t\t\tif (xz_capture_count) {\n"
        "\t\t\t\txz_capture[i * 5 + 0] = v[0];\n"
        "\t\t\t\txz_capture[i * 5 + 1] = v[1];\n"
        "\t\t\t\txz_capture[i * 5 + 2] = v[2];\n"
        "\t\t\t\txz_capture[i * 5 + 3] = s;\n"
        "\t\t\t\txz_capture[i * 5 + 4] = t;\n"
        "\t\t\t}\n"
        "#endif\n\n"
        "\t\t\tglTexCoord2f (s, t);\n",
        "water vertex",
    )
    warp = replace_scoped(
        warp,
        "void EmitWaterPolys (msurface_t *fa)",
        "/*\n=============\nEmitSkyPolys",
        "\t\t\tglTexCoord2f (s, t);\n\t\t\tglVertex3fv (v);\n",
        "#ifdef __ANDROID__\n"
        "\t\t\tif (!xz_suppress_special) {\n"
        "#endif\n"
        "\t\t\tglTexCoord2f (s, t);\n"
        "\t\t\tglVertex3fv (v);\n"
        "#ifdef __ANDROID__\n"
        "\t\t\t}\n"
        "#endif\n",
        "water legacy draw guard",
    )
    warp = replace_scoped(
        warp,
        "void EmitWaterPolys (msurface_t *fa)",
        "/*\n=============\nEmitSkyPolys",
        "\t\tglEnd ();\n\t}\n}\n",
        "#ifdef __ANDROID__\n"
        "\t\tif (!xz_suppress_special)\n"
        "#endif\n"
        "\t\tglEnd ();\n"
        "#ifdef __ANDROID__\n"
        "\t\tif (xz_capture_count) {\n"
        "\t\t\tfloat xz_mv[16], xz_pr[16];\n"
        "\t\t\tGLint xz_tex = 0;\n"
        "\t\t\tXzGeometryRenderState xz_state;\n"
        "\t\t\tXzCaptureLegacyRenderState(&xz_state);\n"
        "\t\t\tglGetFloatv(GL_MODELVIEW_MATRIX, xz_mv);\n"
        "\t\t\tglGetFloatv(GL_PROJECTION_MATRIX, xz_pr);\n"
        "\t\t\tglGetIntegerv(GL_TEXTURE_BINDING_2D, &xz_tex);\n"
        "\t\t\t/* XZ_SPECIAL_WATER_CAPTURE */\n"
        "\t\t\tXzGeometryTap_CaptureSpecialFan(\n"
        "\t\t\t\txz_capture, (unsigned int)xz_capture_count,\n"
        "\t\t\t\t5u, 0u, 3u, (int)xz_tex,\n"
        "\t\t\t\tXZ_GEOMETRY_SPECIAL_WATER,\n"
        "\t\t\t\t&xz_state, xz_mv, xz_pr);\n"
        "\t\t}\n"
        "#endif\n"
        "\t}\n}\n",
        "water end",
    )

if "XZ_SPECIAL_SKY_LAYER_CAPTURE" not in warp:
    warp = replace_scoped(
        warp,
        "void EmitSkyPolys (msurface_t *fa)",
        "void EmitFlatSkyPolys (msurface_t *fa)",
        "\t{\n\t\tglBegin (GL_POLYGON);\n",
        "\t{\n"
        "#ifdef __ANDROID__\n"
        "\t\tfloat xz_capture[64 * 5];\n"
        "\t\tint xz_capture_count = p->numverts <= 64 ? p->numverts : 0;\n"
        "\t\tint xz_suppress_special = XzAndroidRuntime_ShouldSuppressLegacyWorldDraw(XZ_LEGACY_DRAW_SPECIAL);\n"
        "\t\tif (!xz_suppress_special)\n"
        "#endif\n"
        "\t\tglBegin (GL_POLYGON);\n",
        "sky-layer begin",
    )
    warp = replace_scoped(
        warp,
        "void EmitSkyPolys (msurface_t *fa)",
        "void EmitFlatSkyPolys (msurface_t *fa)",
        "\t\t\tt = (speedscale + dir[1]) * (1.0f/128);\n\n\t\t\tglTexCoord2f (s, t);\n",
        "\t\t\tt = (speedscale + dir[1]) * (1.0f/128);\n"
        "#ifdef __ANDROID__\n"
        "\t\t\tif (xz_capture_count) {\n"
        "\t\t\t\txz_capture[i * 5 + 0] = v[0];\n"
        "\t\t\t\txz_capture[i * 5 + 1] = v[1];\n"
        "\t\t\t\txz_capture[i * 5 + 2] = v[2];\n"
        "\t\t\t\txz_capture[i * 5 + 3] = s;\n"
        "\t\t\t\txz_capture[i * 5 + 4] = t;\n"
        "\t\t\t}\n"
        "#endif\n\n"
        "\t\t\tglTexCoord2f (s, t);\n",
        "sky-layer vertex",
    )
    warp = replace_scoped(
        warp,
        "void EmitSkyPolys (msurface_t *fa)",
        "void EmitFlatSkyPolys (msurface_t *fa)",
        "\t\t\tglTexCoord2f (s, t);\n\t\t\tglVertex3fv (v);\n",
        "#ifdef __ANDROID__\n"
        "\t\t\tif (!xz_suppress_special) {\n"
        "#endif\n"
        "\t\t\tglTexCoord2f (s, t);\n"
        "\t\t\tglVertex3fv (v);\n"
        "#ifdef __ANDROID__\n"
        "\t\t\t}\n"
        "#endif\n",
        "sky-layer legacy draw guard",
    )
    warp = replace_scoped(
        warp,
        "void EmitSkyPolys (msurface_t *fa)",
        "void EmitFlatSkyPolys (msurface_t *fa)",
        "\t\tglEnd ();\n\t}\n}\n\n",
        "#ifdef __ANDROID__\n"
        "\t\tif (!xz_suppress_special)\n"
        "#endif\n"
        "\t\tglEnd ();\n"
        "#ifdef __ANDROID__\n"
        "\t\tif (xz_capture_count) {\n"
        "\t\t\tfloat xz_mv[16], xz_pr[16];\n"
        "\t\t\tGLint xz_tex = 0;\n"
        "\t\t\tXzGeometryRenderState xz_state;\n"
        "\t\t\tXzCaptureLegacyRenderState(&xz_state);\n"
        "\t\t\tglGetFloatv(GL_MODELVIEW_MATRIX, xz_mv);\n"
        "\t\t\tglGetFloatv(GL_PROJECTION_MATRIX, xz_pr);\n"
        "\t\t\tglGetIntegerv(GL_TEXTURE_BINDING_2D, &xz_tex);\n"
        "\t\t\t/* XZ_SPECIAL_SKY_LAYER_CAPTURE */\n"
        "\t\t\tXzGeometryTap_CaptureSpecialFan(\n"
        "\t\t\t\txz_capture, (unsigned int)xz_capture_count,\n"
        "\t\t\t\t5u, 0u, 3u, (int)xz_tex,\n"
        "\t\t\t\tXZ_GEOMETRY_SPECIAL_SKY,\n"
        "\t\t\t\t&xz_state, xz_mv, xz_pr);\n"
        "\t\t}\n"
        "#endif\n"
        "\t}\n}\n\n",
        "sky-layer end",
    )

if "XZ_SPECIAL_FLAT_SKY_CAPTURE" not in warp:
    warp = replace_scoped(
        warp,
        "void EmitFlatSkyPolys (msurface_t *fa)",
        "/*\n===============\nEmitBothSkyLayers",
        "\t\t{\n\t\t\tglBegin(GL_POLYGON);\n",
        "\t\t{\n"
        "#ifdef __ANDROID__\n"
        "\t\t\tint xz_suppress_special = XzAndroidRuntime_ShouldSuppressLegacyWorldDraw(XZ_LEGACY_DRAW_SPECIAL);\n"
        "\t\t\tif (!xz_suppress_special)\n"
        "#endif\n"
        "\t\t\tglBegin(GL_POLYGON);\n",
        "flat-sky begin guard",
    )
    warp = replace_scoped(
        warp,
        "void EmitFlatSkyPolys (msurface_t *fa)",
        "/*\n===============\nEmitBothSkyLayers",
        "\t\t\tfor (int i = 0; i < poly->numverts; i++)\n\t\t\t\tglVertex3fv(poly->verts[i]);\n",
        "\t\t\tfor (int i = 0; i < poly->numverts; i++)\n"
        "#ifdef __ANDROID__\n"
        "\t\t\t\tif (!xz_suppress_special)\n"
        "#endif\n"
        "\t\t\t\tglVertex3fv(poly->verts[i]);\n",
        "flat-sky vertex guard",
    )
    warp = replace_scoped(
        warp,
        "void EmitFlatSkyPolys (msurface_t *fa)",
        "/*\n===============\nEmitBothSkyLayers",
        "\t\t\tglEnd();\n",
        "#ifdef __ANDROID__\n"
        "\t\t\tif (!xz_suppress_special)\n"
        "#endif\n"
        "\t\t\tglEnd();\n"
        "#ifdef __ANDROID__\n"
        "\t\t\t{\n"
        "\t\t\t\tfloat xz_mv[16], xz_pr[16];\n"
        "\t\t\t\tGLint xz_tex = 0;\n"
        "\t\t\t\tXzGeometryRenderState xz_state;\n"
        "\t\t\t\tXzCaptureLegacyRenderState(&xz_state);\n"
        "\t\t\t\tglGetFloatv(GL_MODELVIEW_MATRIX, xz_mv);\n"
        "\t\t\t\tglGetFloatv(GL_PROJECTION_MATRIX, xz_pr);\n"
        "\t\t\t\tglGetIntegerv(GL_TEXTURE_BINDING_2D, &xz_tex);\n"
        "\t\t\t\t/* XZ_SPECIAL_FLAT_SKY_CAPTURE */\n"
        "\t\t\t\tXzGeometryTap_CaptureSpecialFan(\n"
        "\t\t\t\t\tpoly->verts[0], (unsigned int)poly->numverts,\n"
        "\t\t\t\t\tVERTEXSIZE, 0u, 3u, (int)xz_tex,\n"
        "\t\t\t\t\tXZ_GEOMETRY_SPECIAL_SKY,\n"
        "\t\t\t\t\t&xz_state, xz_mv, xz_pr);\n"
        "\t\t\t}\n"
        "#endif\n",
        "flat-sky",
    )

if "XZ_SPECIAL_SKYBOX_CAPTURE" not in warp:
    warp = replace_scoped(
        warp,
        "void R_DrawSkyBox (void)",
        "//===============================================================",
        "\t\tglBegin(GL_QUADS);\n",
        "#ifdef __ANDROID__\n"
        "\t\tint xz_suppress_special = XzAndroidRuntime_ShouldSuppressLegacyWorldDraw(XZ_LEGACY_DRAW_SPECIAL);\n"
        "\t\tif (!xz_suppress_special)\n"
        "#endif\n"
        "\t\tglBegin(GL_QUADS);\n",
        "skybox begin guard",
    )
    warp = replace_scoped(
        warp,
        "void R_DrawSkyBox (void)",
        "//===============================================================",
        "\t\tglTexCoord2f (sky_vertices[0].s, sky_vertices[0].t);\n\t\tglVertex3fv (v);\n",
        "#ifdef __ANDROID__\n"
        "\t\tif (!xz_suppress_special) {\n"
        "#endif\n"
        "\t\tglTexCoord2f (sky_vertices[0].s, sky_vertices[0].t);\n"
        "\t\tglVertex3fv (v);\n"
        "#ifdef __ANDROID__\n"
        "\t\t}\n"
        "#endif\n",
        "skybox vertex 0 guard",
    )
    warp = replace_scoped(
        warp,
        "void R_DrawSkyBox (void)",
        "//===============================================================",
        "\t\tglTexCoord2f (sky_vertices[1].s, sky_vertices[1].t);\n\t\tglVertex3fv (v);\n",
        "#ifdef __ANDROID__\n"
        "\t\tif (!xz_suppress_special) {\n"
        "#endif\n"
        "\t\tglTexCoord2f (sky_vertices[1].s, sky_vertices[1].t);\n"
        "\t\tglVertex3fv (v);\n"
        "#ifdef __ANDROID__\n"
        "\t\t}\n"
        "#endif\n",
        "skybox vertex 1 guard",
    )
    warp = replace_scoped(
        warp,
        "void R_DrawSkyBox (void)",
        "//===============================================================",
        "\t\tglTexCoord2f (sky_vertices[2].s, sky_vertices[2].t);\n\t\tglVertex3fv (v);\n",
        "#ifdef __ANDROID__\n"
        "\t\tif (!xz_suppress_special) {\n"
        "#endif\n"
        "\t\tglTexCoord2f (sky_vertices[2].s, sky_vertices[2].t);\n"
        "\t\tglVertex3fv (v);\n"
        "#ifdef __ANDROID__\n"
        "\t\t}\n"
        "#endif\n",
        "skybox vertex 2 guard",
    )
    warp = replace_scoped(
        warp,
        "void R_DrawSkyBox (void)",
        "//===============================================================",
        "\t\tglTexCoord2f (sky_vertices[3].s, sky_vertices[3].t);\n\t\tglVertex3fv (v);\n",
        "#ifdef __ANDROID__\n"
        "\t\tif (!xz_suppress_special) {\n"
        "#endif\n"
        "\t\tglTexCoord2f (sky_vertices[3].s, sky_vertices[3].t);\n"
        "\t\tglVertex3fv (v);\n"
        "#ifdef __ANDROID__\n"
        "\t\t}\n"
        "#endif\n",
        "skybox vertex 3 guard",
    )
    warp = replace_scoped(
        warp,
        "void R_DrawSkyBox (void)",
        "//===============================================================",
        "\t\tglEnd();\n\t}\n",
        "#ifdef __ANDROID__\n"
        "\t\tif (!xz_suppress_special)\n"
        "#endif\n"
        "\t\tglEnd();\n"
        "#ifdef __ANDROID__\n"
        "\t\t{\n"
        "\t\t\tfloat xz_mv[16], xz_pr[16];\n"
        "\t\t\tGLint xz_tex = 0;\n"
        "\t\t\tXzGeometryRenderState xz_state;\n"
        "\t\t\tXzCaptureLegacyRenderState(&xz_state);\n"
        "\t\t\tglGetFloatv(GL_MODELVIEW_MATRIX, xz_mv);\n"
        "\t\t\tglGetFloatv(GL_PROJECTION_MATRIX, xz_pr);\n"
        "\t\t\tglGetIntegerv(GL_TEXTURE_BINDING_2D, &xz_tex);\n"
        "\t\t\t/* XZ_SPECIAL_SKYBOX_CAPTURE */\n"
        "\t\t\tXzGeometryTap_CaptureSpecialFan(\n"
        "\t\t\t\t(const float *)sky_vertices, 4u,\n"
        "\t\t\t\t(unsigned int)(sizeof(glvert_t) / sizeof(float)),\n"
        "\t\t\t\t0u, 3u, (int)xz_tex,\n"
        "\t\t\t\tXZ_GEOMETRY_SPECIAL_SKY,\n"
        "\t\t\t\t&xz_state, xz_mv, xz_pr);\n"
        "\t\t}\n"
        "#endif\n"
        "\t}\n",
        "skybox",
    )

gl_warp.write_text(warp, encoding="utf-8")

if warp.count('#include "xz_geometry_tap.h"') != 1:
    raise SystemExit("Sky/water geometry tap header injection count mismatch")
if warp.count("XZ_SPECIAL_WATER_CAPTURE") != 1:
    raise SystemExit("Water geometry capture injection count mismatch")
if (
    warp.count("XZ_SPECIAL_SKY_LAYER_CAPTURE") != 1
    or warp.count("XZ_SPECIAL_FLAT_SKY_CAPTURE") != 1
    or warp.count("XZ_SPECIAL_SKYBOX_CAPTURE") != 1
):
    raise SystemExit("Sky geometry capture injection count mismatch")



# Explicitly disarm persistent world-raster suppression at every level change.
# This lets stable frames suppress from their first 3D draw while guaranteeing
# that a newly loaded map falls back to legacy GL4ES until MODERN is revalidated.
gl_rmisc = source / "platform" / "sdl" / "gl" / "gl_rmisc.c"
rmisc = gl_rmisc.read_text(encoding="utf-8")

if '#include "xz_android_runtime.h"' not in rmisc:
    anchor = '#include "../../../nzportable_def.h"\n'
    if anchor not in rmisc:
        raise SystemExit("Missing gl_rmisc runtime include anchor")
    rmisc = rmisc.replace(
        anchor,
        anchor +
        '#ifdef __ANDROID__\n'
        '#include "xz_android_runtime.h"\n'
        '#endif\n',
        1,
    )

if "XZ_WORLD_TRANSITION_RESET" not in rmisc:
    anchor = "void R_NewMap (void)\n{\n\tint\t\ti;\n"
    if anchor not in rmisc:
        raise SystemExit("Missing R_NewMap transition-reset anchor")
    rmisc = rmisc.replace(
        anchor,
        "void R_NewMap (void)\n{\n\tint\t\ti;\n"
        "#ifdef __ANDROID__\n"
        "\t/* XZ_WORLD_TRANSITION_RESET */\n"
        "\tXzAndroidRuntime_NotifyWorldTransitionNamed(\n"
        "\t\tcl.worldmodel ? cl.worldmodel->name : NULL);\n"
        "#endif\n",
        1,
    )

gl_rmisc.write_text(rmisc, encoding="utf-8")

if rmisc.count('#include "xz_android_runtime.h"') != 1:
    raise SystemExit("World-transition runtime header injection count mismatch")
if rmisc.count("XZ_WORLD_TRANSITION_RESET") != 1:
    raise SystemExit("World-transition reset injection count mismatch")


# Replace only the visible 3D world before Vril switches to its 2D HUD pass.
# The native GLES3 compositor renders into the same EGL window backbuffer and
# restores the legacy GL4ES context before GL_Set2D, so menus/touch HUD remain
# intact and the existing SDL swap remains the final presentation primitive.
r_screen = source / "render" / "r_screen.c"
screen = r_screen.read_text(encoding="utf-8")

if '#include "../xz_android_runtime.h"' not in screen:
    anchor = '#include "../nzportable_def.h"\n'
    if anchor not in screen:
        raise SystemExit("Missing r_screen include anchor")
    screen = screen.replace(
        anchor,
        anchor +
        '#ifdef __ANDROID__\n'
        '#include "../xz_android_runtime.h"\n'
        '#endif\n',
        1,
    )

visible_anchor = (
    "\tif (!LoadingScreen_IsWaiting()) {\n"
    "\t\tSCR_SetUpToDrawConsole ();\n"
    "\t\tV_RenderView ();\n"
    "\t}\n\n"
    "\tGL_Set2D ();\n"
)
if "XZ_VISIBLE_PRESENT_COMPOSITE" not in screen:
    if visible_anchor not in screen:
        raise SystemExit("Missing pre-HUD visible present anchor")
    visible_block = (
        "\tif (!LoadingScreen_IsWaiting()) {\n"
        "\t\tSCR_SetUpToDrawConsole ();\n"
        "\t\tV_RenderView ();\n"
        "#ifdef __ANDROID__\n"
        "\t\t/* XZ_VISIBLE_PRESENT_COMPOSITE */\n"
        "\t\tXzAndroidRuntime_CompositeVisibleWorld();\n"
        "#endif\n"
        "\t}\n\n"
        "\tGL_Set2D ();\n"
    )
    screen = screen.replace(
        visible_anchor,
        visible_block,
        1,
    )

preswap_anchor = (
    "\tV_UpdatePalette ();\n\n"
    "\tGL_EndRendering ();\n"
)
if "XZ_PRESENT_LUMA_PRESWAP" not in screen:
    if preswap_anchor not in screen:
        raise SystemExit("Missing pre-swap luma audit anchor")
    preswap_block = (
        "\tV_UpdatePalette ();\n\n"
        "#ifdef __ANDROID__\n"
        "\t/* XZ_PRESENT_LUMA_PRESWAP */\n"
        "\tXzAndroidRuntime_AuditLegacyPresentBeforeSwap(\n"
        "\t\t(unsigned int)glwidth,\n"
        "\t\t(unsigned int)glheight,\n"
        "\t\tscreenflash_color,\n"
        "\t\tscreenflash_type,\n"
        "\t\tscreenflash_duration,\n"
        "\t\tscreenflash_starttime,\n"
        "\t\tscreenflash_worktime,\n"
        "\t\tsv.time);\n"
        "#endif\n"
        "\tGL_EndRendering ();\n"
    )
    screen = screen.replace(
        preswap_anchor,
        preswap_block,
        1,
    )

new_preswap_call = (
    "\tXzAndroidRuntime_AuditLegacyPresentBeforeSwap(\n"
    "\t\t(unsigned int)glwidth,\n"
    "\t\t(unsigned int)glheight,\n"
    "\t\tscreenflash_color,\n"
    "\t\tscreenflash_type,\n"
    "\t\tscreenflash_duration,\n"
    "\t\tscreenflash_starttime,\n"
    "\t\tscreenflash_worktime,\n"
    "\t\tsv.time);\n"
)

# Normalize any previously injected 7-argument call regardless of whitespace.
screen, preswap_migrations = re.subn(
    r"XzAndroidRuntime_AuditLegacyPresentBeforeSwap\(\s*"
    r"\(unsigned int\)glwidth\s*,\s*"
    r"\(unsigned int\)glheight\s*,\s*"
    r"screenflash_color\s*,\s*"
    r"screenflash_type\s*,\s*"
    r"screenflash_duration\s*,\s*"
    r"screenflash_starttime\s*,\s*"
    r"screenflash_worktime\s*\)\s*;",
    "XzAndroidRuntime_AuditLegacyPresentBeforeSwap(\n"
    "\t\t(unsigned int)glwidth,\n"
    "\t\t(unsigned int)glheight,\n"
    "\t\tscreenflash_color,\n"
    "\t\tscreenflash_type,\n"
    "\t\tscreenflash_duration,\n"
    "\t\tscreenflash_starttime,\n"
    "\t\tscreenflash_worktime,\n"
    "\t\tsv.time);",
    screen,
)

r_screen.write_text(screen, encoding="utf-8")

if screen.count('#include "../xz_android_runtime.h"') != 1:
    raise SystemExit("Visible present header injection count mismatch")
if screen.count("XZ_VISIBLE_PRESENT_COMPOSITE") != 1:
    raise SystemExit("Visible present composite injection count mismatch")
if screen.count("XzAndroidRuntime_AuditLegacyPresentBeforeSwap(") != 1:
    raise SystemExit("Pre-swap luma audit call count mismatch")
if new_preswap_call.strip() not in screen:
    raise SystemExit("Pre-swap luma audit call does not include server time")
if re.search(
    r"XzAndroidRuntime_AuditLegacyPresentBeforeSwap\([^;]*screenflash_worktime\s*\)\s*;",
    screen,
    flags=re.S,
):
    raise SystemExit("Legacy 7-argument pre-swap luma call survived normalization")
if screen.count("XZ_PRESENT_LUMA_PRESWAP") != 1:
    raise SystemExit("Pre-swap luma audit injection count mismatch")


# Validate the expected integration exactly once. Failing here is preferable to
# silently building an APK that is not actually collecting Phase-0 telemetry.
checks = {
    "runtime header": '#include "xz_android_runtime.h"',
    "bridge header": '#include "xz_vril_bridge.h"',
    "init": "XzAndroidRuntime_Init(heap_size);",
    "package promotion": "XzAndroidRuntime_SetVerifiedMapPackageMode(",
    "texture init": "XzTextureTap_Init();",
    "bridge init": "XzVrilBridge_Init();",
    "begin": "XzAndroidRuntime_BeginFrame(now);",
    "frame-counter snapshot": "int xz_frame_before = host_framecount;",
    "real first-frame gate": "xziel_first_frame && host_framecount != xz_frame_before",
    "capture": "XzVrilBridge_CapturePresentation(host_framecount);",
    "end": "XzAndroidRuntime_EndFrame(Sys_FloatTime());",
    "geometry begin": "XzGeometryTap_BeginFrame",
    "geometry commit": "XzGeometryTap_CommitFrame();",
    "bridge shutdown": "XzVrilBridge_Shutdown();",
    "shutdown": "XzAndroidRuntime_Shutdown();",
}
final = sys_sdl.read_text(encoding="utf-8")
for label, needle in checks.items():
    count = final.count(needle)
    if count != 1:
        raise SystemExit(
            f"Phase-0 integration check failed for {label}: {count} occurrences"
        )

print("Injected Xziel Xz runtime through Phase 16 + real geometry/texture/visible-present parity.")
