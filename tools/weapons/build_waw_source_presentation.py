#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

RUNTIME_ROWS = {
    "colt": 1,
    "stg": 2,
    "trench": 3,
    "browning": 4,
    "mp40": 5,
    "m1a1": 6,
    "kar98k": 7,
    "thompson": 8,
    "doublebarrel": 9,
    "sawnoff": 10,
    "bar": 11,
    "m1": 14,
    "357": 15,
    "ptrs": 16,
    "gewehr": 17,
    "ppsh": 18,
    "type100": 19,
    "fg42": 20,
    "mg42": 21,
    "dp28": 171,
    "type99": 172,
    "nambu": 173,
    "springfield": 174,
    "arisaka": 175,
    "mosin": 176,
    "svt40": 177,
    "tt33": 178,
    "walther": 179,
}

RUNTIME_SOURCE_DIR = {
    "colt": "1911",
    "357": "357",
    "arisaka": "Arisaka",
    "bar": "BAR",
    "browning": "Browning",
    "doublebarrel": "DoubleBarrel",
    "dp28": "DP28",
    "fg42": "FG42",
    "gewehr": "Gewehr",
    "kar98k": "Kar98k",
    "m1a1": "M1Carbine",
    "m1": "M1Garand",
    "mg42": "MG42",
    "mp40": "MP40",
    "mosin": "MosinNagant",
    "nambu": "Nambu",
    "ppsh": "PPSH",
    "ptrs": "PTRS",
    "springfield": "Springfield",
    "stg": "STG44",
    "svt40": "SVT40",
    "thompson": "Thompson",
    "trench": "TrenchGun",
    "tt33": "TT33",
    "type100": "Type100",
    "type99": "Type99",
    "walther": "Walther",
    "sawnoff": "SawedOffDB",
}

HASHED_FIELD = re.compile(r"^(.+?)_\d+_[0-9A-F]+$", re.I)


def unhashed_key(key: str) -> str:
    m = HASHED_FIELD.match(key)
    return m.group(1) if m else key


def clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {unhashed_key(str(k)): clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return value


def field(record: dict[str, Any], prefix: str, default: Any = None) -> Any:
    p = prefix.lower()
    for key, value in record.items():
        if unhashed_key(str(key)).lower() == p:
            return value
    return default


def object_path(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("ObjectPath", "AssetPathName"):
            raw = value.get(key)
            if raw:
                return str(raw)
    return ""


def source_string(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("SourceString", "LocalizedString", "Key"):
            raw = value.get(key)
            if raw:
                return str(raw)
    return str(value or "")


def xyz(value: dict[str, Any]) -> list[float]:
    return [float(value.get("X", 0.0)), float(value.get("Y", 0.0)), float(value.get("Z", 0.0))]


def quat(value: dict[str, Any]) -> list[float]:
    return [
        float(value.get("X", 0.0)),
        float(value.get("Y", 0.0)),
        float(value.get("Z", 0.0)),
        float(value.get("W", 1.0)),
    ]


def ue_transform(value: Any) -> dict[str, Any]:
    value = value if isinstance(value, dict) else {}
    return {
        "rotation_xyzw": quat(value.get("Rotation", {})),
        "translation": xyz(value.get("Translation", {})),
        "scale": xyz(value.get("Scale3D", {"X": 1.0, "Y": 1.0, "Z": 1.0})),
    }


def godot_transform(value: Any) -> dict[str, Any]:
    ue = ue_transform(value)
    x, y, z = ue["translation"]
    qx, qy, qz, qw = ue["rotation_xyzw"]
    sx, sy, sz = ue["scale"]
    return {
        "rotation_xyzw": [-qy, -qz, qx, qw],
        "translation_m": [y / 100.0, z / 100.0, -x / 100.0],
        "scale": [sy, sz, sx],
    }


def readable_object_fields(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, Any] = {}
    for raw_key, raw_value in value.items():
        key = unhashed_key(str(raw_key))
        if isinstance(raw_value, dict) and ("ObjectPath" in raw_value or "AssetPathName" in raw_value):
            result[key.lower()] = object_path(raw_value)
        elif raw_value is None:
            result[key.lower()] = ""
        elif isinstance(raw_value, (str, int, float, bool)):
            result[key.lower()] = raw_value
    return result


def load_rows(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list) or not payload:
        raise RuntimeError("DT_Weapons export is not the expected CUE4Parse list")
    table = payload[0]
    if table.get("Name") != "DT_Weapons":
        raise RuntimeError(f"Expected DT_Weapons, got {table.get('Name')!r}")
    rows = table.get("Rows")
    if not isinstance(rows, dict):
        raise RuntimeError("DT_Weapons Rows missing")
    return rows


def build_record(runtime_id: str, row_index: int, row: dict[str, Any]) -> dict[str, Any]:
    weapon_name = source_string(field(row, "WeaponName", {}))
    view = field(row, "ViewTransform", {})
    ads = field(row, "ADSTransform", {})
    hand_anims_raw = field(row, "HandAnims", {})
    stats_raw = field(row, "WeaponStats", {})

    stats = clean(stats_raw) if isinstance(stats_raw, dict) else {}
    movement = stats.get("Movement", {}) if isinstance(stats, dict) else {}
    misc = stats.get("Misc", {}) if isinstance(stats, dict) else {}
    hand_transform = misc.get("HandTransform", {}) if isinstance(misc, dict) else {}

    if not hand_transform:
        raise RuntimeError(f"{runtime_id}: WeaponStats.Misc.HandTransform missing")

    hand_anims = readable_object_fields(hand_anims_raw)
    t7_armature = bool(
        clean(hand_anims_raw).get("T7_Armature", False)
        if isinstance(hand_anims_raw, dict)
        else False
    )

    return {
        "status": "source_datatable",
        "source_table": "/Game/Assets/Data/DataTables/DT_Weapons",
        "source_row_index": row_index,
        "source_weapon_name": weapon_name,
        "source_weapon_dir": RUNTIME_SOURCE_DIR[runtime_id],
        "view_transform_ue_cm": ue_transform(view),
        "view_transform_godot": godot_transform(view),
        "hand_transform_ue_cm": ue_transform(hand_transform),
        "hand_transform_godot": godot_transform(hand_transform),
        "ads_transform_ue_cm": ue_transform(ads),
        "ads_transform_godot": godot_transform(ads),
        "ads_in_time_s": float(movement.get("AdsInTime", 0.20)),
        "ads_out_time_s": float(movement.get("AdsOutTime", 0.20)),
        "ads_fov_multiplier": float(misc.get("ADSFOVMultiplier", 1.0)),
        "t7_armature": t7_armature,
        "hand_animation_sources": hand_anims,
        "source_runtime_profile": stats,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dt_weapons", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()

    rows = load_rows(args.dt_weapons)
    weapons: dict[str, Any] = {}
    for runtime_id, row_index in RUNTIME_ROWS.items():
        row = rows.get(str(row_index))
        if not isinstance(row, dict):
            raise RuntimeError(f"{runtime_id}: source row {row_index} missing")
        weapons[runtime_id] = build_record(runtime_id, row_index, row)

    if len(weapons) != 28:
        raise RuntimeError(f"Expected 28 source weapon records, got {len(weapons)}")

    missing_hand_paths = [
        wid
        for wid, rec in weapons.items()
        if not any(
            str(rec["hand_animation_sources"].get(role, ""))
            for role in ("idle", "fire", "reload", "raise")
        )
    ]

    payload = {
        "schema": 2,
        "source": "Project Aether UE5.7 /Game/Assets/Data/DataTables/DT_Weapons",
        "coordinate_conversion": "UE cm (X forward,Y right,Z up) -> Godot m (X=Yue/100,Y=Zue/100,Z=-Xue/100); quaternion Godot=(-Yue,-Zue,Xue,Wue)",
        "policy": {
            "source_authored_only": True,
            "scale_guessing_forbidden": True,
            "family_offsets_forbidden": True,
            "manual_per_weapon_pose_fixes_forbidden": True,
            "source_baseline_before_reskin": True,
        },
        "weapon_count": len(weapons),
        "missing_core_hand_animation_rows": missing_hand_paths,
        "weapons": weapons,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        "XZOGOT_WAW_SOURCE_PRESENTATION_GREEN",
        "weapons=", len(weapons),
        "missing_core_hand_rows=", missing_hand_paths,
    )


if __name__ == "__main__":
    main()
