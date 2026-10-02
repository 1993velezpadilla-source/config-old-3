# HAYUYA 3D limit audit — 2026-09-27

## Result

HAYUYA 3D now targets **2,000,000 triangle faces** for its Ultra AAA Hero Master.

There is **no configured HAYUYA vertex hard cap**. Vertex count is measured and reported, not used as an early-decimation target.

The nun benchmark observed:

- 1,938,984 triangles
- 1,023,652 vertices

That benchmark vertex count is an observed result, not a documented Tripo maximum.

## Tripo public limit

Tripo H3.1 documents:

- Standard triangle maximum: 1,500,000
- Ultra triangle maximum: 2,000,000
- Quad maximum: 150,000

Tripo's public developer docs do not publish an independent maximum vertex count.

Sources:

- https://developers.tripo3d.ai/en/models/v3-1
- https://developers.tripo3d.ai/en/docs/generation-image-to-model

## HAYUYA code limits

Current profile table:

- preview Hero target: 30,000 triangles
- mobile Hero target: 120,000
- game Hero target: 400,000
- monster Hero target: 1,500,000
- ultra Hero target: 2,000,000

The HAYUYA mesh gate does not reject a mesh for being above a vertex ceiling.

The direct TRELLIS.2 CUDA adapter now enforces a HAYUYA production triangle target of at most 2,000,000 while preserving the upstream 16,777,216-face nvdiffrast preview safety stage.

## Provider limits versus model limits

The current Microsoft TRELLIS.2 public Hugging Face Space exposes only 100,000–500,000 as its public decimation control. That is a **service/UI constraint**, not the open-source model's intrinsic mesh limit.

The upstream TRELLIS.2 source decodes the latent mesh before GLB extraction and only applies the 16,777,216-face safety simplification for rendering. Its postprocess API accepts a configurable decimation target.

A community MIT TRELLIS.2 wrapper, `visualbruno/ComfyUI-Trellis2`, exposes a simplification target control up to 30,000,000 faces. HAYUYA does not need the entire ComfyUI wrapper, but this validates that the public 500k Space ceiling is not a fundamental CuMesh/TRELLIS.2 geometry limit.

Sources:

- https://huggingface.co/spaces/microsoft/TRELLIS.2/blob/main/app.py
- https://github.com/microsoft/TRELLIS.2
- https://github.com/visualbruno/ComfyUI-Trellis2

## Open high-density options

### TRELLIS.2 direct

Best match for the 2M target when HAYUYA has a CUDA worker. HAYUYA's direct adapter now requests the 2M target rather than inheriting the public Space's 500k slider.

### TripoSG

Open MIT model. Its official CLI defaults to `faces=-1`, so simplification is disabled unless explicitly requested.

### TripoSF / SparseFlex

Open MIT high-resolution arbitrary-topology refinement. Supports up to 1024^3 reconstruction and is intended for dense cloth/open-surface detail. It does not publish a fixed output face cap.

### DetailGen3D

Image-conditioned geometry enhancement. Useful for restoring geometry from the original source image after a coarse candidate, but public ZeroGPU duration limits make the hosted demo unreliable as a production backend. Local/direct GPU execution is preferred.

## Product boundary

HAYUYA 3D no longer defaults to retopology, GamePrep, portable packs, texture delivery, rigging or animation. It exports the approved AAA Hero Master unchanged.

Rigging and motion move to **HAYUYA Motions**. Scene/runtime assembly moves to **HAYUYA Map**.
