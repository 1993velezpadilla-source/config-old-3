#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def get_path(obj, dotted):
    cur = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur

def evaluate(manifest, policy):
    results = []
    stages = manifest.get("stages", {})
    regions = manifest.get("regions", {})

    for stage in policy["requiredStages"]:
        present = stage in stages
        results.append({
            "kind": "stage",
            "name": stage,
            "status": "PASS" if present else "FAIL",
            "detail": "present" if present else "missing stage artifact/record"
        })

    for stage, metrics in policy.get("requiredMetrics", {}).items():
        record = stages.get(stage, {})
        for metric in metrics:
            present = metric in record and record.get(metric) is not None
            results.append({
                "kind": "metric",
                "name": f"{stage}.{metric}",
                "status": "PASS" if present else "FAIL",
                "detail": "recorded" if present else "missing required metric"
            })

    for region in policy.get("requiredRegions", []):
        record = regions.get(region)
        results.append({
            "kind": "region",
            "name": region,
            "status": "PASS" if isinstance(record, dict) else "FAIL",
            "detail": "region QA present" if isinstance(record, dict) else "missing region QA"
        })

    for region, metrics in policy.get("regionMetrics", {}).items():
        record = regions.get(region, {})
        for metric in metrics:
            present = metric in record and record.get(metric) is not None
            results.append({
                "kind": "region_metric",
                "name": f"{region}.{metric}",
                "status": "PASS" if present else "FAIL",
                "detail": "recorded" if present else "missing region metric"
            })

    # Cross-stage invariants.
    master = stages.get("surface_master", {})
    game = stages.get("game_mesh", {})
    if master.get("triangles") is not None and game.get("triangles") is not None:
        ok = int(master["triangles"]) >= int(game["triangles"])
        results.append({
            "kind": "invariant",
            "name": "master_not_lower_detail_than_game",
            "status": "PASS" if ok else "FAIL",
            "detail": f"surface_master={master['triangles']} game_mesh={game['triangles']}"
        })

    face = regions.get("face", {})
    cloth = regions.get("cloth", {})
    results.append({
        "kind": "invariant",
        "name": "face_and_cloth_are_independent",
        "status": "PASS" if face is not cloth and bool(face) and bool(cloth) else "FAIL",
        "detail": "separate region QA records required"
    })

    hard_fail = any(x["status"] == "FAIL" for x in results)
    return {
        "schemaVersion": 1,
        "asset": manifest.get("asset"),
        "results": results,
        "summary": {
            "pass": sum(x["status"] == "PASS" for x in results),
            "fail": sum(x["status"] == "FAIL" for x in results),
            "status": "FAIL" if hard_fail else "PASS"
        }
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("--policy", default=str(Path(__file__).with_name("quality_policy.v1.json")))
    ap.add_argument("--out")
    args = ap.parse_args()

    report = evaluate(load(args.manifest), load(args.policy))
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    raise SystemExit(1 if report["summary"]["status"] == "FAIL" else 0)

if __name__ == "__main__":
    main()
