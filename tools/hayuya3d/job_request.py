#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

PROFILES = {"preview", "mobile", "game", "monster", "ultra"}
MODES = {"auto", "prop", "character", "architecture"}
TIERS = {"auto", "compatibility", "balanced", "high", "flagship"}
ASSET_PROFILES = {"auto", "character.humanoid", "character.creature", "weapon.firearm", "weapon.melee", "prop.mechanical", "vehicle", "foliage.grass", "foliage.tree", "prop.static", "environment.modular"}
WEAPON_FAMILIES = {"auto","handgun_semiauto","revolver","shotgun_pump_tube","shotgun_semiauto_tube","shotgun_break_open","rifle_magazine","rifle_bolt_action","lmg_beltfed","launcher"}
JOB_RE = re.compile(r"^[A-Za-z0-9._-]+$")
ALLOWED_EXTERNAL_REPOS = {
    "1993velezpadilla-source/legacy-cache-staging-03",
}


def _tokens(*values: str) -> set[str]:
    text=" ".join(str(x or "") for x in values).lower()
    return {x for x in re.split(r"[^a-z0-9]+",text) if x}


def infer_asset_profile(data: dict) -> str:
    explicit=str(data.get("asset_profile") or "").strip()
    if explicit and explicit!="auto":
        return explicit
    t=_tokens(data.get("title",""),data.get("geometry_input",""),data.get("job_id",""))
    if t & {"pistol","handgun","revolver","shotgun","rifle","smg","lmg","gun","firearm","sniper","launcher","p90"}:
        return "weapon.firearm"
    if t & {"sword","knife","machete","axe","bat","club","melee"}:
        return "weapon.melee"
    if t & {"grass","turf"}:
        return "foliage.grass"
    if t & {"tree","trees","bush","bushes","plant","plants","foliage"}:
        return "foliage.tree"
    if t & {"car","truck","vehicle","van","motorcycle","bike"}:
        return "vehicle"
    if t & {"door","fan","gear","machine","mechanical","elevator"}:
        return "prop.mechanical"
    if t & {"creature","animal","quadruped"}:
        return "character.creature"
    if t & {"zombie","zombies","human","humanoid","character","npc","llorona"}:
        return "character.humanoid"
    return {
        "character":"character.humanoid",
        "prop":"prop.static",
        "architecture":"environment.modular",
    }.get(str(data.get("mode","auto")),"auto")


def infer_weapon_family(data: dict) -> str:
    explicit=str(data.get("weapon_family") or "auto").strip()
    if explicit!="auto":
        return explicit
    t=_tokens(data.get("title",""),data.get("geometry_input",""),data.get("job_id",""))
    if "revolver" in t:
        return "revolver"
    if "pistol" in t or "handgun" in t or "p90" in t:
        return "handgun_semiauto" if "p90" not in t else "rifle_magazine"
    if "shotgun" in t:
        if t & {"pump","pumpaction","pump-action"}: return "shotgun_pump_tube"
        if t & {"double","break","breakaction"}: return "shotgun_break_open"
        if t & {"semi","semiauto","automatic"}: return "shotgun_semiauto_tube"
        return "auto"
    if t & {"smg","carbine","assaultrifle"}:
        return "rifle_magazine"
    if "rifle" in t:
        if "bolt" in t or "boltaction" in t: return "rifle_bolt_action"
        return "rifle_magazine"
    if "sniper" in t and "bolt" in t:
        return "rifle_bolt_action"
    if "lmg" in t and ("belt" in t or "beltfed" in t):
        return "lmg_beltfed"
    if "launcher" in t:
        return "launcher"
    return "auto"


def load_request(path: Path, repo_root: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") not in (1, 2):
        raise ValueError("unsupported job request schema")

    required = ["job_id", "owner", "title", "geometry_input", "profile", "mode", "portable_target"]
    missing = [key for key in required if not str(data.get(key, "")).strip()]
    if missing:
        raise ValueError("missing required fields: " + ", ".join(missing))

    job_id = str(data["job_id"])
    if not JOB_RE.fullmatch(job_id):
        raise ValueError("job_id may only contain letters, digits, dot, underscore and dash")

    if data["profile"] not in PROFILES:
        raise ValueError(f"invalid profile: {data['profile']}")
    if data["mode"] not in MODES:
        raise ValueError(f"invalid mode: {data['mode']}")
    if data["portable_target"] not in TIERS:
        raise ValueError(f"invalid portable_target: {data['portable_target']}")

    data["asset_profile"] = infer_asset_profile(data)
    if data["asset_profile"] not in ASSET_PROFILES:
        raise ValueError(f"invalid asset_profile: {data['asset_profile']}")
    data["weapon_family"] = infer_weapon_family(data) if data["asset_profile"]=="weapon.firearm" else "auto"
    if data["weapon_family"] not in WEAPON_FAMILIES:
        raise ValueError(f"invalid weapon_family: {data['weapon_family']}")
    data["animation_requested"] = bool(data.get(
        "animation_requested",
        data["asset_profile"] in {"character.humanoid", "character.creature"}
    ))
    data["motion_profile"] = str(data.get("motion_profile") or "auto")
    data["texture_quality"] = str(data.get("texture_quality") or "standard")

    source_repo = str(data.get("source_repo", "") or "").strip()
    source_ref = str(data.get("source_ref", "main") or "main").strip()
    if source_repo:
        if source_repo not in ALLOWED_EXTERNAL_REPOS:
            raise ValueError(f"external source_repo not allowed: {source_repo}")
        if not JOB_RE.fullmatch(source_ref.replace("/", "-")):
            raise ValueError("invalid external source_ref")
        data["source_repo"] = source_repo
        data["source_ref"] = source_ref
    else:
        geometry = (repo_root / str(data["geometry_input"])).resolve()
        try:
            geometry.relative_to(repo_root.resolve())
        except ValueError as exc:
            raise ValueError("geometry_input escapes repository") from exc
        if not geometry.is_file():
            raise FileNotFoundError(f"geometry_input missing: {data['geometry_input']}")

        for key in ("reference_dir", "detail_dir"):
            value = str(data.get(key, "") or "").strip()
            if not value:
                data[key] = ""
                continue
            target = (repo_root / value).resolve()
            try:
                target.relative_to(repo_root.resolve())
            except ValueError as exc:
                raise ValueError(f"{key} escapes repository") from exc
            if not target.is_dir():
                raise FileNotFoundError(f"{key} missing: {value}")
        data["source_repo"] = ""
        data["source_ref"] = ""

    data["gpu_vram"] = int(data.get("gpu_vram", 24))
    data["backends"] = str(
        data.get("backends")
        or "triposg,trellis2,trellis,instantmesh,triposr"
    )
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    data = load_request(args.request, repo_root)
    print(json.dumps(data, indent=2))

    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as f:
            for key in (
                "job_id", "owner", "title", "geometry_input", "reference_dir",
                "detail_dir", "profile", "mode", "portable_target", "gpu_vram", "backends",
                "source_repo", "source_ref", "asset_profile", "weapon_family", "animation_requested", "motion_profile", "texture_quality"
            ):
                value = str(data.get(key, ""))
                if "\n" in value or "\r" in value:
                    raise ValueError(f"multiline workflow output not allowed: {key}")
                f.write(f"{key}={value}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
