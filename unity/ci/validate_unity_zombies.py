#!/usr/bin/env python3
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
errors = []

models = sorted((root / "Assets/_Game/Art/Weapons").glob("*/viewmodel.glb"))
if len(models) < 28:
    errors.append(f"expected >=28 real viewmodels, found {len(models)}")
for model in models:
    if model.stat().st_size < 100_000:
        errors.append(f"suspiciously small weapon model: {model.relative_to(root)}")

for rel in [
    "Assets/_Game/Art/Zombies/MonjaClean/monja_basica_clean_rig.gltf",
    "Assets/_Game/Art/Zombies/MonjaClean/monja_basica_clean_rig.bin",
    "Assets/_Game/Art/Zombies/MonjaClean/baseColor_1.jpg",
    "Assets/_Game/Art/Zombies/MonjaClean/normal_1.png",
    "Assets/_Game/Art/Environment/Church/church_final_architecture.glb",
]:
    if not (root / rel).exists():
        errors.append(f"missing production asset: {rel}")

for rel in [
    "Assets/_Game/Scripts/Combat/WeaponRuntime.cs",
    "Assets/_Game/Scripts/Combat/WeaponADSController.cs",
    "Assets/_Game/Scripts/Combat/ZombieHitbox.cs",
    "Assets/_Game/Scripts/AI/ZombieBrain.cs",
    "Assets/_Game/Scripts/AI/ZombieBarricade.cs",
    "Assets/_Game/Scripts/AI/ZombieSpawnDirector.cs",
    "Assets/_Game/Scripts/Player/MobileFPSController.cs",
    "Assets/_Game/Scripts/Interaction/PlayerInteractor.cs",
    "Assets/_Game/Scripts/Interaction/PackAPunchMachine.cs",
    "Assets/_Game/Scripts/World/LightingQualityDirector.cs",
    "Assets/_Game/Scripts/Editor/VerticalSliceBootstrap.cs",
    "Assets/_Game/Scripts/Editor/AndroidBuild.cs",
]:
    if not (root / rel).exists():
        errors.append(f"missing runtime/editor code: {rel}")

balance_path = root / "Assets/_Game/Data/weapon_balance.json"
if not balance_path.exists():
    errors.append("weapon balance table missing")
else:
    rows = json.loads(balance_path.read_text())["weapons"]
    if len(rows) < 28:
        errors.append(f"expected >=28 weapon balance rows, found {len(rows)}")
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        errors.append("duplicate weapon IDs")
    for row in rows:
        model = root / "Assets/_Game/Art/Weapons" / row["id"] / "viewmodel.glb"
        if not model.exists():
            errors.append(f"balance row has no real model: {row['id']}")
        if row["packDamage"] <= row["baseDamage"]:
            errors.append(f"{row['id']}: Pack-a-Punch damage must exceed base")
        if row["packMagazine"] < row["magazine"]:
            errors.append(f"{row['id']}: Pack-a-Punch magazine smaller than base")
        if row["falloffEnd"] <= row["falloffStart"]:
            errors.append(f"{row['id']}: invalid falloff interval")
        if row["pellets"] < 1:
            errors.append(f"{row['id']}: pellets must be >=1")

if errors:
    print("UNITY_ZOMBIES_STATIC_GATE=RED")
    for error in errors:
        print("ERROR:", error)
    sys.exit(1)

print("UNITY_ZOMBIES_STATIC_GATE=GREEN")
print(f"REAL_WEAPON_MODELS={len(models)}")
print("WEAPON_BALANCE_ROWS=28+")
print("REAL_CHURCH=YES")
print("CLEAN_MONJA_RIG=YES")
print("ADS_DAMAGE_ROUNDS_BARRICADES_PAP_MOBILE_GYRO_LIGHTING=WIRED")
