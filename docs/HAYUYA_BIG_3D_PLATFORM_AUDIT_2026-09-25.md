# HAYUYA — Audit of large image-to-3D platforms and character pipelines
Date: 2026-09-25

## Executive finding

The large services are not doing one single "photo -> triangle soup -> rig" operation. Their public products and the open research closest to them show a multi-stage pipeline: image preprocessing / subject isolation, geometry generation or reconstruction, topology cleanup or a topology-specific generation mode, texture/material synthesis, semantic part handling, then rig/skin/animation. For characters, pose conditioning or a human/body prior is often inserted before or during geometry generation.

The "white ragdoll/template" hypothesis is **partly correct for character-specialized reconstruction**, but it is **not a universal explanation for general image-to-3D**.

* Generic object generators such as TRELLIS.2 generate a learned 3D representation directly; they are not documented as wrapping a stock human mesh.
* Human-specific systems such as ECON, ICON and SiTH explicitly fit SMPL/SMPL-X body models and then reconstruct clothing/high-frequency surface detail around that fitted body. This is the closest public match to "start from a white human base and conform it to the photo."
* Meshy exposes pose control before generation (A-pose, T-pose or custom joint pose). Its exact model internals are proprietary, but the public behavior proves pose is an upstream generation condition, not merely something added after texturing.
* Tripo's public API separates generation, segmentation, retopology, texture, rig-check, rigging and animation retargeting. The VAST research team behind Tripo also publishes TripoSG/TripoSF and, in 2026, AniGen, which directly co-generates mesh + skeleton + skin weights.

## What can actually be proven

### Meshy

Confirmed from Meshy documentation:
1. Input enhancement/background cleanup can happen before 3D generation.
2. Image-to-3D can use one image or multi-view inputs.
3. Character pose can be forced to A-pose, T-pose or a custom joint pose *during generation*.
4. Meshy exposes a high-detail Standard mesh and a Smart Topology path.
5. Its help center explicitly describes an uncolored white base mesh stage before texturing.
6. Texture generation is a separate stage and supports PBR maps and lighting removal.
7. Remesh, part splitting, rigging and animation are downstream stages.

Not disclosed: the exact neural architecture, exact internal Blender scripts, or whether Blender runs on Meshy's servers.

### Tripo

Confirmed from Tripo API/docs:
1. Single-image and multiview generation are separate supported paths.
2. The current generation families expose explicit geometry controls; P2 can generate native quad output.
3. Texture is a separate endpoint with PBR, delight/removal of baked lighting, multi-angle reference images and independent texture seeds.
4. Mesh segmentation is a separate semantic stage; v2 can use a reference image.
5. Retopology/decimation is a separate stage and can bake textures onto the optimized mesh.
6. Rigging is a separate task and Tripo tells clients to run a rig-compatibility check first.
7. Animation retargeting happens after a valid rig.

Open research from the team behind Tripo:
* TripoSG: image-conditioned rectified-flow transformer + SDF VAE, trained on large Image/SDF data. DINOv2 and RMBG are acknowledged dependencies.
* TripoSF / SparseFlex: high-resolution sparse surface representation (up to 1024^3) designed to preserve open surfaces and sharp topology.
* AniGen: directly predicts Shape + Skeleton + Skin in a shared representation. This is especially important for HAYUYA because it attacks the brittleness of sequential "generate bad static mesh, then auto-rig it."

Important: these public research repositories show Tripo/VAST technology directions, but they do **not** prove that the Tripo production website runs those exact checkpoints or exact source files.

### Hyper3D / Rodin

Confirmed from current Rodin Gen-2.5 API:
1. Up to five input images.
2. Separate generation tiers controlling resolved geometric detail.
3. Raw triangle and Quad mesh modes.
4. A quad-normal option explicitly bakes high-resolution geometry detail into a normal map during mesh refinement.
5. Texture quality is independent of geometry tier and can reach very high texture resolutions.

This is direct evidence of a high-resolution master -> topology/refinement -> normal-bake/material route, rather than treating polygon count and texture resolution as the same quality dial.

Not disclosed: exact model architecture or use of Blender internally.

### Hunyuan3D 2.1

Its open source pipeline is unusually explicit:
1. Background removal.
2. Shape diffusion / flow-matching generation.
3. Optional remesh.
4. UV unwrap.
5. Render normal and position maps from selected camera views.
6. Multiview PBR texture diffusion conditioned by the input image plus rendered geometry maps.
7. Image super-resolution.
8. Bake the multiview images back to UV textures.
9. Inpaint unobserved texture regions.
10. Export OBJ/GLB.

The repository includes Blender Python (bpy) in its requirements, but its core generation is neural 3D + mesh processing; this is not evidence that Meshy/Tripo/Rodin secretly use Blender as their generator.

### TRELLIS.2

Confirmed open pipeline:
1. Masked image input / image features.
2. Sparse structure generation.
3. Shape structured-latent generation.
4. Texture/material structured-latent generation.
5. O-Voxel decode to arbitrary-topology geometry and PBR attributes.
6. CuMesh utilities for mesh post-processing, remeshing, decimation and UV work.

TRELLIS.2 specifically advertises a compact field-free O-Voxel representation and a streamlined conversion path. It is not a stock humanoid-template pipeline.

## Why T-pose/A-pose keeps appearing

