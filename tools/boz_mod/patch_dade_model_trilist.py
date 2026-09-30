#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_dade_model_trilist.py <dade-root>")

path = Path(sys.argv[1]).resolve() / "dade" / "marmalade" / "model.py"
text = path.read_text(encoding="utf-8")

old = """    n_idx = u16(t_block + 0x1A)
    n_idx -= n_idx % 3
    idx = [u16(t_block + 0x12 + i * 2) for i in range(n_idx)]
"""
new = """    # Real Marmalade CIwModelBlockGLTriList stores the u16 index count
    # at +0x0A. Public source/binary golden pairs confirm numTris * 3
    # lands here (e.g. 244 tris -> 732 / 0x02dc). +0x1A is already
    # inside the index stream for non-trivial meshes.
    n_idx = u16(t_block + 0x0A)
    n_idx -= n_idx % 3
    idx = [u16(t_block + 0x12 + i * 2) for i in range(n_idx)]
"""

if new in text:
    print("BOZ_DADE_TRILIST_PATCH_ALREADY_APPLIED")
elif old in text:
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("BOZ_DADE_TRILIST_PATCH_OK")
else:
    raise SystemExit("BOZ_DADE_TRILIST_PATCH_ANCHOR_NOT_FOUND")
