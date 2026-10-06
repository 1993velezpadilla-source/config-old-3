#!/usr/bin/env python3
"""Compile exact Nacht UMAP audio placement + SoundCue + OGG authority.

No SoundCue behavior is approximated. The manifest records the complete node
set used by each placed source component and marks whether the current Godot
bridge can reproduce the cue semantics exactly.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

SUPPORTED_NODE_TYPES = {
    "SoundNodeWavePlayer",
    "SoundNodeLooping",
}

# Structural/root-ish node types that carry no independent runtime transform.
PASSTHROUGH_NODE_TYPES = {
    "SoundNode",
}


def canonical(raw: str) -> str:
    value = (raw or "").strip().replace("\\", "/")
    if "'" in value and value.endswith("'"):
        value = value.split("'", 1)[1][:-1]
    if value.startswith("Content/"):
        value = "/Game/" + value[len("Content/"):]
    elif value.startswith("Game/"):
        value = "/" + value
    return value.lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", type=Path, required=True)
    ap.add_argument("--cues", type=Path, required=True)
    ap.add_argument("--waves", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    scene = json.loads(args.scene.read_text())
    cues = json.loads(args.cues.read_text())
    waves = json.loads(args.waves.read_text())

    assert scene.get("ready") is True, scene
    assert scene.get("audioComponentCount") == 3, scene
    assert scene.get("referencedSoundCount") == 3, scene
    assert scene.get("nullSoundCount") == 0, scene
    assert cues.get("ready") is True, cues
    assert cues.get("cueCount") == 102, cues
    assert waves.get("ready") is True, waves
    assert waves.get("audioCount") == 295, waves

    cue_by_path = {
        canonical(row.get("objectPath", "")): row
        for row in cues.get("cues", [])
        if row.get("objectPath")
    }
    wave_by_path = {
        canonical(row.get("objectPath", "")): row
        for row in waves.get("audio", [])
        if row.get("objectPath")
    }

    placed = []
    missing_cues = []
    missing_waves = []
    all_node_types = set()
    unsupported_node_types = set()
    semantic_ready_count = 0

    for component in scene.get("audioComponents", []):
        sound = component.get("sound", {}) or {}
        cue_path = str(sound.get("objectPath") or "")
        cue = cue_by_path.get(canonical(cue_path))
        if cue is None:
            missing_cues.append(
                {
                    "actorName": component.get("actorName"),
                    "componentName": component.get("componentName"),
                    "cuePath": cue_path,
                }
            )
            continue

        node_types = sorted(
            {
                str(node.get("exportType") or "")
                for node in cue.get("nodes", [])
                if str(node.get("exportType") or "")
            }
        )
        all_node_types.update(node_types)

        unsupported = sorted(
            t
            for t in node_types
            if t not in SUPPORTED_NODE_TYPES
            and t not in PASSTHROUGH_NODE_TYPES
        )
        unsupported_node_types.update(unsupported)

        wave_rows = []
        for wave_path in cue.get("waveObjectPaths", []):
            wave = wave_by_path.get(canonical(str(wave_path)))
            if wave is None:
                missing_waves.append(
                    {
                        "cuePath": cue_path,
                        "wavePath": wave_path,
                    }
                )
                continue
            wave_rows.append(
                {
                    "objectPath": wave.get("objectPath"),
                    "runtimeFile": wave.get("runtimeFile"),
                    "format": wave.get("format"),
                    "streaming": wave.get("streaming"),
                    "payloadBytes": wave.get("payloadBytes"),
                }
            )

        semantic_ready = (
            not unsupported
            and len(wave_rows) == len(cue.get("waveObjectPaths", []))
            and len(wave_rows) > 0
        )
        if semantic_ready:
            semantic_ready_count += 1

        placed.append(
            {
                "id": component.get("id"),
                "actorName": component.get("actorName"),
                "componentName": component.get("componentName"),
                "sourcePath": component.get("sourcePath"),
                "hierarchy": component.get("hierarchy", []),
                "properties": component.get("properties", {}),
                "sound": sound,
                "cuePath": cue_path,
                "cueVolumeMultiplier": cue.get("volumeMultiplier"),
                "cuePitchMultiplier": cue.get("pitchMultiplier"),
                "firstNode": cue.get("firstNode"),
                "nodeTypes": node_types,
                "nodes": cue.get("nodes", []),
                "edges": cue.get("edges", []),
                "waveObjectPaths": cue.get("waveObjectPaths", []),
                "waves": wave_rows,
                "unsupportedNodeTypes": unsupported,
                "semanticRuntimeReady": semantic_ready,
            }
        )

    assert not missing_cues, missing_cues
    assert not missing_waves, missing_waves
    assert len(placed) == 3, len(placed)

    result = {
        "schemaVersion": 1,
        "authority": "exact Nacht UMAP AudioComponent + SoundCue graph + source OGG",
        "placementCount": len(placed),
        "sourceCueCount": cues.get("cueCount"),
        "sourceWaveCount": waves.get("audioCount"),
        "supportedNodeTypes": sorted(SUPPORTED_NODE_TYPES),
        "passthroughNodeTypes": sorted(PASSTHROUGH_NODE_TYPES),
        "placedCueNodeTypes": sorted(all_node_types),
        "unsupportedPlacedCueNodeTypes": sorted(unsupported_node_types),
        "semanticRuntimeReadyPlacementCount": semantic_ready_count,
        "allPlacedCueSemanticsSupported": semantic_ready_count == len(placed),
        "placements": placed,
        "ready": True,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        "XZOGOT_NACHT_AUDIO_RUNTIME_MANIFEST_GREEN",
        json.dumps(
            {
                "placements": len(placed),
                "semanticReady": semantic_ready_count,
                "nodeTypes": sorted(all_node_types),
                "unsupported": sorted(unsupported_node_types),
            },
            separators=(",", ":"),
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
