#!/usr/bin/env python3
"""Prevent Vril alias command buffer OOB for animated HD-subdivided zombies.

Verified against the actual Quake MDL triangles:
zfull.mdl changes 484 -> 1936 faces. Engine produces 8713 draw command
integers but gl_mesh.c declares commands[8192], causing memory corruption.

Runtime cannot safely load improved geometry without this fix.
"""
from pathlib import Path
import sys
if len(sys.argv)!=2:raise SystemExit("usage: patch_vril_alias_command_capacity.py <vril-root>")
path=Path(sys.argv[1])/"source/platform/sdl/gl/gl_mesh.c"
s=path.read_text(encoding="utf8")
old="int\t\tcommands[8192];"
new="""/* XZIEL: worst-case with MAXALIASTRIS=2048 is 7*2048+1=14337,
 * because each triangle can become its own fan and generates 1+6 ints.
 * Original commands[8192] overflowed at 8713 on HD zombie zfull.mdl. */
#define XZIEL_ALIAS_COMMAND_CAPACITY 16384
int commands[XZIEL_ALIAS_COMMAND_CAPACITY];"""
assert s.count(old)==1,f"Unexpected Vril gl_mesh.c command buffer anchor ({s.count(old)})"
s=s.replace(old,new,1)
old="\t\tif (besttype == 1)\n\t\t\tcommands[numcommands++] = (bestlen+2);"
new="""        /* Check before writing *any* commands, including both ST values per
         * output vertex and the trailing end-of-list zero marker. */
        if (numcommands + 1 + 2*(bestlen+2) + 1 > XZIEL_ALIAS_COMMAND_CAPACITY)
            Sys_Error("XZIEL: alias GL commands exceeded safety buffer (%d)", numcommands);
\t\tif (besttype == 1)
\t\t\tcommands[numcommands++] = (bestlen+2);"""
assert s.count(old)==1,f"Unexpected BuildTris writer ({s.count(old)})"
s=s.replace(old,new,1)
# guard reordering too: maximum 3*MAXALIASTRIS=6144 <8192
assert "vertexorder[8192]" in s and "used[8192]" in s
assert "commands[numcommands++] = 0;" in s
path.write_text(s,encoding="utf8")
print("XZIEL_ALIAS_COMMANDS_SAFETY_GREEN: 8192 -> 16384 with bounds precheck")
