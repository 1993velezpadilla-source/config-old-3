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

### Fallback if one llvmpipe run takes longer than its allotted GitHub job time

The 16-pose single process can exceed a GitHub job's allocated render time because Mesa software rasterizes the original complex scene. A separate source-identical fail-safe was added:

- [Actual Godot 4.6.1 two-shard script parser — GREEN #37982629251](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37982629251).
- [Two parallel genuine source 8-camera shards and strict 16-camera reassembly #37982897050](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37982897050): one worker checks indoor candidate viewpoints, the other checks outdoor; both use the same 10,793 source actors, DDS source textures, 166 lights and 90-instance-group research policy, and each must create 16 real images. Combining requires exactly 32 camera-matched source screenshots, exactly 16 unique positions/yaws, independent RGB comparisons and real Mesa GPU counter improvements with no unproven Android claim.

Both shard jobs were started; **a submitted or running workflow is NOT a GREEN result**. This fallback is research-only, not new production logic and not a substitute for actual certified 360 reachable/player-window geometry.


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


## 16-view source camera sweep — verified GREEN, Oct 9 2026

Source renderer [#37979580156](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37979580156), independently decoded and measured 32 *real Godot PNGs* [#37979720999](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37979720999), and native Mesa counters [#37980306425](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37980306425): **ALL GREEN**. Exactly 16 paired views, 4 candidate eye-height camera anchors × four cardinal headings, all 16 viewpoints with visibly populated source scene content.

- 16 camera-frame draw calls summed: **78,374 source without batching → 76,463 source with 32m Vista MultiMesh**, **1,911 fewer draw calls across those 16 frame samples**. **Do NOT interpret the sum as a single-frame savings, FPS gain or Android performance**.
- 16 camera-frame Godot `RENDER_TOTAL_PRIMITIVES_IN_FRAME` counts summed: **34,088,244 → 33,427,348** (**660,896 fewer** across 16 different frame samples, not unique triangle deletion).
- All 16 paired cameras measured **strictly positive draw-call and primitive-index savings**; independent counter audit recorded **zero regressions** at any tested candidate orientation.
- Independent original RGB screenshot audit: **16/16 views pass**; maximal significant pixel changes in a view: **248 / 518,400** at central interior yaw 270°. Maximum independently measured whole-image mean RGB difference among all viewpoints approximately **0.003954%**. The other viewpoints have far smaller deltas.
- **Originals retained**: 10,793 native actor nodes, 340 original Vista tree identities, 282 temporarily represented as 90 MultiMesh groups, 58 left individual, **zero permanent deletions**.
- Fail-closed merge of two 8-camera shard PNG artifacts: first combined job [#37982897050](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37982897050) **RED only in merger** because uploaded original PNGs/reports remain nested under `shard-indoors/` and `shard-outdoors/`; **both genuine Godot renderer jobs were GREEN**. The flat-path assumption was fixed with a conservative identity-checked source shard normalizer and [independent replay #37989006848](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37989006848): **GREEN** without re-downloading/re-rendering original 2GB source. It re-certified all 32 PNGs and Mesa GPU evidence.

**Important limits:** 4 candidate origins and 4 cardinal views each are **NOT exhaustive 360 reachable navigation/window certification**. Real mobile device GPU FPS, texture residency and thermal behavior still unmeasured. The source archive is a **Pavlov UE4.21 reconstruction**, not original official BO3 T7. Ship gate remains **CLOSED**.
