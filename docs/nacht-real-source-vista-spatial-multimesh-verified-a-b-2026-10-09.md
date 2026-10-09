# Nacht original-source Mobile renderer A/B — independently verified 2026-10-09

**Status: RESEARCH GREEN for 3 paired visual cameras; NOT production-ready.**

The archive under examination is a reconstructed **Pavlov UE4.21** scene, **NOT verified original BO3 T7/Chronicles assets**. Original geometry/materials/source actors remain preserved. The actual shipping game is not modified by this experimental branch.

## Independent Godot 4.6.1 evidence

- [Godot 4.6.1 source screenshot A/B #37977887054](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37977887054) **GREEN**: 6 authentic scene PNGs, 3 exact source camera positions, original source/optimized frames.
- [Independent PIL byte-level screenshot audit #37978255763](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37978255763) **GREEN**: confirms native Godot quantitative pixel report matches the six PNG file bytes and creates three before/after/difference panels.
- [Fast actual Godot parser preflight #37977952794](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37977952794) **GREEN**: corrected an earlier undeclared camera identifier RED (#37977137171) before re-staging source assets.
- [Four-variant actual Godot Compatibility Mesa renderer measurements #37974910263](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37974910263) **GREEN** and [independent GPU counter audit #37975330395](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37975330395) **GREEN**.

### Three actual source screenshot pairs (960×540)

Before = protected exterior source LOD + actor-local original source Vista DDS. After = exactly that original scene **plus 32 m per-material/mesh source Vista spatial MultiMesh**.

| Source camera | Mean RGB difference in percent | Pixels with mean RGB delta >3% | Significant pixel fraction |
|---|---:|---:|---:|
| Exterior overview | 0.0001512951% | 3 | 0.000578704% |
| Interior | 0.0% | 0 | 0.0% |
| Original Vista tree view | 0.00000579965% | 0 | 0.0% |

The six 960×540 PNGs contain complex populated pixels (distinct colors: exterior 19,038; interior 23,179; Vista 36,537), not flat or fabricated black frames. Results are **visually indistinguishable in these three views** under the specified capture conditions; this is not proof of every reachable camera position, lighting condition, shadow transition or transparent material.

### Measured Mesa GPU render monitor deltas

| Source camera | Original draw calls | Original+LOD+DDS+Spatial MultiMesh | Saved | Original primitive/vertex-or-index monitor | Optimized monitor |
|---|---:|---:|---:|---:|---:|
| Exterior overview | 15,510 | 15,330 | 180 (1.16054%) | 4,758,133 | 4,673,163 |
| Interior | 11,923 | 11,818 | 105 (0.88065%) | 4,072,821 | 4,020,780 |

Godot's `Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME` includes total rendered vertices/indices and shadow/depth passes; it is **not an exact triangle count or Android GPU performance measurement**. The performance deltas represent one diagnostic render sample for each camera/variant on **Linux Mesa llvmpipe**, not median frame time, FPS, Vulkan Mobile renderer or energy draw. The original 173 downsized actor-local Vista DDS textures produced zero additional reduction in the two draw-call snapshots; they may still affect texture bandwidth but VRAM gains have **not** been measured.

### Original source preservation

- 10,793 original GLB source actors, 16,595 material/surface assignments, 718 original DDS images and 166 source lights remained in the research reconstruction.
- Exactly **90 experimental MultiMesh groups** stood in for **282 temporarily hidden but retained** original Vista tree MeshInstance3D actors. Remaining **58 Vista trees** retained standalone instances.
- No original actor was permanently deleted, no source world matrix was changed, no source collision/navigation edited.
- Authored 340-tree/4-native-mesh-family spatial batching read-only source policy remains separate from runtime geometry.

### Release blocks (cannot certify from these three images)

1. Reachable 360° player view volume **including every outside/window/door/upper-floor/scope view** has NOT been exhaustively visibility tested. Do not delete/hide permanent distant geometry based on one camera.
2. Shadow, alpha, texture-filtering, per-actor LOD and material parity need broader lighting/time-of-day/camera sweeps. Source reconstruction images still exhibit existing visual problems (holes/flat skies/very dark areas); parity alone does not fix these original reconstruction defects.
3. **Physical Android hardware**: no actual device FPS, frame-time p95/p99, Vulkan Mobile backend draw calls, GPU memory, CPU throttling, battery draw or APK package measurements have been performed. Do not extrapolate Mesa 1 FPS to Android.
4. Production-game integration, player interaction/collisions/nav and actual shipping APK remain blocked by these gates.

**Decision:** keep the source-preserving 32 m MultiMesh research implementation in draft; allow further optimization experiments but do not silently merge or delete original scenery.
