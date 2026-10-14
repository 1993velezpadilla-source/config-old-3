# XZIEL — Quake model formats and real GLB tooling audit (2026-10-14)

## What the engine REALLY supports

Our **Android Dead Cell app is an SDL/Vril Quake-derived engine**, not Unity. The native alias loader in `nzp-team/vril-engine/source/platform/sdl/gl/gl_model.c` accepts `IDPO` Quake v6 MDL models; our local `scripts/patch_vril_hd_alias_limits.py` increases its polygon/vertex bounds to 16k, but **does not add GLB / skeletal model loading**. A file extension rename never changes format.

**An important discovery:** the original NZ:P team **already uses an enhanced Quake engine** for its PC edition: `nzp-team/fteqw`. The FTE model plugin **directly registers glTF (.gltf) and GLB (.glb)** and parses glTF2 via `plugins/models/gltf.c` (look at `Mod_LoadGLBModel` and `Plug_GLTF_Init`). The upstream FTE code already implements this capability. We were reinventing a substantial piece of this path.

Sources:
- FTE NZ:P fork: https://github.com/nzp-team/fteqw
- Existing engine GLB importer: https://github.com/nzp-team/fteqw/blob/master/plugins/models/gltf.c
- Existing **full** converter build target: https://github.com/nzp-team/fteqw/blob/master/engine/Makefile (make `iqmtool-rel`)
- Converter description: https://github.com/fte-team/fteqw/blob/master/ftetools_readme.txt
- FTE skeletal formats: https://code.nephatrine.net/QuakeArchive/fteqw/src/branch/master/specs/skeletal.txt

IMPORTANT: FTE's top-level `iqm/Makefile` is deliberately a *reduced-feature* utility; the comments explicitly state that **GLB/GLTF reading and Quake MDL output are disabled** when using this lightweight Makefile. Always build the full converter from **`engine/Makefile`**, not `iqm/Makefile`.

## Tools that actually exist (rather than hypothetical hacks)

| Tool / source | Input -> output | Benefit | Important limitation |
|---|---|---|---|
| **FTEQW native engine GLB importer** | GLB directly -> renderable Quake engine model | Keeps skeletal data and modern mesh structure; already written by Quake developers | This is in FTEQW, **NOT our current Vril Android** |
| **FTEQW full iqmtool** | GLB/GLTF, FBX, SMD, etc -> IQM | Real skeleton, skin weights, animations; format intended for enhanced Quake | Our present Vril lacks an IQM runtime loader |
| **FTEQW full iqmtool** | GLB/GLTF -> MDL | Existing direct converter; useful quick legacy test | MDL does **not** preserve skeletal rigs or PBR and uses quantized alias poses |
| **robrohan Blender Quake 1 MDL addon** | Blender mesh/shape keys <-> MDL | Convenient visual QC and import/export (README supports Blender 5.1) | Not a skeletal engine, skin baking needs verification. https://github.com/robrohan/blender_ie_quake_mdl |
| **khreathor mdl-for-blender** | Blender meshes -> Quake v6 MDL | Source-facing Quake export, docs | MDL palette and model limitations. https://github.com/khreathor/mdl-for-blender |
| **Inter-Quake Model dev kit** | FBX/SMD/OBJ/IQE -> IQM | Established skeletal format / toolchain | Standard upstream tool is not the same as FTE's GLB-enabled build. https://github.com/lsalzman/iqm |
| **Khronos glTF tooling** | GLB -> validation and inspection | Find invalid glTF, malformed skin, material, normals | Validation does not solve mismatched target engine animations. https://github.com/KhronosGroup/glTF-Validator |

### Why converting to MDL cannot offer literally zero quality loss

Classic Quake MDL is an **8-bit-per-axis quantized, frame-animated alias format**. It contains no bone skinning, no native PBR roughness/metalness/normal maps, and only a simple UV/skin model. Our external true-color TGA skins and 16K triangle limit improve **our modified renderer**, not the underlying MDL format. Even with the same 3,229 original MP40 gun triangles, different texture sampling, UV packing, back-face winding, quantization and deformed skeleton mappings can create missing patches. In other words, the asset's **GLB source format is not itself the cause of holes** — the legacy conversion/rendering pipeline introduces opportunities for bugs.

FTE's GLB model plugin also has documented limits: no Draco mesh compression, limited UV sets, and no guarantee of 1:1 modern PBR materials. Keeping geometry does not imply matching Black Ops 3 materials/lighting.

## Strongest engineering directions (ranking)

