#!/usr/bin/env python3
from __future__ import annotations

import json
import struct
from dataclasses import asdict, dataclass
from pathlib import Path


JSON_CHUNK = 0x4E4F534A


@dataclass
class RigAudit:
    path: str
    valid_glb: bool
    gltf_version: str | None
    mesh_count: int
    node_count: int
    skin_count: int
    animation_count: int
    material_count: int
    texture_count: int
    skinned_mesh_nodes: int
    joint_count: int
    morph_mesh_count: int
    morph_primitive_count: int
    morph_target_count: int
    morph_ready: bool
    rig_ready: bool
    animation_ready: bool
    material_channels: list[str]
    errors: list[str]
    warnings: list[str]


def read_glb_json(path: Path) -> dict:
    blob = path.read_bytes()
    if len(blob) < 20 or blob[:4] != b"glTF":
        raise ValueError("not a GLB")
    version, total_length = struct.unpack_from("<II", blob, 4)
    if version != 2:
        raise ValueError(f"unsupported glTF binary version: {version}")
    if total_length > len(blob):
        raise ValueError("GLB header length exceeds file size")

    offset = 12
    while offset + 8 <= total_length:
        chunk_length, chunk_type = struct.unpack_from("<II", blob, offset)
        offset += 8
        end = offset + chunk_length
        if end > total_length:
            raise ValueError("GLB chunk exceeds declared file length")
        if chunk_type == JSON_CHUNK:
            raw = blob[offset:end].rstrip(b"\x00 \t\r\n")
            return json.loads(raw.decode("utf-8"))
        offset = end
    raise ValueError("GLB JSON chunk missing")


def _material_channels(doc: dict) -> set[str]:
    channels: set[str] = set()
    for material in doc.get("materials", []):
        pbr = material.get("pbrMetallicRoughness", {})
        if "baseColorTexture" in pbr or "baseColorFactor" in pbr:
            channels.add("baseColor")
        if "metallicRoughnessTexture" in pbr or "metallicFactor" in pbr:
            channels.add("metallic")
        if "metallicRoughnessTexture" in pbr or "roughnessFactor" in pbr:
            channels.add("roughness")
        if "normalTexture" in material:
            channels.add("normal")
        if "occlusionTexture" in material:
            channels.add("occlusion")
        if "emissiveTexture" in material or "emissiveFactor" in material:
            channels.add("emissive")
    return channels


