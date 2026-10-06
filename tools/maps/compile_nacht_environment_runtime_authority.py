#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    source = json.loads(args.source.read_text())
    if source.get("ready") is not True:
        raise SystemExit("environment source authority is not ready")

    components = source.get("components", [])
    type_counts = source.get("typeCounts", {})
    fog = [row for row in components if row.get("componentType") == "exponential_height_fog"]
    reflection = [row for row in components if row.get("componentType") == "reflection_capture"]
    other = [
        row for row in components
        if row.get("componentType") not in {"exponential_height_fog", "reflection_capture"}
    ]

    ready = (
        int(source.get("environmentComponentCount", -1)) == 2
        and len(components) == 2
        and len(fog) == 1
        and len(reflection) == 1
        and not other
        and int(type_counts.get("exponential_height_fog", 0)) == 1
        and int(type_counts.get("reflection_capture", 0)) == 1
    )

    output = {
        "schemaVersion": 1,
        "format": "xogot_nacht_environment_runtime_authority_v1",
        "sourceGame": source.get("sourceGame"),
        "componentCount": len(components),
        "typeCounts": type_counts,
        "fog": fog[0] if fog else None,
        "reflectionCapture": reflection[0] if reflection else None,
        "unsupportedComponents": other,
        # Authority is complete; visual runtime flips only after Godot applies
        # these values and a runtime probe validates the resulting nodes.
        "visualRuntimeReady": False,
        "ready": ready,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")

    print(
        "XZOGOT_NACHT_ENVIRONMENT_RUNTIME_AUTHORITY",
        json.dumps(
            {
                "components": len(components),
                "types": type_counts,
                "fogTyped": (fog[0].get("typed", {}) if fog else {}),
                "reflectionTyped": (reflection[0].get("typed", {}) if reflection else {}),
                "unsupported": len(other),
                "visualRuntimeReady": False,
                "ready": ready,
            },
            separators=(",", ":"),
        ),
    )

    if not ready:
        print("XZOGOT_NACHT_ENVIRONMENT_RUNTIME_AUTHORITY_FAILURE")
        return 5

    print("XZOGOT_NACHT_ENVIRONMENT_RUNTIME_AUTHORITY_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
