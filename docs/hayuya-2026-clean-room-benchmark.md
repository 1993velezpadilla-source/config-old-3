# HAYUYA 2026 clean-room workflow benchmark

Purpose: document public product capabilities/patterns that HAYUYA should match functionally without copying proprietary code, assets, branding, or exact UI.

## Public references reviewed

- Tripo Image-to-3D / Help Center
  - single + multi-view image generation
  - high-detail mesh, quad/triangle mesh controls
  - segmentation, retopology, AI texturing
  - auto-rigging + animation
  - public claims include up to 2M polygons and high-resolution texture workflows
  - https://www.tripo3d.ai/features/image-to-3d-model
  - https://www.tripo3d.ai/help/getting-started/what-features-does-tripo-have

- Meshy Image-to-3D / Features / Help Center
  - single + multi-view image generation
  - mesh inspection, remesh / polygon reduction
  - PBR texture workflows
  - browser auto-rig + animation library
  - workflow exposes generated asset first, optional refinement afterward
  - https://www.meshy.ai/features/image-to-3d
  - https://www.meshy.ai/features
  - https://help.meshy.ai/en/articles/9991738-what-features-does-meshy-have

- Hyper3D / Rodin
  - single or optional additional reference views
  - mesh and texture controls
  - clean topology / PBR positioning
  - async task model and downloadable artifacts
  - https://hyper3d.ai/features
  - https://docs.hyper3d.ai/en/get-started/features

- Rokoko Motion Library
  - motion browsing organized as a library
  - fast preview before selection
  - category/filter driven discovery
  - https://support.rokoko.com/hc/en-us/articles/4410021327121-Getting-Started-Rokoko-Studio-Motion-Library

## HAYUYA product rules derived from the benchmark

1. Preview-first
   - The current model stays visible while choosing refinements.
   - Never substitute a mannequin or donor character as the user's model preview.
   - Unsafe rig output falls back to the clean static model.

2. Progressive workflow, not one giant form
   - Generate
   - Inspect
   - Model / texture
   - Rig / motion
   - Audio / FX
   - Build / export

3. Mobile-first tool drawers
   - Primary tools are one-tap bottom actions.
   - Advanced controls live under More.
   - Never use nested tiny scroll views.
   - One interaction panel at a time.

4. Multi-view is a first-class input
   - Primary reference + additional views + detail references.
   - Preserve all input references in job metadata.
   - Quality pipeline may use detail references for later refinement.

5. Honest geometry / texture quality
   - Display real face count, texture resolution and quality-gate state.
   - Do not advertise 4K/8K when the active generation provider only produced 2K.
   - High/Ultra should increase real generation effort or route to a provider capable of the requested target.

6. Rigging must be visual-quality gated
   - Bone existence is insufficient.
   - Require weighted-joint coverage.
   - Compare rigged rest mesh to the original clean model.
   - Sample every candidate animation for deformation.
   - Publish only per-clip safe subsets.
   - Head/face local deformation has tighter thresholds.

7. Motion discovery must be semantic
   - Zombie Recommended
   - Crawlers
   - Walk / Shamble
   - Chase
   - Attacks
   - Hit Reactions
   - Deaths
   - Idles
   - Generic / Utility
   Internal clip IDs remain stable; UI labels are human-readable.

8. Audio / FX preview must fail visibly
   - Audio preview automatically skips an unavailable file in a pool.
   - Browser autoplay rejection is reported to the user.
   - FX preview has explicit cleanup/reset.
   - Build must refuse unresolved local references.

9. Export is a gate, not a blind button
   - Character packages require safe rig + selected deformation-safe clips.
   - Audio files must exist and be non-empty.
   - Motion systems must match the asset profile.
   - Game-ready is false on unresolved/unsafe dependencies.

10. CI is part of the product
   - DOM/static integrity
   - phone-size interaction smoke
   - audio/motion catalog integrity
   - rig weighted-bone gate
   - deformation/reference-fidelity gate
   - package fail-closed behavior

## Current HAYUYA differentiator

HAYUYA is not trying to be a desktop DCC replacement. It is a phone-first game-asset production surface where creation, preview, rigging, motion, audio, FX and game-ready packaging are one validated pipeline.
