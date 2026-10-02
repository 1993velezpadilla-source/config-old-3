#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK = Path(__file__).with_name("backends.lock.json")
DEFAULT_ROOT = ROOT / ".hayuya" / "models"
PERMISSIVE_LICENSES = {"MIT", "Apache-2.0", "BSD-3-Clause"}


def load_lock() -> dict:
    return json.loads(LOCK.read_text(encoding="utf-8"))


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def git_output(args: list[str], cwd: Path) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def clone_backend(entry: dict, root: Path) -> None:
    backend_id = entry["id"]
    if not entry.get("source_required", True):
        print(
            f"HAYUYA_BACKEND_ENV_ONLY {backend_id} "
            f"license={entry['license']}"
        )
        return
    url = entry["repo"]
    sha = entry["sha"]
    dst = root / backend_id
    root.mkdir(parents=True, exist_ok=True)

    if not dst.exists():
        run(["git", "clone", "--filter=blob:none", "--no-checkout", url, str(dst)])
    elif not (dst / ".git").exists():
        raise RuntimeError(f"{dst} exists but is not a git repository")

    run(["git", "fetch", "--depth", "1", "origin", sha], cwd=dst)
    run(["git", "checkout", "--detach", sha], cwd=dst)
    if entry.get("submodules"):
        run(["git", "submodule", "sync", "--recursive"], cwd=dst)
        run(["git", "submodule", "update", "--init", "--recursive", "--depth", "1"], cwd=dst)
    actual = git_output(["rev-parse", "HEAD"], dst)
    if actual != sha:
        raise RuntimeError(f"{backend_id}: expected {sha}, got {actual}")
    print(f"HAYUYA_BACKEND_READY {backend_id} {actual} license={entry['license']}")


def verify_backend(entry: dict, root: Path) -> bool:
    if not entry.get("source_required", True):
        print(f"PASS {entry['id']} source=env-only")
        return True
    dst = root / entry["id"]
    if not (dst / ".git").exists():
        print(f"MISSING {entry['id']}")
        return False
    actual = git_output(["rev-parse", "HEAD"], dst)
    ok = actual == entry["sha"]
    print(f"{'PASS' if ok else 'DRIFT'} {entry['id']} expected={entry['sha']} actual={actual}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap pinned Hayuya 3D open-source backends.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--all", action="store_true", help="Clone all default-enabled permissive backends.")
    parser.add_argument("--backend", action="append", default=[], help="Specific backend id; repeatable.")
    parser.add_argument("--allow-restricted", action="store_true", help="Allow cloning opt-in community/restricted-license backends.")
    args = parser.parse_args()

    lock = load_lock()
    backends = {x["id"]: x for x in lock["backends"]}

    if args.list:
        for entry in backends.values():
            print(
                f"{entry['id']:16} license={entry['license']:42} "
                f"default={entry['enabled_by_default']} vram>={entry['min_vram_gb']}GB"
            )
        return 0

    selected: list[dict] = []
    if args.all:
        selected.extend(
            x for x in backends.values()
            if x["enabled_by_default"]
            and x["license"] in PERMISSIVE_LICENSES
        )
    for backend_id in args.backend:
        if backend_id not in backends:
            parser.error(f"unknown backend: {backend_id}")
        entry = backends[backend_id]
        if entry["license"] not in PERMISSIVE_LICENSES and not args.allow_restricted:
            parser.error(
                f"{backend_id} has a non-core/restricted license. "
                "Re-run with --allow-restricted only after reviewing its terms."
            )
        selected.append(entry)

    # Preserve order while de-duplicating.
    deduped: list[dict] = []
    seen: set[str] = set()
    for entry in selected:
        if entry["id"] not in seen:
            seen.add(entry["id"])
            deduped.append(entry)

    if args.verify:
        targets = deduped or [
            x for x in backends.values()
            if x["enabled_by_default"] and x["license"] in PERMISSIVE_LICENSES
        ]
        return 0 if all(verify_backend(x, args.root) for x in targets) else 2

    if not deduped:
        parser.error("choose --all or at least one --backend")

    for entry in deduped:
        clone_backend(entry, args.root)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
