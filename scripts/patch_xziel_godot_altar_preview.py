#!/usr/bin/env python3
"""Opt-in Godot altar XZSM v3 preview inside native Xziel Dead Cell.

Run after prepare_android.sh creates and patches the pinned Vril sources, and
before Gradle builds. Original APK, Sanctum v2, all other maps stay untouched.
"""
from pathlib import Path
import sys

def once(s, old, new, label):
    count = s.count(old)
    if count != 1:
        raise SystemExit(f"Godot altar V3 {label}: expected one anchor, got {count}")
    return s.replace(old, new, 1)

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_xziel_godot_altar_preview.py <build/deps/vril>")
gl = Path(sys.argv[1]).resolve() / "source/platform/sdl/gl"
path = gl / "gl_xziel_staticmesh.c"
s = path.read_text(encoding="utf-8")
s = once(s, "#define XZSM_VERSION 2u\n", """#define XZSM_VERSION 2u
#define XZSM_ALTAR_VERSION 3u
/* Proof-only: center exported altar (-17.81, 15.82) at Quake (+220, 0).
 * Both the per-vertex data and AABB must be translated identically. */
#define XZSM_ALTAR_TX (220.0f + 17.81f * 39.3700787402f)
#define XZSM_ALTAR_TY (15.82f * 39.3700787402f)
""", "versions")
s = once(s, "static qboolean xzsm_authority_reported = false;\n",
"""static qboolean xzsm_authority_reported = false;
static uint32_t xzsm_file_version = 0;
/* 0 none, 1 Sanctum exclusive BSP replacement, 2 Godot altar overlay. */
static int xzsm_active_map = 0;
""", "preview state")
s = once(s, "    xzsm_authority_reported = false;\n}\n",
"    xzsm_authority_reported = false;\n    xzsm_file_version = 0;\n}\n", "cleanup")
s = once(s, """static qboolean XZSM_IsSanctum(void)
{
    if (!cl.worldmodel || !cl.worldmodel->name[0])
        return false;
    return strstr(cl.worldmodel->name, "sanctum_harness") != NULL;
}
""", """static int XZSM_DesiredMap(void)
{
    if (!cl.worldmodel || !cl.worldmodel->name[0])
        return 0;
    if (strstr(cl.worldmodel->name, "sanctum_harness"))
        return 1;
    if (strstr(cl.worldmodel->name, "xziel_proto"))
        return 2;
    return 0;
}
qboolean Xziel_StaticMesh_Exclusive(void)
{
    return xzsm_active_map == 1;
}
""", "map selection")
s = once(s, '    file_len = COM_FOpenFile("models/xziel/sanctum/sanctum.xzsm", &f);\n',
"""    file_len = COM_FOpenFile(
        xzsm_active_map == 2 ? "models/xziel/godot_altar/altar.xzsm" :
                               "models/xziel/sanctum/sanctum.xzsm", &f);
""", "asset lookup")
s = once(s, 'if (memcmp(magic, "XZSM", 4) || version != XZSM_VERSION ||\n',
'if (memcmp(magic, "XZSM", 4) ||\n        (version != XZSM_VERSION && !(xzsm_active_map == 2 && version == XZSM_ALTAR_VERSION)) ||\n', "v3 acceptance")
s = once(s, '    xzsm_batches = (xzsm_batch_t *)calloc(xzsm_batch_count, sizeof(*xzsm_batches));\n',
'    xzsm_file_version = version;\n    xzsm_batches = (xzsm_batch_t *)calloc(xzsm_batch_count, sizeof(*xzsm_batches));\n', "version persistence")
s = once(s, '        b->texture = Image_LoadImage(\n', """        if (xzsm_active_map == 2) {
            uint32_t vi;
            for (vi = 0; vi < b->vertex_count; ++vi) {
                b->vertices[vi].x += XZSM_ALTAR_TX;
                b->vertices[vi].y += XZSM_ALTAR_TY;
            }
            b->mins[0] += XZSM_ALTAR_TX;
            b->maxs[0] += XZSM_ALTAR_TX;
            b->mins[1] += XZSM_ALTAR_TY;
            b->maxs[1] += XZSM_ALTAR_TY;
        }
        b->texture = Image_LoadImage(
""", "placement and bounds")
s = once(s, '    Con_Printf("XZSM: Sanctum loaded batches=%u verts=%u indices=%u bytes=%d\\n",\n',
"""    Con_Printf(xzsm_active_map == 2 ?
        "XZSM: Godot altar V3 loaded batches=%u verts=%u indices=%u bytes=%d\\n" :
        "XZSM: Sanctum loaded batches=%u verts=%u indices=%u bytes=%d\\n",
""", "load log")
s = once(s, """    if (!XZSM_IsSanctum()) {
        if (xzsm_loaded || xzsm_attempted)
            XZSM_Free();
        return false;
    }
""", """    int desired_map = XZSM_DesiredMap();
    if (desired_map != xzsm_active_map) {
        XZSM_Free();
        xzsm_active_map = desired_map;
    }
    if (!desired_map)
        return false;
""", "map lifecycle")
s = once(s, """    if (xzsm_loaded && !xzsm_authority_reported) {
        Con_Printf("XZSM: HQ visual authority active; BSP render suppressed; vertex lighting v2\\n");
""", """    if (xzsm_loaded && !xzsm_authority_reported) {
        if (xzsm_active_map == 2)
            Con_Printf("XZSM: Godot altar V3 overlay active; per-vertex lighting; BSP retained\\n");
        else
            Con_Printf("XZSM: HQ visual authority active; BSP render suppressed; vertex lighting v2\\n");
""", "preview log")
s = once(s, """    glTexEnvf(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_REPLACE);

    glEnableClientState(GL_VERTEX_ARRAY);
    glEnableClientState(GL_TEXTURE_COORD_ARRAY);
""", """    glTexEnvf(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE,
        xzsm_file_version == XZSM_ALTAR_VERSION ? GL_MODULATE : GL_REPLACE);

    glEnableClientState(GL_VERTEX_ARRAY);
    glEnableClientState(GL_TEXTURE_COORD_ARRAY);
    if (xzsm_file_version == XZSM_ALTAR_VERSION)
        glEnableClientState(GL_COLOR_ARRAY);
""", "vertex-light GL state")
s = once(s, """        glTexCoordPointer(2, GL_FLOAT, sizeof(xzsm_vertex_t), &b->vertices[0].u);
        glDrawElements(GL_TRIANGLES, b->index_count, GL_UNSIGNED_SHORT, b->indices);
""", """        glTexCoordPointer(2, GL_FLOAT, sizeof(xzsm_vertex_t), &b->vertices[0].u);
        if (xzsm_file_version == XZSM_ALTAR_VERSION)
            glColorPointer(4, GL_UNSIGNED_BYTE, sizeof(xzsm_vertex_t), &b->vertices[0].r);
        glDrawElements(GL_TRIANGLES, b->index_count, GL_UNSIGNED_SHORT, b->indices);
""", "color pointer")
s = once(s, """    glDisableClientState(GL_TEXTURE_COORD_ARRAY);
    glDisableClientState(GL_VERTEX_ARRAY);
""", """    if (xzsm_file_version == XZSM_ALTAR_VERSION)
        glDisableClientState(GL_COLOR_ARRAY);
    glDisableClientState(GL_TEXTURE_COORD_ARRAY);
    glDisableClientState(GL_VERTEX_ARRAY);
""", "GL state restoration")
path.write_text(s, encoding="utf-8")

