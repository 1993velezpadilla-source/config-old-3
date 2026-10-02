#!/usr/bin/env python3
from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_vril_sanctum_hq_lighting.py <vril-root>")

root = Path(sys.argv[1]).resolve()
p = root / "source/platform/sdl/gl/gl_xziel_staticmesh.c"
if not p.is_file():
    raise SystemExit(f"missing generated XZSM bridge: {p}")

s = p.read_text(encoding="utf-8")

# XZSM v2 lighting clamp: keep baked shading data sane even though the current
# visual gate renders full albedo first.
s = s.replace(
    "uint32_t i;\n    uint64_t seen_vertices",
    "uint32_t i, j;\n    uint64_t seen_vertices",
    1,
)

anchor = '''        if (!XZSM_ReadExact(f, b->vertices, sizeof(*b->vertices) * b->vertex_count) ||
            !XZSM_ReadExact(f, b->indices, sizeof(*b->indices) * b->index_count)) {
            fclose(f);
            Con_Printf("XZSM: truncated geometry in batch %u\\n", i);
            XZSM_Free();
            return false;
        }

        b->texture = Image_LoadImage(
'''
replacement = '''        if (!XZSM_ReadExact(f, b->vertices, sizeof(*b->vertices) * b->vertex_count) ||
            !XZSM_ReadExact(f, b->indices, sizeof(*b->indices) * b->index_count)) {
            fclose(f);
            Con_Printf("XZSM: truncated geometry in batch %u\\n", i);
            XZSM_Free();
            return false;
        }

        /* XZSM v2 baked vertex lighting: clamp the floor so later lighting
         * passes cannot crush photogrammetry detail to black on Android. */
        for (j = 0; j < b->vertex_count; ++j) {
            /* Preserve baked light intensity but remove scan-zone RGB casts
             * that were turning neutral stone blue/gray on Android. */
            unsigned int lum = ((unsigned int)b->vertices[j].r +
                                (unsigned int)b->vertices[j].g +
                                (unsigned int)b->vertices[j].b) / 3u;
            if (lum < 144u) lum = 144u;
            if (lum > 255u) lum = 255u;
            b->vertices[j].r = (unsigned char)lum;
            b->vertices[j].g = (unsigned char)lum;
            b->vertices[j].b = (unsigned char)lum;
            b->vertices[j].a = 255;
        }

        b->texture = Image_LoadImage(
'''
if anchor not in s:
    raise SystemExit("geometry load anchor not found")
s = s.replace(anchor, replacement, 1)

# Keep the HQ scan atlases at full-resolution level 0 instead of generating
# a mip chain that visibly softens the close-range stonework on mobile.
s = s.replace(
    '''        b->texture = Image_LoadImage(
            b->texture_name,
            IMAGE_PNG | IMAGE_TGA | IMAGE_JPG,
            0, true, true);''',
    '''        b->texture = Image_LoadImage(
            b->texture_name,
            IMAGE_PNG | IMAGE_TGA | IMAGE_JPG,
            0, false, true);''',
    1,
)

# Preserve enhanced photogrammetry albedo exactly for the visual gate.
s = s.replace(
'''    /* Preserve the photogrammetry albedo in the compatibility path. Lighting
     * belongs to Xziel's renderer; multiplying the scan by baked vertex color
     * here crushed stone/wood detail into black on Android. */
    glTexEnvf(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_REPLACE);

    glEnableClientState(GL_VERTEX_ARRAY);
    glEnableClientState(GL_TEXTURE_COORD_ARRAY);
''',
'''    /* HQ final path: 2K photogrammetry albedo multiplied by XZSM v2
     * baked vertex lighting. Texture loading is now fixed, so this restores
     * depth and atmosphere without the previous black-material failure. */
    glTexEnvf(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE);

    glEnableClientState(GL_VERTEX_ARRAY);
    glEnableClientState(GL_TEXTURE_COORD_ARRAY);
    glEnableClientState(GL_COLOR_ARRAY);
''',
1,
)

