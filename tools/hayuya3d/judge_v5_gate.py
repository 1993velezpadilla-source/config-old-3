#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def _load(path:Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _finite(v):
    try:
        f=float(v)
        return f if math.isfinite(f) else None
    except Exception:
        return None


def evaluate(policy,visual,qrealign,siglip,face,pyiqa,*,ignore_calibration_lock=False):
    reasons=[]
    telemetry=[]

    if not visual or visual.get("passed") is not True:
        reasons.append("visual_eye_gate_not_passed")

    required_views=list(policy.get("required_views",[]))
    qrows={str(x.get("name")):x for x in (qrealign or {}).get("images",[]) if isinstance(x,dict)}
    if not qrealign or qrealign.get("ready") is not True:
        reasons.append("qrealign_missing_or_failed")
    for name in required_views:
        if name not in qrows:
            reasons.append(f"qrealign_missing_view:{name}")

    qpol=policy.get("qrealign",{})
    for name in ("front","three_quarter","side"):
        row=qrows.get(name)
        if not row:
            continue
        score=_finite(row.get("score"))
        bad=_finite(row.get("poor_bad_mass"))
        if score is None or score<float(qpol.get("main_min_score",0.45)):
            reasons.append(f"qrealign_low_quality:{name}:{score}")
        if bad is None or bad>float(qpol.get("main_max_poor_bad_mass",0.35)):
            reasons.append(f"qrealign_poor_bad_mass:{name}:{bad}")

    frow=qrows.get("face")
    if frow:
        score=_finite(frow.get("score"))
        good=_finite(frow.get("good_excellent_mass"))
        bad=_finite(frow.get("poor_bad_mass"))
        if score is None or score<float(qpol.get("face_min_score",0.55)):
            reasons.append(f"qrealign_face_low_quality:{score}")
        if good is None or good<float(qpol.get("face_min_good_excellent_mass",0.50)):
            reasons.append(f"qrealign_face_insufficient_good_mass:{good}")
        if bad is None or bad>float(qpol.get("face_max_poor_bad_mass",0.20)):
            reasons.append(f"qrealign_face_poor_bad_mass:{bad}")

    if not siglip or siglip.get("ready") is not True:
        reasons.append("siglip2_missing_or_failed")
    srows={str(x.get("name")):_finite(x.get("cosine_similarity")) for x in (siglip or {}).get("candidates",[]) if isinstance(x,dict)}
    sp=policy.get("siglip2",{})
    names=list(sp.get("full_body_views",["front","three_quarter","side"]))
    vals=[srows.get(name) for name in names]
    vals=[x for x in vals if x is not None]
    if len(vals)!=len(names):
        reasons.append("siglip2_missing_full_body_view")
    else:
        best=max(vals)
        mean=sum(vals)/len(vals)
        telemetry.extend([f"siglip_best={best:.4f}",f"siglip_mean={mean:.4f}"])
        if best<float(sp.get("best_full_body_catastrophic_floor",0.20)):
            reasons.append(f"siglip2_catastrophic_best:{best:.4f}")
        if mean<float(sp.get("mean_full_body_catastrophic_floor",0.12)):
            reasons.append(f"siglip2_catastrophic_mean:{mean:.4f}")

    fpol=policy.get("face_identity",{})
    if bool(fpol.get("required",True)):
        if not face or face.get("ready") is not True:
            reasons.append("face_identity_missing_or_failed")
        else:
            sim=_finite(face.get("cosine_similarity"))
            telemetry.append(f"adaface_cosine={sim}" if sim is not None else "adaface_cosine=None")
            if sim is None or sim<float(fpol.get("cosine_catastrophic_floor",0.30)):
                reasons.append(f"adaface_catastrophic_identity_mismatch:{sim}")
            elif sim<float(fpol.get("cosine_provisional_accept",0.40)):
                reasons.append(f"adaface_identity_below_provisional_accept:{sim}")

    if not pyiqa or pyiqa.get("ready") is not True:
        reasons.append("pyiqa_ensemble_missing_or_failed")
    else:
        have=set((pyiqa.get("metrics") or {}).keys())
        for metric in policy.get("pyiqa",{}).get("required_metrics",[]):
            if metric not in have:
                reasons.append(f"pyiqa_missing_metric:{metric}")

    metric_pass=not reasons
    approval_enabled=bool(policy.get("approval_enabled",False))
    calibration_status=str(policy.get("calibration_status","unknown"))
    calibration_locked=(not approval_enabled or calibration_status!="ready")
    if calibration_locked and not ignore_calibration_lock:
        reasons.append(f"automatic_approval_locked:{calibration_status}")

    passed=not reasons
    return {
        "schema":1,
        "policy_id":policy.get("id"),
        "metric_pass":metric_pass,
        "automatic_approval_enabled":approval_enabled,
        "calibration_status":calibration_status,
        "passed":passed,
        "status":"APPROVED" if passed else ("REJECTED" if not metric_pass else "BLOCKED_UNCALIBRATED"),
        "hard_veto":True,
        "reasons":reasons,
        "telemetry":telemetry,
        "method":"hayuya-judge-v5-hard-veto-ensemble",
    }


