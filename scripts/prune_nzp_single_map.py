#!/usr/bin/env python3
"""Keep a single map inside an NZ:P game-data tree without deleting shared assets.

Only per-map payloads beneath nzp/maps are removed. The models, hands, skins,
reload animation models, weapon sounds, sprites, and shared textures remain
untouched, so developer inventory can access weapons associated with any map.
"""
from pathlib import Path
import re
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: prune_nzp_single_map.py <nzp-data-root> <map-stem>")
root = Path(sys.argv[1]).resolve()
requested = sys.argv[2]
if not re.fullmatch(r"[A-Za-z0-9_-]+", requested):
    raise SystemExit("Unsafe map identifier")
maps = root / "maps"
if not maps.is_dir():
    raise SystemExit("Game assets do not contain a maps/ directory")
bsps = [f for f in maps.iterdir() if f.is_file() and f.suffix.lower() == ".bsp"]
target = [f for f in bsps if f.stem.casefold() == requested.casefold()]
if len(target) != 1:
    raise SystemExit(
        f"Expected exactly one {requested}.bsp. Found {len(target)} target BSPs; "
        f"available examples: {[f.name for f in bsps[:20]]}"
    )

# Prune compiled level and companion per-map files for all other maps.
# Do not recursively erase directories or remove .pak / shared weapon assets.
per_map_suffixes = {".bsp", ".nsz", ".lit", ".ent", ".loc", ".txt", ".lmp"}
removed = []
saved_bytes = 0
for file in maps.iterdir():
    if not file.is_file() or file.stem.casefold() == requested.casefold():
        continue
    if file.suffix.lower() in per_map_suffixes:
        saved_bytes += file.stat().st_size
        removed.append(file.name)
        file.unlink()

remaining = [p for p in maps.iterdir() if p.is_file() and p.suffix.lower() == ".bsp"]
if len(remaining) != 1 or remaining[0].stem.casefold() != requested.casefold():
    raise SystemExit("Single-map BSP contract not satisfied after pruning")

# This contract guards exactly the failure we must avoid: deleting the original
# MP40 viewmodel or its worldmodel while leaving just one level packaged.
for relative in ("models/weapons/mp40/v_mp40.mdl",
                 "models/weapons/mp40/g_mp40.mdl"):
    if not (root / relative).is_file():
        raise SystemExit(f"Missing protected original weapon asset: {relative}")

print(f"single-map: {requested}, removed={len(removed)} map files, "
      f"bytes_saved={saved_bytes:,}, BSPs_remaining=1, MP40_models=preserved")
