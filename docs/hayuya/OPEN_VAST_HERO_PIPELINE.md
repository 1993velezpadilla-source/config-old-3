# HAYUYA Open VAST Hero Pipeline

This document records the clean-room/public-research path HAYUYA uses to approach
high-fidelity Tripo-class asset generation without depending on private Tripo
service internals.

## Rule

HAYUYA only integrates public code/models and documented public interfaces whose
licenses are compatible with the intended use. Private Tripo service algorithms,
credentials, hidden endpoints, or reverse-engineered server internals are not part
of this pipeline.

## Public building blocks

- **TripoSG** — VAST-AI-Research/TripoSG, MIT. High-fidelity single-image shape
  generation. The public Hugging Face demo exposes a simplify toggle; HAYUYA's
  Hero stage disables simplification and defers runtime retopology.
- **DetailGen3D** — VAST-AI-Research/DetailGen3D, MIT. Image-conditioned geometry
  enhancement from a detailed reference image plus a coarse mesh.
- **TripoSF / SparseFlex** — VAST-AI-Research/TripoSF, MIT. High-resolution
  arbitrary-topology reconstruction up to 1024^3; intended as the local/GPU
  ultra-refinement stage when a >=12 GB CUDA worker is available.
- **HoloPart** — VAST-AI-Research/HoloPart. Semantic 3D part decomposition for
  later component-aware editing/material/rig workflows.
- **UniRig / AniGen** — public VAST rigging research used only after geometry and
  material fidelity have passed.

## HAYUYA stage contract

```
source image(s)
  -> source conditioning / masks / face evidence
  -> high-end shape candidates
       - TRELLIS.2 public candidate (500k export ceiling)
       - unsimplified public TripoSG Hero challenger
  -> image-conditioned DetailGen3D geometry enhancement
  -> material reprojection / PBR preservation
  -> Hero Master fidelity gates
       - face
       - hands
       - cloth/open edges
       - accessories
       - silhouette / appearance
  -> optional TripoSF 1024^3 local refinement
  -> semantic parts
  -> retopology
  -> runtime LODs
  -> rig / skin / animation
```

## Hero Master policy

Runtime budgets are never fed back into high-end reconstruction.

Current profile targets:

| Profile | Hero Master target | Runtime target |
|---|---:|---:|
| Monster | 1,500,000 triangles | 250,000 triangles |
| Ultra | 2,000,000 triangles | 500,000 triangles |

A provider-specific export limit does not redefine the Hero target. A capped mesh
is considered a provisional high-end candidate and must go through a denser or
image-conditioned refinement path before HAYUYA treats it as the master.

## Current public-service constraints

Microsoft's public TRELLIS.2 Gradio Space currently rejects
`decimation_target > 500000`. HAYUYA therefore requests the legal 500k maximum,
records the provider cap explicitly, and sends the result into the open VAST Hero
challenger/refinement stages instead of retrying an invalid 1-2M request.

VAST's public TripoSG demo exposes `simplify=False`, which lets HAYUYA retain the
raw generated topology before runtime decimation.

VAST's public DetailGen3D demo accepts a reference image plus a coarse mesh and
returns image-conditioned refined geometry. HAYUYA aligns that geometry back to
the base mesh bounds and reprojects material evidence before Judge v4.

## Acceptance

No candidate is production-approved because of triangle count alone. Dense
geometry is only a preservation strategy. Judge v4/v5 and downstream anatomy,
appearance, material, deformation, and runtime gates remain authoritative.
