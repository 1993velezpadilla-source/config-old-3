#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--model",type=Path,required=True)
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--detail",type=Path,action="append",default=[])
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()

    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from gameprep import build_turntable
    from judge_v4 import _face_crop,_labelled_sheet,_stack_boards

    a.out.mkdir(parents=True,exist_ok=True)
    turns=[Path(x) for x in build_turntable(a.model,a.out/"turntable",anchor_view=None)]
    if len(turns)!=24:
        raise SystemExit(f"expected 24 turntable frames, got {len(turns)}")

    face_indices=[0,1,2,3,4,20,21,22,23]
    faces=[]
    for idx in face_indices:
        out=a.out/"faces"/f"{idx:02d}.png"
        faces.append(_face_crop(turns[idx],out))

    refs=[a.source,*[x for x in a.detail if x.is_file()]]
    source_sheet=_labelled_sheet(
        [(f"SOURCE {i+1}",x) for i,x in enumerate(refs[:8])],
        a.out/"source_sheet.jpg",
        title="SOURCE REFERENCES",
        columns=4,
        cell=320,
    )
    turn_sheet=_labelled_sheet(
        [(f"TURN {i*15:03d}",x) for i,x in enumerate(turns)],
        a.out/"turntable_sheet.jpg",
        title="KNOWN-BAD MONJA — 24 VIEWS",
        columns=6,
        cell=280,
    )
    face_sheet=_labelled_sheet(
        [(f"FACE {idx*15:03d}",x) for idx,x in zip(face_indices,faces)],
        a.out/"face_sheet.jpg",
        title="KNOWN-BAD MONJA — FACE CLOSEUPS",
        columns=3,
        cell=420,
    )
    board=_stack_boards(
        [("SOURCE REFERENCES",source_sheet),("CANDIDATE TURNTABLE",turn_sheet),("FACE CLOSEUPS",face_sheet)],
        a.out/"board.jpg",
    )
    payload={
        "schema":1,
        "model":str(a.model),
        "source":str(a.source),
        "turns":[str(x) for x in turns],
        "face_indices":face_indices,
        "faces":[str(x) for x in faces],
        "board":str(board),
    }
    (a.out/"evidence.json").write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(payload,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
