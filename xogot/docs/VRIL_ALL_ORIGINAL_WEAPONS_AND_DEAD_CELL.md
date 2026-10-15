# Virin / NZ:P original weapons + Dead Cell — Godot 4.6 import

This is a **separate, reversible original-model import** inside the existing
XZIEL / Xogot Godot 4.6 project. It does not change `main.tscn` or the
working Virin Android APK.

## Exact source

The official `nzp-team/assets` project provides
`common/models/weapons/**/v_*.mdl` and neighboring `v_*.mdl_*.pcx`.
These are the original Quake 1 IDPO **first-person** viewmodels used by NZ:P.
They can contain the original gun **and hands** as already baked geometry.
The format has **vertex-frame animation** rather than modern rigged bones.
We therefore DO NOT invent a skeleton, separate the hands, swap to a modern
MP40 or silently remove original frames.

The original Dead Cell graybox map is regenerated using the repository's
own `tools/zombie_prototype/generate_graybox_map.py` (map `xziel_proto`),
then converted directly to Godot positions/dimensions. We keep the original
map's entity properties in JSON so game mechanics can be ported later.

## Automated build (no PC required)

1. Open the GitHub Actions workflow **Virin Original Weapons to Godot** on
   this branch and run it if it has not run automatically.
2. Download the `Virin-Original-Weapons-DeadCell-Godot46` artifact.
3. Extract its `xogot/` directory into the Xogot Godot 4.6 project.
4. Open **`res://vril_original_gallery.tscn`**.
5. Use the touch-safe **Previous**, **Next**, **Original Frames** buttons.

The importer discovers **every** `v_*.mdl` across all official weapon
folders, including multiple models in one folder. It writes a
`weapons/catalog.json` listing sources, number of frames, original frame
names, triangles and failures. Every MDL frame is baked into a glTF 2.0
morph target and keyframed at 10 FPS in one `original_frames` timeline.
PCX skins are preserved as embedded PNG textures. Nothing is intentionally
downsampled.

**Gate:** the workflow is RED if even one discovered first-person model cannot
be parsed or converted; it uploads whatever evidence exists. A successful
conversion is **not** proof of correct first-person placement, Godot material
appearance, or exact idle/fire/reload frame boundaries: these need a
visual/audio in-engine probe on Android.

## Dead Cell layout

The import includes three rooms, two paid doors, four player starts,
twelve zombie spawns and barricade path entities, weapons, perks, a power
switch, a Mystery Box and Pack-a-Punch as **authoring metadata**. In the
gallery, only geometry and basic collision are previewed. Runtime QuakeC
rounds and purchase logic are not magically transferred to Godot.

## Why not just use .blend?

Blender source files exist for many but not all original weapon families.
The **runtime MDL** remains the authority because its vertex-frame sequence
is exactly what the old engine animates, and every official first-person
model has to survive the conversion. The full editable source rigs can be
migrated in a later quality pass without replacing these original clips.

## Important scope and license

- NZ:P assets and source remain credited to `nzp-team/assets`. See the
  upstream `LICENSE.md` (CC BY-SA obligations). Gameplay QuakeC remains
  a separate licensing concern.
- This tool does **not** download proprietary Call of Duty assets.
- Import output may be large because it retains every animation frame.
- No new Android APK is represented as ready until Godot import/render
  and Android export are actually verified.
