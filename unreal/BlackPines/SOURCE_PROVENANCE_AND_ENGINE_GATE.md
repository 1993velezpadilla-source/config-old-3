# Unreal vs Godot provenance / decision gate — 2026-10-10

This document deliberately separates actual editor projects from **cooked runtime packages**. Matching a game's graphics API or package suffix is not proof the authored scene is editable.

| Source | Evidence already in this repository | Actual origin | UE Editor path | Public release permission |
|---|---|---|---|---|
| Original Black Pines | xogot/data/black_pines_layout.json, xogot/tools/black_pines_author.py | Authored in Blender and Godot, 9 zones | Generate native UE graybox from common JSON; import original Blender outputs later | Original architecture: ours; audit individual CC0 third-party props |
| Pavlov VR Workshop Nacht | .github/workflows/xogot-chronicles-nacht-gameplay-census.yml downloads Steam Workshop 555160 / 2755515831 WindowsNoEditor.pak | A Pavlov Unreal-packaged workshop adaptation of BO3 Nacht; **not** native BO3's underlying engine files | First determine exact Pavlov cook version and lawful authorization; inspect reference data. No promise a cooked .pak can become editable .umap in a blank UE 5.8 project | Not established; require relevant permissions. Do not ship from this source |
| Project Aether | .github/workflows/xogot-aether-usmap-export.yml downloads Project Aether Win64 Shipping, UE5.7 and IoStore .utoc/.pak | Unreal 5.7 cooked standalone game | Cooked runtime, not editable .uproject. UE5.7 source asset compatibility is unproved | Not established; do not redistribute ripped assets |

Facts for installing Unreal:
- Epic's normal editor installer is the Windows/macOS Epic Games Launcher (https://www.unrealengine.com/download).
- Pavlov's documentation lists **UE 5.1.1 modkit** for its newer versions and **UE 4.21.x** for legacy maps: https://pavlovwiki.com/index.php/Getting_Started. A map distributed as WindowsNoEditor.pak may originate from the legacy toolchain; do not assume its UE version based solely on filename.
- Epic's own cooked-content documentation says editor support has **restrictions**, cooked assets can be **read-only**, and even that documentation applies specifically to Windows: https://dev.epicgames.com/documentation/unreal-engine/working-with-cooked-content-in-the-unreal-engine.
- Unreal 5.8 is used here for a NEW, original Black Pines proof of concept, not an assertion that Pavlov files open in 5.8.

Decision gate: only move all gameplay to Unreal once a REAL editor level, original high-fidelity assets, game systems, and an ARM64 Android test pass. Do not discard existing Godot work before then.
