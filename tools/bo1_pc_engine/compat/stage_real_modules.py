#!/usr/bin/env python3
"""Stages pinned upstream *real* BO1 files, replacing only Windows-only includes.
Never copies any upstream source to the public Git repository or artifact.
"""
import argparse
import hashlib
import json
from pathlib import Path

PINNED = "102f6992be332610aff587e681e3180b15f395bb"
ORIGINALS = {
    "orientation": ("src/universal/com_math_anglevectors.cpp", ('#include "q_shared.h"',)),
    "packed_assets": ("src/universal/com_pack.cpp", ('#include "com_math.h"', '#include "q_shared.h"')),
    "compression": ("src/minilzo/minilzo.cpp", ()),
}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--upstream", required=True)
    p.add_argument("--staged", required=True)
    a = p.parse_args()
    root, out = Path(a.upstream), Path(a.staged)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"upstream_sha": PINNED, "scope": "3 real source translation units",
                "all_function_bodies_preserved": True, "files": {}}
    for key, (rel, includes) in ORIGINALS.items():
        src = root / rel
        original = src.read_bytes()
        try:
            text = original.decode("utf-8")
        except UnicodeDecodeError:
            text = original.decode("cp1252")
        compiled = text
        replacements = []
        for idx, include in enumerate(includes):
            assert compiled.count(include) == 1, f"Upstream unexpectedly changed {rel}"
            replacement = f"// BO1_ARM64_DEPENDENCY_ONLY_{key}_{idx}"
            compiled = compiled.replace(include, replacement)
            replacements.append((include,replacement))
        restored = compiled
        for include,replacement in reversed(replacements):
            restored = restored.replace(replacement,include)
        assert restored == text, f"Unintended body edits in {rel}"
        name = src.name
        (out / name).write_text(compiled)
        manifest["files"][key] = {"source": rel, "original_sha256": hashlib.sha256(original).hexdigest(),
             "removed_includes_only": list(includes), "function_bodies_modified": False}
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("STAGED_UPSTREAM_3_MODULES_NO_BODY_REWRITE=PASS")
    print("ORIGINAL_BO1_FUNCTION_BODIES_PRESERVED=PASS")
if __name__=="__main__":
    main()
