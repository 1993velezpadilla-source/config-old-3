# UE5 / CoD World at War (T4) → Godot 4.6 migration tooling: source-first audit

**Research timestamp:** 2026-10-08, Puerto Rico. **Decision:** stop blind per-gun viewmodel offsets; use source-authoritative conversion and validate rig/socket/bind data before editing Godot weapon presentation. This document is research and an implementation gate, not an assertion that a 1:1 gameplay converter has been run.

## Engine provenance is not interchangeable

* Call of Duty: World at War (2008) is Treyarch T4, based on IW3, **not** Unreal Engine. Source asset families: `.ff`, `.iwd`, XMODEL/XANIM, Radiant data. A generic Unreal `.uasset` importer cannot open T4 game files.
* Project Aether repackages/reconstructs WaW assets/data under Unreal Engine 5.7, adding `.uasset`, source datatables and ActorX `.psk/.psa` extraction workflows. That *Aether UE5 project* may be passed to UE→Godot tools **if original UE editor project or cooked UE archives are accessible**.
* The current GitHub branch audit enumerated **3,054 files, no `.uproject`, `.uasset`, `.umap`, `.psk`, `.psa`, `.ff` or `.iwd` checked in**. It holds rebuilt `.glb` runtime assets and the source conversion scripts. This is not the same as having an Unreal editor project on disk.
* Original source is **still recoverable from verified GitHub Actions artifacts**: run `37394234814`, `xogot-source-first-golden-reference`, holds original T4 Marine ActorX PSK reference (~95 MB artifact); run `37244741312`, `aether-waw-usmap-real-weapons`, holds recovered per-weapon Hands PSA (~63 MB artifact, original workflow asserts >=300 PSA files). Both artifacts were confirmed unexpired 2026-10-08.
* Existing `tools/weapons/build_aether_waw_source_hands.py` already calls **DarklightGames/io_scene_psk_psa** from `.github/workflows/xogot-build-all-waw-source-hands.yml`; it scales source PSK 0.01 and imports PSA in preserved source cm units. Do **not** market reusing that addon as an untried new converter or randomly rescale arms. Newer importer v9.1.3 (2026-09-09) fixed ignoring PSA scale-key import option and should be pinned and regression-tested.

## Practical options ranked for these particular source types

| Tool / upstream | Source | Outputs | Free? | Whole-scene vs complete game? | Fit |
| --- | --- | --- | --- | --- | --- |
| **FModel Aug 2026** https://github.com/4sval/FModel/releases | Unreal *cooked* archives | Whole UE worlds `.usda` incl SM, ISM, SK, landscape, lighting, sublevels | yes | **World/level yes**, UE Blueprints gameplay no; exporter warns sockets can be wrong | First option if original Aether UE5 cooked files recovered |
| **Blender USD importer** https://docs.blender.org/manual/en/5.0/files/import_export/usd.html | FModel USDA | Reconstructed Blender scene incl meshes/transforms/material previews | yes | Scene data, not UE gameplay | World intermediary |
| **Meridian 2.0** https://github.com/Naxela/Meridian | Blender scenes | Godot `.tscn`, meshes, materials, lights, cameras, collisions, decals; Godot 4.6 + Blender 4.5+ | yes | **Scene transfer**, user-supplied scripts only; does not port UE Blueprints | Best promising FREE source-to-Godot level authoring bridge for our Godot 4.6 |
| **UE native GLTF Exporter** https://dev.epicgames.com/documentation/en-us/unreal-engine/BlueprintAPI/Miscellaneous/ExporttoGLTF | Unreal editor `.uproject`, UWorld, skeletal meshes/animations | `.glb/.gltf` incl selected/all actors | yes with Unreal | Art/world only, no game logic | Most direct if full Aether UE5 editor project exists |
| **Unreal To Godot Exporter / Ciprian Stanciu** https://www.fab.com/listings/61983625-664c-4308-9b26-edfd58d41002 | UE editor 5.1–5.8 | Godot 4.2+ complete **levels**, actors, skinned animation, geometry, sounds, colliders, materials, foliage | **paid, ~$29.99 on maker site; verify current pricing** | Not Blueprints/gameplay; documented incomplete shaders/VRAM issues | Closest commercial level exporter; user's zero-budget constraint deprioritizes |
| **Asset Bridge / Iron Pixel Games v0.1.0** https://www.ironpixelgames.com/tools/asset-bridge/ | Unreal UE5 content folder | Batch meshes, rig/animations, material/texture conversions, previews | free; Windows | **Asset-level only**; whole-scene later roadmap | Free batch option if UE5 editor project exists |
| **furymob Blender UMAP Importer** https://github.com/furymob-git/blender-umap-importer | FModel `.umap` JSON + exported mesh/texture folders | Blender scene actors, hierarchy, transforms, PBR, ISM/HISM, decal metadata | MIT/free | UE level layout, no blueprint logic | Alternative to newer USDA FModel export; 4-star/young project; verify first |
| **Goblend** https://goblend.dev | Blender collections | Godot scenes, materials baked, primitive/convex collisions | free/GPL addon | Scene only | Alternative to Meridian; Godot 4.5+ |
| **DarklightGames PSK/PSA** https://extensions.blender.org/add-ons/io-scene-psk-psa/ | Original ActorX WaW hands PSK + PSA | Blender rig/animations then GLB | free/GPL | Character/first-person arm pipeline only | **Already used in our project; verify latest v9.1.3, pin exact version and import transforms** |
| **Godot native glTF + FBX/ufbx** https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/import_configuration.html | GLB/FBX | Godot AnimationLibrary, Skeleton3D, skin | free | Import, not an UE converter | Final stage; inspect bone rest, skin IBMs, apply root scale |
| **Godot retarget docs** https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/retargeting_3d_skeletons.html | Rig profiles | BoneMap/rest normalization | free | Character rigs | Rig correctness; different bind/rest can stretch arms |
| **CUE4Parse** https://github.com/FabianFG/CUE4Parse | UE cooked assets, `.pak/.uasset` | Models, textures, sound, raw properties/animations | Apache/free | Asset extraction and metadata, not auto gameplay | Headless UE archive recovery |
| **UAssetAPI/UAssetGUI** https://github.com/atenfyr/UAssetAPI | Cooked/uncooked UE package fields | Props/JSON/Kismet parse | MIT/free | Extract/inspect metadata, not Godot scenes | Datatable and marker auditing |
| **UEViewer (umodel)** https://github.com/gildor2/UEViewer | UE 1–4 archive assets | PSK, PSA, glTF models | MIT/free | Assets only; not robust general UE5 route | Backup for older UE assets |
| **FModel + CUE4Parse Blender UMAP JSON** https://github.com/furymob-git/blender-umap-importer | UE world actor JSON | Blender scene | free | Scenes | Useful when FModel USD insufficient |
| **OpenAssetTools / OAT** https://github.com/Laupetin/OpenAssetTools | T4 WaW fastfiles `.ff` and other CoD | Unlinker assets subset, bins/export | free/GPL | Partial asset extraction; does not turn WaW into UE | Native WaW source alternative |
| **Greyhound** https://github.com/Scobalula/Greyhound | Supported Call of Duty game assets | Rigged models, animations, textures/Cast | free | Asset extraction only; check exact T4 coverage | Native CoD asset route |
| **Cast** https://github.com/dtzxporter/cast | Extracted CoD models/animations + scene instances | Blender import of rig, animated meshes, materials | free | Scene asset interchange not game logic | Bridge native IW assets to Blender |
| **CallOfFile** https://github.com/Scobalula/CallOfFile | XMODEL_EXPORT/BIN; XANIM_EXPORT/BIN | lossless-format parser and converters | MIT/free | Source native model/animation files | CoD data inspection |
| **CoD Asset Importer (Blender)** https://github.com/mauserzjeh/cod-asset-importer | WaW compiled XModel, select other CoD maps | Blender models | free | WaW xmodels only (read its documented matrix); WaW BSP maps not necessarily supported | Native WaW independent compare |
| **Blender CoD addon (Blender5 fork)** https://github.com/notrickzdumbo/blender5-cod | XMODEL_EXPORT, XANIM_EXPORT | Blender export/experimental import | free | Animation and meshes only, import limitations | Alternative if source XMODEL/XANIM |
| **Husky BSP** https://github.com/Scobalula/Husky | Documented newer CoD titles | OBJ level meshes and .map metadata | free | BSP layout only; **does not list WaW support** | Do NOT assume compatible with Nacht |
| **Godot-specific Blender bridge Blendot** https://godotengine.org/asset-library/asset/5504 | Godot scene edits | round-trip Blender changes | free | Existing Godot scene editing only | Secondary after a valid import |

