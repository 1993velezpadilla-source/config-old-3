#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_dade_boz_resgroup.py <dade-root>")

root = Path(sys.argv[1]).resolve()
path = root / "dade" / "marmalade" / "resgroup.py"
text = path.read_text(encoding="utf-8")

old = """        elif section_hash == _H_RESOURCES:
            resources = _parse_resources(payload)
        else:
            log.debug('Skipping unrecognised section %#010x (%d bytes).', section_hash, size)
"""

new = """        elif section_hash == _H_RESOURCES:
            resources = _parse_resources(payload)
            # BOZ Android's ResourceObjects block stores a virtual/managed
            # length that can exceed the serialized .group.bin byte length.
            # The resource table itself is self-sized per object and this is
            # the terminal data block, so do not seek using that outer length.
            break
        else:
            log.debug('Skipping unrecognised section %#010x (%d bytes).', section_hash, size)
"""

if new in text:
    print("BOZ_DADE_RESGROUP_PATCH_ALREADY_APPLIED")
elif old in text:
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("BOZ_DADE_RESGROUP_PATCH_OK")
else:
    raise SystemExit("BOZ_DADE_RESGROUP_PATCH_ANCHOR_NOT_FOUND")
