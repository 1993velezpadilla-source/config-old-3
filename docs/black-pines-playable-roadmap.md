# BLACK PINES SANATORIUM — game-first public-map candidate

**2026-10-10 · Authoring branch:** `feature/black-pines-sanatorium-playable-v1`

## Non-negotiable scope

- **The Church/Nacht main maps are immutable** in this branch. Do not alter `xogot/main.tscn`, `xogot/nacht_full_map.tscn`, `xogot/scripts/you_wont_win.gd`, `xogot/scripts/nacht_full_map.gd` or any Nacht source GLB/material/DDSTexture.
- New **original design**, not geometry traced/copied from any original zombies map. One floor, nine traversable named cells, interconnected loops for classic kiting and 20-round stress target. 36 × 36 m building grid plus 56 × 62 m fenced exterior test ring.
- The same manifest `xogot/data/black_pines_layout.json` drives **two distinct implementations**:
  1. `xogot/tools/black_pines_author.py` makes Blender-authored original architectural GLB and first art-pass reference PNG using **zero paid APIs**.
  2. `xogot/scripts/black_pines_map.gd` builds collision, doors, windows, machines, enemies and Godot-native fallback materials; can mount Blender visuals without changing gameplay/collision.
- Run the scene at `res://black_pines.tscn`, not through the shipping main-menu map unless later approved.
- **Not public-ready.** Existing test zombie models/animations and legacy machines may contain third-party copyrighted content; replace with independently created/licensed models, sounds, texture art, iconography, and designs before export to public players.

## Gameplay stations designed for actual repeatable testing

| Station | Scope | Gate |
|---|---|---|
| Window barricades | 12 outside entrances, repair planks and Carpenter | 12 real Godot objects; round-15/20 requires device playtest |
| Buy doors | 12 linked passages; hinged, sliding, rolling, sealed, and gate design variations | unlock must remove collider and visual; anti-clipping |
| Perk machines | six original game API `PerkCatalog` IDs, Power Switch | buy/pay/apply/duplicate-guard; full viewhands drink animation still **not validated** |
| Wall buys | M1, MP40, Trench, Thompson, BAR | catalog/ADS/hand alignment need separate gauntlets |
| Mystery Box | four authored relocation points; one active at a time; scripted repeatable cycle | actual weapon grant & points; **not network 4P or original source semantics parity yet** |
| Pack-a-Punch | one power-gated upgrade machine | real weapon stat upgrades; visual hand machine interaction pending |
| Power-ups | Max Ammo, Insta-Kill, Double Points, Nuke, Carpenter | preexisting `PowerUpManager` round death signal wiring |
| Zombies | original two `source_waw` internal-use GLBs + existing AI logic and seven animation roles | **originals are not distributable by default** |
| GobbleGum | intentionally excluded at this stage | excluded by manifest/CI |
| Long play | 3 repeated 15–20 round plays and 3-day survival test | **RED until physical Android tests and 4P authority pass** |

## Correct order / definition of done

1. **Source/layout gate**: new separate scene opens in Godot, doors, window holes, test actors correctly placed, no missing colliders or outside escape holes.
2. **Art gate**: original Blender scene matches the Godot collision grid, versioned GLB build, documented source/provenance and zoomable real Blender **and** Godot captures. Moodboard is a concept, not runtime footage.
3. **Gameplay unit gate**: paid door and perk, perk/no-power block, barrcade break/repair, carpenter, Insta-Kill, Double Points, Max Ammo, Nuke, Mystery Box grant/relocation, Pack-a-Punch result; fail if purchase can charge without giving reward.
4. **First-person motion gate**: **all 28 available arms** hipfire, aligned ADS iron sights, hands normal/grip, reload and interaction animation. No generic `animation exists` GREEN counts as correct appearance.
5. **Zombies gate**: walk/run/sprint/attack/window traversal/damage/death/crawler visual. External WaW source test art stays internal. No ai-path clipping and no visible pop-in.
6. **Sustained test gate**: round 15, 20, repeated sessions; FPS, VRAM, thermals on real Android (budget user target), 4P host/clients + in-session joins/leaves and synchronized pickups/doors.
7. **Reskin**: only after mechanics pass; original authored nun UV texture atlas + normal/roughness maps and independently authorized rig; reject claims that PNG copy alone guarantees a recognizable nun silhouette.
8. **Original public art gate**: all publishing-rights checks pass, replace renamed/modified-but-derivative original commercial machine meshes with distinguishable independent designs, re-validate all gameplay and perf. Church unaffected throughout.

## CI

`.github/workflows/black-pines-original-playable-blender-gate.yml` runs separate native Godot and free Blender pipelines. **A green build is not a 20-round or on-device release certificate.** The generated GLB is retained as an artifact and not silently packed into the public APK. Tests create `black-pines-real-firstframe-overview.png`, labelled as an actual Godot capture (unlike the preliminary AI concept illustration).

## First implementation gates intentionally unfinished

- Animated, verifiable perk bottle pickup/open/drink and viewhands source-to-rig retarget.
- Original-source 3D machine art with legal release provenance, sound timing and original font/name replacements.
- Mystery Box replication/state and per-weapon original 28 ADS accuracy/hand animation.
- All 12 windows fully proven outdoors-to-interior pathfinding across 20 rounds.
- Original Public-license asset replacement and Android ARM64 device smoke test.
