#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from judge_model_provenance import model_provenance


@dataclass
class CandidateSimilarity:
    name: str
    path: str
    cosine_similarity: float
    max_source_similarity: float
    best_source: str


@dataclass
class SourceCoverage:
    source: str
    best_candidate: str
    best_similarity: float


@dataclass
class SigLIP2Report:
    schema: int
    model: str
    sources: list[str]
    device: str
    ready: bool
    candidates: list[CandidateSimilarity]
    source_coverage: list[SourceCoverage]
    warnings: list[str]
    method: str = "siglip2-giant-multisource-image-fidelity-v3"


def _parse_named(items:list[str])->list[tuple[str,Path]]:
    out=[]
    for raw in items:
        if "=" not in raw:
            raise ValueError(f"expected NAME=PATH, got {raw!r}")
        name,path=raw.split("=",1)
        p=Path(path)
        if not name.strip() or not p.is_file():
            raise FileNotFoundError(f"missing candidate {name}={p}")
        out.append((name.strip(),p))
    return out


def _pooled(value):
    import torch
    if torch.is_tensor(value):
        return value
    for attr in ("pooler_output","image_embeds","last_hidden_state"):
        raw=getattr(value,attr,None)
        if raw is None:
            continue
        if attr=="last_hidden_state":
            return raw.mean(dim=1)
        return raw
    if isinstance(value,(tuple,list)) and value:
        return _pooled(value[0])
    raise TypeError(f"cannot extract pooled embedding from {type(value).__name__}")


def score(sources:list[Path],candidates:list[tuple[str,Path]],model_id:str)->SigLIP2Report:
    import torch
    import torch.nn.functional as F
    from PIL import Image
    from transformers import AutoModel, AutoProcessor

    if not sources:
        raise ValueError("at least one source is required")
    if not candidates:
        raise ValueError("at least one candidate is required")

    device="cuda" if torch.cuda.is_available() else "cpu"
    model=AutoModel.from_pretrained(model_id,dtype="auto").to(device).eval()
    processor=AutoProcessor.from_pretrained(model_id)

    images=[
        *[Image.open(path).convert("RGB") for path in sources],
        *[Image.open(path).convert("RGB") for _,path in candidates],
    ]
    inputs=processor(images=images,return_tensors="pt")
    inputs={k:(v.to(device) if hasattr(v,"to") else v) for k,v in inputs.items()}
    with torch.inference_mode():
        features=_pooled(model.get_image_features(**inputs)).float()
    features=F.normalize(features,dim=-1)

    ns=len(sources)
    src=features[:ns]
    cand=features[ns:]
    centroid=F.normalize(src.mean(dim=0,keepdim=True),dim=-1)
    matrix=(cand@src.T).detach().cpu()
    centroid_sims=(cand@centroid.T).squeeze(-1).detach().cpu().tolist()
    if not isinstance(centroid_sims,list):
        centroid_sims=[float(centroid_sims)]

    rows=[]
    for index,((name,path),centroid_sim) in enumerate(zip(candidates,centroid_sims)):
        source_scores=matrix[index].tolist()
        if not isinstance(source_scores,list):
            source_scores=[float(source_scores)]
        best_index=max(range(len(source_scores)),key=lambda i:source_scores[i])
        rows.append(CandidateSimilarity(
            name=name,
            path=str(path),
            cosine_similarity=round(float(centroid_sim),7),
            max_source_similarity=round(float(source_scores[best_index]),7),
            best_source=str(sources[best_index]),
        ))

    coverage=[]
    matrix_t=matrix.T
    for source_index,source in enumerate(sources):
        values=matrix_t[source_index].tolist()
        if not isinstance(values,list):
            values=[float(values)]
        best_index=max(range(len(values)),key=lambda i:values[i])
        coverage.append(SourceCoverage(
            source=str(source),
            best_candidate=candidates[best_index][0],
            best_similarity=round(float(values[best_index]),7),
        ))

    report=SigLIP2Report(
        schema=3,
        model=model_id,
        sources=[str(x) for x in sources],
        device=device,
        ready=(len(rows)==len(candidates) and len(coverage)==len(sources)),
        candidates=rows,
        source_coverage=coverage,
        warnings=[],
    )
    payload=asdict(report)
    payload["provenance"]=model_provenance(model_id,model)
    return payload


def main()->int:
    p=argparse.ArgumentParser(description="HAYUYA Judge v5 SigLIP2 multi-source fidelity eye.")
    p.add_argument("--source",type=Path,action="append",required=True)
    p.add_argument("--candidate",action="append",default=[],required=True,help="NAME=PATH")
    p.add_argument("--model",default="google/siglip2-giant-opt-patch16-384")
    p.add_argument("--json",type=Path,required=True)
    a=p.parse_args()
    try:
        missing=[str(p) for p in a.source if not p.is_file()]
        if missing:
            raise FileNotFoundError(",".join(missing))
        payload=score(a.source,_parse_named(a.candidate),a.model)
        code=0 if payload.get("ready") else 2
    except Exception as exc:
        payload={
            "schema":3,"model":a.model,"sources":[str(x) for x in a.source],
            "ready":False,"candidates":[],"source_coverage":[],
            "warnings":[f"{type(exc).__name__}:{exc}"],
            "method":"siglip2-giant-multisource-image-fidelity-v3",
        }
        code=2
    a.json.parent.mkdir(parents=True,exist_ok=True)
    a.json.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(payload,indent=2))
    return code


if __name__=="__main__":
    raise SystemExit(main())
