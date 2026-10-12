#!/usr/bin/env python3
"""XZIEL native SDL/Vril alias-model HD limits (Android-only source patch).

Scoped to the pinned v0.26 Vril dependency in scripts/prepare_android.sh.
NO zombie asset conversion, no entity/AI/QuakeC changes, no other platforms.

Quake MDL v6 still stores each animated vertex as a compressed trivertx_t;
higher polygon budgets do not magically add PBR, bones, or HD UVs.
"""
from pathlib import Path
import argparse

HD_TAG = "XZIEL_ALIAS_HD_16K"
MAX_TRIANGLES = 16384
MAX_VERTICES = 16384
MAX_REORDERED = 3 * MAX_TRIANGLES
MAX_COMMAND_WORDS = 7 * MAX_TRIANGLES + 1

def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f"{label}: expected precisely 1 pinned source anchor, found {n}")
    return text.replace(old, new, 1)

def patch(root: Path):
    header = root / "source/platform/sdl/gl/gl_model.h"
    loader = root / "source/platform/sdl/gl/gl_model.c"
    mesh = root / "source/platform/sdl/gl/gl_mesh.c"
    batch = root / "source/render/r_mdl.c"
    for p in (header, loader, mesh, batch):
        if not p.is_file():
            raise FileNotFoundError(f"Required pinned Vril file missing: {p}")

    h = header.read_text()
    l = loader.read_text()
    m = mesh.read_text()
    b = batch.read_text()
    if HD_TAG in m:
        raise RuntimeError("Vril alias HD patch has already been applied")
    if "static unsigned short *r_alias_indices;" not in b:
        raise RuntimeError("Shared alias renderer index type changed; re-audit 16-bit index ceiling")
    assert MAX_REORDERED <= 65535, "Shared renderer indexes are 16-bit"

    h = replace_once(h, "#define\tMAXALIASVERTS\t2048",
                     "#define\tMAXALIASVERTS\t16384 /* XZIEL native Android HD alias */",
                     "SDL max MDL vertices")
    h = replace_once(h, "#define\tMAXALIASTRIS\t2048",
                     "#define\tMAXALIASTRIS\t16384 /* 3*triangles fits 16-bit index batch */",
                     "SDL max MDL triangles")

    # Validate the counts BEFORE indexing the fixed-size stverts/triangles/
    # poseverts globals, or sizing the variable-length alias header.
    l = replace_once(
        l,
        """\tsize = \tsizeof (aliashdr_t) 
\t\t\t+ (LittleLong (pinmodel->numframes) - 1) *
\t\t\tsizeof (pheader->frames[0]);""",
        """\t/* Reject corrupt frame counts before the flexible-header allocation. */
\tif (LittleLong(pinmodel->numframes) < 1 ||
\t    LittleLong(pinmodel->numframes) > MAXALIASFRAMES)
\t\tSys_Error("XZIEL HD alias: invalid frame count in %s", mod->name);
\tsize = \tsizeof (aliashdr_t) 
\t\t\t+ (LittleLong (pinmodel->numframes) - 1) *
\t\t\tsizeof (pheader->frames[0]);""",
        "alias header allocation")
    l = replace_once(
        l,
        """\tif (pheader->skinheight > MAX_LBM_HEIGHT)
\t\tSys_Error ("model %s has a skin taller than %d", mod->name,
\t\t\t\t   MAX_LBM_HEIGHT);""",
        """\t/* MDL-only: other LBM/PCX image formats keep their stock limits.
\t * GLES2 still needs a per-device texture-capability check at runtime.
\t * 2048x2048 indexed skin = at most 4 MiB per embedded skin. */
\tif (pheader->skinwidth <= 0 || pheader->skinheight <= 0 ||
\t    pheader->skinwidth > 2048 || pheader->skinheight > 2048)
\t\tSys_Error("XZIEL HD alias: invalid embedded skin size in %s", mod->name);""",
        "MDL embedded skin dimension")
    l = replace_once(
        l,
        """\tif (pheader->numtris <= 0)
\t\tSys_Error ("model %s has no triangles", mod->name);""",
        """\tif (pheader->numtris <= 0)
\t\tSys_Error ("model %s has no triangles", mod->name);
\tif (pheader->numtris > MAXALIASTRIS)
\t\tSys_Error("XZIEL HD alias: model %s exceeds %d triangles",
\t\t\tmod->name, MAXALIASTRIS);""",
        "triangle bounds guard")
    l = replace_once(
        l,
        """\tposeverts[posenum] = pinframe;
\tposenum++;""",
        """\tif (posenum >= MAXALIASFRAMES)
\t\tSys_Error("XZIEL HD alias: too many animation poses");
\tposeverts[posenum] = pinframe;
\tposenum++;""",
        "single-frame pose array guard")
    l = replace_once(
        l,
        """\tnumframes = LittleLong (pingroup->numframes);

\tframe->firstpose = posenum;""",
        """\tnumframes = LittleLong (pingroup->numframes);
\tif (numframes <= 0 || numframes > MAXALIASFRAMES - posenum)
\t\tSys_Error("XZIEL HD alias: group poses exceed %d", MAXALIASFRAMES);

\tframe->firstpose = posenum;""",
        "grouped-frame pose array guard")

    # Worst case: one GL_TRIANGLE_FAN for each triangle, i.e. 7 ints per
    # triangle (1 count, 6 UV values). Reordered vertices = max 3/triangle.
    # Those must BOTH be guarded; raising MAXALIASTRIS by itself corrupts RAM.
    m = replace_once(
        m,
        """qboolean\tused[8192];

// the command list holds counts and s/t values that are valid for
// every frame
int\t\tcommands[8192];
int\t\tnumcommands;

// all frames will have their vertexes rearranged and expanded
// so they are in the order expected by the command list
int\t\tvertexorder[8192];
int\t\tnumorder;""",
        """/* XZIEL_ALIAS_HD_16K: worst-case fan = 7 command ints per triangle,
 * and the shared renderer uses 16-bit vertex indices (3*16384 <= 65535).
 * Static globals: never allocate these buffers on the Android stack. */
#define XZIEL_ALIAS_HD_MAX_ORDER (MAXALIASTRIS * 3)
#define XZIEL_ALIAS_HD_MAX_COMMANDS (MAXALIASTRIS * 7 + 1)
qboolean used[MAXALIASTRIS];

// GL command words include signed primitive count + packed UV floats.
int commands[XZIEL_ALIAS_HD_MAX_COMMANDS];
int numcommands;

// Expands model vertices for fan/strip display lists.
int vertexorder[XZIEL_ALIAS_HD_MAX_ORDER];
int numorder;""",
        "native alias command/reorder buffers")
    m = replace_once(
        m,
        """int\t\tstripverts[128];
int\t\tstriptris[128];""",
        """int stripverts[MAXALIASTRIS + 2];
int striptris[MAXALIASTRIS];""",
        "strip scratch arrays")
    m = replace_once(
        m,
        """\tint\t\tbestverts[1024];
\tint\t\tbesttris[1024];""",
        """\t/* Static scratch, not a 128 KiB stack allocation on Android. */
\tstatic int bestverts[MAXALIASTRIS + 2];
\tstatic int besttris[MAXALIASTRIS];""",
        "best fan/strip scratch arrays")
    m = replace_once(
        m,
        """\tnumorder = 0;
\tnumcommands = 0;
\tmemset (used, 0, sizeof(used));""",
        """\tif (pheader->numtris <= 0 || pheader->numtris > MAXALIASTRIS ||
\t    pheader->numverts <= 0 || pheader->numverts > MAXALIASVERTS)
\t\tSys_Error("XZIEL HD alias: untrusted geometry bounds");
\tnumorder = 0;
\tnumcommands = 0;
\tmemset (used, 0, sizeof(used));""",
        "BuildTris model bounds")
    m = replace_once(
        m,
        """\t\tif (besttype == 1)
\t\t\tcommands[numcommands++] = (bestlen+2);""",
        """\t\t/* Reserve count + 2 UV ints per vertex + final zero marker.
\t\t * Precheck all writes before touching either fixed buffer. */
\t\tif (bestlen <= 0 || bestlen > pheader->numtris ||
\t\t    numcommands + 1 + 2 * (bestlen + 2) + 1 > XZIEL_ALIAS_HD_MAX_COMMANDS ||
\t\t    numorder + (bestlen + 2) > XZIEL_ALIAS_HD_MAX_ORDER)
\t\t\tSys_Error("XZIEL HD alias: command/reorder capacity exhausted");
\t\tif (besttype == 1)
\t\t\tcommands[numcommands++] = (bestlen+2);""",
        "before-command-write capacity precheck")
    # Already-compiled source only. Other platforms untouched and no changes
    # to build data, the custom zombie model, animations, gameplay or map.
    header.write_text(h)
    loader.write_text(l)
    mesh.write_text(m)
    print(f"{HD_TAG}_PATCHED vertices={MAX_VERTICES} triangles={MAX_TRIANGLES} "
          f"reorder={MAX_REORDERED} command_words={MAX_COMMAND_WORDS} "
          "embedded_skin_max=2048")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("vril_root", type=Path)
    args = p.parse_args()
    patch(args.vril_root)

if __name__ == "__main__":
    main()
