## Agent command: OPEN HAYUYA

`open hayuya` / `abre hayuya` is an action command for Christian and Felix/Volnox.

Agents must resolve `hayuya/workspace.json`, open the preferred GUI workspace, and return the direct GUI link. Do not require LAN IPs, terminal commands, or GitHub Actions knowledge for the normal open flow. The GitHub Issue Hub is fallback only when the GUI deployment is unavailable.

# HAYUYA 3D MASTER PROMPT

**Hayuya 3D** now means the team's complete **image-to-3D orchestration engine**. It is not just an alias for Hunyuan3D.

Use this instruction whenever Christian, Félix, Volnox, or another teammate says things such as:

- "use Hayuya"
- "make this a 3D model"
- "make a GLB from this photo"
- "prepare it for Hayuya 3D"
- "turn this zombie/prop/building into a model"

## Normal input: 1 or more photos

Hayuya must be able to start from **one photo**, but there is no Hayuya-level upper limit on useful real references.

Every additional photo of the same asset is authoritative evidence and must materially improve reconstruction, material/detail recovery, or validation; never silently ignore extra references.

Whole-object views and detail close-ups have different jobs. Hayuya should keep them in the same master reference pool while routing full-object views to geometry/Judge and detail/close-up images to material/local-detail stages.

Do **not** demand a manual 8-view turnaround. If 1, 2, 5, 9, 20, or more useful real references exist, ingest the complete reference pool.

## Automatic pipeline

1. Lock the supplied source photo(s).
2. Remove/normalize background and framing without changing identity.
3. Build missing view coverage automatically; on one-source jobs use executable Wonder3D ViewForge when available.
4. Preserve real source views as higher-confidence anchors than generated views; synthetic front must never replace the real anchor.
5. Generate multiple independent 3D candidates.
6. Judge candidates against mesh health, confidence-weighted silhouette/source-view agreement, perspective-refined cameras, DINOv2 RGB appearance, local-detail references, and low-weight synthetic normal support when available.
7. Select the strongest valid candidate.
8. In Monster/Ultra, optionally let TripoSF challenge the geometry at 1024³; never promote it merely for having more detail.
9. If refined geometry wins real-source evidence, use Material Bridge v2 to transfer packed UV/PBR material evidence (baseColor, metallic/roughness, normal, AO/occlusion, emissive when available); fall back to v1 base-color projection only when no usable PBR/UV exists.
10. Return the bridged GLB to the full final Judge; never auto-promote refinement merely because it is denser.
11. Build/retain UV and PBR material data.
12. For game/mobile/monster/ultra assets, run GamePrep to create master, LOD0-LOD3, convex collision, turntable and GamePrep manifest unless explicitly disabled. Preserve PBR through the shared Material Bridge v2 transfer context whenever possible.
13. Export the final GLB plus plan, ranking and manifests.

## Canonical ViewForge coverage

When extra views are useful, Hayuya targets:

1. Front
2. Front 45 Right
3. Right Side
4. Back 45 Right
5. Back
6. Back 45 Left
7. Left Side
8. Front 45 Left

These views may come from:

- real user references
- open-source sparse-view generation
- multiview RGB generation
- multiview normal/depth generation

Generated views are support evidence. They must not silently rewrite the identity of a real source photo.

## Identity lock

Across every candidate and synthesized view preserve:

- same identity / face
- same hair and silhouette
- same clothing
- same accessories
- same proportions
- same asymmetry
- same damage / tears / wear logic
- same distinctive geometry

Never use blind mirroring when it corrupts asymmetric details.

## Multi-reference rule

When multiple photos are supplied:

- preserve **every unique real photo** in the reference pool
- accept complete folders recursively, not only individually enumerated files
- recognize explicit `details/`, `textures/`, `materials/`, `closeups/` folders as local-detail evidence
- keep detail refs out of whole-object silhouette scoring
- when Judge v3/DINOv2 is active, search those detail refs against local patches from multiple candidate angles so face/clothing/symbol/wound/material evidence affects ranking
- use all real photos as Judge evidence
- prefer native multi-image reconstruction for at least one candidate family
- when a backend has a per-call image/VRAM limit, split references into deterministic overlapping anchor groups rather than discarding extras
- keep the primary source in every bounded group for identity continuity
- in Monster/Ultra workflows, allow independent single-image geometry hypotheses from every real source unless an explicit compute budget is requested
- never replace a real photo with an invented synthetic view
- synthetic views fill missing coverage only