## Important non-options / blockers

There is no verified universal **one-click entire Unreal or World at War gameplay to Godot** translator in this audit. Unreal C++/Blueprint, CoD GSC/engine game logic, multiplayer synchronization, shaders and renderer have no 1:1 executable equivalents. FModel's 2026 *whole world export* and Meridian's *one-click full Blender scene compilation* are **not complete game ports**. A package exporter does not imply rights to redistribute proprietary assets; require independently licensed game content for commercial shipping.

**Arms-specific critical constraint:** scene/asset exporters cannot automatically reconstruct the original muzzle/optic and animated grip semantics if the source skeleton/animation bind axes or socket parent relationships were transformed incorrectly. Godot 4 bone poses vs rest, bind matrices, armature scale and quaternion handedness must be validated against the untouched original PSK+PSA. The current imported runtime (28 hand GLBs) is a derivative, not the gold source.

## Source-first implementation acceptance protocol (do not guess offsets)

1. Preserve current shipping branch. Create **a clean isolated experiment**, not another 28-arm-roll change.
2. Download the two still-live source Actions artifacts above; fingerprint the original PSK and all source PSA (SHA-256). Assert complete 113-bone skeleton and source animation track count. Do not require a user to re-upload originals already archived in our own Actions.
3. Compare source in **Blender with a pinned and verified PSK/PSA extension** to the extracted GLB. Verify bind/rest matrices, pose quaternion order, skinning, source handedness, unit conversion, `tag_weapon` and `j_wrist_ri` **at the same animation frame**. Include weapon mesh alongside hand rig at original source attachment.
4. Run **FG42, Arisaka, MP40** acceptance samples in Blender and Godot at HIP and settled ADS. Require zero manual per-gun pose offsets. Fail if trigger wrist floats, camera obstruction returns or iron optic doesn't line up. A rig-native REST frame alone is NOT successful weapon grip.
5. If raw Project Aether UE5 editor world exists, trial native UE GLTF UWorld export against one map. If only cooked Aether UE archive exists, trial **FModel Aug 2026 whole world USDA → Blender USD → Meridian 2.0 → Godot 4.6**. Validate collision, props counts, instances, normals/units/light and Android performance before whole game.
6. Keep Godot-authored gameplay systems separate; migrate data (weapons, placements, collisions, animation events) and test behavior explicitly instead of promising Blueprints auto-conversion.
7. No GREEN until side-by-side real source and Godot images match sight axis and hand contact on all 28 weapons, including firing/reloading and return-to-HIP.

**Research status:** catalog/compatibility checked; *none of the third-party UE→Godot whole-scene tools is installed or proven on the owner's sources yet*. License and feasibility checks first.