# Missing-texture fallback: bright magenta rather than silent black.
fallback_anchor = '''        if (b->texture >= 0)
            GL_Bind(b->texture);
        glVertexPointer(3, GL_FLOAT, sizeof(xzsm_vertex_t), &b->vertices[0].x);
        glTexCoordPointer(2, GL_FLOAT, sizeof(xzsm_vertex_t), &b->vertices[0].u);
        glDrawElements(GL_TRIANGLES, b->index_count, GL_UNSIGNED_SHORT, b->indices);
'''
fallback_repl = '''        if (b->texture >= 0) {
            glEnable(GL_TEXTURE_2D);
            GL_Bind(b->texture);
            glColor4f(1, 1, 1, 1);
        } else {
            glDisable(GL_TEXTURE_2D);
            glColor4f(1, 0, 1, 1);
        }
        glVertexPointer(3, GL_FLOAT, sizeof(xzsm_vertex_t), &b->vertices[0].x);
        glTexCoordPointer(2, GL_FLOAT, sizeof(xzsm_vertex_t), &b->vertices[0].u);
        glColorPointer(4, GL_UNSIGNED_BYTE, sizeof(xzsm_vertex_t), &b->vertices[0].r);
        glDrawElements(GL_TRIANGLES, b->index_count, GL_UNSIGNED_SHORT, b->indices);
        if (b->texture < 0) {
            glEnable(GL_TEXTURE_2D);
            glColor4f(1, 1, 1, 1);
        }
'''
if fallback_anchor not in s:
    raise SystemExit("missing-texture fallback anchor not found")
s = s.replace(fallback_anchor, fallback_repl, 1)

disable_anchor = '''    glDisableClientState(GL_TEXTURE_COORD_ARRAY);
    glDisableClientState(GL_VERTEX_ARRAY);
'''
disable_repl = '''    glDisableClientState(GL_COLOR_ARRAY);
    glDisableClientState(GL_TEXTURE_COORD_ARRAY);
    glDisableClientState(GL_VERTEX_ARRAY);
'''
if disable_anchor not in s:
    raise SystemExit("color-array disable anchor not found")
s = s.replace(disable_anchor, disable_repl, 1)

# Android diagnostics.
s = s.replace(
    '#include <string.h>\n',
    '#include <string.h>\n#if defined(__ANDROID__)\n#include <android/log.h>\n#endif\n',
    1,
)

tex_anchor = '''        if (b->texture < 0)
            Con_Printf("XZSM: missing texture %s\\n", b->texture_name);
'''
tex_repl = '''        if (b->texture < 0)
            Con_Printf("XZSM: missing texture %s\\n", b->texture_name);
#if defined(__ANDROID__)
        __android_log_print(
            b->texture < 0 ? ANDROID_LOG_ERROR : ANDROID_LOG_INFO,
            "XZIEL_XZSM",
            "texture[%u] handle=%d path=%s",
            i, b->texture, b->texture_name);
#endif
'''
if tex_anchor not in s:
    raise SystemExit("texture diagnostic anchor not found")
s = s.replace(tex_anchor, tex_repl, 1)

sum_anchor = '''    xzsm_loaded = true;
    Con_Printf("XZSM: Sanctum loaded batches=%u verts=%u indices=%u bytes=%d\\n",
        xzsm_batch_count, total_vertices, total_indices, file_len);
'''
sum_repl = '''    xzsm_loaded = true;
    Con_Printf("XZSM: Sanctum loaded batches=%u verts=%u indices=%u bytes=%d\\n",
        xzsm_batch_count, total_vertices, total_indices, file_len);
#if defined(__ANDROID__)
    __android_log_print(ANDROID_LOG_INFO, "XZIEL_XZSM",
        "loaded batches=%u verts=%u indices=%u bytes=%d",
        xzsm_batch_count, total_vertices, total_indices, file_len);
#endif
'''
if sum_anchor not in s:
    raise SystemExit("XZSM load summary anchor not found")
