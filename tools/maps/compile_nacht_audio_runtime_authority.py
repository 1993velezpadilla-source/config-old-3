#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

AUDIO_CLASSES = {"SoundCue", "SoundWave"}
AUDIO_CALLS = {
    "playsoundatlocation",
    "playsound2d",
    "spawnsoundatlocation",
    "spawnsoundattached",
    "playsoundattached",
    "setsound",
    "play",
    "stop",
    "fadein",
    "fadeout",
    "adjustvolume",
}
GEN_SUFFIX = "_GEN_VARIABLE"


def strip_ref(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    match = re.match(r"^(?:import|export):-?\d+:(.*)$", text)
    if match:
        text = match.group(1)
    match = re.match(r"^[A-Za-z0-9_]+['\"](.*)['\"]$", text)
    if match:
        text = match.group(1)
    return text


def canonical(value: Any) -> str | None:
    text = strip_ref(value)
    if not text:
        return None
    text = text.replace("\\", "/")
    if text.startswith("Content/"):
        text = "/Game/" + text[len("Content/"):]
    elif text.startswith("Game/"):
        text = "/" + text
    return text


def normalize_component(name: str) -> str:
    return name[:-len(GEN_SUFFIX)] if name.upper().endswith(GEN_SUFFIX) else name


def pointer_ref(expr: Any) -> str | None:
    if not isinstance(expr, dict):
        return None
    variable = expr.get("Variable")
    if isinstance(variable, dict):
        old = variable.get("Old")
        if isinstance(old, str):
            return old
    return None


def property_name_from_ref(ref: str | None) -> str | None:
    if not ref:
        return None
    match = re.match(r"export:\d+:(.*)$", ref)
    if match:
        return normalize_component(match.group(1))
    match = re.match(r"import:-?\d+:(.*)$", ref)
    if match:
        return normalize_component(match.group(1).split(".")[-1])
    return None


def asset_filename_from_class_path(class_path: str | None, class_name: str | None) -> str | None:
    if class_name and class_name.endswith("_C"):
        return class_name[:-2] + ".uasset"
    if not class_path:
        return None
    asset = canonical(class_path)
    if not asset:
        return None
    asset = asset.split(".", 1)[0]
    return asset.rsplit("/", 1)[-1] + ".uasset"


def package_filename_from_component_import(row: dict[str, Any] | None) -> str | None:
    if not row:
        return None
    resolved = canonical(row.get("resolved"))
    if not resolved:
        return None
    asset_path = resolved.split(".", 1)[0]
    return asset_path.rsplit("/", 1)[-1] + ".uasset"


def resolve_index(value: Any, imports: dict[int, dict[str, Any]]) -> str | Any:
    if isinstance(value, int) and value < 0 and value in imports:
        return canonical(imports[value].get("resolved"))
    return value


def build_package_info(package: dict[str, Any]) -> dict[str, Any]:
    imports = {int(row["rawIndex"]): row for row in package.get("imports", [])}
    import_by_path = {
        canonical(row.get("resolved")): row
        for row in package.get("imports", [])
        if canonical(row.get("resolved"))
    }

    cdo: dict[str, Any] = {}
    components: dict[str, dict[str, Any]] = {}
    normal_exports: dict[str, dict[str, Any]] = {}

    for row in package.get("normalExportProperties", []):
        name = str(row.get("objectName", ""))
        normal_exports[name] = row
        props = {
            str(prop.get("Name")): prop
            for prop in row.get("properties", [])
            if isinstance(prop, dict) and prop.get("Name")
        }

        if name.startswith("Default__"):
            for prop_name, prop in props.items():
                cdo[prop_name] = resolve_index(prop.get("Value"), imports)

        if name.upper().endswith(GEN_SUFFIX):
            key = normalize_component(name).lower()
            entry: dict[str, Any] = {
                "objectName": name,
                "package": package.get("fileName"),
            }
            if "Sound" in props:
                sound = resolve_index(props["Sound"].get("Value"), imports)
                if isinstance(sound, str):
                    entry["sound"] = sound
            if "bAutoActivate" in props:
                entry["autoActivate"] = bool(props["bAutoActivate"].get("Value"))
            components[key] = entry

    component_imports: dict[str, dict[str, Any]] = {}
    for row in package.get("imports", []):
        if str(row.get("className")) != "AudioComponent":
            continue
        component_imports[
            normalize_component(str(row.get("objectName", ""))).lower()
        ] = row

    return {
        "package": package,
        "file": str(package.get("fileName", "")),
        "imports": imports,
        "importByPath": import_by_path,
        "cdo": cdo,
        "components": components,
        "componentImports": component_imports,
        "normalExports": normal_exports,
    }


def actor_authority(component: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    for row in component.get("ownerResolutionChain", []):
        class_name = str(row.get("exportType", ""))
        if class_name.endswith("_C"):
            class_path = row.get("classPath")
            return (
                class_name,
                class_path,
                asset_filename_from_class_path(class_path, class_name),
            )
    return None, None, None


def expression_asset(
    expr: Any,
    info: dict[str, Any],
) -> tuple[str | None, str | None]:
    if not isinstance(expr, dict):
        return None, None

    expr_type = str(expr.get("$type", ""))
    if expr_type == "EX_ObjectConst":
        path = canonical(expr.get("Value"))
        imported = info["importByPath"].get(path)
        if imported and str(imported.get("className")) in AUDIO_CLASSES:
            return path, None

    if expr_type in {"EX_InstanceVariable", "EX_LocalVariable", "EX_DefaultVariable"}:
        prop_name = property_name_from_ref(pointer_ref(expr))
        if prop_name:
            value = info["cdo"].get(prop_name)
            if isinstance(value, str) and value.startswith("/Game/"):
                return value, prop_name
            return None, prop_name

    for value in expr.values():
        if isinstance(value, dict):
            asset, prop_name = expression_asset(value, info)
            if asset or prop_name:
                return asset, prop_name
    return None, None


def extract_blueprint_events(info: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    for function in info["package"].get("functions", []):
        for top in function.get("topLevelExpressions", []):
            start = int(top.get("startOffset", -1))
            end = int(top.get("endOffset", -1))

            def walk(node: Any, context_target: Any = None) -> None:
                if not isinstance(node, dict):
                    return

                expr_type = str(node.get("$type", ""))
                if expr_type == "EX_Context":
                    walk(node.get("ContextExpression"), node.get("ObjectExpression"))
                    return

                if expr_type in {"EX_FinalFunction", "EX_VirtualFunction"}:
                    call_ref = node.get("StackNode") or node.get("VirtualFunctionName") or ""
                    call_name = str(call_ref).split(".")[-1]
                    if call_name.lower() in AUDIO_CALLS:
                        asset = None
                        property_name = None
                        for parameter in node.get("Parameters", []):
                            asset, property_name = expression_asset(parameter, info)
                            if asset or property_name:
                                break

                        target_ref = pointer_ref(context_target)
                        events.append(
                            {
                                "package": info["file"],
                                "function": str(function.get("name", "")),
                                "startOffset": start,
                                "endOffset": end,
                                "call": call_name,
                                "callReference": call_ref,
                                "asset": asset,
                                "assetProperty": property_name,
                                "targetReference": target_ref,
                                "targetComponent": property_name_from_ref(target_ref),
                            }
                        )

                for value in node.values():
                    if isinstance(value, dict):
                        walk(value, context_target)
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                walk(item, context_target)

            walk(top.get("expression"))

    unique: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for event in events:
        signature = (
            event["package"],
            event["function"],
            event["startOffset"],
            event["endOffset"],
            event["call"],
            event.get("asset"),
            event.get("assetProperty"),
            event.get("targetReference"),
        )
        if signature in seen:
            continue
        seen.add(signature)
        unique.append(event)
    return unique


def child_override_asset(
    event: dict[str, Any],
    child: dict[str, Any] | None,
    authority: dict[str, Any] | None,
) -> str | None:
    prop = event.get("assetProperty")
    if prop:
        if child:
            value = child["cdo"].get(prop)
            if isinstance(value, str) and value.startswith("/Game/"):
                return value
        if authority:
            value = authority["cdo"].get(prop)
            if isinstance(value, str) and value.startswith("/Game/"):
                return value
    asset = event.get("asset")
    return asset if isinstance(asset, str) else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio-scene", required=True, type=Path)
    parser.add_argument("--bytecode", required=True, type=Path)
    parser.add_argument("--cue-graph", type=Path)
    parser.add_argument("--native-audio-report", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    audio_scene = json.loads(args.audio_scene.read_text())
    bytecode = json.loads(args.bytecode.read_text())

    if audio_scene.get("ready") is not True:
        raise SystemExit("audio scene authority is not ready")
    if bytecode.get("ready") is not True:
        raise SystemExit("Blueprint bytecode authority is not ready")

    packages = {
        info["file"]: info
        for info in (build_package_info(row) for row in bytecode.get("packages", []))
    }
    events_by_package = {
        name: extract_blueprint_events(info)
        for name, info in packages.items()
    }

    component_bindings: list[dict[str, Any]] = []
    component_by_actor_and_name: dict[tuple[str, str], dict[str, Any]] = {}
    unresolved_components: list[dict[str, Any]] = []

    for component in audio_scene.get("audioComponents", []):
        actor_class, actor_class_path, child_file = actor_authority(component)
        child = packages.get(child_file or "")
        component_name = str(component.get("componentName", ""))
        key = component_name.lower()

        scene_sound = canonical((component.get("sound") or {}).get("objectPath"))
        sound = scene_sound
        provenance = (
            (component.get("sound") or {}).get("provenance")
            if scene_sound
            else None
        )
        authority_file = child_file
        template: dict[str, Any] | None = None

        if child:
            template = child["components"].get(key)
            if not sound and template and template.get("sound"):
                sound = template["sound"]
                provenance = (
                    "bytecode_component_default:"
                    + child["file"]
                    + ":"
                    + str(template.get("objectName"))
                )

            if not sound:
                imported_component = child["componentImports"].get(key)
                parent_file = package_filename_from_component_import(imported_component)
                parent = packages.get(parent_file or "")
                parent_template = parent["components"].get(key) if parent else None
                if parent_template and parent_template.get("sound"):
                    sound = parent_template["sound"]
                    authority_file = parent_file
                    template = parent_template
                    provenance = (
                        "bytecode_inherited_component_default:"
                        + str(parent_file)
                        + ":"
                        + str(parent_template.get("objectName"))
                    )

        auto_activate = bool((component.get("properties") or {}).get("autoActivate", True))
        if template and "autoActivate" in template:
            auto_activate = bool(template["autoActivate"])

        binding = {
            "id": component.get("id"),
            "actorName": component.get("actorName"),
            "actorClass": actor_class,
            "actorClassPath": actor_class_path,
            "componentName": component_name,
            "sourcePath": component.get("sourcePath"),
            "hierarchy": component.get("hierarchy", []),
            "soundObjectPath": sound,
            "soundKind": None,
            "provenance": provenance,
            "childBlueprintPackage": child_file,
            "authorityBlueprintPackage": authority_file,
            "autoActivate": auto_activate,
            "volumeMultiplier": (component.get("properties") or {}).get("volumeMultiplier", 1.0),
            "pitchMultiplier": (component.get("properties") or {}).get("pitchMultiplier", 1.0),
            "allowSpatialization": (component.get("properties") or {}).get("allowSpatialization", True),
        }

        if not sound:
            unresolved_components.append(binding)
        component_bindings.append(binding)
        if actor_class:
            component_by_actor_and_name[(actor_class, component_name.lower())] = binding

    all_events = [
        event
        for package_events in events_by_package.values()
        for event in package_events
    ]

    actor_events: list[dict[str, Any]] = []
    for binding in component_bindings:
        actor_class = binding.get("actorClass")
        child_file = binding.get("childBlueprintPackage")
        authority_file = binding.get("authorityBlueprintPackage")
        child = packages.get(str(child_file or ""))
        authority = packages.get(str(authority_file or ""))

        package_order: list[str] = []
        for candidate in (child_file, authority_file):
            if candidate and candidate not in package_order:
                package_order.append(str(candidate))

        for package_name in package_order:
            event_authority = packages.get(package_name)
            if not event_authority:
                continue
            for event in events_by_package.get(package_name, []):
                runtime_event = dict(event)
                runtime_event["actorName"] = binding.get("actorName")
                runtime_event["actorClass"] = actor_class
                runtime_event["resolvedAsset"] = child_override_asset(
                    event,
                    child,
                    event_authority,
                )

                target_name = event.get("targetComponent")
                if target_name and actor_class:
                    target_binding = component_by_actor_and_name.get(
                        (str(actor_class), str(target_name).lower())
                    )
                    if target_binding:
                        runtime_event["resolvedComponentId"] = target_binding.get("id")
                        runtime_event["resolvedComponentSound"] = target_binding.get("soundObjectPath")

                actor_events.append(runtime_event)

    cue_graph = None
    cue_by_path: dict[str, dict[str, Any]] = {}
    if args.cue_graph:
        cue_graph = json.loads(args.cue_graph.read_text())
        if cue_graph.get("ready") is not True:
            raise SystemExit("cue graph authority is not ready")
        cue_by_path = {
            canonical(row.get("objectPath")): row
            for row in cue_graph.get("cues", [])
            if canonical(row.get("objectPath"))
        }

    native_audio = None
    wave_by_path: dict[str, dict[str, Any]] = {}
    if args.native_audio_report:
        native_audio = json.loads(args.native_audio_report.read_text())
        if native_audio.get("ready") is not True:
            raise SystemExit("native audio report is not ready")
        wave_by_path = {
            canonical(row.get("objectPath")): row
            for row in native_audio.get("soundWaves", [])
            if canonical(row.get("objectPath"))
        }

    unresolved_assets: list[dict[str, Any]] = []

    def describe_asset(path: str | None, provenance: dict[str, Any]) -> dict[str, Any] | None:
        if not path:
            return None
        if path in cue_by_path:
            cue = cue_by_path[path]
            waves = [canonical(x) for x in cue.get("waveObjectPaths", []) if canonical(x)]
            missing_waves = [x for x in waves if wave_by_path and x not in wave_by_path]
            if missing_waves:
                unresolved_assets.append(
                    {
                        **provenance,
                        "asset": path,
                        "error": "cue references native waves not present",
                        "missingWaves": missing_waves,
                    }
                )
            return {
                "kind": "SoundCue",
                "objectPath": path,
                "waveObjectPaths": waves,
                "nodeCount": cue.get("nodeCount"),
                "edgeCount": cue.get("edgeCount"),
                "volumeMultiplier": cue.get("volumeMultiplier"),
                "pitchMultiplier": cue.get("pitchMultiplier"),
            }
        if path in wave_by_path:
            wave = wave_by_path[path]
            return {
                "kind": "SoundWave",
                "objectPath": path,
                "sourceFile": wave.get("file"),
                "format": wave.get("format"),
                "payloadBytes": wave.get("payloadBytes"),
            }

        if cue_by_path or wave_by_path:
            unresolved_assets.append(
                {
                    **provenance,
                    "asset": path,
                    "error": "audio asset absent from cue/native-wave authority",
                }
            )
        return {
            "kind": "unclassified",
            "objectPath": path,
        }

    for binding in component_bindings:
        binding["assetAuthority"] = describe_asset(
            binding.get("soundObjectPath"),
            {"componentId": binding.get("id")},
        )
        if binding.get("assetAuthority"):
            binding["soundKind"] = binding["assetAuthority"].get("kind")

    for event in actor_events:
        event["assetAuthority"] = describe_asset(
            event.get("resolvedAsset"),
            {
                "actorClass": event.get("actorClass"),
                "package": event.get("package"),
                "function": event.get("function"),
                "startOffset": event.get("startOffset"),
            },
        )

    unresolved_actor_events = []
    for event in actor_events:
        call = str(event.get("call", "")).lower()
        if call in {"play", "stop", "fadein", "fadeout", "adjustvolume"}:
            if event.get("targetComponent") and not event.get("resolvedComponentId"):
                # Ignore generated temporary AudioComponents returned by
                # SpawnSoundAtLocation. Their source asset is represented by the
                # spawning call immediately before the Play call.
                if not str(event.get("targetComponent", "")).startswith("CallFunc_"):
                    unresolved_actor_events.append(event)
        elif call == "setsound":
            if not event.get("resolvedAsset"):
                unresolved_actor_events.append(event)
        elif call.startswith("playsound") or call.startswith("spawnsound"):
            if not event.get("resolvedAsset"):
                unresolved_actor_events.append(event)

    ready = (
        len(component_bindings) == int(audio_scene.get("audioComponentCount", -1))
        and not unresolved_components
        and not unresolved_actor_events
        and not unresolved_assets
    )

    output = {
        "schemaVersion": 1,
        "format": "xogot_nacht_source_audio_runtime_authority_v1",
        "sourceGame": audio_scene.get("sourceGame"),
        "audioComponentCount": len(component_bindings),
        "resolvedAudioComponentCount": len(component_bindings) - len(unresolved_components),
        "blueprintPackageCount": len(packages),
        "blueprintAudioEventCount": len(all_events),
        "actorAudioEventCount": len(actor_events),
        "componentBindings": component_bindings,
        "blueprintEvents": all_events,
        "actorEventBindings": actor_events,
        "unresolvedComponents": unresolved_components,
        "unresolvedActorEvents": unresolved_actor_events,
        "unresolvedAssets": unresolved_assets,
        "cueAuthorityCount": int(cue_graph.get("cueCount", 0)) if cue_graph else None,
        "nativeWaveAuthorityCount": int(native_audio.get("convertedSoundWaves", 0)) if native_audio else None,
        "ready": ready,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")

    print(
        "XZOGOT_NACHT_AUDIO_RUNTIME_AUTHORITY",
        json.dumps(
            {
                "components": output["audioComponentCount"],
                "resolvedComponents": output["resolvedAudioComponentCount"],
                "blueprintPackages": output["blueprintPackageCount"],
                "blueprintEvents": output["blueprintAudioEventCount"],
                "actorEvents": output["actorAudioEventCount"],
                "unresolvedComponents": len(unresolved_components),
                "unresolvedActorEvents": len(unresolved_actor_events),
                "unresolvedAssets": len(unresolved_assets),
                "ready": ready,
            },
            separators=(",", ":"),
        ),
    )

    if not ready:
        print("XZOGOT_NACHT_AUDIO_RUNTIME_AUTHORITY_FAILURE")
        return 5

    print("XZOGOT_NACHT_AUDIO_RUNTIME_AUTHORITY_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
