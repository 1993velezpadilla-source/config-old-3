# HAYUYA product split

## HAYUYA 3D

Purpose: produce the highest-fidelity static 3D asset possible from image or multiview references.

HAYUYA 3D owns:

- source cleanup and reference conditioning;
- geometry generation;
- dense Hero Master preservation;
- geometry refinement;
- UV/PBR/material fidelity;
- face, anatomy, silhouette and appearance QA;
- GLB/OBJ export.

HAYUYA 3D does **not** own:

- skeleton generation;
- skinning;
- animation banks;
- gameplay motion;
- runtime/game LOD packaging;
- map assembly.

The approved `hayuya_final.glb` is treated as an immutable source asset. Downstream tools derive new files and never modify that Hero Master in place.

## HAYUYA Motions

Separate downstream product.

Input:

- approved HAYUYA 3D GLB/OBJ;
- `hayuya_motions_handoff.json`;
- optional motion profile / animation requirements.

Responsibilities:

- skeleton prediction;
- skin weights;
- bone cleanup;
- animation retargeting;
- animation generation;
- deformation QA;
- facial/secondary motion;
- gameplay-ready animated derivatives.

Candidate research stack includes UniRig / SkinTokens plus HAYUYA's existing rig and animation QA code.

## HAYUYA Map

Separate downstream product for assembling approved HAYUYA 3D assets into playable spaces.

Responsibilities may include:

- scene assembly;
- collision;
- portals/culling;
- nav/walkable surfaces;
- material batching;
- level streaming;
- XZIEL runtime packaging.

## Quality boundary

Generation quality and runtime optimization are intentionally decoupled.

```
references
   -> HAYUYA 3D
      -> AAA Hero Master
         -> HAYUYA Motions
         -> HAYUYA Map
         -> XZIEL-specific runtime optimization
```

No downstream triangle budget is allowed to reduce the HAYUYA 3D Hero Master before visual/anatomy approval.
