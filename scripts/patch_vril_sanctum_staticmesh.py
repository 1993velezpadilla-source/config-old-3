#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_vril_sanctum_staticmesh.py <vril-root>")

root = Path(sys.argv[1]).resolve()
source = root / "source"
gl_dir = source / "platform" / "sdl" / "gl"
if not gl_dir.is_dir():
    raise SystemExit(f"SDL GL directory missing: {gl_dir}")

c_path = gl_dir / "gl_xziel_staticmesh.c"
c_path.write_text(r'''// Xziel textured static-mesh bridge for Android/SDL.
// XZSM is intentionally tiny: fixed-layout textured triangle batches exported
// by the headless Blender church pipeline. BSP remains gameplay/collision.

#include "../../../nzportable_def.h"
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#ifdef __ANDROID__
#include <android/log.h>
#define XZLOG(...) __android_log_print(ANDROID_LOG_INFO, "XZIEL_XZSM", __VA_ARGS__)
#else
#define XZLOG(...) Con_Printf(__VA_ARGS__)
#endif

#define XZSM_VERSION 2u
#define XZSM_MAX_BATCHES 512u
#define XZSM_MAX_VERTICES 3000000u
#define XZSM_MAX_INDICES  3500000u

typedef struct {
    float x, y, z;
    float u, v;
    uint8_t r, g, b, a;
} xzsm_vertex_t;

/* XZSM v2 is written by Python as <5f4B: exactly 24 bytes/vertex. */
typedef char xzsm_vertex_stride_must_be_24[(sizeof(xzsm_vertex_t) == 24) ? 1 : -1];

typedef struct {
    uint32_t vertex_count;
    uint32_t index_count;
    char texture_name[96];
    vec3_t mins;
    vec3_t maxs;
    xzsm_vertex_t *vertices;
    uint16_t *indices;
    int texture;
} xzsm_batch_t;

static xzsm_batch_t *xzsm_batches = NULL;
static uint32_t xzsm_batch_count = 0;
static qboolean xzsm_loaded = false;
static qboolean xzsm_attempted = false;
static qboolean xzsm_authority_reported = false;
static qboolean xzsm_draw_logged = false;

extern cvar_t gl_cull;
extern qboolean R_CullBox(vec3_t mins, vec3_t maxs);

static void XZSM_Free(void)
{
    uint32_t i;
    if (xzsm_batches) {
        for (i = 0; i < xzsm_batch_count; ++i) {
            free(xzsm_batches[i].vertices);
            free(xzsm_batches[i].indices);
        }
        free(xzsm_batches);
    }
    xzsm_batches = NULL;
    xzsm_batch_count = 0;
    xzsm_loaded = false;
    xzsm_attempted = false;
    xzsm_authority_reported = false;
    xzsm_draw_logged = false;
}

static int XZSM_ReadExact(FILE *f, void *dst, size_t size)
{
    return fread(dst, 1, size, f) == size;
}

static qboolean XZSM_IsSanctum(void)
{
    if (!cl.worldmodel || !cl.worldmodel->name[0])
        return false;
    return strstr(cl.worldmodel->name, "sanctum_harness") != NULL;
}

static qboolean XZSM_LoadSanctum(void)
{
    FILE *f = NULL;
    int file_len;
    char magic[4];
    uint32_t version, total_vertices, total_indices;
    uint32_t i;
    uint64_t seen_vertices = 0, seen_indices = 0;

    xzsm_attempted = true;
    file_len = COM_FOpenFile("models/xziel/sanctum/sanctum.xzsm", &f);
    if (file_len < 20 || !f) {
        Con_Printf("XZSM: Sanctum mesh not found\n");
        return false;
    }

    if (!XZSM_ReadExact(f, magic, 4) ||
        !XZSM_ReadExact(f, &version, 4) ||
        !XZSM_ReadExact(f, &xzsm_batch_count, 4) ||
        !XZSM_ReadExact(f, &total_vertices, 4) ||
        !XZSM_ReadExact(f, &total_indices, 4)) {
        fclose(f);
        Con_Printf("XZSM: truncated header\n");
        XZSM_Free();
        return false;
    }

    if (memcmp(magic, "XZSM", 4) || version != XZSM_VERSION ||
        xzsm_batch_count == 0 || xzsm_batch_count > XZSM_MAX_BATCHES ||
        total_vertices > XZSM_MAX_VERTICES || total_indices > XZSM_MAX_INDICES) {
        fclose(f);
        Con_Printf("XZSM: invalid header v%u batches=%u verts=%u idx=%u\n",
            version, xzsm_batch_count, total_vertices, total_indices);
        XZSM_Free();
        return false;
    }

    xzsm_batches = (xzsm_batch_t *)calloc(xzsm_batch_count, sizeof(*xzsm_batches));
    if (!xzsm_batches) {
        fclose(f);
        Sys_Error("XZSM: out of memory for batches");
        return false;
    }

    for (i = 0; i < xzsm_batch_count; ++i) {
        xzsm_batch_t *b = &xzsm_batches[i];
        if (!XZSM_ReadExact(f, &b->vertex_count, 4) ||
            !XZSM_ReadExact(f, &b->index_count, 4) ||
            !XZSM_ReadExact(f, b->texture_name, sizeof(b->texture_name)) ||
            !XZSM_ReadExact(f, b->mins, sizeof(float) * 3) ||
            !XZSM_ReadExact(f, b->maxs, sizeof(float) * 3)) {
            fclose(f);
            Con_Printf("XZSM: truncated batch header %u\n", i);
            XZSM_Free();
            return false;
        }

        b->texture_name[sizeof(b->texture_name) - 1] = 0;
        if (!b->vertex_count || b->vertex_count > 65535u ||
            !b->index_count || b->index_count > 65535u) {
            fclose(f);
            Con_Printf("XZSM: invalid batch %u verts=%u idx=%u\n",
                i, b->vertex_count, b->index_count);
            XZSM_Free();
            return false;
        }

        seen_vertices += b->vertex_count;
        seen_indices += b->index_count;
        if (seen_vertices > total_vertices || seen_indices > total_indices) {
            fclose(f);
            Con_Printf("XZSM: batch totals overflow header\n");
            XZSM_Free();
            return false;
        }

        b->vertices = (xzsm_vertex_t *)malloc(sizeof(*b->vertices) * b->vertex_count);
        b->indices = (uint16_t *)malloc(sizeof(*b->indices) * b->index_count);
        if (!b->vertices || !b->indices) {
            fclose(f);
            Sys_Error("XZSM: out of memory for geometry");
            return false;
        }
        if (!XZSM_ReadExact(f, b->vertices, sizeof(*b->vertices) * b->vertex_count) ||
            !XZSM_ReadExact(f, b->indices, sizeof(*b->indices) * b->index_count)) {
            fclose(f);
            Con_Printf("XZSM: truncated geometry in batch %u\n", i);
            XZSM_Free();
            return false;
        }

        b->texture = Image_LoadImage(
            b->texture_name,
            IMAGE_PNG | IMAGE_TGA | IMAGE_JPG,
            0, true, true);
        XZLOG("load batch=%u name=%s tex=%d", i, b->texture_name, b->texture);
        if (b->texture < 0) {
            Con_Printf("XZSM: missing texture %s\n", b->texture_name);
            XZLOG("MISSING batch=%u name=%s", i, b->texture_name);
        }
    }

    fclose(f);
    if (seen_vertices != total_vertices || seen_indices != total_indices) {
        Con_Printf("XZSM: total mismatch verts=%u/%u idx=%u/%u\n",
            (unsigned)seen_vertices, total_vertices,
            (unsigned)seen_indices, total_indices);
        XZSM_Free();
        return false;
    }

    xzsm_loaded = true;
    Con_Printf("XZSM: Sanctum loaded batches=%u verts=%u indices=%u bytes=%d\n",
        xzsm_batch_count, total_vertices, total_indices, file_len);
    return true;
}

qboolean Xziel_StaticMesh_Prepare(void)
{
    if (!XZSM_IsSanctum()) {
        if (xzsm_loaded || xzsm_attempted)
            XZSM_Free();
        return false;
    }

    if (!xzsm_loaded && !xzsm_attempted)
        XZSM_LoadSanctum();

    if (xzsm_loaded && !xzsm_authority_reported) {
        Con_Printf("XZSM: HQ visual authority active; BSP render suppressed; vertex lighting v2\n");
        xzsm_authority_reported = true;
    }

    return xzsm_loaded;
}

void Xziel_StaticMesh_Draw(void)
{
    uint32_t i;

    if (!Xziel_StaticMesh_Prepare())
        return;

    glEnable(GL_TEXTURE_2D);
    glEnable(GL_DEPTH_TEST);
    glDepthMask(GL_TRUE);
    glDisable(GL_BLEND);
    glDisable(GL_ALPHA_TEST);
    glDisable(GL_CULL_FACE);
    glColor4f(1, 1, 1, 1);
    /* Preserve the photogrammetry albedo in the compatibility path. Lighting
     * belongs to Xziel's renderer; multiplying the scan by baked vertex color
     * here crushed stone/wood detail into black on Android. */
    glTexEnvf(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_REPLACE);

    glEnableClientState(GL_VERTEX_ARRAY);
    glEnableClientState(GL_TEXTURE_COORD_ARRAY);

    for (i = 0; i < xzsm_batch_count; ++i) {
        xzsm_batch_t *b = &xzsm_batches[i];
        if (R_CullBox(b->mins, b->maxs))
            continue;
        if (!xzsm_draw_logged)
            XZLOG("draw batch=%u name=%s tex=%d", i, b->texture_name, b->texture);
        if (b->texture >= 0)
            GL_Bind(b->texture);
        glVertexPointer(3, GL_FLOAT, sizeof(xzsm_vertex_t), &b->vertices[0].x);
        glTexCoordPointer(2, GL_FLOAT, sizeof(xzsm_vertex_t), &b->vertices[0].u);
        glDrawElements(GL_TRIANGLES, b->index_count, GL_UNSIGNED_SHORT, b->indices);
    }

    xzsm_draw_logged = true;
    glDisableClientState(GL_TEXTURE_COORD_ARRAY);
    glDisableClientState(GL_VERTEX_ARRAY);
    if (gl_cull.value)
        glEnable(GL_CULL_FACE);
    glColor4f(1, 1, 1, 1);
    glTexEnvf(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_REPLACE);
}
''', encoding="utf-8")