s = s.replace(sum_anchor, sum_repl, 1)

draw_anchor = '''    glEnable(GL_TEXTURE_2D);
    glEnable(GL_DEPTH_TEST);
    glDepthMask(GL_TRUE);
    glDisable(GL_BLEND);
    glDisable(GL_ALPHA_TEST);
    glDisable(GL_CULL_FACE);
    glColor4f(1, 1, 1, 1);
'''
draw_repl = '''    glEnable(GL_TEXTURE_2D);
    glEnable(GL_DEPTH_TEST);
    glDepthMask(GL_TRUE);
    glDisable(GL_BLEND);
    glDisable(GL_ALPHA_TEST);
    /* The source scan is consistently wound. Back-face culling removes
     * the thin reverse-facing photogrammetry shards visible around windows
     * and broken wall edges without touching gameplay collision. */
    glEnable(GL_CULL_FACE);
    glCullFace(GL_BACK);
    glFrontFace(GL_CCW);
#ifdef GL_FOG
    glDisable(GL_FOG);
#endif
#ifdef GL_LIGHTING
    glDisable(GL_LIGHTING);
#endif
    glColor4f(1, 1, 1, 1);
'''
if draw_anchor not in s:
    raise SystemExit("explicit GL state anchor not found")
s = s.replace(draw_anchor, draw_repl, 1)

loop_anchor = '''    for (i = 0; i < xzsm_batch_count; ++i) {
'''
loop_repl = '''#if defined(__ANDROID__)
    {
        static int xziel_xzsm_draw_reported = 0;
        if (!xziel_xzsm_draw_reported) {
            GLenum e = glGetError();
            __android_log_print(ANDROID_LOG_INFO, "XZIEL_XZSM",
                "first draw batches=%u glErrorBefore=0x%x",
                xzsm_batch_count, (unsigned)e);
            xziel_xzsm_draw_reported = 1;
        }
    }
#endif
    for (i = 0; i < xzsm_batch_count; ++i) {
'''
if loop_anchor not in s:
    raise SystemExit("draw loop diagnostic anchor not found")
s = s.replace(loop_anchor, loop_repl, 1)

# Fix 1: Image_LoadPixels used MAX_QPATH (64), truncating the extension-qualified
# St Giles atlas paths before COM_FOpenFile.
images = root / "source/images.c"
it = images.read_text(encoding="utf-8")
old = '''byte* Image_LoadPixels(char* filename, int image_format)
{
\tFILE\t*f;
\tchar name[MAX_QPATH];
'''
new = '''byte* Image_LoadPixels(char* filename, int image_format)
{
\tFILE\t*f;
\tchar name[MAX_OSPATH];
'''
if old not in it:
    raise SystemExit("Could not find Image_LoadPixels path buffer")
it = it.replace(old, new, 1)
images.write_text(it, encoding="utf-8")

# Fix 2: Android app-private basedir + the HQ texture path can exceed the
# legacy MAX_OSPATH=128 used by COM_FindFile. Expand it only in this HQ build.
defs = root / "source/nzportable_def.h"
dt = defs.read_text(encoding="utf-8")
dt, n = re.subn(
    r'(?m)^(\s*#define\s+MAX_OSPATH\s+)128(\b.*)$',
    r'\g<1>512\2',
    dt,
    count=1,
)
if n != 1:
    raise SystemExit("Could not find MAX_OSPATH definition")
defs.write_text(dt, encoding="utf-8")


# HQ sampling pass: stop feeding the 2K photogrammetry through Quake's
# default retro/1K path. Keep this scoped to the Sanctum HQ build.
gdraw = root / "source/platform/sdl/gl/gl_draw.c"
gt = gdraw.read_text(encoding="utf-8")
gt, n1 = re.subn(
    r'cvar_t\s+gl_max_size\s*=\s*\{"gl_max_size",\s*"1024"\};',
    'cvar_t\\t\\tgl_max_size = {"gl_max_size", "4096"};',
    gt,
    count=1,
)
gt, n2 = re.subn(
    r'int\s+gl_filter_min\s*=\s*GL_LINEAR_MIPMAP_NEAREST\s*;',
    'int\\t\\tgl_filter_min = GL_LINEAR_MIPMAP_LINEAR;',
    gt,
    count=1,
)
if n1 != 1 or n2 != 1:
    raise SystemExit(f"Could not patch HQ texture sampling defaults max={n1} filter={n2}")
