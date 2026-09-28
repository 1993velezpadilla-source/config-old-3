#!/usr/bin/env python3
"""Generate a CTW3D patch-profile template from elf_probe JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

PREFIX = "Java_com_rockstargames_oswrapper_GameNative_"
DRAW = PREFIX + "implOnDrawFrame"
SETUP = PREFIX + "implOnInitialSetup"
AXES = PREFIX + "implOnGamepadAxesChanged"

TARGET_KEYS = (
    "camera_update",
    "projection_setup",
    "world_stream_update",
    "sector_visibility",
    "lod_test",
    "player_render",
)



TARGET_EVIDENCE_RULES = {
    "camera_update": {
        "groups": ("camera",),
        "strong_terms": ("cameraupdate", "camera_update", "view", "look", "aim"),
        "weak_terms": ("camera", "cam"),
    },
    "projection_setup": {
        "groups": ("camera",),
        "strong_terms": (
            "projection", "proj", "perspective", "fov", "nearclip",
            "farclip", "matproj", "clip",
        ),
        "weak_terms": ("camera", "matmodelview"),
    },
    "world_stream_update": {
        "groups": ("streaming",),
        "strong_terms": ("worldblock", "world_block", "streamradius", "stream_radius"),
        "weak_terms": ("stream", "resident"),
    },
    "sector_visibility": {
        "groups": ("streaming", "lod_culling"),
        "strong_terms": ("sector", "visibility", "visible", "frustum"),
        "weak_terms": ("cull", "stream"),
    },
    "lod_test": {
        "groups": ("lod_culling",),
        "strong_terms": ("lod", "drawdistance", "draw_distance", "culldistance", "cull_distance"),
        "weak_terms": ("distance", "cull", "visible"),
    },
    "player_render": {
        "groups": ("player_render",),
        "strong_terms": (
            "player", "ped", "skin", "skeleton", "body", "character",
            "modelrender", "model_render",
        ),
        "weak_terms": ("weapon", "render"),
    },
}


def rank_target_evidence(report: dict, xref_report: dict | None) -> dict:
    """Rank evidence for each patch target without selecting a target RVA.

    Scores are intentionally evidence-only. They are useful for narrowing the
    reverse-engineering search, but never populate patch_targets_rva.
    """
    xref_groups = summarize_xrefs(xref_report)
    symbol_groups = report.get("symbols", {}).get("candidate_groups", {})
    out = {}

    for target, rule in TARGET_EVIDENCE_RULES.items():
        merged = {}

        for group in rule["groups"]:
            for item in xref_groups.get(group, []):
                rva = item.get("rva")
                if rva is None:
                    continue
                entry = merged.setdefault(int(rva), {
                    "rva": int(rva),
                    "function": item.get("function"),
                    "score": 0,
                    "reasons": [],
                    "xref_hits": 0,
                    "strings": [],
                    "symbol_names": [],
                    "call_sites": [],
                })
                hits = int(item.get("hits") or 0)
                entry["xref_hits"] += hits
                entry["score"] += min(hits, 6)
                if hits:
                    entry["reasons"].append(f"{hits} {group} string xref hit(s)")

                for text in item.get("strings", []):
                    if text not in entry["strings"]:
                        entry["strings"].append(text)
                for pc in item.get("call_sites", []):
                    if pc not in entry["call_sites"]:
                        entry["call_sites"].append(pc)

        for group in rule["groups"]:
            for sym in symbol_groups.get(group, []):
                if sym.get("source") != "symbol" or sym.get("value") is None:
                    continue
                rva = int(sym["value"])
                entry = merged.setdefault(rva, {
                    "rva": rva,
                    "function": sym.get("name"),
                    "score": 0,
                    "reasons": [],
                    "xref_hits": 0,
                    "strings": [],
                    "symbol_names": [],
                    "call_sites": [],
                })
                name = sym.get("name") or ""
                if name not in entry["symbol_names"]:
                    entry["symbol_names"].append(name)
                entry["score"] += 3
                entry["reasons"].append(f"{group} symbol candidate")

        strong_terms = tuple(x.lower() for x in rule["strong_terms"])
        weak_terms = tuple(x.lower() for x in rule["weak_terms"])
        for entry in merged.values():
            haystack_parts = []
            if entry.get("function"):
                haystack_parts.append(entry["function"])
            haystack_parts += entry["symbol_names"]
            haystack_parts += entry["strings"]
            haystack = " ".join(haystack_parts).lower()

            strong_matches = sorted({
                term for term in strong_terms if term in haystack
            })
            weak_matches = sorted({
                term for term in weak_terms if term in haystack
            })

            if strong_matches:
                bonus = min(len(strong_matches), 4) * 4
                entry["score"] += bonus
                entry["reasons"].append(
                    "strong target match: " + ", ".join(strong_matches)
                )
            if weak_matches:
                bonus = min(len(weak_matches), 3)
                entry["score"] += bonus
                entry["reasons"].append(
                    "weak target match: " + ", ".join(weak_matches)
                )

            # Distinct strings are a stronger signal than repeated references
            # to the same literal.
            distinct = len(entry["strings"])
            if distinct > 1:
                bonus = min(distinct - 1, 4)
                entry["score"] += bonus
                entry["reasons"].append(
                    f"{distinct} distinct evidence strings"
                )

            # Same RVA seen both as a symbol candidate and an xref owner is a
            # useful cross-signal.
            if entry["xref_hits"] and entry["symbol_names"]:
                entry["score"] += 4
                entry["reasons"].append("symbol + xref cross-signal")

        ranked = sorted(
            merged.values(),
            key=lambda x: (-x["score"], -x["xref_hits"], x["rva"]),
        )
        out[target] = ranked[:16]

    return out


def _jni_rva(report: dict, name: str) -> int | None:
    details = report.get("symbols", {}).get("known_jni_details", {})
    item = details.get(name)
    if not item or not item.get("present"):
        return None
    value = item.get("value")
    return int(value) if value is not None else None


def summarize_xrefs(xref_report: dict | None) -> dict:
    groups = (xref_report or {}).get("groups", {})
    out = {}
    for group in ("camera", "streaming", "lod_culling", "player_render"):
        by_func = {}
        for item in groups.get(group, []):
            rva = item.get("function_rva")
            name = item.get("function")
            if rva is None:
                continue
            key = (name, int(rva))
            entry = by_func.setdefault(key, {
                "function": name,
                "rva": int(rva),
                "hits": 0,
                "strings": [],
                "call_sites": [],
            })
            entry["hits"] += 1
            text = item.get("string")
            if text and text not in entry["strings"]:
                entry["strings"].append(text)
            pc = item.get("pc_rva")
            if pc is not None and pc not in entry["call_sites"]:
                entry["call_sites"].append(pc)

        ranked = sorted(
            by_func.values(),
            key=lambda x: (-x["hits"], x["rva"]),
        )
        out[group] = ranked[:32]
    return out


def make_profile(report: dict, xref_report: dict | None = None) -> dict:
    if report.get("elf", {}).get("machine") != "AArch64":
        raise ValueError("report is not for an AArch64 libGame.so")

    draw_rva = _jni_rva(report, DRAW)
    setup_rva = _jni_rva(report, SETUP)
    axes_rva = _jni_rva(report, AXES)

    if draw_rva is None or setup_rva is None:
        raise ValueError("report is missing required CTW GameNative JNI RVAs")

    candidates = report.get("symbols", {}).get("candidate_groups", {})
    candidate_summary = {}
    for group in ("camera", "streaming", "lod_culling", "player_render"):
        entries = candidates.get(group, [])
        candidate_summary[group] = [
            {
                "name": item.get("name"),
                "rva": item.get("value"),
                "size": item.get("size"),
            }
            for item in entries[:64]
            if item.get("source") == "symbol"
        ]

    return {
        "schema": 1,
        "game": "GTA Chinatown Wars Android",
        "abi": "arm64-v8a",
        "fingerprint": {
            "file_size": report.get("file_size"),
            "sha256": report.get("sha256"),
            "text_sha256": report.get("text", {}).get("sha256"),
            "gnu_build_id": report.get("elf", {}).get("build_id"),
            "jni_rvas": {
                "implOnDrawFrame": draw_rva,
                "implOnInitialSetup": setup_rva,
                "implOnGamepadAxesChanged": axes_rva,
            },
        },
        "patch_targets_rva": {key: None for key in TARGET_KEYS},
        "target_verification": {
            key: {
                "status": "pending",
                "rva": None,
                "evidence": [],
            }
            for key in TARGET_KEYS
        },
        "camera_defaults": {
            "initial_mode": "third_person",
            "toggle_button": 13,
            "right_stick_look": True,
            "fov_degrees": 70.0,
            "near_clip": 0.05,
        },
        "world_distance_defaults": {
            "far_clip_multiplier": 2.0,
            "stream_radius_multiplier": 2.0,
            "lod_distance_multiplier": 2.0,
            "requires_coordinated_patch": True,
        },
        "candidate_symbols": candidate_summary,
        "candidate_xref_functions": summarize_xrefs(xref_report),
        "target_evidence_rankings": rank_target_evidence(report, xref_report),
        "status": "template_needs_verified_internal_rvas",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("elf_report", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--xrefs", type=Path, help="Optional aarch64_xref JSON report")
    args = ap.parse_args()

    try:
        report = json.loads(args.elf_report.read_text(encoding="utf-8"))
        xrefs = (
            json.loads(args.xrefs.read_text(encoding="utf-8"))
            if args.xrefs is not None else None
        )
        profile = make_profile(report, xrefs)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(args.out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
