#!/usr/bin/env python3
"""Build a CTW modpack using the loader variant implied by verified hook evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import apk_modpack
import apkset_modpack
import loader_variant


def _source_mode(source: Path) -> str:
    if source.is_dir():
        return "apkset"
    if source.is_file() and source.suffix.lower() == ".apk":
        return "apk"
    if source.is_file():
        return "apkset"
    raise FileNotFoundError(source)


def build_from_profile(
    source: Path,
    profile_path: Path,
    minimal_loader: Path,
    shadowhook_loader: Path,
    output: Path,
    config_ini: Path | None = None,
) -> dict:
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    plan = loader_variant.select_loader_variant(profile)
    if not plan["ready"]:
        raise ValueError(
            "loader variant is undetermined; verify all six target RVAs and "
            "their matching trampoline strategy evidence first"
        )

    variant = plan["loader_variant"]
    if variant == "minimal":
        loader = minimal_loader
    elif variant == "shadowhook":
        loader = shadowhook_loader
    else:
        raise ValueError(f"unsupported loader variant: {variant}")

    if not loader.is_file():
        raise FileNotFoundError(loader)

    mode = _source_mode(source)
    if mode == "apk":
        repack = apk_modpack.build_mod_apk(
            source,
            loader,
            output,
            config_ini,
        )
    else:
        repack = apkset_modpack.build_split_modpack(
            source,
            loader,
            output,
            config_ini,
        )

    return {
        "ok": True,
        "source": str(source),
        "source_mode": mode,
        "profile": str(profile_path),
        "loader_variant": variant,
        "selected_loader": str(loader),
        "variant_plan": plan,
        "repack": repack,
        "note": (
            "Output is unsigned. Align/sign with one key before installation. "
            "This selector does not bypass target/ABI verification gates."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("--profile", type=Path, required=True)
    ap.add_argument("--minimal-loader", type=Path, required=True)
    ap.add_argument("--shadowhook-loader", type=Path, required=True)
    ap.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output APK for monolithic input, or output directory for split input",
    )
    ap.add_argument("--config", type=Path)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()

    try:
        result = build_from_profile(
            args.source,
            args.profile,
            args.minimal_loader,
            args.shadowhook_loader,
            args.out,
            args.config,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    payload = json.dumps(result, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
