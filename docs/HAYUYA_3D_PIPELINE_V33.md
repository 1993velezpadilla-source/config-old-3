# HAYUYA 3D Pipeline v33

The Stained Shade Tripo benchmark made one architectural problem obvious: **whole-body quality is not a useful single score**.

The observed Tripo model is extremely dense (~1.95M visible triangle faces) and reads well in cloth/silhouette, while the close-up face visibly degrades. HAYUYA therefore treats face quality and cloth/thin-surface quality as independent problems.

## Artifact chain

`input_conditioned`
→ `coarse_scene`
→ `semantic_shape`
→ `surface_master`
→ `parts`
→ `uv_master`
→ `texture_pbr_master`
→ `game_mesh`
→ `baked_game_materials`
→ `skeleton`
→ `skinned_asset`
→ `animation_validation`

The master reconstruction is never replaced by the runtime mesh.

## Dedicated face path

The face is evaluated independently for:
- landmark preservation;
- geometry preservation after surface refinement;
- texture alignment;
- eye/nose/mouth structural stability.

A beautiful robe does not allow a failed face to pass.

## Dedicated cloth path

Layered cloth/veils are evaluated independently for:
- thin-surface survival;
- layer separation;
- silhouette preservation;
- no accidental welding during retopology.

This specifically targets Stained Shade-style layered veils and torn robe edges.

## Reconstruction vs runtime

Reconstruction may be very high density. Runtime topology is a derived artifact.

High-density master → retopology → game mesh → detail bake.

This avoids throwing away facial or cloth detail merely because Android eventually needs a lower triangle count.

## Executable gate

`tools/hayuya_3d/quality_contract.py` validates that every required stage and region has evidence. It intentionally checks evidence presence before numeric thresholds; thresholds can then evolve per asset class without losing pipeline observability.

The current external benchmark record is stored in:
`tools/hayuya_3d/stained_shade_tripo_observed.v1.json`.
