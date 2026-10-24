# Arena Breakout → Xziel AAA-Mobile Clean-Room Study

Research date: 2026-09-21

## Why this game matters

Arena Breakout is unusually valuable because Tencent/MoreFun published real implementation details.

GDC identifies the mobile title as Unreal Engine 4.26.

Its public architecture includes:

- forward rendering;
- PBR;
- dynamic weather;
- precomputed indoor GI;
- Android Vulkan RHI;
- Vulkan Ray Query;
- RT reflections;
- RT ambient occlusion;
- RT soft shadows;
- high-refresh frame prediction.

## Ray-tracing scene management

The mobile team identified three major constraints:

1. BLAS memory;
2. mobile cost of BLAS construction;
3. TLAS trace cost with too many instances.

Public results after optimization:

- BLAS count reduced from ~4,700 to ~700;
- RT video memory reduced from ~4.4 GB to ~1.1 GB;
- TLAS instance count reduced to around ~600 using distance/projected-angle culling;
- Vivo X90: BLAS build <0.5 ms;
- Vivo X90: TLAS build ~1 ms.

This is the important lesson: mobile RT is primarily a **scene-management problem**.

## Reflection pipeline

Arena Breakout needed reflections without a conventional desktop RT pipeline and without bindless textures.

Publicly described sequence:

```
Base Pass
 -> Query Scene Pass
 -> Visibility Resolve
 -> joint bilateral filtering
 -> second bilateral filtering
 -> composite into scene color
```

Visibility resolve was heavily optimized:
- draw calls dropped from 600+ to roughly 110;
- overdraw was eliminated in that stage.

Roughness controls filtering and fully rough materials can avoid rays.

## RT soft shadows + AO

Public pipeline:

```
Full Prepass
 -> normals + depth
 -> Ray Query
      one shadow ray
      one AO ray
 -> temporal denoise
 -> A-Trous spatial denoise
 -> Base Pass samples result
```

They can run this at lower resolution for speed.

On Dimensity 9200-class hardware the presentation reports >70 rendering FPS in the demonstrated configuration, with caveats around masked/transparent materials and power cost.

## Opacity / foliage direction

MediaTek has also documented Opacity Micromap-related work with Arena Breakout.

Long term, Xziel can treat alpha-tested foliage/fences as a special RT capability tier rather than requiring generic any-hit processing.

## 144 FPS frame prediction

Arena Breakout also shipped a non-neural-network frame prediction pipeline.

The GDC description states that it:

- reuses previously rendered pixels;
- substantially raises output frame rate;
- lowers power consumption;
- does not add framebuffer-presentation latency in the same way traditional delayed interpolation can;
- is designed for 120/144-Hz displays.

This should be a future Xziel **Ultra-tier** feature, not a foundation.

Prerequisites:
- stable motion vectors or equivalent reprojection data;
- depth;
- disocclusion handling;
- UI/HUD separation;
- reliable frame pacing;
- robust fallback on camera cuts / large state changes.

## Proposed Xziel RT tier

Do not make RT required.

```
Tier 0: baked lighting / no RT
Tier 1: SSR / SSAO
Tier 2: enhanced SSR/GTAO
Tier 3: Vulkan Ray Query reflections OR shadows
Tier 4: RT reflection + AO + selected soft shadows
```

Ray budgets should be chosen per effect and quality state.

## RT scene data

Proposed objects:

```
XzRtGeometry
XzRtBlasCache
XzRtInstance
XzRtTlas
XzRtMaterialProxy
XzRtBudget
```

Static architecture:
- prebuilt/compacted BLAS;
- share geometry;
- aggressive LOD;
- no duplicate BLAS per visually identical object.

Dynamic zombies/characters:
- only include when effect requires them;
- distance/importance cull;
- simplified RT mesh when useful.

## Power discipline

Arena Breakout's own presentation notes that excessive render passes and texture sampling can raise power consumption.

Therefore Xziel's PerformanceGovernor must be able to disable RT dynamically when:
- GPU time rises;
- thermal headroom falls;
- memory pressure rises;
- battery/performance mode requests it.

## What we should borrow

- scene-managed RT rather than brute force;
- BLAS/TLAS budgets;
- ray-query hybrid rendering;
- temporal/spatial denoise;
- low-resolution ray effects;
- no rays for surfaces that do not visually benefit;
- high-refresh frame prediction only after correct base rendering.

## What we should not do

Do not make Xziel dependent on ray tracing.

Our maps must retain excellent baked/PBR visuals on GLES3 and ordinary Vulkan devices.

RT should be additive.

## Public references

- GDC 2024: Next Level of Mobile Graphics: Ray Tracing in Arena Breakout
  https://www.gdcvault.com/play/1034690/Next-Level-of-Mobile-Graphics
- GameRes transcript
  https://www.gameres.com/905311.html
- GDC 2024: 144FPS Rendering on Mobile
  https://www.gdcvault.com/play/1034689/144FPS-Rendering-on-Mobile-Frame
- Tencent GDC summary
  https://www.tencent.com/tencent-games-shares-insights-and-technologies-at-gdc-2024/
- MediaTek mobile OMM material
  https://developer.mediatek.com/RayTracing/6811e12b3648cc23f27eae08.html
