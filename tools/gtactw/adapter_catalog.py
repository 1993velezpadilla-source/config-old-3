#!/usr/bin/env python3
"""Validate that a CTW profile's named hook adapters exist in the native catalog."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import profile_template


def load_catalog(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("schema") != 1:
        raise ValueError("adapter catalog schema must be 1")
    adapters = obj.get("adapters")
    if not isinstance(adapters, list):
        raise ValueError("adapter catalog adapters must be a list")
    return obj


def _index_catalog(catalog: dict) -> dict[str, dict]:
    out = {}
    for item in catalog.get("adapters", []):
        if not isinstance(item, dict):
            raise ValueError("adapter catalog entries must be objects")
        name = item.get("name")
        target = item.get("target")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("adapter catalog entry needs name")
        if target not in profile_template.TARGET_KEYS:
            raise ValueError(f"adapter {name} has invalid target {target}")
        if name in out:
            raise ValueError(f"duplicate adapter name: {name}")
        out[name] = item
    return out


def validate_profile_adapters(profile: dict, catalog: dict) -> dict:
    index = _index_catalog(catalog)
    abi = profile.get("abi_verification", {})
    targets = profile.get("patch_targets_rva", {})

    per_target = {}
    ready_count = 0

    for target in profile_template.TARGET_KEYS:
        item = abi.get(target)
        rva = targets.get(target)
        adapter = item.get("adapter") if isinstance(item, dict) else None
        status = item.get("status") if isinstance(item, dict) else None
        verified_rva = item.get("verified_rva") if isinstance(item, dict) else None

        reasons = []
        catalog_item = None

        if status != "verified":
            reasons.append("abi_not_verified")
        if not isinstance(rva, int) or rva <= 0:
            reasons.append("target_rva_missing")
        if verified_rva != rva:
            reasons.append("abi_verified_rva_mismatch")
        if not isinstance(adapter, str) or not adapter.strip():
            reasons.append("adapter_name_missing")
        else:
            catalog_item = index.get(adapter)
            if catalog_item is None:
                reasons.append("adapter_not_in_catalog")
            else:
                if catalog_item.get("target") != target:
                    reasons.append("adapter_target_mismatch")
                if catalog_item.get("implemented") is not True:
                    reasons.append("adapter_not_implemented")
                symbol = catalog_item.get("native_symbol")
                if not isinstance(symbol, str) or not symbol.strip():
                    reasons.append("adapter_native_symbol_missing")

        ok = not reasons
        if ok:
            ready_count += 1

        per_target[target] = {
            "ready": ok,
            "rva": rva,
            "adapter": adapter,
            "catalog_entry": catalog_item,
            "reasons": reasons,
        }

    total = len(profile_template.TARGET_KEYS)
    return {
        "ready": ready_count == total,
        "ready_count": ready_count,
        "total": total,
        "targets": per_target,
        "note": (
            "A profile is adapter-ready only when every ABI is verified and "
            "its named adapter is explicitly marked implemented in the native "
            "adapter catalog."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("profile", type=Path)
    ap.add_argument(
        "--catalog",
        type=Path,
        default=Path("projects/gtactw-android-3d/adapter_catalog.json"),
    )
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    try:
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
        catalog = load_catalog(args.catalog)
        report = validate_profile_adapters(profile, catalog)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    payload = json.dumps(report, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