path = gl / "gl_rmain.c"
s = path.read_text(encoding="utf-8")
s = once(s, "qboolean Xziel_StaticMesh_Prepare(void);\n",
"qboolean Xziel_StaticMesh_Prepare(void);\nqboolean Xziel_StaticMesh_Exclusive(void);\n", "renderer prototype")
s = once(s, """\t\tglColorMask(GL_FALSE, GL_FALSE, GL_FALSE, GL_FALSE);
\t\tglDepthMask(GL_FALSE);
\t\tR_DrawWorld ();\t\t// still adds static entities to the list
\t\tglColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);
\t\tglDepthMask(GL_TRUE);
\t\tXziel_StaticMesh_Draw();
""", """\t\tif (Xziel_StaticMesh_Exclusive())
\t\t{
\t\t\t// Original Sanctum v2: suppress BSP color and depth.
\t\t\tglColorMask(GL_FALSE, GL_FALSE, GL_FALSE, GL_FALSE);
\t\t\tglDepthMask(GL_FALSE);
\t\t\tR_DrawWorld ();
\t\t\tglColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);
\t\t\tglDepthMask(GL_TRUE);
\t\t}
\t\telse
\t\t{
\t\t\t// Godot altar proof: keep Dead Cell BSP and collision visible.
\t\t\tR_DrawWorld ();
\t\t}
\t\tXziel_StaticMesh_Draw();
""", "BSP overlay")
path.write_text(s, encoding="utf-8")
print("XZIEL_GODOT_ALTAR_NATIVE_V3_PATCH_GREEN: opt-in map overlay")
