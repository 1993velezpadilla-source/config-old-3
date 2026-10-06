#!/usr/bin/env python3
"""Compile Nacht interactive placements from source UMAP actor anchors.

This does not invent coordinates. Categories are keyed by known Blueprint
identities present in the validated Nacht package; every output row retains
the exact actor-anchor transform emitted by UEStaticSceneExtract.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

CATEGORIES = {
    "mystery_box": ("mysterybox_c",),
    "mystery_box_location": ("mysteryboxlocation_c",),
    "pack_a_punch": ("punchapackmachine_c",),
    "gumball_machine": ("machinegumball_c",),
    "perk_machine": ("perkmachine_",),
    "wonderfizz": ("wonderfizz_c",),
    "power_switch": ("powerswitch_c", "powerswitchdynamic_c"),
    "wallbuy": ("wallbuy_c",),
    "barricade": ("barricade_c",),
    "zombie_spawner": ("zombiespawner_c",),
    "hound_spawner": ("zombie_hounds_spawner_c",),
    "buyable_door": ("buyabledoor_c", "buyabledoor_child_c"),
}

# These systems are expected for a playable Nacht source-world handoff.
REQUIRED = (
    "mystery_box",
    "mystery_box_location",
    "pack_a_punch",
    "gumball_machine",
    "perk_machine",
    "power_switch",
    "wallbuy",
    "barricade",
    "zombie_spawner",
    "buyable_door",
)


def identity(row: dict) -> str:
    return " ".join(
        str(row.get(k, ""))
        for k in ("className", "objectPath", "rootComponentPath")
    ).lower()


def classify(row: dict) -> list[str]:
    ident = identity(row)
    hits = []
    for category, tokens in CATEGORIES.items():
        if any(token in ident for token in tokens):
            hits.append(category)
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    scene = json.loads(args.scene.read_text(encoding="utf-8"))
    if scene.get("format") != "xziel_visual_scene_v1":
        raise SystemExit("interactive placements rejected: wrong scene format")

    anchors = scene.get("actorAnchors", [])
    if not isinstance(anchors, list) or not anchors:
        raise SystemExit("interactive placements rejected: no actor anchors")

    categories: dict[str, list[dict]] = {k: [] for k in CATEGORIES}
    multi_category = []

    for anchor in anchors:
        if not isinstance(anchor, dict):
            continue
        hits = classify(anchor)
        if len(hits) > 1:
            multi_category.append({
                "objectPath": anchor.get("objectPath"),
                "className": anchor.get("className"),
                "categories": hits,
            })
        for category in hits:
            categories[category].append({
                "packagePath": anchor.get("packagePath"),
                "exportIndex": anchor.get("exportIndex"),
                "objectPath": anchor.get("objectPath"),
                "className": anchor.get("className"),
                "rootComponentPath": anchor.get("rootComponentPath"),
                "anchorSource": anchor.get("anchorSource"),
                "matrixRowMajor": anchor.get("matrixRowMajor"),
                "positionMeters": anchor.get("positionMeters"),
            })

    counts = {k: len(v) for k, v in categories.items()}
    missing = [k for k in REQUIRED if counts[k] == 0]

    # Deterministic ordering keeps source diffs auditable.
    for rows in categories.values():
        rows.sort(key=lambda r: (
            str(r.get("className", "")).lower(),
            str(r.get("objectPath", "")).lower(),
        ))

    output = {
        "schemaVersion": 1,
        "authority": "Nacht UMAP actor anchors; no synthetic placements",
        "sourceActorAnchorCount": len(anchors),
        "categories": categories,
        "counts": counts,
        "requiredCategories": list(REQUIRED),
        "missingRequiredCategories": missing,
        "multiCategoryMatches": multi_category,
        "ready": not missing,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")

    print("XZOGOT_NACHT_INTERACTIVE_PLACEMENTS", json.dumps({
        "sourceActors": len(anchors),
        "counts": counts,
        "missing": missing,
        "ready": output["ready"],
    }, sort_keys=True))

    if missing:
        print("XZOGOT_NACHT_INTERACTIVE_PLACEMENTS_FAILURE")
        return 5

    print("XZOGOT_NACHT_INTERACTIVE_PLACEMENTS_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