rmain = gl_dir / "gl_rmain.c"
text = rmain.read_text(encoding="utf-8")

protos = (
    "qboolean Xziel_StaticMesh_Prepare(void);\n"
    "void Xziel_StaticMesh_Draw(void);\n"
)
include_anchor = '#include "../../../nzportable_def.h"\n'
if "qboolean Xziel_StaticMesh_Prepare(void);" not in text:
    if include_anchor not in text:
        raise SystemExit("Could not find gl_rmain include anchor")
    text = text.replace(include_anchor, include_anchor + "\n" + protos, 1)

old = "\tR_DrawWorld ();\t\t// adds static entities to the list\n"
new = (
    "\tif (Xziel_StaticMesh_Prepare())\n"
    "\t{\n"
    "\t\t// Sanctum: BSP remains the gameplay/visibility harness but is not\n"
    "\t\t// allowed to contribute color or depth. The HQ XZSM mesh is the\n"
    "\t\t// sole architectural visual authority.\n"
    "\t\tglColorMask(GL_FALSE, GL_FALSE, GL_FALSE, GL_FALSE);\n"
    "\t\tglDepthMask(GL_FALSE);\n"
    "\t\tR_DrawWorld ();\t\t// still adds static entities to the list\n"
    "\t\tglColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);\n"
    "\t\tglDepthMask(GL_TRUE);\n"
    "\t\tXziel_StaticMesh_Draw();\n"
    "\t}\n"
    "\telse\n"
    "\t{\n"
    "\t\tR_DrawWorld ();\t\t// normal NZ:P path\n"
    "\t}\n"
)
if "sole architectural visual authority" not in text:
    if old not in text:
        raise SystemExit("Could not find R_DrawWorld hook")
    text = text.replace(old, new, 1)

rmain.write_text(text, encoding="utf-8")
print("Patched Vril SDL renderer with XZSM Sanctum static-mesh bridge.")
