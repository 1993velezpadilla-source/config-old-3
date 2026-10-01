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
'''    /* HQ visual gate: preserve the enhanced photogrammetry albedo exactly.
     * Lighting will be layered after the real church is visually validated. */
    glTexEnvf(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_REPLACE);

    glEnableClientState(GL_VERTEX_ARRAY);
    glEnableClientState(GL_TEXTURE_COORD_ARRAY);
''',1)

s=s.replace(
'''        glVertexPointer(3, GL_FLOAT, sizeof(xzsm_vertex_t), &b->vertices[0].x);
        glTexCoordPointer(2, GL_FLOAT, sizeof(xzsm_vertex_t), &b->vertices[0].u);
        glDrawElements(GL_TRIANGLES, b->index_count, GL_UNSIGNED_SHORT, b->indices);
''',
'''        glVertexPointer(3, GL_FLOAT, sizeof(xzsm_vertex_t), &b->vertices[0].x);
        glTexCoordPointer(2, GL_FLOAT, sizeof(xzsm_vertex_t), &b->vertices[0].u);
        glDrawElements(GL_TRIANGLES, b->index_count, GL_UNSIGNED_SHORT, b->indices);
''',1)

s=s.replace(
'''    glDisableClientState(GL_TEXTURE_COORD_ARRAY);
    glDisableClientState(GL_VERTEX_ARRAY);
''',
'''    glDisableClientState(GL_TEXTURE_COORD_ARRAY);
    glDisableClientState(GL_VERTEX_ARRAY);
''',1)

p.write_text(s,encoding="utf-8")

// Replace the GL4ES-sensitive color-mask suppression hook with a robust
// two-stage compatibility path: let R_DrawWorld run for visibility/static
// brush side-effects, then clear its pixels/depth and draw the HQ XZSM before
// entity rendering. This keeps doors/zombies/HUD alive without exposing BSP.
rmain=root/"source/platform/sdl/gl/gl_rmain.c"
rt=rmain.read_text(encoding="utf-8")
old_block='''\tif (Xziel_StaticMesh_Prepare())\n\t{\n\t\t// Sanctum: BSP remains the gameplay/visibility harness but is not\n\t\t// allowed to contribute color or depth. The HQ XZSM mesh is the\n\t\t// sole architectural visual authority.\n\t\tglColorMask(GL_FALSE, GL_FALSE, GL_FALSE, GL_FALSE);\n\t\tglDepthMask(GL_FALSE);\n\t\tR_DrawWorld ();\t\t// still adds static entities to the list\n\t\tglColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);\n\t\tglDepthMask(GL_TRUE);\n\t\tXziel_StaticMesh_Draw();\n\t}\n\telse\n\t{\n\t\tR_DrawWorld ();\t\t// normal NZ:P path\n\t}\n'''
new_block='''\tif (Xziel_StaticMesh_Prepare())\n\t{\n\t\t// Run the BSP world pass for visibility/static-brush side effects.\n\t\t// Then erase BSP pixels/depth and make XZSM the visible architecture.\n\t\tR_DrawWorld ();\n\t\tglClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);\n\t\tglDepthRange(gldepthmin, gldepthmax);\n\t\tglDepthFunc(GL_LEQUAL);\n\t\tglDepthMask(GL_TRUE);\n\t\tglColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);\n\t\tXziel_StaticMesh_Draw();\n\t}\n\telse\n\t{\n\t\tR_DrawWorld ();\n\t}\n'''
if old_block not in rt:
    raise SystemExit("Could not find existing Sanctum color-mask hook")
rt=rt.replace(old_block,new_block,1)
rmain.write_text(rt,encoding="utf-8")

print("Patched Sanctum XZSM bridge for full photogrammetry albedo authority + GL4ES-safe BSP erase.")