## Hayuya Monster backends

Default core is permissive open-source and version pinned.

Current families include:

- TripoSG
- TRELLIS.2
- TRELLIS multi-image
- InstantMesh / Zero123++
- TripoSR
- Wonder3D executable ViewForge RGB + normal expansion
- TripoSF evidence-gated 1024³ refinement
- Material Bridge v2 PBR UV/material transfer with v1 base-color fallback
- PSHuman character-specialist roadmap

Hunyuan3D is an optional backend, not the definition of Hayuya.

Cloud services such as Tripo or Meshy may be optional official-API comparison backends, never mandatory dependencies.

## GPU proof rule

Do not describe a heavy backend as "GPU proven" until a real provisioned runner has executed it.

The repo includes:

- `tools/hayuya3d/gpu_doctor.py` — verifies NVIDIA inventory, pinned backend SHAs, backend Python executables and CUDA readiness
- `tools/hayuya3d/gpu_e2e.sh` — one-photo La Llorona end-to-end proof runner
- `tools/hayuya3d/gpu_verify.py` — validates final GLB + four LODs + turntable and writes `GPU_E2E_PASS.json`
- `.github/workflows/hayuya-gpu-e2e.yml` — manual self-hosted GPU workflow

DINOv2 may run in a separate environment through `HAYUYA_DINOV2_PYTHON`, just like the generation backends.

## Quality rule

Do not choose a model because it is the newest or has the highest polygon count.

Choose the model that best preserves the supplied reference while remaining healthy and production-usable.

Real photographs outrank synthetic evidence. A refinement, synthetic view, normal map, or high polygon count can help a candidate, but none of them may override contradictory real-source evidence.

Backend runtime environments are isolated. Never "fix" a backend by silently installing its Torch/CUDA stack into Hayuya's controller environment. Use the pinned backend environment plan and `HAYUYA_<BACKEND>_PYTHON` wrappers.

After any topology change, do not blindly preserve tangent-space normal maps or baked AO. Carry safe PBR channels, mark normal/AO as requiring rebake, and expose that state in manifests.

## Quality tiers: mobile is a derivative, never the ceiling

Hayuya must compete in two different output classes and must never confuse them:

1. **Hero / high-quality master** — preserve the strongest available geometry and material evidence for close-up, cinematic, desktop/console, portfolio, offline render, and future rebakes. Do not decimate this asset merely to satisfy a mobile/runtime budget.
2. **Real-time derivatives** — build optimized game/mobile meshes, LODs, collision and texture variants *from the accepted high-quality master*.

The existence of 35k/80k/250k/500k face targets in current profiles is an execution/packaging policy, not a statement that Hayuya should stop there. When a backend can produce materially better source-faithful geometry above the requested runtime budget, preserve that high-detail source as an auditable master before retopology/LOD generation.

High-quality parity work must explicitly target:

- source-faithful high-density geometry without artificial low/medium-poly ceilings
- 4K PBR as the current minimum high-quality baseline and an **8K PBR parity path** where source/backend quality justifies it
- baseColor/albedo, normal, roughness, metallic and AO/occlusion preservation; emissive/opacity when present
- high-frequency detail retention through geometry, normals/displacement or rebaked maps instead of simply deleting detail
- clean UVs and a production-usable topology path
- close-up face/material/accessory fidelity for characters and monsters
- scale/orientation consistency and clean export to Unreal/Unity/Blender-class workflows
- high-quality master retained separately from LOD0-LOD3 and mobile derivatives
- Judge/QA comparisons against the original references at close and normal viewing distances

**Competitive rule:** Hayuya is not considered toe-to-toe with major image-to-3D web platforms merely because it can emit a GLB. It must be benchmarked against current Tripo, Meshy, Hyper3D/Rodin, 3D AI Studio and Kaedim-class workflows across fidelity, PBR/material quality, topology/retopo, reference handling, production readiness, and real-time derivation. High-quality/hero results are part of the core benchmark, not an optional future category.

## Mobile portability authority

When an asset is intended for a game/mobile/portable workflow, HAYUYA must consult:

- `tools/hayuya3d/mobile_portability.json` — machine-readable engine/hardware knowledge base and HAYUYA runtime budgets
- `docs/hayuya/HAYUYA_MOBILE_PORTABILITY_SPEC.md` — sourced research and rationale
- `tools/hayuya3d/mobile_portability.py` — executable tier resolver

