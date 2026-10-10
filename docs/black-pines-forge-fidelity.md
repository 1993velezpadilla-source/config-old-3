# Black Pines Forge GUI + Fidelity Pass (original indie game map)

## Source of truth / no paid tools
- Editable nine-zone map contract: `xogot/data/black_pines_layout.json`.
- Original Blender architectural authority: `xogot/tools/black_pines_author.py`.
- Original Forge decorative authority: `xogot/tools/black_pines_forge_detail.py` and `black_pines_forge_surface.py`.
- The GUI at `xogot/tools/black_pines_forge_gui.py` and headless CI call the *same backend*. No alternate source geometry, texture subscriptions, AI generation, stolen textures, or asset-store dependencies.
- Gameplay doors, zombies, collision, repairs, purchases and spawns remain owned by Godot. **Forge art is currently visual-only**; furniture collision/capsule sweeps will be a later gate. Church/Nacht unchanged.

## Open the Forge GUI
1. In Blender (3.x+), install and enable `black_pines_forge_gui.py` via **Edit > Preferences > Add-ons > Install**.
2. In **3D Viewport**, press **N** and open **Black Pines Forge**.
3. Set the repository's `xogot/data/black_pines_layout.json` as the manifest. The default `//xogot/... ` path only resolves from Blender's project working directory; browse explicitly if necessary.
4. Run **01 - Forge Entire Map**, **02 - Fidelity Pass**, then **03 - Export Original GLB**. Export is refused after RED.
5. For a no-desktop/mobile-only workflow, push a change to the Black Pines branch: GitHub Actions runs that exact author and verifies the GUI build/audit/export operators in headless Blender. No paid service is required.

## Current fidelity measures (not AAA certification)
- All 9 named rooms contain original landmark compositions.
- All 12 doorframes have original steel transoms.
- All 9 rooms have *batched*, material-varied tile-floor meshes.
- Exterior main facade has a branded, original Black Pines sign, not a commercial game mesh.
- Budgets: <=850 mesh objects, <=190,000 original mesh triangles. These numbers are *provisional authoring limits*, **not proven device FPS**.
- Real Godot visual probe captures original overview + first-person with the actual touch HUD + *nine full-resolution room closeups* from the mounted GLB. CI checks PNG existence and genuine rendering; **no automated screenshot test can certify 'perfect' artistic fidelity**.
- Independent physics/AI verifies all 12 real window crossings, all 12 door openings and all 81 nine-room route combinations.
- The remaining artistic fidelity review is human: spatial composition, silhouettes, lighting, material complexity, floor wear, window detail, prop realism, readability, immersion. Fix issues from the actual Godot screenshots, not simulated previews.

## Non-negotiable next gates
1. Synchronize any solid decorative props with native Godot collision and re-run traversal/nav checks (without shrinking zombie lanes).
2. Authentic game-ready doors, medical equipment, structural silhouette, weathering/baked PBR textures, adjusted lighting and native mobile LOD/material budgets. **No fabricated PBR source or visual perfection claim.**
3. Physically verified 15-20 rounds and zombie anti-stuck in Black Pines.
4. Real Android hardware touch/gyro/FPS/memory acceptance and all-weapon ADS/hands audits.
5. Multiplayer 4-player authoritative replication + legal redistributability audit. Existing WaW ripped/sourced assets remain internal test ONLY; never bundle them into a public release without permission.
6. Re-evaluate the nine Godot screenshots after each Fidelity Pass, iterating until approved; never substitute AI illustration for real gameplay evidence.

## Repeatable headless build
```bash
env PYTHONPATH=/usr/lib/python3/dist-packages blender -b --python xogot/tools/black_pines_author.py -- \
  --layout xogot/data/black_pines_layout.json \
  --out xogot/assets/black_pines/black_pines_architecture.glb \
  --preview build/black-pines/preview.png \
  --report build/black-pines/fidelity.json
```
