#!/usr/bin/env python3
"""Evaluate ORIGINAL CoD4 XAnim v17 bone-track keyframes in native time.

Source tracks decoded by iw3_xanim_bones_v17.py. For each original joint,
recover the quantized (x,y,z,w) or (2-component) quaternion, honor source
quat sign continuity and sample translations and rotations at a given frame.

IMPORTANT: original Quat2 returns a 2-component pair rather than guessing
a CoD-to-glTF axis. This is source-compatible PRE-SKINNING material; it
does not yet animate vertices on Android. Never publish bone names or
copyrighted animation samples in public CI reports.
"""
from __future__ import annotations
from bisect import bisect_right
import math

SOURCE_Q_SCALE=32767.0
W_SQUARED=0x3FFF0001


def pairs(track:list[int],items:int,total_frames:int):
    if not track:
        return [0] if items==1 else list(range(items))
    if len(track)!=items or any(x<0 or x>=total_frames for x in track):
        raise ValueError("Invalid IW3 original XAnim keyframe indices")
    if any(track[i]>=track[i+1] for i in range(len(track)-1)):
        raise ValueError("Out-of-order IW3 original keyframe sequence")
    return track


def interpolate(items:list,indices:list[int],frame:float,frames:int):
    if not items: return None
    if len(items)==1: return tuple(float(x) for x in items[0])
    indices=pairs(indices,len(items),frames)
    pos=bisect_right(indices,frame)
    if pos<=0:return tuple(float(x) for x in items[0])
    if pos>=len(items):return tuple(float(x) for x in items[-1])
    a,b=pos-1,pos
    span=indices[b]-indices[a]
    t=(frame-indices[a])/span
    return tuple(float(items[a][k])*(1.-t)+float(items[b][k])*t
                 for k in range(len(items[a])))


def original_quantized_quaternion(track:dict,frame:float,total_frames:int):
    kind=track["kind"]
    if kind=="identity":
        return ("quat2",(0.,1.))
    if kind not in ("half","full"):
        raise ValueError("Unknown CoD4 source quaternion format")
    raw=track["raw_values"]
    indices=pairs(track["frame_indices"],len(raw),total_frames)
    vectors=[]
    for current in raw:
        sq=sum(x*x for x in current)
        w=math.floor(math.sqrt(max(0,W_SQUARED-sq))+0.5)
        values=[*current,int(w)]
        # OAT ConsumeQuat/ConsumeQuat2 and continuous-sign logic:
        # first flip from the exported bone mask, later shortest dot.
        if len(vectors)==0 and track.get("flip_first",False):
            values=[-x for x in values]
        if vectors and sum(a*b for a,b in zip(values,vectors[-1]))<0:
            values=[-x for x in values]
        vectors.append(values)
    normalized=[[x/SOURCE_Q_SCALE for x in values] for values in vectors]
    selected=interpolate(normalized,indices,frame,total_frames)
    if selected is None: raise ValueError("CoD4 source quat track unexpectedly empty")
    length=math.sqrt(sum(x*x for x in selected))
    if length<1.e-9: raise ValueError("Zero original keyframed quaternion")
    selected=tuple(x/length for x in selected)
    return ("quat2" if kind=="half" else "quat4",selected)


def original_translation(track:dict,frame:float,total_frames:int):
    if track["kind"]=="none": return None
    return interpolate(track["xyz"],track["frame_indices"],frame,total_frames)


def source_animation_pose(animation:dict,frame:float):
    if not math.isfinite(frame):raise ValueError("Invalid animation clock")
    frames=animation["frames"]
    if frames<1 or frames>65536:raise ValueError("Invalid IW3 frame count")
    if animation["looped"]:
        frame=frame%frames
    else:
        frame=max(0.,min(frame,frames-1))
    bones=[]
    for bone in animation["bones"]:
        bones.append({
            "original_joint_name":bone["name"],
            "source_quaternion":original_quantized_quaternion(
                bone["rotation"],frame,frames),
            "source_translation":original_translation(
                bone["position"],frame,frames),
        })
    return {"original_frame":frame,"fps":animation["fps"],
            "bones":bones,"root_delta_present":animation["root_delta"] is not None,
            "original_animation_playing_in_vril":False}