gdraw.write_text(gt, encoding="utf-8")

# Disable the engine's intentionally pixelated presentation defaults for HQ.
rmain_defaults = root / "source/platform/sdl/gl/gl_rmain.c"
rd = rmain_defaults.read_text(encoding="utf-8")
rd, nr = re.subn(
    r'(cvar_t\s+r_retro\s*=\s*\{"r_retro",\s*)"1"(\s*,\s*true\};)',
    r'\g<1>"0"\g<2>',
    rd,
    count=1,
)
rd, nd = re.subn(
    r'(cvar_t\s+r_dithering\s*=\s*\{"r_dithering",\s*)"1"(\s*,\s*true\};)',
    r'\g<1>"0"\g<2>',
    rd,
    count=1,
)
if nr != 1 or nd != 1:
    raise SystemExit(f"Could not patch retro/dither defaults retro={nr} dither={nd}")
rmain_defaults.write_text(rd, encoding="utf-8")

# Even if a user config later toggles retro mode, the HQ church itself must use
# proper filtered sampling. Override immediately after each XZSM bind.
hq_bind = '''            GL_Bind(b->texture);
            glColor4f(1, 1, 1, 1);
'''
hq_bind_repl = '''            GL_Bind(b->texture);
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
            glColor4f(1, 1, 1, 1);
'''
if hq_bind not in s:
    raise SystemExit("Could not find XZSM texture bind for HQ sampling override")
s = s.replace(hq_bind, hq_bind_repl, 1)

p.write_text(s, encoding="utf-8")

# GL4ES-safe visual authority handoff: keep the BSP world pass for visibility
# and static-brush side effects, then erase its pixels/depth and draw XZSM.
rmain = root / "source/platform/sdl/gl/gl_rmain.c"
rt = rmain.read_text(encoding="utf-8")
old_block = '''\tif (Xziel_StaticMesh_Prepare())\n\t{\n\t\t// Sanctum: BSP remains the gameplay/visibility harness but is not\n\t\t// allowed to contribute color or depth. The HQ XZSM mesh is the\n\t\t// sole architectural visual authority.\n\t\tglColorMask(GL_FALSE, GL_FALSE, GL_FALSE, GL_FALSE);\n\t\tglDepthMask(GL_FALSE);\n\t\tR_DrawWorld ();\t\t// still adds static entities to the list\n\t\tglColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);\n\t\tglDepthMask(GL_TRUE);\n\t\tXziel_StaticMesh_Draw();\n\t}\n\telse\n\t{\n\t\tR_DrawWorld ();\t\t// normal NZ:P path\n\t}\n'''
new_block = '''\tif (Xziel_StaticMesh_Prepare())\n\t{\n\t\t// Run BSP for visibility/static-brush side effects, erase its visual\n\t\t// contribution, then make XZSM the visible architecture.\n\t\tR_DrawWorld ();\n\t\tglClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);\n\t\tglDepthRange(gldepthmin, gldepthmax);\n\t\tglDepthFunc(GL_LEQUAL);\n\t\tglDepthMask(GL_TRUE);\n\t\tglColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);\n\t\tXziel_StaticMesh_Draw();\n\t}\n\telse\n\t{\n\t\tR_DrawWorld ();\n\t}\n'''
if old_block not in rt:
    raise SystemExit("Could not find existing Sanctum color-mask hook")
rt = rt.replace(old_block, new_block, 1)
rmain.write_text(rt, encoding="utf-8")

print("Patched Sanctum HQ: 2K trilinear textures + baked vertex lighting + GL4ES-safe BSP erase.")
