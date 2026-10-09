# Nacht der Untoten: real BO3 Zombies Chronicles (T7) vs Pavlov workshop UE4.21 → Godot 4.6

**Research:** 2026-10-08 | **Objective:** whole level/scene translation first; original engine coordinates, sockets, map actor placement, art and gameplay metadata; zero guessed per-object offsets.

## Crucial correction: TWO separate source games

1. **The official 2017 Black Ops III Zombies Chronicles Nacht der Untoten** was built in the **Treyarch T7/IW-derived engine**, *not* Unreal. Internal map codename is **`zm_prototype`** (not `zm_nacht`), documented at https://www.ugx-mods.com/forum/general/70/-zombies-chronicles-map-codenames-already-in-bo3-pc/15377/ . Black Ops III tools and/or a legitimately owned running PC game are needed to produce original BO3 data.
2. **The currently staged Godot Nacht source is a community recreation titled "BO3 Nacht der Untoten" for Pavlov VR**, Steam Workshop item **2755515831**, app **555160**, by **MichelCats** (Feb 2022). That workshop map is **UE4.21**, archive **WindowsNoEditor.pak**, content root **`Pavlov/Content/CustomMaps/UGC2755515831/Nacht_de_Untoten.umap`**. See https://steamcommunity.com/sharedfiles/filedetails/?id=2755515831 . The user asked for true BO3 Chronicles: this Pavlov copy is a useful substantial reference/asset source but must NOT be labeled the direct original 2017 BO3 map.
3. Existing workflow `.github/workflows/xogot-nacht-chronicles-full-map-authority.yml` already downloads Pavlov workshop 555160/2755515831 and validates **3,871 UE packages**, the UE4.21 UMAP and full package extraction. Existing `.github/workflows/xogot-stage-nacht-full-map.yml` rebuilds that into a native Godot runtime. Confirmed still-present GitHub Actions artifacts: **#37714627696** `Xogot-Nacht-Chronicles-Full-Map-Authority` (~2.9 GB), **#37762871109** `Xogot-Nacht-Chronicles-Godot-Runtime` (~2.1 GB), and **#37762871146** release APK gauntlet (~1.78 GB). Successful CI is a pipeline result; it is **not** evidence of identical BO3 source, complete gameplay, or artistically approved 1:1 layout.
4. The GitHub branch itself has no original `.ff`, `.xpak`, `.uasset`, `.umap` checked in. Original Pavlov source is in the archived CI artifact/workshop, **not** a local editor UProject. Do not waste time re-downloading or "converting" it before inventorying existing artifacts.

## Lane A — Original BO3 Chronicles Nacht (T7) to Godot

**Priority when source-authentic BO3 is the target, rather than the Pavlov approximation.**

| Tool | Source / result | Notes / limitation |
| --- | --- | --- |
| **Husky** https://github.com/Scobalula/Husky | Load legit BO3 `zm_prototype` in running PC game; export BSP geometry `*.obj`, material names `*.mtl`, image search list `*.txt`, static model placements `*.map` | **Directly supports BO3**, strongest candidate for 1:1 original static world. Not full gameplay. It warns script brushmodels may appear at origin pending mapents transform. Validate exact world scale (old exports needed 2.54 correction). |
| **Husky BO3Fix** https://github.com/Sand-Planet/Husky-BO3Fix | Fork claiming BO3 fixes | Alternative if upstream memory offsets changed; compatibility must be proven on current legitimate PC build, not assumed |
| **Greyhound** https://github.com/Scobalula/Greyhound | BO3 XModel meshes (props/weapons/characters), texture maps, XAnim animation, Cast and related formats | Has native BO3 support; recent changelog mentions BO3 LZ4 xpak extraction fix; inspect specific export file formats. Original assets remain copyrighted |
| **HydraX** https://github.com/Scobalula/HydraX | BO3/T7 scripts, tables, weapons, AI, gameplay config, zbarriers, audio structures | Specialized asset *decompiler* for BO3; GSC/LUA not automatically rebuilt as working Godot scripts |
| **BO3 Mod Tools** https://store.steampowered.com/news/posts/?appids=311210&enddate=1475054677 | Official Radiant, APE, launcher, map examples **The Giant** & Combine | This is an authoring environment; **no official Zombies Chronicles original Nacht map source** is promised/included |
| **Cast Blender addon** https://github.com/dtzxporter/cast | Greyhound/Cast meshes+skeletal animations and **scene instances** into Blender, preserve hierarchy | Correct scene root and instance library needed; animations/retarget/scale must be checked |
| **Blender native OBJ/MTL** https://docs.blender.org/manual/en/latest/files/import_export/obj.html | Husky BSP and its UV/material slots | OBJ only contains static geometry; collision/navigation and entity triggers must be derived separately |
| **Meridian 2.0** https://github.com/Naxela/Meridian | One Blender scene → Godot 4.6 `.tscn`, lighting, mesh, collision, materials | Free scene exporter, **not an automatic BO3 gameplay port**; Blender 4.5+ |
| **Goblend** https://goblend.dev/ | Alternative Blender → Godot level export | Validate on test slice before replacing existing Godot runtime |
| **Cast Python library** https://github.com/dtzxporter/cast | Inspect native scene/instance/animated hierarchy deterministically | Build pass/fail source metadata manifests, not hand-adjusted objects |
| **Community decompiled GSC** https://github.com/SyndiShanX/COD-GSC-Source | Document BO3 perks, Pack-a-Punch, GobbleGum systems | The repo already pins commit b8cce0ff... in `xogot-bo3-gameplay-source-census.yml`; scripts are **reference data**, not Godot executable gameplay |
| **OAT** https://github.com/Laupetin/OpenAssetTools | T4/T5/T6 and IW game fastfiles | **DO NOT choose for BO3**: current documented support stops at T6. Useful for original WaW, not BO3 T7 |
| **UEViewer / CUE4Parse / FModel** | Unreal archive tools | **NOT applicable to official BO3 T7**. Only the separately sourced Pavlov UE4.21 copy |

