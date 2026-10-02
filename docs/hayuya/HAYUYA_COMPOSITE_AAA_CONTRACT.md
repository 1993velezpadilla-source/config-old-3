# HAYUYA Composite Champion + AAA Acceptance

Status: active engineering contract  
Branch: `art/hayuya-monster-v1`

## Principle

HAYUYA does not treat the highest global candidate score as the final truth.

The final asset may be a **Composite Champion** assembled from the strongest compatible evidence among finalists. Every transfer creates a new challenger. No donor is copied blindly and no original finalist is overwritten.

"AAA" in HAYUYA means the internal acceptance contract in `tools/hayuya3d/aaa_acceptance.py`. It is not an external certification or marketing claim.

## Champion hierarchy

1. Generate diverse candidates.
2. Run complete real-source Judge.
3. Select the strongest globally shippable base.
4. Build a regional quality matrix for the top finalists.
5. Select regional donors.
6. Execute only transfers whose safety contract is implemented.
7. Rebuild topology-dependent material evidence.
8. Re-run the full Judge.
9. Run Mesh Doctor, source-vs-turntable, rig/animation and runtime QA.
10. Promote only if the composite is monotonic or meaningfully superior without critical regressions.

## Regional DNA matrix

The planner currently tracks:

- global shape / silhouette
- global appearance
- face identity, including the weakest explicit face reference
- face geometry density
- face texel allocation
- face visible texture detail
- material response
- texture resolution
- detached accessory evidence

The intended expansion is:

### Head and identity
- cranium and skull silhouette
- jaw/chin
- cheeks
- nose bridge/tip/nostrils
- lips and philtrum
- eyelids and eye socket depth
- ears
- forehead/brow
- facial asymmetry
- scars, wounds and zombie-specific deformation
- facial microdetail and pores
- beard/moustache stubble
- headwear contact and occlusion

### Eyes
- sclera/iris/pupil separation
- corneal bulge
- catchlight plausibility
- wetline / tear line
- eyelash geometry/cards
- eye convergence
- gaze symmetry
- eyelid contact with eyeball
- eye material roughness/refraction policy

### Mouth
- lip seal
- mouth cavity depth
- teeth/gums/tongue separation
- dental silhouette
- open-mouth topology
- zombie teeth damage
- tongue and gum materials
- expression-safe interior

### Hair
- hair silhouette
- scalp coverage
- strand/card density
- card orientation
- alpha edge quality
- anisotropy readiness
- hairline continuity
- eyebrow and facial-hair continuity

### Upper body
- shoulder width/slope
- clavicle/neck transition
- chest/back silhouette
- garment folds
- armor/clothing layer separation
- sleeve/armpit deformation zones

### Arms and hands
- elbow anatomy
- wrist transition
- palm volume
- individual fingers
- nail geometry/material
- finger spacing
- hand pose neutrality
- skin-weight quality around knuckles

### Lower body
- pelvis/hip silhouette
- thigh/knee/calf anatomy
- footwear
- cloth/pants folds
- ankle transition
- sole contact plane

### Accessories
- disconnected accessory preservation
- donor accessory uniqueness
- alignment to body
- penetration/intersection
- attachment anchor
- material matching
- rig attachment

## Transfer classes

### A. Topology-preserving material challenger — implemented

Donor material evidence can be projected onto the untouched base topology through Material Bridge.

Rules:

- base geometry/topology must remain exact;
- candidate is never auto-promoted;
- candidate re-enters complete Judge;
- weakest facial evidence cannot regress;
- FaceTex / FaceDetail cannot regress;
- normal/AO blockers remain explicit if topology-dependent evidence becomes stale.

### B. Seam-aware head wrap — implemented as regional fusion core

`regional_fusion.py`:

- unskinned only;
- donor normalized to base bounds;
- upper-head region only;
- smooth neck falloff;
- displacement clamp;
- seam drift bound;
- bbox drift bound;
- normal/AO rebake required when present;
- not Judge-eligible until required rebake succeeds.

### C. Local texture/detail transfer — next

Do not use a whole-body material projection when only the face donor is superior.

Required design:

- identify base head UV footprint;
- generate donor-to-base local correspondence;
- project only allowed semantic region;
- feather atlas boundary in texture space;
- preserve unrelated base pixels exactly;
- preserve alpha;
- rebuild mip-safe padding;
- measure color/structure discontinuity across seam;
- compare face Judge before/after.

### D. Detached component swap — next

Suitable for hair, jewelry, hats, armor pieces, props and other disconnected components.

Required gates:

- source component must be marked accessory candidate by Part Map;
- whole-body alignment confidence;
- component/body penetration check;
- duplicate-accessory detection;
- attachment distance;
- scale/orientation plausibility;
- Mesh Doctor after merge;
- rig attachment policy for characters.

### E. Soft body-region geometry fusion — guarded future

Face, hands, torso and limbs cannot be copied by triangle slicing.

Required:

- semantic correspondence or robust surface correspondence;
- boundary loop / falloff;
- local ARAP-like deformation or wrap;
- UV continuity;
- tangent-space material rebuild;
- skin-weight transfer when skinned;
- blendshape/morph transfer if present;
- seam curvature/normal continuity metrics;
- complete re-Judge.

