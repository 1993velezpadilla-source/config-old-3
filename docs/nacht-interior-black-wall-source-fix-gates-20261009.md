# Nacht — Black Interior Wall Recovery, original material fidelity and shipping gates

**2026-10-09 research only — NOT an approved game change.**

This is the black-interior defect called out by the player, **not** a MultiMesh performance failure. Archive provenance is the **Pavlov UE4.21 reconstruction** of a Nacht-inspired map, NOT authentic BO3 T7. The goal is faithful source-authored walls/materials, not manually painting black pixels gray or making all source shaders opaque.

## Verified baseline

- 10,793 original native source actor nodes, 16,595 original effective material-surface bindings, 574 distinct original material paths; 718 original-used DDS staged with 166 UE4 light components.
- [Nacht material census GREEN #37990257942](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37990257942): Godot loads 16,593/16,595 source albedo textures but 570/574 recovered UE shader graphs are only partial; a texture loaded does **not** imply opaque walls, correct UE OpacityMask, tangents, or lighting fidelity.
- [Actual black-pixel forensic GREEN #37990475959](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37990475959): three matched source interiors compared (source material / backface-culling disabled / opaque unlit categorical original geometry). Most black pixels are backed by actual geometry. Debug color does **not** fix shipping materials.
- [Original Alpha Scissor vs unshaded source DDS A/B GREEN #37991956823](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37991956823): at central interior camera, of **62,395** almost-black ROI pixels, **18,494** become nonblack with mask disabled; an **additional 40,384** become nonblack when original DDS shaders are unshaded; **3,517** remain nearly black. These numbers partition *experimental* pixel responses; unshaded does **not prove** which real source light, shadow, normal map or gameplay nighttime condition is wrong. Source materials restored exactly.
- [Unsafe full 564 MasterMat alpha preview GREEN #37993064837](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37993064837): 15,339 original surface bindings become temporarily opaque across all source MasterMat derivatives, bringing back dark geometry but **includes foliage and potentially real cutouts**. This is unacceptable as a shipping fix.
- Source records list **571** masked original materials, **564** generic MasterMat derivatives and **7** other masked sources. OpacityMask output link is **unproven** because cooked graphs are partial. Do not confuse absent recovered links with certified original graph output.

## Candidate FIX A — **only original hard structural surfaces**

- [Conservative source-policy + actual Godot parser GREEN #37994785597](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37994785597).
- Exact source material paths including original `materials/` and `MAP_FILES/` repositories: **26** structural wall/column/concrete/tile/plaster families, **1,262** exact surface bindings, all other **548** original materials left unchanged.
- Reversible GDScript controller: `tools/maps/nacht_apply_conservative_opaque_architecture_research.gd`. It *clones* actual original StandardMaterial3D per distinct resource, removes only their alpha scissor, keeps the original DDS albedo, normal map, culling, lights and mesh transform. All **1,262** original override pointers must restore exactly, otherwise RED; no source asset changes.
- First native-source A/B [#37994861667](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37994861667) was RED because a strict provenance validator allowed only original `materials/` but some source-authoritative masks live in `MAP_FILES/`. Corrected guard and re-run [#37995469541](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37995469541) were launched. Check GitHub for the conclusion; a queued/executing gauntlet is **not GREEN**.
- Independent actual 3-camera source 26-architecture vs 564-generic original PNG comparison [#3799547](https://github.com/1993velezpadilla-source/config-old-3/actions) will be verified via fresh run ID. Must preserve 3 original source before/after views and a 100%-restored control.

## Candidate investigation B — actual source normals vs shadows

- Godot full archive stage in [#37995056516](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/37995056516): 2 original player-height cameras × (original source material/light, *temporary* all source shadow casting off, *temporary* normal maps off) + original restored screenshot. 7 real frame PNGs and exact material/light-state restoration.
- The original light inventory is **144 points, 19 spots, 2 directionals, 1 skylight**. Godot Compatibility has an OpenGL scene light budget, while source lighting used UE4.21; an unlit scene screenshot becoming brighter alone **cannot identify** incorrectly-translated per-source light photometry, normals, masked alpha, night exposure or shadow occlusion.
- **Important 4.6 engine constraint**: Godot official documentation says `rendering/lights_and_shadows/use_physical_light_units` is only effective in **Forward+**, **not Mobile and Compatibility**. Merely flipping that project flag cannot fix this game's Godot Compatibility source camera darkness. `light_intensity_lumens` / `light_intensity_lux` recorded with `light_energy=1` is not proof physically equivalent real renderer lighting on mobile.

## Shipping gates remain BLOCKED

1. Prove selected hard-surface source material alpha behavior with original PNG before/after at all relevant indoor/exterior player-visible, especially through windows; preserve intended alpha foliage, fencing and window glass. **Do not force all 564 MasterMats opaque.**
2. Diagnose shadowing, normal orientation, actual light intensities/units, tonemapping/exposure and source material albedo independently. Keep Nacht spooky rather than blast uniform white light.
3. Verify there are no actual missing source actor geometries causing holes (masked/unshaded geometry color is only a diagnostic).
4. Only after those gates pass, separately propose default-on source-driven material/shader fix, run gameplay collision and native Android sustained frame budget tests. No irreversible source geometry deletion or production PR merge.

**Black interior currently remains RED as a shipping-quality criterion; GREEN proof is diagnosis or reversible code only.**
