# Black Pines Sanatorium — Unreal Engine 5.8

**This is a native Unreal Engine C++ game project.** Active gameplay development
lives under `unreal/BlackPines/`.

## What is committed

- `BlackPines.uproject`, UnrealBuildTool game/editor targets and native C++ module.
- `ABlackPinesCharacter`: first-person walking/look/jump foundation.
- `ABlackPinesGameMode`: native UE pawn startup and automatic round-director bootstrap.
- `ABlackPinesRoundDirector`: endless-wave arithmetic, live spawn bookkeeping,
  tagged `ZombieSpawn` discovery, paced spawning, concurrent-actor cap and
  inter-round transitions.
- `ABlackPinesZombie`: replicated health/death state, round-scaled health,
  server-authoritative damage and melee attacks.
- `ABlackPinesZombieAIController`: low-frequency mobile-conscious pursuit of
  the nearest player through Unreal AI/navigation.
- `Content/MapData/black_pines_layout.json`: original 9 rooms, 12 portals,
  12 windows, 6 perks, and authored gameplay positions as portable map data.
- Android configuration targets ARM64 with mobile rendering settings.

## Native zombie loop

The authored source path is now:

`ABlackPinesGameMode`
→ `ABlackPinesRoundDirector`
→ actors tagged `ZombieSpawn`
→ `ABlackPinesZombie`
→ `ABlackPinesZombieAIController`
→ player pursuit / melee
→ zombie death
→ `RegisterZombieDeath()`
→ next-round transition.

The runtime source under `Source/BlackPines` does not depend on Godot, Xogot
or GDScript.

## What still requires a real Unreal runner

The source is authored in GitHub, but Unreal Engine 5.8 still must be installed
on a capable runner/workstation before any Editor compile, PIE test, Android
cook or APK can be claimed as passing.

Required validation:

1. Generate project files and compile `BlackPinesEditor`.
2. Create/import the actual level and add navigation.
3. Place/tag zombie spawn actors with `ZombieSpawn`.
4. Import the licensed/original weapon, enemy and environment assets directly
   into Unreal.
5. Validate navigation, combat, round transitions and replication in PIE.
6. Install the UE 5.8 Android toolchain with Turnkey and cook/package ARM64.
7. Test performance, memory, touch controls and gyroscope on Android hardware.

## Current status

The native zombie C++ foundation is committed, but **Unreal Engine 5.8 has not
yet been run against this branch in a real UE environment**, so this remains
an uncompiled source implementation rather than a certified playable build.

Only original and properly licensed content should be included in a public release.