## Skin/rig transfer contract

A geometry donor is not allowed to modify a skinned character until HAYUYA can prove:

- JOINTS/WEIGHTS survive or are transferred;
- per-vertex weights remain normalized;
- joint indices are valid;
- influence count is bounded;
- inverse bind matrices stay valid;
- bind-pose deformation is stable;
- elbow/knee/shoulder/wrist/neck deformation tests pass;
- animations retain finite transforms;
- donor region does not introduce exploding vertices;
- LOD skinning parity passes.

For face/head fusion additionally:

- jaw joint relationship;
- eye joints if present;
- facial bones if present;
- blendshape/morph-target transfer if present;
- expression test suite.

## Seam acceptance

A composite transfer must measure more than topology validity.

Future seam QA should include:

- positional discontinuity
- normal discontinuity
- tangent discontinuity
- curvature discontinuity
- UV seam delta
- baseColor seam delta
- roughness seam delta
- normal-map seam energy
- AO discontinuity
- silhouette discontinuity across multiple views
- self-intersection near transfer boundary

The boundary should be evaluated under neutral lighting and high-contrast raking light.

## Face identity contract

If explicit face close-ups exist:

- every reference must be evaluated;
- aggregate face score is recorded;
- weakest individual face score is recorded;
- regional detail evidence is balanced so multiple torso references cannot dilute one face reference;
- a refinement/composite cannot regress the weakest face score;
- identity evidence is required for final acceptance.

Even without explicit close-ups, characters require measurable:

- FaceMesh
- FaceTex
- FaceDetail

## Material contract

For high-end Hero Master:

- baseColor target met;
- roughness present;
- normal present;
- topology-dependent normal evidence rebaked after geometry change;
- AO/occlusion rebuilt where the pipeline requires it;
- no black/flat texture output;
- no silent PBR channel loss;
- source-consistency guard for super-resolution;
- texture donor cannot modify base geometry.

Future material gates:

- skin SSS/transmission policy
- eye material policy
- hair anisotropy policy
- metal dielectric correctness
- energy-conserving roughness/metal response
- channel color-space validation
- normal handedness
- tangent basis validation
- mip/bleed-safe UV padding
- texel density variance by semantic region
- no oversharpen/noise masquerading as detail

## Geometry contract

- finite vertices
- no duplicate faces
- no degenerate faces
- no non-manifold edges
- consistent winding
- intentional open boundaries only
- no collapsed bbox axis
- local face density evidence
- accessory components preserved unless explicitly rejected
- high-risk repair never deletes small components automatically

Future geometry gates:

- self-intersection
- zero-thickness slivers
- inverted shells
- interpenetrating body/clothing
- eye/eyelid penetration
- mouth interior collision
- hand/finger fusion
- foot-ground plausibility
- cloth thickness where required

## Animation/deformation contract

Character AAA acceptance requires a validated rig and animation clips.

Future deformation suite:

- neutral idle
- walk/run
- crouch
- aim
- reload hand pose
- head yaw/pitch
- jaw/open-mouth
- shoulder extreme
- elbow extreme
- wrist extreme
- knee extreme
- ankle extreme

Measure:

- volume collapse
- joint candy-wrapper deformation
- vertex explosion
- body/clothing penetration
- detached accessories
- face/neck seam under animation

## LOD contract

Every runtime tier derives independently from the Hero Master.

Never derive a higher-quality tier from a lower-quality tier.

LOD tests should measure:

- silhouette delta
- face identity delta
- face texture/detail delta
- material channel parity
- rig/skin parity
- animation parity
- UV/material rebake completion
- accessory preservation
- screen-space error
- transition popping

## Mobile/portable parity

Portable quality is not merely triangle count.

Test:

- Vulkan/mobile shader path
- texture format/transcode path
- mip chain
- memory budget
- draw-call/material binding budget
- skinning cost
- animation cost
- LOD transition
- normal/roughness readability on mobile
- face readability at gameplay camera distance
- thermal/power tiers
- flagship/high/balanced/compatibility independent derivation

## Image-to-3D temporal/view consistency

Future Judge layers:

- front ↔ 3/4 ↔ side identity consistency
- side ↔ back transition
- symmetry only where source evidence supports symmetry
- preserve intentional asymmetry
- texture landmark stability across turntable
- no texture swimming
- no view-dependent hallucinated accessories
- no face change between angles
- calibrated camera/lens evidence

## Composite promotion contract

A composite candidate must:

1. remain a separate challenger;
2. pass structural QA;
3. pass source fidelity;
4. pass regional face evidence;
5. pass material contract;
6. pass rebakes;
7. pass rig/animation when character;
8. pass source-vs-turntable;
9. pass runtime packaging;
10. beat or match the base on protected monotonic metrics.

If a better regional donor exists but cannot yet be fused safely, internal AAA acceptance stays blocked. HAYUYA should prefer an honest blocker over a false green badge.

## Acceptance philosophy

The goal is not to make metrics say 100.

The goal is to make it difficult for a visually broken asset to become green.

Every new discovered failure mode should become one of:

- a generator/refiner improvement,
- a regional donor opportunity,
- a rejection guard,
- a new QA measurement,
- a regression fixture,
- or a permanent acceptance gate.