Portable never means "make the master low quality."

The required sequence is:

1. reconstruct and preserve the strongest source-faithful **Hero Master**;
2. classify the requested runtime tier as `compatibility`, `balanced`, `high`, or `flagship`;
3. derive LOD0-LOD3, texture-size/compression targets and collision from that master;
4. keep material slots, transparency/overdraw and runtime shader assumptions portable;
5. retain Android ASTC as the preferred modern runtime texture path with ETC2 fallback, and use KTX2/Basis Universal packaging where the target runtime supports it;
6. treat frame time, draw calls, bandwidth, RAM, animation cost and sustained thermal headroom as first-class constraints alongside triangle count;
7. never present HAYUYA house triangle ranges as universal engine hard limits;
8. require real-device sustained profiling before calling a shipping asset portable.

Automatic tier mapping is:

- `preview` -> `compatibility`
- `mobile` -> `compatibility`
- `game` -> `balanced`
- `monster` -> `high`
- `ultra` -> `flagship`

An explicit `--portable-target` may override that mapping without changing the Hero Master.

## Physical mobile texture delivery

Portable Pack may physically transcode runtime LOD GLBs to **KTX2 + Basis Universal** using the pinned toolchain:

- @gltf-transform/cli 4.5.0
- Khronos KTX-Software 4.4.2

Policy:

- resize runtime textures to the selected tier ceiling before compression;
- encode normal / occlusion / metallic-roughness maps with UASTC for higher fidelity;
- encode remaining compatible maps with ETC1S;
- generate mipmaps;
- require and verify KHR_texture_basisu in the resulting GLB;
- verify every runtime image became image/ktx2;
- preserve the ordinary GLB sibling as a compatibility fallback;
- never call a Basis Universal payload native ASTC or native ETC2. Those are GPU-native delivery formats selected by the engine/runtime/build system after or instead of universal BasisU delivery.

Use --texture-delivery required when a job must fail rather than silently skip physical KTX2 generation.
## Portable Pack contract

For game/mobile/monster/ultra execution, Portable Pack should derive the following sibling packages directly from the accepted Hero Master:

- `portable/HeroMaster/master.glb` — exact preserved champion
- `portable/Flagship/` — tier manifest + runtime master/LOD0-LOD3/collision/turntable
- `portable/High/` — tier manifest + runtime master/LOD0-LOD3/collision/turntable
- `portable/Balanced/` — tier manifest + runtime master/LOD0-LOD3/collision/turntable
- `portable/Compatibility/` — tier manifest + runtime master/LOD0-LOD3/collision/turntable
- `portable/portable_pack_manifest.json`

Every tier must derive independently from Hero Master. Never generate High from Flagship, Balanced from High, or Compatibility from Balanced, because cascading simplification compounds geometry/material loss.

For unrigged assets, runtime LOD0 must pass through the tier material/texture derivation even when its geometry is already below the triangle ceiling. This prevents a low-poly Hero Master with an 8K authoring texture from being mislabeled as a Compatibility runtime asset.

For skinned assets, preserving JOINTS/WEIGHTS outranks blindly emitting LOD1-LOD3. Until skin-weight-preserving simplification is proven, report the missing chain explicitly rather than silently stripping the rig.

## Output contract

A completed Hayuya job should converge on:

- `hayuya_final.glb`
- `plan.json`
- `ranking.json`
- `manifest.json`
- candidate outputs for audit
- editable retopo OBJ + retopo manifest when smart retopology runs
- GamePrep master + LOD0-LOD3
- convex collision proxy when valid
- 8-frame turntable preview
- orientation-locked `source_vs_turntable.json`
- paired `source_vs_turntable.png` audit sheet
- GamePrep manifest
- four-tier Portable Pack + per-tier manifests

## Manual 8-view art workflow

The previous 8-view preview + individual-image process is still valid when the team intentionally wants art-directed references.

It is now an **optional high-control input workflow**, not a prerequisite for Hayuya.

For the full engine architecture see:

- `docs/hayuya/HAYUYA_MONSTER_ARCHITECTURE.md`
- `docs/hayuya/IMAGE_TO_3D_RESEARCH_2026.md`

Interpret **"use Hayuya"** as: ingest the complete real reference pool, expand only missing visual coverage, run the strongest permitted 3D pipeline, judge every candidate against all available real evidence, and return the best production-ready asset.
