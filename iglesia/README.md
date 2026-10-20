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
