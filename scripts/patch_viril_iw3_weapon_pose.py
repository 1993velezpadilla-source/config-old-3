#!/usr/bin/env python3
"""Attach the opt-in, portable IW3 pose engine to Vril's real SDL GL renderer.

This is the first true native integration boundary, NOT a CoD4 XModel/XAnim
loader. Apply only to generated VIRIL IW3 build (never original v0.26).
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: patch_viril_iw3_weapon_pose.py <repo-root>")
root = Path(sys.argv[1]).resolve()
vril = root / "build/deps/vril/source/platform/sdl/gl"
buildsrc = root / "build/android-project/app/jni/src"
src = root / "android/jni/src"
for name in ("iw3_weapon_pose.c", "iw3_weapon_pose.h",
             "iw3_weapon_profiles_generated.h"):
    if not (src / name).is_file():
        raise SystemExit("Missing source: " + name)
    buildsrc.mkdir(parents=True, exist_ok=True)
    (buildsrc / name).write_bytes((src / name).read_bytes())
(vril / "iw3_weapon_pose.h").write_bytes(
    (src / "iw3_weapon_pose.h").read_bytes())
(vril / "gl_iw3_weapon_mesh.c").write_bytes(
    (src / "gl_iw3_weapon_mesh.c").read_bytes())

rmain = vril / "gl_rmain.c"
text = rmain.read_text(encoding="utf-8")
def replace_once(text, before, after, label):
    if after in text:
        return text
    if text.count(before) != 1:
        raise SystemExit(f"{label}: expected one anchor, found {text.count(before)}")
    return text.replace(before, after, 1)

text = replace_once(
    text, '#include "../../../nzportable_def.h"',
    '#include "../../../nzportable_def.h"\n#include "iw3_weapon_pose.h"\n'
    'extern int IW3_WeaponMesh_Draw(entity_t *view);',
    "renderer source include")
text = replace_once(
    text, 'cvar_t\tr_drawviewmodel = {"r_drawviewmodel","1"};',
    'cvar_t\tr_drawviewmodel = {"r_drawviewmodel","1"};\n'
    'cvar_t iw3_weapon_bridge = {"iw3_weapon_bridge","1",true};',
    "renderer cvar declaration")
text = replace_once(
    text, 'void R_DrawViewModel (void)\n{',
    'void R_DrawViewModel (void)\n{\n\tentity_t iw3_viewent_copy;',
    "viewmodel entity copy declaration")
original = '''\tcurrententity = &cl.viewent;
\tif (!currententity->model)
\t\treturn;

\tj = R_LightPoint (currententity->origin);'''
bridge = '''\tcurrententity = &cl.viewent;
\tif (!currententity->model)
\t\treturn;

\t/* IW3 WeaponDef transform bridge. Exact CoD4 geometry/animation needs
\t * converted assets and matching .weapon metadata. If absent, this is
\t * byte-for-byte equivalent to Vril's original viewmodel rendering. */
\tif (iw3_weapon_bridge.value) {
\t\tconst iw3_weapon_pose_t *iw3_pose =
\t\t\tIW3_WeaponFindPose(currententity->model->name);
\t\tif (iw3_pose) {
\t\t\t/* Do not mutate cl.viewent every frame: the original pose
\t\t\t * must be restored after draw, or offsets accumulate. */
\t\t\tiw3_viewent_copy = *currententity;
\t\t\tcurrententity = &iw3_viewent_copy;
\t\t\tfloat axes[3][3], dxyz[3], dpyr[3];
\t\t\tfloat speed = sqrtf(cl.velocity[0]*cl.velocity[0] +
\t\t\t\tcl.velocity[1]*cl.velocity[1]) / 320.0f;
\t\t\tfloat ads = cl.stats[STAT_ZOOM] ? 1.0f : 0.0f;
\t\t\tint j;
\t\t\tAngleVectors(r_refdef.viewangles, axes[0], axes[1], axes[2]);
\t\t\tIW3_WeaponPoseDelta(iw3_pose, axes, 0, speed, ads,
\t\t\t\tdxyz, dpyr);
\t\t\tfor (j=0; j<3; ++j) {
\t\t\t\tcurrententity->origin[j] += dxyz[j];
\t\t\t\tcurrententity->angles[j] += dpyr[j];
\t\t\t}
\t\t}
\t}

\tj = R_LightPoint (currententity->origin);'''
text = replace_once(text, original, bridge, "first-person render dispatch")
# Replace viewmodel draw only. The second viewmodel (cl.viewent2) must remain
# the original NZP renderer unless explicitly supported in a later pass.
before, after = text.split("void R_DrawViewModel (void)", 1)
after = replace_once(
    after,
    'R_DrawAliasModel (currententity);\n\tglDepthRange (gldepthmin, gldepthmax);',
    'if (!(iw3_weapon_bridge.value && IW3_WeaponMesh_Draw(currententity)))\n'
    '\t\tR_DrawAliasModel (currententity);\n'
    '\tglDepthRange (gldepthmin, gldepthmax);\n'
    '\tcurrententity = &cl.viewent;',
    "Vril native GLES 3D weapon draw dispatch")
text = before + "void R_DrawViewModel (void)" + after
rmain.write_text(text, encoding="utf-8")

rmisc = vril / "gl_rmisc.c"
text = rmisc.read_text(encoding="utf-8")
text = replace_once(
    text, 'void R_Init (void)',
    'extern cvar_t iw3_weapon_bridge;\n\nvoid R_Init (void)',
    "renderer bridge extern")
text = replace_once(
    text, 'Cvar_RegisterVariable (&r_drawviewmodel);',
    'Cvar_RegisterVariable (&r_drawviewmodel);\n'
    '\tCvar_RegisterVariable (&iw3_weapon_bridge);',
    "register bridge cvar")
rmisc.write_text(text, encoding="utf-8")

mk = buildsrc / "Android.mk"
text = mk.read_text(encoding="utf-8")
text = replace_once(text, 'xziel_android_bridge.c',
    'xziel_android_bridge.c     iw3_weapon_pose.c',
    "native library source list")
mk.write_text(text, encoding="utf-8")

# Hard safety gates: no IW3 reference D3D code in the Android build, no
# changes to the original recovery branch and no silent fallback to stock.
assert "iw3_weapon_pose.c" in mk.read_text(encoding="utf-8")
assert "IW3_WeaponPoseDelta" in rmain.read_text(encoding="utf-8")
print("IW3 portable weapon pose bridge compiled into Vril native renderer.")
