#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_vril_sanctum_hq_lighting.py <vril-root>")

root=Path(sys.argv[1]).resolve()
p=root/"source/platform/sdl/gl/gl_xziel_staticmesh.c"
if not p.is_file():
    raise SystemExit(f"missing generated XZSM bridge: {p}")

s=p.read_text(encoding="utf-8")

s=s.replace("uint32_t i;\n    uint64_t seen_vertices", "uint32_t i, j;\n    uint64_t seen_vertices", 1)

anchor='''        if (!XZSM_ReadExact(f, b->vertices, sizeof(*b->vertices) * b->vertex_count) ||
            !XZSM_ReadExact(f, b->indices, sizeof(*b->indices) * b->index_count)) {
            fclose(f);
            Con_Printf("XZSM: truncated geometry in batch %u\\n", i);
            XZSM_Free();
            return false;
        }

        b->texture = Image_LoadImage(
'''
replacement='''        if (!XZSM_ReadExact(f, b->vertices, sizeof(*b->vertices) * b->vertex_count) ||
            !XZSM_ReadExact(f, b->indices, sizeof(*b->indices) * b->index_count)) {
            fclose(f);
            Con_Printf("XZSM: truncated geometry in batch %u\\n", i);
            XZSM_Free();
            return false;
        }

        /* XZSM v2 contains baked per-vertex lighting from the Blender church
         * authoring pass. Keep the dark horror shaping, but clamp the floor
         * so Android/GL4ES never crushes photogrammetry texture detail to black. */
        for (j = 0; j < b->vertex_count; ++j) {
            if (b->vertices[j].r < 112) b->vertices[j].r = 112;
            if (b->vertices[j].g < 112) b->vertices[j].g = 112;
            if (b->vertices[j].b < 112) b->vertices[j].b = 112;
            b->vertices[j].a = 255;
        }

        b->texture = Image_LoadImage(
'''
if anchor not in s:
    raise SystemExit("geometry load anchor not found")
s=s.replace(anchor,replacement,1)

s=s.replace(
'''    /* Preserve the photogrammetry albedo in the compatibility path. Lighting
     * belongs to Xziel's renderer; multiplying the scan by baked vertex color
     * here crushed stone/wood detail into black on Android. */
    glTexEnvf(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_REPLACE);

    glEnableClientState(GL_VERTEX_ARRAY);
    glEnableClientState(GL_TEXTURE_COORD_ARRAY);
''',
'''    /* HQ compatibility path: 2K photogrammetry albedo multiplied by the
     * clamped XZSM v2 baked vertex-light term. This gives depth and atmosphere
     * without sacrificing mobile texture detail. */
    glTexEnvf(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE);

    glEnableClientState(GL_VERTEX_ARRAY);
    glEnableClientState(GL_TEXTURE_COORD_ARRAY);
    glEnableClientState(GL_COLOR_ARRAY);
''',1)

s=s.replace(
'''        glVertexPointer(3, GL_FLOAT, sizeof(xzsm_vertex_t), &b->vertices[0].x);
        glTexCoordPointer(2, GL_FLOAT, sizeof(xzsm_vertex_t), &b->vertices[0].u);
        glDrawElements(GL_TRIANGLES, b->index_count, GL_UNSIGNED_SHORT, b->indices);
''',
'''        glVertexPointer(3, GL_FLOAT, sizeof(xzsm_vertex_t), &b->vertices[0].x);
        glTexCoordPointer(2, GL_FLOAT, sizeof(xzsm_vertex_t), &b->vertices[0].u);
        glColorPointer(4, GL_UNSIGNED_BYTE, sizeof(xzsm_vertex_t), &b->vertices[0].r);
        glDrawElements(GL_TRIANGLES, b->index_count, GL_UNSIGNED_SHORT, b->indices);
''',1)

s=s.replace(
'''    glDisableClientState(GL_TEXTURE_COORD_ARRAY);
    glDisableClientState(GL_VERTEX_ARRAY);
''',
'''    glDisableClientState(GL_COLOR_ARRAY);
    glDisableClientState(GL_TEXTURE_COORD_ARRAY);
    glDisableClientState(GL_VERTEX_ARRAY);
''',1)

p.write_text(s,encoding="utf-8")
print("Patched Sanctum XZSM bridge for clamped baked vertex lighting + 2K albedo modulation.")
