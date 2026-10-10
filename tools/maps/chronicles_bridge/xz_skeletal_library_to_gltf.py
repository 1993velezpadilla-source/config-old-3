#!/usr/bin/env python3
"""Convert the complete Nuketown XZRG/XZSK/XZAN library to Godot-importable glTF.

This is intentionally generic: every recovered skeletal mesh is paired with its
source skeleton hash and every recovered animation for that same skeleton.
No animation keyframes are synthesized beyond the same timing fallback already
used by the proven Mystery Box bridge when the source omits explicit per-key
sample times.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
from collections import defaultdict
from pathlib import Path

import xz_mystery_to_gltf as core


def slug(text: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")
    return value or "source_skeletal_mesh"


def build_one(
    mesh_index: int,
    meshrow: dict,
    rigrow: dict,
    animrows: list[dict],
    rig_root: Path,
    mesh_root: Path,
    anim_root: Path,
    output_dir: Path,
) -> dict:
    skeleton_hash = str(meshrow["skeletonHash"])
    rig_hash, bones = core.parse_rig(rig_root / rigrow["file"])
    mesh_hash, mesh = core.parse_mesh(mesh_root / meshrow["file"])

    expected_hash = int(skeleton_hash, 16)
    if rig_hash != expected_hash or mesh_hash != expected_hash:
        raise SystemExit(
            f"skeleton hash mismatch mesh={meshrow['packagePath']} "
            f"expected={skeleton_hash} rig={rig_hash:016x} mesh={mesh_hash:016x}"
        )

    max_joint = max(
        (joint for row in mesh["j0"] + mesh["j1"] for joint in row),
        default=0,
    )
    if max_joint >= len(bones):
        raise SystemExit(
            f"joint remap exceeds rig mesh={meshrow['packagePath']} "
            f"joint={max_joint} bones={len(bones)}"
        )

    builder = core.Builder()
    pos_a = builder.floats(mesh["pos"], "VEC3", core.TARGET_ARRAY, True)
    nrm_a = builder.floats(mesh["nrm"], "VEC3", core.TARGET_ARRAY)
    tan_a = builder.floats(mesh["tan"], "VEC4", core.TARGET_ARRAY)
    uv_a = builder.floats(mesh["uv"], "VEC2", core.TARGET_ARRAY)
    j0_a = builder.u16s(mesh["j0"], "VEC4", core.TARGET_ARRAY)
    w0_a = builder.floats(mesh["w0"], "VEC4", core.TARGET_ARRAY)
    j1_a = builder.u16s(mesh["j1"], "VEC4", core.TARGET_ARRAY)
    w1_a = builder.floats(mesh["w1"], "VEC4", core.TARGET_ARRAY)
    idx_a = builder.u32s(mesh["indices"], core.TARGET_ELEMENT)

    local = [
        core.trs_matrix(bone["translation"], bone["rotation"], bone["scale"])
        for bone in bones
    ]
    global_bind = []
    for index, bone in enumerate(bones):
        global_bind.append(
            local[index]
            if bone["parent"] < 0
            else core.mat_mul(global_bind[bone["parent"]], local[index])
        )
    inverse_bind = [core.inv_affine(matrix) for matrix in global_bind]
    ibm_a = builder.floats(inverse_bind, "MAT4")

    nodes = []
    for bone in bones:
        nodes.append(
            {
                "name": bone["name"],
                "translation": bone["translation"],
                "rotation": bone["rotation"],
                "scale": bone["scale"],
            }
        )

    roots = []
    for index, bone in enumerate(bones):
        if bone["parent"] < 0:
            roots.append(index)
        else:
            nodes[bone["parent"]].setdefault("children", []).append(index)

    mesh_label = slug(Path(str(meshrow["packagePath"])).stem)
    mesh_node = len(nodes)
    nodes.append(
        {
            "name": f"{mesh_label}_SourceMesh",
            "mesh": 0,
            "skin": 0,
        }
    )

    max_material = max(
        (section["material"] for section in mesh["sections"]),
        default=0,
    )
    materials = [
        {
            "name": f"SourceMaterial_{index:02d}",
            "pbrMetallicRoughness": {
                "baseColorFactor": [0.72, 0.72, 0.72, 1.0],
                "metallicFactor": 0.0,
                "roughnessFactor": 0.75,
            },
        }
        for index in range(max_material + 1)
    ]

    primitives = []
    index_view = builder.accessors[idx_a]["bufferView"]
    for section in mesh["sections"]:
        accessor = {
            "bufferView": index_view,
            "byteOffset": section["first"] * 4,
            "componentType": core.COMPONENT_U32,
            "count": section["count"],
            "type": "SCALAR",
        }
        accessor_index = len(builder.accessors)
        builder.accessors.append(accessor)
        primitives.append(
            {
                "attributes": {
                    "POSITION": pos_a,
                    "NORMAL": nrm_a,
                    "TANGENT": tan_a,
                    "TEXCOORD_0": uv_a,
                    "JOINTS_0": j0_a,
                    "WEIGHTS_0": w0_a,
                    "JOINTS_1": j1_a,
                    "WEIGHTS_1": w1_a,
                },
                "indices": accessor_index,
                "material": section["material"],
                "mode": 4,
            }
        )

    animations = []
    manifest_animations = []
    for row in sorted(animrows, key=lambda value: value["packagePath"]):
        anim_hash, frames, fps, duration, additive, tracks = core.parse_anim(
            anim_root / row["file"]
        )
        if anim_hash != expected_hash:
            raise SystemExit(
                f"animation hash mismatch file={row['file']} "
                f"expected={skeleton_hash} got={anim_hash:016x}"
            )

        samplers = []
        channels = []
        for track_index, track in enumerate(tracks[: len(bones)]):
            for key, path_name, value_type in (
                ("pos", "translation", "VEC3"),
                ("rot", "rotation", "VEC4"),
                ("scale", "scale", "VEC3"),
            ):
                values = track[key]
                if not values:
                    continue
                time_key = {"pos": "pt", "rot": "rt", "scale": "st"}[key]
                times = core.choose_times(
                    track,
                    len(values),
                    time_key,
                    frames,
                    fps,
                    duration,
                )
                input_accessor = builder.scalars(times, True)
                output_accessor = builder.floats(values, value_type)
                sampler_index = len(samplers)
                samplers.append(
                    {
                        "input": input_accessor,
                        "output": output_accessor,
                        "interpolation": "LINEAR",
                    }
                )
                channels.append(
                    {
                        "sampler": sampler_index,
                        "target": {
                            "node": track_index,
                            "path": path_name,
                        },
                    }
                )

        animation_name = core.safe_anim_name(row["packagePath"])
        animations.append(
            {
                "name": animation_name,
                "samplers": samplers,
                "channels": channels,
            }
        )
        manifest_animations.append(
            {
                "name": animation_name,
                "packagePath": row["packagePath"],
                "frames": frames,
                "fps": fps,
                "duration": duration,
                "additive": additive,
            }
        )

    output_name = f"skeletal_{mesh_index:02d}_{mesh_label}.gltf"
    output_path = output_dir / output_name
    gltf = {
        "asset": {
            "version": "2.0",
            "generator": "XZIEL complete XZRG/XZSK/XZAN -> Godot glTF bridge",
        },
        "scene": 0,
        "scenes": [
            {
                "name": f"{mesh_label}_Source",
                "nodes": roots + [mesh_node],
            }
        ],
        "nodes": nodes,
        "meshes": [
            {
                "name": f"{mesh_label}_SourceMesh",
                "primitives": primitives,
            }
        ],
        "skins": [
            {
                "name": f"{mesh_label}_SourceSkin",
                "joints": list(range(len(bones))),
                "skeleton": roots[0] if roots else 0,
                "inverseBindMatrices": ibm_a,
            }
        ],
        "materials": materials,
        "animations": animations,
        "buffers": [
            {
                "byteLength": len(builder.buf),
                "uri": "data:application/octet-stream;base64,"
                + base64.b64encode(bytes(builder.buf)).decode("ascii"),
            }
        ],
        "bufferViews": builder.views,
        "accessors": builder.accessors,
    }
    output_path.write_text(json.dumps(gltf, separators=(",", ":")))

    return {
        "output": output_name,
        "sourceGeometry": meshrow["packagePath"],
        "sourceXzskFile": meshrow["file"],
        "sourceSkeleton": rigrow["packagePath"],
        "skeletonHash": skeleton_hash,
        "bones": len(bones),
        "vertices": len(mesh["pos"]),
        "indices": len(mesh["indices"]),
        "sections": len(mesh["sections"]),
        "animations": manifest_animations,
    }


def find_probe_report(root: Path, folder: str) -> tuple[Path, dict]:
    hits = list(root.glob(f"**/{folder}/report.json"))
    if len(hits) != 1:
        raise SystemExit(
            f"expected one {folder}/report.json, got {hits}"
        )
    path = hits[0]
    return path, json.loads(path.read_text())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_root", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--rig-report", type=Path)
    parser.add_argument("--mesh-report", type=Path)
    parser.add_argument("--anim-report", type=Path)
    parser.add_argument("--expected-rigs", type=int, default=3)
    parser.add_argument("--expected-meshes", type=int, default=3)
    parser.add_argument("--expected-anims", type=int, default=9)
    args = parser.parse_args()

    explicit = [args.rig_report, args.mesh_report, args.anim_report]
    if any(value is not None for value in explicit):
        if not all(value is not None for value in explicit):
            raise SystemExit(
                "--rig-report, --mesh-report and --anim-report must be provided together"
            )
        rig_report_path = args.rig_report
        mesh_report_path = args.mesh_report
        anim_report_path = args.anim_report
        assert rig_report_path is not None
        assert mesh_report_path is not None
        assert anim_report_path is not None
        rig_report = json.loads(rig_report_path.read_text())
        mesh_report = json.loads(mesh_report_path.read_text())
        anim_report = json.loads(anim_report_path.read_text())
    else:
        rig_report_path, rig_report = find_probe_report(
            args.artifact_root, "ue-xzrg-probe"
        )
        mesh_report_path, mesh_report = find_probe_report(
            args.artifact_root, "ue-xzsk-probe"
        )
        anim_report_path, anim_report = find_probe_report(
            args.artifact_root, "ue-xzan-probe"
        )

    rigs = list(rig_report.get("skeletons", []))
    meshes = list(mesh_report.get("meshes", []))
    animations = list(anim_report.get("animations", []))

    if len(rigs) != args.expected_rigs:
        raise SystemExit(
            f"expected {args.expected_rigs} source skeletons, got {len(rigs)}"
        )
    if len(meshes) != args.expected_meshes:
        raise SystemExit(
            f"expected {args.expected_meshes} source skeletal meshes, got {len(meshes)}"
        )
    if len(animations) != args.expected_anims:
        raise SystemExit(
            f"expected {args.expected_anims} source animations, got {len(animations)}"
        )

    rig_by_hash = {str(row["skeletonHash"]): row for row in rigs}
    animations_by_hash: dict[str, list[dict]] = defaultdict(list)
    for row in animations:
        animations_by_hash[str(row["skeletonHash"])].append(row)

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    for stale in output_dir.glob("*.gltf"):
        stale.unlink()

    rows = []
    for index, meshrow in enumerate(
        sorted(meshes, key=lambda value: value["packagePath"])
    ):
        skeleton_hash = str(meshrow["skeletonHash"])
        rigrow = rig_by_hash.get(skeleton_hash)
        if rigrow is None:
            raise SystemExit(
                f"no recovered skeleton for mesh {meshrow['packagePath']} "
                f"hash={skeleton_hash}"
            )
        rows.append(
            build_one(
                index,
                meshrow,
                rigrow,
                animations_by_hash.get(skeleton_hash, []),
                rig_report_path.parent,
                mesh_report_path.parent,
                anim_report_path.parent,
                output_dir,
            )
        )

    covered_animation_packages = {
        animation["packagePath"]
        for row in rows
        for animation in row["animations"]
    }
    source_animation_packages = {
        row["packagePath"]
        for row in animations
    }
    if covered_animation_packages != source_animation_packages:
        missing = sorted(source_animation_packages - covered_animation_packages)
        raise SystemExit(f"source animations not bridged: {missing}")

    mesh_hashes = {str(row["skeletonHash"]) for row in meshes}
    animation_hashes = {str(row["skeletonHash"]) for row in animations}
    rig_hashes = {str(row["skeletonHash"]) for row in rigs}
    missing_animation_rigs = sorted(animation_hashes - rig_hashes)
    unmounted_animation_hashes = sorted(animation_hashes - mesh_hashes)
    if missing_animation_rigs:
        raise SystemExit(
            "animations reference unrecovered skeleton hashes: "
            + repr(missing_animation_rigs)
        )
    if unmounted_animation_hashes:
        raise SystemExit(
            "animations have no skeletal mesh carrier: "
            + repr(unmounted_animation_hashes)
        )

    manifest = {
        "schemaVersion": 2,
        "sourceSkeletonCount": len(rigs),
        "sourceSkeletalMeshCount": len(meshes),
        "sourceAnimationCount": len(animations),
        "outputCount": len(rows),
        "coveredAnimationCount": len(covered_animation_packages),
        "skeletonHashCount": len(rig_hashes),
        "meshSkeletonHashCount": len(mesh_hashes),
        "animationSkeletonHashCount": len(animation_hashes),
        "unmountedAnimationSkeletonHashes": unmounted_animation_hashes,
        "meshes": rows,
        "ready": (
            len(covered_animation_packages) == len(animations)
            and not missing_animation_rigs
            and not unmounted_animation_hashes
        ),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )

    print(
        "XZOGOT_SKELETAL_LIBRARY_GLTF_GREEN",
        f"skeletons={len(rigs)}",
        f"meshes={len(meshes)}",
        f"animations={len(animations)}",
        f"outputs={len(rows)}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