def audit_glb(path: Path) -> RigAudit:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        doc = read_glb_json(path)
    except Exception as exc:
        return RigAudit(
            path=str(path),
            valid_glb=False,
            gltf_version=None,
            mesh_count=0,
            node_count=0,
            skin_count=0,
            animation_count=0,
            material_count=0,
            texture_count=0,
            skinned_mesh_nodes=0,
            joint_count=0,
            morph_mesh_count=0,
            morph_primitive_count=0,
            morph_target_count=0,
            morph_ready=False,
            rig_ready=False,
            animation_ready=False,
            material_channels=[],
            errors=[f"{type(exc).__name__}: {exc}"],
            warnings=[],
        )

    nodes = doc.get("nodes", [])
    meshes = doc.get("meshes", [])
    skins = doc.get("skins", [])
    accessors = doc.get("accessors", [])
    animations = doc.get("animations", [])

    def node_ok(index) -> bool:
        return isinstance(index, int) and 0 <= index < len(nodes)

    def accessor_ok(index) -> bool:
        return isinstance(index, int) and 0 <= index < len(accessors)

    joint_total = 0
    for skin_index, skin in enumerate(skins):
        joints = skin.get("joints", [])
        joint_total += len(joints)
        if not joints:
            errors.append(f"skin[{skin_index}] has no joints")
        bad_joints = [j for j in joints if not node_ok(j)]
        if bad_joints:
            errors.append(f"skin[{skin_index}] invalid joint nodes: {bad_joints[:8]}")

        skeleton = skin.get("skeleton")
        if skeleton is not None and not node_ok(skeleton):
            errors.append(f"skin[{skin_index}] invalid skeleton node: {skeleton}")

        ibm = skin.get("inverseBindMatrices")
        if ibm is not None:
            if not accessor_ok(ibm):
                errors.append(f"skin[{skin_index}] invalid inverseBindMatrices accessor: {ibm}")
            else:
                count = int(accessors[ibm].get("count", 0))
                if count != len(joints):
                    errors.append(
                        f"skin[{skin_index}] inverseBindMatrices count {count} != joints {len(joints)}"
                    )
        else:
            warnings.append(f"skin[{skin_index}] has no inverseBindMatrices accessor")

    skinned_nodes = 0
    for node_index, node in enumerate(nodes):
        skin = node.get("skin")
        mesh = node.get("mesh")
        if skin is not None:
            if not isinstance(skin, int) or not (0 <= skin < len(skins)):
                errors.append(f"node[{node_index}] references invalid skin {skin}")
            if mesh is None:
                warnings.append(f"node[{node_index}] has skin but no mesh")
            elif not isinstance(mesh, int) or not (0 <= mesh < len(meshes)):
                errors.append(f"node[{node_index}] references invalid mesh {mesh}")
            else:
                skinned_nodes += 1

    morph_errors: list[str] = []
    morph_mesh_count = 0
    morph_primitive_count = 0
    morph_target_count = 0
    mesh_target_counts: dict[int,int] = {}

    for mesh_index, mesh in enumerate(meshes):
        primitive_counts: list[int] = []
        for primitive_index, primitive in enumerate(mesh.get("primitives", [])):
            attrs = primitive.get("attributes", {}) or {}
            position_accessor = attrs.get("POSITION")
            position_count = None
            if accessor_ok(position_accessor):
                position_count = int(accessors[position_accessor].get("count", 0))
            targets = primitive.get("targets") or []
            primitive_counts.append(len(targets))
            if not targets:
                continue
            morph_primitive_count += 1
            for target_index, target in enumerate(targets):
                if not isinstance(target, dict) or not target:
                    message=(
                        f"mesh[{mesh_index}].primitive[{primitive_index}] "
                        f"target[{target_index}] is empty or malformed"
                    )
                    morph_errors.append(message)
                    errors.append(message)
                    continue
                for semantic, accessor_index in target.items():
                    if semantic not in {"POSITION","NORMAL","TANGENT"}:
                        message=(
                            f"mesh[{mesh_index}].primitive[{primitive_index}] "
                            f"target[{target_index}] unsupported semantic {semantic}"
                        )
                        morph_errors.append(message)
                        errors.append(message)
                    if not accessor_ok(accessor_index):
                        message=(
                            f"mesh[{mesh_index}].primitive[{primitive_index}] "
                            f"target[{target_index}] invalid {semantic} accessor "
                            f"{accessor_index}"
                        )
                        morph_errors.append(message)
                        errors.append(message)
                        continue
                    accessor=accessors[accessor_index]
                    if str(accessor.get("type") or "")!="VEC3":
                        message=(
                            f"mesh[{mesh_index}].primitive[{primitive_index}] "
                            f"target[{target_index}] {semantic} accessor must be VEC3"
                        )
                        morph_errors.append(message)
                        errors.append(message)
                    if (
                        position_count is not None
                        and int(accessor.get("count",0))!=position_count
                    ):
                        message=(
                            f"mesh[{mesh_index}].primitive[{primitive_index}] "
                            f"target[{target_index}] {semantic} count "
                            f"{accessor.get('count')} != POSITION {position_count}"
                        )
                        morph_errors.append(message)
                        errors.append(message)

        nonzero=[count for count in primitive_counts if count>0]
        if nonzero:
            morph_mesh_count += 1
            target_count=max(nonzero)
            if len(set(primitive_counts))>1:
                message=(
                    f"mesh[{mesh_index}] primitives disagree on morph target count: "
                    f"{primitive_counts}"
                )
                morph_errors.append(message)
                errors.append(message)
            mesh_target_counts[mesh_index]=target_count
            morph_target_count += target_count
            mesh_weights=mesh.get("weights")
            if mesh_weights is not None and len(mesh_weights)!=target_count:
                message=(
                    f"mesh[{mesh_index}] weights length {len(mesh_weights)} "
                    f"!= morph target count {target_count}"
                )
                morph_errors.append(message)
                errors.append(message)
        else:
            mesh_target_counts[mesh_index]=0

    for node_index,node in enumerate(nodes):
        node_weights=node.get("weights")
        if node_weights is None:
            continue
        mesh_index=node.get("mesh")
        target_count=(
            mesh_target_counts.get(mesh_index,0)
            if isinstance(mesh_index,int)
            else 0
        )
        if target_count<=0:
            message=f"node[{node_index}] has weights but referenced mesh has no morph targets"
            morph_errors.append(message)
            errors.append(message)
        elif len(node_weights)!=target_count:
            message=(
                f"node[{node_index}] weights length {len(node_weights)} "
                f"!= morph target count {target_count}"
            )
            morph_errors.append(message)
            errors.append(message)

    has_joint_attributes = False
    for mesh_index, mesh in enumerate(meshes):
        for primitive_index, primitive in enumerate(mesh.get("primitives", [])):
            attrs = primitive.get("attributes", {})
            joint_keys = [key for key in attrs if key.startswith("JOINTS_")]
            weight_keys = [key for key in attrs if key.startswith("WEIGHTS_")]
            if joint_keys or weight_keys:
                has_joint_attributes = True
            if bool(joint_keys) != bool(weight_keys):
                errors.append(
                    f"mesh[{mesh_index}].primitive[{primitive_index}] has unmatched JOINTS/WEIGHTS attributes"
                )
            for key in joint_keys + weight_keys:
                if not accessor_ok(attrs.get(key)):
                    errors.append(
                        f"mesh[{mesh_index}].primitive[{primitive_index}] invalid {key} accessor"
                    )

    for animation_index, animation in enumerate(animations):
        samplers = animation.get("samplers", [])
        for channel_index, channel in enumerate(animation.get("channels", [])):
            sampler = channel.get("sampler")
            if not isinstance(sampler, int) or not (0 <= sampler < len(samplers)):
                errors.append(
                    f"animation[{animation_index}].channel[{channel_index}] invalid sampler {sampler}"
                )
            target = channel.get("target", {}) or {}
            target_node = target.get("node")
            if target_node is not None and not node_ok(target_node):
                errors.append(
                    f"animation[{animation_index}].channel[{channel_index}] invalid target node {target_node}"
                )
            if target.get("path")=="weights":
                if not node_ok(target_node):
                    message=(
                        f"animation[{animation_index}].channel[{channel_index}] "
                        "weights channel has invalid target node"
                    )
                    morph_errors.append(message)
                    errors.append(message)
                else:
                    mesh_index=nodes[target_node].get("mesh")
                    target_count=(
                        mesh_target_counts.get(mesh_index,0)
                        if isinstance(mesh_index,int)
                        else 0
                    )
                    if target_count<=0:
                        message=(
                            f"animation[{animation_index}].channel[{channel_index}] "
                            "targets weights on node without morph targets"
                        )
                        morph_errors.append(message)
                        errors.append(message)

    rig_ready = bool(skins and skinned_nodes and has_joint_attributes and not errors)
    if skins and not has_joint_attributes:
        warnings.append("skins exist but mesh primitives expose no JOINTS/WEIGHTS attributes")
    if not skins:
        warnings.append("asset is unrigged: no glTF skins")

    return RigAudit(
        path=str(path),
        valid_glb=True,
        gltf_version=str(doc.get("asset", {}).get("version")) if doc.get("asset") else None,
        mesh_count=len(meshes),
        node_count=len(nodes),
        skin_count=len(skins),
        animation_count=len(animations),
        material_count=len(doc.get("materials", [])),
        texture_count=len(doc.get("textures", [])),
        skinned_mesh_nodes=skinned_nodes,
        joint_count=joint_total,
        morph_mesh_count=morph_mesh_count,
        morph_primitive_count=morph_primitive_count,
        morph_target_count=morph_target_count,
        morph_ready=not morph_errors,
        rig_ready=rig_ready,
        animation_ready=bool(rig_ready and animations),
        material_channels=sorted(_material_channels(doc)),
        errors=errors,
        warnings=warnings,
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="HAYUYA glTF rig/skin/material audit.")
    parser.add_argument("glb", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--require-rig", action="store_true")
    args = parser.parse_args()

    report = audit_glb(args.glb)
    payload = json.dumps(asdict(report), indent=2)
    print(payload)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(payload + "\n", encoding="utf-8")

    if not report.valid_glb or report.errors:
        return 2
    if args.require_rig and not report.rig_ready:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
