#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

RULES = [
    ("navigation", ["navigation"], [
        r"^Nav", r"RecastNavMesh", r"NavigationSystem", r"NavLink",
    ]),
    ("collision_physics", ["collision", "physics"], [
        r"BodySetup", r"Physics", r"Constraint", r"Collision",
        r"BlockingVolume", r"KillVolume", r"Blocker", r"InvisibleWall",
        r"BoxComponent", r"CapsuleComponent", r"SphereComponent",
        r"TriggerBox", r"ProjectileMovement", r"LandscapeHeightfieldCollision",
    ]),
    ("animation_rig", ["rig_db", "animation_db"], [
        r"Anim", r"Skeleton", r"Skeletal", r"BlendSpace",
        r"IKRig", r"IKRetarget", r"Retarget", r"Pose",
    ]),
    ("audio", ["audio"], [
        r"Sound", r"Audio", r"Synth", r"Dialogue",
    ]),
    ("fx_particles", ["fx"], [
        r"Particle", r"Niagara", r"Decal", r"Emitter",
        r"Beam", r"Ribbon", r"Trail", r"VectorField",
    ]),
    ("lighting_environment", ["material_shader", "world"], [
        r"Light", r"Fog", r"Sky", r"ReflectionCapture",
        r"PostProcess", r"Atmosphere", r"VolumetricCloud",
        r"PrecomputedVisibility", r"MapBuildDataRegistry",
        r"SceneCapture",
    ]),
    ("material_texture_shader", ["material_shader"], [
        r"Material", r"Texture", r"FontFace", r"^Font$",
    ]),
    ("world_geometry", ["world"], [
        r"StaticMesh", r"Model", r"Brush", r"Landscape",
        r"^World$", r"WorldSettings", r"^Level$",
        r"SceneComponent", r"Pavlov_Map",
    ]),
    ("hud_ui", ["hud_ui"], [
        r"Widget", r"Text", r"^Image$", r"Canvas", r"Border",
        r"Button", r"HUD", r"Slate", r"ProgressBar", r"Overlay",
        r"Scroll", r"VerticalBox", r"HorizontalBox", r"PanelSlot",
        r"Slider", r"ComboBox", r"CheckBox", r"BackgroundBlur",
    ]),
    ("cinematic_media_camera", ["world", "hud_ui"], [
        r"Camera", r"MovieScene", r"Sequence", r"MediaPlayer",
        r"MediaTexture", r"ImgMediaSource", r"Cine",
    ]),
    ("input_haptics", ["hud_ui", "game_systems"], [
        r"Haptic", r"Input",
    ]),
    ("spawn_gameplay", ["script_module_db", "game_systems"], [
        r"PlayerStart", r"Pavlov_Spawn",
    ]),
    ("script_gameplay", ["script_module_db", "game_systems"], [
        r"_C$", r"Blueprint", r"^Function$", r"Script", r"Struct$",
        r"Enum$", r"Timeline", r"Delegate", r"SCS_Node",
        r"InheritableComponentHandler", r"^Actor$", r"^Component$",
        r"Pavlov_InteractBox", r"Object$",
    ]),
    ("data_curves", ["precache", "script_module_db"], [
        r"Curve", r"Distribution", r"DataTable", r"DataAsset",
        r"StringTable",
    ]),
]

COMPILED = [
    (category, gates, [re.compile(p, re.IGNORECASE) for p in patterns])
    for category, gates, patterns in RULES
]

def classify(name):
    for category, gates, patterns in COMPILED:
        if any(p.search(name) for p in patterns):
            return category, gates
    return None, []

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    classes = data.get("classCounts", {})
    if not isinstance(classes, dict) or not classes:
        raise SystemExit("classCounts missing/empty")

    coverage = []
    categories = {}
    gates = {}
    unknown = []

    for name, count in sorted(classes.items()):
        category, required_gates = classify(name)
        if category is None:
            unknown.append({"class": name, "count": count})
            continue

        row = {
            "class": name,
            "count": count,
            "category": category,
            "requiredGates": required_gates,
        }
        coverage.append(row)
        categories[category] = categories.get(category, 0) + count
        for gate in required_gates:
            gates[gate] = gates.get(gate, 0) + count

    report = {
        "schemaVersion": 1,
        "sourcePackageCount": data.get("packageCount"),
        "sourceExportCount": data.get("totalExports"),
        "sourceClassCount": len(classes),
        "classifiedClassCount": len(coverage),
        "unclassifiedClassCount": len(unknown),
        "unclassifiedExportCount": sum(x["count"] for x in unknown),
        "categoryExportCounts": dict(sorted(categories.items())),
        "gateExportCounts": dict(sorted(gates.items())),
        "coverage": coverage,
        "unclassified": unknown,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print("XZIEL_SOURCE_CLASS_REQUIREMENTS", json.dumps({
        "classes": report["sourceClassCount"],
        "classified": report["classifiedClassCount"],
        "unclassified": report["unclassifiedClassCount"],
        "unclassifiedExports": report["unclassifiedExportCount"],
        "categories": report["categoryExportCounts"],
    }, sort_keys=True))

    if unknown:
        for row in unknown:
            print("XZIEL_UNCLASSIFIED_SOURCE_CLASS", row["count"], row["class"])
        return 5

    print("XZIEL_SOURCE_CLASS_REQUIREMENTS_GREEN")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
