#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import math
import struct
from dataclasses import asdict, dataclass
from pathlib import Path


JSON_CHUNK=0x4E4F534A
BIN_CHUNK=0x004E4942


@dataclass
class SemanticRigReport:
    schema:int
    source:str
    output:str
    skin_index:int
    joint_count:int
    root_joint:int
    chest_joint:int
    lateral_axis:int
    torso_path:list[int]
    head_path:list[int]
    left_arm_path:list[int]
    right_arm_path:list[int]
    left_leg_path:list[int]
    right_leg_path:list[int]
    mapping:dict[str,str]
    core_groups:list[str]
    confidence:float
    ready:bool
    warnings:list[str]


def _load_glb(path:Path):
    blob=path.read_bytes()
    if len(blob)<20 or blob[:4]!=b"glTF":
        raise ValueError("not_a_glb")
    version,total=struct.unpack_from("<II",blob,4)
    if version!=2 or total>len(blob):
        raise ValueError("invalid_glb_header")
    off=12
    doc=None
    chunks=[]
    while off+8<=total:
        length,kind=struct.unpack_from("<II",blob,off)
        off+=8
        end=off+length
        if end>total:
            raise ValueError("glb_chunk_exceeds_file")
        payload=blob[off:end]
        off=end
        chunks.append((kind,payload))
        if kind==JSON_CHUNK:
            doc=json.loads(payload.rstrip(b"\x00 \t\r\n").decode("utf-8"))
    if doc is None:
        raise ValueError("glb_missing_json")
    return doc,chunks


def _write_glb(path:Path,doc:dict,chunks):
    json_blob=json.dumps(doc,separators=(",",":")).encode("utf-8")
    json_blob+=b" "*((-len(json_blob))%4)
    output_chunks=[]
    replaced=False
    for kind,payload in chunks:
        if kind==JSON_CHUNK and not replaced:
            output_chunks.append((kind,json_blob))
            replaced=True
        else:
            padded=payload+b"\x00"*((-len(payload))%4)
            output_chunks.append((kind,padded))
    if not replaced:
        output_chunks.insert(0,(JSON_CHUNK,json_blob))
    total=12+sum(8+len(payload) for _,payload in output_chunks)
    out=bytearray(struct.pack("<4sII",b"glTF",2,total))
    for kind,payload in output_chunks:
        out.extend(struct.pack("<II",len(payload),kind))
        out.extend(payload)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(out)
    if path.read_bytes()[:4]!=b"glTF":
        raise RuntimeError("semantic_rig_output_invalid_glb")


def _identity():
    return [
        [1.0,0.0,0.0,0.0],
        [0.0,1.0,0.0,0.0],
        [0.0,0.0,1.0,0.0],
        [0.0,0.0,0.0,1.0],
    ]


def _mul(a,b):
    return [[sum(a[r][k]*b[k][c] for k in range(4)) for c in range(4)] for r in range(4)]


def _node_matrix(node):
    matrix=node.get("matrix")
    if isinstance(matrix,list) and len(matrix)==16:
        return [[float(matrix[c*4+r]) for c in range(4)] for r in range(4)]
    tx,ty,tz=[float(x) for x in node.get("translation",[0.0,0.0,0.0])]
    sx,sy,sz=[float(x) for x in node.get("scale",[1.0,1.0,1.0])]
    x,y,z,w=[float(x) for x in node.get("rotation",[0.0,0.0,0.0,1.0])]
    xx,yy,zz=x*x,y*y,z*z
    xy,xz,yz=x*y,x*z,y*z
    wx,wy,wz=w*x,w*y,w*z
    rot=[
        [1.0-2.0*(yy+zz),2.0*(xy-wz),2.0*(xz+wy),0.0],
        [2.0*(xy+wz),1.0-2.0*(xx+zz),2.0*(yz-wx),0.0],
        [2.0*(xz-wy),2.0*(yz+wx),1.0-2.0*(xx+yy),0.0],
        [0.0,0.0,0.0,1.0],
    ]
    for r,s in enumerate((sx,sy,sz)):
        for row in range(3):
            rot[row][r]*=s
    rot[0][3]=tx
    rot[1][3]=ty
    rot[2][3]=tz
    return rot


