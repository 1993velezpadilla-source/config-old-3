#!/usr/bin/env python3
from pathlib import Path
import sys

ROOTS = [
    Path("engine/xz"),
    Path("android"),
    Path("scripts"),
    Path("tools/maps"),
    Path("assets"),
]

SELF = Path("scripts/check_no_legacy_runtime.py")

BANNED_PATH = (
    "quake",
    "vril",
    "nzp",
    "nzportable",
)

BANNED_TEXT = (
    "quake",
    "vril",
    "nzp",
    "nzportable",
    "gl4es",
    "com_openfile",
    "com_closefile",
    "sys_fileread",
    "sys_fileseek",
    "host_frame",
    "cl_visedicts",
    "r_origin",
    "r_refdef",
    "glquake",
    "progs.dat",
    "ndu.bsp",
)

TEXT_SUFFIXES = {
    ".c", ".h", ".cpp", ".hpp", ".cc",
    ".java", ".kt", ".xml", ".gradle",
    ".mk", ".sh", ".py", ".json", ".yml", ".yaml",
}

failures = []

for root in ROOTS:
    if not root.exists():
        continue
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path == SELF:
            continue

        lower_path = path.as_posix().lower()
        for token in BANNED_PATH:
            if token in lower_path:
                failures.append(f"PATH {path}: contains forbidden token {token!r}")

        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"Android.mk", "Application.mk"}:
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        lower = text.lower()
        for token in BANNED_TEXT:
            if token in lower:
                failures.append(f"TEXT {path}: contains forbidden token {token!r}")

if failures:
    print("XZIEL_NO_LEGACY_RUNTIME_FAIL")
    for failure in failures:
        print(failure)
    print(f"TOTAL={len(failures)}")
    sys.exit(1)

print("XZIEL_NO_LEGACY_RUNTIME_GREEN")
