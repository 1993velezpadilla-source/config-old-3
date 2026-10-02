# HAYUYA 3D — 2026 Public Image-to-3D Research Notes

Research date: 2026-09-23.

Purpose: capture public product behavior and open research that can improve Hayuya without copying private code or bypassing access controls.

## Tripo

Public developer docs show a modular production pipeline rather than a single opaque "image-to-3D" button.

Observed public capabilities:

- Image to Multiview: one image -> front/left/back/right.
- Multiview to Model: at least two views including front; four canonical slots supported.
- H3.1: image/text/multiview input, high-fidelity mesh + PBR, up to 2M faces in Ultra.
- P-series: dedicated low-poly generation; P2 supports quad output.
- Image autofix for weak inputs.
- Independent geometry/model seed and texture seed.
- Texture alignment can prioritize the original image or geometry.
- Dedicated texture regeneration.
- Semantic mesh segmentation.
- Mesh completion: AI completion or quick cap.
- Smart retopology / face limits / quad option.
- Rig check, auto-rig and animation retargeting.

Open research from the Tripo/VAST team is especially useful to Hayuya:

- TripoSR — MIT; very fast feed-forward single-image reconstruction.
- TripoSG — MIT; 1.5B rectified-flow high-fidelity image-to-shape model.
- TripoSF / SparseFlex — MIT; high-resolution sparse reconstruction up to 1024^3 and strong handling of open/complex topology.

### Hayuya lesson

Do not treat reconstruction, view generation, texturing, mesh repair, topology reduction and rigging as one indivisible model call. They should be independent stages that can be replaced and judged separately.

Public references:

- https://developers.tripo3d.ai/en/docs/introduction
- https://developers.tripo3d.ai/en/docs/generation-image-to-multiview
- https://developers.tripo3d.ai/en/docs/generation-multiview-to-model/standard
- https://developers.tripo3d.ai/en/docs/models-texture
- https://developers.tripo3d.ai/en/docs/mesh-complete
- https://developers.tripo3d.ai/en/docs/mesh-decimate
- https://github.com/VAST-AI-Research/TripoSR
- https://github.com/VAST-AI-Research/TripoSG
- https://github.com/VAST-AI-Research/TripoSF

## Meshy

Public Meshy 7.1 API docs expose several production knobs worth copying at the architecture level:

- multi-image generation accepts 1–4 images of the same object
- first image is the primary/front reference
- Ultra multi-image geometry uses a 2K geometry pass
- image-to-3D exposes 4K geometry
- PBR generation
- independent texture reference images
- texture resolutions up to 8K in documented flows
- remesh toggle
- triangle/quad topology
- target polygon count
- save pre-remeshed master
- A-pose option
- image enhancement and de-lighting
- GLB outputs
- rigging/animation exist as post-processing tools

### Hayuya lesson

Always preserve a high-resolution/master candidate before game optimization. Geometry generation and game retopology must be separate artifacts.

Public references:

- https://docs.meshy.ai/en/api/image-to-3d
- https://docs.meshy.ai/en/api/multi-image-to-3d
- https://docs.meshy.ai/en/api/ai

## Microsoft TRELLIS.2

TRELLIS.2 is a 4B MIT-licensed image-to-3D system using O-Voxel structured latents.

Public characteristics:

- full PBR surface attributes
- open surfaces
- non-manifold geometry
- internal enclosed structures
- 512^3 / 1024^3 / 1536^3 generation modes
- 24GB+ NVIDIA GPU requirement in the official README
- direct GLB extraction with remesh/decimation/texture-size controls
- dedicated shape-conditioned PBR texture generation

### Hayuya lesson

O-Voxel-style sparse representations are a strong fit for torn zombie clothing, hair cards/sheets, foliage, straps, thin props and other geometry that classic closed SDF assumptions often damage.

Public reference:

- https://github.com/microsoft/TRELLIS.2

## Microsoft TRELLIS

Classic TRELLIS remains important because its public pipeline exposes:

`run_multi_image(images, mode="stochastic" | "multidiffusion")`

The official demo states the algorithm is experimental rather than a separately trained multiview model, but it provides a real open-source path for using two user photographs as simultaneous conditioning.

