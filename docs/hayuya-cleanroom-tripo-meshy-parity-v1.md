# HAYUYA Clean-Room Tripo/Meshy Parity v1

## Goal

Reproduce the observable production behavior of modern image-to-3D services without using stolen, leaked, private, or unauthorized proprietary source code.

HAYUYA treats hosted services as black boxes and uses only:
- public documentation,
- public APIs,
- publicly released model/code repositories,
- output behavior and artifact inspection,
- our own source-fidelity / geometry / material / rig QA.

## Public capability targets observed

### Meshy public API behavior (September 2026)

The current public API exposes enough behavior to define a production parity target:

- single-image and 1-4 image multi-view conditioning,
- geometry passes named standard / 2k / 4k,
- 2K / 4K / 8K base-color texture targets,
- PBR output (base color, metallic, roughness, normal; model-dependent emission),
- input image enhancement toggle,
- lighting removal / delighting for relightable textures,
- remesh / smart topology with requested polycount,
- natively separated parts in Smart Topology,
- A/T-pose requests,
- selectable target formats,
- UV unwrap, rigging, animation and retexture as distinct downstream operations.

This strongly suggests a staged production architecture rather than one monolithic image->GLB model.

## Open implementation pool

### VAST / Tripo
- VAST-AI-Research/TripoSR — public fast single-image reconstruction.
- VAST-AI-Research/TripoSG — MIT-licensed high-fidelity shape synthesis.
- TripoSG paper describes a large rectified-flow transformer, 3D VAE, SDF/normal/eikonal supervision and a multi-million-sample 3D data pipeline.

### Microsoft
- microsoft/TRELLIS.2 — MIT-licensed structured-latent 3D generation.
- HAYUYA already has local and cloud adapters.

### Tencent
- Tencent-Hunyuan/Hunyuan3D-2.1 — public image-to-3D plus production-oriented PBR material pipeline.
- HAYUYA already has a cloud adapter and material-donor path.

### Stability AI
- Stability-AI/stable-fast-3d — based on TripoSR, adds UV unwrapping, illumination disentanglement, texture/material generation and remeshing.
- Use only under the applicable Stability license/weight terms.

## HAYUYA parity architecture

1. INPUT CANONICALIZATION
   - alpha-aware foreground extraction
   - crop/scale normalization
   - preserve-source mode for identity-sensitive subjects

2. VIEW CONDITIONING
   - real multi-view images when supplied
   - generated auxiliary views only as secondary evidence
   - camera/view metadata retained in manifest

3. SHAPE TOURNAMENT
   - TripoSG
   - TRELLIS.2
   - Hunyuan3D
   - SF3D when locally configured
   - never silently replace a higher-quality candidate with a low-detail fallback

4. PROVIDER-NEUTRAL GEOMETRY QA
   - GLB structural validity
   - face / vertex census
   - finite geometry
   - duplicate / degenerate / non-manifold checks
   - component attachment and self-intersection checks

5. SOURCE-FIDELITY JUDGE
   - front / side / back source-vs-render checks
   - identity / face evidence for characters
   - hands / hair / eyes / mouth / clothing silhouette when referenced
   - reject visually wrong but structurally valid meshes

6. GEOMETRY FUSION / REPAIR
   - region-scoped donors only
   - front face repair must not overwrite side/back body geometry
   - head/hand/accessory repair is driven by the current input, never a hard-coded subject silhouette

7. TOPOLOGY PASS
   - preserve Hero Master before runtime decimation
   - smart remesh target based on asset role
   - separated components where downstream rigging benefits

8. MATERIAL PASS
   - UV validation / rebake
   - source-guided albedo
   - delight / illumination removal
   - PBR core: baseColor + roughness + normal; metallic when applicable
   - 4K minimum Hero target; 8K source textures allowed when justified

9. CHARACTER PASS
   - pose normalization only after source fidelity
   - autorig
   - deformation QA
   - animation compatibility check

10. PROMOTION
   - only the final HAYUYA acceptance gates decide what ships

## New router

`tools/hayuya3d/cleanroom_engine_router.py`

The router runs public/open candidates as a tournament and creates:
- one GLB per provider,
- `cleanroom_tournament.json`,
- `winner.glb`.

The router's numeric score is deliberately structural. It does not pretend that triangle count equals visual fidelity. Final promotion remains under HAYUYA Judge and the existing AAA acceptance contract.

### Example

```bash
python tools/hayuya3d/cleanroom_engine_router.py \
  --input subject.png \
  --output-dir out/hayuya_cleanroom \
  --providers triposg,trellis2,hunyuan
```

To enable local Stable Fast 3D:

```bash
export HAYUYA_SF3D_ROOT=/path/to/stable-fast-3d
python tools/hayuya3d/cleanroom_engine_router.py \
  --input subject.png \
  --output-dir out/hayuya_cleanroom \
  --providers sf3d,triposg,trellis2,hunyuan
```

## Non-goal

Do not ingest alleged leaked Tripo or Meshy server code, stolen model weights, private endpoints, bypassed authentication, or copied proprietary implementation. Personal-only usage does not make those artifacts technically trustworthy or legally clean, and they would contaminate HAYUYA's codebase.

The clean-room path is stronger for the game: every important stage remains replaceable, inspectable and under our control.
