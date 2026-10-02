# HAYUYA — TOP WEB IMAGE-TO-3D PARITY BENCHMARK

Date established: 2026-09-23

## Mission

HAYUYA must compete directly with major image-to-3D production platforms, not only with lightweight/mobile asset generators.

Primary comparison set:
- Tripo
- Meshy
- Hyper3D / Rodin
- 3D AI Studio
- Kaedim

The benchmark has TWO equally important targets:

1. HERO / HIGH-QUALITY MASTER
2. REAL-TIME GAME DERIVATIVES

Mobile and low/medium-poly outputs are derivatives. They are not the quality ceiling.

## A. Hero / high-quality master target

The accepted hero asset must preserve the best geometry and material evidence available from the source references.

Required properties:
- no arbitrary mobile face ceiling
- preserve a dense source-faithful master before retopo/LOD
- 4K PBR minimum baseline when supported
- explicit 8K PBR parity roadmap
- baseColor/albedo
- normal
- roughness
- metallic
- AO/occlusion
- emissive and opacity when source material needs them
- UV preservation or rebake path
- high-frequency detail retained through geometry and/or baked maps
- close-up material and silhouette fidelity
- healthy topology or a validated production retopo derivative
- scale/orientation consistency
- Unreal / Unity / Blender usable export

## B. Real-time derivative target

From the accepted hero master, produce:
- LOD0
- LOD1
- LOD2
- LOD3
- mobile/low-budget variant when requested
- convex/simple collision
- turntable QA
- material-preserving simplification
- triangle-budget audit
- GamePrep manifest

Never destroy the hero master in order to make a runtime version.

## Competitive categories

Every benchmark asset is scored separately in these categories:

### Source fidelity
- silhouette agreement
- proportions
- asymmetric detail preservation
- backside plausibility
- fine geometry detail
- local-detail/close-up agreement
- identity consistency for characters

### Materials
- texture sharpness
- source color fidelity
- PBR completeness
- seams
- normal detail
- roughness/metallic plausibility
- high-resolution texture capability

### Mesh quality
- holes
- non-manifold geometry
- degenerate faces
- floating garbage
- disconnected components
- thin-part preservation
- usable topology
- retopo quality

### Production readiness
- GLB validity
- UV validity
- engine import
- orientation
- scale
- editable topology availability
- LOD generation
- collision generation
- rigging/animation readiness when applicable

### Reference handling
- one-photo result
- 2–4 photo result
- 8-view result
- large reference pack
- close-up/detail references
- conflicting/duplicate references
- generated-view use without overwriting real evidence

### Efficiency
- generation time
- VRAM requirement
- retries/failures
- deterministic manifests
- amount of manual cleanup required

## Test pack — 20 assets

### Characters / creatures
1. La Llorona full body
2. zombie humanoid
3. long-hair creature
4. asymmetric wounded character
5. clothed character with thin accessories

### Props
6. radio
7. lantern
8. machete
9. ornate cross
10. statue

### Furniture / hard surface
11. chair
12. table
13. cabinet
14. mechanical prop
15. damaged metal object

### Architecture-scale objects
16. altar
17. mausoleum
18. church facade / small chapel
19. doorway + trim assembly
20. architectural statue / column element

The environment/map generator will later use a separate benchmark because full scenes require scale systems, modular decomposition, repeated structures, collision/navmesh rules, and scene assembly. That future tool may reuse HAYUYA Judge, Material Bridge, Mesh Doctor and GamePrep technology but should not force object reconstruction logic to solve an entire map.

## Run matrix

For each applicable asset:
- 1 real image
- best available multi-reference set
- HAYUYA default/monster
- HAYUYA ultra/high-quality path
- competitor output using comparable source evidence
- hero-master comparison
- optimized real-time comparison

## Pass gates

HAYUYA cannot claim parity from a single attractive render.

A candidate passes only if:
- reference fidelity is competitive across multiple viewpoints
- no severe topology defect survives final QA
- material output is engine-usable
- the high-quality master is preserved
- runtime derivatives remain recognizably faithful to that master
- output opens/imports successfully in the target toolchain
- results and settings are reproducible from manifests

## Current known gap ledger

Do not hide these behind marketing language.

- Current TRELLIS.2 adapter accepts up to 4096 texture size.
- 8K PBR is therefore a parity target/gap, not yet a proven HAYUYA capability.
- Full GPU E2E across the heavy ensemble remains required before declaring production parity.
- Character auto-rigging/animation parity must be validated separately.
- High-quality topology/retopo must be evaluated visually as well as structurally.
- Major-platform comparisons must use the same or equivalent input evidence wherever possible.

## Win condition

HAYUYA should aim to:
- match the strongest competitor result on general image-to-3D fidelity often enough to be dependable,
- beat generic web tools on deep reference-pack usage, explicit evidence scoring, auditability and game-prep,
- retain a true hero master while also producing efficient runtime derivatives,
- specialize strongly for horror characters, monsters, props and architecture assets used by this project.

The core rule is simple:

**HIGH QUALITY FIRST. OPTIMIZATION SECOND. NEVER LET MOBILE BUDGETS DEFINE THE MASTER.**
