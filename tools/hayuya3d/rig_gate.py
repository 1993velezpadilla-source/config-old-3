#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import struct
from dataclasses import asdict, dataclass
from pathlib import Path

JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942

_COMPONENT = {
    5120: ("b", 1),
    5121: ("B", 1),
    5122: ("h", 2),
    5123: ("H", 2),
    5125: ("I", 4),
    5126: ("f", 4),
}
_WIDTH = {
    "SCALAR": 1,
    "VEC2": 2,
    "VEC3": 3,
    "VEC4": 4,
}

def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())

def _load_glb(path: Path) -> tuple[dict, bytes]:
    blob = path.read_bytes()
    if len(blob) < 20 or blob[:4] != b"glTF":
        raise ValueError("not a GLB")
    version, total = struct.unpack_from("<II", blob, 4)
    if version != 2 or total > len(blob):
        raise ValueError("invalid GLB header")
    offset = 12
    doc = None
    binary = b""
    while offset + 8 <= total:
        length, chunk_type = struct.unpack_from("<II", blob, offset)
        offset += 8
        end = offset + length
        if end > total:
            raise ValueError("chunk exceeds GLB length")
        data = blob[offset:end]
        offset = end
        if chunk_type == JSON_CHUNK:
            doc = json.loads(data.rstrip(b"\x00 \t\r\n").decode("utf-8"))
        elif chunk_type == BIN_CHUNK:
            binary = data
    if doc is None:
        raise ValueError("GLB missing JSON chunk")
    return doc, binary

def _accessor(doc: dict, binary: bytes, index: int):
    acc = doc["accessors"][index]
    if "bufferView" not in acc:
        raise ValueError(f"sparse/implicit accessor unsupported:{index}")
    view = doc["bufferViews"][acc["bufferView"]]
    fmt, scalar_bytes = _COMPONENT[acc["componentType"]]
    width = _WIDTH[acc["type"]]
    count = int(acc["count"])
    base = int(view.get("byteOffset", 0)) + int(acc.get("byteOffset", 0))
    stride = int(view.get("byteStride", scalar_bytes * width))
    item = struct.Struct("<" + fmt * width)
    mv = memoryview(binary)
    return [item.unpack_from(mv, base + i * stride) for i in range(count)]

def _weighted_joint_names(doc: dict, binary: bytes, node_names: list[str]) -> list[str]:
    names=set()
    meshes=doc.get("meshes",[])
    skins=doc.get("skins",[])
    for node in doc.get("nodes",[]):
        mesh_idx=node.get("mesh")
        skin_idx=node.get("skin")
        if not isinstance(mesh_idx,int) or not isinstance(skin_idx,int):
            continue
        if not (0<=mesh_idx<len(meshes) and 0<=skin_idx<len(skins)):
            continue
        joints=skins[skin_idx].get("joints",[]) or []
        for prim in meshes[mesh_idx].get("primitives",[]) or []:
            attrs=prim.get("attributes",{}) or {}
            jidx=attrs.get("JOINTS_0")
            widx=attrs.get("WEIGHTS_0")
            if not isinstance(jidx,int) or not isinstance(widx,int):
                continue
            joint_rows=_accessor(doc,binary,jidx)
            weight_rows=_accessor(doc,binary,widx)
            for jr,wr in zip(joint_rows,weight_rows):
                for local_joint,weight in zip(jr,wr):
                    if float(weight) <= 1e-5:
                        continue
                    lj=int(local_joint)
                    if 0<=lj<len(joints):
                        ni=joints[lj]
                        if isinstance(ni,int) and 0<=ni<len(node_names):
                            names.add(node_names[ni])
    return sorted(names)

