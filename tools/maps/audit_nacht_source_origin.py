#!/usr/bin/env python3
"""Fail-closed Nacht source/engine classifier: Pavlov UE4 vs authentic BO3 T7.

No file or geometry modification. Only explicitly provided source receipts
can justify a claim that a toolchain corresponds to original BO3 Chronicles.
"""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_WORKFLOW = ROOT / ".github/workflows/xogot-nacht-chronicles-full-map-authority.yml"
DEFAULT_OUTPUT = ROOT / "build/nacht-origin/source-provenance.json"

TOOLS = {
    "pavlov_ue421": [
        {"stage": "unpack", "name": "repak", "status": "already_used"},
        {"stage": "authoritative", "name": "UEStaticSceneExtract", "status": "already_used"},
        {"stage": "whole_world_candidate", "name": "FModel_Aug_2026_USDA", "status": "requires_AB"},
        {"stage": "scene_import", "name": "Blender_USD", "status": "requires_AB"},
        {"stage": "godot_scene", "name": "Meridian_2_0", "status": "requires_AB"},
    ],
    "bo3_t7": [
        {"stage": "bsp", "name": "Husky_BO3", "status": "requires_owned_running_BO3"},
        {"stage": "props", "name": "Greyhound_BO3", "status": "requires_owned_running_BO3"},
        {"stage": "logic_authority", "name": "HydraX_BO3", "status": "requires_owned_running_BO3"},
        {"stage": "blender", "name": "Cast_Blend", "status": "requires_BO3_exports"},
        {"stage": "godot_scene", "name": "Meridian_2_0", "status": "requires_AB"},
    ],
}


def get_quoted(name: str, text: str) -> str:
    found = re.search(r"(?m)^\s*" + re.escape(name) + r':\s*["\x27]([^"\x27]+)["\x27]\s*$', text)
    if not found:
        raise ValueError("required source authority not found: " + name)
    return found.group(1)


def audit(repo_root: Path, bo3_export_dir: Path | None = None) -> dict:
    workflow = repo_root / ".github/workflows/xogot-nacht-chronicles-full-map-authority.yml"
    wf = workflow.read_text(encoding="utf-8")
    app_id = get_quoted("WORKSHOP_APP_ID", wf)
    item_id = get_quoted("WORKSHOP_ITEM_ID", wf)
    engine = get_quoted("SOURCE_GAME", wf)
    packaged_count = int(get_quoted("EXPECTED_PACKAGE_COUNT", wf))
    umap = get_quoted("EXPECTED_MAP", wf)
    if (app_id, item_id, engine, packaged_count, umap) != (
        "555160", "2755515831", "ue4.21", 3871,
        "Pavlov/Content/CustomMaps/UGC2755515831/Nacht_de_Untoten.umap"
    ):
        raise ValueError("SOURCE_LINEAGE_RED: unexpected Pavlov workshop reference; reevaluate BEFORE calling it BO3")
    other_workflow = repo_root / ".github/workflows/xogot-stage-nacht-full-map.yml"
    staged = other_workflow.read_text(encoding="utf-8")
    if "Xogot-Nacht-Chronicles-Full-Map-Authority" not in staged:
        raise ValueError("SOURCE_LINEAGE_RED: stage doesn't consume tracked UE4 authority")
    is_bo3_export_valid = False
    bo3_receipt = {}
    if bo3_export_dir:
        bo3_export_dir = bo3_export_dir.resolve()
        needed = [bo3_export_dir / ("zm_prototype" + ext) for ext in (".obj", ".mtl", ".map", ".txt")]
        bo3_receipt = {file.name: file.is_file() and file.stat().st_size > 0 for file in needed}
        is_bo3_export_valid = all(bo3_receipt.values())
        if not is_bo3_export_valid:
            raise ValueError("BO3_ORIGINAL_SOURCE_NOT_PROVEN: requires original Husky zm_prototype obj/mtl/map/txt")
    return {
        "schema": 1,
        "engine_separation": "T7 Black Ops III != Pavlov Unreal Engine 4.21",
        "official_reference": {
            "game": "Call of Duty Black Ops III - Zombies Chronicles",
            "engine": "Treyarch T7",
            "native_map": "zm_prototype",
            "unmodified_source_proven_in_this_repo": is_bo3_export_valid,
            "bo3_husky_receipt": bo3_receipt,
            "tools": TOOLS["bo3_t7"],
        },
        "imported_nacht_reference": {
            "title": "Pavlov VR community workshop BO3 Nacht der Untoten",
            "engine": engine,
            "workshop_app": app_id,
            "workshop_item": item_id,
            "umap": umap,
            "expected_packages": packaged_count,
            "stage": "xogot-stage-nacht-full-map.yml",
            "tools": TOOLS["pavlov_ue421"],
            "proof_of_original_BO3_world": False,
        },
        "ci_reference_runs": {
            "pavlov_ue421_authority": 37714627696,
            "pavlov_godot_runtime": 37762871109,
            "pavlov_android_release": 37762871146,
        },
        "allowed_claims": [
            "Pavlov UE4.21 map archive, 3871 asset packages tracked",
            "Godot source-runtime and Android CI artifacts already exist",
            "BO3 T7 pipeline requires separate legitimate original BO3 source",
        ],
        "blocked_claims": [
            "Pavlov Workshop UMAP is official BO3 T7 zm_prototype",
            "FModel can extract real BO3 T7 fastfiles",
            "Meridian automatically reproduces all BO3 GSC gameplay logic",
            "existing Godot CI source means BO3 identical art or licensed standalone redistribution",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bo3-export-dir", type=Path,
                        help="ONLY if authentic BO3 zm_prototype Husky output has been provided")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        data = audit(ROOT, args.bo3_export_dir)
    except (ValueError, OSError) as exc:
        print("XZOGOT_NACHT_ORIGIN_SOURCE_RED", str(exc), file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("XZOGOT_NACHT_PAVLOV_UE421_PROVEN",
          data["imported_nacht_reference"]["expected_packages"],
          "workshop", data["imported_nacht_reference"]["workshop_item"])
    print("XZOGOT_NACHT_BO3_T7_ORIGINAL_PRESENT",
          data["official_reference"]["unmodified_source_proven_in_this_repo"])
    print("XZOGOT_NACHT_ORIGIN_LINEAGE_GREEN", str(args.output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
