# Wuthering Waves → Xziel Mobile Engine Clean-Room Study

Research date: 2026-09-21

## Why this game matters

Wuthering Waves is important because it demonstrates a very different answer from CODM/Apex/Arena Breakout.

Instead of using mobile forward rendering everywhere, Kuro chose a heavily optimized **one-pass deferred** pipeline to keep complex materials, weather, SSR and GTAO manageable across platforms.

This means Xziel should not encode "forward is always correct" as dogma.

The RHI should make both forward and a future bandwidth-efficient one-pass deferred experiment possible.

## One-pass deferred

Kuro publicly states:

- mobile one-pass deferred reduces read/write bandwidth to roughly 1.5 GB/s;
- stable 60 FPS was maintained in its target environment;
- the goal was to reduce power/heat caused by high bandwidth.

### Mali limitations noted by Kuro

PLS-based one-pass deferred had constraints including:
- 128-bit on-chip cache;
- alpha-blend restrictions;
- limited resolve behavior;
- extra depth-fetch overhead.

Their effects had to be designed around those constraints.

Lesson:
**renderer architecture must be capability driven.**

## SSR + GTAO

Kuro integrated SSR and GTAO without breaking the one-pass design by using information from prior frames.

SSR:
- prior-frame depth/scene color;
- reprojection into current frame;
- denoising.

They report that many mobile devices could support medium-quality SSR and high-quality GTAO without severe performance loss.

For Xziel, this suggests an intermediate tier before hardware ray tracing:

```
reflection probes
 + SSR
 + GTAO
```

## Vegetation

Mobile version:
- billboards can replace 3D foreground trees;
- imposters used for middle/far ranges;
- billboard polygon count approximately 30–40% of full model trees;
- billboards face the light during shadow rendering to avoid camera-rotating shadows;
- imposter slices are dynamically streamed;
- Dynamic Texture Array enables efficient batching.

This technique applies directly to:
- dead trees;
- grass clusters;
- hanging vegetation;
- distant rubble;
- repeated exterior silhouettes.

## Weather

Kuro moved away from costly general volumetric-cloud rendering and used a custom 2D-to-3D sky workflow with animated cloud formation and weather-specific effects.

For Xziel this is a strong lesson:
**fake the correct visual result instead of simulating the most expensive physical solution.**

Our horror maps can use:
- layered sky geometry;
- scrolling/warped cloud layers;
- depth-aware fog;
- local fog volumes;
- rain sheets + near-camera droplets;
- occasional volumetric effects only in bounded spaces.

## Power profiling

Google's Android Developers case study documents Kuro's power-optimization workflow.

Kuro built a custom Perfetto + ODPM profiling setup.

Reported optimizations included:
- CPU core scheduling changes;
- thread-priority changes;
- PSO pre-compilation;
- PVS culling;
- offline baked shadow-occlusion culling.

Result:
- 3233 mW -> 2920 mW
- ~9.68% total power reduction
- same FPS and graphics settings in controlled testing.

This is exactly the measurement philosophy Xziel should adopt.

## Proposed Xziel power lab

For each representative scene:
- fixed camera path;
- fixed brightness;
- fixed quality;
- fixed FPS cap;
- fixed duration;
- same device temperature starting band.

Capture:
- CPU package/rail where available;
- GPU rail;
- DRAM/memory rail;
- total power;
- thermal state;
- frame-time percentiles.

Then A/B one engine change at a time.

## PSO precompilation

Kuro explicitly lists PSO precompilation as a power/CPU optimization.

Xziel Vulkan backend should therefore support:
- pipeline manifest at cook time;
- persistent pipeline cache;
- warm common pipelines during loading;
- record runtime cache misses;
- update next-build manifest from telemetry.

## Offline visibility

PVS and baked shadow occlusion appear again here.

That strengthens our plan to retain BSP/PVS concepts even after building a modern renderer.

Classic spatial preprocessing is not obsolete on mobile; it is a major efficiency asset.

## Renderer-choice implication

Recommended Xziel path remains:

### First modern renderer
Forward / Forward+:
- easiest transition from Vril;
- good transparency/VFX integration;
- lower architectural risk.

### Future experimental high tier
One-pass deferred:
- only after RHI/renderpass system is stable;
- only if material/lighting complexity justifies it;
- use subpass/input-attachment/PLS-like techniques by capability.

Do not prematurely force every device onto deferred.

## Public references

- Unreal Engine developer interview with Kuro Games
  https://www.unrealengine.com/developer-interviews/exploring-the-post-apocalyptic-charm-of-asg-open-worlds-in-wuthering-waves
- Android Developers power-profiling case study
  https://developer.android.com/stories/games/kuro-powerprofiler
