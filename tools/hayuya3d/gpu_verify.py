#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def validate_glb(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.read_bytes()[:4] != b"glTF":
        raise ValueError(f"invalid GLB magic: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify HAYUYA 3D direct-GPU AAA Hero Master output."
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--profile",
        choices=["preview", "mobile", "game", "monster", "ultra"],
        default="ultra",
    )
    args = parser.parse_args()

    manifests = list(args.root.rglob("manifest.json"))
    if not manifests:
        raise SystemExit("GPU E2E produced no HAYUYA manifest")

    manifest_path = max(manifests, key=lambda p: p.stat().st_mtime)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    final_glb = Path(data["final_glb"])
    validate_glb(final_glb)

    # HAYUYA 3D is geometry/material generation only. Do not require GamePrep,
    # LODs, rigging or animation here; those belong to downstream products.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from mesh_gate import inspect as inspect_mesh_gate

    mesh = inspect_mesh_gate(final_glb, require_normals=False)
    if not mesh.passed:
        raise SystemExit(
            "Hero Master mesh gate failed: " + ";".join(mesh.reasons[:16])
        )

    floors = {
        "preview": 0,
        "mobile": 0,
        "game": 0,
        "monster": 650_000,
        "ultra": 1_000_000,
    }
    ceilings = {
        "preview": 30_000,
        "mobile": 120_000,
        "game": 400_000,
        "monster": 1_500_000,
        "ultra": 2_000_000,
    }
    floor = floors[args.profile]
    ceiling = ceilings[args.profile]

    if floor and int(mesh.faces) < floor:
        raise SystemExit(
            f"{args.profile} Hero Master density too low: "
            f"{mesh.faces}<{floor} triangles"
        )
    if int(mesh.faces) > ceiling:
        raise SystemExit(
            f"{args.profile} Hero Master exceeded production ceiling: "
            f"{mesh.faces}>{ceiling} triangles"
        )

    judge_v4 = data.get("judge_v4") or {}
    if judge_v4.get("passed") is not True:
        reasons = judge_v4.get("hard_fail_reasons") or []
        raise SystemExit(
            "Judge v4 did not pass final visual acceptance: "
            + ";".join(str(x) for x in reasons[:16])
        )

    judge_v5 = data.get("judge_v5") or {}
    visual_approval = data.get("visual_approval") or {}
    if (
        judge_v5.get("passed") is not True
        or judge_v5.get("status") != "APPROVED"
        or visual_approval.get("production_approved") is not True
    ):
        reasons = judge_v5.get("hard_fail_reasons") or []
        raise SystemExit(
            "Judge v5 did not production-approve final visual asset: "
            f"status={judge_v5.get('status')} "
            + ";".join(str(x) for x in reasons[:16])
        )

    aaa = data.get("aaa_acceptance") or {}
    visual_gate = next(
        (
            gate for gate in (aaa.get("gates") or [])
            if gate.get("id") == "character.visual_judge_v4"
        ),
        None,
    )
    if visual_gate is not None and visual_gate.get("ready") is not True:
        raise SystemExit("AAA visual Judge v4 gate is not ready")

    report = {
        "status": "PASS",
        "product": "HAYUYA 3D",
        "profile": args.profile,
        "manifest": str(manifest_path),
        "final_glb": str(final_glb),
        "champion": data.get("champion", {}).get("backend"),
        "score": data.get("champion", {}).get("score"),
        "hero_master": {
            "triangles": int(mesh.faces),
            "vertices": int(mesh.vertices),
            "minimum_triangles": int(floor),
            "production_ceiling_triangles": int(ceiling),
            "runtime_optimization_applied": False,
            "immutable_source": True,
        },
        "viewforge": bool(data.get("viewforge")),
        "geometry_refinement": data.get("geometry_refinement"),
        "material_bridge": data.get("material_bridge"),
        "judge_v4_passed": True,
        "judge_v4_hard_failures": len(judge_v4.get("hard_fail_reasons") or []),
        "judge_v5_passed": True,
        "judge_v5_status": "APPROVED",
        "production_approved": True,
        "aaa_visual_v4_ready": (
            bool(visual_gate.get("ready")) if visual_gate is not None else None
        ),
        "downstream": {
            "rigging": "HAYUYA Motions",
            "animation": "HAYUYA Motions",
            "runtime_lods": "downstream/XZIEL",
            "map_assembly": "HAYUYA Map",
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("HAYUYA_GPU_HERO_VERIFY_PASS")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
