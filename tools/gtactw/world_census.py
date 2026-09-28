#!/usr/bin/env python3
"""Build a streaming-density census for CTW worldblocks inside game.pak.

Operates only on a locally supplied user-owned PAK.  The report contains
metadata/counts, not game assets.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics

import pak_inventory
import wbl_probe


def census_pak(path: Path) -> dict:
    with path.open("rb") as fp:
        index = pak_inventory.read_index(fp)
        names = pak_inventory.map_known_names(fp, index)

        blocks = []
        parse_errors = []
        all_models = set()

        for rid, name in sorted(names.items()):
            if not name.endswith(".wbl"):
                continue
            start, end = pak_inventory.resource_span(index, rid)
            fp.seek(start)
            blob = fp.read(end - start)
            try:
                w = wbl_probe.parse_wbl_bytes(blob)
            except Exception as exc:
                parse_errors.append({
                    "resource_id": rid,
                    "name": name,
                    "error": str(exc),
                })
                continue

            totals = w["totals"]
            all_models.update(w["unique_model_resource_ids"])
            blocks.append({
                "resource_id": rid,
                "name": name,
                "size": end - start,
                "origin": w["transform"]["position"],
                "sector_offsets": w["sector_offsets"],
                "instances": totals["instances"],
                "levels": totals["levels"],
                "lights": totals["lights"],
                "texture_refs": totals["texture_refs"],
                "unique_model_refs": len(w["unique_model_resource_ids"]),
                "unique_texture_refs": len(w["unique_texture_ids"]),
                "local_level_bounds": w["overall_level_bounds"],
                "sector_instance_counts": w["sector_instance_counts"],
                "sector_level_counts": w["sector_level_counts"],
            })

    instance_counts = [b["instances"] for b in blocks]
    level_counts = [b["levels"] for b in blocks]

    def stat(values):
        if not values:
            return {"min": 0, "max": 0, "mean": 0.0, "median": 0.0}
        return {
            "min": min(values),
            "max": max(values),
            "mean": statistics.fmean(values),
            "median": statistics.median(values),
        }

    dense = sorted(
        blocks,
        key=lambda b: (b["instances"], b["levels"], b["size"]),
        reverse=True,
    )[:32]

    return {
        "pak": str(path),
        "worldblocks_named": sum(1 for n in names.values() if n.endswith(".wbl")),
        "worldblocks_parsed": len(blocks),
        "parse_errors": parse_errors,
        "totals": {
            "instances": sum(instance_counts),
            "levels": sum(level_counts),
            "lights": sum(b["lights"] for b in blocks),
            "texture_refs": sum(b["texture_refs"] for b in blocks),
            "unique_model_resource_ids": len(all_models),
        },
        "instance_stats_per_worldblock": stat(instance_counts),
        "level_stats_per_worldblock": stat(level_counts),
        "densest_worldblocks": dense,
        "worldblocks": blocks,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pak", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument(
        "--require-clean",
        action="store_true",
        help="Fail when any named worldblock cannot be parsed",
    )
    args = ap.parse_args()

    try:
        report = census_pak(args.pak)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    report["ok"] = not (args.require_clean and report["parse_errors"])
    payload = json.dumps(report, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
