#!/usr/bin/env python3
import argparse
import os
import pathlib
import shutil
import subprocess
import tempfile

def replace_bytes_in_tree(root: pathlib.Path, old: bytes, new: bytes):
    files_changed = 0
    replacements = 0
    changed_paths = []
    for base, dirs, files in os.walk(root, followlinks=False):
        # Never descend through symlinked dirs.
        dirs[:] = [d for d in dirs if not (pathlib.Path(base) / d).is_symlink()]
        for name in files:
            p = pathlib.Path(base) / name
            if p.is_symlink() or not p.is_file():
                continue
            data = p.read_bytes()
            count = data.count(old)
            if count:
                p.write_bytes(data.replace(old, new))
                files_changed += 1
                replacements += count
                changed_paths.append(str(p.relative_to(root)))
    # Safety gate: no old package bytes may remain in regular files.
    leftovers = []
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if not (pathlib.Path(base) / d).is_symlink()]
        for name in files:
            p = pathlib.Path(base) / name
            if p.is_symlink() or not p.is_file():
                continue
            if old in p.read_bytes():
                leftovers.append(str(p.relative_to(root)))
                if len(leftovers) >= 20:
                    break
        if leftovers:
            break
    if leftovers:
        raise SystemExit(f"old package bytes remain under {root}: {leftovers}")
    return files_changed, replacements, changed_paths

def repack_tzst(archive: pathlib.Path, old: bytes, new: bytes):
    with tempfile.TemporaryDirectory(prefix="xziel-tzst-") as td:
        td = pathlib.Path(td)
        extract = td / "root"
        extract.mkdir()
        subprocess.run(["tar", "--zstd", "-xf", str(archive), "-C", str(extract)], check=True)

        files_changed, replacements, changed_paths = replace_bytes_in_tree(extract, old, new)
        if not replacements:
            return 0, 0, []

        rebuilt = td / archive.name
        env = os.environ.copy()
        env.setdefault("ZSTD_CLEVEL", "9")
        subprocess.run(
            [
                "tar", "--zstd", "--numeric-owner", "--owner=0", "--group=0",
                "-cf", str(rebuilt), "-C", str(extract), "."
            ],
            check=True,
            env=env,
        )
        subprocess.run(["tar", "--zstd", "-tf", str(rebuilt)], check=True, stdout=subprocess.DEVNULL)
        shutil.copy2(rebuilt, archive)
        return files_changed, replacements, changed_paths

def patch_source_literals(winlator: pathlib.Path, old_pkg: str, new_pkg: str):
    old_path = f"/data/data/{old_pkg}"
    new_path = f"/data/data/{new_pkg}"
    old_provider = f"{old_pkg}.FileProvider"
    new_provider = f"{new_pkg}.FileProvider"

    roots = [
        winlator / "app/src/main/java",
        winlator / "app/src/main/cpp",
    ]
    changed = 0
    replacements = 0
    for root in roots:
        for p in root.rglob("*"):
            if not p.is_file() or p.is_symlink():
                continue
            if p.suffix.lower() not in {".java", ".c", ".cc", ".cpp", ".h", ".hpp", ".xml"}:
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            original = text
            text = text.replace(old_path, new_path)
            text = text.replace(old_provider, new_provider)
            if text != original:
                replacements += original.count(old_path) + original.count(old_provider)
                p.write_text(text, encoding="utf-8")
                changed += 1
    return changed, replacements

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("winlator_root")
    ap.add_argument("--old", default="com.winlator")
    ap.add_argument("--new", default="com.xzielapp")
    args = ap.parse_args()

    old_pkg = args.old
    new_pkg = args.new
    if len(old_pkg.encode()) != len(new_pkg.encode()):
        raise SystemExit(f"package ids must have equal byte length: {old_pkg} vs {new_pkg}")

    winlator = pathlib.Path(args.winlator_root).resolve()
    assets = winlator / "app/src/main/assets"
    if not assets.is_dir():
        raise SystemExit(f"missing assets dir: {assets}")

    source_files, source_replacements = patch_source_literals(winlator, old_pkg, new_pkg)
    print(
        f"XZIEL_RUNTIME_PACKAGE_SOURCE_REWRITE files={source_files} "
        f"replacements={source_replacements} old={old_pkg} new={new_pkg}"
    )

    old = old_pkg.encode("ascii")
    new = new_pkg.encode("ascii")

    archive_count = 0
    file_count = 0
    replacement_count = 0
    changed_archives = []
    for archive in sorted(assets.rglob("*.tzst")):
        files_changed, replacements, changed_paths = repack_tzst(archive, old, new)
        if replacements:
            archive_count += 1
            file_count += files_changed
            replacement_count += replacements
            rel = str(archive.relative_to(assets))
            changed_archives.append(rel)
            print(
                f"XZIEL_RUNTIME_PACKAGE_ARCHIVE_REWRITE archive={rel} "
                f"files={files_changed} replacements={replacements}"
            )
            for p in changed_paths[:20]:
                print(f"  patched={p}")

    # These two are mandatory because they contain the glibc runtime and Box64.
    required = {"rootfs.tzst", "box64/box64-0.4.4.tzst"}
    missing = sorted(required.difference(changed_archives))
    if missing:
        raise SystemExit(f"mandatory runtime archives were not rewritten: {missing}")

    print(
        f"XZIEL_RUNTIME_PACKAGE_REWRITE_GREEN old={old_pkg} new={new_pkg} "
        f"archives={archive_count} files={file_count} replacements={replacement_count}"
    )

if __name__ == "__main__":
    main()
