#!/usr/bin/env python3
"""XZIEL: optional 1024px PNG zombie skins, reversible PCX fallback.

SDL GL only. Does not alter QuakeC, AI, geometry, detachable limbs or animation.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_vril_zombie_hd_png.py <vril-root>")
root = Path(sys.argv[1]) / "source/platform/sdl/gl"
rmisc = root / "gl_rmisc.c"
rmain = root / "gl_rmain.c"
a = rmisc.read_text(encoding="utf8")
b = rmain.read_text(encoding="utf8")
old = "int zombie_skins[4];\n"
new = """int zombie_skins[4];
/* Missing HD texture (-1) always falls back to unmodified NZ:P skin. */
int xziel_zombie_hd_skins[4] = {-1, -1, -1, -1};
extern cvar_t r_zombie_hd;
"""
assert a.count(old) == 1, "R_InitOtherTextures skin array mismatch"
a = a.replace(old, new, 1)
old = '''\tzombie_skins[3] = Image_LoadImage ("models/ai/zfull.mdl_3", IMAGE_PCX, 0, true, false);
}'''
new = '''\tzombie_skins[3] = Image_LoadImage ("models/ai/zfull.mdl_3", IMAGE_PCX, 0, true, false);
    /* PNG filenames are new; the four original 128px PCX textures stay intact. */
    {
        int i;
        char texture_path[64];
        for (i = 0; i < 4; ++i) {
            snprintf(texture_path, sizeof(texture_path), "models/ai/xziel_zombie_hd_%d", i);
            xziel_zombie_hd_skins[i] = Image_LoadImage(
                texture_path, IMAGE_PNG, 0, true, true);
            Con_Printf("XZIEL_ZOMBIE_HD: skin=%d handle=%d stock=%d\\n",
                i, xziel_zombie_hd_skins[i], zombie_skins[i]);
        }
    }
}'''
assert a.count(old) == 1, "R_InitOtherTextures source anchor mismatch"
a = a.replace(old,new,1)
old = "\tCvar_RegisterVariable (&r_shadows);"
assert a.count(old) == 1, "R_Init cvar registration missing"
a = a.replace(old,old+"\n\tCvar_RegisterVariable (&r_zombie_hd);",1)
rmisc.write_text(a,encoding="utf8")

old = 'cvar_t\tr_shadows = {"r_shadows","0"};'
new = '''cvar_t\tr_shadows = {"r_shadows","0"};
/* A/B: 0=original 128 PCX, 1=generated 1024 PNG. */
cvar_t r_zombie_hd = {"r_zombie_hd", "1", true};
extern int xziel_zombie_hd_skins[4];'''
assert b.count(old) == 1, "Renderer cvar anchor missing"
b = b.replace(old,new,1)
old = '''\tif (specChar == '%')//Zombie body
\t{
\t\tswitch(e->skinnum)
\t\t{'''
new = '''\tif (specChar == '%')//Zombie body
\t{
        /* Full-body optimization and detachable limb path both use the same
         * bound zombie atlas. Skin indices and frame logic remain untouched. */
        if (r_zombie_hd.value > 0 && e->skinnum >= 0 && e->skinnum < 4 &&
            xziel_zombie_hd_skins[e->skinnum] >= 0) {
            GL_Bind(xziel_zombie_hd_skins[e->skinnum]);
        } else {
\t\tswitch(e->skinnum)
\t\t{'''
assert b.count(old) == 1, "Zombie body skin switch anchor missing"
b = b.replace(old,new,1)
old = '''\t\t\tdefault: //out of bounds? assuming 0
\t\t\t\tCon_Printf("Zombie tex out of bounds: Tex[%i]\\n",e->skinnum);
\t\t\t\tGL_Bind(zombie_skins[0]);
\t\t\t\tbreak;
\t\t}
\t}
\telse
\t{'''
new = '''\t\t\tdefault: //out of bounds? assuming 0
\t\t\t\tCon_Printf("Zombie tex out of bounds: Tex[%i]\\n",e->skinnum);
\t\t\t\tGL_Bind(zombie_skins[0]);
\t\t\t\tbreak;
\t\t}
        }
\t}
\telse
\t{'''
assert b.count(old) == 1, "Zombie PCX fallback block mismatch"
b = b.replace(old,new,1)
assert "void R_DrawZombieLimb (entity_t *e, int which)" in b
assert "R_SetupAliasBlendedFrame (currententity->frame, paliashdr, e)" in b
rmain.write_text(b,encoding="utf8")
print("XZIEL_ZOMBIE_HD_PNG_RENDERER_APPLIED_4_SKINS_WITH_ORIGINAL_FALLBACK")
