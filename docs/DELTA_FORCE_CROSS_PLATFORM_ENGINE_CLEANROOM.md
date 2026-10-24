# Delta Force → Xziel Cross-Platform AAA-Mobile Clean-Room Study

Research date: 2026-09-21
Target: Xziel / NZ:P modernization

## Executive conclusion

Delta Force is one of the most directly useful references for Xziel because Team Jade built one production workflow for PC, console and mobile while allowing runtime representations and renderers to differ per platform.

Core lesson: author once, cook per capability, preserve gameplay semantics rather than identical GPU work.

## Different renderers, same game

Team Jade publicly described using different rendering pipelines across device classes while preserving common visual semantics. Their 2024 material describes deferred rendering on PC and high-end mobile and forward rendering on other mobile devices. This strongly supports Xziel's planned RHI/render-graph architecture instead of hardcoding one path.

Recommended Xziel paths:
- Compatibility: legacy GL4ES/simple forward
- Mainstream: GLES3 forward
- High: Vulkan forward/Forward+
- Selected high tier: bandwidth-efficient deferred
- Ultra: optional Vulkan RT/reconstruction features

## Virtual material abstraction

Delta Force decouples shared mesh/material intent from platform-specific shaders and resource layouts. Editor-time virtual material templates can hold platform and quality variants, while the cook emits ordinary target-specific runtime materials and strips irrelevant data.

Xziel should add XzVirtualMaterial, XzMaterialRecipe, XzMaterialVariant and XzMaterialCookProfile. Artists author semantic inputs once; the cook decides whether a target receives full PBR, packed PBR, grayscale+tint reconstruction, vertex masks or another cheaper representation.

## Platform-correct collision

Delta Force treats FPS collision as independent from visual LOD because aggressive mobile LOD can otherwise create invisible railings, missing cover edges or shot/collision mismatch. Xziel should make GameplayCollision independent from PresentationMesh for doors, windows, barricades, stairs, railings and cover.

## Runtime-level transformation

Team Jade does not simply ship editor levels. Its automated build cleans unused actors, extracts/merges physics data for dedicated-server efficiency, turns vegetation into streamable type-based assets, converts terrain to CDLOD, partitions meshes based on position/bounds, performs platform-specific batching and collects performance statistics.

Xziel should build a real xzcook pipeline with level analysis, collision extraction, runtime cells, mesh clusters, instance batching, light/probe cooking, texture packing and performance estimates.

## Shared gameplay layer + platform richness

Gameplay-relevant layout stays shared. PC/high-tier presentation can add decoration, denser PCG vegetation, extra decals, micro-rubble and richer secondary effects. This is exactly how Xziel should scale without changing zombie routes, windows, doors or quest logic.

## ADS-aware streaming

Delta Force documents a mobile strategy where aiming can prioritize streaming inside the active camera frustum. Xziel should give ADS/scope mode higher priority to target-direction geometry and texture mips while deprioritizing peripheral cosmetic assets.

## Mobile batch cooker

Delta's batching validation includes material compatibility, texture format, lightmap, shadow casting, IBL, vertex budget, texture resolution and spatial distance. Xziel should use a similar BatchCompatibilityKey rather than batching only by material name.

## Sparse-probe GI

Delta's GI uses sparse probes and offline-fitted weights with common distribution/fitting/block-streaming concepts across PC/mobile. Mobile uses lower density and simpler GPU sampling; PC can carry denser data and more GPU-side work. This maps well to Xziel: lightmaps for static architecture plus sparse SH/probe blocks for zombies, players and dynamic props.

## Clipmap world-control data

Delta Force's 2025 terrain work uses clipmaps for large-world environmental state. A roughly 100 MB full control texture is reduced to about 2.5 MB resident scale in the described setup. Channels carry vegetation state, seasons, battle damage, water/flow, wetness and related biome information.

Xziel can use a much smaller XzWorldControlClipmap for wetness, blood/grime, scorch, puddles, ash/snow and environment blending.

## Dynamic texture arrays

Delta Force exposes many logical terrain materials while keeping only currently needed full-resolution layers resident. The architecture includes a low-end fallback for devices with problematic VT support.

Xziel should implement logical material IDs, resident-slice cache, priority/LRU replacement and low-mip fallback for modular walls, floors, rubble, terrain and detail families.

## Mobile material simplification

Public Delta material describes several transformations more useful than simply lowering resolution: merge texture layers, convert color layers to grayscale+tint, pack masks with normals, move masks into vertex color, reduce water sampling and replace SSR with IBL where appropriate.

