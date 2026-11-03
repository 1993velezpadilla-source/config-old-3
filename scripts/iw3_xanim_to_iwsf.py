#!/usr/bin/env python3
"""Prototype original COD4 XAnim -> bounded native per-frame skin matrices.

IWSF v1 (<4sIIIf> header, then frame-major joint-major 16*f32 matrices)
contains skinning matrices for the IWSK original bone order and IWVM mesh.
Frame 0 is the original GLB bind pose. Later frames are driven by DELTAS
between actual original XAnim v17 per-bone keyframes (not invented motion).
This conservative delta-on-bind policy may differ from official CoD4 graph
blends and attachment behavior; preview only, not exact 1:1 animation.

This runs PRIVATELY on owner-supplied extracted COD4 OAT .glb and .xanim.
No proprietary bone matrices, model data or animation bytes in public repo.
"""
from __future__ import annotations
import argparse,json,math,struct
from pathlib import Path
from iw3_glb_to_iwsk import export as export_skin,BONE,HEADER as SKIN_HEADER
from iw3_glb_to_iwvm import mmul,mat_trs,IDENT
from iw3_xanim_bones_v17 import decode
from iw3_xanim_pose_sample import original_quantized_quaternion,original_translation

FRAME_HEADER=struct.Struct("<4sIIIf")
ORIGINAL_TO_QUAKE=(0.,-1.,0.,0., 1.,0.,0.,0., 0.,0.,1.,0., 0.,0.,0.,1.)
QUAKE_TO_ORIGINAL=(0.,1.,0.,0., -1.,0.,0.,0., 0.,0.,1.,0., 0.,0.,0.,1.)


def local_delta(bone,frame,frames,source_first):
    if bone is None: return IDENT
    kind,q=original_quantized_quaternion(bone["rotation"],frame,frames)
    _,first=source_first
    if kind=="quat2":
        # Source IW3 Quat2 is a yaw-like (z,w) pair. Keep genuine samples.
        cur=(0.,0.,q[0],q[1])
        orig=(0.,0.,first[0],first[1])
    else:
        cur=q
        orig=first
    inv=(-orig[0],-orig[1],-orig[2],orig[3])
    # Original CoD4 native axes -> Quake axes by conjugation.
    raw=mmul(mat_trs({"rotation":cur}),mat_trs({"rotation":inv}))
    d=mmul(mmul(ORIGINAL_TO_QUAKE,raw),QUAKE_TO_ORIGINAL)
    now=original_translation(bone["position"],frame,frames)
    start=original_translation(bone["position"],0,frames)
    if now is not None and start is not None:
        dt=(now[0]-start[0],now[1]-start[1],now[2]-start[2])
        d=list(d)
        d[12:15]=[dt[1],-dt[0],dt[2]]
        d=tuple(d)
    return d


def pack_original_preview(glb:Path,xanim:Path,max_frames:int=240):
    data,meta=export_skin(glb)
    _,_,_,joint_count,_=SKIN_HEADER.unpack_from(data)
    joints=[]
    offset=SKIN_HEADER.size
    for i in range(joint_count):
        name,parent,*m=BONE.unpack_from(data,offset+i*BONE.size)
        joints.append((name.split(b"\0",1)[0].decode("utf-8").lower(),
                       parent,tuple(m[:16]),tuple(m[16:])))
    anim=decode(xanim)
    frame_count=anim["frames"]
    if not (2<=frame_count<=min(max_frames,600)):
        raise ValueError("Original XAnim animation beyond experimental frame limit")
    fps=float(anim["fps"])
    if not 1<=fps<=300 or not math.isfinite(fps):
        raise ValueError("Invalid original CoD4 animation frame rate")
    bone_by_name={x["name"].lower():x for x in anim["bones"]}
    matching=[bone_by_name.get(name) for name,_,_,_ in joints]
    samples=[]
    for bone in matching:
        if bone:
            q=original_quantized_quaternion(bone["rotation"],0,frame_count)
            samples.append(q)
        else:
            samples.append(None)
    bind=[]
    def visit_bind(index,trail:set):
        if index in trail:raise ValueError("Cyclic original GLB bind joint graph")
        if bind[index] is not None:return bind[index]
        parent=joints[index][1]
        matrix=joints[index][2]
        bind[index]=(mmul(visit_bind(parent,trail|{index}),matrix)
                     if parent>=0 else matrix)
        return bind[index]
    bind=[None]*joint_count
    for i in range(joint_count):visit_bind(i,set())
    # Original OAT inverse bind matrices must be compatible with rest mesh.
    errs=[max(abs(v-(1. if k in (0,5,10,15) else 0.))
              for k,v in enumerate(mmul(bind[i],joints[i][3])))
          for i in range(joint_count)]
    if max(errs)>0.04:
        raise ValueError("Original bind matrices do not match GLB skeleton; refusing distorted preview")
    output=bytearray(FRAME_HEADER.pack(b"IWSF",1,frame_count,joint_count,fps))
    changed=set()
    max_delta=0.
    for frame in range(frame_count):
        globals_=[None]*joint_count
        def visit(index,trail:set):
            if index in trail:raise ValueError("Cycle in original joint animation")
            if globals_[index] is not None:return globals_[index]
            parent=joints[index][1]
            bone=matching[index]
            delta=(local_delta(bone,float(frame),frame_count,samples[index])
                   if bone else IDENT)
            local=mmul(joints[index][2],delta)
            globals_[index]=(mmul(visit(parent,trail|{index}),local)
                             if parent>=0 else local)
            return globals_[index]
        for i in range(joint_count):
            skin=mmul(visit(i,set()),joints[i][3])
            if any(not math.isfinite(v) or abs(v)>1e6 for v in skin):
                raise ValueError("Invalid original animated bone matrix")
            if frame:
                distance=max(abs(v-(1. if k in (0,5,10,15) else 0.))
                             for k,v in enumerate(skin))
                if distance>0.0001:changed.add(i)
                max_delta=max(max_delta,distance)
            output+=struct.pack("<16f",*skin)
    if not changed:
        raise ValueError("Original XAnim does not move any matching original model joint")
    return bytes(output),{
        "original_xanim_fps":fps,
        "original_animation_frames":frame_count,
        "original_gun_joint_count":joint_count,
        "joints_animated_from_original_keyframes":len(changed),
        "max_source_bone_matrix_delta":round(max_delta,6),
        "source_animation_asset_in_public_repo":False,
        "preview_uses_source_motion_not_exact_official_attachments":True,
        "native_runtime_playback_verified":False,
    }


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--owner-original-glb",type=Path,required=True)
    p.add_argument("--owner-original-xanim",type=Path,required=True)
    p.add_argument("--private-output",type=Path,required=True)
    a=p.parse_args()
    binary,metrics=pack_original_preview(a.owner_original_glb,a.owner_original_xanim)
    a.private_output.parent.mkdir(parents=True,exist_ok=True)
    a.private_output.write_bytes(binary)
    print(json.dumps(metrics,indent=2))