### Hayuya lesson

When two real images exist, feed them jointly to at least one native multiview reconstruction path. Do not simply select one and discard the other.

Public reference:

- https://github.com/microsoft/TRELLIS
- https://github.com/microsoft/TRELLIS/blob/main/example_multi_image.py

## InstantMesh

InstantMesh is Apache-2.0 and combines:

1. customized Zero123++ sparse-view generation
2. sparse-view Large Reconstruction Model
3. mesh/FlexiCubes extraction

The official run path creates six synthesized views before reconstruction.

### Hayuya lesson

A single photo can become a richer reconstruction problem by first predicting structured sparse views. This is the basis of Hayuya ViewForge.

Public reference:

- https://github.com/TencentARC/InstantMesh

## Wonder3D

Wonder3D is MIT and explicitly generates both:

- consistent multi-view RGB images
- corresponding multi-view normal maps

It then fuses normals for reconstruction.

The public project notes also identify a critical real-photo problem: fixed orthographic assumptions can distort geometry, and later Era3D work estimates focal length/elevation.

### Hayuya lesson

View synthesis should include geometry evidence (normals/depth), not only RGB. Hayuya Judge v2 should score normal and camera consistency, especially for photographs with perspective.

Public reference:

- https://github.com/xxlong0/Wonder3D

## PSHuman

PSHuman is MIT and is a specialist path for clothed humans from one image using cross-scale multiview diffusion.

Public notes:

- SMPL-free mode exists
- detailed human reconstruction
- very high VRAM requirement in the public implementation

### Hayuya lesson

Humanoid/zombie reconstruction should eventually route through a specialist candidate in addition to general object generators.

Public reference:

- https://github.com/pengHTYX/PSHuman

## Hunyuan3D-2.1

Hunyuan3D-2.1 publicly separates:

- shape generation
- PBR texture generation

It is technologically useful as a reference architecture, but its current community license is not as frictionless as MIT/Apache.

Important license observations from the public license:

- territory restrictions apply
- commercial-scale conditions exist
- redistribution/notice obligations exist
- outputs/results cannot be used to improve another AI model except allowed Hunyuan derivatives

### Hayuya decision

Keep Hunyuan as an explicit opt-in backend, not as the identity of Hayuya and not as the default commercial core.

Public reference:

- https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1

## Hyper3D Rodin Gen-2.5

Rodin's current public v2 API is another useful production reference.

Public behavior:

- image-to-3D accepts 1-5 ordered images
- the first image is used for material generation
- tiers separate speed/detail from downstream mesh/material controls
- PBR output is explicit
- raw/quad-style mesh controls exist across Rodin families
- Gen-2.5 Extreme-High can return an additional mesh up to roughly 10M faces
- texture generation is a separate endpoint and supports 2K/4K PBR outputs
- older Rodin 1/1.5 docs expose useful multi-image semantics: `concat` for views of one object and `fuse` for combining features

### Hayuya lesson

Multi-image input should preserve ordering and confidence. A high-resolution master should be an optional independent artifact, while texture generation should stay separable from geometry.

Public references:

- https://docs.hyper3d.ai/en/api-specification/rodin-gen2-5
- https://docs.hyper3d.ai/en/api-specification/rodin-gen1-1-5
- https://docs.hyper3d.ai/en/api-specification/generate-texture

## Stability AI SPAR3D / Stable Fast 3D

SPAR3D extends Stable Fast 3D with a point-cloud-conditioned reconstruction path intended to improve unseen/backside geometry from a single image. Its public CLI can also return the generated point cloud, bake textures and optionally remesh when the extra remesh dependencies are installed.

Stable Fast 3D remains useful as a fast UV/material-aware baseline.

Both currently use the Stability AI Community License rather than MIT/Apache. That license includes commercial registration/revenue conditions and restrictions on using model outputs to create or improve other foundational generative AI models.

### Hayuya decision

Pin both for optional comparison, but keep them disabled by default. SPAR3D gets an executable opt-in adapter because backside recovery is directly relevant to the one-photo goal.

Public references:

- https://github.com/Stability-AI/stable-point-aware-3d
- https://github.com/Stability-AI/stable-fast-3d

## Architecture extracted from the market