1. **Least reinvention for modern art:** build a FTEQW/NZ:P *experimental sidecar* running native GLB or IQM in a supported desktop/headless test. Measure gun, zombies and gloved hands as model classes. Then audit how much of FTE's model loader + skeletal rendering (and animation contract) can be shared with our **Android Vril**. Preserve the current working Vril mobile version; do NOT simply replace it with FTE's PC binary.
2. **Portable long-term route:** bring the *already written* FTE IQM / glTF model-loading and skinning techniques into our SDL/Vril Android fork. This requires a real GLES runtime path, texture shader support, bone animation timing and safe cache/lifetime integration; it is not a `.glb` rename or Python exporter-only patch.
3. **Legacy fallback:** FTE `GLB -> MDL` or Blender MDL exporter, with measured skeleton alignment and pose timing. Only use when original-format compatibility is worth the unavoidable format downgrade.

Our own previous MP40 hybrid preserved gun triangles but re-bound 6 Aether bones to only `Body/Clip/Slide` from the old Quake rig, and sampled / remapped 46 alias poses; that is distinct from preserving the original Aether animation. Do NOT label it a 1:1 visual import.

## Whole-game work package, not "MP40 only"

The NZ:P `nzp-team/assets` directory currently contains **26 weapon source-category folders** (`source/models/weapons`) and **31 published weapon-category folders** (`common/models/weapons`). Some hold multiple viewmodel files. An actual catalog must enumerate **individual** first-person `v_*.mdl` models, handedness, skin variants, triangles, UV seams, frame ranges, animation role mapping, muzzle / bolt / magazine anchors, and whether the original Blender source has usable arm and hand weights. We should derive that from source rather than promise one single bone rig is compatible with every weapon.

Separate general-purpose assets:
- **All weapons:** original shot/reload/ADS source pose profiles, meshes and their hand placement.
- **All hands:** one *design family* of realistically shaped low-cost WW2 gloved hand meshes; reuse textures and retarget **per-weapon** grip and movements. Never say that changing one MP40 hand automatically updates every MDL.
- **All zombies:** same runtime GLB/IQM loader; skeleton/clip migration and head hitbox authority independent from visual scale and LOD.
- **Every map:** preserve existing Dead Cell / Nacht gameplay map and collision; GLB loading should not force a remap or damage QuakeC weapons/perks.

## First **real** source conversion evidence — GREEN, 2026-10-14

GitHub Actions run: https://github.com/1993velezpadilla-source/config-old-3/actions/runs/38655097762
Metrics-only artifact: https://github.com/1993velezpadilla-source/config-old-3/actions/runs/38655097762/artifacts/11935709467

**The upstream NZ:P FTEQW IQM utility (actual original C++ source) compiled under GitHub Actions and both conversions exited 0** against the project's **original 501,256-byte MP40 GLB**. We did **not** run any fake stand-in proxy geometry.

| Measured format | Triangles | Vertices | Joints | Animation clips | Frames | Notes |
|---|---:|---:|---:|---:|---:|---|
| Source Aether GLB | **3,229** | accessors (not necessarily shared/render count) | 1 glTF skin | **18** | source animation keyframes | **0 embedded image payloads**; external texture references need resolving |
| Native FTE **IQM** | **3,229** | 3,566 | **8** | **18** | **254** | **all 3,229 triangles and all 18 clips preserved by header counts** |
| Native FTE Quake **MDL** | **3,229** | 3,566 | **0** (no skeletal format) | 18 frame entries | 18 | Skin **128×128**. **Not** NZ:P's original 46-pose runtime contract. Material fidelity reduced |

**Significance:** The converter is real, already supplied by the NZ:P FTE fork, and maintains the modern model's polygon count in both outputs. **IQM**, not the 18-pose MDL, is the superior geometry+skeletal intermediate. Header metrics do not guarantee all facial lighting, UVs, transform quality or in-game appearance. We have **no claim** that our current Android Vril engine can load IQM or GLB yet. The direct FTE GLB plugin lives in the **FTE PC source**, not in Vril's Android path.

## Automated evidence

`.github/workflows/xziel-quake-modern-model-converters.yml` builds the **existing NZ:P FTE IQM tool** and tries converting the **real project's Aether MP40 GLB** into IQM (plus a diagnostic MDL), then checks actual on-disk geometry, bones, frames and animation counts via `tools/quake_modern_formats/audit_fte_glb_iqm.py`. Reports contain **JSON metrics only**. **No extracted BO3-derived game binaries are published**.

Tests must explicitly distinguish: successful GLB conversion; native Android Vril runtime support; first-person placement and hand grip; 46 QC pose compatibility; PBR fidelity; mobile GPU performance; and **commercial rights**.

## Licensing

NZ:P's documentation states that engine forks use GPLv2 and the NZ:P assets are CC BY-SA 4.0; the terms need project-by-project review. **Black Ops 3 / Project Aether-recovered art does not thereby become licensed for commercial redistribution.** Keep such assets experimental; production weapons/zombies/hands must come from licensed or newly authored sources. GPLv2 engine source redistribution obligations also require review before commercial release.

**Bottom line:** modern-Quake conversion tooling EXISTS, including from the *same NZ:P family*. The missing piece is a supported **modern format model runtime on our Android Vril variant** and per-weapon game animation/ADS integration, not the mere discovery of a converter.