A/T poses are canonical **rigging poses**. They reduce ambiguity at shoulders/armpits, separate the arms from the torso, make automatic joint placement and weight transfer easier, and make motion retargeting predictable.

There are three different ways a service can arrive there:
1. Generate directly in a pose-conditioned A/T pose (Meshy publicly exposes this).
2. Fit a parametric body/skeleton to the input and canonicalize the body before reconstructing clothing/detail (SMPL/SMPL-X style research pipelines).
3. Re-pose/retarget an already generated character before auto-rigging.

So the T-pose itself is not evidence that a service started with a premade white model, but human-template fitting is a real and widely used technique.

## Human/template route: the public systems closest to Christian's hypothesis

### SMPL/SMPL-X family + ECON / ICON / SiTH

This route is fundamentally different from HAYUYA's current generic one-shot path.

Typical sequence:
1. Detect/crop human.
2. Estimate body joints/pose.
3. Fit a parameterized body mesh (SMPL/SMPL-X: body, hands, face depending on variant).
4. Predict front/back normal or appearance information.
5. Reconstruct the clothed surface around the fitted body.
6. Refine high-frequency geometry.
7. Transfer/retain the known skeleton and skinning relationship.
8. Texture and animate.

ECON explicitly combines high-frequency front/back surface normals with low-frequency SMPL-X surface guidance. SiTH explicitly downloads/fits SMPL-X, hallucinates the unseen back view, then reconstructs a textured human.

Licensing warning: ECON/DECA/SMPL-X-family assets have research/non-commercial or separate model terms. They are useful to understand the architecture but must not be silently embedded into a commercial HAYUYA release.

### Face-specific route

A face should not be treated as just another patch of a generic 3D object's triangle soup.

Public systems such as DECA/FLAME reconstruct:
* face/head shape parameters,
* pose,
* expression,
* dense detail/displacement,
* landmarks,
* optional albedo/texture.

For HAYUYA this suggests a dedicated head/face pass: detect face -> fit/estimate head structure -> fuse/transfer the result into the body/head region -> preserve eyelid/mouth loops -> then final retopo/texture bake. A dedicated face route is much closer to production character tooling than hoping a generic image-to-3D generator allocates enough coherent topology to the face.

## Blender tools worth keeping as external tooling

These are not proven to be what the proprietary websites run internally. They are open tools that implement production stages HAYUYA needs.

* Blender Rigify: built-in auto rigging, including face rigs.
* Blender QuadriFlow: built-in quad remeshing.
* MPFB2: parametric Blender human generator; useful for canonical base-body experiments. Code GPLv3; bundled assets CC0.
* MB-Lab: Blender humanoid morph, measurements, skeleton and face-rig scripts (GPL).
* BlenRig: automated biped rigging/skinning with a strong facial system (GPL).
* Instant Meshes: BSD field-aligned automatic quad retopology.

Keep GPL tools as separate Blender/external processes rather than copying their Python directly into a differently licensed HAYUYA codebase.

## What HAYUYA was missing

The failed Monja run exposed the architectural gap.

Current bad route:
image -> generic shape generator -> catastrophic mesh gate -> texture gate -> auto-rig -> animation

That only proves the file is technically a mesh and the rig moves it. It does not prove the character has a coherent human body, face, hands, clothing topology, or useful deformation topology.

Recommended character route:
image(s)
-> subject/background isolation + enhancement
-> classify humanoid/creature
-> 2D pose + body landmarks + face landmarks
-> canonical character scaffold (skeleton/body prior OR joint shape/skeleton generation)
-> dense character geometry
-> dedicated face/head refinement
-> clothing/open-surface refinement
-> visual/reference similarity gate
-> anatomy/face/hand gate
-> topology reconstruction / quad retopo
-> UVs + PBR material generation + delight
-> high-res detail bake to normal/displacement
-> semantic part segmentation
-> rig/skin validation
-> motion/animation
-> game LOD/export

The decisive change is that **rigging is no longer allowed to rescue or legitimize a bad mesh**.

## HAYUYA experiments to run next

A. AniGen character challenger
- Use the Monja primary image.
- Generate mesh + skeleton + skin jointly.
- Render front/3/4/profile/head close-up.
- Compare against current TRELLIS.2 and reject before animation if facial/anatomy gates fail.

B. Human-prior challenger
- Research-only proof using SiTH/ECON-style SMPL-X fitting.
- Measure whether canonical body proportions/head placement/hands are materially better.
- Do not ship restricted code/assets.

C. Generic high-detail challenger
- TripoSG geometry -> optional TripoSF/SparseFlex-style high-res reconstruction/refinement.
- Run reference and face crops through appearance gates.
- Retopo only after the dense master passes visual/anatomical QA.

D. Surface/material pass
- Borrow the *architecture* of Hunyuan3D Paint: geometry-conditioned multiview texture generation, super-resolution, UV bake/inpaint.
- Keep geometry quality and texture quality as separate gates.

E. Blender postprocess
- Smooth/repair normals.
- QuadriFlow/Instant Meshes/other retopo.
- Preserve a dense master.
- Bake dense-master geometric detail to normal/displacement onto game topology.
- Rigify/BlenRig only after topology is coherent.

## Source lock

The companion file `tools/hayuya3d/external_research_tools.lock.json` pins the public source snapshots audited here. The bootstrap script downloads source code only and keeps third-party code outside HAYUYA production sources.
