#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def _parse_named(items:list[str])->list[tuple[str,Path]]:
    out=[]
    for raw in items:
        if "=" not in raw:
            raise ValueError(f"expected NAME=PATH, got {raw!r}")
        name,path=raw.split("=",1)
        p=Path(path)
        if not name.strip() or not p.is_file():
            raise FileNotFoundError(f"{name}={p}")
        out.append((name.strip(),p))
    return out


def run(rows:list[tuple[str,Path]])->dict:
    import cv2
    from uniface.constants import EDifFIQAWeights
    from uniface.detection import SCRFD
    from uniface.quality import EDifFIQA

    detector=SCRFD(confidence_threshold=0.25)
    quality=EDifFIQA(model_name=EDifFIQAWeights.L)

    evidence=[]
    scores=[]
    for name,path in rows:
        image=cv2.imread(str(path))
        if image is None:
            evidence.append({"name":name,"path":str(path),"detected":False,"score":None,"reason":"decode_failed"})
            continue
        faces=detector.detect(image)
        if not faces:
            evidence.append({"name":name,"path":str(path),"detected":False,"score":None,"reason":"no_face"})
            continue
        # Use largest detected face; candidate crops are already face-focused.
        face=max(
            faces,
            key=lambda f:max(0.0,float(f.bbox[2]-f.bbox[0]))*max(0.0,float(f.bbox[3]-f.bbox[1])),
        )
        result=quality.predict(image,face.landmarks)
        score=float(result.score)
        if not math.isfinite(score):
            raise RuntimeError(f"non-finite eDifFIQA score for {path}")
        scores.append(score)
        evidence.append({
            "name":name,
            "path":str(path),
            "detected":True,
            "score":round(score,7),
            "bbox":[float(x) for x in face.bbox],
        })

    detected=sum(1 for x in evidence if x.get("detected"))
    ordered=sorted(scores)
    return {
        "schema":1,
        "model":"eDifFIQA-L",
        # Execution success is separate from visual acceptance. A missing face
        # must remain inspectable evidence, not be misreported as a worker crash.
        "ready":bool(evidence),
        "detected":detected,
        "total":len(evidence),
        "detection_fraction":round(detected/max(1,len(evidence)),6),
        "minimum":round(min(ordered),7) if ordered else None,
        "median":round(ordered[len(ordered)//2],7) if ordered else None,
        "mean":round(sum(ordered)/len(ordered),7) if ordered else None,
        "images":evidence,
        "warnings":([] if detected==len(evidence) else ["face_detection_incomplete"]),
        "method":"ediffiqa-l-uniface-face-quality-v1",
    }


def main()->int:
    p=argparse.ArgumentParser(description="HAYUYA Judge V5 eDifFIQA-L face-quality eye.")
    p.add_argument("--image",action="append",required=True,help="NAME=PATH")
    p.add_argument("--json",type=Path,required=True)
    a=p.parse_args()
    try:
        payload=run(_parse_named(a.image))
        code=0 if payload["ready"] else 2
    except Exception as exc:
        payload={
            "schema":1,"model":"eDifFIQA-L","ready":False,"images":[],
            "warnings":[f"{type(exc).__name__}:{exc}"],
            "method":"ediffiqa-l-uniface-face-quality-v1",
        }
        code=2
    a.json.parent.mkdir(parents=True,exist_ok=True)
    a.json.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(payload,indent=2))
    return code


if __name__=="__main__":
    raise SystemExit(main())
