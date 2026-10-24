# Honor of Kings → Xziel Perceptual / Differentiable Asset Pipeline

Research date: 2026-09-21

## Why it matters

Honor of Kings targets an unusually broad mobile device range while maintaining a common visual identity. Tencent publicly described shipping 1080p/60-FPS rendering across varied hardware and built an automated asset-scaling pipeline around image-space error rather than only hand-authored LOD rules.

## Mythal differentiable renderer

Tencent's GDC 2023 session describes an in-house Hybrid Differentiable Renderer named Mythal combining rasterization and ray tracing.

Pipeline:
- render a high-quality reference;
- render candidate simplified asset;
- measure image-space rendering loss;
- backpropagate gradients through differentiable rendering stages;
- optimize material/mesh/skeleton parameters;
- emit the lowest-cost representation that stays inside the visual-loss target.

Public applications include:
- fitting full PBR appearance into cheaper material representations;
- auto skinning LOD;
- automatic mesh simplification;
- visibility baking.

## 2026 evolution

Tencent's later scalable-asset-pipeline material extends the same philosophy with differentiable rendering plus AIGC-assisted tooling. Geometry simplification and software-occlusion-related asset preparation use rendering loss and visual importance rather than geometry count alone.

## Xziel design

Add XzPerceptualCooker:

Inputs:
- master mesh/material/rig;
- reference camera set;
- lighting reference set;
- target backend/device tier;
- CPU/GPU/memory budgets;
- maximum perceptual error.

Outputs:
- simplified mesh or cluster hierarchy;
- reduced-bone rig;
- material recipe;
- texture packing/resolution;
- billboard/impostor candidate;
- visibility/occluder proxy.

Important: use image error as one signal, not the only signal. Gameplay silhouettes, head/limb hit regions, window edges and interactable geometry need semantic protection even if their screen-space error is small.

## Suggested score

candidateScore = visualError + silhouettePenalty + gameplayPenalty + memoryCostWeight + runtimeCostWeight

Near-player weapons/zombies get tighter error bounds than distant scenery.

## Public references

- GDC 2023: Differentiable Rendering for Scalable Asset Pipeline in Honor of Kings
  https://www.gdcvault.com/play/1029223/Machine-Learning-Summit-Differentiable-Rendering
- GDC 2023: Practical High-Performance Rendering On Mobile Platforms
  https://www.gdcvault.com/play/1029284/Practical-High-Performance-Rendering-On
- GDC: The Scalable Game Asset-Assisted Production Pipeline of Honor of Kings
  https://gdcvault.com/play/1035742/The-Scalable-Game-Asset-Assisted

## Clean-room rule

Xziel implements the optimization principles independently. No Honor of Kings assets/code are required.