def _vsub(a,b):
    return [a[i]-b[i] for i in range(3)]


def _dot(a,b):
    return sum(a[i]*b[i] for i in range(3))


def _norm(a):
    return math.sqrt(max(0.0,_dot(a,a)))


def _unit(a):
    length=_norm(a)
    if length<=1e-12:
        raise ValueError("zero_length_direction")
    return [x/length for x in a]


def _semantic_mapping(doc:dict,skin_index:int):
    nodes=doc.get("nodes",[])
    skins=doc.get("skins",[])
    if not (0<=skin_index<len(skins)):
        raise ValueError("skin_index_out_of_range")
    joints=[int(i) for i in (skins[skin_index].get("joints") or [])]
    if len(joints)<15:
        raise ValueError(f"too_few_anigen_joints:{len(joints)}")
    joint_set=set(joints)
    parents={i:None for i in joints}
    children={i:[] for i in joints}
    for parent in joints:
        for child in nodes[parent].get("children",[]) or []:
            if child in joint_set:
                if parents[child] is not None:
                    raise ValueError(f"joint_has_multiple_parents:{child}")
                parents[child]=parent
                children[parent].append(child)
    roots=[i for i in joints if parents[i] is None]
    if len(roots)!=1:
        raise ValueError(f"expected_single_joint_root:{roots}")
    root=roots[0]

    world={}
    def world_matrix(i):
        if i in world:
            return world[i]
        local=_node_matrix(nodes[i])
        parent=parents[i]
        world[i]=local if parent is None else _mul(world_matrix(parent),local)
        return world[i]
    def position(i):
        m=world_matrix(i)
        return [m[0][3],m[1][3],m[2][3]]
    def descendants(i):
        out=[i]
        for child in children[i]:
            out.extend(descendants(child))
        return out
    def dcount(i):
        return len(descendants(i))
    def single_chain(start):
        path=[]
        cur=start
        seen=set()
        while cur not in seen:
            seen.add(cur)
            path.append(cur)
            if len(children[cur])!=1:
                break
            cur=children[cur][0]
        return path

    root_children=children[root]
    if len(root_children)<3:
        raise ValueError(f"root_needs_three_body_branches:{root_children}")
    torso_child=max(root_children,key=dcount)
    leg_children=[c for c in root_children if c!=torso_child]
    if len(leg_children)!=2:
        raise ValueError(f"expected_two_leg_branches:{leg_children}")

    torso_path=[]
    cur=torso_child
    chest=None
    seen=set()
    while cur not in seen:
        seen.add(cur)
        torso_path.append(cur)
        if len(children[cur])>=3:
            chest=cur
            break
        if len(children[cur])!=1:
            break
        cur=children[cur][0]
    if chest is None:
        raise ValueError("torso_has_no_shoulder_head_fork")

    up=_unit(_vsub(position(chest),position(root)))
    chest_children=children[chest]
    if len(chest_children)<3:
        raise ValueError(f"chest_needs_three_branches:{chest_children}")

    head_scores={}
    for child in chest_children:
        head_scores[child]=max(
            _dot(_vsub(position(d),position(chest)),up)
            for d in descendants(child)
        )
    ranked=sorted(head_scores,key=head_scores.get,reverse=True)
    head_child=ranked[0]
    arm_children=sorted(
        [c for c in chest_children if c!=head_child],
        key=dcount,
        reverse=True,
    )[:2]
    if len(arm_children)!=2:
        raise ValueError(f"expected_two_arm_branches:{arm_children}")

    head_path=single_chain(head_child)
    arm_paths={child:single_chain(child) for child in arm_children}
    leg_paths={child:single_chain(child) for child in leg_children}
    if len(head_path)<2:
        raise ValueError(f"head_chain_too_short:{head_path}")
    if any(len(path)<3 for path in arm_paths.values()):
        raise ValueError(f"arm_chain_too_short:{arm_paths}")
    if any(len(path)<3 for path in leg_paths.values()):
        raise ValueError(f"leg_chain_too_short:{leg_paths}")

    arm_ends={c:arm_paths[c][-1] for c in arm_children}
    delta=_vsub(position(arm_ends[arm_children[0]]),position(arm_ends[arm_children[1]]))
    lateral_axis=max(range(3),key=lambda axis:abs(delta[axis]))
    if abs(delta[lateral_axis])<=1e-6:
        raise ValueError("unable_to_resolve_lateral_axis")

    # AniGen's public exporter converts its Z-up working coordinates to glTF Y-up
    # with an X sign flip. Therefore positive glTF lateral is anatomical left.
    def side_for(node_a,node_b):
        return "l" if position(node_a)[lateral_axis]>position(node_b)[lateral_axis] else "r"

    arm_side={}
    for child in arm_children:
        other=arm_children[1] if child==arm_children[0] else arm_children[0]
        arm_side[child]=side_for(arm_ends[child],arm_ends[other])
    if set(arm_side.values())!={"l","r"}:
        raise ValueError(f"arm_side_resolution_failed:{arm_side}")

    leg_ends={c:leg_paths[c][-1] for c in leg_children}
    leg_side={}
    for child in leg_children:
        other=leg_children[1] if child==leg_children[0] else leg_children[0]
        leg_side[child]=side_for(leg_ends[child],leg_ends[other])
    if set(leg_side.values())!={"l","r"}:
        raise ValueError(f"leg_side_resolution_failed:{leg_side}")

    mapping={root:"pelvis"}
    mapping[torso_path[0]]="spine"
    for index,node in enumerate(torso_path[1:-1],start=1):
        mapping[node]=f"spine_{index:02d}"
    mapping[chest]="chest"

    mapping[head_path[0]]="neck"
    for index,node in enumerate(head_path[1:-1],start=1):
        mapping[node]=f"neck_{index:02d}"
    mapping[head_path[-1]]="head"

    resolved_arm_paths={}
    for child,path in arm_paths.items():
        side=arm_side[child]
        if len(path)>=4:
            mapping[path[0]]=f"clavicle_{side}"
            mapping[path[1]]=f"upperarm_{side}"
            mapping[path[2]]=f"lowerarm_{side}"
            mapping[path[3]]=f"hand_{side}"
            hand=path[3]
            core=path[:4]
        else:
            mapping[path[0]]=f"upperarm_{side}"
            mapping[path[1]]=f"lowerarm_{side}"
            mapping[path[2]]=f"hand_{side}"
            hand=path[2]
            core=path[:3]
        finger_nodes=[n for n in descendants(hand) if n!=hand and n not in mapping]
        for index,node in enumerate(finger_nodes):
            mapping[node]=f"finger_{side}_{index:02d}"
        resolved_arm_paths[side]=core

    resolved_leg_paths={}
    for child,path in leg_paths.items():
        side=leg_side[child]
        mapping[path[0]]=f"thigh_{side}"
        mapping[path[1]]=f"calf_{side}"
        mapping[path[2]]=f"foot_{side}"
        if len(path)>=4:
            mapping[path[3]]=f"toe_{side}"
        for index,node in enumerate(path[4:],start=1):
            mapping[node]=f"toe_{side}_{index:02d}"
        resolved_leg_paths[side]=path[:4]

    core={
        "pelvis","spine","chest","neck","head",
        "upperarm_l","lowerarm_l","hand_l",
        "upperarm_r","lowerarm_r","hand_r",
        "thigh_l","calf_l","foot_l",
        "thigh_r","calf_r","foot_r",
    }
    mapped_core=sorted(core.intersection(mapping.values()))

    torso_length=max(_norm(_vsub(position(chest),position(root))),1e-9)
    head_margin=(
        head_scores[ranked[0]]-head_scores[ranked[1]]
        if len(ranked)>1 else 0.0
    )
    head_margin_ratio=max(0.0,min(1.0,head_margin/torso_length))
    structural_score=1.0
    if len(root_children)!=3:
        structural_score-=0.10
    if len(chest_children)!=3:
        structural_score-=0.10
    if len(mapped_core)<17:
        structural_score-=0.40
    if head_margin_ratio<0.08:
        structural_score-=0.15
    confidence=max(0.0,min(1.0,structural_score))

    return mapping,{
        "root":root,
        "chest":chest,
        "torso_path":torso_path,
        "head_path":head_path,
        "arm_paths":resolved_arm_paths,
        "leg_paths":resolved_leg_paths,
        "lateral_axis":lateral_axis,
        "core_groups":mapped_core,
        "confidence":confidence,
        "head_margin_ratio":head_margin_ratio,
    }


