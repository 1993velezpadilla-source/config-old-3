# Diablo Immortal → Xziel Dynamic Light/Shadow Budget Study

Research date: 2026-09-21

## Why it matters

NetEase's Diablo Immortal GDC session describes rebuilding parts of the mobile rendering/shadow pipeline to support efficient multiple dynamic lights and shadows within strict memory, performance and compatibility limits.

## Xziel lesson

Dynamic lights should be a budgeted resource, not an unrestricted scene feature.

Create XzLightBudget with:
- light importance;
- projected screen influence;
- distance;
- whether it casts shadow;
- shadow resolution/tier;
- gameplay relevance;
- temporal stability;
- room/cell ownership.

XzFeaturePlanner then selects:
- full dynamic+shadow;
- dynamic no-shadow;
- baked/probe contribution only;
- emissive-only approximation.

## Zombies examples

High priority:
- muzzle flash nearest player;
- electrical trap currently active;
- lightning nearby;
- boss/special attack;
- flashlight if gameplay-critical.

Lower priority:
- far decorative lamps;
- distant sparks;
- many overlapping particle lights;
- lights hidden behind room occlusion.

## Public reference

- GDC 2023: Rendering Lights and Shadows on Mobile in Diablo Immortal
  https://gdcvault.com/play/1029299/Rendering-Lights-and-Shadows-on