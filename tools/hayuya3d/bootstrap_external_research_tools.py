#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
LOCK = HERE / "external_research_tools.lock.json"


def run(*args: str, cwd: Path | None = None) -> None:
    print("+", " ".join(args))
    subprocess.run(args, cwd=cwd, check=True)


def checkout(repo: str, sha: str, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    run("git", "init", "-q", str(dst))
    run("git", "remote", "add", "origin", f"https://github.com/{repo}.git", cwd=dst)
    run("git", "fetch", "-q", "--depth=1", "origin", sha, cwd=dst)
    run("git", "checkout", "-q", "--detach", "FETCH_HEAD", cwd=dst)


def digest_tree(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts):
        h.update(path.relative_to(root).as_posix().encode())
        h.update(b"\0")
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", type=Path, default=HERE / ".external")
    ap.add_argument("--include-restricted", action="store_true")
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--inventory", type=Path)
    args = ap.parse_args()

    data = json.loads(LOCK.read_text(encoding="utf-8"))
    wanted = set(args.only)
    inventory = []

    for tool in data["tools"]:
        if wanted and tool["id"] not in wanted:
            continue
        if tool["tier"] == "research_restricted" and not args.include_restricted:
            print("SKIP restricted:", tool["id"])
            continue
        dst = args.dest / tool["id"]
        checkout(tool["repo"], tool["sha"], dst)
        inventory.append({
            "id": tool["id"],
            "repo": tool["repo"],
            "sha": tool["sha"],
            "license": tool["license"],
            "tier": tool["tier"],
            "path": str(dst),
            "tree_sha256": digest_tree(dst),
        })

    inv_path = args.inventory or (args.dest / "inventory.json")
    inv_path.parent.mkdir(parents=True, exist_ok=True)
    inv_path.write_text(json.dumps({"schema": 1, "tools": inventory}, indent=2) + "\n", encoding="utf-8")
    print("WROTE", inv_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
