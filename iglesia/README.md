# IGLESIA — Godot 4.6 clean-room Android FPS

**Mapa: Iglesia.** This is a NEW self-contained Godot project under `iglesia/`. It is not the old NZ:P, Quake, Virin, Sanctum, or Xogot runtime; no previous gameplay/weapon/UI script is imported. Old repositories are read-only reference sources. The first target is the nave with original Tripo benches and altar, stone PBR 4K materials, collidable pews, 2.5D zombie presentation, 2D pixel weapon art, and Android touch input.

## Source authority (explicit and immutable)
- Base project and new GDScript: `iglesia/`.
- Owner-authored altar and benches (GLB): `config-old-3` branch `feature/sanctum-ash-tripo-furniture-swap-20261020`, `xogot/assets/environment/church/altar.glb` and `bench.glb`. **Art only; do not import scenes/scripts.**
- 4K stone PBR diffuse/normal/roughness: same branch, `xogot/assets/materials/church/stone_wall_4k`.
- Approved **12 touch action PNGs**, not the rejected SVG skins: `config-old-3` commit `0119c5b0f9109c4c88dbdd4173a9a2ba523abc3d`, `assets/xziel/official_touch_skins_v1/`.
- Owner-approved 1448×1086 MP40 2D source sheet: `XZombie` branch `experiment/nun-universal-bone2d-hands-v1-20261019`, `bukkbeek-mobile/pixel_assets/WWII MP40 Pixel Art Sprite Sheet.png`. **Art only**, no old weapon or gameplay scripts.
- NZ:P/WaW gameplay research `temp-files-2/docs/zombies-design-research/` is **reference**, not runtime code.
- Forgive Me Father 2: **visual direction** for billboarding/sprite-driven enemies, not copied commercial art.

## Bootstrapping assets
At repo root run `python3 iglesia/tools/stage_assets.py`. Pillow is required for splitting the existing owner-approved MP40 sheet (`python3 -m pip install Pillow`). This copies from the parent repo's existing `xogot` art and downloads pinned approved PNGs from the owner's GitHub; it never alters original assets. Godot's importer then converts GLB and textures. The generated `iglesia/assets` files are ignored in Git except the manifest, to avoid duplicating ~170 MB of binary meshes; CI stages them before the import. The runner must have network access for GitHub PNG fetch.

Open **`iglesia/project.godot`**, not the old `xogot/project.godot`. Run `godot --headless --path iglesia --editor --import --quit`, then `godot --headless --path iglesia --script res://tests/smoke.gd`. The project boots to a single original church nave; asset staging is required for the real bench/altar visuals. Missing assets are flagged, never silently represented as validated shipped art.

## Release gates
A real APK, valid art import, rendering screenshots, collision/pathing under combat, 4K surface inspection, licensing and real-device controls must be verified before GREEN. These gates are **NOT** automatically passed by a GitHub commit. Zombie artwork is a provisional debug stand-in until the owner's approved fully animated 2.5D nun sheet is incorporated. There is no claim of final FMF2-quality art, finished map, four-player network, or ready-to-download APK yet.

## Non-negotiable gameplay direction
Landscape Android; thumb joystick + right-look + simultaneous fire/look; ADS hold/toggle option; gyroscope only while ADS; sprint never interrupts reload; weapon pose frames from approved 2D source; zombies must physically navigate around pews, not through them; unbounded round counter; wallbuy visible; no legacy Virin systems or deprecated touch skins.

## Real Tripo church chandelier import (source-gated)
The independent `stage_tripo_fixtures.py` searches the existing owner church/Tripo asset directories, copies only matching ORIGINAL GLBs without editing their bytes and records their Git blob hashes in a staged JSON catalog. `level.gd` fits real hanging chandeliers to the ceiling underside, sconces to wall planes, and standing candelabra to the floor. No generated substitutes or floating dummy candles. The headless smoke requires that every source catalog entry produce a real imported fixture.

As of 2026-10-20, the accessible GitHub branch has owner altar and bench GLBs but **no confirmed Tripo chandelier/sconce GLBs**. Hence there are not yet any actual Tripo light fixtures to instantiate; automated gauntlet prints a clear missing-source message, rather than claiming they're fixed. Import locations and audit: `docs/TRIPO_CHURCH_ASSET_AUDIT.md`.

## 2026-10-20 source correction — recovered split Tripo archive library
**The 104 original user Tripo GLBs ARE FOUND**, in the user's project Library
`/ZOMBIESSSSSSS PORTABLE/gift_runtime_packs/`. Original eight ZIPs are:
`altar.zip`, `candleholders.zip`, `chandeliers.zip`, `furniture.zip`,
`ruins.zip`, `stained_multi.zip`, `stained_single.zip`, `statues.zip`.
The new `stage_original_tripo_packs.py` is the source-locked importer, tested
against each archive SHA256 and split membership. It replaces generic
filename guessing when actual original archives are staged into the repo.
This is source code integration only; GitHub APK still lacks these archives
until the binary files are copied/uploaded into a source folder.

## Authentic Tripo source-release gate
The Android CI now blocks export unless all 8 preserved ZIPs and all 104 split source GLBs are verified, and the ten first-room fixtures (four chandelier pieces, four wall-mounted holders, two floor holders) are staged from original Tripo GLBs. The eight ZIP archives have been located in the project Library, but not yet transferred into the GitHub repository; until then, CI must show a source-gate RED rather than publish the old-looking APK as the new art update. Original meshes/textures are not replaced with synthetics.

## Single-bundle mobile source transfer (October 20)
Exact owner archives are available in `Iglesia-8-ZIP-Originales-Tripo-104-GLB.zip` (250,870,223 bytes, SHA256 `3dbb9c860106ba907ff7e5ff46fa1dc84f8ef12e93a7f1d503b513103d87265b`). It wraps eight untouched original ZIPs plus one manifest. Android browser users upload only this single archive as a Release asset at tag `iglesia-tripo-originals-v1`. The Godot workflow downloads it, checks outer SHA, unpacks original 8 ZIPs, and checks each source SHA before stage; source absence is RED. `iglesia-original-tripo-release.yml` creates release metadata/tag, never claims to have transferred missing media.
