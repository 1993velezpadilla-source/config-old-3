#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

def main() -> int:
    ap=argparse.ArgumentParser(description="Aggregate isolated HAYUYA cleanroom provider runs")
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    args=ap.parse_args()

    root=args.root.resolve()
    out=args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)

    manifests=sorted(root.rglob("cleanroom_tournament.json"))
    candidates=[]
    providers=[]

    for mp in manifests:
        try:
            d=json.loads(mp.read_text(encoding="utf-8"))
        except Exception as exc:
            providers.append({"manifest":str(mp),"ok":False,"error":f"{type(exc).__name__}: {exc}"})
            continue

        results=d.get("results") or []
        if not results:
            providers.append({"manifest":str(mp),"ok":False,"error":"manifest contains no results"})
            continue

        r=results[0]
        provider=str(r.get("name") or "unknown")
        item={
            "provider":provider,
            "manifest":str(mp),
            "ok":bool(r.get("ok")),
            "score":float(r.get("score") or 0.0),
            "faces":r.get("faces"),
            "vertices":r.get("vertices"),
            "bytes":int(r.get("bytes") or 0),
            "error":r.get("error"),
            "meta":r.get("meta") or {},
        }

        path=r.get("path")
        if path:
            p=Path(path)
            if not p.is_file():
                # Artifact download changes the original runner path. Resolve by
                # provider filename near the downloaded manifest.
                p=mp.parent / f"{provider}.glb"
            if p.is_file():
                item["artifact_path"]=str(p)
                if item["ok"]:
                    candidates.append((item,p))
        providers.append(item)

    candidates.sort(
        key=lambda x: (
            float(x[0].get("score") or 0.0),
            int(x[0].get("faces") or 0),
            int(x[0].get("bytes") or 0),
        ),
        reverse=True,
    )

    winner=None
    if candidates:
        meta,src=candidates[0]
        dst=out/"winner.glb"
        shutil.copy2(src,dst)
        winner={**meta,"path":str(dst)}

    report={
        "schema":1,
        "method":"hayuya-cleanroom-isolated-provider-aggregate-v1",
        "provider_manifests":len(manifests),
        "providers":providers,
        "winner":winner,
    }
    (out/"cleanroom_aggregate.json").write_text(
        json.dumps(report,indent=2,default=str)+"\n",
        encoding="utf-8",
    )

    if winner is None:
        print("HAYUYA_CLEANROOM_AGGREGATE_NO_WINNER",json.dumps(report,separators=(",",":"),default=str),flush=True)
        return 2

    print("HAYUYA_CLEANROOM_AGGREGATE_WINNER",json.dumps(winner,separators=(",",":"),default=str),flush=True)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
