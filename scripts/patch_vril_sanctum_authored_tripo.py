#!/usr/bin/env python3
"""Map-specific native overlay: draw the REAL Sanctum authored BSP and original
Tripo bench/altar XZSM on top, without changing Church Mini or Sanctum Harness.

Requires patch_vril_church_mini.py to have already patched the SDL renderer.
"""
import sys
from pathlib import Path
if len(sys.argv)!=2:
    raise SystemExit("usage: patch_vril_sanctum_authored_tripo.py <vril-root>")
gl=Path(sys.argv[1])/"source/platform/sdl/gl"
mesh=gl/"gl_xziel_staticmesh.c"
draw=gl/"gl_rmain.c"
s=mesh.read_text(encoding="utf-8")
old='return strstr(cl.worldmodel->name, "sanctum_harness") != NULL || strstr(cl.worldmodel->name, "sanctum_mini") != NULL;'
new='return strstr(cl.worldmodel->name, "sanctum_harness") != NULL || strstr(cl.worldmodel->name, "sanctum_mini") != NULL || strstr(cl.worldmodel->name, "sanctum_authored") != NULL;'
if s.count(old)!=1:
    raise RuntimeError("XZSM recognized map selector changed")
s=s.replace(old,new,1)
old='file_len = COM_FOpenFile(strstr(cl.worldmodel->name, "sanctum_mini") != NULL\n        ? "models/xziel/sanctum_mini/sanctum_mini.xzsm"\n        : "models/xziel/sanctum/sanctum.xzsm", &f);'
new='file_len = COM_FOpenFile(strstr(cl.worldmodel->name, "sanctum_authored") != NULL\n        ? "models/xziel/sanctum_ash_tripo/sanctum_ash_tripo.xzsm"\n        : strstr(cl.worldmodel->name, "sanctum_mini") != NULL\n        ? "models/xziel/sanctum_mini/sanctum_mini.xzsm"\n        : "models/xziel/sanctum/sanctum.xzsm", &f);'
if s.count(old)!=1:
    raise RuntimeError("XZSM original model path changed")
s=s.replace(old,new,1)
# Never bypass Hyena registry's native ID -> OpenGL texture handle mapping.
if s.count("Hyena_BindTexture(b->texture);")!=1:
    raise RuntimeError("Expected texture binding fix missing")
mesh.write_text(s,encoding="utf-8")
s=draw.read_text(encoding="utf-8")
old='if (cl.worldmodel && strstr(cl.worldmodel->name, "sanctum_mini") != NULL)'
new='if (cl.worldmodel && (strstr(cl.worldmodel->name, "sanctum_mini") != NULL ||\n        strstr(cl.worldmodel->name, "sanctum_authored") != NULL))'
if s.count(old)!=1:
    raise RuntimeError("Expected mini overlay hook missing")
s=s.replace(old,new,1)
draw.write_text(s,encoding="utf-8")
print("XZIEL_SANCTUM_AUTHORED_ORIGINAL_BSP_PLUS_TRIPO_OVERLAY_GREEN")