def _load_spec(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def _target_names(doc: dict) -> list[str]:
    names: list[str] = []
    for mesh in doc.get("meshes", []):
        extras = mesh.get("extras") or {}
        for name in extras.get("targetNames", []) or []:
            if isinstance(name, str):
                names.append(name)
    return names

def _matches(names: list[str], aliases: list[str]) -> bool:
    normalized = {_norm(n) for n in names}
    return any(_norm(a) in normalized for a in aliases)

def _pattern_hits(names: list[str], patterns: list[str]) -> list[str]:
    pats = [_norm(p) for p in patterns]
    hits = []
    for name in names:
        n = _norm(name)
        if any(p and p in n for p in pats):
            hits.append(name)
    return sorted(set(hits))

@dataclass
class RigReport:
    schema: int
    skeleton_type: str
    valid_glb: bool
    skins: int
    joints: int
    weighted_joints: int
    weighted_joint_names: list[str]
    weighted_required_groups_found: int
    weighted_required_group_fraction: float
    required_groups_found: int
    required_groups_total: int
    required_group_fraction: float
    missing_required_groups: list[str]
    animation_clips: list[str]
    rig_ready: bool
    animation_ready: bool
    preview_animation_ready: bool
    facial: dict
    secondary_motion: dict
    warnings: list[str]

def inspect(glb: Path, spec_path: Path) -> RigReport:
    spec = _load_spec(spec_path)
    doc, binary = _load_glb(glb)
    nodes = doc.get("nodes", [])
    node_names = [str(n.get("name", "")) for n in nodes]
    skins = doc.get("skins", [])
    joint_indices = set()
    for skin in skins:
        for idx in skin.get("joints", []) or []:
            if isinstance(idx, int):
                joint_indices.add(idx)
    joint_names = [
        node_names[i] for i in sorted(joint_indices)
        if 0 <= i < len(node_names)
    ]
    weighted_joint_names=_weighted_joint_names(doc,binary,node_names)

    required = spec.get("required_bones", {})
    missing = []
    found = 0
    for group, aliases in required.items():
        if _matches(joint_names, aliases):
            found += 1
        else:
            missing.append(group)
    total = max(1, len(required))
    fraction = found / total
    weighted_found=0
    for group,aliases in required.items():
        if _matches(weighted_joint_names,aliases):
            weighted_found += 1
    weighted_fraction=weighted_found/total

    animations = []
    for i, anim in enumerate(doc.get("animations", []) or []):
        name = str(anim.get("name") or f"clip_{i}")
        animations.append(name)

    targets = _target_names(doc)
    facial_optional = spec.get("facial_optional", {})
    jaw = _matches(joint_names, facial_optional.get("jaw", [])) or bool(
        _pattern_hits(targets, ["jaw", "mouthopen", "viseme"])
    )
    eye_l = _matches(joint_names, facial_optional.get("eye_l", []))
    eye_r = _matches(joint_names, facial_optional.get("eye_r", []))
    blink_l = _matches(joint_names, facial_optional.get("eyelid_l", [])) or bool(
        _pattern_hits(targets, ["blink_l", "blinkleft", "eyeblinkleft"])
    )
    blink_r = _matches(joint_names, facial_optional.get("eyelid_r", [])) or bool(
        _pattern_hits(targets, ["blink_r", "blinkright", "eyeblinkright"])
    )

    secondary = spec.get("secondary_motion_patterns", {})
    hair_hits = _pattern_hits(node_names, secondary.get("hair", []))
    cloth_hits = _pattern_hits(node_names, secondary.get("cloth", []))

    rules = spec.get("rules", {})
    min_joints = int(rules.get("min_joint_count", 15))
    min_fraction = float(rules.get("ready_required_group_fraction", 0.8))
    min_weighted_joints = int(rules.get("min_weighted_joint_count", 12))
    min_weighted_fraction = float(rules.get("ready_weighted_group_fraction", 0.65))
    require_skin = bool(rules.get("require_skin", True))
    rig_ready = (
        (not require_skin or len(skins) > 0)
        and len(joint_indices) >= min_joints
        and fraction >= min_fraction
        and len(weighted_joint_names) >= min_weighted_joints
        and weighted_fraction >= min_weighted_fraction
    )

    warnings = []
    if not skins:
        warnings.append("no_skin")
    if len(joint_indices) < min_joints:
        warnings.append(f"too_few_joints:{len(joint_indices)}<{min_joints}")
    if fraction < min_fraction:
        warnings.append(f"missing_core_bones:{found}/{len(required)}")
    if len(weighted_joint_names) < min_weighted_joints:
        warnings.append(f"too_few_weighted_joints:{len(weighted_joint_names)}<{min_weighted_joints}")
    if weighted_fraction < min_weighted_fraction:
        warnings.append(f"insufficient_weighted_core_bones:{weighted_found}/{len(required)}")
    if not animations:
        warnings.append("no_embedded_animation_clips")
    if not jaw:
        warnings.append("no_jaw_control")
    if not (blink_l and blink_r):
        warnings.append("no_blink_controls")

    return RigReport(
        schema=1,
        skeleton_type=str(spec.get("id", "hayuya_humanoid_v1")),
        valid_glb=True,
        skins=len(skins),
        joints=len(joint_indices),
        weighted_joints=len(weighted_joint_names),
        weighted_joint_names=weighted_joint_names,
        weighted_required_groups_found=weighted_found,
        weighted_required_group_fraction=round(weighted_fraction,6),
        required_groups_found=found,
        required_groups_total=len(required),
        required_group_fraction=round(fraction, 6),
        missing_required_groups=missing,
        animation_clips=animations,
        rig_ready=rig_ready,
        animation_ready=rig_ready,
        preview_animation_ready=rig_ready and bool(animations),
        facial={
            "jaw": jaw,
            "eye_l": eye_l,
            "eye_r": eye_r,
            "blink_l": blink_l,
            "blink_r": blink_r,
            "morph_targets": targets,
        },
        secondary_motion={
            "hair_nodes": hair_hits,
            "cloth_nodes": cloth_hits,
            "hair_ready": bool(hair_hits),
            "cloth_ready": bool(cloth_hits),
        },
        warnings=warnings,
    )

def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a GLB for HAYUYA humanoid rig/animation readiness.")
    parser.add_argument("glb", type=Path)
    parser.add_argument(
        "--spec",
        type=Path,
        default=Path("hayuya/standards/hayuya_humanoid_v1.json"),
    )
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    try:
        report = inspect(args.glb, args.spec)
        payload = json.dumps(asdict(report), indent=2)
        print(payload)
        if args.json:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(payload + "\n", encoding="utf-8")
        return 0
    except Exception as exc:
        payload = {
            "schema": 1,
            "skeleton_type": "hayuya_humanoid_v1",
            "valid_glb": False,
            "rig_ready": False,
            "animation_ready": False,
            "preview_animation_ready": False,
            "warnings": [f"{type(exc).__name__}:{exc}"],
        }
        print(json.dumps(payload, indent=2))
        if args.json:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