def _self_test()->int:
    policy={
        "id":"selftest","approval_enabled":True,"calibration_status":"ready",
        "required_views":["front","three_quarter","side","face"],
        "qrealign":{"main_min_score":0.45,"main_max_poor_bad_mass":0.35,"face_min_score":0.55,"face_min_good_excellent_mass":0.5,"face_max_poor_bad_mass":0.2},
        "siglip2":{"full_body_views":["front","three_quarter","side"],"best_full_body_catastrophic_floor":0.2,"mean_full_body_catastrophic_floor":0.12},
        "face_identity":{"required":True,"cosine_catastrophic_floor":0.3,"cosine_provisional_accept":0.4},
        "pyiqa":{"required_metrics":["topiq_nr","musiq","clipiqa+","maniqa","topiq_nr-face"]},
    }
    def q(face_score=.8,face_good=.8,face_bad=.05):
        rows=[]
        for n in ["front","three_quarter","side"]:
            rows.append({"name":n,"score":.8,"poor_bad_mass":.05,"good_excellent_mass":.8})
        rows.append({"name":"face","score":face_score,"poor_bad_mass":face_bad,"good_excellent_mass":face_good})
        return {"ready":True,"images":rows}
    visual={"passed":True}
    sig={"ready":True,"candidates":[{"name":n,"cosine_similarity":.5} for n in ["front","three_quarter","side","face"]]}
    face={"ready":True,"cosine_similarity":.65}
    iq={"ready":True,"metrics":{n:{} for n in policy["pyiqa"]["required_metrics"]}}
    assert evaluate(policy,visual,q(),sig,face,iq)["passed"]
    assert not evaluate(policy,visual,q(.25,.1,.7),sig,face,iq)["passed"]
    assert not evaluate(policy,visual,q(),sig,{"ready":True,"cosine_similarity":.1},iq)["passed"]
    assert not evaluate(policy,visual,None,sig,face,iq)["passed"]
    print("HAYUYA_JUDGE_V5_SELFTEST PASS")
    return 0


def main()->int:
    p=argparse.ArgumentParser(description="HAYUYA Judge v5 hard-veto approval gate.")
    p.add_argument("--policy",type=Path)
    p.add_argument("--visual",type=Path)
    p.add_argument("--qrealign",type=Path)
    p.add_argument("--siglip2",type=Path)
    p.add_argument("--face",type=Path)
    p.add_argument("--pyiqa",type=Path)
    p.add_argument("--json",type=Path)
    p.add_argument("--ignore-calibration-lock",action="store_true")
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test:
        return _self_test()
    required=[a.policy,a.visual,a.qrealign,a.siglip2,a.face,a.pyiqa,a.json]
    if any(x is None for x in required):
        p.error("all report paths and --json are required unless --self-test")
    payload=evaluate(
        _load(a.policy),_load(a.visual),_load(a.qrealign),_load(a.siglip2),_load(a.face),_load(a.pyiqa),
        ignore_calibration_lock=a.ignore_calibration_lock,
    )
    a.json.parent.mkdir(parents=True,exist_ok=True)
    a.json.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(payload,indent=2))
    return 0 if payload["passed"] else 7


if __name__=="__main__":
    raise SystemExit(main())