def convert(source:Path,output:Path,report_path:Path,skin_index:int=0)->SemanticRigReport:
    doc,chunks=_load_glb(source)
    mapping,meta=_semantic_mapping(doc,skin_index)
    new_doc=copy.deepcopy(doc)
    source_names={}
    for node_index,new_name in mapping.items():
        source_names[str(node_index)]=str(new_doc["nodes"][node_index].get("name",""))
        new_doc["nodes"][node_index]["name"]=new_name

    warnings=[]
    if meta["confidence"]<0.80:
        warnings.append(f"low_mapping_confidence:{meta['confidence']:.3f}")
    if len(meta["core_groups"])<17:
        warnings.append(f"missing_semantic_core_groups:{17-len(meta['core_groups'])}")

    ready=meta["confidence"]>=0.80 and len(meta["core_groups"])>=17
    if not ready:
        raise RuntimeError("AniGen semantic mapping did not reach the humanoid safety threshold")

    _write_glb(output,new_doc,chunks)
    report=SemanticRigReport(
        schema=1,
        source=str(source),
        output=str(output),
        skin_index=skin_index,
        joint_count=len(doc["skins"][skin_index].get("joints") or []),
        root_joint=int(meta["root"]),
        chest_joint=int(meta["chest"]),
        lateral_axis=int(meta["lateral_axis"]),
        torso_path=[int(x) for x in meta["torso_path"]],
        head_path=[int(x) for x in meta["head_path"]],
        left_arm_path=[int(x) for x in meta["arm_paths"]["l"]],
        right_arm_path=[int(x) for x in meta["arm_paths"]["r"]],
        left_leg_path=[int(x) for x in meta["leg_paths"]["l"]],
        right_leg_path=[int(x) for x in meta["leg_paths"]["r"]],
        mapping={
            source_names[str(index)]:name
            for index,name in sorted(mapping.items())
        },
        core_groups=meta["core_groups"],
        confidence=round(float(meta["confidence"]),6),
        ready=ready,
        warnings=warnings,
    )
    report_path.parent.mkdir(parents=True,exist_ok=True)
    report_path.write_text(json.dumps(asdict(report),indent=2)+"\n",encoding="utf-8")
    return report


def main()->int:
    p=argparse.ArgumentParser(description="Map AniGen generic joints to HAYUYA humanoid semantics.")
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    p.add_argument("--skin-index",type=int,default=0)
    a=p.parse_args()
    try:
        report=convert(a.input,a.output,a.report,a.skin_index)
        print("HAYUYA_ANIGEN_SEMANTIC_RIG",json.dumps(asdict(report),separators=(",",":")))
        return 0
    except Exception as exc:
        payload={
            "schema":1,
            "source":str(a.input),
            "output":str(a.output),
            "ready":False,
            "warnings":[f"{type(exc).__name__}:{exc}"],
        }
        a.report.parent.mkdir(parents=True,exist_ok=True)
        a.report.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(payload,indent=2))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
