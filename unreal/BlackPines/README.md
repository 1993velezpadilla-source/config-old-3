# Black Pines Sanatorium — Unreal Engine 5.8

**This is a native Unreal Engine C++ game project**, not a workflow to convert
Unreal assets to Godot. New development is in `unreal/BlackPines/`.

## What is actually committed

- `BlackPines.uproject`, UnrealBuildTool game/editor targets and native C++ module.
- `ABlackPinesCharacter`: first-person walking/look/jump foundation.
- `ABlackPinesGameMode`: native UE pawn startup.
- `ABlackPinesRoundDirector`: UE-native endless-wave **arithmetic and actor
  bookkeeping only**, with 24 concurrent actors max, 144 solo / 192 four-player
  late waves and 250,000 zombie-health budget. Not yet connected to enemies.
- `Content/MapData/black_pines_layout.json`: original 9 rooms, 12 portals,
  12 windows, 6 perks, and authored gameplay positions. Portable map DATA,
  not a Godot runtime or scene.

## Required to do real work in the Unreal Editor

1. On a capable Windows workstation, install Epic Games Launcher and
   **Unreal Engine 5.8** with Android target platform. For Linux, use the
   Epic-authenticated official installed build.
2. Open `unreal/BlackPines/BlackPines.uproject`, generate project files and
   compile `BlackPinesEditor` with UnrealBuildTool.
3. In Unreal Editor create the sanatorium level, import original/verified
   licensed GLB or FBX assets, then author UE collision and navigation.
4. Connect zombie actors and AI to native round director; implement
   weapon ADS, movable touch HUD, gyroscope, mystery box, perks and
   Unreal networking. Validate each in PIE and on-device.
5. In Unreal Editor use **Platforms > SDK Management > Android >
   Install SDK** (Turnkey). Build ARM64, test performance and memory on
   actual Android hardware.

Official UE installation docs:
https://dev.epicgames.com/documentation/unreal-engine/install-unreal-engine

UE 5.8 Android development requirements:
https://dev.epicgames.com/documentation/unreal-engine/android-development-requirements-for-unreal-engine

## Status / no fake completion claims

**Unreal Engine 5.8 has NOT been downloaded, installed, run or compiled by
this ChatGPT environment.** This repository is an authored **uncompiled
starter project**, not a built Android APK or working playable Unreal map.
No Unreal screenshots, zombie AI, UI, gyro, co-op or Unreal gameplay test
passes have been produced. Godot files remain in source-control history for
preservation; the Unreal port does not run or depend on Godot.

Only original and licensed content may be included in a public release.
