# Black Pines Forge GUI + Fidelity Pass (original game map with licensed CC0 medical props)

## Source of truth / no paid tools
- Editable nine-zone map contract: `xogot/data/black_pines_layout.json`.
- Original Blender architectural authority: `xogot/tools/black_pines_author.py`.
- Original Forge decorative authority: `xogot/tools/black_pines_forge_detail.py`, `black_pines_forge_surface.py`, `black_pines_forge_hospital_kit.py` and `black_pines_forge_materials.py`.
- The GUI at `xogot/tools/black_pines_forge_gui.py` and headless CI call the *same backend*. Core building/architecture, routes and gameplay are original. Four explicitly listed CC0 3DAssets.dev meshes are now imported via `black_pines_cc0_import.py`; source records/placements are in `xogot/data/black_pines_cc0_manifest.json`. These models were produced with AI-assisted tools by their provider; do not represent them as originally authored by this project.
- Gameplay doors, zombies, collision, repairs, purchases and spawns remain owned by Godot. **Nine major furnishings now have native low-cost collision** driven by the same manifest as Blender; other small decorations remain visual-only. Church/Nacht unchanged.

## Open the Forge GUI
1. In Blender (3.x+), install the **`Black-Pines-Forge-GUI-install-in-Blender.zip`** produced by the **Blender Artpass** GitHub Actions artifact via **Edit > Preferences > Add-ons > Install**. The ZIP contains the Blender Python modules, CC0 source manifest, and four bundled source GLBs for offline editing.; installing only the loose GUI `.py` without its author/detail/surface siblings does not work.
2. In **3D Viewport**, press **N** and open **Black Pines Forge**.
3. Set the repository's `xogot/data/black_pines_layout.json` as the manifest. The default `//xogot/... ` path only resolves from Blender's project working directory; browse explicitly if necessary.
4. Run **01 - Forge Entire Map**, **02 - Fidelity Pass**, then **03 - Export Original GLB**. Export is refused after RED.
5. For a no-desktop/mobile-only workflow, push a change to the Black Pines branch: GitHub Actions runs that exact author and verifies the GUI build/audit/export operators in headless Blender. No paid service is required.


## Free CC0 hospital integration (real models, no Tripo credits)
- Four source assets from 3DAssets.dev's [Hospital Wards and Clinic Operations](https://3dassets.dev/packs/hospital-wards-and-clinic-operations): wheelchair + IV stand in Patient Wing, three-panel privacy screen in Isolation, ceiling surgical lamp in Surgery.
- Publisher license: [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/); commercial reuse and redistribution allowed as stated on each asset page. The source manifest preserves provenance and exact CDN model path for each item. The four imported models are **third-party assets**, distinct from original Black Pines architecture.
- Reproducible GitHub build downloads four real glTF2 binary files, checks their format, then imports via Blender 4 and bakes them into the mobile-optimized scene GLB. The distributable Blender GUI add-on includes the four downloaded source GLBs to work without internet once installed.
- The assets are **noninteractive cosmetic geometry** with no additional native collisions until separate physics/navigation acceptance; the existing 9 major collision proxies remain authoritative. This is not a guarantee of completed AAA visuals, long-round gameplay or Android device FPS.

## Current fidelity measures (not AAA certification)
- All 9 named rooms contain original landmark compositions.
- All 12 doorframes have original steel transoms.
- All 9 rooms have *batched*, material-varied tile-floor meshes.
- Exterior main facade has a branded, original Black Pines sign, not a commercial game mesh.
- **Ambulance Court visual QA**: reviewed actual Godot yard shot, added 30 original ambulance details (side cabin glazing, windshield, emergency stripes, exterior door seams, headlights, grille, bumpers, medical side plaques). Blender fidelity and imported Godot runtime assert that two genuine side-label meshes survive mobile batching. Still a stylized low-poly vehicle; no AAA/perfect claim.
- Budgets: <=850 source mesh objects, <=190,000 source mesh triangles. The latest passing mobile batch reduced 611 original meshes to 126 exported Godot meshes (79.4% reduction) while retaining 9 hero objects, 9 floor meshes and the editable `.blend`. These numbers are *provisional authoring limits*, **not proven device FPS**.
- Real Godot visual probe captures original overview + first-person with the actual touch HUD + *nine full-resolution room closeups* from the mounted GLB. CI checks PNG existence and genuine rendering; **no automated screenshot test can certify 'perfect' artistic fidelity**.
- Independent physics/AI verifies all 12 real window crossings, all 12 door openings and all 81 nine-room route combinations. Nine medical/industrial hero collision boxes are ray-tested, and 36 player-height rays must remain clear through the opened portals.
- The remaining artistic fidelity review is human: spatial composition, silhouettes, lighting, material complexity, floor wear, window detail, prop realism, readability, immersion. Fix issues from the actual Godot screenshots, not simulated previews.

## Non-negotiable next gates
1. Expand collision carefully to additional large furniture only after maintaining door/window routes; nine major hero fixtures already have Godot native colliders with a shared Blender/Godot manifest.
2. Authentic game-ready doors, medical equipment, structural silhouette, weathering/baked PBR textures, adjusted lighting and native mobile LOD/material budgets. **No fabricated PBR source or visual perfection claim.**
3. **Endless-round survival is now configured** for Black Pines; 20 automated rounds (674 zombie actors), full actual round 21 (63), and one-actor samples at rounds 50 through 1,000,000 pass Godot director tests. This is NOT 1,000,000 played rounds. The game has no designed terminal round, but Android-safe wave/HP caps (144 solo, 192 four-player, 24 simultaneously, 250,000 max HP) do apply. Still required: physically played long sessions with zombie anti-stuck audits.
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
