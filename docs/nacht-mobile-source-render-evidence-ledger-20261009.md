# Nacht Research — Mobile Rendering Evidence Ledger
_Last verified: 2026-10-09. Not a production release approval._

## Source authority and non-negotiable limits

- Actual archive provenance: **Pavlov UE4.21 map reconstruction**. Do **not** label these files genuine **Black Ops III T7** assets.
- **10,793** original native scene actors, **493** mesh types, **16,595** material surface bindings, **574** effective materials, **718** source-used DDS textures and **166** reconstructed UE4.21 lights.
- Any source actor removal is blocked until all reachable outside/interior/door/window view cones have been *certified* never to see it. No such 360-degree navigation/visibility proof exists.
- All current spatial batching is **research branch only**; no original source actor nodes deleted, no production branch merge, and no physical Android FPS/VRAM benchmark.

## Original Godot 4.6.1 Mesa llvmpipe A/B — measured native renderer

All calls are **actual Godot Performance RENDER_TOTAL_DRAW_CALLS_IN_FRAME / RENDER_TOTAL_PRIMITIVES_IN_FRAME** at the same source camera and lighting arrangement, not projected material slots. Mesa Linux GPU software renderer is **not an Android chipset**.

| Camera | Original draws | FarLOD+DDS draws | + 32 m MultiMesh draws | Original visible primitive indices | FarLOD+DDS indices | + MultiMesh indices |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Exterior overview | 15,510 | 15,506 | **15,330** | 4,758,133 | 4,734,111 | **4,673,163** |
| Interior | 11,923 | 11,920 | **11,818** | 4,072,821 | 4,056,078 | **4,020,780** |

Actual original-source **340 Vista trees**: **282 batched into 90 MultiMesh nodes**, **58 retained individually**. The 10,793 original MeshInstance3D nodes remain available; batched ones are only temporarily hidden in research runtime.

- [Four-variant native source GPU A/B — GREEN #37974910263](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37974910263)
- [Independent real A/B GPU regression audit — GREEN #37975330395](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37975330395)
- [Original source six images / three camera positions — GREEN #37977887054](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37977887054)
- [Independent PNG RGB comparison — GREEN #37978255763](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37978255763)

Three matched source image pairs (960×540 original and batching): **3 significant changed pixels exterior overview, 0 interior, 0 tree-facing**. This is **not** proof of every gameplay position or all window sightlines.

## Additional 16 candidate cardinal viewpoints — new checks, NOT universal 360 proof

New test samples **four eye-height reference positions × 4 compass headings**, 16 matched before/after views = 32 genuine source-scene PNGs at 960×540. Camera locations are deliberately labeled **candidate**: no verified source navmesh/window topology and no claim those positions are player-reachable or form a complete traversal.

- [Native source sweep #37979580156](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37979580156)
- [Independent 32-PNG RGB + four contact-sheet audit #37979720999](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37979720999)
- [Independent 16 camera GPU drawcall/primitive regression guard #37980306425](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37980306425)
- [Real Godot parser preflight — GREEN #37979504607](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37979504607)

These 16-camera runs were started and may still be running; their actual conclusions must be rechecked via GitHub Actions rather than assumed GREEN.

## Texture bottleneck candidate — original compressed-source inventory, not measured Android VRAM

[718 original-used DDS inventory — GREEN #37959311556](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37959311556)

- 718 source DDS: 186 DXT1, 199 DXT5, 332 ATI2, 1 uncompressed.
- **647,695,308 source compressed on-disk bytes = 617.69 MiB.**
- RGBA8 fully decoded/mipped **upper-bound estimate**: 2.78 GiB; **NOT measured GPU residency, APK size, or Android memory consumption.**
- Mobile ETC2/ASTC transcode, actual residency, texture streaming, thermal throttling, window/portal culling, and actual Android FPS/p95 frame times remain **unproven**.

## Approval requirements before shipping

1. Candidate camera image audits GREEN; material/shadow/alpha and near-window visibility parity.
2. Real source actor collision/nav, accessibility and window viewpoints verified; **zero permanent deletion** until never-visible certified.
3. Profiling on a physical Android handset of the real APK using the native mobile renderer; include warm-up, sustained p95/p99 FPS and memory/thermal behavior. The llvmpipe **1 FPS CI readings are diagnostic only**.
4. Production integration reviewed separately, not silently merged from this research branch.

**Status: research only; production merge NOT approved.**
