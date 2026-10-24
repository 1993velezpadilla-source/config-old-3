# PUBG Mobile → Xziel AAA-Mobile Clean-Room Study

Research date: 2026-09-21

## Why this game matters

PUBG Mobile is one of the best examples of a huge Unreal-powered mobile game designed to run across an extreme device range.

LIGHTSPEED's engine lead Fan Zhang described a device ecosystem exceeding 22,000 phone models, with more than half of the population on lower-end devices. Their optimization philosophy is therefore not a single renderer path but a multi-level strategy.

Public GDC material summarizes the work in four principles:

1. load less and load smoothly;
2. draw less;
3. render with cheaper techniques;
4. tick/update smoothly.

The engine team also built internal tools to measure GPU, CPU and temperature and used device-specific strategies instead of one universal setting.

## Verified renderer optimizations

Samsung/Unreal Vulkan material publicly lists PUBG Mobile optimizations including:

- CPU occlusion optimization;
- RHI thread enable;
- bloom optimization.

In the shown Note9 Mali case, the combined changes produced up to about 30% FPS improvement.

This is especially relevant to Xziel because we currently have a largely single-threaded legacy rendering path and can benefit from separating game simulation, visibility, render-command generation and GPU submission.

## CPU occlusion

For Xziel, PUBG's CPU-occlusion lesson reinforces the Apex-Mobile cluster-culling direction.

Recommended visibility stack:

```
BSP/PVS
 -> room/cell visibility
 -> object frustum
 -> projected-size cull
 -> CPU occlusion
 -> mesh-cluster cull
 -> draw/instance batch
```

The important part is to avoid paying GPU cost for work the CPU can cheaply prove invisible.

## RHI thread

Long-term Xziel renderer should not issue all GPU work directly from gameplay state.

Target:

```
Gameplay thread
    |
presentation snapshot
    |
render preparation/jobs
    |
RHI submission thread
    |
GLES3 / Vulkan
```

This lets the CPU overlap game logic and render submission and gives Vulkan a useful threading model.

## Bloom optimization

PUBG Mobile and Apex Mobile both show that post processing must be bandwidth-aware.

Xziel bloom should therefore have:

- very low resolution mip chain;
- selectable pass count;
- shared downsample chain;
- optional temporal/frame amortization;
- hard GPU-time budget;
- complete disable path on low tier.

## Performance telemetry

PUBG's in-house profiling strategy maps directly to our planned XzPerformanceGovernor.

Collect:

- CPU frame time;
- GPU frame time;
- thermal state/headroom;
- FPS percentiles;
- memory high-water;
- draw calls;
- triangles;
- streaming stalls;
- shader/PSO misses;
- quality transitions.

Every major engine module should be benchmarkable independently.

## Device tiers

Do not map quality merely by brand/device name.

Device capability database should include:

- SoC/GPU;
- API/driver;
- RAM bucket;
- sustained thermal behavior;
- Vulkan/GLES features;
- measured CPU/GPU budgets.

Then runtime telemetry can override the initial profile.

## Destruction

PUBG Mobile's GDC 2025 talk also documents a fully destructible mobile-world architecture involving:

- asset pre-fracturing;
- fragment physics;
- realtime terrain destruction;
- mobile-specific performance optimization.

For Xziel this becomes a later optional feature. Pre-fracturing is far safer than runtime arbitrary mesh fracture on mobile.

Potential Zombies uses:
- breakable barricades;
- destructible cover;
- walls that expose routes;
- scripted collapse events;
- debris that becomes non-simulated after settling.

Gameplay collision/state must remain authoritative and deterministic.

## Xziel takeaways

Highest-value PUBG lessons:

1. device diversity is an engine architecture problem;
2. performance telemetry must be first-class;
3. CPU visibility optimization can be worth more than fancy GPU features;
4. separate RHI submission from gameplay;
5. post FX needs a bandwidth budget;
6. low-end and flagship paths should intentionally diverge;
7. optimize sustained power/temperature, not only cold FPS.

## Public references

- GDC 2023 LIGHTSPEED: PUBG MOBILE Performance Optimization on Mobile Platform
  https://www.gdcvault.com/play/1028709/LIGHTSPEED-STUDIOS-Developer-Summit-PUBG
- PocketGamer interview with Fan Zhang
  https://www.pocketgamer.biz/pubg-mobile-co-developer-discusses-optimising-unreal-for-thousands-of-phone-types/
- Samsung / Unreal Vulkan optimization material
  https://d3unf4s5rp9dfh.cloudfront.net/GameDev_doc/Unreal_Summit_2019-GameDev.pdf
- GDC 2025: Creating a Fully Destructible World on Mobile
  https://gdcvault.com/play/1035374/PUBG-MOBILE-Creating-A-Fully
