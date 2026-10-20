#!/usr/bin/env python3
"""Inventory owner-saved church Tripo GLBs. NO asset creation or substitutes."""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Callable

KNOWN_OTHER = {"altar.glb", "bench.glb", "church_final_architecture.glb"}
ROOTS = (
    "xogot/assets/environment/church", "xogot/assets/church",
    "assets/tripo/church", "assets/tripo3d/church",
    "xogot/assets/tripo", "iglesia/source_tripo",
)

def _category(relative: Path) -> str | None:
    name = relative.as_posix().casefold().replace(" ", "_").replace("-", "_")
    if not any(w in name for w in (
        "chandelier", "candelab", "candle_holder", "candlestick",
        "sconce", "wall_light", "wall_lamp", "aplique", "pendant",
        "ceiling_light", "hanging_lamp", "lamp_hanging", "lamp_candle",
    )):
        return None
    if any(w in name for w in ("wall", "pared", "sconce", "aplique", "mural")):
        return "wall_sconce"
    if any(w in name for w in ("chandelier", "pendant", "ceiling", "hanging", "colgante", "techo")):
        return "ceiling_chandelier"
    return "standing_candelabrum"

def stage_fixtures(repo: Path, asset_dest: Path, git_sha: Callable[[bytes], str]) -> None:
    output = asset_dest / "tripo"
    (output / "fixtures").mkdir(parents=True, exist_ok=True)
    catalog: list[dict] = []
    unclassified: list[str] = []
    unique_sha: set[str] = set()
    for rel_root in ROOTS:
        folder = repo / rel_root
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*.glb")):
            if path.name.casefold() in KNOWN_OTHER:
                continue  # original altar/benches already pinned and imported
            kind = _category(path.relative_to(folder))
            if kind is None:
                unclassified.append(path.relative_to(repo).as_posix())
                continue
            original = path.read_bytes()
            if original[:4] != b"glTF":
                raise RuntimeError("INVALID_ORIGINAL_TRIPO_GLB: " + path.as_posix())
            sha = git_sha(original)
            if sha in unique_sha:
                continue
            unique_sha.add(sha)
            relative_dest = f"tripo/fixtures/{kind}_{sha[:16]}.glb"
            (asset_dest / relative_dest).write_bytes(original)
            catalog.append({
                "kind": kind, "source": path.relative_to(repo).as_posix(),
                "destination": "res://assets/" + relative_dest,
                "git_blob_sha": sha, "bytes": len(original),
            })
            print("TRIPO_CHURCH_ORIGINAL_FOUND", kind, path.relative_to(repo))
    from stage_original_tripo_packs import stage_archived_tripo
    restored = stage_archived_tripo(repo, asset_dest, catalog)
    if os.environ.get("IGLESIA_REQUIRE_REAL_TRIPO_104", "0") == "1" and (restored["packages_found"] != 8 or restored["models_audited"] != 104):
        raise RuntimeError("IGLESIA_ORIGINAL_TRIPO_8_ZIP_104_GLB_MISSING_FROM_GITHUB: do not publish fake APK")
    if restored["packages_found"]:
        # Exact canonical source ZIPs override any legacy filename-based picks.
        catalog = restored["visible_fixtures"]
    manifest = {
        "source_library_status": restored.get("source", "project_library_recovered_not_in_repository"),
        "original_split_model_count": restored["models_audited"],
        "original_split_archive_count": restored["packages_found"],
        "archive_entries": restored["archive_entries"],
        "version": 2, "fixture_count": len(catalog),
        "source_roots": list(ROOTS), "fixtures": catalog,
        "unclassified_glbs": unclassified, "no_synthetic_replacements": True,
    }
    (output / "fixtures_catalog.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if not catalog:
        print("TRIPO_ARCHIVES_EXIST_IN_PROJECT_LIBRARY_BUT_NOT_IN_GITHUB_SOURCE: code cannot copy them automatically")
    else:
        print("IGLESIA_TRIPO_OWNER_FIXTURES_STAGED", len(catalog))