The recurring winning pattern across modern tools is:

1. **Input repair**
   - background removal
   - crop/scale
   - de-lighting
   - image enhancement
2. **View expansion**
   - generate missing angles
   - estimate camera
   - predict normals/depth
3. **Shape generation**
   - high-resolution master
   - multiple seeds/models
4. **Validation**
   - compare source to re-render
   - mesh health
   - view consistency
5. **Repair**
   - segmentation
   - part completion
   - hole filling
6. **Material**
   - source-aligned PBR
   - retexture without changing shape
7. **Topology**
   - smart low-poly / quads
   - target platform budget
8. **Character processing**
   - rig check
   - skeleton
   - skin weights
9. **Export**
   - GLB/FBX
   - LODs
   - preview
   - manifest

Hayuya Monster adopts this as a vendor-neutral pipeline rather than cloning any proprietary implementation.

## What we deliberately did not do

- no access-control bypass
- no stolen/leaked source
- no private API discovery
- no credential interception
- no proxying around authentication/credits
- no assumption that a proprietary web UI equals permission to copy its backend

Only public documentation, public behavior and open-source repositories are used as the engineering source material.

## DINOv2 / VGGT evaluation decisions

### DINOv2

The original DINOv2 model card identifies the classic vision backbones as Apache-2.0. Hayuya pins the public repository at:

`7764ea0f912e53c92e82eb78a2a1631e92725fc8`

Judge v3 uses only the original `dinov2_vits14` LVD-142M path. Newer specialized Cell-DINO/X-Ray-DINO variants in the same repository have different/restricted licenses and are explicitly out of scope for the default Hayuya evaluator.

### MEt3R

MEt3R itself is MIT and is a useful architectural reference for feature-space multi-view consistency. Its implementation bundles/depends on MASt3R/DUSt3R-family components whose licensing is non-commercial, so Hayuya does not make the complete MEt3R stack a default commercial dependency.

Pinned research SHA:

`ee0e1752898559e1a3e85e2e151d3edeb9b55f73`

### VGGT

VGGT can infer cameras, depth, point maps and tracks across one, a few or many views and is highly relevant to future camera/depth Judge layers. Its commercial checkpoint and repository use custom terms/access rather than the permissive MIT/Apache policy of Hayuya's default core.

Pinned research SHA:

`a288dd0f14786c93483e45524328726ab7b1b4ce`

Decision: keep VGGT camera/depth integration opt-in until the intended checkpoint/license is explicitly reviewed.

## Evaluation research: source and multi-view consistency

Modern image-to-3D quality needs more than polygon counts.

### MEt3R

MEt3R (2025) measures multi-view consistency by using DUSt3R to obtain dense pairwise 3D correspondences, warping one view into another, and comparing learned image features in aligned regions.

Hayuya does not need the full method for its dependency-light v2 judge, but the architecture is directly relevant to Judge v3:

- infer correspondence between candidate renders and source/synthetic views
- warp into a common frame
- compare learned features instead of raw pixels
- tolerate view-dependent appearance changes

### Differentiable ray/view consistency

Earlier reconstruction work formalized consistency between 3D geometry and 2D observations using ray consistency over masks, depth, color and semantic evidence.

Hayuya Judge v2 applies the same core product principle in a lightweight form: a generated 3D candidate must explain the actual 2D evidence.

### Hayuya evaluation ladder

1. **Judge v1** — topology/material/production health.
2. **Judge v2** — implemented software silhouette camera search against every real source photo.
3. **Judge v3** — DINO/MEt3R-style feature consistency, normal/depth agreement and calibrated camera estimation.

References:

- https://arxiv.org/abs/2501.06336
- https://arxiv.org/abs/1704.06254

## Priority after v1

1. ViewForge executable Wonder3D/normal stage.
2. Camera estimation for real photos.
3. Candidate re-renderer.
4. Source-view similarity Judge v2.
5. TripoSF microgeometry/refinement.
6. Generic PBR projection from all source/synthetic views.
7. Automatic LOD + collision pack.
8. Zombie/humanoid rig specialist.
9. Semantic part segmentation and repair.
10. Optional official Tripo/Meshy API adapters for comparison, never as mandatory dependencies.