Xziel's cooker should support texture-mask-to-vertex-color, channel repacking, RGB-to-grayscale+tint, detail removal and texture-array conversion.

## Fake shadows where correct

Delta Mobile avoids expensive real shadows for huge amounts of vegetation and uses vertex AO/fake direct-light grounding. Xziel should reserve costly shadows for the player weapon, nearest zombies and important moving threats; distant horde members and clutter can use cheaper contact/fake shadow representations.

## Shared skeleton, scaled animation

Delta shares a base skeleton and animation foundation across platforms, with extra bones/details and different compression/sample quality on higher tiers. Some expensive animation behavior can be substituted by IK on mobile.

Xziel should author one master rig and cook bone count, clip rate, compression, IK substitutions and secondary-physics complexity by tier.

## Feature planning instead of only presets

This is one of Delta Force's most important ideas. Their public talk describes a planner conceptually similar to a knapsack problem: features have value, runtime LOD, CPU/GPU cost and constraints. The system selects the most expressive feature set that fits the available budget, keeping expensive quality on important characters and allowing cheaper approximation on less important ones.

Xziel should add XzFeaturePlanner above XzPerformanceGovernor.

Candidate data should include:
- visual value
- gameplay value
- CPU cost
- GPU cost
- memory cost
- dependencies/conflicts
- tier mask
- distance/screen-size/importance constraints

Example: a nearby zombie can keep full skeletal update, hit reaction, dynamic shadow, decal and rich audio while a distant zombie keeps authoritative gameplay but loses IK, high-rate animation, dynamic shadow and premium VFX.

## Adaptive UI

Delta separates shared UI business logic from platform DPI, ratio, padding, navigation and cooking rules. Xziel should use the same principle for Android touch, foldables, tablets and future PC/controller support.

## Metaperf

Team Jade built Metaperf because standard tools did not meet its need for low-overhead, cross-platform, long-running, frame-by-frame capture plus custom game state and automated attribution.

The 2024 public material reported more than 10,000 captured records and more than 1,000 performance problems identified/resolved. The GDC 2026 session reports more than 15,000 sessions and more than 3,000 performance defects over 30 months, with hybrid sampling, automated stutter classification and AI-driven attribution.

Xziel should eventually build XzPerfCapture, XzPerfSession, XzFrameRecord, XzStutterClassifier and a regression database, even if the first implementation is much smaller.

## 2026 mobile direction

TiMi and Qualcomm's GDC 2026 Delta Force Mobile session explicitly focuses on scaling high-complexity PC scenes to mobile using resource recomposition plus CPU/GPU/memory/bandwidth optimization. This confirms that the production architecture continues to center on converting a high-end source representation into a mobile-efficient runtime representation.

## Updated Xziel implementation order

1. XzFrameMetrics
2. XzDeviceCaps
3. XzMemoryBudget
4. XzPerformanceGovernor
5. XzFeaturePlanner
6. XzVirtualMaterial
7. XzCook platform/quality profiles
8. Runtime-level builder and collision contracts
9. XzRHI + GLES3
10. PBR/probes/lightmaps
11. Streaming/clipmaps/visibility/cluster culling
12. Vulkan
13. Skeletal animation/VFX/audio
14. SSR/GTAO and selected high-tier rendering
15. Optional RT/frame reconstruction

## Public reference set

- GDC 2024: Delta Force Techniques From Unified Production Pipeline to Cross-Platform Runtime Support
  https://gdcvault.com/play/1034688/Delta-Force-Techniques-From-Unified
- GameRes 2024 transcript
  https://www.gameres.com/905639.html
- GDC 2024: Delta Force World Creation: Cross-Platform Art Pipeline and Tools
  https://www.gdcvault.com/play/1034826/Delta-Force-World-Creation-Cross
- GDC 2025: Performant High-Quality Terrain and Biome Technology for PC and Mobile
  https://gdcvault.com/play/1035606/-Delta-Force-Performant-High
- GameRes 2025 terrain/biome transcript
  https://www.gameres.com/911914.html
- GDC 2026: Metaperf
  https://gdcvault.com/play/1036028/Metaperf-Industrializing-Performance-Optimization-for
- GDC 2026: Mobile Development Best Practices, Delta Force Mobile
  https://gdcvault.com/play/1036052/Mobile-Development-Best-Practices-Delta
- Qualcomm GDC 2026 recap
  https://www.qualcomm.com/developer/blog/2026/05/snapdragon-game-studios-developer-forum-gdc-2026-recap

## Clean-room rule

No proprietary Delta Force source, encrypted packages, extracted assets, textures, maps or shaders are required. Xziel reproduces publicly disclosed engineering patterns in original code.