# Nacht — black interior material fidelity gate (NOT PASSED)

**2026-10-09 | research only, source archive is reconstructed Pavlov UE4.21, NOT actual BO3 T7.**

## Player-reported RED

Significant black surfaces that appear to have no texture exist in the original (unoptimized) native Godot scene. Optimization MultiMesh before/after pixel parity passing **does not** certify quality or actual intended art. No guessed texture, new geometry, or irreversible deletion is permitted to claim a fix.

## Reproducible source proof

- [Original 10,793 actors, 574 source material paths, 16,595 source surfaces, 718 used original DDS Godot binding #37945872261](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37945872261): 16,593 of 16,595 surfaces have original albedo textures loaded; **texture presence is not shader-translation correctness**.
- [All 574 original effective material graph states #37990257942](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37990257942): 570 partial graph, 3 missing, 1 not-applicable; 571 original UE4.21 materials are Masked, 3 Opaque.
- [Eight genuine original Godot interior screenshot black-region audit #37990807275](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37990807275): worst original interior central yaw270 screen-center sample **23.98% near-black**, original interior yaw270 **18.29%**, original interior yaw180 **12.98%**. This includes intentional sky/shadows; color alone doesn't prove a material failed.
- [Nine genuine full-source three-stage camera renders #37990475959](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37990475959): unaltered source vs only two-sided rasterization vs temporarily opaque unshaded debug material. **All RED art causes still need source attribution**:
  - interior central yaw180: 62,395 near-black source ROI pixels → 1,653 recovered by no-cull only, another 60,569 by full opaque unshaded geometry, 173 remained black.
  - interior original yaw0: 17,889 black → 10 recovered by no-cull, 16,349 by opaque unshaded, 1,530 remain.
  - interior original yaw270: 46,864 black → 39 recovered by no-cull, 45,742 by opaque unshaded, 1,083 remain.
  - These are **pixel class diagnostic changes**, not a texture/material fidelity fix; replacing all source materials with flat unshaded colors is NOT a valid game output.
- Two real authored gray untextured Basic Cube actors at imported source origin: **ue_instance_000004**, **ue_instance_000005**, source mesh type 492, bounds 1.0m / 2.54m. Preserve originals until the 3D placement/provenance/gameplay role is verified.

## Source shader-translation hypothesis under test — no production alpha override

Original native Godot `xogot/scripts/xziel_benchmark_loader.gd` translates **all 571 `BLEND_Masked`** source materials to Godot `TRANSPARENCY_ALPHA_SCISSOR`, which evaluates the imported diffuse texture's **alpha**. Source UE4 masking instead depends on actual shader-graph **OpacityMask output**, not necessarily diffuse alpha. Across all 571 archived masked materials, no explicit OpacityMask output link is present **in the recovered partial cooked metadata**; this is inconclusive, not proof the actual shader has no mask. Source graph is partial, and masks are legitimate for foliage, glass, fences, damaged surfaces. Never disable them globally merely to turn black holes into walls.

- [Exact source mask link audit #37991708288](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37991708288) GREEN: 571 masked material identities, 15,372 original surfaces, 0 explicit recovered OpacityMask outputs; all source shader graphs may be incomplete.
- [Repaired native Godot parser #37991956651](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37991956651) GREEN after initial RED due missing helper.
- [Original full scene three-camera actual pixel A/B alpha-mask vs unshaded-lighting #37991956823](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37991956823) is the next decisive test. One temporary experiment disables only Godot alpha scissor while retaining DDS textures and source lighting; the next keeps DDS but disables lighting; then it restores all original source materials. All shader overrides are research-only and are reverted; no shipped gameplay scene is changed.

## Definition of done

1. Attribute each major black wall/hole to exact original source actor/material/texture coordinates (or confirm legitimate source hole/dark night sky), then change a **global shader semantic** only where source metadata establishes it.
2. Preserve intentional masked material holes (foliage, barricades, glass/fences), original geometry, collision/navmesh and exact source 10,793 actor identities. Never fill with arbitrary stock texture.
3. Re-render exact paired original-source interior + exterior cameras and independent RGB/geometry/shadow/alpha diagnostics; correct visible black panels without converting foliage cards to opaque rectangles.
4. Test real Godot Android scene on a physical handset, sustained p95/p99, VRAM/memory; CI Mesa raster screenshots are **not** a phone benchmark.
5. Review independently before merging into production. **Current status: INTERIOR ART FIDELITY RED; deployment/merge blocked.**
