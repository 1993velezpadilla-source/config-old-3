#!/usr/bin/env python3
"""Extend stock XZIEL patched VRIL renderer to draw mini church GLB-derived XZSM
ON TOP of normal BSP architecture. Do not change legacy Sanctum behavior.
Called only for the opt-in CHURCH_MINI build.
"""
from pathlib import Path
import sys

root=Path(sys.argv[1]) if len(sys.argv)>1 else None
if root is None:
    raise SystemExit("usage: patch_vril_church_mini.py <vril-root>")
gl=root/"source/platform/sdl/gl"
file=gl/"gl_xziel_staticmesh.c"
renderer=gl/"gl_rmain.c"
s=file.read_text(encoding="utf-8")

# XZSM resources are entirely map-local; old Sanctum remains unchanged.
old='return strstr(cl.worldmodel->name, "sanctum_harness") != NULL;'
new='return strstr(cl.worldmodel->name, "sanctum_harness") != NULL || strstr(cl.worldmodel->name, "sanctum_mini") != NULL;'
if old not in s:
    raise SystemExit("Unexpected VRIL XZSM map selector; refusing unsafe patch")
s=s.replace(old,new,1)
old='file_len = COM_FOpenFile("models/xziel/sanctum/sanctum.xzsm", &f);'
new=('file_len = COM_FOpenFile(strstr(cl.worldmodel->name, "sanctum_mini") != NULL\n'
     '        ? "models/xziel/sanctum_mini/sanctum_mini.xzsm"\n'
     '        : "models/xziel/sanctum/sanctum.xzsm", &f);')
if old not in s:
    raise SystemExit("Cannot find static mesh loader anchor")
s=s.replace(old,new,1)
# CRITICAL: Image_LoadImage returns a HYENA logical texture INDEX,
# not an OpenGL GLuint. glBindTexture(index) drew the wrong atlas and made
# real Tripo objects look like torn black/orange mosaics.
# Hyena_BindTexture resolves registry index -> actual glTextureObject.
if s.count("GL_Bind(b->texture);") == 1:
    # Backward compatibility with earlier renderer templates.
    s=s.replace("GL_Bind(b->texture);", "Hyena_BindTexture(b->texture);", 1)
if s.count("Hyena_BindTexture(b->texture);") != 1:
    raise SystemExit("XZSM must bind via HYENA texture registry exactly once")
file.write_text(s,encoding="utf-8")

s=renderer.read_text(encoding="utf-8")
old='\tif (Xziel_StaticMesh_Prepare())\n\t{\n'
new=('\tif (cl.worldmodel && strstr(cl.worldmodel->name, "sanctum_mini") != NULL)\n'
     '\t{\n'
     '\t\t/* Quake BSP remains visible and authoritative in the mini scene. */\n'
     '\t\tR_DrawWorld();\n'
     '\t\tif (Xziel_StaticMesh_Prepare()) Xziel_StaticMesh_Draw();\n'
     '\t}\n'
     '\telse if (Xziel_StaticMesh_Prepare())\n\t{\n')
if s.count(old)!=1:
    raise SystemExit("Expected exactly one R_DrawWorld XZSM hook")
s=s.replace(old,new,1)
renderer.write_text(s,encoding="utf-8")
print("XZIEL_CHURCH_MINI_RENDER_PATCH_GREEN")