### Direct BO3 source-first workflow

1. **Prerequisite:** legitimate BO3 + Zombies Chronicles files and a Windows host running `zm_prototype`. If unavailable, **block direct source claims**. GitHub Actions hosted runner alone cannot silently download/run a user's privately owned Steam DLC.
2. Export once with Husky (+ independent BO3Fix test only if needed). Archive `zm_prototype.obj`, `.mtl`, `.map`, `.txt`, SHA256, tool version, counts/bounds.
3. Export referenced **models, textures and animations** from the same exact BO3 build via Greyhound; export **interactables/weapon/zbarrier/AI source data** via HydraX if needed. Preserve native names, origin and source transforms.
4. In Blender import Husky OBJ, instantiate props from native map placement data, then import Cast/selected Greyhound meshes. Validate Z-up, coordinate units, rotations, normals, UVs and all placements; no mystery constants/90° roll on individual guns.
5. Convert this complete *scene* via Meridian → Godot 4.6 with collision and chosen mobile LOD/material budgets. Measure count, AABB, walls/doors/windows, transformed props, material references and walkable surface against native source.
6. Gameplay reconstruction separately from BO3 GSC/metadata: zombie nav/volumes/doors/window barriers, mystery box, wallbuys, perks, source timings, audio events, multiplayer state. Static mesh export alone cannot create executable AI or network code.
7. Keep **copyright/license checks** separate: ability to extract first-party BO3 art does not imply permission to redistribute it in an independent APK.

## Lane B — Existing Pavlov Workshop (UE4.21) Nacht to Godot

**Best immediate no-new-game-data route for the world already under construction, but NOT a proof of original BO3 scene fidelity.**

| Tool | Stage | Status |
| --- | --- | --- |
| `repak` https://github.com/trumank/repak | Unpack workshop `WindowsNoEditor.pak` | **Already used** in existing 3,871-package authority pipeline |
| Existing `UEStaticSceneExtract`, `UELightExtract`, `UEMaterialAudit` etc | Extract UE4.21 UMAP objects/materials/lights/audio/particles | **Already used**; inspect differences before rebuilding with another tool |
| **FModel August 2026** https://github.com/4sval/FModel/releases/tag/aug-2026 | Whole UE worlds exported as `USD .usda` incl static/instanced/skeletal meshes, landscapes and lights | **Promising alternative**, not yet verified for this specific Pavlov UE4.21 map. Developer explicitly warns sockets/attachments may export inaccurately |
| **CUE4Parse** https://github.com/FabianFG/CUE4Parse | Read cooked UE4.21 package world/property data | Useful cross-check with existing custom C# scene reader |
| **Blender USD** https://docs.blender.org/manual/en/latest/files/import_export/usd.html | Import FModel `USDA` level assembly | Validate scene counts and transforms against source, no false "complete world" without proof |
| **Meridian 2.0** https://github.com/Naxela/Meridian | Compiles Blender scene to native Godot `.tscn` | Can be A/B compared with existing 2.1GB Godot runtime; supports renderer selection and scene-specific collisions |
| **Unreal native GLTF Exporter** https://dev.epicgames.com/documentation/en-us/unreal-engine/gltf-file-format-support-in-unreal-engine | Export UWorld if an *editable* original UE project is available | We only know of cooked workshop UE4.21 `.pak`, **not editable UProject**; do not assume this is usable |
| **UE→Godot Exporter (Fab)** https://www.fab.com/listings/61983625-664c-4308-9b26-edfd58d41002 | Commercial level conversion | Requires an Unreal editor project, not merely an extracted cooked package; conflicts with zero-budget default |

### No-fake-GREEN equivalence metrics

* Input *origin and exact engine* proven separately: direct BO3 T7 vs Pavlov UE4.21.
* Validate before/after source **level world AABB, total geometry faces, nonzero collision hulls, xform transform count, instance count, terrain, lights, materials and rendered unique cameras**, plus 10 source-authored player walk paths.
* Verify separate gameplay bindings for stairs, doors, 8+ barricade windows, rounds/AI, powerups, wallbuys, Mystery Box, audio, particles and fog; do not equate any visual import with playable game.
* Verify Android RAM, LOD/batching, thermal steady-state, offline initial scene and multiplayer separately.
* **No claim of 1:1 BO3 original** from only a Pavlov UE map, however visually similar.

**Decision today:** preserve existing Pavlov→Godot gate and current shipped project; start a **provenance + tool compatibility A/B** rather than abandoning two gigabytes of already-converted reference geometry. If authentic official BO3 Nacht is required, the native Husky + Greyhound + HydraX → Blender/Cast → Meridian route is first to validate once authorized BO3 PC source files are available.
